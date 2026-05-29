from __future__ import annotations

from html import escape
import json
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import socket
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import Config, expand_path
from .control import is_paused, toggle_paused


def serve(config: Config, host: str, port: int) -> None:
    output_dir = expand_path(config.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    handler = _handler_for(output_dir)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Serving proc-util transcript from {output_dir}")
    print(f"Local URL: http://127.0.0.1:{server.server_port}")
    for address in _local_addresses():
        print(f"LAN URL:   http://{address}:{server.server_port}")
    server.serve_forever()


def _handler_for(output_dir: Path) -> type[BaseHTTPRequestHandler]:
    class ProcUtilHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(_render_index(output_dir))
                return
            if parsed.path == "/events.json":
                limit = _limit_from_query(parsed.query)
                self._send_json(_read_events(output_dir, limit=limit))
                return
            if parsed.path == "/health":
                self._send_text("ok\n", content_type="text/plain; charset=utf-8")
                return
            self.send_error(404, "not found")

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/pause":
                toggle_paused(output_dir)
                self.send_response(303)
                self.send_header("Location", "/")
                self.end_headers()
                return
            self.send_error(404, "not found")

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_html(self, body: str) -> None:
            self._send_text(body, content_type="text/html; charset=utf-8")

        def _send_json(self, data: Any) -> None:
            encoded = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_text(self, body: str, content_type: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return ProcUtilHandler


def _render_index(output_dir: Path) -> str:
    latest = _latest_event(output_dir)
    output_text = escape(str(latest.get("output_text") or "")) if latest else ""
    pause_label = "Продолжить" if is_paused(output_dir) else "Пауза"
    return f"""<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="10">
  <title>proc-util answers</title>
  <style>
    :root {{
      color-scheme: light dark;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.45;
    }}
    html, body {{
      min-height: 100%;
    }}
    body {{
      margin: 0;
      padding: 22px 22px 88px;
    }}
    pre {{
      white-space: pre-wrap;
      overflow-wrap: anywhere;
      margin: 0;
      font: inherit;
    }}
    form {{
      position: fixed;
      right: 16px;
      bottom: 16px;
      margin: 0;
    }}
    button {{
      border: 1px solid color-mix(in srgb, CanvasText 25%, transparent);
      border-radius: 999px;
      padding: 10px 14px;
      background: Canvas;
      color: CanvasText;
      font: inherit;
    }}
  </style>
</head>
<body>
  <pre>{output_text}</pre>
  <form method="post" action="/pause">
    <button type="submit">{pause_label}</button>
  </form>
</body>
</html>
"""


def _read_events(output_dir: Path, limit: int) -> list[dict[str, Any]]:
    path = output_dir / "events.jsonl"
    if not path.exists():
        return []

    lines = path.read_text(encoding="utf-8").splitlines()
    events: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _latest_event(output_dir: Path) -> dict[str, Any] | None:
    events = _read_events(output_dir, limit=1)
    return events[-1] if events else None


def _limit_from_query(query: str) -> int:
    raw_limit = parse_qs(query).get("limit", ["100"])[0]
    try:
        return max(1, min(int(raw_limit), 1000))
    except ValueError:
        return 100


def _local_addresses() -> list[str]:
    addresses: set[str] = set()
    hostname = socket.gethostname()
    try:
        for item in socket.getaddrinfo(hostname, None, socket.AF_INET):
            address = item[4][0]
            if not address.startswith("127."):
                addresses.add(address)
    except socket.gaierror:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            addresses.add(sock.getsockname()[0])
    except OSError:
        pass

    return sorted(addresses)
