from __future__ import annotations

import copy
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
from .legacy_adapter import semantic_draft_to_legacy_sections
from .models import (
    Chapter1SemanticDraft,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    Chapter1TaskCreateRequest,
    Chapter1TaskSnapshot,
    Chapter1TaskStatus,
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
        normalized_request = request.model_copy(
            update={
                "model_name": CHAPTER1_MODEL_NAME,
                "enable_web_retrieval": False,
            }
        )
        snapshot = self.store.create(normalized_request)
        snapshot.model_name = CHAPTER1_MODEL_NAME
        snapshot.model_mode = CHAPTER1_MODEL_MODE
        snapshot.generation_mode = normalized_request.generation_mode
        snapshot.use_cache = bool(normalized_request.use_cache)
        snapshot.enable_web_retrieval = False
        snapshot.allow_incomplete_export = bool(normalized_request.allow_incomplete_export)
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
            sources: list[Any] = []
            section_warnings.append(f"{section_title}：已跳过本地联网检索，直接调用 DeepSeek-V4-Pro Thinking 生成。")

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
                section_errors.append(str(exc))
                warnings.append(f"{section_title} 生成失败：{exc}")
                section = Chapter1SemanticSection(
                    section_id=section_key,
                    section_title=section_title,
                    section_goal=str(spec.get("section_goal") or ""),
                    content_blocks=[],
                    sources=list(sources),
                    status=Chapter1SectionStatus.FAILED,
                    validation_score=0,
                    validation_issues=[str(exc)],
                    missing_items=[section_title],
                    repair_attempts=0,
                    warnings=[str(exc)],
                )
                generation_records.append(
                    {
                        "section_key": section_key,
                        "section_title": section_title,
                        "error": str(exc),
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
            validated = validate_section(section, spec)
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
        draft = validate_draft(draft)
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

        all_ok = all(section.status in {Chapter1SectionStatus.COMPLETED, Chapter1SectionStatus.COMPLETED_WITH_WARNING} for section in draft.sections)
        has_real_content = any(
            any(str(block.body or "").strip() and not _is_missing_text(str(block.body or "").strip()) for block in section.content_blocks)
            for section in draft.sections
        )
        if all_ok:
            snapshot.status = Chapter1TaskStatus.COMPLETED
        elif has_real_content:
            snapshot.status = Chapter1TaskStatus.COMPLETED_WITH_MISSING
        else:
            snapshot.status = Chapter1TaskStatus.FAILED
        snapshot.can_export = snapshot.status in {Chapter1TaskStatus.COMPLETED, Chapter1TaskStatus.COMPLETED_WITH_MISSING}

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
        completed_summaries = [
            _section_summary(item.section_title, item)
            for item in existing_sections
            if str(item.section_id or "").strip() != section_key
        ]

        section_generator = self._new_section_generator()
        repair_service = self._new_repair_service()
        sources: list[Any] = []

        section = section_generator.generate_section(
            company_name=snapshot.company_name,
            product_name=snapshot.product_name,
            section_spec=dict(spec),
            sources=sources,
            completed_section_summaries=completed_summaries,
        )
        section.sources = list(sources)
        section = validate_section(section, spec)
        if _needs_repair(section):
            section = repair_service.repair_section(
                section=section,
                section_spec=dict(spec),
                product_name=snapshot.product_name,
                company_name=snapshot.company_name,
                sources=sources,
            )

        updated_sections = []
        for item in existing_sections:
            if str(item.section_id or "").strip() == section_key:
                updated_sections.append(section)
            else:
                updated_sections.append(item)

        snapshot.semantic_draft = validate_draft(
            snapshot.semantic_draft.model_copy(update={"sections": updated_sections})
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

        sources: list[Any] = []
        repair_service = self._new_repair_service()
        repaired = repair_service.repair_section(
            section=section,
            section_spec=dict(spec),
            product_name=snapshot.product_name,
            company_name=snapshot.company_name,
            sources=sources,
        )

        updated_sections = []
        for item in snapshot.semantic_draft.sections or []:
            if str(item.section_id or "").strip() == section_key:
                updated_sections.append(repaired)
            else:
                updated_sections.append(item)

        snapshot.semantic_draft = validate_draft(snapshot.semantic_draft.model_copy(update={"sections": updated_sections}))
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
        return "|".join(
            [
                str(request.company_name or "").strip().lower(),
                str(request.product_name or "").strip().lower(),
                CHAPTER1_MODEL_NAME,
                CHAPTER1_MODEL_MODE,
                str(request.generation_mode or "balanced"),
                "allow" if request.allow_incomplete_export else "strict",
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
            use_cache=snapshot.use_cache,
            enable_web_retrieval=False,
            allow_incomplete_export=snapshot.allow_incomplete_export,
            generation_mode=snapshot.generation_mode if snapshot.generation_mode in {"balanced", "strict", "fast"} else "balanced",
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
        cloned.generation_mode = str(request.generation_mode or "balanced")
        cloned.use_cache = bool(request.use_cache)
        cloned.enable_web_retrieval = False
        cloned.allow_incomplete_export = bool(request.allow_incomplete_export)
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
        snapshot.can_export = bool(snapshot.legacy_sections)
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


def _needs_repair(section: Chapter1SemanticSection) -> bool:
    return (
        section.status == Chapter1SectionStatus.INCOMPLETE
        or section.validation_score < 70
        or bool(section.missing_items)
        or not section.content_blocks
    )


def _section_summary(section_title: str, section: Chapter1SemanticSection) -> str:
    if not section.content_blocks:
        return f"{section_title}：{section.status.value}"
    first_block = section.content_blocks[0]
    heading = str(first_block.heading or "").strip()
    body = str(first_block.body or "").strip()
    snippet = body[:60]
    if heading:
        return f"{section_title}：{heading} {snippet}".strip()
    return f"{section_title}：{snippet}".strip()


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


def _is_missing_text(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(keyword in normalized for keyword in ("待补充", "生成失败", "请人工补充", "暂无资料"))


def _derive_task_status(sections: Sequence[Chapter1SemanticSection]) -> tuple[Chapter1TaskStatus, bool]:
    all_ok = all(section.status in {Chapter1SectionStatus.COMPLETED, Chapter1SectionStatus.COMPLETED_WITH_WARNING} for section in sections)
    has_real_content = any(
        any(str(block.body or "").strip() and not _is_missing_text(str(block.body or "").strip()) for block in section.content_blocks)
        for section in sections
    )
    if all_ok:
        return Chapter1TaskStatus.COMPLETED, True
    if has_real_content:
        return Chapter1TaskStatus.COMPLETED_WITH_MISSING, True
    return Chapter1TaskStatus.FAILED, False


chapter1_task_service = Chapter1TaskService()
