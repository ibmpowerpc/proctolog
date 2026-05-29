from __future__ import annotations

from pathlib import Path
import platform
import shutil
import subprocess


class ScreenshotError(RuntimeError):
    pass


def capture_screenshot(output_path: Path, command: list[str] | None = None) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = command_for_output(output_path, command)
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise ScreenshotError(f"screenshot command failed ({result.returncode}): {stderr}")
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise ScreenshotError(f"screenshot was not created: {output_path}")
    return output_path


def command_for_output(output_path: Path, command: list[str] | None = None) -> list[str]:
    if command:
        rendered = [part.replace("{output}", str(output_path)) for part in command]
        if all("{output}" not in part for part in command):
            rendered.append(str(output_path))
        return rendered

    if platform.system() == "Darwin":
        return ["/usr/sbin/screencapture", "-x", str(output_path)]

    gnome_screenshot = shutil.which("gnome-screenshot")
    if gnome_screenshot:
        return [gnome_screenshot, "-f", str(output_path)]

    grim = shutil.which("grim")
    if grim:
        return [grim, str(output_path)]

    imagemagick_import = shutil.which("import")
    if imagemagick_import:
        return [imagemagick_import, "-window", "root", str(output_path)]

    raise ScreenshotError(
        "no screenshot command found; set screenshot_command in the config"
    )
