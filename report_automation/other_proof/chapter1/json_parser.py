from __future__ import annotations

import json
from typing import Any, Dict


class Chapter1ParseError(RuntimeError):
    def __init__(self, code: str, message: str | None = None) -> None:
        self.code = code
        super().__init__(message or code)


def parse_deepseek_json_object(raw: str) -> Dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        raise Chapter1ParseError("LLM_EMPTY_CONTENT")

    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    else:
        if isinstance(parsed, dict):
            return parsed
        raise Chapter1ParseError("PARSE_FAILED", "LLM 返回的 JSON 不是对象")

    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < 0 or end <= start:
        raise Chapter1ParseError("PARSE_FAILED")

    snippet = text[start : end + 1]
    try:
        parsed = json.loads(snippet)
    except Exception as exc:
        if _looks_truncated(text, snippet):
            raise Chapter1ParseError("PARSE_TRUNCATED_JSON") from exc
        raise Chapter1ParseError("PARSE_FAILED") from exc

    if not isinstance(parsed, dict):
        raise Chapter1ParseError("PARSE_FAILED", "LLM 返回的 JSON 不是对象")
    return parsed


def _looks_truncated(raw: str, snippet: str) -> bool:
    stripped = raw.strip()
    if not stripped.endswith("}"):
        return True
    if raw.count("{") > raw.count("}"):
        return True
    if snippet.count("{") > snippet.count("}"):
        return True
    return False

