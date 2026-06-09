from __future__ import annotations

from typing import Iterable

from .legacy_adapter import legacy_sections_have_missing_markers
from .models import Chapter1SectionStatus, Chapter1TaskSnapshot

BLOCKING_PATTERNS = (
    "【待补充：",
    "该部分生成失败",
    "请人工补充",
    "暂无资料",
    "待补充",
    "、：",
    "、:",
    "，：",
    "，:",
    "。：",
    "。:",
    "；：",
    "；:",
)


def validate_chapter1_exportable(snapshot: Chapter1TaskSnapshot) -> tuple[bool, list[str]]:
    issues: list[str] = []
    draft = snapshot.semantic_draft
    if draft is None:
        issues.append("第一章语义草稿为空")
        return False, issues

    sections = list(draft.sections or [])
    if not sections:
        issues.append("第一章语义草稿没有小节")

    for section in sections:
        if section.status not in {Chapter1SectionStatus.COMPLETED, Chapter1SectionStatus.COMPLETED_WITH_WARNING}:
            issues.append(f"{section.section_title} 未完成")
        if int(section.validation_score or 0) < 80:
            issues.append(f"{section.section_title} 校验分低于 80")
        for block in section.content_blocks or []:
            body = str(block.body or "").strip()
            heading = str(block.heading or "").strip()
            if _has_blocking_text(body) or _has_blocking_text(heading):
                issues.append(f"{section.section_title} 存在阻断导出的异常文本")
            if _has_colon(body) or _has_colon(heading):
                issues.append(f"{section.section_title} 存在冒号")
            if _has_company_name(body, snapshot.company_name) or _has_company_name(heading, snapshot.company_name):
                issues.append(f"{section.section_title} 出现企业名称")

    if legacy_sections_have_missing_markers(snapshot.legacy_sections or []):
        issues.append("第一章 legacy 段落存在阻断导出的异常文本")

    for legacy_section in snapshot.legacy_sections or []:
        if not isinstance(legacy_section, dict):
            continue
        for paragraph in legacy_section.get("paragraphs") or []:
            text = str(paragraph or "").strip()
            if _has_blocking_text(text):
                issues.append(f"{legacy_section.get('title') or legacy_section.get('key') or '第一章'} 存在阻断导出的异常文本")
            if _has_colon(text):
                issues.append(f"{legacy_section.get('title') or legacy_section.get('key') or '第一章'} 存在冒号")
            if _has_company_name(text, snapshot.company_name):
                issues.append(f"{legacy_section.get('title') or legacy_section.get('key') or '第一章'} 出现企业名称")

    issues = _unique(issues)
    return len(issues) == 0, issues


def _has_blocking_text(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(pattern in normalized for pattern in BLOCKING_PATTERNS)


def _has_colon(text: str) -> bool:
    value = str(text or "")
    return "：" in value or ":" in value


def _has_company_name(text: str, company_name: str = "") -> bool:
    company = str(company_name or "").strip()
    if not company:
        return False
    candidates = [
        company,
        company.replace("有限公司", ""),
        company.replace("股份有限公司", ""),
        company.replace("科技有限公司", ""),
    ]
    return any(item and item in str(text or "") for item in candidates)


def _unique(items: Iterable[str]) -> list[str]:
    result: list[str] = []
    for item in items:
        text = str(item or "").strip()
        if not text or text in result:
            continue
        result.append(text)
    return result
