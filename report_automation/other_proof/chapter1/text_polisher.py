from __future__ import annotations

import re
from typing import Sequence

LABEL_PREFIX_PATTERNS = (
    "产品定义",
    "行业定位与价值",
    "应用范围",
    "核心技术原理",
    "关键工作流程",
    "工业应用模式",
    "算法架构与训练数据",
    "系统部署与实时处理特性",
    "核心功能特性",
    "产品优势",
    "技术规格",
    "处理性能",
    "性能指标",
    "从传统建模到AI智能建模的演变",
    "工业三维建模发展关键阶段",
    "政策驱动智能制造与数字化转型",
    "工业领域数字化建模需求持续扩大",
    "深度学习与点云处理融合推动技术变革",
    "AI驱动三维建模智能化跃迁",
    "政策红利与工业数字化转型需求共振",
    "行业竞争聚焦算法精度与落地能力",
    "上游",
    "中游",
    "下游",
    "技术组件与数据采集",
    "系统开发与集成",
    "工业应用与服务",
    "核心特征与面临的挑战",
    "发展方向",
)

UNCERTAIN_WORDS = (
    "可能",
    "或许",
    "大概",
    "预计",
    "预估",
    "有望",
    "约",
    "左右",
    "以上",
    "以下",
    "超过",
    "接近",
    "推测",
    "猜测",
    "不确定",
    "据公开资料",
    "暂无资料",
    "待补充",
    "请人工补充",
)


def polish_chapter1_paragraph(text: str, *, company_name: str = "") -> str:
    cleaned = str(text or "").strip()
    if not cleaned:
        return ""

    cleaned = _remove_company_name(cleaned, company_name)
    cleaned = _remove_leading_labels(cleaned)
    cleaned = _remove_ai_markers(cleaned)
    cleaned = _normalize_colons(cleaned)
    cleaned = _normalize_spaces(cleaned)
    cleaned = _normalize_punctuation_spacing(cleaned)
    return cleaned.strip()


def polish_paragraphs(paragraphs: Sequence[str], *, company_name: str = "") -> list[str]:
    result: list[str] = []
    for item in paragraphs:
        cleaned = polish_chapter1_paragraph(item, company_name=company_name)
        if cleaned:
            result.append(cleaned)
    return result


def _remove_company_name(text: str, company_name: str) -> str:
    cleaned = text
    company = str(company_name or "").strip()
    candidates: list[str] = []
    if company:
        candidates.append(company)
        candidates.append(company.replace("有限公司", ""))
        candidates.append(company.replace("股份有限公司", ""))
        candidates.append(company.replace("科技有限公司", ""))
    for item in candidates:
        value = item.strip()
        if value:
            cleaned = cleaned.replace(value, "该产品")
    return cleaned


def _remove_leading_labels(text: str) -> str:
    cleaned = text.strip()
    changed = True
    while changed:
        changed = False
        for label in LABEL_PREFIX_PATTERNS:
            for mark in ("：", ":"):
                prefix = f"{label}{mark}"
                if cleaned.startswith(prefix):
                    cleaned = cleaned[len(prefix) :].strip()
                    changed = True
                    break
            if changed:
                break
    cleaned = re.sub(r"^[一-龥A-Za-z0-9（）()、]{2,18}[：:]\s*", "", cleaned)
    cleaned = re.sub(r"^[一二三四五六七八九十]+[、.．]\s*", "", cleaned)
    return cleaned.strip()


def _remove_ai_markers(text: str) -> str:
    cleaned = text
    replacements = {
        "可能采用": "通常采用",
        "有望持续提升": "将持续深化",
        "有望": "将",
        "可能": "通常",
        "预计": "将",
        "大概": "",
        "或许": "",
        "据公开资料": "",
    }
    for old, new in replacements.items():
        cleaned = cleaned.replace(old, new)
    return cleaned


def _normalize_colons(text: str) -> str:
    cleaned = text.replace("：", "，").replace(":", "，")
    cleaned = re.sub(r"，\s*，+", "，", cleaned)
    cleaned = cleaned.replace("，。", "。")
    return cleaned


def _normalize_spaces(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    cleaned = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", cleaned)
    return cleaned


def _normalize_punctuation_spacing(text: str) -> str:
    cleaned = re.sub(r"\s+([，。；、])", r"\1", text)
    cleaned = re.sub(r"([，。；、])\s+", r"\1", cleaned)
    cleaned = cleaned.replace(" ,", "，").replace(", ", "，")
    return cleaned

