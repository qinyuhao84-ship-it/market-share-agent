from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .config import SECTION_SPECS
from .models import Chapter1SemanticSection, Chapter1Source


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
    generation_mode: str = "balanced",
) -> str:
    source_lines = _render_sources(sources)
    completed_lines = [str(item).strip() for item in completed_section_summaries if str(item).strip()]
    section_id = str(section_spec.get("key") or "").strip()
    section_title = str(section_spec.get("title") or "").strip()
    example = _build_section_example(section_id=section_id, section_title=section_title, section_spec=section_spec)
    return "\n".join(
        [
            f"产品名称：{product_name}",
            "企业名称仅用于禁用词判断，不得写入正文。",
            f"小节：{section_title}（{section_id}）",
            f"生成模式：{generation_mode}",
            f"小节目标：{section_spec.get('section_goal', '') or '围绕产品与行业公开信息，写出完整的定性分析。'}",
            f"建议块类型：{', '.join(section_spec.get('required_block_types') or [])}",
            f"最低正文长度建议：{int(section_spec.get('min_body_chars') or 0)} 字左右",
            "写作规则：",
            *([f"- {item}" for item in _consulting_style_rules(company_name)]),
            *(_supply_chain_section_rules() if section_id == "industry_supply_chain" else []),
            "已完成小节摘要：",
            *([f"- {item}" for item in completed_lines] or ["- 暂无"]),
            "可用资料来源：",
            *([f"- {item}" for item in source_lines] or ["- 暂无检索资料"]),
            "请只输出 json，不要输出 Markdown，不要输出解释。",
            "不要编造具体数据、年份、金额、比例、增速、排名、市场份额。",
            "如果资料不足，只做定性表述。",
            "输出必须是一个 JSON 对象，下面是示例：",
            json.dumps(example, ensure_ascii=False, indent=2),
        ]
    )


def build_repair_prompt(
    *,
    company_name: str,
    product_name: str,
    section_spec: Mapping[str, Any],
    section: Chapter1SemanticSection,
    sources: Sequence[Chapter1Source | Mapping[str, Any]],
) -> str:
    source_lines = _render_sources(sources)
    current_blocks = []
    for block in section.content_blocks:
        heading = str(block.heading or "").strip()
        body = str(block.body or "").strip()
        current_blocks.append(
            {
                "block_id": block.block_id,
                "block_type": block.block_type,
                "heading": heading,
                "body": body,
                "source_refs": list(block.source_refs or []),
                "edited_by_user": bool(block.edited_by_user),
            }
        )
    section_id = str(section_spec.get("key") or "").strip()
    section_title = str(section_spec.get("title") or "").strip()
    example = _build_repair_example(section_id=section_id, section_title=section_title, section_spec=section_spec)
    return "\n".join(
        [
            f"产品名称：{product_name}",
            "企业名称仅用于禁用词判断，不得写入正文。",
            f"小节：{section.section_title}（{section.section_id}）",
            "当前已有内容如下，补写时不要重写用户已编辑内容，只补缺失块：",
            json.dumps(current_blocks, ensure_ascii=False, indent=2),
            "缺失项：",
            *([f"- {item}" for item in (section.missing_items or [])] or ["- 暂无"]),
            "可用资料来源：",
            *([f"- {item}" for item in source_lines] or ["- 暂无检索资料"]),
            "补写规则：",
            *([f"- {item}" for item in _consulting_style_rules(company_name)]),
            *(_supply_chain_repair_rules() if section_id == "industry_supply_chain" else []),
            "请只输出 json，不要输出 Markdown，不要输出解释。",
            "不要编造具体数据、年份、金额、比例、增速、排名、市场份额。",
            "如果资料不足，只做定性表述。",
            "输出必须是一个 JSON 对象，下面是示例：",
            json.dumps(example, ensure_ascii=False, indent=2),
        ]
    )


