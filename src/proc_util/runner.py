from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import base64
import json
import multiprocessing
import os
from pathlib import Path
import queue
import sys
import time
from typing import Any

from .config import Config, expand_path, save_json
from .control import is_paused
from .openai_client import OpenAICompatibleClient, extract_output_text
from .screenshot import capture_screenshot


CONTROL_POLL_SECONDS = 0.2


@dataclass
class RunOptions:
    once: bool = False
    dry_run: bool = False
    max_iterations: int | None = None


@dataclass
class IterationResult:
    timestamp: str
    screenshot_path: Path
    response_id: str | None
    output_text: str
    previous_screenshot_path: Path | None = None


def run_monitor(config: Config, options: RunOptions) -> None:
    output_dir = expand_path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    state_path = output_dir / "state.json"
    state = _load_state(state_path)

    client = None
    if not options.dry_run:
        api_key = os.environ.get(config.api_key_env)
        if not api_key:
            raise RuntimeError(f"environment variable {config.api_key_env} is not set")
        client = OpenAICompatibleClient(
            api_key=api_key,
            base_url=config.api_base_url,
            timeout_seconds=config.request_timeout_seconds,
        )

    iteration = 0
    while True:
        if is_paused(output_dir):
            if options.once:
                return
            _wait_until_unpaused(output_dir)
            continue

        iteration += 1
        try:
            result = run_iteration_cancelable(
                config=config,
                output_dir=output_dir,
                state=state,
                client=client,
                dry_run=options.dry_run,
            )
            if result is None:
                if options.once:
                    return
                _wait_until_unpaused(output_dir)
                continue
            if result.response_id:
                state["last_response_id"] = result.response_id
            state["last_screenshot_path"] = str(result.screenshot_path)
            _append_history(state, config, result)
            save_json(state_path, state)
            _append_logs(output_dir, config.prompt, result)
            _cleanup_screenshots(output_dir, config.keep_screenshots)
            print(
                f"[{result.timestamp}] response_id={result.response_id or 'dry-run'}",
                file=sys.stderr,
            )
        except Exception as error:
            if options.once:
                raise
            print(f"proc-util iteration failed: {error}", file=sys.stderr)

        if options.once:
            return
        if options.max_iterations is not None and iteration >= options.max_iterations:
            return
        _sleep_until_next_iteration(output_dir, config.interval_seconds)


def run_iteration_cancelable(
    *,
    config: Config,
    output_dir: Path,
    state: dict[str, Any],
    client: OpenAICompatibleClient | None,
    dry_run: bool,
) -> IterationResult | None:
    context = multiprocessing.get_context("spawn")
    result_queue: multiprocessing.Queue[dict[str, Any]] = context.Queue(maxsize=1)
    process = context.Process(
        target=_iteration_worker,
        args=(config, output_dir, dict(state), client, dry_run, result_queue),
    )
    process.start()

    while process.is_alive():
        if is_paused(output_dir):
            _terminate_process(process)
            print("proc-util iteration cancelled by pause", file=sys.stderr)
            return None
        process.join(timeout=CONTROL_POLL_SECONDS)

    process.join()
    try:
        payload = result_queue.get_nowait()
    except queue.Empty as error:
        raise RuntimeError("iteration worker exited without a result") from error

    if payload.get("ok") is True:
        result = payload.get("result")
        if isinstance(result, IterationResult):
            return result
        raise RuntimeError("iteration worker returned an invalid result")

    error_message = payload.get("error")
    raise RuntimeError(str(error_message or "iteration worker failed"))


def _iteration_worker(
    config: Config,
    output_dir: Path,
    state: dict[str, Any],
    client: OpenAICompatibleClient | None,
    dry_run: bool,
    result_queue: multiprocessing.Queue[dict[str, Any]],
) -> None:
    try:
        result_queue.put(
            {
                "ok": True,
                "result": run_iteration(
                    config=config,
                    output_dir=output_dir,
                    state=state,
                    client=client,
                    dry_run=dry_run,
                ),
            }
        )
    except Exception as error:
        result_queue.put({"ok": False, "error": str(error)})


def _terminate_process(process: multiprocessing.Process) -> None:
    if not process.is_alive():
        process.join()
        return
    process.terminate()
    process.join(timeout=2)
    if process.is_alive():
        process.kill()
        process.join(timeout=2)


def _wait_until_unpaused(output_dir: Path) -> None:
    while is_paused(output_dir):
        time.sleep(CONTROL_POLL_SECONDS)


def _sleep_until_next_iteration(output_dir: Path, seconds: float) -> None:
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if is_paused(output_dir):
            _wait_until_unpaused(output_dir)
            return
        time.sleep(min(CONTROL_POLL_SECONDS, max(0.0, deadline - time.monotonic())))


