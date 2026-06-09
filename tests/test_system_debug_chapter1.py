from __future__ import annotations

import httpx

from fastapi.testclient import TestClient

from report_automation.main import create_app
import report_automation.api.system as system_module


class _FakeProbeOrchestrator:
    def __init__(self, api_key_source: str = "TEST_DEEPSEEK_KEY") -> None:
        self.api_key_source = api_key_source


class _FakeProbeClientSuccess:
    def __init__(self, config) -> None:  # noqa: ANN001
        self.orchestrator = _FakeProbeOrchestrator()

    def complete_json(self, **kwargs):  # noqa: ANN003
        return '{"ok": true, "module": "chapter1", "model": "deepseek-v4-pro"}'


class _FakeProbeClientFailure:
    def __init__(self, config) -> None:  # noqa: ANN001
        self.orchestrator = _FakeProbeOrchestrator()

    def complete_json(self, **kwargs):  # noqa: ANN003
        request = httpx.Request("POST", "https://api.deepseek.com/chat/completions")
        response = httpx.Response(401, request=request, json={"error": "unauthorized"})
        raise httpx.HTTPStatusError("unauthorized", request=request, response=response)


def test_chapter1_probe_success(monkeypatch):
    monkeypatch.setenv("TEST_DEEPSEEK_KEY", "sk-test")
    monkeypatch.setattr(system_module, "DeepSeekV4ProChapter1Client", _FakeProbeClientSuccess)

    client = TestClient(create_app())
    resp = client.get("/system/debug/chapter1-llm-probe")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["model"] == "deepseek-v4-pro"
    assert body["model_mode"] == "thinking"
    assert body["direct_generation_only"] is True
    assert body["api_key_source"] == "TEST_DEEPSEEK_KEY"
    assert body["api_key_present"] is True
    assert body["parsed"]["ok"] is True
    assert body["parsed"]["module"] == "chapter1"


def test_chapter1_probe_failure_returns_status_code(monkeypatch):
    monkeypatch.setattr(system_module, "DeepSeekV4ProChapter1Client", _FakeProbeClientFailure)

    client = TestClient(create_app())
    resp = client.get("/system/debug/chapter1-llm-probe")

    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["model"] == "deepseek-v4-pro"
    assert body["model_mode"] == "thinking"
    assert body["direct_generation_only"] is True
    assert body["status_code"] == 401
    assert body["error_type"] == "HTTPStatusError"
    assert body["root_error_type"] == "HTTPStatusError"
