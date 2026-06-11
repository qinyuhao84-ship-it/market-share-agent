from __future__ import annotations

from typing import Iterable

from .legacy_adapter import legacy_sections_have_missing_markers
from .models import Chapter1TaskSnapshot

BLOCKING_TEXT_PATTERNS = (
    "【待补充：",
    "该部分生成失败",
    "请人工补充",
    "暂无资料",
    "待补充",
)

ABNORMAL_PUNCTUATION_PATTERNS = (
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
    """Return advisory Chapter 1 issues without blocking Word export.

    The product requirement is to always generate the Word document once content exists,
    even when Chapter 1 contains placeholders or failed sections. Callers may still log
    the returned issues, but the boolean is intentionally always True.
    """
    issues: list[str] = []

    draft = snapshot.semantic_draft
    if draft is None:
        issues.append("第一章语义草稿为空")

    sections = list(draft.sections or []) if draft is not None else []
    if draft is not None and not sections:
        issues.append("第一章语义草稿没有小节")

    for section in sections:
        title = str(section.section_title or section.section_id or "第一章").strip() or "第一章"
        status = str(getattr(section.status, "value", section.status) or "").strip()
        score = int(section.validation_score or 0)
        if status and status not in {"completed", "completed_with_warning"}:
            issues.append(f"{title} 结构校验状态为 {status}")
        if score and score < 80:
            issues.append(f"{title} 结构校验分低于 80")
        elif not score:
            issues.append(f"{title} 缺少结构校验分")

    legacy_sections = list(snapshot.legacy_sections or [])
    if not legacy_sections:
        issues.append("第一章没有可导出的正式段落")

    if legacy_sections_have_missing_markers(legacy_sections):
        issues.append("第一章正式段落存在待补充或生成失败标记")

    for legacy_section in legacy_sections:
        if not isinstance(legacy_section, dict):
            issues.append("第一章正式段落结构异常")
            continue
        title = str(legacy_section.get("title") or legacy_section.get("key") or "第一章").strip() or "第一章"
        paragraphs = [str(item or "").strip() for item in (legacy_section.get("paragraphs") or []) if str(item or "").strip()]
        if not paragraphs:
            issues.append(f"{title} 没有可导出的正式段落")
            continue
        for paragraph in paragraphs:
            if _has_blocking_text(paragraph):
                issues.append(f"{title} 存在待补充或生成失败标记")
            if _has_abnormal_punctuation(paragraph):
                issues.append(f"{title} 存在异常标点组合")
            if _has_colon(paragraph):
                issues.append(f"{title} 正式段落仍存在冒号")
            if _has_company_name(paragraph, snapshot.company_name):
                issues.append(f"{title} 正式段落仍出现企业名称")

    return True, _unique(issues)


def _has_blocking_text(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(pattern in normalized for pattern in BLOCKING_TEXT_PATTERNS)


def _has_abnormal_punctuation(text: str) -> bool:
    value = str(text or "")
    return any(pattern in value for pattern in ABNORMAL_PUNCTUATION_PATTERNS)


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
