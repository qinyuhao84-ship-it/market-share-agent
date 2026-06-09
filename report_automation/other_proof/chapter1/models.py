from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from .config import CHAPTER1_MODEL_MODE, CHAPTER1_MODEL_NAME


class Chapter1TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    COMPLETED_WITH_MISSING = "completed_with_missing"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Chapter1SectionStatus(str, Enum):
    PENDING = "pending"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    PARSING = "parsing"
    VALIDATING = "validating"
    REPAIRING = "repairing"
    COMPLETED = "completed"
    COMPLETED_WITH_WARNING = "completed_with_warning"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    USER_EDITED = "user_edited"


class Chapter1MarketScope(BaseModel):
    market_name: str = ""
    parent_market: str = ""
    segmentation_path: List[str] = Field(default_factory=list)
    included_scope: List[str] = Field(default_factory=list)
    excluded_scope: List[str] = Field(default_factory=list)


class Chapter1EvidenceFact(BaseModel):
    fact_id: str
    type: str = "general"
    title: str = ""
    fact: str
    source_title: str = ""
    url: str = ""
    allowed_sections: List[str] = Field(default_factory=list)


class Chapter1GenerationContext(BaseModel):
    raw_product_name: str = ""
    normalized_product_name: str = ""
    product_code: str = ""
    product_category: str = ""
    product_intro: str = ""
    product_capabilities: List[str] = Field(default_factory=list)
    product_outputs: List[str] = Field(default_factory=list)
    excluded_capabilities: List[str] = Field(default_factory=list)
    application_industries: List[str] = Field(default_factory=list)
    application_scenarios: List[str] = Field(default_factory=list)
    target_users: List[str] = Field(default_factory=list)
    market_scope: Chapter1MarketScope = Field(default_factory=Chapter1MarketScope)
    evidence_facts: List[Chapter1EvidenceFact] = Field(default_factory=list)
    writing_style: str = "consulting_report"


class Chapter1TaskCreateRequest(BaseModel):
    company_name: str = ""
    product_name: str = Field(..., min_length=1)
    product_code: str = ""
    product_intro: str = ""
    market_name: str = ""
    proof_scope: str = ""
    target_scope: str = ""
    chapter1_context: Chapter1GenerationContext = Field(default_factory=Chapter1GenerationContext)
    use_cache: bool = True
    enable_web_retrieval: bool = False
    allow_incomplete_export: bool = False
    generation_mode: Literal["balanced", "strict", "fast"] = "strict"
    model_name: str = Field(default=CHAPTER1_MODEL_NAME)

    model_config = ConfigDict(extra="ignore")


class Chapter1Source(BaseModel):
    source_id: str
    title: str = ""
    url: str = ""
    publisher: str = ""
    publish_date: str = ""
    retrieved_at: str = ""
    source_type: str = "web"
    reliability_level: str = "unknown"
    related_sections: List[str] = Field(default_factory=list)
    extracted_facts: List[str] = Field(default_factory=list)
    raw_excerpt: str = ""


class Chapter1ContentBlock(BaseModel):
    block_id: str
    block_type: str
    heading: str = ""
    body: str
    source_refs: List[str] = Field(default_factory=list)
    confidence: str = "medium"
    validation_issues: List[str] = Field(default_factory=list)
    generated_by: str = CHAPTER1_MODEL_NAME
    edited_by_user: bool = False


class Chapter1SemanticSection(BaseModel):
    section_id: str
    section_title: str
    section_goal: str = ""
    content_blocks: List[Chapter1ContentBlock] = Field(default_factory=list)
    sources: List[Chapter1Source] = Field(default_factory=list)
    status: Chapter1SectionStatus = Chapter1SectionStatus.PENDING
    validation_score: int = 0
    validation_issues: List[str] = Field(default_factory=list)
    missing_items: List[str] = Field(default_factory=list)
    repair_attempts: int = 0
    warnings: List[str] = Field(default_factory=list)


class Chapter1SemanticDraft(BaseModel):
    draft_id: str
    task_id: str
    company_name: str = ""
    product_name: str
    model_name: str = Field(default=CHAPTER1_MODEL_NAME)
    model_mode: str = Field(default=CHAPTER1_MODEL_MODE)
    schema_version: str = "chapter1_semantic_v1"
    template_version: str = "legacy_other_docx_v1"
    sections: List[Chapter1SemanticSection] = Field(default_factory=list)
    sources: List[Chapter1Source] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    replay_file_path: str = ""


class Chapter1TaskSnapshot(BaseModel):
    task_id: str
    status: Chapter1TaskStatus
    progress: int = 0
    current_stage: str = ""
    current_section: str = ""
    company_name: str = ""
    product_name: str
    model_name: str = Field(default=CHAPTER1_MODEL_NAME)
    model_mode: str = Field(default=CHAPTER1_MODEL_MODE)
    generation_mode: str = "strict"
    use_cache: bool = True
    enable_web_retrieval: bool = False
    allow_incomplete_export: bool = False
    chapter1_context: Chapter1GenerationContext = Field(default_factory=Chapter1GenerationContext)
    semantic_draft: Optional[Chapter1SemanticDraft] = None
    legacy_sections: List[dict] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    can_export: bool = False
    replay_file_path: str = ""
    cancelled: bool = False
    created_at: str = ""
    updated_at: str = ""
    retrieval_records: List[Dict[str, Any]] = Field(default_factory=list)
    generation_records: List[Dict[str, Any]] = Field(default_factory=list)
    repair_records: List[Dict[str, Any]] = Field(default_factory=list)
    raw_model_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    parsed_outputs: List[Dict[str, Any]] = Field(default_factory=list)
    validation_results: List[Dict[str, Any]] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)


class Chapter1TaskError(RuntimeError):
    pass


class Chapter1TaskNotFoundError(Chapter1TaskError):
    pass
