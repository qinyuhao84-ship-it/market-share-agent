from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import CHAPTER1_MODEL_MODE, CHAPTER1_MODEL_NAME, CHAPTER1_TASK_SNAPSHOT_DIR
from .models import (
    Chapter1SemanticDraft,
    Chapter1TaskCreateRequest,
    Chapter1TaskError,
    Chapter1TaskNotFoundError,
    Chapter1TaskSnapshot,
    Chapter1TaskStatus,
)


class Chapter1TaskStore:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tasks: dict[str, Chapter1TaskSnapshot] = {}
        CHAPTER1_TASK_SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def create(self, request: Chapter1TaskCreateRequest) -> Chapter1TaskSnapshot:
        task_id = uuid.uuid4().hex
        now = _now()
        snapshot = Chapter1TaskSnapshot(
            task_id=task_id,
            status=Chapter1TaskStatus.QUEUED,
            progress=0,
            current_stage="已排队",
            current_section="",
            company_name=str(request.company_name or "").strip(),
            product_name=str(request.product_name or "").strip(),
            model_name=str(request.model_name or CHAPTER1_MODEL_NAME).strip() or CHAPTER1_MODEL_NAME,
            model_mode=CHAPTER1_MODEL_MODE,
            generation_mode=str(request.generation_mode or "strict"),
            use_cache=bool(request.use_cache),
            enable_web_retrieval=False,
            allow_incomplete_export=bool(request.allow_incomplete_export),
            chapter1_context=request.chapter1_context.model_copy(deep=True),
            created_at=now,
            updated_at=now,
        )
        return self.save_snapshot(snapshot)

    def get(self, task_id: str) -> Chapter1TaskSnapshot:
        key = str(task_id or "").strip()
        if not key:
            raise Chapter1TaskNotFoundError("任务不存在")
        with self._lock:
            snapshot = self._tasks.get(key)
            if snapshot is None:
                snapshot = self._load_snapshot_from_disk(key)
                if snapshot is not None:
                    self._tasks[key] = snapshot
            if snapshot is None:
                raise Chapter1TaskNotFoundError(f"任务不存在：{key}")
            return snapshot.model_copy(deep=True)

    def update(self, task_id: str, **patch: Any) -> Chapter1TaskSnapshot:
        key = str(task_id or "").strip()
        if not key:
            raise Chapter1TaskNotFoundError("任务不存在")
        with self._lock:
            current = self._tasks.get(key)
            if current is None:
                current = self._load_snapshot_from_disk(key)
            if current is None:
                raise Chapter1TaskNotFoundError(f"任务不存在：{key}")
            data = current.model_dump(mode="python")
            data.update(patch)
            data["updated_at"] = _now()
            snapshot = Chapter1TaskSnapshot.model_validate(data)
            self._tasks[key] = snapshot.model_copy(deep=True)
            self._save_snapshot_to_disk(snapshot)
            return snapshot.model_copy(deep=True)

    def cancel(self, task_id: str) -> Chapter1TaskSnapshot:
        key = str(task_id or "").strip()
        if not key:
            raise Chapter1TaskNotFoundError("任务不存在")
        with self._lock:
            current = self._tasks.get(key)
            if current is None:
                current = self._load_snapshot_from_disk(key)
            if current is None:
                raise Chapter1TaskNotFoundError(f"任务不存在：{key}")
            updated = current.model_copy(deep=True)
            updated.cancelled = True
            if updated.status not in {Chapter1TaskStatus.COMPLETED, Chapter1TaskStatus.COMPLETED_WITH_MISSING, Chapter1TaskStatus.FAILED, Chapter1TaskStatus.CANCELLED}:
                updated.status = Chapter1TaskStatus.CANCELLED
            updated.current_stage = "已取消"
            updated.updated_at = _now()
            self._tasks[key] = updated.model_copy(deep=True)
            self._save_snapshot_to_disk(updated)
            return updated.model_copy(deep=True)

    def should_cancel(self, task_id: str) -> bool:
        key = str(task_id or "").strip()
        if not key:
            return False
        with self._lock:
            snapshot = self._tasks.get(key)
            if snapshot is None:
                snapshot = self._load_snapshot_from_disk(key)
            return bool(snapshot.cancelled) if snapshot is not None else False

    def save_snapshot(self, snapshot: Chapter1TaskSnapshot) -> Chapter1TaskSnapshot:
        if not snapshot.task_id:
            raise Chapter1TaskError("task_id 不能为空")
        with self._lock:
            data = snapshot.model_dump(mode="python")
            if not data.get("created_at"):
                data["created_at"] = _now()
            if not data.get("updated_at"):
                data["updated_at"] = _now()
            stored = Chapter1TaskSnapshot.model_validate(data)
            self._tasks[stored.task_id] = stored.model_copy(deep=True)
            self._save_snapshot_to_disk(stored)
            return stored.model_copy(deep=True)

    def _snapshot_path(self, task_id: str) -> Path:
        return CHAPTER1_TASK_SNAPSHOT_DIR / f"{task_id}.json"

    def _save_snapshot_to_disk(self, snapshot: Chapter1TaskSnapshot) -> None:
        path = self._snapshot_path(snapshot.task_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False, indent=2)
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            with tmp_path.open("w", encoding="utf-8") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_path, path)
        finally:
            try:
                if tmp_path.exists():
                    tmp_path.unlink()
            except OSError:
                pass

    def _load_snapshot_from_disk(self, task_id: str) -> Chapter1TaskSnapshot | None:
        path = self._snapshot_path(task_id)
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            snapshot = Chapter1TaskSnapshot.model_validate(raw)
        except Exception as exc:  # pragma: no cover - defensive
            raise Chapter1TaskError(f"任务快照损坏：{task_id}") from exc
        return snapshot


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


chapter1_task_store = Chapter1TaskStore()
