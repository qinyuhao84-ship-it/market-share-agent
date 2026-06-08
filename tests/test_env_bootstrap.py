from __future__ import annotations

import os
from pathlib import Path

import report_automation.env as env_loader


def test_load_local_environment_files_reads_env_file(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_BASE", raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                'export OPENAI_API_KEY="sk-from-env-file"',
                "OPENAI_API_BASE=https://proxy.example.com/v1",
                "# comment line",
            ]
        ),
        encoding="utf-8",
    )

    env_loader.load_local_environment_files([env_file])

    assert os.getenv("OPENAI_API_KEY") == "sk-from-env-file"
    assert os.getenv("OPENAI_API_BASE") == "https://proxy.example.com/v1"


def test_load_local_environment_files_does_not_override_existing_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-existing")
    monkeypatch.setenv("OPENAI_API_BASE", "https://existing.example.com/v1")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-from-env-file",
                "OPENAI_API_BASE=https://proxy.example.com/v1",
            ]
        ),
        encoding="utf-8",
    )

    env_loader.load_local_environment_files([env_file])

    assert os.getenv("OPENAI_API_KEY") == "sk-existing"
    assert os.getenv("OPENAI_API_BASE") == "https://existing.example.com/v1"


def test_load_local_environment_files_fills_blank_values(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_BASE", "")

    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=sk-from-env-file",
                "OPENAI_API_BASE=https://proxy.example.com/v1",
            ]
        ),
        encoding="utf-8",
    )

    env_loader.load_local_environment_files([env_file])

    assert os.getenv("OPENAI_API_KEY") == "sk-from-env-file"
    assert os.getenv("OPENAI_API_BASE") == "https://proxy.example.com/v1"


def test_bootstrap_local_environment_prefers_env_local_over_env(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_BASE", raising=False)

    env_local = tmp_path / ".env.local"
    env_local.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=sk-local",
                "DEEPSEEK_API_BASE=https://api.deepseek.com/v1",
            ]
        ),
        encoding="utf-8",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "DEEPSEEK_API_KEY=sk-env",
                "DEEPSEEK_API_BASE=https://proxy.example.com/v1",
            ]
        ),
        encoding="utf-8",
    )

    env_loader.bootstrap_local_environment(tmp_path)

    assert os.getenv("DEEPSEEK_API_KEY") == "sk-local"
    assert os.getenv("DEEPSEEK_API_BASE") == "https://api.deepseek.com/v1"
