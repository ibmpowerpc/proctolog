from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from proc_util.config import Config, load_config, write_default_config


class ConfigTests(unittest.TestCase):
    def test_default_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            write_default_config(path)
            config = load_config(path)

        self.assertIsInstance(config, Config)
        self.assertEqual(config.interval_seconds, 10.0)
        self.assertEqual(config.detail, "low")
        self.assertEqual(config.api_key_env, "ROUTERAI_API_KEY")
        self.assertEqual(config.model, "x-ai/grok-4.3")
        self.assertEqual(config.output_dir, "~/.local/share/proctolog")
        self.assertIn("рамки объёма", config.prompt)
        self.assertIn("лимит слов", config.system_prompt)

    def test_rejects_text_only_deepseek_for_screenshot_workflow(self) -> None:
        config = Config(model="deepseek/deepseek-v4-pro")

        with self.assertRaises(ValueError):
            config.validate()

    def test_rejects_invalid_detail(self) -> None:
        config = Config(detail="full")

        with self.assertRaises(ValueError):
            config.validate()


if __name__ == "__main__":
    unittest.main()
