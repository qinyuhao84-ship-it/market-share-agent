from __future__ import annotations

from typing import Any, Mapping, Sequence

from inference import InferenceConfig, LLMOrchestrator

from .config import (
    CHAPTER1_MODEL_MODE,
    CHAPTER1_MODEL_NAME,
    CHAPTER1_REASONING_EFFORT,
    CHAPTER1_RESPONSE_FORMAT,
    CHAPTER1_THINKING_CONFIG,
)


class Chapter1LLMError(RuntimeError):
    pass


class Chapter1LLMUnavailableError(Chapter1LLMError):
    pass


class DeepSeekV4FlashChapter1Client:
    def __init__(self, config: InferenceConfig | None = None) -> None:
        self.config = config or InferenceConfig()
        self.model_name = CHAPTER1_MODEL_NAME
        self.model_mode = CHAPTER1_MODEL_MODE
        self.last_raw_output: str = ""
        self.last_messages: list[dict[str, str]] = []
        self.last_request: dict[str, Any] = {}
        self._init_error: Exception | None = None
        try:
            self.orchestrator = LLMOrchestrator.from_config(self.config)
        except Exception as exc:  # pragma: no cover - defensive
            self.orchestrator = None
            self._init_error = exc

    def is_available(self) -> bool:
        return bool(
            self.orchestrator is not None
            and getattr(self.orchestrator, "client", None) is not None
            and self.orchestrator.is_available()
        )

    def complete_json(
        self,
        *,
        messages: Sequence[dict[str, str]],
        section_key: str,
        max_output_tokens: int,
        timeout_seconds: int,
        retry_max_attempts: int = 1,
    ) -> str:
        if not self.is_available():
            reason = f"第一章模型 {CHAPTER1_MODEL_NAME} 不可用"
            if self._init_error is not None:
                reason = f"{reason}：{self._init_error}"
            raise Chapter1LLMUnavailableError(reason)

        self.last_messages = [dict(item) for item in messages]
        self.last_request = {
            "model": CHAPTER1_MODEL_NAME,
            "model_mode": CHAPTER1_MODEL_MODE,
            "section_key": section_key,
            "max_output_tokens": int(max_output_tokens),
            "timeout_seconds": int(timeout_seconds),
            "retry_max_attempts": int(retry_max_attempts),
            "response_format": dict(CHAPTER1_RESPONSE_FORMAT),
            "reasoning_effort": CHAPTER1_REASONING_EFFORT,
            "thinking": dict(CHAPTER1_THINKING_CONFIG.get("thinking", {})),
        }
        try:
            raw = self.orchestrator.client.complete(  # type: ignore[union-attr]
                self.last_messages,
                model=CHAPTER1_MODEL_NAME,
                temperature=None,
                max_output_tokens=max_output_tokens,
                timeout_seconds=timeout_seconds,
                retry_max_attempts=retry_max_attempts,
                section_key=section_key,
                response_format=CHAPTER1_RESPONSE_FORMAT,
                reasoning_effort=CHAPTER1_REASONING_EFFORT,
                extra_body=CHAPTER1_THINKING_CONFIG,
            )
        except Exception as exc:
            raise Chapter1LLMError(f"第一章模型调用失败：{exc}") from exc

        text = str(raw or "").strip()
        if not text:
            raise Chapter1LLMError("LLM_EMPTY_CONTENT")
        self.last_raw_output = text
        return text


DeepSeekV4ProChapter1Client = DeepSeekV4FlashChapter1Client
