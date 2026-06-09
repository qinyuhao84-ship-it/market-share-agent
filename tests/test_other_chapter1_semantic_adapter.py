from __future__ import annotations

from report_automation.other_proof.chapter1 import (
    Chapter1ContentBlock,
    Chapter1SemanticDraft,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    semantic_draft_to_legacy_sections,
)


def test_semantic_draft_to_legacy_sections_polishes_body_without_heading_colon():
    draft = Chapter1SemanticDraft(
        draft_id="draft-001",
        task_id="task-001",
        company_name="南京强思数字科技有限公司",
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
                        body="产品定义：南京强思数字科技有限公司推出的系统适用于工业建模。",
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
    assert "：" not in legacy_sections[0]["paragraphs"][0]
    assert "南京强思数字科技有限公司" not in legacy_sections[0]["paragraphs"][0]
    assert not legacy_sections[0]["paragraphs"][0].startswith("产品定义")
    assert any("【待补充：" in paragraph for section in legacy_sections for paragraph in section["paragraphs"])


def test_semantic_draft_to_legacy_sections_outputs_six_supply_chain_paragraphs():
    draft = Chapter1SemanticDraft(
        draft_id="draft-002",
        task_id="task-002",
        company_name="示例公司",
        product_name="示例产品",
        sections=[
            Chapter1SemanticSection(
                section_id="industry_supply_chain",
                section_title="行业供应链",
                content_blocks=[
                    Chapter1ContentBlock(
                        block_id="industry_supply_chain_001",
                        block_type="supply_chain_overview",
                        heading="供应链总述",
                        body="行业供应链总述：该系统所处供应链围绕数据采集和模型转换展开。",
                        source_refs=["source_001"],
                    ),
                    Chapter1ContentBlock(
                        block_id="industry_supply_chain_002",
                        block_type="upstream",
                        heading="上游供应链",
                        body="上游：技术组件与数据采集：上游环节主要提供传感设备和算力资源。",
                        source_refs=["source_002"],
                    ),
                    Chapter1ContentBlock(
                        block_id="industry_supply_chain_003",
                        block_type="midstream",
                        heading="中游制造与集成",
                        body="中游制造与集成：相关企业负责算法训练、软件开发和系统交付。",
                        source_refs=["source_003"],
                    ),
                    Chapter1ContentBlock(
                        block_id="industry_supply_chain_004",
                        block_type="downstream",
                        heading="下游应用与分销",
                        body="下游应用与分销：产品主要服务于流程工业企业和工程设计单位。",
                        source_refs=["source_004"],
                    ),
                    Chapter1ContentBlock(
                        block_id="industry_supply_chain_005",
                        block_type="core_challenges",
                        heading="核心特征与挑战",
                        body="核心特征与挑战：该环节具有专业交付要求高、场景差异大的特点。",
                        source_refs=["source_005"],
                    ),
                    Chapter1ContentBlock(
                        block_id="industry_supply_chain_006",
                        block_type="development_direction",
                        heading="发展方向",
                        body="发展方向：未来将继续向标准化、工程化和复用化方向发展。",
                        source_refs=["source_006"],
                    ),
                ],
                status=Chapter1SectionStatus.COMPLETED,
            )
        ],
    )

    legacy_sections = semantic_draft_to_legacy_sections(draft)
    supply_chain = next(item for item in legacy_sections if item["key"] == "industry_supply_chain")

    assert len(supply_chain["paragraphs"]) == 6
    assert all("：" not in paragraph for paragraph in supply_chain["paragraphs"])
    assert not supply_chain["paragraphs"][0].startswith("上游")
    assert "供应链总述" not in supply_chain["paragraphs"][0]


def test_semantic_draft_to_legacy_sections_removes_company_name():
    draft = Chapter1SemanticDraft(
        draft_id="draft-003",
        task_id="task-003",
        company_name="南京强思数字科技有限公司",
        product_name="示例产品",
        sections=[
            Chapter1SemanticSection(
                section_id="definition",
                section_title="定义",
                content_blocks=[
                    Chapter1ContentBlock(
                        block_id="definition_001",
                        block_type="definition",
                        heading="定义",
                        body="南京强思数字科技有限公司推出的系统面向工业建模与运维协同。",
                        source_refs=["source_001"],
                    )
                ],
                status=Chapter1SectionStatus.COMPLETED,
            )
        ],
    )

    legacy_sections = semantic_draft_to_legacy_sections(draft)
    all_paragraphs = "".join(
        paragraph
        for section in legacy_sections
        for paragraph in section["paragraphs"]
    )

    assert "南京强思数字科技有限公司" not in all_paragraphs
    assert "强思数字" not in all_paragraphs
