from __future__ import annotations

from pathlib import Path

CHAPTER1_MODEL_NAME = "deepseek-v4-pro"
CHAPTER1_MODEL_MODE = "thinking"
CHAPTER1_RESPONSE_FORMAT = {"type": "json_object"}
CHAPTER1_THINKING_CONFIG = {"thinking": {"type": "enabled"}}
CHAPTER1_REASONING_EFFORT = "high"
CHAPTER1_DIRECT_GENERATION_ONLY = True

CHAPTER1_TASK_REPLAY_DIR = Path("output/chapter1_replays")
CHAPTER1_TASK_SNAPSHOT_DIR = Path("output/chapter1_tasks")

MISSING_MARKER_PREFIX = "【待补充："
MISSING_MARKER_SUFFIX = "】"

CHAPTER1_SECTION_TIMEOUT_SECONDS = 240
CHAPTER1_REPAIR_TIMEOUT_SECONDS = 240
CHAPTER1_PROBE_TIMEOUT_SECONDS = 30
CHAPTER1_REPAIR_ATTEMPT_LIMIT = 2
CHAPTER1_FORBID_COMPANY_NAME_IN_BODY = True
CHAPTER1_FORBID_QUANTITATIVE_UNCERTAIN_DATA = True
CHAPTER1_FORBID_COLON_IN_BODY = True
CHAPTER1_CONSULTING_STYLE = True

SECTION_SPECS = [
    {
        "key": "background_overview",
        "title": "背景与概述",
        "required_block_types": ["intro", "product_position"],
        "min_body_chars": 180,
    },
    {
        "key": "definition",
        "title": "定义",
        "required_block_types": ["definition", "scope"],
        "min_body_chars": 160,
    },
    {
        "key": "working_principle",
        "title": "工作原理",
        "required_block_types": ["principle", "process", "application"],
        "min_body_chars": 220,
    },
    {
        "key": "product_attributes",
        "title": "产品属性",
        "required_block_types": ["features", "advantages"],
        "min_body_chars": 200,
    },
    {
        "key": "technical_specifications",
        "title": "技术规范",
        "required_block_types": ["specification", "parameters"],
        "min_body_chars": 220,
    },
    {
        "key": "industry_history",
        "title": "行业发展历程",
        "required_block_types": ["history", "timeline"],
        "min_body_chars": 180,
    },
    {
        "key": "industry_environment",
        "title": "行业发展环境",
        "required_block_types": ["policy", "market", "technology"],
        "min_body_chars": 240,
    },
    {
        "key": "industry_trends",
        "title": "行业发展趋势",
        "required_block_types": ["trend", "market", "competition"],
        "min_body_chars": 240,
    },
    {
        "key": "industry_supply_chain",
        "title": "行业供应链",
        "required_block_types": [
            "supply_chain_overview",
            "upstream",
            "midstream",
            "downstream",
            "core_challenges",
            "development_direction",
        ],
        "min_body_chars": 900,
    },
]

SECTION_LOOKUP = {item["key"]: item for item in SECTION_SPECS}
SECTION_ORDER = [item["key"] for item in SECTION_SPECS]

SECTION_MAX_TOKENS = {
    "background_overview": 1800,
    "definition": 1600,
    "working_principle": 2200,
    "product_attributes": 1800,
    "technical_specifications": 2200,
    "industry_history": 1800,
    "industry_environment": 3600,
    "industry_trends": 3600,
    "industry_supply_chain": 4200,
}

EXPORTABLE_STATUSES = {"completed", "completed_with_missing"}
TASK_TERMINAL_STATUSES = {"completed", "completed_with_missing", "failed", "cancelled"}
