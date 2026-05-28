from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from knowledge_mcp.service import KnowledgeService


class KnowledgeFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_path = root / "knowledge.db"
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
        self.service = KnowledgeService(self.db_path, self.categories_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_add_search_and_ask(self) -> None:
        added = self.service.add_knowledge(
            title="导量空结果排查",
            content="当任务列表为空时，优先检查互斥规则、频控和实验位。",
        )
        item_id = added["item"]["item_id"]
        self.assertIsNotNone(item_id)
        self.assertEqual(added["item"]["title"], "导量空结果排查")
        self.assertTrue(added["item"]["tags"])

        searched = self.service.search_knowledge("空结果", limit=3)
        self.assertEqual(len(searched["items"]), 1)
        self.assertEqual(searched["items"][0]["item_id"], item_id)

        answered = self.service.ask_knowledge("导量任务空结果先排查什么？", limit=2)
        self.assertIn("结论：", answered["answer"])
        self.assertIn("导量空结果排查", answered["answer"])

        updated = self.service.update_knowledge(item_id, content="优先检查互斥规则、频控、实验位和配置开关。")
        self.assertIn("配置开关", updated["item"]["content"])

        got = self.service.get_knowledge(item_id)
        self.assertEqual(got["item"]["item_id"], item_id)


if __name__ == "__main__":
    unittest.main()
