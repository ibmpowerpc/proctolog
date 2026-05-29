from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class APIError(RuntimeError):
    pass


class OpenAICompatibleClient:
    def __init__(self, api_key: str, base_url: str, timeout_seconds: float = 120.0) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def create_chat_completion(
        self,
        *,
        model: str,
        system_prompt: str,
        prompt: str,
        image_data_urls: list[str],
        detail: str,
    ) -> dict[str, Any]:
        payload = build_image_chat_completion_payload(
            model=model,
            system_prompt=system_prompt,
            prompt=prompt,
            image_data_urls=image_data_urls,
            detail=detail,
        )
        return self._request("POST", "/chat/completions", payload)

    def _request(self, method: str, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            message = error.read().decode("utf-8", errors="replace")
            raise APIError(f"AI API error {error.code}: {message}") from error
        except urllib.error.URLError as error:
            raise APIError(f"AI API request failed: {error}") from error


def build_image_chat_completion_payload(
    *,
    model: str,
    system_prompt: str,
    prompt: str,
    image_data_urls: list[str],
    detail: str,
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for image_data_url in image_data_urls:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": image_data_url,
                    "detail": detail,
                },
            }
        )

    return {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": content,
            },
        ],
    }


def extract_output_text(response: dict[str, Any]) -> str:
    direct = response.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct

    choices = response.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if isinstance(content, str):
                    return content.strip()
                if isinstance(content, list):
                    parts = [
                        item.get("text")
                        for item in content
                        if isinstance(item, dict) and isinstance(item.get("text"), str)
                    ]
                    return "\n".join(parts).strip()

    parts: list[str] = []
    for item in response.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text:
                parts.append(text)
    return "\n".join(parts).strip()
