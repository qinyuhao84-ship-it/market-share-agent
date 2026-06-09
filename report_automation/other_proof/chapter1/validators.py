from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable, List, Mapping, Sequence

from .config import CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER, SECTION_LOOKUP, SECTION_SPECS
from .models import (
    Chapter1ContentBlock,
    Chapter1GenerationContext,
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

ABNORMAL_PUNCTUATION_PATTERNS = (
    "、：",
    "、:",
    "，：",
    "，:",
    "。：",
    "。:",
    "；：",
    "；:",
    "、，",
    "，、",
    ",：",
    ":，",
)

AI_CLICHE_PATTERNS = (
    "日益凸显",
    "持续赋能",
    "深度融合",
    "市场增长动力强劲",
    "核心地位",
    "关键支撑",
    "重要抓手",
    "生态体系",
    "闭环能力",
    "高质量发展",
    "提供有力支撑",
    "不断推进",
    "持续深化",
    "显著提升",
    "稳步增长",
)

OFF_SCOPE_WORDS = (
    "消费级",
    "家装",
    "娱乐",
    "游戏",
    "影视",
    "城市CIM",
    "商业展示",
    "通用可视化",
)

SUSPICIOUS_SPEC_WORDS = (
    "阈值",
    "容差",
    "精度等级",
    "置信度",
    "响应时间",
    "处理规模",
    "参数",
    "指标",
    "标准",
    "规范明确",
    "需控制在",
)

TOPIC_RULES = {
    "industry_supply_chain": ("上游", "中游", "下游"),
    "industry_environment": ("政策", "市场", "技术", "应用"),
    "industry_trends": ("技术", "市场", "应用", "竞争"),
}


def validate_section(
    section: Chapter1SemanticSection,
    section_spec: Mapping[str, object],
    *,
    company_name: str = "",
    chapter1_context: Chapter1GenerationContext | Mapping[str, object] | None = None,
) -> Chapter1SemanticSection:
    spec_key = str(section_spec.get("key") or "").strip()
    spec_title = str(section_spec.get("title") or "").strip()
    required_block_types = [str(item).strip() for item in (section_spec.get("required_block_types") or []) if str(item).strip()]
    target_blocks = int(section_spec.get("target_blocks") or len(required_block_types) or 0)
    min_body_chars = int(section_spec.get("min_body_chars") or 0)
    avoid_topics = [str(item).strip() for item in (section_spec.get("avoid_topics") or []) if str(item).strip()]

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

    block_types_seen: list[str] = []
    has_real_source = False
    has_topic_match = False
    has_placeholder = False
    section_text_parts: list[str] = []

    for block in blocks:
        block_issues: List[str] = list(block.validation_issues or [])
        block_type = str(block.block_type or "").strip()
        heading = str(block.heading or "").strip()
        body = str(block.body or "").strip()
        if block_type:
            block_types_seen.append(block_type)
        section_text_parts.append(f"{heading} {body}".strip())

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
        if _has_abnormal_punctuation(body) or _has_abnormal_punctuation(heading):
            block_issues.append("正文存在异常标点组合")
            score -= 30
        if _has_uncertain_words(body):
            block_issues.append("正文存在不确定或估算表达")
            score -= 10
        if _has_company_name(body, company_name) or _has_company_name(heading, company_name):
            block_issues.append("正文出现企业名称")
            score -= 40
        if _contains_placeholder(body) or _contains_placeholder(heading):
            has_placeholder = True
            issues.append("内容包含占位文本")
            block_issues.append("出现占位文本")
            score -= 40
        if _looks_like_other_section_title(body) or _looks_like_other_section_title(heading):
            block_issues.append("疑似混入其他小节标题")
            score -= 50
        if avoid_topics and any(topic and topic in body for topic in avoid_topics):
            block_issues.append("正文出现本节禁止展开的主题")
            score -= 10
        if any(word in body for word in OFF_SCOPE_WORDS):
            block_issues.append("正文出现疑似偏离市场口径的词汇")
            score -= 5
        cliche_count = _count_cliches(body)
        if cliche_count >= 3:
            block_issues.append("正文存在过多 AI 套话")
            score -= 15
        chinese_chars = _count_cjk_chars(body)
        if chinese_chars < 30:
            block_issues.append("正文长度不足")
            score -= 20
        if section.section_id == "technical_specifications" and _suspicious_spec_count(body) >= 3 and not (block.source_refs or section.sources):
            block_issues.append("技术规范中的参数化表达缺少来源支撑")
            score -= 25
        if block.source_refs:
            has_real_source = True
        if block_issues:
            block.validation_issues = _unique([*(block.validation_issues or []), *block_issues])
        if _section_has_topic_match(section.section_id, body + " " + heading):
            has_topic_match = True

    for index, left in enumerate(blocks):
        for right in blocks[index + 1 :]:
            if _similarity_ratio(left.body, right.body) > 0.55:
                issues.append("不同内容块之间重复度过高")
                score -= 20
                break

    if target_blocks and len(blocks) != target_blocks:
        issues.append(f"内容块数量不符合要求，期望 {target_blocks} 个，实际 {len(blocks)} 个")
        score -= 20

    missing_block_types = [item for item in required_block_types if item not in block_types_seen]
    if missing_block_types:
        if section.section_id == "industry_supply_chain":
            issues.append(f"供应链缺少必要内容块：{', '.join(missing_block_types)}")
            score -= 20 + 5 * len(missing_block_types)
        else:
            issues.append(f"缺少必要块类型：{', '.join(missing_block_types)}")
            score -= 20
        missing_items.extend(missing_block_types)

    if section.section_id == "industry_supply_chain":
        actual_types = [str(block.block_type or "").strip() for block in blocks]
        if actual_types != CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER:
            issues.append(
                "供应链内容块顺序或数量不符合要求，"
                f"期望 {CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER}，实际 {actual_types}"
            )
            score -= 60
            missing_items.extend([item for item in CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER if item not in actual_types])
        supply_chain_text = " ".join(section_text_parts)
        for keyword in ("上游", "中游", "下游"):
            if keyword not in supply_chain_text:
                issues.append(f"供应链未覆盖{keyword}")
                missing_items.append(keyword)
                score -= 20
    elif section.section_id == "industry_environment":
        env_text = " ".join(section_text_parts)
        for keyword in ("政策", "市场", "技术", "应用"):
            if keyword not in env_text:
                issues.append(f"行业环境未覆盖{keyword}")
                missing_items.append(keyword)
                score -= 10
    elif section.section_id == "industry_trends":
        trend_text = " ".join(section_text_parts)
        for keyword in ("技术", "市场", "应用", "竞争"):
            if keyword not in trend_text:
                issues.append(f"行业趋势未覆盖{keyword}")
                missing_items.append(keyword)
                score -= 10

    if min_body_chars and blocks:
        longest_block = max((_count_cjk_chars(block.body) for block in blocks), default=0)
        if longest_block < min_body_chars:
            issues.append(f"正文整体长度不足，建议至少 {min_body_chars} 个汉字")
            score -= 10

    if section.sources and not has_real_source:
        issues.append("资料来源未被正文引用")
        score -= 5

    if _count_cliches(" ".join(section_text_parts)) >= 8:
        issues.append("整节 AI 套话密度过高")
        score -= 20

    if not has_topic_match and spec_key in TOPIC_RULES:
        issues.append(f"主题覆盖不足：{spec_title}")
        score -= 10

    score = max(0, min(100, score))
    if score >= 90:
        status = Chapter1SectionStatus.COMPLETED
    elif score >= 80:
        status = Chapter1SectionStatus.COMPLETED_WITH_WARNING
    elif score >= 60:
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


def validate_draft(
    draft: Chapter1SemanticDraft,
    *,
    company_name: str = "",
    chapter1_context: Chapter1GenerationContext | Mapping[str, object] | None = None,
) -> Chapter1SemanticDraft:
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
        validated = validate_section(
            section,
            spec,
            company_name=company_name,
            chapter1_context=chapter1_context,
        )
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


def _has_abnormal_punctuation(text: str) -> bool:
    value = str(text or "")
    return any(pattern in value for pattern in ABNORMAL_PUNCTUATION_PATTERNS)


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


def _count_cliches(text: str) -> int:
    value = str(text or "")
    return sum(value.count(pattern) for pattern in AI_CLICHE_PATTERNS)


def _suspicious_spec_count(text: str) -> int:
    value = str(text or "")
    return sum(value.count(pattern) for pattern in SUSPICIOUS_SPEC_WORDS)


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


def _similarity_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, str(a or "").strip(), str(b or "").strip()).ratio()
