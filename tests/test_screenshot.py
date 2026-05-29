from __future__ import annotations

import os
from pathlib import Path
import unittest
from unittest.mock import patch

from proc_util.screenshot import command_for_output, linux_command_for_output, ScreenshotError


class ScreenshotTests(unittest.TestCase):
    def test_custom_command_replaces_output_placeholder(self) -> None:
        command = command_for_output(
            Path("/tmp/out.png"),
            ["tool", "--file", "{output}"],
        )

        self.assertEqual(command, ["tool", "--file", "/tmp/out.png"])

    def test_custom_command_appends_output_without_placeholder(self) -> None:
        command = command_for_output(Path("/tmp/out.png"), ["tool", "--file"])

        self.assertEqual(command, ["tool", "--file", "/tmp/out.png"])

    def test_linux_wayland_prefers_grim(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "wayland"}), patch(
            "proc_util.screenshot.shutil.which",
            side_effect=lambda name: f"/usr/bin/{name}" if name == "grim" else None,
        ):
            command = linux_command_for_output(Path("/tmp/out.png"))

        self.assertEqual(command, ["/usr/bin/grim", "/tmp/out.png"])

    def test_linux_x11_uses_scrot(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}), patch(
            "proc_util.screenshot.shutil.which",
            side_effect=lambda name: f"/usr/bin/{name}" if name == "scrot" else None,
        ):
            command = linux_command_for_output(Path("/tmp/out.png"))

        self.assertEqual(command, ["/usr/bin/scrot", "/tmp/out.png"])

    def test_linux_errors_without_tools(self) -> None:
        with patch.dict(os.environ, {"XDG_SESSION_TYPE": "x11"}), patch(
            "proc_util.screenshot.shutil.which",
            return_value=None,
        ):
            with self.assertRaises(ScreenshotError):
                linux_command_for_output(Path("/tmp/out.png"))


if __name__ == "__main__":
    unittest.main()
