from __future__ import annotations

from pathlib import Path

CHAPTER1_MODEL_NAME = "deepseek-v4-pro"
CHAPTER1_MODEL_MODE = "thinking"
CHAPTER1_TEMPERATURE = 0.2
CHAPTER1_RESPONSE_FORMAT = {"type": "json_object"}
CHAPTER1_THINKING_CONFIG = {"thinking": {"type": "enabled"}}
CHAPTER1_REASONING_EFFORT = "high"
CHAPTER1_DIRECT_GENERATION_ONLY = True

CHAPTER1_TASK_REPLAY_DIR = Path("output/chapter1_replays")
CHAPTER1_TASK_SNAPSHOT_DIR = Path("output/chapter1_tasks")

MISSING_MARKER_PREFIX = "【待补充："
MISSING_MARKER_SUFFIX = "】"

CHAPTER1_SECTION_TIMEOUT_SECONDS = 360
CHAPTER1_REPAIR_TIMEOUT_SECONDS = 360
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
        "target_blocks": 2,
        "min_body_chars": 360,
        "section_goal": "说明行业数字化背景下该类产品出现的产业原因，并将产品定位为工业三维数字化和数字孪生链条中的基础建模环节。不得展开技术流程细节，不得写企业介绍。",
        "avoid_topics": ["具体工作流程", "技术参数", "供应链", "企业名称"],
    },
    {
        "key": "definition",
        "title": "定义",
        "required_block_types": ["definition", "scope"],
        "target_blocks": 2,
        "min_body_chars": 320,
        "section_goal": "用正式行业分类语言定义该类产品，并说明其行业边界、包含内容和排除内容。重点为后续市场口径提供定义基础。",
        "avoid_topics": ["行业趋势", "政策环境", "供应链"],
    },
    {
        "key": "working_principle",
        "title": "工作原理",
        "required_block_types": ["principle", "process", "application"],
        "target_blocks": 3,
        "min_body_chars": 480,
        "section_goal": "按数据输入、智能识别、模型重建、工程输出四个环节解释工作原理。只讲必要技术逻辑，不写宣传性效果。",
        "avoid_topics": ["市场规模", "企业竞争", "供应链"],
    },
    {
        "key": "product_attributes",
        "title": "产品属性",
        "required_block_types": ["features", "advantages"],
        "target_blocks": 2,
        "min_body_chars": 360,
        "section_goal": "说明该产品的软件属性、算法属性、工程交付属性和工业场景属性，突出其区别于普通扫描硬件、消费级建模和纯可视化平台。",
        "avoid_topics": ["技术流程重复", "政策环境", "供应链"],
    },
    {
        "key": "technical_specifications",
        "title": "技术规范",
        "required_block_types": ["specification", "parameters"],
        "target_blocks": 2,
        "min_body_chars": 360,
        "section_goal": "在没有具体数值时，写成关键技术要求，不得伪造精度、阈值、速度、格式兼容性等具体指标。若资料事实包提供具体参数，才可写入。",
        "avoid_topics": ["虚构数值", "无来源标准", "重复工作原理"],
    },
    {
        "key": "industry_history",
        "title": "行业发展历程",
        "required_block_types": ["history", "timeline"],
        "target_blocks": 2,
        "min_body_chars": 360,
        "section_goal": "概括行业从人工建模、数字化采集、半自动处理到智能建模的演进逻辑。不得两段重复同一演进链条。",
        "avoid_topics": ["详细技术流程", "供应链"],
    },
    {
        "key": "industry_environment",
        "title": "行业发展环境",
        "required_block_types": ["policy", "market", "technology"],
        "target_blocks": 3,
        "min_body_chars": 540,
        "section_goal": "从政策环境、需求环境、技术环境三方面说明行业发展条件。政策表述必须来自 evidence_facts，没有政策事实时只能写一般性背景。",
        "avoid_topics": ["虚构政策名称", "市场规模数据", "企业名称"],
    },
    {
        "key": "industry_trends",
        "title": "行业发展趋势",
        "required_block_types": ["trend", "market", "competition"],
        "target_blocks": 3,
        "min_body_chars": 540,
        "section_goal": "从技术演进、应用深化、竞争格局三方面写趋势，必须承接市场口径。不得写成泛泛的智能制造口号。",
        "avoid_topics": ["定量预测", "市场份额", "企业排名"],
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
        "target_blocks": 6,
        "min_body_chars": 900,
        "section_goal": "按固定六段说明供应链总述、上游数据采集与基础软硬件、中游算法平台与工程交付、下游流程工业应用、核心挑战、发展方向。",
        "avoid_topics": ["分销渠道泛写", "标题式冒号", "企业名称"],
        "generate_strategy": "per_required_block",
    },
]

SECTION_LOOKUP = {item["key"]: item for item in SECTION_SPECS}
SECTION_ORDER = [item["key"] for item in SECTION_SPECS]

CHAPTER1_SUPPLY_CHAIN_BLOCK_ORDER = [
    "supply_chain_overview",
    "upstream",
    "midstream",
    "downstream",
    "core_challenges",
    "development_direction",
]

CHAPTER1_SUPPLY_CHAIN_SLOT_TITLES = {
    "supply_chain_overview": "行业供应链总述",
    "upstream": "上游数据采集与基础软硬件",
    "midstream": "中游算法平台与工程交付",
    "downstream": "下游流程工业应用场景",
    "core_challenges": "行业供应链的核心特征与面临的挑战",
    "development_direction": "行业供应链的发展方向",
}

SECTION_MAX_TOKENS = {
    "background_overview": 1800,
    "definition": 1600,
    "working_principle": 2200,
    "product_attributes": 1800,
    "technical_specifications": 2200,
    "industry_history": 1800,
    "industry_environment": 3000,
    "industry_trends": 3000,
    "industry_supply_chain": 5200,
}

EXPORTABLE_STATUSES = {"completed", "completed_with_missing"}
TASK_TERMINAL_STATUSES = {"completed", "completed_with_missing", "failed", "cancelled"}
