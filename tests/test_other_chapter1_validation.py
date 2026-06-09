from __future__ import annotations

from report_automation.other_proof.chapter1 import (
    Chapter1ContentBlock,
    Chapter1SemanticDraft,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    Chapter1Source,
    SECTION_LOOKUP,
    validate_draft,
    validate_section,
)


def _long_text(seed: str) -> str:
    return (seed + "，") * 20 + "用于校验逻辑。"


def test_validate_section_without_content_fails():
    spec = SECTION_LOOKUP["background_overview"]
    section = Chapter1SemanticSection(
        section_id="background_overview",
        section_title="背景与概述",
        content_blocks=[],
        sources=[],
    )

    validated = validate_section(section, spec)

    assert validated.status == Chapter1SectionStatus.FAILED
    assert validated.validation_score == 0 or validated.validation_score < 50
    assert "内容块为空" in validated.validation_issues


def test_validate_section_with_content_but_no_sources_fails_on_structure():
    spec = SECTION_LOOKUP["background_overview"]
    section = Chapter1SemanticSection(
        section_id="background_overview",
        section_title="背景与概述",
        content_blocks=[
            Chapter1ContentBlock(
                block_id="background_overview_001",
                block_type="intro",
                heading="产品概述",
                body=_long_text("产品围绕可靠连接场景展开，强调稳定性、兼容性和长期应用价值"),
                source_refs=[],
            )
        ],
        sources=[],
    )

    validated = validate_section(section, spec)

    assert validated.status == Chapter1SectionStatus.FAILED
    assert any("内容块数量不符合要求" in item for item in validated.validation_issues)
    assert any("缺少必要块类型：product_position" in item for item in validated.validation_issues)


def test_validate_section_placeholder_text_is_not_treated_as_real_content():
    spec = SECTION_LOOKUP["definition"]
    section = Chapter1SemanticSection(
        section_id="definition",
        section_title="定义",
        content_blocks=[
            Chapter1ContentBlock(
                block_id="definition_001",
                block_type="definition",
                heading="定义",
                body="待补充，请结合公开资料补充。",
                source_refs=["source_001"],
            )
        ],
        sources=[
            Chapter1Source(
                source_id="source_001",
                title="示例来源",
                url="https://example.com",
            )
        ],
    )

    validated = validate_section(section, spec)

    assert validated.status in {Chapter1SectionStatus.INCOMPLETE, Chapter1SectionStatus.FAILED}
    assert any("占位" in item for item in validated.validation_issues)


def test_validate_section_supply_chain_missing_three_blocks_is_incomplete():
    spec = SECTION_LOOKUP["industry_supply_chain"]
    section = Chapter1SemanticSection(
        section_id="industry_supply_chain",
        section_title="行业供应链",
        content_blocks=[
            Chapter1ContentBlock(
                block_id="industry_supply_chain_001",
                block_type="supply_chain_overview",
                heading="供应链总述",
                body=_long_text("行业供应链围绕协同效率、交付质量和供应稳定性展开，上游、中游、下游三个环节共同影响最终落地效果"),
                source_refs=["source_001"],
            ),
            Chapter1ContentBlock(
                block_id="industry_supply_chain_002",
                block_type="upstream",
                heading="上游供应链",
                body=_long_text("上游主要包括传感设备、扫描采集工具和基础算力资源"),
                source_refs=["source_002"],
            ),
            Chapter1ContentBlock(
                block_id="industry_supply_chain_003",
                block_type="midstream",
                heading="中游制造与集成",
                body=_long_text("中游主要承担算法训练、软件开发、模型转换和系统集成工作"),
                source_refs=["source_001"],
            )
        ],
        sources=[
            Chapter1Source(
                source_id="source_001",
                title="示例来源",
                url="https://example.com",
            )
        ],
    )

    validated = validate_section(section, spec)

    assert validated.status in {Chapter1SectionStatus.INCOMPLETE, Chapter1SectionStatus.FAILED}
    assert "downstream" in validated.missing_items
    assert "core_challenges" in validated.missing_items
    assert "development_direction" in validated.missing_items


def test_validate_section_requires_fixed_paragraph_count():
    spec = SECTION_LOOKUP["background_overview"]
    section = Chapter1SemanticSection(
        section_id="background_overview",
        section_title="背景与概述",
        content_blocks=[
            Chapter1ContentBlock(
                block_id="background_overview_001",
                block_type="intro",
                heading="概述",
                body=_long_text("这是足够长的正文内容，用一段就可以说明产品背景与应用场景"),
                source_refs=["source_001"],
            )
        ],
        sources=[
            Chapter1Source(
                source_id="source_001",
                title="示例来源",
                url="https://example.com",
            )
        ],
    )

    validated = validate_section(section, spec)

    assert validated.status == Chapter1SectionStatus.FAILED
    assert validated.validation_score < 80
    assert any("内容块数量不符合要求" in item for item in validated.validation_issues)


def test_validate_draft_fills_missing_sections():
    draft = Chapter1SemanticDraft(
        draft_id="draft-001",
        task_id="task-001",
        product_name="示例产品",
        sections=[
            Chapter1SemanticSection(
                section_id="background_overview",
                section_title="背景与概述",
                content_blocks=[
                    Chapter1ContentBlock(
                        block_id="background_overview_001",
                        block_type="intro",
                        heading="概述",
                        body=_long_text("产品背景足够充分"),
                        source_refs=["source_001"],
                    )
                ],
                sources=[
                    Chapter1Source(
                        source_id="source_001",
                        title="示例来源",
                        url="https://example.com",
                    )
                ],
            )
        ],
    )

    validated = validate_draft(draft)

    assert len(validated.sections) == 9
    assert validated.sections[0].section_id == "background_overview"
    assert any(section.section_id == "industry_supply_chain" for section in validated.sections)
