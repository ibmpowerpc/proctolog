from __future__ import annotations

import unittest

from proc_util.openai_client import build_image_chat_completion_payload, extract_output_text


class OpenAICompatibleClientTests(unittest.TestCase):
    def test_builds_vision_payload_with_conversation(self) -> None:
        payload = build_image_chat_completion_payload(
            model="x-ai/grok-4.3",
            system_prompt="system",
            prompt="check this",
            image_data_urls=["data:image/png;base64,AAAA"],
            detail="low",
        )

        self.assertEqual(payload["model"], "x-ai/grok-4.3")
        self.assertEqual(payload["messages"][0]["role"], "system")
        self.assertEqual(payload["messages"][1]["content"][0]["type"], "text")
        self.assertEqual(payload["messages"][1]["content"][1]["type"], "image_url")

    def test_builds_payload_with_previous_and_current_images(self) -> None:
        payload = build_image_chat_completion_payload(
            model="x-ai/grok-4.3",
            system_prompt="system",
            prompt="check this",
            image_data_urls=[
                "data:image/png;base64,PREVIOUS",
                "data:image/png;base64,CURRENT",
            ],
            detail="low",
        )

        content = payload["messages"][1]["content"]
        self.assertEqual(content[1]["image_url"]["url"], "data:image/png;base64,PREVIOUS")
        self.assertEqual(content[2]["image_url"]["url"], "data:image/png;base64,CURRENT")

    def test_extracts_output_text_from_chat_completion(self) -> None:
        response = {"choices": [{"message": {"content": "hello"}}]}

        self.assertEqual(extract_output_text(response), "hello")

    def test_extracts_output_text_from_nested_response(self) -> None:
        response = {
            "output": [
                {
                    "type": "message",
                    "content": [
                        {"type": "output_text", "text": "hello"},
                        {"type": "output_text", "text": "world"},
                    ],
                }
            ]
        }

        self.assertEqual(extract_output_text(response), "hello\nworld")


if __name__ == "__main__":
    unittest.main()
