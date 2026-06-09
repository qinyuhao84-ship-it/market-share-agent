from __future__ import annotations

from fastapi.testclient import TestClient
import pytest

from report_automation.main import create_app
from report_automation.other_proof.chapter1 import (
    CHAPTER1_MODEL_MODE,
    CHAPTER1_MODEL_NAME,
    Chapter1ContentBlock,
    Chapter1SemanticDraft,
    Chapter1SemanticSection,
    Chapter1SectionStatus,
    Chapter1TaskCreateRequest,
    Chapter1TaskSnapshot,
    Chapter1TaskStatus,
    chapter1_task_service,
    chapter1_task_store,
)
import report_automation.other_proof.chapter1.task_service as task_service_module
import report_automation.other_proof.chapter1.task_store as task_store_module
import report_automation.other_proof.chapter1.replay_writer as replay_writer_module


@pytest.fixture(autouse=True)
def isolate_chapter1_state(tmp_path, monkeypatch):
    monkeypatch.setattr(task_store_module, "CHAPTER1_TASK_SNAPSHOT_DIR", tmp_path / "chapter1_tasks")
    monkeypatch.setattr(replay_writer_module, "CHAPTER1_TASK_REPLAY_DIR", tmp_path / "chapter1_replays")
    chapter1_task_store._tasks = {}
    task_service_module.chapter1_task_service._result_cache = {}
    yield


def test_create_task_api_returns_task_id_and_get_returns_legacy_sections(monkeypatch):
    client = TestClient(create_app())

    def fake_start_task(payload: Chapter1TaskCreateRequest):
        snapshot = Chapter1TaskSnapshot(
            task_id="task-001",
            status=Chapter1TaskStatus.QUEUED,
            progress=0,
            current_stage="已排队",
            current_section="",
            company_name=payload.company_name,
            product_name=payload.product_name,
            model_name=CHAPTER1_MODEL_NAME,
            model_mode=CHAPTER1_MODEL_MODE,
            generation_mode=payload.generation_mode,
            use_cache=payload.use_cache,
            enable_web_retrieval=False,
            allow_incomplete_export=payload.allow_incomplete_export,
            created_at="2026-06-09T00:00:00",
            updated_at="2026-06-09T00:00:00",
            diagnostics={
                "model_name": CHAPTER1_MODEL_NAME,
                "model_mode": CHAPTER1_MODEL_MODE,
                "direct_generation_only": True,
                "local_retrieval": "disabled",
                "web_retrieval_disabled": True,
            },
        )
        chapter1_task_store.save_snapshot(snapshot)
        return snapshot

    def fake_run_task(task_id: str):
        snapshot = chapter1_task_store.get(task_id)
        draft = Chapter1SemanticDraft(
            draft_id=f"{task_id}-draft",
            task_id=task_id,
            company_name=snapshot.company_name,
            product_name=snapshot.product_name,
            sections=[
                Chapter1SemanticSection(
                    section_id="background_overview",
                    section_title="背景与概述",
                    content_blocks=[
                        Chapter1ContentBlock(
                            block_id="background_overview_001",
                            block_type="intro",
                            heading="概述",
                            body="这是一段足够长的正文内容，用于模拟任务完成后的语义草稿。",
                            source_refs=["source_001"],
                        )
                    ],
                    sources=[],
                    status=Chapter1SectionStatus.COMPLETED,
                )
            ],
        )
        snapshot.semantic_draft = draft
        snapshot.legacy_sections = [
            {"key": "background_overview", "title": "背景与概述", "paragraphs": ["概述：这是一段足够长的正文内容，用于模拟任务完成后的语义草稿。"]},
        ]
        snapshot.status = Chapter1TaskStatus.COMPLETED_WITH_MISSING
        snapshot.progress = 100
        snapshot.current_stage = "整理输出"
        snapshot.current_section = ""
        snapshot.can_export = True
        snapshot.warnings = ["资料来源不足"]
        snapshot.replay_file_path = str((replay_writer_module.CHAPTER1_TASK_REPLAY_DIR / "task-001.json").resolve())
        snapshot.semantic_draft.replay_file_path = snapshot.replay_file_path
        snapshot.diagnostics = {
            "model_name": CHAPTER1_MODEL_NAME,
            "model_mode": CHAPTER1_MODEL_MODE,
            "direct_generation_only": True,
            "local_retrieval": "disabled",
            "web_retrieval_disabled": True,
        }
        chapter1_task_store.save_snapshot(snapshot)

    monkeypatch.setattr(task_service_module.chapter1_task_service, "start_task", fake_start_task)
    monkeypatch.setattr(task_service_module.chapter1_task_service, "run_task", fake_run_task)

    resp = client.post(
        "/other-proof/chapter1/tasks",
        json={
            "company_name": "浙江达航数据技术有限公司",
            "product_name": "示例产品",
            "use_cache": True,
            "enable_web_retrieval": True,
            "allow_incomplete_export": True,
            "generation_mode": "balanced",
            "model_name": "deepseek-v4-pro",
        },
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["task_id"] == "task-001"
    assert body["model_name"] == CHAPTER1_MODEL_NAME
    assert body["enable_web_retrieval"] is False
    assert body["diagnostics"]["direct_generation_only"] is True

    task_resp = client.get("/other-proof/chapter1/tasks/task-001")
    assert task_resp.status_code == 200
    snapshot = task_resp.json()
    assert snapshot["status"] == "completed_with_missing"
    assert snapshot["can_export"] is True
    assert snapshot["legacy_sections"][0]["key"] == "background_overview"
    assert snapshot["legacy_sections"][0]["paragraphs"][0].startswith("概述：")
    assert snapshot["diagnostics"]["local_retrieval"] == "disabled"


def test_cancel_task_api_sets_cancelled_status():
    client = TestClient(create_app())
    snapshot = Chapter1TaskSnapshot(
        task_id="task-cancel",
        status=Chapter1TaskStatus.QUEUED,
        progress=0,
        current_stage="已排队",
        current_section="",
        company_name="浙江达航数据技术有限公司",
        product_name="示例产品",
        model_name=CHAPTER1_MODEL_NAME,
        model_mode=CHAPTER1_MODEL_MODE,
        created_at="2026-06-09T00:00:00",
        updated_at="2026-06-09T00:00:00",
    )
    chapter1_task_store.save_snapshot(snapshot)

    resp = client.post("/other-proof/chapter1/tasks/task-cancel/cancel")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "cancelled"
    assert body["cancelled"] is True
