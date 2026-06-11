from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from report_automation.other_proof.chapter1 import (
    Chapter1TaskCreateRequest,
    Chapter1TaskError,
    Chapter1TaskNotFoundError,
    Chapter1TaskSnapshot,
    Chapter1TaskStatus,
    chapter1_task_service,
    chapter1_task_store,
)
from report_automation.other_proof.chapter1.config import CHAPTER1_TASK_REPLAY_DIR

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/other-proof/chapter1")

TERMINAL_STATUSES = {
    Chapter1TaskStatus.COMPLETED,
    Chapter1TaskStatus.COMPLETED_WITH_MISSING,
    Chapter1TaskStatus.FAILED,
    Chapter1TaskStatus.CANCELLED,
}

_CHAPTER1_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="chapter1-task")


@router.post("/tasks")
def create_chapter1_task(payload: Chapter1TaskCreateRequest):
    snapshot = chapter1_task_service.start_task(payload)
    if snapshot.status not in TERMINAL_STATUSES:
        _CHAPTER1_EXECUTOR.submit(_run_chapter1_task_safely, snapshot.task_id)
    return _task_status_payload(snapshot)


@router.get("/tasks/{task_id}")
def get_chapter1_task(task_id: str, full: bool = Query(default=False)):
    try:
        snapshot = chapter1_task_store.get(task_id)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Chapter1TaskError as exc:
        logger.warning("chapter1_task_snapshot_unavailable", exc_info=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("chapter1_task_status_failed")
        raise HTTPException(status_code=503, detail="第一章任务状态暂时不可用，请稍后重试") from exc

    if full or snapshot.status in TERMINAL_STATUSES:
        return _full_task_payload(snapshot)
    return _task_status_payload(snapshot)


@router.get("/tasks/{task_id}/replay")
def download_chapter1_replay(task_id: str):
    try:
        snapshot = chapter1_task_store.get(task_id)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Chapter1TaskError as exc:
        logger.warning("chapter1_task_replay_snapshot_unavailable", exc_info=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    replay_path = _resolve_replay_path(snapshot)
    if replay_path is None or not replay_path.is_file():
        raise HTTPException(status_code=404, detail="第一章调试回放文件不存在或已被清理")

    return FileResponse(
        replay_path,
        media_type="application/json",
        filename=replay_path.name,
    )


@router.post("/tasks/{task_id}/cancel")
def cancel_chapter1_task(task_id: str):
    try:
        return chapter1_task_service.cancel_task(task_id)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Chapter1TaskError as exc:
        logger.warning("chapter1_task_cancel_failed", exc_info=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/sections/{section_key}/retry")
def retry_chapter1_section(task_id: str, section_key: str):
    try:
        return chapter1_task_service.retry_section(task_id, section_key)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Chapter1TaskError as exc:
        logger.warning("chapter1_task_retry_failed", exc_info=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/sections/{section_key}/repair")
def repair_chapter1_section(task_id: str, section_key: str):
    try:
        return chapter1_task_service.repair_section(task_id, section_key)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Chapter1TaskError as exc:
        logger.warning("chapter1_task_repair_failed", exc_info=True)
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _run_chapter1_task_safely(task_id: str) -> None:
    try:
        chapter1_task_service.run_task(task_id)
    except Exception:  # pragma: no cover - run_task already marks failures defensively
        logger.exception("chapter1_background_task_crashed", extra={"task_id": task_id})


def _resolve_replay_path(snapshot: Chapter1TaskSnapshot) -> Path | None:
    replay_root = CHAPTER1_TASK_REPLAY_DIR.resolve()
    candidates: list[Path] = []
    if snapshot.replay_file_path:
        candidates.append(Path(snapshot.replay_file_path))
    if snapshot.semantic_draft and snapshot.semantic_draft.replay_file_path:
        candidates.append(Path(snapshot.semantic_draft.replay_file_path))
    candidates.extend(sorted(replay_root.glob(f"*-{snapshot.task_id}.json"), reverse=True))

    for candidate in candidates:
        try:
            path = candidate.resolve()
            if not path.is_relative_to(replay_root):
                continue
            return path
        except OSError:
            continue
    return None


def _replay_download_url(snapshot: Chapter1TaskSnapshot) -> str:
    replay_path = _resolve_replay_path(snapshot)
    if replay_path is None or not replay_path.is_file():
        return ""
    return f"/other-proof/chapter1/tasks/{snapshot.task_id}/replay"


def _full_task_payload(snapshot: Chapter1TaskSnapshot) -> dict:
    payload = snapshot.model_dump(mode="json")
    payload["replay_download_url"] = _replay_download_url(snapshot)
    return payload


def _task_status_payload(snapshot: Chapter1TaskSnapshot) -> dict:
    return {
        "task_id": snapshot.task_id,
        "status": snapshot.status.value if isinstance(snapshot.status, Chapter1TaskStatus) else str(snapshot.status),
        "progress": snapshot.progress,
        "current_stage": snapshot.current_stage,
        "current_section": snapshot.current_section,
        "company_name": snapshot.company_name,
        "product_name": snapshot.product_name,
        "model_name": snapshot.model_name,
        "model_mode": snapshot.model_mode,
        "generation_mode": snapshot.generation_mode,
        "use_cache": snapshot.use_cache,
        "enable_web_retrieval": snapshot.enable_web_retrieval,
        "allow_incomplete_export": snapshot.allow_incomplete_export,
        "warnings": list(snapshot.warnings or [])[-10:],
        "errors": list(snapshot.errors or [])[-10:],
        "can_export": snapshot.can_export,
        "replay_file_path": snapshot.replay_file_path,
        "replay_download_url": _replay_download_url(snapshot),
        "cancelled": snapshot.cancelled,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
        "diagnostics": dict(snapshot.diagnostics or {}),
    }
