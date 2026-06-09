from __future__ import annotations

import os
import platform
import subprocess
from urllib.parse import urlparse

from fastapi import APIRouter

from inference import InferenceConfig
from inference.llm_orchestrator import LLMOrchestrator
from report_automation.other_proof.core import CHAPTER1_REQUEST_TIMEOUT_SECONDS, CHAPTER1_RESPONSE_FORMAT
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
