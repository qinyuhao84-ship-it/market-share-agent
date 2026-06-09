from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .config import CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER, SECTION_SPECS
from .models import Chapter1GenerationContext, Chapter1SemanticSection, Chapter1Source

CHAPTER1_SYSTEM_PROMPT = (
    "你是正式咨询报告的行业研究分析师，正在撰写市场占有率证明报告第一章。"
    "你的任务不是写产品宣传稿，也不是写技术科普，而是为后续市场规模测算提供行业边界、产品归属、应用场景和产业链逻辑。"
    "正文必须可直接进入 Word 报告，语气客观、克制、严谨。只输出严格 JSON 对象，不要输出 Markdown，不要输出解释。"
)

_GENERIC_BLOCK_BODY_TEMPLATES = {
    "intro": "该部分围绕行业背景和产品出现的产业原因展开，强调产品与行业数字化转型之间的对应关系。",
    "product_position": "该部分说明产品在工业三维数字化链条中的位置，并交代其与相关市场口径的边界。",
    "definition": "该部分用行业分类语言界定产品属性、行业归属和纳入范围。",
    "scope": "该部分补充产品边界，说明哪些能力应纳入本章讨论，哪些能力应排除。",
    "principle": "该部分围绕数据输入、识别处理、模型重建与工程输出的关系解释工作原理。",
    "process": "该部分说明从现场数据到工程模型的关键流程，但不展开成技术教程。",
    "application": "该部分把工作原理和具体工业应用场景对应起来，说明其落地路径。",
    "features": "该部分说明软件、算法和工程交付层面的产品属性。",
    "advantages": "该部分说明该类产品在行业应用中的价值特征，但不写宣传性判断。",
    "specification": "该部分写关键技术要求，避免无来源参数化表达。",
    "parameters": "该部分写必要的参数约束或接口要求，若没有事实支撑则保持定性表述。",
    "history": "该部分概括行业从人工处理到智能建模的演进逻辑。",
    "timeline": "该部分补足行业阶段变化，重点是技术路线和交付模式的变化。",
    "policy": "该部分从政策环境说明行业发展条件，政策表述必须与事实包一致。",
    "market": "该部分从需求环境说明行业发展条件，强调工程和项目型场景。",
    "technology": "该部分从技术环境说明行业发展条件，强调数据、算法和工程化能力。",
    "trend": "该部分概括行业未来的发展方向，但不写定量预测。",
    "competition": "该部分说明竞争格局的演进逻辑，但不写企业排名或份额。",
    "supply_chain_overview": "该部分说明供应链总述，强调数据采集、算法平台、工程交付和下游应用的连接关系。",
    "upstream": "该部分说明上游供给条件，聚焦数据采集和基础软硬件。",
    "midstream": "该部分说明中游算法平台和工程交付环节。",
    "downstream": "该部分说明下游流程工业应用场景。",
    "core_challenges": "该部分说明供应链的核心特征和面临的挑战。",
    "development_direction": "该部分说明供应链的发展方向。",
}


def build_outline_prompt(
    *,
    company_name: str,
    product_name: str,
    section_specs: Sequence[Mapping[str, Any]] = SECTION_SPECS,
) -> str:
    sections = [
        {
            "section_id": spec["key"],
            "section_title": spec["title"],
            "section_goal": spec.get("section_goal", ""),
            "required_block_types": list(spec.get("required_block_types") or []),
            "target_blocks": int(spec.get("target_blocks") or len(spec.get("required_block_types") or []) or 1),
            "min_body_chars": int(spec.get("min_body_chars") or 0),
        }
        for spec in section_specs
    ]
    example = {
        "draft_id": "draft_001",
        "task_id": "task_001",
        "company_name": company_name,
        "product_name": product_name,
        "sections": sections,
        "self_check": {
            "is_complete": True,
            "risk_notes": [],
        },
    }
    return "\n".join(
        [
            f"你正在为企业“{company_name}”的主导产品“{product_name}”生成第一章结构草稿。",
            "请只输出 json，不要输出 Markdown，不要输出解释。",
            "不要编造具体数据、年份、金额、比例、增速、排名、市场份额。",
            "如果资料不足，只做定性表述。",
            "下面给出 JSON 示例，严格按相同风格输出：",
            json.dumps(example, ensure_ascii=False, indent=2),
        ]
    )


