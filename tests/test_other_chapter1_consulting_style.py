from __future__ import annotations

from report_automation.other_proof.chapter1 import (
    Chapter1ContentBlock,
    Chapter1SemanticSection,
    SECTION_LOOKUP,
    build_repair_prompt,
    build_section_prompt,
)


def test_section_prompt_requires_consulting_style_rules():
    prompt = build_section_prompt(
        company_name="南京强思数字科技有限公司",
        product_name="示例产品",
        section_spec=SECTION_LOOKUP["background_overview"],
        sources=[],
        completed_section_summaries=["背景与概述 这是一段摘要"],
    )

    assert "正式咨询行业研究报告正文" in prompt
    assert "heading 字段必须输出为空字符串" in prompt
    assert "正文中禁止出现企业名称“南京强思数字科技有限公司”及其简称。" in prompt
    assert "冒号或英文冒号" in prompt
    assert "产品名称：示例产品" in prompt
    assert "企业：示例产品" not in prompt


def test_supply_chain_section_prompt_requires_six_blocks():
    prompt = build_section_prompt(
        company_name="示例公司",
        product_name="示例产品",
        section_spec=SECTION_LOOKUP["industry_supply_chain"],
        sources=[],
        completed_section_summaries=[],
    )

    assert "本小节必须输出 6 个 content_blocks" in prompt
    assert "supply_chain_overview" in prompt
    assert "core_challenges" in prompt
    assert "development_direction" in prompt
    assert '"heading": ""' in prompt


def test_supply_chain_repair_prompt_requires_missing_only():
    section = Chapter1SemanticSection(
        section_id="industry_supply_chain",
        section_title="行业供应链",
        content_blocks=[
            Chapter1ContentBlock(
                block_id="industry_supply_chain_001",
                block_type="supply_chain_overview",
                heading="",
                body="该系统所处供应链围绕数据采集和模型转换展开。",
                source_refs=["source_001"],
            )
        ],
        missing_items=["downstream", "core_challenges", "development_direction"],
    )

    prompt = build_repair_prompt(
        company_name="示例公司",
        product_name="示例产品",
        section_spec=SECTION_LOOKUP["industry_supply_chain"],
        section=section,
        sources=[],
    )

    assert "本小节的完整结构固定为 6 个 block_type" in prompt
    assert "当前只输出缺失项" in prompt
    assert "缺失项必须对应 supply_chain_overview、upstream、midstream、downstream、core_challenges、development_direction 之一。" in prompt
    assert '"heading": ""' in prompt
