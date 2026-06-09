from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from inference import InferenceConfig

from .config import CHAPTER1_REPAIR_ATTEMPT_LIMIT, CHAPTER1_REPAIR_TIMEOUT_SECONDS, SECTION_MAX_TOKENS
from .deepseek_client import Chapter1LLMError, Chapter1LLMUnavailableError, DeepSeekV4ProChapter1Client
from .json_parser import Chapter1ParseError, parse_deepseek_json_object
from .models import (
    Chapter1ContentBlock,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    Chapter1Source,
)
from .prompt_builder import build_repair_prompt
from .validators import validate_section


class Chapter1RepairService:
    def __init__(
        self,
        client: DeepSeekV4ProChapter1Client | None = None,
        config: InferenceConfig | None = None,
    ) -> None:
        self.config = config or InferenceConfig()
        self.client = client or DeepSeekV4ProChapter1Client(self.config)
        self.last_record: dict[str, Any] = {}

    def repair_section(
        self,
        *,
        section: Chapter1SemanticSection,
        section_spec: dict,
        product_name: str,
        company_name: str,
        sources: list[Chapter1Source],
    ) -> Chapter1SemanticSection:
        section_key = str(section_spec.get("key") or "").strip()
        section_title = str(section_spec.get("title") or "").strip()
        need_repair = (
            section.status == Chapter1SectionStatus.INCOMPLETE
            or section.validation_score < 70
            or bool(section.missing_items)
            or not section.content_blocks
            or (not section.sources and not section.content_blocks)
        )
        if not need_repair:
            self.last_record = {
                "section_key": section_key,
                "section_title": section_title,
                "skipped": True,
                "reason": "no_repair_needed",
            }
            return section

        current = section.model_copy(deep=True)
        record: dict[str, Any] = {
            "section_key": section_key,
            "section_title": section_title,
            "attempts": [],
            "warnings": [],
            "skipped": False,
        }
        self.last_record = record

        allowed_block_types = set(str(item).strip() for item in (section_spec.get("required_block_types") or []) if str(item).strip())
        max_output_tokens = SECTION_MAX_TOKENS.get(section_key, 1800)
        for attempt in range(1, CHAPTER1_REPAIR_ATTEMPT_LIMIT + 1):
            current.repair_attempts = max(current.repair_attempts, attempt)
            prompt = build_repair_prompt(
                company_name=company_name,
                product_name=product_name,
                section_spec=section_spec,
                section=current,
                sources=sources,
            )
            messages = [
                {
                    "role": "system",
                    "content": "你是产业研究分析师，只负责补写缺失块。请只输出 json，不要输出 Markdown，不要输出解释。",
                },
                {
                    "role": "user",
                    "content": prompt,
                },
            ]
            attempt_record: dict[str, Any] = {
                "attempt": attempt,
                "messages": copy.deepcopy(messages),
            }
            record["attempts"].append(attempt_record)
            try:
                raw = self.client.complete_json(
                    messages=messages,
                    section_key=section_key,
                    max_output_tokens=max_output_tokens,
                    timeout_seconds=CHAPTER1_REPAIR_TIMEOUT_SECONDS,
                    retry_max_attempts=1,
                )
            except (Chapter1LLMUnavailableError, Chapter1LLMError) as exc:
                warning = f"{section_title} 第 {attempt} 次补写失败：{exc}"
                record["warnings"].append(warning)
                continue

            attempt_record["raw_output"] = raw
            try:
                parsed = parse_deepseek_json_object(raw)
            except Chapter1ParseError as exc:
                warning = f"{section_title} 第 {attempt} 次补写解析失败：{exc.code}"
                record["warnings"].append(warning)
                attempt_record["parse_error"] = exc.code
                continue

            attempt_record["parsed_output"] = copy.deepcopy(parsed)
            blocks = self._parse_blocks(parsed, section_key=section_key, allowed_block_types=allowed_block_types)
            if not blocks:
                warning = f"{section_title} 第 {attempt} 次补写未返回可用内容块"
                record["warnings"].append(warning)
                continue

            current = self._merge_blocks(current, blocks)
            current = validate_section(current, section_spec)
            attempt_record["validated_status"] = current.status.value
            attempt_record["validated_score"] = current.validation_score
            if current.status in {Chapter1SectionStatus.COMPLETED, Chapter1SectionStatus.COMPLETED_WITH_WARNING}:
                break
            if current.validation_score >= 70 and current.content_blocks:
                break

        if current.status in {Chapter1SectionStatus.INCOMPLETE, Chapter1SectionStatus.FAILED}:
            warning = f"{section_title} 自动补写未达到可导出标准"
            record["warnings"].append(warning)
            current = current.model_copy(update={"warnings": _unique([*current.warnings, warning])})
        self.last_record = record
        return current

    def _parse_blocks(
        self,
        payload: Mapping[str, Any],
        *,
        section_key: str,
        allowed_block_types: set[str],
    ) -> list[Chapter1ContentBlock]:
        blocks: list[Chapter1ContentBlock] = []
        for index, item in enumerate(payload.get("content_blocks") or [], start=1):
            if not isinstance(item, Mapping):
                continue
            body = str(item.get("body") or item.get("text") or "").strip()
            if not body:
                continue
            block_type = str(item.get("block_type") or item.get("type") or "body").strip() or "body"
            if allowed_block_types and block_type not in allowed_block_types:
                continue
            blocks.append(
                Chapter1ContentBlock(
                    block_id=str(item.get("block_id") or f"{section_key}_repair_{index:03d}").strip(),
                    block_type=block_type,
                    heading=str(item.get("heading") or "").strip(),
                    body=body,
                    source_refs=[str(ref).strip() for ref in (item.get("source_refs") or []) if str(ref).strip()],
                    confidence=str(item.get("confidence") or "medium").strip() or "medium",
                    validation_issues=[],
                    generated_by=self.client.model_name,
                    edited_by_user=bool(item.get("edited_by_user", False)),
                )
            )
        return blocks

    def _merge_blocks(
        self,
        section: Chapter1SemanticSection,
        new_blocks: Sequence[Chapter1ContentBlock],
    ) -> Chapter1SemanticSection:
        existing_signatures = {
            (str(block.block_type).strip(), str(block.heading).strip(), str(block.body).strip())
            for block in section.content_blocks or []
        }
        merged_blocks = list(section.content_blocks or [])
        for block in new_blocks:
            signature = (str(block.block_type).strip(), str(block.heading).strip(), str(block.body).strip())
            if signature in existing_signatures:
                continue
            merged_blocks.append(block)
            existing_signatures.add(signature)
        return section.model_copy(update={"content_blocks": merged_blocks})


def _unique(items: Sequence[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in result:
            continue
        result.append(text)
    return result
