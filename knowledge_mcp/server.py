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
                            "version": "0.1.0",
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
        payload = handler(arguments)
        return {
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, indent=2)}],
            "isError": bool(payload.get("error")),
        }

    def _tool_definitions(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "add_knowledge",
                "description": "新增知识条目，并自动补齐摘要、分类与标签。",
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
                        "confidence": {"type": "string"}
                    },
                    "required": ["title", "content"]
                }
            },
            {
                "name": "update_knowledge",
                "description": "按知识 ID 更新条目内容。",
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
                        "confidence": {"type": "string"}
                    },
                    "required": ["item_id"]
                }
            },
            {
                "name": "get_knowledge",
                "description": "按知识 ID 读取单条知识。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "item_id": {"type": "integer"}
                    },
                    "required": ["item_id"]
                }
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
                        "limit": {"type": "integer"}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "ask_knowledge",
                "description": "输入问题，自动检索并生成回答，同时返回摘要预览结果。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["question"]
                }
            },
            {
                "name": "list_categories",
                "description": "查看内置分类清单。",
                "inputSchema": {
                    "type": "object",
                    "properties": {}
                }
            }
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
