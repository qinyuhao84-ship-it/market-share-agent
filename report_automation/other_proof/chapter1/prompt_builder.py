from __future__ import annotations

import json
from typing import Any, Mapping, Sequence

from .config import SECTION_LOOKUP, SECTION_SPECS
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
    example = {
        "section_id": section_id,
        "section_title": section_title,
        "content_blocks": [
            {
                "block_id": f"{section_id}_001",
                "block_type": (section_spec.get("required_block_types") or ["body"])[0],
                "heading": "产品定义",
                "body": "正文内容",
                "source_refs": ["source_001"],
                "confidence": "medium",
            }
        ],
        "missing_items": [],
        "self_check": {
            "is_complete": True,
            "risk_notes": [],
        },
    }
    return "\n".join(
        [
            f"企业：{company_name}",
            f"产品：{product_name}",
            f"小节：{section_title}（{section_id}）",
            f"生成模式：{generation_mode}",
            f"小节目标：{section_spec.get('section_goal', '') or '围绕产品与行业公开信息，写出完整的定性分析。'}",
            f"建议块类型：{', '.join(section_spec.get('required_block_types') or [])}",
            f"最低正文长度建议：{int(section_spec.get('min_body_chars') or 0)} 字左右",
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
    example = {
        "section_id": str(section_spec.get("key") or "").strip(),
        "section_title": str(section_spec.get("title") or "").strip(),
        "content_blocks": [
            {
                "block_id": "repair_001",
                "block_type": (section_spec.get("required_block_types") or ["body"])[0],
                "heading": "补写标题",
                "body": "补写正文",
                "source_refs": ["source_001"],
                "confidence": "medium",
            }
        ],
        "missing_items": [],
        "self_check": {
            "is_complete": True,
            "risk_notes": [],
        },
    }
    return "\n".join(
        [
            f"企业：{company_name}",
            f"产品：{product_name}",
            f"小节：{section.section_title}（{section.section_id}）",
            "当前已有内容如下，补写时不要重写用户已编辑内容，只补缺失块：",
            json.dumps(current_blocks, ensure_ascii=False, indent=2),
            "缺失项：",
            *([f"- {item}" for item in (section.missing_items or [])] or ["- 暂无"]),
            "可用资料来源：",
            *([f"- {item}" for item in source_lines] or ["- 暂无检索资料"]),
            "请只输出 json，不要输出 Markdown，不要输出解释。",
            "不要编造具体数据、年份、金额、比例、增速、排名、市场份额。",
            "如果资料不足，只做定性表述。",
            "输出必须是一个 JSON 对象，下面是示例：",
            json.dumps(example, ensure_ascii=False, indent=2),
        ]
    )


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

