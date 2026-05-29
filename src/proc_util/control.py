from __future__ import annotations

import json
from pathlib import Path

from .config import save_json


def control_path(output_dir: Path) -> Path:
    return output_dir / "control.json"


def is_paused(output_dir: Path) -> bool:
    return _read_control(output_dir).get("paused") is True


def set_paused(output_dir: Path, paused: bool) -> None:
    save_json(control_path(output_dir), {"paused": paused})


def toggle_paused(output_dir: Path) -> bool:
    paused = not is_paused(output_dir)
    set_paused(output_dir, paused)
    return paused


def _read_control(output_dir: Path) -> dict[str, object]:
    path = control_path(output_dir)
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as stream:
            data = json.load(stream)
    except (OSError, json.JSONDecodeError):
        return {}

    return data if isinstance(data, dict) else {}
