from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

from .config import CHAPTER1_TASK_REPLAY_DIR
from .models import Chapter1TaskSnapshot


class Chapter1ReplayWriter:
    def write(self, snapshot: Chapter1TaskSnapshot) -> str:
        CHAPTER1_TASK_REPLAY_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        safe_product = _safe_name(snapshot.product_name)
        path = CHAPTER1_TASK_REPLAY_DIR / f"{timestamp}-{safe_product}-{snapshot.task_id}.json"
        payload = {
            "task_id": snapshot.task_id,
            "model_name": snapshot.model_name,
            "model_mode": snapshot.model_mode,
            "request": {
                "company_name": snapshot.company_name,
                "product_name": snapshot.product_name,
                "generation_mode": snapshot.generation_mode,
                "use_cache": snapshot.use_cache,
                "enable_web_retrieval": snapshot.enable_web_retrieval,
                "allow_incomplete_export": snapshot.allow_incomplete_export,
                "progress": snapshot.progress,
                "current_stage": snapshot.current_stage,
                "current_section": snapshot.current_section,
                "status": snapshot.status.value,
            },
            "semantic_draft": snapshot.semantic_draft.model_dump(mode="json") if snapshot.semantic_draft else None,
            "retrieval_records": list(snapshot.retrieval_records or []),
            "generation_records": list(snapshot.generation_records or []),
            "raw_model_outputs": list(snapshot.raw_model_outputs or []),
            "parsed_outputs": list(snapshot.parsed_outputs or []),
            "validation_results": list(snapshot.validation_results or []),
            "repair_records": list(snapshot.repair_records or []),
            "legacy_sections": list(snapshot.legacy_sections or []),
            "warnings": list(snapshot.warnings or []),
            "errors": list(snapshot.errors or []),
            "final_status": snapshot.status.value,
            "replay_file_path": str(path.resolve()),
            "can_export": snapshot.can_export,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path.resolve())


def _safe_name(value: str) -> str:
    text = str(value or "").strip()
    safe = re.sub(r"[^\w\u4e00-\u9fff]+", "-", text).strip("-")
    return safe or "product"
