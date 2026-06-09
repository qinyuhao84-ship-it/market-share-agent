from __future__ import annotations

import copy
import json
import re
import threading
from typing import Any, Iterable, Sequence

from inference import InferenceConfig

from .config import (
    CHAPTER1_DIRECT_GENERATION_ONLY,
    CHAPTER1_MODEL_MODE,
    CHAPTER1_MODEL_NAME,
    SECTION_LOOKUP,
    SECTION_SPECS,
    TASK_TERMINAL_STATUSES,
)
from .deepseek_client import DeepSeekV4ProChapter1Client
from .export_gate import validate_chapter1_exportable
from .legacy_adapter import semantic_draft_to_legacy_sections
from .models import (
    Chapter1GenerationContext,
    Chapter1SemanticDraft,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    Chapter1TaskCreateRequest,
    Chapter1TaskSnapshot,
    Chapter1TaskStatus,
    Chapter1Source,
)
from .repair_service import Chapter1RepairService
from .replay_writer import Chapter1ReplayWriter
from .section_generator import Chapter1SectionGenerator
from .task_store import Chapter1TaskNotFoundError, chapter1_task_store
from .validators import validate_draft, validate_section


class Chapter1TaskService:
    def __init__(self, store=chapter1_task_store) -> None:
        self.store = store
        self._cache_lock = threading.RLock()
        self._result_cache: dict[str, Chapter1TaskSnapshot] = {}

    def start_task(self, request: Chapter1TaskCreateRequest) -> Chapter1TaskSnapshot:
        chapter1_context = self._normalize_request_context(request)
        normalized_request = request.model_copy(
            update={
                "model_name": CHAPTER1_MODEL_NAME,
                "enable_web_retrieval": False,
                "allow_incomplete_export": bool(request.allow_incomplete_export),
                "chapter1_context": chapter1_context,
            }
        )
        snapshot = self.store.create(normalized_request)
        snapshot.model_name = CHAPTER1_MODEL_NAME
        snapshot.model_mode = CHAPTER1_MODEL_MODE
        snapshot.generation_mode = str(normalized_request.generation_mode or "strict")
        snapshot.use_cache = bool(normalized_request.use_cache)
        snapshot.enable_web_retrieval = False
        snapshot.allow_incomplete_export = bool(normalized_request.allow_incomplete_export)
        snapshot.chapter1_context = chapter1_context.model_copy(deep=True)
        snapshot.current_stage = "已排队"
        snapshot.updated_at = snapshot.created_at
        snapshot.diagnostics = self._build_diagnostics()
        snapshot = self.store.save_snapshot(snapshot)

        if normalized_request.use_cache:
            cached = self._get_cached_snapshot(normalized_request)
            if cached is not None:
                cached_copy = self._clone_cached_snapshot(cached, snapshot.task_id, normalized_request)
                snapshot = self.store.save_snapshot(cached_copy)
                return snapshot

        return snapshot

    def run_task(self, task_id: str) -> None:
        try:
            self._run_task_inner(task_id)
        except Exception as exc:  # pragma: no cover - defensive
            self._mark_task_failed_by_exception(task_id, exc)

    def _run_task_inner(self, task_id: str) -> None:
        try:
            snapshot = self.store.get(task_id)
        except Chapter1TaskNotFoundError:
            return

        if snapshot.status.value in TASK_TERMINAL_STATUSES and snapshot.status != Chapter1TaskStatus.QUEUED:
            return

        snapshot = self._set_running(snapshot)
        draft_sections: list[Chapter1SemanticSection] = []
        generation_records: list[dict[str, Any]] = []
        repair_records: list[dict[str, Any]] = []
        raw_model_outputs: list[dict[str, Any]] = []
        parsed_outputs: list[dict[str, Any]] = []
        validation_results: list[dict[str, Any]] = []
        warnings = list(snapshot.warnings or [])
        errors = list(snapshot.errors or [])

        section_generator = self._new_section_generator()
        repair_service = self._new_repair_service()
        chapter1_context = self._build_generation_context(snapshot)

        total = len(SECTION_SPECS)
        completed_summaries: list[str] = []

        for index, spec in enumerate(SECTION_SPECS, start=1):
            if self.store.should_cancel(task_id):
                snapshot = self._mark_cancelled(snapshot)
                snapshot.warnings = _unique([*warnings, *snapshot.warnings])
                snapshot.errors = _unique(errors)
                self.store.save_snapshot(snapshot)
                return

            section_key = str(spec["key"])
            section_title = str(spec["title"])
            snapshot.current_section = section_title
            base_progress = int(((index - 1) / total) * 100)
            snapshot.current_stage = "准备生成"
            snapshot.progress = max(snapshot.progress, base_progress, 1 if index == 1 else base_progress)
            snapshot.updated_at = _now()
            self.store.save_snapshot(snapshot)

            section_warnings: list[str] = []
            section_errors: list[str] = []
            sources = self._sources_from_context_for_section(chapter1_context, section_key)
            section_warnings.append(f"{section_title}：已使用结构化上下文和事实包生成，不进行本地联网检索。")

            snapshot.current_stage = "DeepSeek 生成"
            snapshot.progress = max(snapshot.progress, base_progress + 3)
            snapshot.updated_at = _now()
            self.store.save_snapshot(snapshot)
            try:
                section = section_generator.generate_section(
                    company_name=snapshot.company_name,
                    product_name=snapshot.product_name,
                    section_spec=dict(spec),
                    sources=sources,
                    completed_section_summaries=list(completed_summaries),
                    chapter1_context=chapter1_context,
                    generation_mode=snapshot.generation_mode,
                )
                generation_records.append(copy.deepcopy(section_generator.last_record))
                raw_model_outputs.append(
                    {
                        "section_key": section_key,
                        "raw_output": section_generator.last_raw_output,
                        "messages": copy.deepcopy(section_generator.last_messages),
                    }
                )
                parsed_outputs.append(
                    {
                        "section_key": section_key,
                        "parsed_output": copy.deepcopy(section_generator.last_parsed_output),
                    }
                )
            except Exception as exc:
                error_text = f"{exc.__class__.__name__}: {exc}"
                section_errors.append(error_text)
                warnings.append(f"{section_title} 生成失败：{error_text}")
                section = Chapter1SemanticSection(
                    section_id=section_key,
                    section_title=section_title,
                    section_goal=str(spec.get("section_goal") or ""),
                    content_blocks=[],
                    sources=list(sources),
                    status=Chapter1SectionStatus.FAILED,
                    validation_score=0,
                    validation_issues=[error_text],
                    missing_items=[section_title],
                    repair_attempts=0,
                    warnings=[error_text],
                )
                generation_records.append(
                    {
                        "section_key": section_key,
                        "section_title": section_title,
                        "error": error_text,
                        "messages": copy.deepcopy(getattr(section_generator, "last_messages", [])),
                    }
                )
                raw_model_outputs.append(
                    {
                        "section_key": section_key,
                        "raw_output": "",
                        "messages": copy.deepcopy(getattr(section_generator, "last_messages", [])),
                    }
                )
                parsed_outputs.append(
                    {
                        "section_key": section_key,
                        "parsed_output": {},
                    }
                )

            section.sources = list(sources)
            snapshot.current_stage = "结构校验"
            snapshot.updated_at = _now()
            validated = validate_section(
                section,
                spec,
                company_name=snapshot.company_name,
                chapter1_context=chapter1_context,
            )
            validation_results.append(
                {
                    "section_key": section_key,
                    "section_title": section_title,
                    "status": validated.status.value,
                    "validation_score": validated.validation_score,
                    "validation_issues": list(validated.validation_issues or []),
                    "missing_items": list(validated.missing_items or []),
                }
            )

            if _needs_repair(validated):
                snapshot.current_stage = "自动补写"
                snapshot.updated_at = _now()
                validated = repair_service.repair_section(
                    section=validated,
                    section_spec=dict(spec),
                    product_name=snapshot.product_name,
                    company_name=snapshot.company_name,
                    sources=sources,
                    chapter1_context=chapter1_context,
                    repair_mode=self._repair_mode_for_section(validated, spec),
                    validation_issues=list(validated.validation_issues or []),
                )
                repair_records.append(copy.deepcopy(repair_service.last_record))
                section_warnings.extend(repair_service.last_record.get("warnings", []))
                validation_results.append(
                    {
                        "section_key": section_key,
                        "section_title": section_title,
                        "status": validated.status.value,
                        "validation_score": validated.validation_score,
                        "validation_issues": list(validated.validation_issues or []),
                        "missing_items": list(validated.missing_items or []),
                        "after_repair": True,
                    }
                )

            draft_sections.append(validated)
            completed_summaries.append(_section_summary(section_title, validated))
            warnings.extend(section_warnings)
            errors.extend(section_errors)
            snapshot.progress = max(snapshot.progress, int((index / total) * 100))
            snapshot.current_stage = "已完成"
            snapshot.updated_at = _now()
            snapshot.warnings = _unique(warnings)
            snapshot.errors = _unique(errors)
            self.store.save_snapshot(snapshot)

        draft = Chapter1SemanticDraft(
            draft_id=f"{snapshot.task_id}-draft",
            task_id=snapshot.task_id,
            company_name=snapshot.company_name,
            product_name=snapshot.product_name,
            model_name=CHAPTER1_MODEL_NAME,
            model_mode=CHAPTER1_MODEL_MODE,
            sections=draft_sections,
            sources=_dedupe_sources([source for section in draft_sections for source in section.sources]),
            warnings=_unique(warnings),
            replay_file_path="",
        )
        draft = validate_draft(draft, company_name=snapshot.company_name, chapter1_context=chapter1_context)
        legacy_sections = semantic_draft_to_legacy_sections(draft)

        snapshot.semantic_draft = draft
        snapshot.legacy_sections = legacy_sections
        snapshot.retrieval_records = []
        snapshot.generation_records = generation_records
        snapshot.repair_records = repair_records
        snapshot.raw_model_outputs = raw_model_outputs
        snapshot.parsed_outputs = parsed_outputs
        snapshot.validation_results = validation_results
        snapshot.warnings = _unique([*warnings, *draft.warnings])
        snapshot.errors = _unique(errors)
        snapshot.diagnostics = self._build_diagnostics()
        snapshot.progress = 100
        snapshot.current_section = ""
        snapshot.current_stage = "整理输出"
        snapshot.updated_at = _now()

        snapshot.status, snapshot.can_export = _derive_task_status(draft.sections)
        snapshot = self._apply_export_gate(snapshot)

        replay_writer = self._new_replay_writer()
        snapshot.replay_file_path = replay_writer.write(snapshot)
        if snapshot.semantic_draft is not None:
            snapshot.semantic_draft.replay_file_path = snapshot.replay_file_path
        snapshot.updated_at = _now()
        self.store.save_snapshot(snapshot)

        if snapshot.can_export:
            self._store_cache(snapshot)

    def retry_section(self, task_id: str, section_key: str) -> Chapter1TaskSnapshot:
        snapshot = self.store.get(task_id)
        section_key = str(section_key or "").strip()
        if not section_key:
            raise Chapter1TaskNotFoundError("小节不存在")
        if snapshot.semantic_draft is None:
            raise Chapter1TaskNotFoundError("任务尚未生成语义草稿")

        spec = SECTION_LOOKUP.get(section_key)
        if spec is None:
            raise Chapter1TaskNotFoundError("小节不存在")

        section_map = {
            str(section.section_id or "").strip(): section
            for section in snapshot.semantic_draft.sections or []
        }
        existing_sections = list(snapshot.semantic_draft.sections or [])
        chapter1_context = self._build_generation_context(snapshot)
        completed_summaries = [
            _section_summary(item.section_title, item)
            for item in existing_sections
            if str(item.section_id or "").strip() != section_key
        ]

        section_generator = self._new_section_generator()
        repair_service = self._new_repair_service()
        sources = self._sources_from_context_for_section(chapter1_context, section_key)

        section = section_generator.generate_section(
            company_name=snapshot.company_name,
            product_name=snapshot.product_name,
            section_spec=dict(spec),
            sources=sources,
            completed_section_summaries=completed_summaries,
            chapter1_context=chapter1_context,
            generation_mode=snapshot.generation_mode,
        )
        section.sources = list(sources)
        section = validate_section(
            section,
            spec,
            company_name=snapshot.company_name,
            chapter1_context=chapter1_context,
        )
        if _needs_repair(section):
            section = repair_service.repair_section(
                section=section,
                section_spec=dict(spec),
                product_name=snapshot.product_name,
                company_name=snapshot.company_name,
                sources=sources,
                chapter1_context=chapter1_context,
                repair_mode=self._repair_mode_for_section(section, spec),
                validation_issues=list(section.validation_issues or []),
            )

        updated_sections = []
        for item in existing_sections:
            if str(item.section_id or "").strip() == section_key:
                updated_sections.append(section)
            else:
                updated_sections.append(item)

        snapshot.semantic_draft = validate_draft(
            snapshot.semantic_draft.model_copy(update={"sections": updated_sections}),
            company_name=snapshot.company_name,
            chapter1_context=chapter1_context,
        )
        snapshot.legacy_sections = semantic_draft_to_legacy_sections(snapshot.semantic_draft)
        snapshot.generation_records.append(copy.deepcopy(section_generator.last_record))
        if repair_service.last_record:
            snapshot.repair_records.append(copy.deepcopy(repair_service.last_record))
        snapshot.raw_model_outputs.append(
            {
                "section_key": section_key,
                "raw_output": section_generator.last_raw_output,
                "messages": copy.deepcopy(section_generator.last_messages),
            }
        )
        snapshot.parsed_outputs.append(
            {
                "section_key": section_key,
                "parsed_output": copy.deepcopy(section_generator.last_parsed_output),
            }
        )
        snapshot.validation_results.append(
            {
                "section_key": section_key,
                "section_title": section.section_title,
                "status": section.status.value,
                "validation_score": section.validation_score,
                "validation_issues": list(section.validation_issues or []),
                "missing_items": list(section.missing_items or []),
            }
        )
        snapshot.warnings = _unique([*snapshot.warnings, *section.warnings])
        snapshot.diagnostics = self._build_diagnostics()
        snapshot.replay_file_path = self._new_replay_writer().write(snapshot)
        if snapshot.semantic_draft is not None:
            snapshot.semantic_draft.replay_file_path = snapshot.replay_file_path
        snapshot.progress = 100
        snapshot.current_section = ""
        snapshot.current_stage = "整理输出"
        snapshot.status, snapshot.can_export = _derive_task_status(snapshot.semantic_draft.sections)
        snapshot = self._apply_export_gate(snapshot)
        snapshot.updated_at = _now()
        self.store.save_snapshot(snapshot)
        if snapshot.can_export:
            self._store_cache(snapshot)
        return snapshot

    def repair_section(self, task_id: str, section_key: str) -> Chapter1TaskSnapshot:
        snapshot = self.store.get(task_id)
        section_key = str(section_key or "").strip()
        if not section_key:
            raise Chapter1TaskNotFoundError("小节不存在")
        if snapshot.semantic_draft is None:
            raise Chapter1TaskNotFoundError("任务尚未生成语义草稿")
        spec = SECTION_LOOKUP.get(section_key)
        if spec is None:
            raise Chapter1TaskNotFoundError("小节不存在")

        section_map = {
            str(section.section_id or "").strip(): section
            for section in snapshot.semantic_draft.sections or []
        }
        section = section_map.get(section_key)
        if section is None:
            raise Chapter1TaskNotFoundError("小节不存在")

        chapter1_context = self._build_generation_context(snapshot)
        sources = self._sources_from_context_for_section(chapter1_context, section_key)
        repair_service = self._new_repair_service()
        repaired = repair_service.repair_section(
            section=section,
            section_spec=dict(spec),
            product_name=snapshot.product_name,
            company_name=snapshot.company_name,
            sources=sources,
            chapter1_context=chapter1_context,
            repair_mode=self._repair_mode_for_section(section, spec),
            validation_issues=list(section.validation_issues or []),
        )

        updated_sections = []
        for item in snapshot.semantic_draft.sections or []:
            if str(item.section_id or "").strip() == section_key:
                updated_sections.append(repaired)
            else:
                updated_sections.append(item)

        snapshot.semantic_draft = validate_draft(
            snapshot.semantic_draft.model_copy(update={"sections": updated_sections}),
            company_name=snapshot.company_name,
            chapter1_context=chapter1_context,
        )
        snapshot.legacy_sections = semantic_draft_to_legacy_sections(snapshot.semantic_draft)
        if repair_service.last_record:
            snapshot.repair_records.append(copy.deepcopy(repair_service.last_record))
        snapshot.validation_results.append(
            {
                "section_key": section_key,
                "section_title": repaired.section_title,
                "status": repaired.status.value,
                "validation_score": repaired.validation_score,
                "validation_issues": list(repaired.validation_issues or []),
                "missing_items": list(repaired.missing_items or []),
                "repair_only": True,
            }
        )
        snapshot.warnings = _unique([*snapshot.warnings, *repaired.warnings])
        snapshot.diagnostics = self._build_diagnostics()
        snapshot.replay_file_path = self._new_replay_writer().write(snapshot)
        if snapshot.semantic_draft is not None:
            snapshot.semantic_draft.replay_file_path = snapshot.replay_file_path
        snapshot.progress = 100
        snapshot.current_section = ""
        snapshot.current_stage = "整理输出"
        snapshot.status, snapshot.can_export = _derive_task_status(snapshot.semantic_draft.sections)
        snapshot = self._apply_export_gate(snapshot)
        snapshot.updated_at = _now()
        self.store.save_snapshot(snapshot)
        if snapshot.can_export:
            self._store_cache(snapshot)
        return snapshot

    def cancel_task(self, task_id: str) -> Chapter1TaskSnapshot:
        return self.store.cancel(task_id)

    def _set_running(self, snapshot: Chapter1TaskSnapshot) -> Chapter1TaskSnapshot:
        snapshot.status = Chapter1TaskStatus.RUNNING
        snapshot.current_stage = "开始生成"
        snapshot.progress = 0
        snapshot.diagnostics = self._build_diagnostics()
        snapshot.updated_at = _now()
        return self.store.save_snapshot(snapshot)

    def _mark_cancelled(self, snapshot: Chapter1TaskSnapshot) -> Chapter1TaskSnapshot:
        snapshot.status = Chapter1TaskStatus.CANCELLED
        snapshot.cancelled = True
        snapshot.current_stage = "已取消"
        snapshot.updated_at = _now()
        return snapshot

    def _new_config(self) -> InferenceConfig:
        return InferenceConfig()

    def _new_section_generator(self) -> Chapter1SectionGenerator:
        config = self._new_config()
        return Chapter1SectionGenerator(DeepSeekV4ProChapter1Client(config), config)

    def _new_repair_service(self) -> Chapter1RepairService:
        config = self._new_config()
        return Chapter1RepairService(DeepSeekV4ProChapter1Client(config), config)

    def _new_replay_writer(self) -> Chapter1ReplayWriter:
        return Chapter1ReplayWriter()

    def _cache_key(self, request: Chapter1TaskCreateRequest) -> str:
        context_payload = request.chapter1_context.model_dump(mode="json") if request.chapter1_context else {}
        return "|".join(
            [
                str(request.company_name or "").strip().lower(),
                str(request.product_name or "").strip().lower(),
                CHAPTER1_MODEL_NAME,
                CHAPTER1_MODEL_MODE,
                str(request.generation_mode or "strict"),
                "allow" if request.allow_incomplete_export else "strict",
                json.dumps(context_payload, ensure_ascii=False, sort_keys=True),
            ]
        )

    def _get_cached_snapshot(self, request: Chapter1TaskCreateRequest) -> Chapter1TaskSnapshot | None:
        key = self._cache_key(request)
        with self._cache_lock:
            cached = self._result_cache.get(key)
            if cached is None:
                return None
            return cached.model_copy(deep=True)

    def _store_cache(self, snapshot: Chapter1TaskSnapshot) -> None:
        request = Chapter1TaskCreateRequest(
            company_name=snapshot.company_name,
            product_name=snapshot.product_name,
            chapter1_context=snapshot.chapter1_context.model_copy(deep=True),
            use_cache=snapshot.use_cache,
            enable_web_retrieval=False,
            allow_incomplete_export=snapshot.allow_incomplete_export,
            generation_mode=snapshot.generation_mode if snapshot.generation_mode in {"balanced", "strict", "fast"} else "strict",
            model_name=snapshot.model_name,
        )
        key = self._cache_key(request)
        with self._cache_lock:
            self._result_cache[key] = snapshot.model_copy(deep=True)

    def _clone_cached_snapshot(
        self,
        cached: Chapter1TaskSnapshot,
        task_id: str,
        request: Chapter1TaskCreateRequest,
    ) -> Chapter1TaskSnapshot:
        cloned = cached.model_copy(deep=True)
        cloned.task_id = task_id
        cloned.company_name = str(request.company_name or "").strip()
        cloned.product_name = str(request.product_name or "").strip()
        cloned.model_name = CHAPTER1_MODEL_NAME
        cloned.model_mode = CHAPTER1_MODEL_MODE
        cloned.generation_mode = str(request.generation_mode or "strict")
        cloned.use_cache = bool(request.use_cache)
        cloned.enable_web_retrieval = False
        cloned.allow_incomplete_export = bool(request.allow_incomplete_export)
        cloned.chapter1_context = request.chapter1_context.model_copy(deep=True)
        cloned.status = cached.status
        cloned.cancelled = False
        cloned.created_at = _now()
        cloned.updated_at = cloned.created_at
        cloned.progress = 100 if cloned.can_export else cloned.progress
        cloned.diagnostics = self._build_diagnostics()
        if cloned.semantic_draft is not None:
            cloned.semantic_draft.task_id = task_id
            cloned.semantic_draft.model_name = CHAPTER1_MODEL_NAME
            cloned.semantic_draft.model_mode = CHAPTER1_MODEL_MODE
            cloned.semantic_draft.draft_id = f"{task_id}-draft"
        return cloned

    def _build_diagnostics(self) -> dict[str, Any]:
        return {
            "model_name": CHAPTER1_MODEL_NAME,
            "model_mode": CHAPTER1_MODEL_MODE,
            "direct_generation_only": CHAPTER1_DIRECT_GENERATION_ONLY,
            "local_retrieval": "disabled",
            "web_retrieval_disabled": True,
        }

    def _mark_task_failed_by_exception(self, task_id: str, exc: Exception) -> None:
        try:
            snapshot = self.store.get(task_id)
        except Chapter1TaskNotFoundError:
            return

        error_text = f"{exc.__class__.__name__}: {exc}"
        snapshot.status = Chapter1TaskStatus.FAILED
        snapshot.current_stage = "任务异常失败"
        snapshot.current_section = ""
        snapshot.errors = _unique([*snapshot.errors, error_text])
        snapshot.warnings = _unique([*snapshot.warnings, f"第一章任务异常失败：{error_text}"])
        snapshot.can_export = False
        snapshot.diagnostics = self._build_diagnostics()
        snapshot.updated_at = _now()

        try:
            replay_writer = self._new_replay_writer()
            snapshot.replay_file_path = replay_writer.write(snapshot)
            if snapshot.semantic_draft is not None:
                snapshot.semantic_draft.replay_file_path = snapshot.replay_file_path
        except Exception:
            pass

        self.store.save_snapshot(snapshot)

    def _normalize_request_context(self, request: Chapter1TaskCreateRequest) -> Chapter1GenerationContext:
        context = request.chapter1_context.model_copy(deep=True)
        raw_product_name = str(context.raw_product_name or request.product_name or "").strip()
        normalized_product_name = str(context.normalized_product_name or "").strip()
        if not normalized_product_name:
            normalized_product_name = raw_product_name
        normalized_product_name = _normalize_formal_product_name(normalized_product_name or raw_product_name)
        context.raw_product_name = raw_product_name
        context.normalized_product_name = normalized_product_name
        context.product_code = str(context.product_code or request.product_code or "").strip()
        context.product_intro = str(context.product_intro or request.product_intro or "").strip()
        market_scope = context.market_scope.model_copy(deep=True)
        market_scope.market_name = str(market_scope.market_name or request.market_name or "").strip()
        if not market_scope.parent_market and market_scope.market_name:
            market_scope.parent_market = ""
        context.market_scope = market_scope
        return context

    def _build_generation_context(self, snapshot: Chapter1TaskSnapshot) -> Chapter1GenerationContext:
        context = snapshot.chapter1_context.model_copy(deep=True)
        raw_product_name = str(context.raw_product_name or snapshot.product_name or "").strip()
        context.raw_product_name = raw_product_name
        context.normalized_product_name = _normalize_formal_product_name(
            str(context.normalized_product_name or raw_product_name or snapshot.product_name or "").strip()
        )
        if not context.product_code:
            context.product_code = ""
        if not context.product_intro:
            context.product_intro = ""
        return context

    def _sources_from_context_for_section(
        self,
        context: Chapter1GenerationContext,
        section_key: str,
    ) -> list[Chapter1Source]:
        sources: list[Chapter1Source] = []
        for fact in context.evidence_facts or []:
            allowed_sections = [str(item).strip() for item in (fact.allowed_sections or []) if str(item).strip()]
            if allowed_sections and section_key not in allowed_sections:
                continue
            fact_text = str(fact.fact or "").strip()
            if not fact_text:
                continue
            source_id = str(fact.fact_id or "").strip() or f"fact_{len(sources) + 1:03d}"
            sources.append(
                Chapter1Source(
                    source_id=source_id,
                    title=str(fact.title or fact.source_title or source_id).strip() or source_id,
                    url=str(fact.url or "").strip(),
                    publisher=str(fact.source_title or fact.title or "").strip(),
                    retrieved_at="",
                    source_type=str(fact.type or "general").strip() or "general",
                    reliability_level=str(fact.type or "unknown").strip() or "unknown",
                    related_sections=allowed_sections,
                    extracted_facts=[fact_text],
                    raw_excerpt=fact_text,
                )
            )
        return sources

    def _repair_mode_for_section(self, section: Chapter1SemanticSection, spec: dict) -> str:
        section_key = str(spec.get("key") or "").strip()
        required_block_types = [
            str(item).strip()
            for item in (spec.get("required_block_types") or [])
            if str(item).strip()
        ]
        actual_types = [str(block.block_type or "").strip() for block in section.content_blocks or []]
        if section_key == "industry_supply_chain" and actual_types != required_block_types:
            return "rewrite_quality"
        blocking_issue_markers = (
            "异常标点",
            "企业名称",
            "重复度",
            "套话",
            "冒号",
            "长度不足",
            "参数化表达",
            "内容块数量",
            "缺少必要块类型",
            "主题覆盖不足",
            "偏离市场口径",
            "标签式表达",
        )
        if any(any(marker in issue for marker in blocking_issue_markers) for issue in (section.validation_issues or [])):
            return "rewrite_quality"
        if not section.content_blocks or not section.missing_items:
            return "rewrite_quality"
        return "fill_missing"

    def _apply_export_gate(self, snapshot: Chapter1TaskSnapshot) -> Chapter1TaskSnapshot:
        export_ok, export_issues = validate_chapter1_exportable(snapshot)
        if export_ok:
            snapshot.can_export = snapshot.status in {Chapter1TaskStatus.COMPLETED, Chapter1TaskStatus.COMPLETED_WITH_MISSING}
            return snapshot

        has_real_content = _task_has_real_content(snapshot)
        if snapshot.status == Chapter1TaskStatus.COMPLETED:
            snapshot.status = Chapter1TaskStatus.COMPLETED_WITH_MISSING if has_real_content else Chapter1TaskStatus.FAILED
        elif snapshot.status == Chapter1TaskStatus.COMPLETED_WITH_MISSING and not has_real_content:
            snapshot.status = Chapter1TaskStatus.FAILED
        snapshot.can_export = False
        snapshot.errors = _unique([*snapshot.errors, *export_issues])
        snapshot.warnings = _unique([*snapshot.warnings, *export_issues])
        return snapshot


