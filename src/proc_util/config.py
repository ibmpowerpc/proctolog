from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path("~/.config/proc-util/config.json")


@dataclass
class Config:
    api_base_url: str = "https://routerai.ru/api/v1"
    api_key_env: str = "ROUTERAI_API_KEY"
    model: str = "x-ai/grok-4.3"
    interval_seconds: float = 10.0
    prompt: str = (
        "Реши тестовое задание на текущем скриншоте. Если предыдущий скриншот "
        "связан с текущим, используй его как дополнительный контекст. "
        "В ответе дай краткий итог и конкретный вариант ответа."
    )
    system_prompt: str = (
        "Ты помощник, который решает тестовые задания по скриншотам рабочего стола. "
        "Всегда сначала ориентируйся на текущий скриншот. Предыдущий скриншот "
        "используй только если он связан с текущим заданием или содержит "
        "недостающий контекст. Отвечай кратко, по делу и на русском языке."
    )
    detail: str = "low"
    conversation_id: str | None = None
    history_turns: int = 3
    output_dir: str = "~/.local/share/proc-util"
    keep_screenshots: int | None = 120
    screenshot_command: list[str] | None = None
    request_timeout_seconds: float = 120.0

    def validate(self) -> None:
        if self.interval_seconds <= 0:
            raise ValueError("interval_seconds must be greater than zero")
        if self.detail not in {"auto", "low", "high"}:
            raise ValueError("detail must be one of: auto, low, high")
        if self.keep_screenshots is not None and self.keep_screenshots < 1:
            raise ValueError("keep_screenshots must be null or greater than zero")
        if self.screenshot_command is not None and not self.screenshot_command:
            raise ValueError("screenshot_command must be null or a non-empty list")
        if self.history_turns < 0:
            raise ValueError("history_turns must be zero or greater")
        if self.model == "deepseek/deepseek-v4-pro":
            raise ValueError(
                "deepseek/deepseek-v4-pro is text-only on RouterAI and cannot "
                "analyze screenshots; use a vision model like x-ai/grok-4.3"
            )


def expand_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve()


def default_config_path() -> Path:
    return expand_path(DEFAULT_CONFIG_PATH)


def load_config(path: str | Path | None = None) -> Config:
    config_path = expand_path(path) if path else default_config_path()
    if not config_path.exists():
        config = Config()
        config.validate()
        return config

    with config_path.open("r", encoding="utf-8") as stream:
        raw = json.load(stream)

    config = Config(**_filter_known_keys(raw))
    config.validate()
    return config


def write_default_config(path: str | Path | None = None, force: bool = False) -> Path:
    config_path = expand_path(path) if path else default_config_path()
    if config_path.exists() and not force:
        raise FileExistsError(f"config already exists: {config_path}")

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with config_path.open("w", encoding="utf-8") as stream:
        json.dump(asdict(Config()), stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return config_path


def save_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    tmp_path.replace(path)


def _filter_known_keys(raw: dict[str, Any]) -> dict[str, Any]:
    known = set(Config.__dataclass_fields__)
    return {key: value for key, value in raw.items() if key in known}