def build_section_prompt(
    *,
    company_name: str,
    product_name: str,
    section_spec: Mapping[str, Any],
    sources: Sequence[Chapter1Source | Mapping[str, Any]],
    completed_section_summaries: Sequence[str],
    chapter1_context: Chapter1GenerationContext | Mapping[str, Any] | None = None,
    generation_mode: str = "strict",
) -> str:
    section_id = str(section_spec.get("key") or "").strip()
    section_title = str(section_spec.get("title") or "").strip()
    required_block_types = [str(item).strip() for item in (section_spec.get("required_block_types") or []) if str(item).strip()]
    target_blocks = int(section_spec.get("target_blocks") or len(required_block_types) or 1)
    section_goal = str(section_spec.get("section_goal") or "").strip()
    avoid_topics = [str(item).strip() for item in (section_spec.get("avoid_topics") or []) if str(item).strip()]
    context_lines = _render_generation_context(chapter1_context)
    fact_lines = _render_evidence_facts(chapter1_context, section_id)
    source_lines = _render_sources(sources)
    completed_lines = [str(item).strip() for item in completed_section_summaries if str(item).strip()]
    example = _build_section_example(
        section_id=section_id,
        section_title=section_title,
        required_block_types=required_block_types,
        target_blocks=target_blocks,
    )

    prompt_parts = [
        "任务：为市场占有率证明报告第一章生成指定小节正文。",
        "",
        "当前小节",
        f"小节名称：{section_title}",
        f"产品名称：{product_name}",
        f"小节目标：{section_goal or '围绕产品与行业公开信息，写出正式咨询报告正文。'}",
        f"本节必须覆盖：{', '.join(required_block_types) if required_block_types else '无'}",
        f"本节不得展开：{', '.join(avoid_topics) if avoid_topics else '无'}",
        f"目标段落数：{target_blocks}",
        f"生成模式：{generation_mode}",
        "",
        "结构化上下文",
        *context_lines,
        "",
        "市场口径约束",
        *(_render_market_scope(chapter1_context) or ["- 未提供市场口径，只能写保守定性内容。"]),
        "",
        "可用事实包",
        *fact_lines,
        "",
        "可用资料来源",
        *source_lines,
        "",
        "已完成小节摘要",
        *completed_lines,
        "要求：不要重复已完成小节的核心句式和内容。",
        "",
        "写作规则",
        *([f"- {item}" for item in _consulting_style_rules(company_name)]),
        "输出 JSON schema",
        json.dumps(example, ensure_ascii=False, indent=2),
        "",
        "强制要求",
        f"- 本小节必须输出 {target_blocks} 个 content_blocks",
        f"- 本小节的完整结构固定为 {target_blocks} 个 block_type" if section_id == "industry_supply_chain" else "- block_type 必须严格按要求顺序输出",
        f"- content_blocks 数量必须等于 {target_blocks}",
        f"- block_type 必须严格按 {', '.join(required_block_types) if required_block_types else '模型自定但需稳定'} 的顺序输出",
        "- heading 必须是空字符串",
        "- body 不得出现冒号、英文冒号、Markdown、编号列表或标题式表达",
        "- body 不得以 block_type 名称、中文标题、上游、中游、下游等标签词开头",
        "- 只能输出 JSON，不要输出 Markdown，不要解释",
    ]
    return "\n".join(prompt_parts)


