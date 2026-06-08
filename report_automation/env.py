from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _parse_env_line(line: str) -> tuple[str, str] | None:
    text = line.strip()
    if not text or text.startswith("#"):
        return None
    if text.startswith("export "):
        text = text[len("export ") :].lstrip()
    if "=" not in text:
        return None
    key, raw_value = text.split("=", 1)
    key = key.strip()
    if not key:
        return None
    value = raw_value.strip()
    if len(value) >= 2 and value[:1] == value[-1:] and value[:1] in {'"', "'"}:
        value = value[1:-1]
    return key, value


def _load_env_file(path: Path) -> bool:
    if not path.is_file():
        return False
    changed = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        current = os.environ.get(key, "")
        if current.strip():
            continue
        os.environ[key] = value
        changed = True
    return changed


def load_local_environment_files(paths: Iterable[Path]) -> None:
    for path in paths:
        _load_env_file(path)
