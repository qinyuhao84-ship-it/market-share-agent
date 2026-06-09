from __future__ import annotations

import json
import logging
import os
import time

from fastapi import APIRouter, HTTPException

from inference import InferenceConfig
from report_automation.other_proof import (
    OtherProofError,
    OtherProofTimeoutError,
    generate_other_chapter1,
    generate_other_chapter1_section,
    lookup_other_companies,
)
from report_automation.schemas import Chapter1Request, Chapter1SectionRequest, CompanyLookupRequest
from report_automation.services.errors import other_proof_error_detail

router = APIRouter(prefix="/other-proof")
logger = logging.getLogger("uvicorn.error")


@router.post("/chapter1")
def generate_other_proof_chapter1_api(payload: Chapter1Request):
    started_at = time.monotonic()
    config = InferenceConfig()
    logger.info(
        "chapter1_api_started %s",
        json.dumps(
            {
                "product_name_present": bool(payload.product_name and payload.product_name.strip()),
                "allow_partial": bool(payload.allow_partial),
                "llm_enabled": bool(config.llm_enabled),
                "llm_api_base": config.llm_api_base,
                "llm_api_key_env": config.llm_api_key_env,
                "llm_api_key_present": bool(config.llm_api_key_env and os.getenv(config.llm_api_key_env)),
                "llm_model": config.llm_model,
            },
            ensure_ascii=False,
        ),
    )
    try:
        result = generate_other_chapter1(
            payload.product_name,
            config,
            allow_partial=bool(payload.allow_partial),
        )
        logger.info(
            "chapter1_api_succeeded %s",
            json.dumps(
                {
                    "elapsed_ms": int((time.monotonic() - started_at) * 1000),
                    "section_count": len(result.get("sections") or []),
                    "warning_count": len(result.get("warnings") or []),
                    "placeholder_counts": _chapter1_placeholder_counts(result.get("sections") or []),
                    "has_replay_file_path": bool(result.get("replay_file_path")),
                },
                ensure_ascii=False,
            ),
        )
        return result
    except OtherProofTimeoutError as exc:
        _log_chapter1_api_error(started_at, exc, status_code=504)
        raise HTTPException(status_code=504, detail=other_proof_error_detail(exc)) from exc
    except OtherProofError as exc:
        _log_chapter1_api_error(started_at, exc, status_code=400)
        raise HTTPException(status_code=400, detail=other_proof_error_detail(exc)) from exc
    except Exception as exc:
        _log_chapter1_api_error(started_at, exc, status_code=500)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/chapter1-section")
def generate_other_proof_chapter1_section_api(payload: Chapter1SectionRequest):
    try:
        return generate_other_chapter1_section(
            payload.product_name,
            payload.section_key,
            [item.model_dump() for item in payload.generated_sections],
            InferenceConfig(),
        )
    except OtherProofTimeoutError as exc:
        raise HTTPException(status_code=504, detail=other_proof_error_detail(exc)) from exc
    except OtherProofError as exc:
        raise HTTPException(status_code=400, detail=other_proof_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def _chapter1_placeholder_counts(sections):
    counts = {}
    for section in sections:
        if not isinstance(section, dict):
            continue
        key = str(section.get("key") or "").strip() or "unknown"
        count = 0
        for paragraph in section.get("paragraphs") or []:
            text = str(paragraph or "").strip()
            if "待补充" in text or text == "暂无内容":
                count += 1
        if count:
            counts[key] = count
    return counts


def _log_chapter1_api_error(started_at: float, exc: Exception, *, status_code: int) -> None:
    logger.error(
        "chapter1_api_failed %s",
        json.dumps(
            {
                "elapsed_ms": int((time.monotonic() - started_at) * 1000),
                "status_code": status_code,
                "error_type": exc.__class__.__name__,
                "message": str(exc),
                "has_replay_file_path": bool(getattr(exc, "replay_file_path", "")),
            },
            ensure_ascii=False,
        ),
    )


@router.post("/company-lookup")
def lookup_other_proof_companies_api(payload: CompanyLookupRequest):
    try:
        return lookup_other_companies([item.model_dump() for item in payload.companies])
    except OtherProofError as exc:
        raise HTTPException(status_code=400, detail=other_proof_error_detail(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