def _consulting_style_rules(company_name: str = "") -> list[str]:
    company = str(company_name or "").strip()
    rules = [
        "写作风格必须是正式咨询行业研究报告正文，不要写成提纲、列表、科普说明或产品宣传稿。",
        "正文必须是连贯段落，每个 content_blocks 的 body 都必须是一段完整咨询报告正文。",
        "heading 字段必须输出为空字符串，不得在 heading 中写“产品定义”“核心技术原理”“上游”等标题。",
        "body 中不得出现冒号或英文冒号，不得使用“标题：正文”的结构。",
        "body 开头不得出现“产品定义”“应用范围”“核心技术原理”“上游”“中游”“下游”等标签词。",
        "正文不得出现 Markdown、项目符号、编号列表、短句罗列。",
        "第一章是产品与行业概况，不是企业介绍，正文不得出现企业名称。",
        "不得出现具体年份、金额、比例、增长率、市场份额、排名、CAGR等定量数据。",
        "不得编造任何定量数据。没有资料时只写定性判断。",
        "不得使用“可能”“或许”“大概”“预计”“有望”“约”“左右”“以上”“以下”“超过”等不确定或估算表达。",
        "不要使用过度营销化表述，如“全球领先”“显著领先”“独特优势”等无法证明的判断。",
        "可以使用“该产品”“该系统”“此类产品”“相关系统”等中性称呼。",
    ]
    if company:
        rules.append(f"正文中禁止出现企业名称“{company}”及其简称。")
    return rules


def _supply_chain_section_rules() -> list[str]:
    return [
        "本小节必须输出 6 个 content_blocks，顺序必须固定。",
        "第 1 个 block_type 必须是 supply_chain_overview，body 写供应链总述，对应“五、行业供应链”标题下的总述段。",
        "第 2 个 block_type 必须是 upstream，body 写上游供应链，对应“（一）上游供应链”。",
        "第 3 个 block_type 必须是 midstream，body 写中游制造与集成，对应“（二）中游制造与集成”。",
        "第 4 个 block_type 必须是 downstream，body 写下游应用与分销，对应“（三）下游应用与分销”。",
        "第 5 个 block_type 必须是 core_challenges，body 写行业供应链的核心特征与面临的挑战，对应“（四）行业供应链的核心特征与面临的挑战”。",
        "第 6 个 block_type 必须是 development_direction，body 写行业供应链的发展方向，对应“（五）行业供应链的发展方向”。",
        "每个 body 必须是完整段落，不要以“上游”“中游”“下游”等标签开头。",
    ]


def _supply_chain_repair_rules() -> list[str]:
    return [
        "本小节的完整结构固定为 6 个 block_type，当前只输出缺失项，顺序按固定结构返回，不要重复已有块。",
        "缺失项必须对应 supply_chain_overview、upstream、midstream、downstream、core_challenges、development_direction 之一。",
        "每个补写 body 必须是完整段落，不要以“上游”“中游”“下游”等标签开头。",
    ]


