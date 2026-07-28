from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from knowledge_mcp.api.app import create_app
from knowledge_mcp.api.config import ApiSettings


class LarkBotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        categories_path = root / "bootstrap_categories.json"
        categories_path.write_text(
            """
            {
              "categories": [
                {"name": "项目知识", "description": "项目背景"},
                {"name": "测试方法", "description": "测试设计"}
              ]
            }
            """.strip(),
            encoding="utf-8",
        )
        settings = ApiSettings(
            db_path=root / "knowledge.db",
            categories_path=categories_path,
            service_name="test-knowledge-service",
            lark_app_id="",
            lark_app_secret="",
            lark_verification_token="token-for-test",
            lark_encrypt_key="",
            model_api_base="",
            model_api_key="",
            model_name="",
            model_timeout_seconds=3,
        )
        self.client = TestClient(create_app(settings))
        self.client.post(
            "/api/knowledge",
            json={
                "title": "接口空结果排查",
                "content": "接口返回空列表时，优先检查实验位、配置、频控和互斥规则。",
                "confirm_write": True,
            },
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_lark_verification_and_message_dispatch(self) -> None:
        # 输入：飞书 URL verification 事件。
        # 预期输出：token 匹配时原样返回 challenge。
        verification = self.client.post(
            "/api/lark/events",
            json={"type": "url_verification", "token": "token-for-test", "challenge": "challenge-value"},
        )
        self.assertEqual(verification.json()["challenge"], "challenge-value")

        mismatch = self.client.post(
            "/api/lark/events",
            json={"type": "url_verification", "token": "bad-token", "challenge": "challenge-value"},
        )
        self.assertIn("error", mismatch.json())

        # 输入：飞书文本消息，content 使用飞书常见 JSON 字符串格式。
        # 预期输出：本地未配置飞书凭证时不真实发送，但会生成回复文本。
        message_event = self.client.post(
            "/api/lark/events",
            json={
                "schema": "2.0",
                "event": {
                    "message": {
                        "message_id": "message-test-id",
                        "message_type": "text",
                        "content": json.dumps({"text": "/search 空结果"}, ensure_ascii=False),
                    }
                },
            },
        )
        payload = message_event.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["received_text"], "/search 空结果")
        self.assertIn("接口空结果排查", payload["reply_text"])
        self.assertTrue(payload["send_result"]["skipped"])

        help_event = self.client.post(
            "/api/lark/events",
            json={"event": {"message": {"content": json.dumps({"text": "/help"}, ensure_ascii=False)}}},
        )
        self.assertIn("知识库机器人支持", help_event.json()["reply_text"])

        write_event = self.client.post(
            "/api/lark/events",
            json={"event": {"message": {"content": json.dumps({"text": "/add 新知识"}, ensure_ascii=False)}}},
        )
        self.assertIn("暂不直接执行写操作", write_event.json()["reply_text"])


if __name__ == "__main__":
    unittest.main()
