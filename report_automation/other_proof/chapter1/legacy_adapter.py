from __future__ import annotations

from typing import Dict, List

from .config import MISSING_MARKER_PREFIX, MISSING_MARKER_SUFFIX, SECTION_LOOKUP, SECTION_SPECS
from .models import Chapter1SemanticDraft, Chapter1SemanticSection, Chapter1SectionStatus


def semantic_draft_to_legacy_sections(draft: Chapter1SemanticDraft) -> list[dict]:
    section_map = {
        str(section.section_id or "").strip(): section
        for section in (draft.sections or [])
        if isinstance(section, Chapter1SemanticSection)
    }
    legacy_sections: List[Dict[str, object]] = []
    for spec in SECTION_SPECS:
        section = section_map.get(str(spec["key"]))
        if section is None:
            legacy_sections.append(
                {
                    "key": spec["key"],
                    "title": spec["title"],
                    "paragraphs": [
                        _missing_marker(
                            spec["title"],
                            ["生成失败", "资料不足"],
                        )
                    ],
                }
            )
            continue

        paragraphs = _section_to_paragraphs(section)
        if not paragraphs and section.status in {Chapter1SectionStatus.FAILED, Chapter1SectionStatus.INCOMPLETE}:
            paragraphs = [_missing_marker(spec["title"], _missing_reasons(section))]
        legacy_sections.append(
            {
                "key": spec["key"],
                "title": spec["title"],
                "paragraphs": paragraphs,
            }
        )
    return legacy_sections


def _section_to_paragraphs(section: Chapter1SemanticSection) -> list[str]:
    paragraphs: list[str] = []
    for block in section.content_blocks or []:
        heading = str(block.heading or "").strip()
        body = str(block.body or "").strip()
        if not body:
            continue
        if heading:
            paragraphs.append(f"{heading}：{body}")
        else:
            paragraphs.append(body)
    return [item for item in paragraphs if str(item).strip()]


def _missing_reasons(section: Chapter1SemanticSection) -> list[str]:
    reasons: list[str] = []
    if section.status == Chapter1SectionStatus.FAILED:
        reasons.append("生成失败")
    elif section.status == Chapter1SectionStatus.INCOMPLETE:
        reasons.append("自动补写失败")
    if section.missing_items:
        reasons.extend(str(item).strip() for item in section.missing_items if str(item).strip())
    if section.validation_issues and not reasons:
        reasons.extend(str(item).strip() for item in section.validation_issues if str(item).strip())
    if section.warnings and not reasons:
        reasons.extend(str(item).strip() for item in section.warnings if str(item).strip())
    if not reasons:
        reasons.append("资料不足")
    unique: list[str] = []
    for item in reasons:
        if item and item not in unique:
            unique.append(item)
    return unique


def _missing_marker(section_title: str, reasons: list[str]) -> str:
    reason_text = " / ".join(item for item in reasons if item)
    return f"{MISSING_MARKER_PREFIX}此处缺少“{section_title}”的完整内容。原因：{reason_text}。{MISSING_MARKER_SUFFIX}"

