from __future__ import annotations

import re
from typing import Iterable, List, Mapping, Sequence

from .config import SECTION_LOOKUP, SECTION_SPECS
from .models import (
    Chapter1ContentBlock,
    Chapter1SemanticDraft,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    Chapter1Source,
)
from .text_polisher import UNCERTAIN_WORDS

ALLOWED_BLOCK_TYPES = {
    "intro",
    "product_position",
    "definition",
    "scope",
    "principle",
    "process",
    "application",
    "features",
    "advantages",
    "specification",
    "parameters",
    "history",
    "timeline",
    "policy",
    "market",
    "technology",
    "trend",
    "competition",
    "supply_chain_overview",
    "upstream",
    "midstream",
    "downstream",
    "core_challenges",
    "development_direction",
    "summary",
    "analysis",
    "risk",
    "body",
}

PLACEHOLDER_PATTERNS = (
    "待补充",
    "暂无资料",
    "请结合公开资料补充",
    "该部分生成失败",
    "请人工补充",
)

TOPIC_RULES = {
    "industry_supply_chain": ("上游", "中游", "下游"),
    "industry_environment": ("政策", "市场", "技术", "应用"),
    "industry_trends": ("技术", "市场", "应用", "竞争"),
}


def validate_section(section: Chapter1SemanticSection, section_spec: Mapping[str, object]) -> Chapter1SemanticSection:
    spec_key = str(section_spec.get("key") or "").strip()
    spec_title = str(section_spec.get("title") or "").strip()
    required_block_types = [str(item).strip() for item in (section_spec.get("required_block_types") or []) if str(item).strip()]
    min_body_chars = int(section_spec.get("min_body_chars") or 0)

    issues: List[str] = []
    missing_items: List[str] = list(section.missing_items or [])
    warnings: List[str] = list(section.warnings or [])
    score = 100

    if str(section.section_id or "").strip() != spec_key:
        issues.append(f"section_id 不匹配，期望 {spec_key}")
        score -= 50
    if str(section.section_title or "").strip() != spec_title:
        issues.append(f"section_title 不匹配，期望 {spec_title}")
        score -= 50

    blocks = list(section.content_blocks or [])
    if not blocks:
        issues.append("内容块为空")
        score -= 80

    block_types_seen: set[str] = set()
    has_real_source = False
    has_topic_match = False
    has_placeholder = False

    for block in blocks:
        block_issues: List[str] = list(block.validation_issues or [])
        block_type = str(block.block_type or "").strip()
        heading = str(block.heading or "").strip()
        body = str(block.body or "").strip()
        if block_type:
            block_types_seen.add(block_type)
        if block_type not in ALLOWED_BLOCK_TYPES:
            block_issues.append(f"不允许的块类型：{block_type or '空'}")
            score -= 20
        if not body:
            block_issues.append("正文为空")
            score -= 30
        if heading:
            block_issues.append("heading 应为空，避免生成标题式正文")
            score -= 10
        if _has_colon(body) or _has_colon(heading):
            block_issues.append("正文存在冒号或标签式表达")
            score -= 15
        if _has_uncertain_words(body):
            block_issues.append("正文存在不确定或估算表达")
            score -= 10
        chinese_chars = _count_cjk_chars(body)
        if chinese_chars < 30:
            block_issues.append("正文长度不足")
            score -= 20
        if _contains_placeholder(body) or _contains_placeholder(heading):
            has_placeholder = True
            issues.append("内容包含占位文本")
            block_issues.append("出现占位文本")
            score -= 40
        if _looks_like_other_section_title(body) or _looks_like_other_section_title(heading):
            block_issues.append("疑似混入其他小节标题")
            score -= 50
        if section.section_id == "technical_specifications" and re.search(r"\d", body) and not (block.source_refs or section.sources):
            block_issues.append("技术规范中的具体数值缺少来源支撑")
            score -= 10
        if block.source_refs:
            has_real_source = True
        if block_issues:
            block.validation_issues = _unique(block.validation_issues + block_issues)

        if _section_has_topic_match(section.section_id, body + " " + heading):
            has_topic_match = True

    missing_block_types = [item for item in required_block_types if item not in block_types_seen]
    if missing_block_types:
        if section.section_id == "industry_supply_chain":
            issues.append(f"供应链缺少必要内容块：{', '.join(missing_block_types)}")
            score -= 20 + 5 * len(missing_block_types)
        else:
            issues.append(f"缺少必要块类型：{', '.join(missing_block_types)}")
            score -= 20
        missing_items.extend(missing_block_types)

    if section.sources and not has_real_source:
        issues.append("资料来源未被正文引用")
        score -= 5

    topic_keywords = TOPIC_RULES.get(spec_key)
    if topic_keywords and not has_topic_match:
        issues.append(f"主题覆盖不足：{spec_title}")
        missing_items.extend(list(topic_keywords))
        score -= 10

    if section.section_id == "industry_supply_chain":
        supply_chain_text = " ".join(f"{block.heading} {block.body}" for block in blocks)
        supply_chain_keywords = ("上游", "中游", "下游")
        missing_supply_chain = [keyword for keyword in supply_chain_keywords if keyword not in supply_chain_text]
        if missing_supply_chain:
            issues.append(f"供应链未覆盖{', '.join(missing_supply_chain)}")
            missing_items.extend(missing_supply_chain)
            score -= 20 + 5 * len(missing_supply_chain)
    elif section.section_id == "industry_environment":
        env_text = " ".join(f"{block.heading} {block.body}" for block in blocks)
        env_keywords = ("政策", "市场", "技术", "应用")
        missing_env = [keyword for keyword in env_keywords if keyword not in env_text]
        if missing_env:
            issues.append(f"行业环境未尽量覆盖{', '.join(missing_env)}")
            missing_items.extend(missing_env)
            score -= 10 + 3 * len(missing_env)
    elif section.section_id == "industry_trends":
        trend_text = " ".join(f"{block.heading} {block.body}" for block in blocks)
        trend_keywords = ("技术", "市场", "应用", "竞争")
        missing_trends = [keyword for keyword in trend_keywords if keyword not in trend_text]
        if missing_trends:
            issues.append(f"行业趋势未尽量覆盖{', '.join(missing_trends)}")
            missing_items.extend(missing_trends)
            score -= 10 + 3 * len(missing_trends)

    if min_body_chars and blocks:
        if max((_count_cjk_chars(block.body) for block in blocks), default=0) < min_body_chars:
            issues.append(f"正文整体长度不足，建议至少 {min_body_chars} 个汉字")
            score -= 10

    score = max(0, min(100, score))
    if score >= 90:
        status = Chapter1SectionStatus.COMPLETED
    elif score >= 70:
        status = Chapter1SectionStatus.COMPLETED_WITH_WARNING
    elif score >= 50:
        status = Chapter1SectionStatus.INCOMPLETE
    else:
        status = Chapter1SectionStatus.FAILED

    if has_placeholder and status == Chapter1SectionStatus.COMPLETED:
        status = Chapter1SectionStatus.COMPLETED_WITH_WARNING
    if section.sources and not has_real_source and status == Chapter1SectionStatus.COMPLETED:
        status = Chapter1SectionStatus.COMPLETED_WITH_WARNING

    merged_issues = _unique([*section.validation_issues, *issues])
    merged_missing = _unique([*missing_items, *section.missing_items])
    merged_warnings = _unique([*warnings, *merged_issues])

    return section.model_copy(
        update={
            "status": status,
            "validation_score": score,
            "validation_issues": merged_issues,
            "missing_items": merged_missing,
            "warnings": merged_warnings,
        },
    )


