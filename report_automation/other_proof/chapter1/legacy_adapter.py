from __future__ import annotations

from typing import Dict, List

from .config import (
    CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER as SUPPLY_CHAIN_BLOCK_ORDER,
    CHAPTER1_SUPPLY_CHAIN_SLOT_TITLES as SUPPLY_CHAIN_SLOT_TITLES,
    MISSING_MARKER_PREFIX,
    MISSING_MARKER_SUFFIX,
    SECTION_LOOKUP,
    SECTION_SPECS,
)
from .models import Chapter1SemanticDraft, Chapter1SemanticSection, Chapter1SectionStatus
from .text_polisher import polish_chapter1_paragraph

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

        paragraphs = _section_to_paragraphs(section, company_name=draft.company_name)
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


def _section_to_paragraphs(section: Chapter1SemanticSection, *, company_name: str = "") -> list[str]:
    if str(section.section_id or "").strip() == "industry_supply_chain":
        return _supply_chain_paragraphs(section, company_name=company_name)

    paragraphs: list[str] = []
    for block in section.content_blocks or []:
        body = str(block.body or "").strip()
        if not body:
            continue
        cleaned = polish_chapter1_paragraph(body, company_name=company_name)
        if cleaned:
            paragraphs.append(cleaned)
    return [item for item in paragraphs if str(item).strip()]


def _supply_chain_paragraphs(section: Chapter1SemanticSection, *, company_name: str = "") -> list[str]:
    blocks_by_type: dict[str, list[str]] = {}
    for block in section.content_blocks or []:
        block_type = str(block.block_type or "").strip()
        body = str(block.body or "").strip()
        if not block_type or not body:
            continue
        cleaned = polish_chapter1_paragraph(body, company_name=company_name)
        if not cleaned:
            continue
        blocks_by_type.setdefault(block_type, []).append(cleaned)

    paragraphs: list[str] = []
    for block_type in SUPPLY_CHAIN_BLOCK_ORDER:
        items = blocks_by_type.get(block_type) or []
        if items:
            if len(items) == 1:
                paragraphs.append(items[0])
            else:
                joined = "。".join(item.rstrip("。") for item in items if item.strip())
                paragraphs.append(f"{joined}。")
        else:
            paragraphs.append(_missing_marker(SUPPLY_CHAIN_SLOT_TITLES[block_type], ["生成缺失"]))
    return paragraphs


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


def legacy_sections_have_missing_markers(legacy_sections: list[dict]) -> bool:
    for section in legacy_sections or []:
        if not isinstance(section, dict):
            continue
        for paragraph in section.get("paragraphs") or []:
            text = str(paragraph or "")
            if "【待补充：" in text or "该部分生成失败" in text or "请人工补充" in text:
                return True
    return False
