from __future__ import annotations

from pathlib import Path
import os
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

    if platform.system() == "Linux":
        return linux_command_for_output(output_path)

    raise ScreenshotError(
        "unsupported platform; set screenshot_command in the config"
    )


def linux_command_for_output(output_path: Path) -> list[str]:
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    if session_type == "wayland":
        cmd = _wayland_command_for_output(output_path)
        if cmd:
            return cmd

    if session_type == "x11":
        cmd = _x11_command_for_output(output_path)
        if cmd:
            return cmd

    # Unknown session type: try Wayland first, then X11. This covers shells that
    # do not export XDG_SESSION_TYPE.
    cmd = _wayland_command_for_output(output_path) or _x11_command_for_output(output_path)
    if cmd:
        return cmd

    raise ScreenshotError(
        "no Linux screenshot command found; install grim, gnome-screenshot, "
        "spectacle, scrot, or imagemagick, or set screenshot_command in the config"
    )


def _wayland_command_for_output(output_path: Path) -> list[str] | None:
    grim = shutil.which("grim")
    if grim:
        return [grim, str(output_path)]

    gnome_screenshot = shutil.which("gnome-screenshot")
    if gnome_screenshot:
        return [gnome_screenshot, "-f", str(output_path)]

    spectacle = shutil.which("spectacle")
    if spectacle:
        return [spectacle, "-b", "-n", "-o", str(output_path)]

    return None


def _x11_command_for_output(output_path: Path) -> list[str] | None:
    gnome_screenshot = shutil.which("gnome-screenshot")
    if gnome_screenshot:
        return [gnome_screenshot, "-f", str(output_path)]

    spectacle = shutil.which("spectacle")
    if spectacle:
        return [spectacle, "-b", "-n", "-o", str(output_path)]

    scrot = shutil.which("scrot")
    if scrot:
        return [scrot, str(output_path)]

    imagemagick_import = shutil.which("import")
    if imagemagick_import:
        return [imagemagick_import, "-window", "root", str(output_path)]

    return None
