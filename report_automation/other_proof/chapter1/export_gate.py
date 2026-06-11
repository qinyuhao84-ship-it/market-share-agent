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
    """Validate the final Chapter 1 content that will actually be exported.

    The generation pipeline keeps two representations:
    1. semantic_draft: raw structured model output used for validation and replay.
    2. legacy_sections: polished paragraphs that are written into the Word template.

    Previous logic blocked export by scanning raw semantic blocks for colons and company
    names. That caused false failures because legacy conversion intentionally removes
    these issues before export. This gate must block only when the final exportable
    paragraphs are missing or still contain hard failure markers.
    """
    hard_issues: list[str] = []
    advisory_issues: list[str] = []

    draft = snapshot.semantic_draft
    if draft is None:
        hard_issues.append("第一章语义草稿为空")

    sections = list(draft.sections or []) if draft is not None else []
    if draft is not None and not sections:
        hard_issues.append("第一章语义草稿没有小节")

    for section in sections:
        title = str(section.section_title or section.section_id or "第一章").strip() or "第一章"
        status = str(getattr(section.status, "value", section.status) or "").strip()
        score = int(section.validation_score or 0)
        if status not in {"completed", "completed_with_warning"}:
            advisory_issues.append(f"{title} 结构校验状态为 {status or '未知'}")
        if score and score < 80:
            advisory_issues.append(f"{title} 结构校验分低于 80")
        elif not score:
            advisory_issues.append(f"{title} 缺少结构校验分")

    legacy_sections = list(snapshot.legacy_sections or [])
    if not legacy_sections:
        hard_issues.append("第一章没有可导出的正式段落")

    if legacy_sections_have_missing_markers(legacy_sections):
        hard_issues.append("第一章正式段落存在待补充或生成失败标记")

    for legacy_section in legacy_sections:
        if not isinstance(legacy_section, dict):
            hard_issues.append("第一章正式段落结构异常")
            continue
        title = str(legacy_section.get("title") or legacy_section.get("key") or "第一章").strip() or "第一章"
        paragraphs = [str(item or "").strip() for item in (legacy_section.get("paragraphs") or []) if str(item or "").strip()]
        if not paragraphs:
            hard_issues.append(f"{title} 没有可导出的正式段落")
            continue
        for paragraph in paragraphs:
            if _has_blocking_text(paragraph):
                hard_issues.append(f"{title} 存在待补充或生成失败标记")
            if _has_abnormal_punctuation(paragraph):
                hard_issues.append(f"{title} 存在异常标点组合")
            if _has_colon(paragraph):
                hard_issues.append(f"{title} 正式段落仍存在冒号")
            if _has_company_name(paragraph, snapshot.company_name):
                hard_issues.append(f"{title} 正式段落仍出现企业名称")

    hard_issues = _unique(hard_issues)
    advisory_issues = _unique(advisory_issues)
    if hard_issues:
        return False, hard_issues
    return True, advisory_issues


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
