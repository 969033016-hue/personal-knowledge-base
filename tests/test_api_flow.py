from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from knowledge_mcp.api.app import create_app
from knowledge_mcp.api.config import ApiSettings


class ApiFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.categories_path = root / "bootstrap_categories.json"
        self.categories_path.write_text(
            """
            {
              "categories": [
                {"name": "项目知识", "description": "项目背景"},
                {"name": "测试方法", "description": "测试设计"},
                {"name": "排障案例", "description": "异常排查"}
              ]
            }
            """.strip(),
            encoding="utf-8",
        )
        settings = ApiSettings(
            db_path=root / "knowledge.db",
            categories_path=self.categories_path,
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

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_rest_api_confirm_write_and_query_flow(self) -> None:
        # 输入：不带 confirm_write 的新增请求。
        # 预期输出：服务端只提示需要确认，不应写入知识库。
        blocked = self.client.post(
            "/api/knowledge",
            json={"title": "导量空结果排查", "content": "优先检查实验位、配置、频控和互斥规则。"},
        )
        self.assertEqual(blocked.status_code, 200)
        self.assertTrue(blocked.json()["need_confirm"])

        empty_search = self.client.post("/api/knowledge/search", json={"query": "空结果"})
        self.assertEqual(empty_search.json()["items"], [])

        # 输入：显式确认写入后新增知识。
        # 预期输出：创建知识卡片，并能通过详情、检索和问答接口读到。
        added = self.client.post(
            "/api/knowledge",
            json={
                "title": "导量空结果排查",
                "content": "优先检查实验位、配置、频控和互斥规则。",
                "confirm_write": True,
            },
        )
        self.assertEqual(added.status_code, 200)
        item_id = added.json()["item"]["item_id"]
        self.assertIsNotNone(item_id)

        got = self.client.get(f"/api/knowledge/{item_id}")
        self.assertEqual(got.json()["item"]["title"], "导量空结果排查")

        searched = self.client.post("/api/knowledge/search", json={"query": "空结果", "limit": 3})
        self.assertEqual(len(searched.json()["items"]), 1)

        answered = self.client.post("/api/knowledge/ask", json={"question": "导量空结果先看什么？"})
        self.assertEqual(answered.json()["answer_source"], "local")
        self.assertIn("结论：", answered.json()["answer"])

        # 输入：更新接口同样需要确认。
        # 预期输出：未确认时不更新，确认后正文变更生效。
        blocked_update = self.client.patch(
            f"/api/knowledge/{item_id}",
            json={"content": "这次不应该写入。"},
        )
        self.assertTrue(blocked_update.json()["need_confirm"])
        still_old = self.client.get(f"/api/knowledge/{item_id}")
        self.assertNotIn("不应该写入", still_old.json()["item"]["content"])

        updated = self.client.patch(
            f"/api/knowledge/{item_id}",
            json={"content": "优先检查实验位、配置、频控、互斥规则和缓存。", "confirm_write": True},
        )
        self.assertIn("缓存", updated.json()["item"]["content"])

        # 输入：来源导入和知识关联也必须确认。
        # 预期输出：确认后生成来源、证据和关系。
        ingested = self.client.post(
            "/api/sources/ingest",
            json={
                "title": "接口联调记录",
                "content": "接口返回空列表时先看实验位和配置。",
                "category": "测试方法",
                "confirm_write": True,
            },
        )
        source_item_id = ingested.json()["items"][0]["item_id"]
        linked = self.client.post(
            "/api/links",
            json={
                "from_item_id": item_id,
                "to_item_id": source_item_id,
                "link_type": "supplements",
                "note": "补充联调排查口径",
                "confirm_write": True,
            },
        )
        self.assertEqual(linked.json()["link"]["link_type"], "supplements")

        categories = self.client.get("/api/categories")
        self.assertEqual(categories.json()["categories"][0]["name"], "项目知识")

        lint_result = self.client.get("/api/lint")
        self.assertIn("summary", lint_result.json())


if __name__ == "__main__":
    unittest.main()
