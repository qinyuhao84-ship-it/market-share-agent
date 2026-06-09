from __future__ import annotations

from report_automation.other_proof.chapter1 import (
    Chapter1ContentBlock,
    Chapter1SemanticDraft,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    semantic_draft_to_legacy_sections,
)


def test_semantic_draft_to_legacy_sections_keeps_section_order_and_merges_heading():
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
                        heading="产品定义",
                        body="这是一段足够长的正文内容，用于验证 heading 和 body 会合并成一段。",
                        source_refs=["source_001"],
                    )
                ],
                status=Chapter1SectionStatus.COMPLETED,
            ),
            Chapter1SemanticSection(
                section_id="industry_trends",
                section_title="行业发展趋势",
                content_blocks=[],
                missing_items=["趋势资料不足"],
                status=Chapter1SectionStatus.FAILED,
            ),
        ],
    )

    legacy_sections = semantic_draft_to_legacy_sections(draft)

    assert len(legacy_sections) == 9
    assert legacy_sections[0]["key"] == "background_overview"
    assert legacy_sections[0]["title"] == "背景与概述"
    assert legacy_sections[0]["paragraphs"][0].startswith("产品定义：")
    assert any("【待补充：" in paragraph for section in legacy_sections for paragraph in section["paragraphs"])