def build_repair_prompt(
    *,
    company_name: str,
    product_name: str,
    section_spec: Mapping[str, Any],
    section: Chapter1SemanticSection,
    sources: Sequence[Chapter1Source | Mapping[str, Any]],
    chapter1_context: Chapter1GenerationContext | Mapping[str, Any] | None = None,
    repair_mode: str = "fill_missing",
    validation_issues: Sequence[str] | None = None,
) -> str:
    section_id = str(section_spec.get("key") or "").strip()
    section_title = str(section_spec.get("title") or "").strip()
    required_block_types = [str(item).strip() for item in (section_spec.get("required_block_types") or []) if str(item).strip()]
    target_blocks = int(section_spec.get("target_blocks") or len(required_block_types) or 1)
    section_goal = str(section_spec.get("section_goal") or "").strip()
    avoid_topics = [str(item).strip() for item in (section_spec.get("avoid_topics") or []) if str(item).strip()]
    source_lines = _render_sources(sources)
    context_lines = _render_generation_context(chapter1_context)
    issue_lines = [str(item).strip() for item in (validation_issues or section.validation_issues or []) if str(item).strip()]
    current_blocks = []
    for block in section.content_blocks:
        current_blocks.append(
            {
                "block_id": block.block_id,
                "block_type": block.block_type,
                "heading": str(block.heading or "").strip(),
                "body": str(block.body or "").strip(),
                "source_refs": list(block.source_refs or []),
                "edited_by_user": bool(block.edited_by_user),
            }
        )

    if repair_mode == "rewrite_quality":
        example = _build_section_example(
            section_id=section_id,
            section_title=section_title,
            required_block_types=required_block_types,
            target_blocks=target_blocks,
        )
    else:
        example = _build_repair_example(
            section_id=section_id,
            section_title=section_title,
            missing_items=list(section.missing_items or []),
        )

    prompt_parts = [
        "任务：为市场占有率证明报告第一章修复当前小节正文。",
        f"当前修复模式：{repair_mode}",
        "",
        "当前小节",
        f"小节名称：{section_title}",
        f"产品名称：{product_name}",
        f"小节目标：{section_goal or '围绕产品与行业公开信息，写出正式咨询报告正文。'}",
        f"本节必须覆盖：{', '.join(required_block_types) if required_block_types else '无'}",
        f"本节不得展开：{', '.join(avoid_topics) if avoid_topics else '无'}",
        f"目标段落数：{target_blocks}",
        f"本小节的完整结构固定为 {target_blocks} 个 block_type",
        "",
        "当前已有内容如下，补写时不要重写用户已编辑内容，只补缺失块：" if repair_mode != "rewrite_quality" else "当前已有内容如下，修复时以整节重写为主，不要沿用错误表达：",
        json.dumps(current_blocks, ensure_ascii=False, indent=2),
        "当前只输出缺失项" if repair_mode != "rewrite_quality" else "当前需要整节重写",
        f"缺失项必须对应 { '、'.join(required_block_types) if required_block_types else '模型自定但需稳定' } 之一。" if repair_mode != "rewrite_quality" else f"block_type 必须严格按 {', '.join(required_block_types) if required_block_types else '模型自定但需稳定'} 的顺序输出",
        "",
        "必须修复的问题",
        *([f"- {item}" for item in issue_lines] or ["- 当前未提供明确问题，但仍需保证结构和质量"]),
        "",
        "结构化上下文",
        *context_lines,
        "",
        "可用资料来源",
        *source_lines,
        "",
        "补写规则" if repair_mode != "rewrite_quality" else "重写规则",
        *([f"- {item}" for item in _consulting_style_rules(company_name)]),
        "请只输出 json，不要输出 Markdown，不要输出解释。",
        "不要编造具体数据、年份、金额、比例、增速、排名、市场份额。",
        "如果资料不足，只做定性表述。",
        "输出必须是一个 JSON 对象，下面是示例：",
        json.dumps(example, ensure_ascii=False, indent=2),
        "",
        "强制要求",
        f"- content_blocks 数量必须等于 {target_blocks if repair_mode == 'rewrite_quality' else '缺失项数量'}",
        f"- block_type 必须严格按 {', '.join(required_block_types) if required_block_types else '模型自定但需稳定'} 的顺序输出",
        "- heading 必须是空字符串",
        "- body 不得出现冒号、英文冒号、Markdown、编号列表或标题式表达",
        "- body 不得以 block_type 名称、中文标题、上游、中游、下游等标签词开头",
        "- 只能输出 JSON，不要输出 Markdown，不要解释",
    ]
    return "\n".join(prompt_parts)


def build_chapter1_system_prompt() -> str:
    return CHAPTER1_SYSTEM_PROMPT


