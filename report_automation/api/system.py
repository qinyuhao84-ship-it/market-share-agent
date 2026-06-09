from __future__ import annotations

import os
import platform
import subprocess
import time
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter

from inference import InferenceConfig
from inference.llm_orchestrator import LLMOrchestrator
from report_automation.other_proof.core import CHAPTER1_REQUEST_TIMEOUT_SECONDS, CHAPTER1_RESPONSE_FORMAT
from report_automation.other_proof.chapter1.config import (
    CHAPTER1_DIRECT_GENERATION_ONLY,
    CHAPTER1_MODEL_MODE,
    CHAPTER1_MODEL_NAME,
    CHAPTER1_PROBE_TIMEOUT_SECONDS,
    CHAPTER1_RESPONSE_FORMAT as CHAPTER1_TASK_RESPONSE_FORMAT,
)
from report_automation.other_proof.chapter1.deepseek_client import DeepSeekV4ProChapter1Client
from report_automation.other_proof.chapter1.json_parser import parse_deepseek_json_object
from report_automation.settings import FRONTEND_DIR, OTHER_TEMPLATE_PATH, ROOT_DIR, SELF_TEMPLATE_PATH

router = APIRouter(prefix="/system")


@router.get("/debug")
def system_debug():
    config = InferenceConfig()
    orchestrator = LLMOrchestrator.from_config(config)
    api_key_source = getattr(orchestrator, "api_key_source", "") or config.llm_api_key_env
    api_base = config.llm_api_base or ""
    return {
        "status": "ok",
        "runtime": {
            "python": platform.python_version(),
            "port_env_present": bool(os.getenv("PORT")),
        },
        "deploy": {
            "git_commit": _current_git_commit(),
            "render_service_name_present": bool(os.getenv("RENDER_SERVICE_NAME")),
            "render_git_commit": os.getenv("RENDER_GIT_COMMIT", ""),
        },
        "llm": {
            "enabled_by_config": bool(config.llm_enabled),
            "available": orchestrator.is_available(),
            "api_base": _safe_url(api_base),
            "api_key_source": api_key_source,
            "api_key_present": bool(os.getenv(api_key_source or "")),
            "model": config.llm_model,
        },
        "chapter1": {
            "timeout_seconds": CHAPTER1_REQUEST_TIMEOUT_SECONDS,
            "response_format": CHAPTER1_RESPONSE_FORMAT,
        },
        "chapter1_task": {
            "model": CHAPTER1_MODEL_NAME,
            "model_mode": CHAPTER1_MODEL_MODE,
            "response_format": CHAPTER1_TASK_RESPONSE_FORMAT,
            "direct_generation_only": CHAPTER1_DIRECT_GENERATION_ONLY,
            "local_retrieval": "disabled",
            "probe_endpoint": "/system/debug/chapter1-llm-probe",
        },
        "files": {
            "frontend_index_exists": (FRONTEND_DIR / "index.html").is_file(),
            "self_template_exists": SELF_TEMPLATE_PATH.is_file(),
            "other_template_exists": OTHER_TEMPLATE_PATH.is_file(),
        },
    }


def _safe_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.scheme or not parsed.netloc:
        return value
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


def _current_git_commit() -> str:
    render_commit = os.getenv("RENDER_GIT_COMMIT", "").strip()
    if render_commit:
        return render_commit
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
            timeout=2,
        )
    except Exception:
        return ""
    return result.stdout.strip()


@router.get("/debug/chapter1-llm-probe")
def chapter1_llm_probe():
    config = InferenceConfig()
    client = DeepSeekV4ProChapter1Client(config)

    api_key_source = ""
    api_key_present = False
    api_base = config.llm_api_base or ""
    try:
        orchestrator = getattr(client, "orchestrator", None)
        api_key_source = getattr(orchestrator, "api_key_source", "") or config.llm_api_key_env
        api_key_present = bool(os.getenv(api_key_source or ""))
    except Exception:
        api_key_source = config.llm_api_key_env
        api_key_present = bool(os.getenv(api_key_source or ""))

    started = time.monotonic()
    messages = [
        {
            "role": "system",
            "content": "你是接口健康检查器。只输出 json，不要输出解释。",
        },
        {
            "role": "user",
            "content": '请输出一个 JSON 对象：{"ok":true,"module":"chapter1","model":"deepseek-v4-pro"}',
        },
    ]

    try:
        raw = client.complete_json(
            messages=messages,
            section_key="system_probe",
            max_output_tokens=256,
            timeout_seconds=CHAPTER1_PROBE_TIMEOUT_SECONDS,
            retry_max_attempts=0,
        )
        parsed = parse_deepseek_json_object(raw)
        return {
            "ok": True,
            "model": CHAPTER1_MODEL_NAME,
            "model_mode": CHAPTER1_MODEL_MODE,
            "direct_generation_only": CHAPTER1_DIRECT_GENERATION_ONLY,
            "api_base": _safe_url(api_base),
            "api_key_source": api_key_source,
            "api_key_present": api_key_present,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "parsed": parsed,
            "raw_length": len(raw),
        }
    except Exception as exc:
        status_code = 0
        root: Exception = exc
        while getattr(root, "__cause__", None) is not None:
            root = getattr(root, "__cause__")
        if isinstance(root, httpx.HTTPStatusError):
            status_code = int(root.response.status_code)

        return {
            "ok": False,
            "model": CHAPTER1_MODEL_NAME,
            "model_mode": CHAPTER1_MODEL_MODE,
            "direct_generation_only": CHAPTER1_DIRECT_GENERATION_ONLY,
            "api_base": _safe_url(api_base),
            "api_key_source": api_key_source,
            "api_key_present": api_key_present,
            "duration_ms": int((time.monotonic() - started) * 1000),
            "error_type": exc.__class__.__name__,
            "root_error_type": root.__class__.__name__,
            "status_code": status_code,
            "error": str(exc)[:500],
        }
