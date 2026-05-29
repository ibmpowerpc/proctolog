from __future__ import annotations

import tempfile
import threading
import time
import unittest
from pathlib import Path

from proc_util.config import Config
from proc_util.control import set_paused
from proc_util.runner import (
    _image_paths_for_request,
    _prompt_with_images_context,
    run_iteration_cancelable,
)


class SlowClient:
    def create_chat_completion(self, **_: object) -> dict[str, object]:
        time.sleep(10)
        return {"id": "late", "choices": [{"message": {"content": "late"}}]}


class RunnerTests(unittest.TestCase):
    def test_uses_previous_then_current_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = Path(directory) / "previous.png"
            current = Path(directory) / "current.png"
            previous.write_bytes(b"previous")
            current.write_bytes(b"current")

            paths = _image_paths_for_request(previous, current)

        self.assertEqual([path.name for path in paths], ["previous.png", "current.png"])

    def test_prompt_describes_two_images_order(self) -> None:
        prompt = _prompt_with_images_context(
            "solve test",
            state={},
            history_turns=0,
            image_paths=[Path("previous.png"), Path("current.png")],
        )

        self.assertIn("1. Предыдущий скриншот", prompt)
        self.assertIn("2. Текущий скриншот", prompt)

    def test_cancelable_iteration_stops_worker_on_pause(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            source = output_dir / "source.png"
            source.write_bytes(b"png")
            config = Config(
                output_dir=str(output_dir),
                screenshot_command=["/bin/cp", str(source), "{output}"],
            )

            def pause_later() -> None:
                time.sleep(0.5)
                set_paused(output_dir, True)

            thread = threading.Thread(target=pause_later)
            thread.start()
            started = time.monotonic()
            result = run_iteration_cancelable(
                config=config,
                output_dir=output_dir,
                state={},
                client=SlowClient(),
                dry_run=False,
            )
            elapsed = time.monotonic() - started
            thread.join(timeout=1)

        self.assertIsNone(result)
        self.assertLess(elapsed, 3)


if __name__ == "__main__":
    unittest.main()