def _render_generation_context(
    context: Chapter1GenerationContext | Mapping[str, Any] | None,
) -> list[str]:
    if not context:
        return ["- 未提供结构化行业上下文，只能生成保守定性正文。"]

    data = _to_plain_dict(context)
    market_scope = _to_plain_dict(data.get("market_scope") or {})
    lines = [
        f"- 原始产品名：{str(data.get('raw_product_name') or '').strip() or '未提供'}",
        f"- 正式产品名：{str(data.get('normalized_product_name') or '').strip() or str(data.get('raw_product_name') or '').strip() or '未提供'}",
        f"- 产品代码：{str(data.get('product_code') or '').strip() or '未提供'}",
        f"- 产品类别：{str(data.get('product_category') or '').strip() or '未提供'}",
        f"- 产品介绍：{str(data.get('product_intro') or '').strip() or '未提供'}",
        f"- 产品能力：{_join_items(data.get('product_capabilities'))}",
        f"- 产品输出：{_join_items(data.get('product_outputs'))}",
        f"- 排除能力：{_join_items(data.get('excluded_capabilities'))}",
        f"- 应用行业：{_join_items(data.get('application_industries'))}",
        f"- 应用场景：{_join_items(data.get('application_scenarios'))}",
        f"- 目标用户：{_join_items(data.get('target_users'))}",
        f"- 写作风格：{str(data.get('writing_style') or '').strip() or 'consulting_report'}",
        f"- 市场名称：{str(market_scope.get('market_name') or '').strip() or '未提供'}",
        f"- 上位市场：{str(market_scope.get('parent_market') or '').strip() or '未提供'}",
        f"- 纳入范围：{_join_items(market_scope.get('included_scope'))}",
        f"- 排除范围：{_join_items(market_scope.get('excluded_scope'))}",
        f"- 细分路径：{_join_items(market_scope.get('segmentation_path'))}",
    ]
    return lines


def _render_market_scope(context: Chapter1GenerationContext | Mapping[str, Any] | None) -> list[str]:
    if not context:
        return []
    data = _to_plain_dict(context)
    market_scope = _to_plain_dict(data.get("market_scope") or {})
    market_name = str(market_scope.get("market_name") or "").strip()
    if not market_name:
        return []
    return [
        f"- 本章所有内容必须服务以下市场口径：{market_name}",
        f"- 纳入范围：{_join_items(market_scope.get('included_scope'))}",
        f"- 排除范围：{_join_items(market_scope.get('excluded_scope'))}",
        f"- 细分路径：{_join_items(market_scope.get('segmentation_path'))}",
        "- 正文不得把排除范围写成产品所属范围。",
    ]


def _render_evidence_facts(
    context: Chapter1GenerationContext | Mapping[str, Any] | None,
    section_id: str,
) -> list[str]:
    if not context:
        return ["- 暂无"]
    data = _to_plain_dict(context)
    facts = data.get("evidence_facts") or []
    rendered: list[str] = []
    for item in facts:
        fact = _to_plain_dict(item)
        allowed_sections = [str(value).strip() for value in (fact.get("allowed_sections") or []) if str(value).strip()]
        if allowed_sections and section_id not in allowed_sections:
            continue
        fact_text = str(fact.get("fact") or "").strip()
        if not fact_text:
            continue
        rendered.append(
            f"- [{str(fact.get('fact_id') or '').strip() or 'fact'}] "
            f"{fact_text} 来源：{str(fact.get('source_title') or fact.get('title') or '').strip() or '未提供'}"
        )
    return rendered or ["- 暂无"]


def _render_sources(sources: Sequence[Chapter1Source | Mapping[str, Any]]) -> list[str]:
    rendered: list[str] = []
    for source in sources:
        data = _to_plain_dict(source)
        title = str(data.get("title") or data.get("source_title") or "").strip()
        url = str(data.get("url") or "").strip()
        fact = str(data.get("raw_excerpt") or data.get("fact") or "").strip()
        source_type = str(data.get("source_type") or data.get("type") or "web").strip() or "web"
        related_sections = _join_items(data.get("related_sections"))
        extracted_facts = _join_items(data.get("extracted_facts"))
        line = f"- {title or '未命名来源'}"
        details: list[str] = []
        if url:
            details.append(f"链接 {url}")
        if fact:
            details.append(f"摘要 {fact}")
        if extracted_facts and extracted_facts != "未提供":
            details.append(f"已提取事实 {extracted_facts}")
        if related_sections and related_sections != "未提供":
            details.append(f"相关小节 {related_sections}")
        details.append(f"来源类型 {source_type}")
        if details:
            line = f"{line}，" + "，".join(details)
        rendered.append(line)
    return rendered or ["- 暂无检索资料"]