def _build_section_example(
    *,
    section_id: str,
    section_title: str,
    section_spec: Mapping[str, Any],
) -> dict[str, Any]:
    if section_id == "industry_supply_chain":
        return {
            "section_id": section_id,
            "section_title": section_title,
            "content_blocks": [
                {
                    "block_id": f"{section_id}_001",
                    "block_type": "supply_chain_overview",
                    "heading": "",
                    "body": "该系统所处供应链围绕数据采集、算法处理、系统集成和工业应用展开，各环节共同支撑点云数据向工程化三维模型的转化。相关产品通常以现场采集、软件建模和工程交付为主线，形成从数据输入到场景落地的完整链条。",
                    "source_refs": [],
                    "confidence": "medium",
                },
                {
                    "block_id": f"{section_id}_002",
                    "block_type": "upstream",
                    "heading": "",
                    "body": "上游环节主要包括传感设备、扫描采集工具、基础算法框架、计算资源和现场数据服务等基础能力，它们决定了原始数据的质量和后续处理的稳定性。",
                    "source_refs": [],
                    "confidence": "medium",
                },
                {
                    "block_id": f"{section_id}_003",
                    "block_type": "midstream",
                    "heading": "",
                    "body": "中游环节主要承担算法训练、软件开发、模型转换、系统集成和工程化交付等职能，是把底层能力转化为可用产品的核心阶段。",
                    "source_refs": [],
                    "confidence": "medium",
                },
                {
                    "block_id": f"{section_id}_004",
                    "block_type": "downstream",
                    "heading": "",
                    "body": "下游应用主要集中在流程工业企业、工程设计单位、资产运维单位和数字孪生平台建设场景，重点围绕建模效率、协同效率和交付质量展开。",
                    "source_refs": [],
                    "confidence": "medium",
                },
                {
                    "block_id": f"{section_id}_005",
                    "block_type": "core_challenges",
                    "heading": "",
                    "body": "该类供应链具有软硬件协同程度高、场景适配要求强、交付过程专业化明显等特征，同时也面临数据质量不稳定、工业场景差异大和系统集成复杂等挑战。",
                    "source_refs": [],
                    "confidence": "medium",
                },
                {
                    "block_id": f"{section_id}_006",
                    "block_type": "development_direction",
                    "heading": "",
                    "body": "未来供应链将进一步向数据采集标准化、算法模型工程化、平台接口开放化和行业场景复用化方向发展，以提升整体协同效率和交付一致性。",
                    "source_refs": [],
                    "confidence": "medium",
                },
            ],
            "missing_items": [],
            "self_check": {
                "is_complete": True,
                "risk_notes": [],
            },
        }

    required_block_types = list(section_spec.get("required_block_types") or [])
    block_type = required_block_types[0] if required_block_types else "body"
    return {
        "section_id": section_id,
        "section_title": section_title,
        "content_blocks": [
            {
                "block_id": f"{section_id}_001",
                "block_type": block_type,
                "heading": "",
                "body": "该系统围绕工业场景中的数据采集、模型转换和工程协同展开，重点解决空间信息结构化、三维表达统一和后续应用复用等问题。其价值主要体现在把分散的现场数据整理为可持续使用的工程化模型，为数字化交付、运维协同和后续平台化应用提供稳定底座。",
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


def _build_repair_example(
    *,
    section_id: str,
    section_title: str,
    section_spec: Mapping[str, Any],
) -> dict[str, Any]:
    required_block_types = list(section_spec.get("required_block_types") or [])
    block_type = required_block_types[0] if required_block_types else "body"
    return {
        "section_id": section_id,
        "section_title": section_title,
        "content_blocks": [
            {
                "block_id": "repair_001",
                "block_type": block_type,
                "heading": "",
                "body": "该系统围绕工业场景中的数据采集、模型转换和工程协同展开，重点解决空间信息结构化、三维表达统一和后续应用复用等问题。其价值主要体现在把分散的现场数据整理为可持续使用的工程化模型，为数字化交付、运维协同和后续平台化应用提供稳定底座。",
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


def _render_sources(sources: Sequence[Chapter1Source | Mapping[str, Any]]) -> list[str]:
    rendered: list[str] = []
    for index, source in enumerate(sources, start=1):
        if isinstance(source, Chapter1Source):
            item = source.model_dump(mode="python")
        else:
            item = dict(source)
        source_id = str(item.get("source_id") or f"source_{index:03d}").strip()
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        facts = item.get("extracted_facts") or []
        fact_text = "；".join(str(part).strip() for part in facts if str(part).strip())
        rendered.append(
            " | ".join(
                [
                    source_id,
                    title or "未命名来源",
                    url or "未提供链接",
                    fact_text or "未提取到事实",
                ]
            )
        )
    return rendered
