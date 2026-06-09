from __future__ import annotations

from typing import Any

from inference.models import InferenceConfig

import report_automation.other_proof.chapter1.deepseek_client as deepseek_client_module
from report_automation.other_proof.chapter1.deepseek_client import DeepSeekV4ProChapter1Client


class _FakeCompleteClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def complete(self, messages, **kwargs):  # noqa: ANN001
        self.calls.append(
            {
                "messages": list(messages),
                "kwargs": dict(kwargs),
            }
        )
        return '{"ok": true}'


class _FakeOrchestrator:
    def __init__(self, client: _FakeCompleteClient) -> None:
        self.client = client
        self.api_key_source = "DEEPSEEK_API_KEY"

    def is_available(self) -> bool:
        return True


def test_deepseek_client_uses_thinking_payload(monkeypatch):
    fake_client = _FakeCompleteClient()
    fake_orchestrator = _FakeOrchestrator(fake_client)
    monkeypatch.setattr(
        deepseek_client_module.LLMOrchestrator,
        "from_config",
        classmethod(lambda cls, config: fake_orchestrator),
    )

    client = DeepSeekV4ProChapter1Client(InferenceConfig())
    raw = client.complete_json(
        messages=[{"role": "user", "content": "json"}],
        section_key="background_overview",
        max_output_tokens=256,
        timeout_seconds=30,
        retry_max_attempts=0,
    )

    assert raw == '{"ok": true}'
    assert client.model_name == "deepseek-v4-pro"
    assert client.model_mode == "thinking"
    assert client.last_request["model"] == "deepseek-v4-pro"
    assert client.last_request["model_mode"] == "thinking"
    assert client.last_request["response_format"] == {"type": "json_object"}
    assert client.last_request["reasoning_effort"] == "high"
    assert client.last_request["thinking"] == {"type": "enabled"}
    assert fake_client.calls[0]["kwargs"]["temperature"] is None
    assert fake_client.calls[0]["kwargs"]["reasoning_effort"] == "high"
    assert fake_client.calls[0]["kwargs"]["extra_body"] == {"thinking": {"type": "enabled"}}
    assert fake_client.calls[0]["kwargs"]["response_format"] == {"type": "json_object"}