def _build_section_example(
    *,
    section_id: str,
    section_title: str,
    required_block_types: Sequence[str],
    target_blocks: int,
) -> dict[str, Any]:
    if section_id == "industry_supply_chain":
        return {
            "section_id": section_id,
            "section_title": section_title,
            "content_blocks": [
                {
                    "block_id": f"{section_id}_001",
                    "block_type": block_type,
                    "heading": "",
                    "body": _supply_chain_example_body(block_type),
                    "source_refs": [],
                    "confidence": "medium",
                }
                for block_type in CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER
            ],
            "missing_items": [],
            "self_check": {
                "is_complete": True,
                "risk_notes": [],
            },
        }

    blocks: list[dict[str, Any]] = []
    for index, block_type in enumerate(required_block_types or ["body"], start=1):
        blocks.append(
            {
                "block_id": f"{section_id}_{index:03d}",
                "block_type": block_type,
                "heading": "",
                "body": _generic_example_body(section_title, block_type),
                "source_refs": [],
                "confidence": "medium",
            }
        )
    while len(blocks) < target_blocks:
        blocks.append(
            {
                "block_id": f"{section_id}_{len(blocks) + 1:03d}",
                "block_type": blocks[-1]["block_type"] if blocks else "body",
                "heading": "",
                "body": _generic_example_body(section_title, blocks[-1]["block_type"] if blocks else "body"),
                "source_refs": [],
                "confidence": "medium",
            }
        )
    return {
        "section_id": section_id,
        "section_title": section_title,
        "content_blocks": blocks[:target_blocks],
        "missing_items": [],
        "self_check": {
            "is_complete": True,
            "risk_notes": [],
        },
    }


def _build_repair_example(
    *,
    section_id: str,
    section_title: str,
    missing_items: Sequence[str],
) -> dict[str, Any]:
    if section_id == "industry_supply_chain":
        missing = [item for item in missing_items if item in CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER] or CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER
        return {
            "section_id": section_id,
            "section_title": section_title,
            "content_blocks": [
                {
                    "block_id": f"{section_id}_{index:03d}",
                    "block_type": block_type,
                    "heading": "",
                    "body": _supply_chain_example_body(block_type),
                    "source_refs": [],
                    "confidence": "medium",
                }
                for index, block_type in enumerate(missing, start=1)
            ],
            "missing_items": [],
            "self_check": {
                "is_complete": True,
                "risk_notes": [],
            },
        }

    block_type = missing_items[0] if missing_items else "body"
    return {
        "section_id": section_id,
        "section_title": section_title,
        "content_blocks": [
            {
                "block_id": f"{section_id}_repair_001",
                "block_type": block_type,
                "heading": "",
                "body": _generic_example_body(section_title, block_type),
                "source_refs": [],
                "confidence": "medium",
            }
        ],
        "missing_items": [],
        "self_check": {
            "is_complete": True,
            "risk_notes": [],
        },
    }