def validate_draft(draft: Chapter1SemanticDraft) -> Chapter1SemanticDraft:
    section_map = {
        str(section.section_id or "").strip(): section
        for section in draft.sections or []
        if isinstance(section, Chapter1SemanticSection)
    }
    validated_sections: List[Chapter1SemanticSection] = []
    draft_warnings = list(draft.warnings or [])
    for spec in SECTION_SPECS:
        section = section_map.get(str(spec["key"]))
        if section is None:
            section = Chapter1SemanticSection(
                section_id=str(spec["key"]),
                section_title=str(spec["title"]),
                section_goal=str(spec.get("section_goal") or ""),
                content_blocks=[],
                sources=[],
                status=Chapter1SectionStatus.FAILED,
                validation_score=0,
                validation_issues=["章节缺失"],
                missing_items=[str(spec["title"])],
                warnings=["章节缺失"],
            )
        validated = validate_section(section, spec)
        validated_sections.append(validated)
        draft_warnings.extend(validated.warnings)

    sources = _dedupe_sources([source for section in validated_sections for source in section.sources])
    return draft.model_copy(
        update={
            "sections": validated_sections,
            "sources": sources,
            "warnings": _unique(draft_warnings),
        },
    )


def _contains_placeholder(text: str) -> bool:
    normalized = str(text or "").strip()
    return any(pattern in normalized for pattern in PLACEHOLDER_PATTERNS)


def _has_colon(text: str) -> bool:
    value = str(text or "")
    return "：" in value or ":" in value


def _has_uncertain_words(text: str) -> bool:
    value = str(text or "")
    return any(word in value for word in UNCERTAIN_WORDS)


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


def _looks_like_other_section_title(text: str) -> bool:
    normalized = str(text or "").strip()
    if not normalized:
        return False
    for spec in SECTION_SPECS:
        title = str(spec["title"])
        if title and normalized.startswith(title) and normalized != title:
            return True
    return False


def _section_has_topic_match(section_id: str, text: str) -> bool:
    keywords = TOPIC_RULES.get(section_id)
    if not keywords:
        return True
    return any(keyword in text for keyword in keywords)


def _count_cjk_chars(text: str) -> int:
    return len(re.findall(r"[\u4e00-\u9fff]", str(text or "")))


def _dedupe_sources(sources: Sequence[Chapter1Source]) -> list[Chapter1Source]:
    deduped: list[Chapter1Source] = []
    seen: set[str] = set()
    for source in sources:
        key = str(source.source_id or "").strip()
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
