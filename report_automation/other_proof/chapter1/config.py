from __future__ import annotations

from pathlib import Path

CHAPTER1_MODEL_NAME = "deepseek-v4-flash"
CHAPTER1_MODEL_MODE = "non-thinking"
CHAPTER1_RESPONSE_FORMAT = {"type": "json_object"}

CHAPTER1_TASK_REPLAY_DIR = Path("output/chapter1_replays")
CHAPTER1_TASK_SNAPSHOT_DIR = Path("output/chapter1_tasks")

MISSING_MARKER_PREFIX = "【待补充："
MISSING_MARKER_SUFFIX = "】"

CHAPTER1_SECTION_TIMEOUT_SECONDS = 180
CHAPTER1_REPAIR_ATTEMPT_LIMIT = 2

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
        "required_block_types": ["upstream", "midstream", "downstream"],
        "min_body_chars": 220,
    },
]

SECTION_LOOKUP = {item["key"]: item for item in SECTION_SPECS}
SECTION_ORDER = [item["key"] for item in SECTION_SPECS]

SECTION_QUERY_TEMPLATES = {
    "background_overview": ["{product_name} 行业 应用", "{product_name} 产品 概述"],
    "definition": ["{product_name} 定义", "{product_name} 标准 术语"],
    "working_principle": ["{product_name} 工作原理", "{product_name} 技术方案"],
    "product_attributes": ["{product_name} 产品特点", "{product_name} 应用场景"],
    "technical_specifications": ["{product_name} 技术参数", "{product_name} 技术指标 标准"],
    "industry_history": ["{product_name} 行业 发展历程"],
    "industry_environment": ["{product_name} 行业 政策 市场 技术"],
    "industry_trends": ["{product_name} 行业 发展趋势"],
    "industry_supply_chain": ["{product_name} 产业链 上游 下游"],
}

SECTION_MAX_TOKENS = {
    "background_overview": 1800,
    "definition": 1600,
    "working_principle": 2200,
    "product_attributes": 1800,
    "technical_specifications": 2200,
    "industry_history": 1800,
    "industry_environment": 2600,
    "industry_trends": 2600,
    "industry_supply_chain": 2400,
}

EXPORTABLE_STATUSES = {"completed", "completed_with_missing"}
TASK_TERMINAL_STATUSES = {"completed", "completed_with_missing", "failed", "cancelled"}