def _needs_repair(section: Chapter1SemanticSection) -> bool:
    return (
        section.status == Chapter1SectionStatus.INCOMPLETE
        or section.validation_score < 80
        or bool(section.missing_items)
        or not section.content_blocks
    )


def _section_summary(section_title: str, section: Chapter1SemanticSection) -> str:
    if not section.content_blocks:
        return f"{section_title} 未完成"
    block_types = [str(block.block_type or "").strip() for block in section.content_blocks if str(block.block_type or "").strip()]
    if not block_types:
        return f"{section_title} 已生成内容，但缺少结构标签"
    visible = "、".join(block_types[:3])
    suffix = "等" if len(block_types) > 3 else ""
    return f"{section_title} 已覆盖 {visible}{suffix}，后续不要重复相同边界与逻辑"


def _dedupe_sources(sources: Sequence[Any]) -> list[Any]:
    deduped = []
    seen: set[str] = set()
    for source in sources:
        key = str(getattr(source, "source_id", "") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(source)
    return deduped


def _unique(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in result:
            continue
        result.append(text)
    return result


def _now() -> str:
    from datetime import datetime

    return datetime.now().isoformat(timespec="seconds")


def _normalize_formal_product_name(raw: str) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    text = text.replace("面向一些工业流程", "面向流程工业")
    text = text.replace("某些", "")
    text = text.replace("一些", "")
    text = re.sub(r"\s+", "", text)
    return text


def _is_missing_text(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(keyword in normalized for keyword in ("待补充", "生成失败", "请人工补充", "暂无资料", "占位"))


def _derive_task_status(sections: Sequence[Chapter1SemanticSection]) -> tuple[Chapter1TaskStatus, bool]:
    all_ok = all(section.status in {Chapter1SectionStatus.COMPLETED, Chapter1SectionStatus.COMPLETED_WITH_WARNING} for section in sections)
    has_real_content = _sections_have_real_content(sections)
    if all_ok and has_real_content:
        return Chapter1TaskStatus.COMPLETED, True
    if all_ok and not has_real_content:
        return Chapter1TaskStatus.FAILED, False
    if has_real_content:
        return Chapter1TaskStatus.COMPLETED_WITH_MISSING, True
    return Chapter1TaskStatus.FAILED, False


def _sections_have_real_content(sections: Sequence[Chapter1SemanticSection]) -> bool:
    return any(
        any(
            str(block.body or "").strip()
            and not _is_missing_text(str(block.body or "").strip())
            for block in section.content_blocks or []
        )
        for section in sections
    )


def _task_has_real_content(snapshot: Chapter1TaskSnapshot) -> bool:
    if snapshot.semantic_draft is not None:
        return _sections_have_real_content(snapshot.semantic_draft.sections or [])
    return bool(snapshot.legacy_sections)


chapter1_task_service = Chapter1TaskService()
