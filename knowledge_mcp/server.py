from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .service import KnowledgeService

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = ROOT_DIR / "data" / "knowledge.db"
DEFAULT_CATEGORIES_PATH = ROOT_DIR / "data" / "bootstrap_categories.json"


class StdioJsonRpcServer:
    def __init__(self, service: KnowledgeService):
        self.service = service
        self.tool_handlers = {
            "add_knowledge": self._handle_add_knowledge,
            "update_knowledge": self._handle_update_knowledge,
            "get_knowledge": self._handle_get_knowledge,
            "search_knowledge": self._handle_search_knowledge,
            "ask_knowledge": self._handle_ask_knowledge,
            "list_categories": self._handle_list_categories,
            "ingest_source": self._handle_ingest_source,
            "lint_knowledge": self._handle_lint_knowledge,
            "link_knowledge": self._handle_link_knowledge,
        }

    def serve(self) -> None:
        while True:
            message = self._read_message()
            if message is None:
                return
            method = message.get("method")
            request_id = message.get("id")
            params = message.get("params", {})
            if method == "initialize":
                self._write_result(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "personal-knowledge-base",
                            "version": "0.2.0",
                        },
                    },
                )
            elif method == "tools/list":
                self._write_result(request_id, {"tools": self._tool_definitions()})
            elif method == "tools/call":
                result = self._call_tool(params)
                self._write_result(request_id, result)
            elif method == "notifications/initialized":
                continue
            else:
                self._write_error(request_id, code=-32601, message=f"unsupported method: {method}")

    def _call_tool(self, params: dict[str, Any]) -> dict[str, Any]:
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        handler = self.tool_handlers.get(str(tool_name))
        if handler is None:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": f"unknown tool: {tool_name}"}, ensure_ascii=False)}],
                "isError": True,
            }
        payload = handler(dict(arguments))
        return {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "isError": bool(payload.get("error")),
        }

    def _tool_definitions(self) -> list[dict[str, Any]]:
        # 工具定义集中维护，方便 MCP 客户端一次性读取完整能力边界。
        return [
            {
                "name": "add_knowledge",
                "description": "新增知识卡片，并自动补齐摘要、分类与标签。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "summary": {"type": "string"},
                        "category": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "project_scope": {"type": "string"},
                        "source_type": {"type": "string"},
                        "confidence": {"type": "string"},
                        "knowledge_type": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "update_knowledge",
                "description": "按知识 ID 更新卡片内容。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer"},
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "summary": {"type": "string"},
                        "category": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "project_scope": {"type": "string"},
                        "source_type": {"type": "string"},
                        "confidence": {"type": "string"},
                        "knowledge_type": {"type": "string"},
                        "status": {"type": "string"},
                    },
                    "required": ["item_id"],
                },
            },
            {
                "name": "get_knowledge",
                "description": "按知识 ID 读取单条知识详情。",
                "inputSchema": {
                    "type": "object",
                    "properties": {"item_id": {"type": "integer"}},
                    "required": ["item_id"],
                },
            },
            {
                "name": "search_knowledge",
                "description": "按关键词、分类、标签检索知识，默认返回摘要预览结果。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "category": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "limit": {"type": "integer"},
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "ask_knowledge",
                "description": "输入问题，自动检索并生成回答，同时返回摘要预览结果。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "limit": {"type": "integer"},
                    },
                    "required": ["question"],
                },
            },
            {
                "name": "list_categories",
                "description": "查看内置分类清单，并同步到知识域表。",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "ingest_source",
                "description": "导入来源材料，创建来源记录、知识卡片和证据片段。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "source_type": {"type": "string"},
                        "uri": {"type": "string"},
                        "owner": {"type": "string"},
                        "category": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "project_scope": {"type": "string"},
                        "confidence": {"type": "string"},
                        "split_by_paragraph": {"type": "boolean"},
                        "metadata": {"type": "object"},
                    },
                    "required": ["title", "content"],
                },
            },
            {
                "name": "lint_knowledge",
                "description": "检查知识库质量问题，返回问题统计和明细。",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "link_knowledge",
                "description": "建立两条知识之间的关系，如补充、依赖、冲突、重复。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "from_item_id": {"type": "integer"},
                        "to_item_id": {"type": "integer"},
                        "link_type": {"type": "string"},
                        "note": {"type": "string"},
                    },
                    "required": ["from_item_id", "to_item_id"],
                },
            },
        ]

    def _handle_add_knowledge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.add_knowledge(**arguments)

    def _handle_update_knowledge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        item_id = int(arguments.pop("item_id"))
        return self.service.update_knowledge(item_id, **arguments)

    def _handle_get_knowledge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.get_knowledge(int(arguments["item_id"]))

    def _handle_search_knowledge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.search_knowledge(
            query=str(arguments.get("query", "")),
            category=arguments.get("category"),
            tags=arguments.get("tags"),
            limit=int(arguments.get("limit", 5)),
        )

    def _handle_ask_knowledge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.ask_knowledge(
            question=str(arguments.get("question", "")),
            limit=int(arguments.get("limit", 3)),
        )

    def _handle_list_categories(self, _: dict[str, Any]) -> dict[str, Any]:
        return self.service.list_categories()

    def _handle_ingest_source(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.ingest_source(**arguments)

    def _handle_lint_knowledge(self, _: dict[str, Any]) -> dict[str, Any]:
        return self.service.lint_knowledge()

    def _handle_link_knowledge(self, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.service.link_knowledge(
            from_item_id=int(arguments["from_item_id"]),
            to_item_id=int(arguments["to_item_id"]),
            link_type=str(arguments.get("link_type", "related")),
            note=str(arguments.get("note", "")),
        )

    def _read_message(self) -> dict[str, Any] | None:
        headers: dict[str, str] = {}
        while True:
            line = sys.stdin.buffer.readline()
            if not line:
                return None
            decoded = line.decode("utf-8").strip()
            if not decoded:
                break
            key, _, value = decoded.partition(":")
            headers[key.strip().lower()] = value.strip()

        content_length = int(headers.get("content-length", "0"))
        if content_length <= 0:
            return None
        body = sys.stdin.buffer.read(content_length)
        return json.loads(body.decode("utf-8"))

    def _write_result(self, request_id: Any, result: dict[str, Any]) -> None:
        payload = {"jsonrpc": "2.0", "id": request_id, "result": result}
        self._write_message(payload)

    def _write_error(self, request_id: Any, code: int, message: str) -> None:
        payload = {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {"code": code, "message": message},
        }
        self._write_message(payload)

    def _write_message(self, payload: dict[str, Any]) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        sys.stdout.buffer.write(f"Content-Length: {len(raw)}\r\n\r\n".encode("utf-8"))
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()


def build_service(db_path: str | Path | None = None) -> KnowledgeService:
    return KnowledgeService(db_path or DEFAULT_DB_PATH, DEFAULT_CATEGORIES_PATH)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the personal knowledge service.")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH), help="SQLite database path")
    parser.add_argument("--mode", default="stdio", choices=["stdio"], help="Transport mode")
    args = parser.parse_args()

    service = build_service(args.db_path)
    server = StdioJsonRpcServer(service)
    server.serve()


if __name__ == "__main__":
    main()
