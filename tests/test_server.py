from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from proc_util.control import is_paused, toggle_paused
from proc_util.server import _latest_event, _read_events, _render_index


class ServerTests(unittest.TestCase):
    def test_read_events_skips_invalid_lines(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            events_path = output_dir / "events.jsonl"
            events_path.write_text(
                json.dumps({"timestamp": "1", "output_text": "hello"}) + "\n"
                + "not-json\n"
                + json.dumps({"timestamp": "2", "output_text": "world"}) + "\n",
                encoding="utf-8",
            )

            events = _read_events(output_dir, limit=10)

        self.assertEqual([event["timestamp"] for event in events], ["1", "2"])

    def test_latest_event_returns_only_last_valid_event(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            events_path = output_dir / "events.jsonl"
            events_path.write_text(
                json.dumps({"timestamp": "1", "output_text": "old"}) + "\n"
                + json.dumps({"timestamp": "2", "output_text": "new"}) + "\n",
                encoding="utf-8",
            )

            latest = _latest_event(output_dir)

        self.assertIsNotNone(latest)
        self.assertEqual(latest["output_text"], "new")

    def test_render_index_shows_latest_answer_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            events_path = output_dir / "events.jsonl"
            events_path.write_text(
                json.dumps({"timestamp": "1", "output_text": "old answer"}) + "\n"
                + json.dumps({"timestamp": "2", "output_text": "new answer"}) + "\n",
                encoding="utf-8",
            )

            html = _render_index(output_dir)

        self.assertIn("new answer", html)
        self.assertNotIn("old answer", html)

    def test_pause_toggle_is_rendered(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory)
            self.assertFalse(is_paused(output_dir))
            self.assertTrue(toggle_paused(output_dir))

            html = _render_index(output_dir)

        self.assertIn("Продолжить", html)


if __name__ == "__main__":
    unittest.main()