def run_iteration(
    *,
    config: Config,
    output_dir: Path,
    state: dict[str, Any],
    client: OpenAICompatibleClient | None,
    dry_run: bool,
) -> IterationResult:
    timestamp = _timestamp()
    screenshot_path = output_dir / "screenshots" / f"{timestamp}.png"
    capture_screenshot(screenshot_path, config.screenshot_command)
    previous_screenshot_path = _previous_screenshot_path(state)

    if dry_run:
        return IterationResult(
            timestamp=timestamp,
            screenshot_path=screenshot_path,
            response_id=None,
            output_text=f"[dry-run] Captured screenshot: {screenshot_path}",
            previous_screenshot_path=previous_screenshot_path,
        )

    if client is None:
        raise RuntimeError("AI client is not configured")

    image_paths = _image_paths_for_request(previous_screenshot_path, screenshot_path)
    response = client.create_chat_completion(
        model=config.model,
        system_prompt=config.system_prompt,
        prompt=_prompt_with_images_context(config.prompt, state, config.history_turns, image_paths),
        image_data_urls=[_image_data_url(path) for path in image_paths],
        detail=config.detail,
    )
    response_id = response.get("id")
    output_text = extract_output_text(response)

    return IterationResult(
        timestamp=timestamp,
        screenshot_path=screenshot_path,
        response_id=response_id if isinstance(response_id, str) else None,
        output_text=output_text,
        previous_screenshot_path=previous_screenshot_path,
    )


def _load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise RuntimeError(f"state file must contain a JSON object: {path}")
    return data


def _prompt_with_history(prompt: str, state: dict[str, Any], history_turns: int) -> str:
    history = state.get("history")
    if history_turns == 0 or not isinstance(history, list):
        return prompt

    recent = [item for item in history if isinstance(item, dict)][-history_turns:]
    if not recent:
        return prompt

    lines = [prompt, "", "Контекст последних ответов:"]
    for item in recent:
        timestamp = item.get("timestamp", "unknown-time")
        output_text = item.get("output_text", "")
        if isinstance(output_text, str) and output_text.strip():
            lines.append(f"- {timestamp}: {output_text.strip()}")
    return "\n".join(lines)


def _prompt_with_images_context(
    prompt: str,
    state: dict[str, Any],
    history_turns: int,
    image_paths: list[Path],
) -> str:
    lines = [prompt, "", "Изображения в этом запросе:"]
    if len(image_paths) == 1:
        lines.append("1. Текущий скриншот.")
    else:
        lines.append("1. Предыдущий скриншот.")
        lines.append("2. Текущий скриншот.")
    lines.append("")
    lines.append(
        "Если скриншоты показывают разные несвязанные задания, отвечай только по текущему скриншоту."
    )
    return _prompt_with_history("\n".join(lines), state, history_turns)


def _previous_screenshot_path(state: dict[str, Any]) -> Path | None:
    raw_path = state.get("last_screenshot_path")
    if not isinstance(raw_path, str):
        return None
    path = Path(raw_path).expanduser()
    if not path.exists() or not path.is_file():
        return None
    return path


def _image_paths_for_request(previous_screenshot_path: Path | None, screenshot_path: Path) -> list[Path]:
    if previous_screenshot_path is None or previous_screenshot_path == screenshot_path:
        return [screenshot_path]
    return [previous_screenshot_path, screenshot_path]


def _append_history(state: dict[str, Any], config: Config, result: IterationResult) -> None:
    if config.history_turns == 0:
        state.pop("history", None)
        return

    history = state.get("history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "timestamp": result.timestamp,
            "response_id": result.response_id,
            "output_text": result.output_text,
        }
    )
    state["history"] = history[-config.history_turns :]


def _append_logs(output_dir: Path, prompt: str, result: IterationResult) -> None:
    event = {
        "timestamp": result.timestamp,
        "screenshot_path": str(result.screenshot_path),
        "previous_screenshot_path": str(result.previous_screenshot_path)
        if result.previous_screenshot_path
        else None,
        "response_id": result.response_id,
        "output_text": result.output_text,
    }
    with (output_dir / "events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")

    with (output_dir / "transcript.md").open("a", encoding="utf-8") as stream:
        stream.write(f"\n## {result.timestamp}\n\n")
        stream.write(f"Screenshot: `{result.screenshot_path}`\n\n")
        if result.previous_screenshot_path:
            stream.write(f"Previous screenshot: `{result.previous_screenshot_path}`\n\n")
        if result.response_id:
            stream.write(f"Response ID: `{result.response_id}`\n\n")
        stream.write("Prompt:\n\n")
        stream.write(f"> {prompt.replace(chr(10), chr(10) + '> ')}\n\n")
        stream.write("Response:\n\n")
        stream.write(result.output_text or "_No text output returned._")
        stream.write("\n")


def _cleanup_screenshots(output_dir: Path, keep_screenshots: int | None) -> None:
    if keep_screenshots is None:
        return
    screenshot_dir = output_dir / "screenshots"
    if not screenshot_dir.exists():
        return
    screenshots = sorted(
        screenshot_dir.glob("*.png"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for old_path in screenshots[keep_screenshots:]:
        old_path.unlink(missing_ok=True)


def _image_data_url(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
