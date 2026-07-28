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

    def test_phase_one_schema_tools_and_basic_flow(self) -> None:
        # 输入：只提供标题和正文，验证旧 add/search/ask 链路仍然可用。
        added = self.service.add_knowledge(
            title="导量空结果排查",
            content="当任务列表为空时，优先检查互斥规则、频控和实验位。",
        )
        item_id = added["item"]["item_id"]
        self.assertIsNotNone(item_id)
        self.assertEqual(added["item"]["title"], "导量空结果排查")
        self.assertTrue(added["item"]["tags"])
        self.assertEqual(added["item"]["status"], "active")

        # 预期输出：摘要检索不返回正文，但会返回来源标题和证据数量，便于先摘要后详情。
        searched = self.service.search_knowledge("空结果", limit=3)
        self.assertEqual(len(searched["items"]), 1)
        self.assertEqual(searched["items"][0]["item_id"], item_id)
        self.assertIn("source_titles", searched["items"][0])
        self.assertIn("evidence_count", searched["items"][0])
        self.assertNotIn("content", searched["items"][0])

        answered = self.service.ask_knowledge("导量任务空结果先排查什么？", limit=2)
        self.assertIn("结论：", answered["answer"])
        self.assertIn("导量空结果排查", answered["answer"])

        updated = self.service.update_knowledge(item_id, content="优先检查互斥规则、频控、实验位和配置开关。")
        self.assertIn("配置开关", updated["item"]["content"])

        # 输入：导入来源材料，验证来源、知识卡片、证据三者能自动串起来。
        ingested = self.service.ingest_source(
            title="接口联调记录",
            content="接口返回空列表时先看实验位和配置。\n\n发奖链路要校验金额精度和幂等。",
            source_type="note",
            uri="local://debug-note",
            category="测试方法",
            tags=["接口", "发奖"],
        )
        self.assertEqual(len(ingested["items"]), 2)
        self.assertEqual(ingested["source"]["title"], "接口联调记录")
        self.assertGreater(ingested["items"][0]["evidence"]["evidence_id"], 0)

        source_item_id = ingested["items"][0]["item_id"]
        got = self.service.get_knowledge(source_item_id)
        self.assertEqual(got["item"]["source_titles"], ["接口联调记录"])
        self.assertEqual(got["item"]["evidence_count"], 1)

        # 输入：建立知识关系，验证阶段一新增 link_knowledge 工具可用。
        linked = self.service.link_knowledge(
            from_item_id=item_id,
            to_item_id=source_item_id,
            link_type="supplements",
            note="接口联调记录补充了空结果排查口径",
        )
        self.assertEqual(linked["link"]["link_type"], "supplements")

        # 预期输出：旧 add 写入的知识因为缺证据被提示，新 ingest 写入的知识不应出现缺证据问题。
        lint_result = self.service.lint_knowledge()
        self.assertGreaterEqual(lint_result["summary"]["issue_count"], 1)
        issue_codes = {issue["code"] for issue in lint_result["issues"]}
        self.assertIn("missing_evidence", issue_codes)

        categories = self.service.list_categories()
        self.assertEqual(categories["categories"][0]["name"], "项目知识")


if __name__ == "__main__":
    unittest.main()
