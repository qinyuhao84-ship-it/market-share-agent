from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from inference import InferenceConfig

from .config import CHAPTER1_SECTION_TIMEOUT_SECONDS, SECTION_MAX_TOKENS
from .deepseek_client import Chapter1LLMError, Chapter1LLMUnavailableError, DeepSeekV4ProChapter1Client
from .json_parser import Chapter1ParseError, parse_deepseek_json_object
from .models import (
    Chapter1ContentBlock,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    Chapter1Source,
)
from .prompt_builder import build_section_prompt
from .text_polisher import polish_chapter1_paragraph


class Chapter1SectionGenerator:
    def __init__(
        self,
        client: DeepSeekV4ProChapter1Client | None = None,
        config: InferenceConfig | None = None,
    ) -> None:
        self.config = config or InferenceConfig()
        self.client = client or DeepSeekV4ProChapter1Client(self.config)
        self.last_raw_output: str = ""
        self.last_parsed_output: dict[str, Any] = {}
        self.last_messages: list[dict[str, str]] = []
        self.last_record: dict[str, Any] = {}

    def generate_section(
        self,
        *,
        company_name: str,
        product_name: str,
        section_spec: dict,
        sources: list[Chapter1Source],
        completed_section_summaries: list[str],
    ) -> Chapter1SemanticSection:
        section_key = str(section_spec.get("key") or "").strip()
        section_title = str(section_spec.get("title") or "").strip()
        max_output_tokens = SECTION_MAX_TOKENS.get(section_key, 1800)
        prompt = build_section_prompt(
            company_name=company_name,
            product_name=product_name,
            section_spec=section_spec,
            sources=sources,
            completed_section_summaries=completed_section_summaries,
            generation_mode="balanced",
        )
        messages = [
            {
                "role": "system",
                "content": "你是产业研究分析师。只输出 json，不要输出 Markdown，不要输出解释。",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ]
        self.last_messages = [dict(item) for item in messages]
        self.last_record = {
            "section_key": section_key,
            "section_title": section_title,
            "messages": copy.deepcopy(messages),
            "model_name": self.client.model_name,
            "max_output_tokens": max_output_tokens,
            "timeout_seconds": CHAPTER1_SECTION_TIMEOUT_SECONDS,
        }

        raw = self.client.complete_json(
            messages=messages,
            section_key=section_key,
            max_output_tokens=max_output_tokens,
            timeout_seconds=CHAPTER1_SECTION_TIMEOUT_SECONDS,
            retry_max_attempts=1,
        )
        self.last_raw_output = raw
        self.last_record["raw_output"] = raw

        parsed = parse_deepseek_json_object(raw)
        self.last_parsed_output = copy.deepcopy(parsed)
        self.last_record["parsed_output"] = copy.deepcopy(parsed)

        section = self._payload_to_section(
            parsed,
            section_spec=section_spec,
            sources=sources,
            company_name=company_name,
        )
        self.last_record["content_block_count"] = len(section.content_blocks)
        return section

    def _payload_to_section(
        self,
        payload: Mapping[str, Any],
        *,
        section_spec: Mapping[str, Any],
        sources: Sequence[Chapter1Source],
        company_name: str = "",
    ) -> Chapter1SemanticSection:
        section_key = str(section_spec.get("key") or "").strip()
        section_title = str(section_spec.get("title") or "").strip()
        section_goal = str(section_spec.get("section_goal") or "").strip()
        block_payloads = self._extract_block_payloads(payload)
        blocks: list[Chapter1ContentBlock] = []
        for index, item in enumerate(block_payloads, start=1):
            if not isinstance(item, Mapping):
                continue
            body = polish_chapter1_paragraph(
                str(item.get("body") or item.get("text") or "").strip(),
                company_name=company_name,
            )
            if not body:
                continue
            block_type = str(item.get("block_type") or item.get("type") or "body").strip() or "body"
            source_refs = [str(ref).strip() for ref in (item.get("source_refs") or []) if str(ref).strip()]
            confidence = str(item.get("confidence") or "medium").strip() or "medium"
            blocks.append(
                Chapter1ContentBlock(
                    block_id=str(item.get("block_id") or f"{section_key}_{index:03d}").strip(),
                    block_type=block_type,
                    heading="",
                    body=body,
                    source_refs=source_refs,
                    confidence=confidence,
                    validation_issues=[],
                    generated_by=self.client.model_name,
                    edited_by_user=bool(item.get("edited_by_user", False)),
                )
            )

        missing_items = [str(item).strip() for item in (payload.get("missing_items") or []) if str(item).strip()]
        section_goal = str(payload.get("section_goal") or section_goal).strip()
        return Chapter1SemanticSection(
            section_id=str(payload.get("section_id") or section_key).strip() or section_key,
            section_title=str(payload.get("section_title") or section_title).strip() or section_title,
            section_goal=section_goal,
            content_blocks=blocks,
            sources=list(sources),
            status=Chapter1SectionStatus.PENDING,
            validation_score=0,
            validation_issues=[],
            missing_items=missing_items,
            repair_attempts=0,
            warnings=[],
        )

    def _extract_block_payloads(self, payload: Mapping[str, Any]) -> list[Any]:
        for key in ("content_blocks", "blocks", "paragraphs"):
            value = payload.get(key)
            if isinstance(value, list):
                if key == "paragraphs":
                    return [
                        {
                            "block_id": f"block_{index:03d}",
                            "block_type": "body",
                            "heading": "",
                            "body": str(item or "").strip(),
                            "source_refs": [],
                            "confidence": "medium",
                        }
                        for index, item in enumerate(value, start=1)
                        if str(item or "").strip()
                    ]
                return list(value)
        return []