def _consulting_style_rules(company_name: str = "") -> list[str]:
    company = str(company_name or "").strip()
    rules = [
        "写作风格必须是正式咨询行业研究报告正文，不要写成提纲、列表、科普说明或产品宣传稿。",
        "正文必须是连贯段落，每个 content_blocks 的 body 都必须是一段完整咨询报告正文。",
        "heading 字段必须输出为空字符串，不得在 heading 中写任何标题文本。",
        "body 中不得出现冒号或英文冒号，不得使用标题式冒号结构。",
        "正文不得出现 Markdown、项目符号、编号列表、短句罗列。",
        "第一章是产品与行业概况，不是企业介绍，正文不得出现企业名称。",
        "不得出现具体年份、金额、比例、增长率、市场份额、排名、CAGR 等定量数据。",
        "不得编造任何定量数据。没有资料时只写定性判断。",
        "不得使用“可能”“或许”“大概”“预计”“有望”“约”“左右”“以上”“以下”“超过”等不确定或估算表达。",
        "不要使用过度营销化表述，如“全球领先”“显著领先”“独特优势”等无法证明的判断。",
        "不要使用空泛套话，必须围绕产品边界、行业链条、应用场景和市场口径展开。",
        "政策、标准、报告、行业数据等来源性表述必须来自事实包。",
        "没有具体参数时，不得写精度、阈值、容差、置信度、响应时间等疑似参数化表达。",
        "第一章每个小节都有独立职责，不得把工作原理、产品属性、行业趋势、供应链内容相互混写。",
        "正文要服务市场口径，不要泛泛谈智能制造、数字化转型、数字孪生。",
        "每段必须包含明确主语和行业对象，不得连续使用抽象名词堆叠。",
        "不得重复上一小节已经出现的核心技术流程。",
    ]
    if company:
        rules.append(f"正文中禁止出现企业名称“{company}”及其简称。")
    return rules


def _supply_chain_example_body(block_type: str) -> str:
    mapping = {
        "supply_chain_overview": "该类产品所在供应链围绕工业现场空间数据的采集、处理、建模和应用展开，价值传导并不依赖单一硬件设备，而是由数据质量、算法能力、工程软件适配和行业交付经验共同决定。其产业链条从现场数据获取延伸至模型生成、系统集成和流程工业应用，最终服务于工程设计、数字化交付和资产运维等环节。",
        "upstream": "数据采集设备、扫描作业服务、基础计算资源和点云处理框架构成该类产品的基础供给条件。激光扫描仪、移动采集设备和工业现场采集服务决定原始点云的完整性与可用性，算法框架和计算资源则影响后续模型训练、识别推理和大规模点云处理的效率。",
        "midstream": "中游环节主要承担算法平台开发、模型转换、系统集成和工程交付等职能，是把底层能力转化为可用产品的核心阶段。该环节决定产品能否在复杂工业现场形成稳定的工程化输出，也决定软件、算法和交付流程能否协同运转。",
        "downstream": "下游应用主要集中在流程工业业主单位、工程设计机构、资产运维部门和项目交付团队，重点围绕建模效率、协同效率和交付质量展开。产品在这一环节的价值，更多体现为支撑设计复核、施工比对、数字化交付和运维协同等具体业务。",
        "core_challenges": "该类供应链具有软硬件协同程度高、场景适配要求强、交付过程专业化明显等特征，同时也面临数据质量不稳定、工业场景差异大和系统集成复杂等挑战。行业竞争并不只看单点算法，而是看从采集到交付的整体能力。",
        "development_direction": "未来供应链将进一步向数据采集标准化、算法模型工程化、平台接口开放化和行业场景复用化方向发展，以提升整体协同效率和交付一致性。随着工业项目对数字化交付要求提高，供应链各环节的协同边界也会逐步清晰。",
    }
    return mapping.get(block_type, "该部分围绕产品边界、行业链条和工程化应用展开，强调其在正式市场口径中的角色。")


def _generic_example_body(section_title: str, block_type: str) -> str:
    template = _GENERIC_BLOCK_BODY_TEMPLATES.get(block_type)
    if template:
        return template
    return f"该部分围绕{section_title}展开，强调该类产品在行业口径中的定位、边界和作用机制。"


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "model_dump"):
        dumped = value.model_dump(mode="python")  # type: ignore[call-arg]
        if isinstance(dumped, Mapping):
            return dict(dumped)
    return {}


def _join_items(value: Any) -> str:
    if value is None:
        return "未提供"
    if isinstance(value, str):
        text = value.strip()
        return text or "未提供"
    if isinstance(value, Sequence):
        items = [str(item).strip() for item in value if str(item).strip()]
        return "；".join(items) if items else "未提供"
    text = str(value).strip()
    return text or "未提供"
