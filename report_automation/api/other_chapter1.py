from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, HTTPException

from report_automation.other_proof.chapter1 import (
    Chapter1TaskCreateRequest,
    Chapter1TaskNotFoundError,
    chapter1_task_service,
    chapter1_task_store,
)

router = APIRouter(prefix="/other-proof/chapter1")


@router.post("/tasks")
def create_chapter1_task(payload: Chapter1TaskCreateRequest, background_tasks: BackgroundTasks):
    snapshot = chapter1_task_service.start_task(payload)
    background_tasks.add_task(chapter1_task_service.run_task, snapshot.task_id)
    return snapshot


@router.get("/tasks/{task_id}")
def get_chapter1_task(task_id: str):
    try:
        return chapter1_task_store.get(task_id)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/cancel")
def cancel_chapter1_task(task_id: str):
    try:
        return chapter1_task_service.cancel_task(task_id)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/sections/{section_key}/retry")
def retry_chapter1_section(task_id: str, section_key: str):
    try:
        return chapter1_task_service.retry_section(task_id, section_key)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/tasks/{task_id}/sections/{section_key}/repair")
def repair_chapter1_section(task_id: str, section_key: str):
    try:
        return chapter1_task_service.repair_section(task_id, section_key)
    except Chapter1TaskNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

