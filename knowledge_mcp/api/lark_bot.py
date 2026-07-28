from __future__ import annotations

import json
from typing import Any, Dict

from knowledge_mcp.service import KnowledgeService

from .config import ApiSettings
from .lark_client import LarkClient
from .model_client import ModelClient


class LarkBotHandler:
    """飞书机器人事件处理器。

    该模块只负责解析事件、分发命令和触发回复；知识检索、问答和写入仍统一走 KnowledgeService，
    避免机器人入口绕过阶段二 REST 服务的安全边界。
    """

    def __init__(
        self,
        settings: ApiSettings,
        service: KnowledgeService,
        lark_client: LarkClient,
        model_client: ModelClient,
    ):
        self.settings = settings
        self.service = service
        self.lark_client = lark_client
        self.model_client = model_client

    def handle_event(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """处理飞书回调。

        URL verification 直接返回 challenge；消息事件会解析文本并生成知识库回答。
        单测和本地环境未配置飞书凭证时，只返回 reply_text，不发送真实消息。
        """

        if payload.get("type") == "url_verification":
            return self._handle_url_verification(payload)

        event = payload.get("event", {}) if isinstance(payload.get("event"), dict) else {}
        message = event.get("message", {}) if isinstance(event.get("message"), dict) else {}
        message_id = str(message.get("message_id", ""))
        text = self.extract_text(message)
        reply_text = self.dispatch_text(text)
        send_result = {}
        if message_id:
            send_result = self.lark_client.reply_text(message_id, reply_text)
        return {
            "ok": True,
            "message_id": message_id,
            "received_text": text,
            "reply_text": reply_text,
            "send_result": send_result,
        }

    def extract_text(self, message: Dict[str, Any]) -> str:
        """兼容解析飞书文本消息。

        飞书文本 content 常见形态是 JSON 字符串：{"text":"xxx"}。这里兼容字符串、字典和异常格式，
        确保机器人不会因为单条脏消息影响服务可用性。
        """

        raw_content = message.get("content", "")
        if isinstance(raw_content, dict):
            return str(raw_content.get("text", "")).strip()
        if not isinstance(raw_content, str):
            return ""
        try:
            parsed = json.loads(raw_content)
            if isinstance(parsed, dict):
                return str(parsed.get("text", "")).strip()
        except json.JSONDecodeError:
            return raw_content.strip()
        return raw_content.strip()

    def dispatch_text(self, text: str) -> str:
        """按机器人命令分发。

        默认把普通文本当成问题处理；写入类命令暂不开放自动执行，避免聊天入口误写知识库。
        """

        cleaned = text.strip()
        if not cleaned or cleaned in {"/help", "help", "帮助"}:
            return self._help_text()
        if cleaned.startswith("/search "):
            query = cleaned.removeprefix("/search ").strip()
            return self._format_search_result(query)
        if cleaned.startswith("/ask "):
            question = cleaned.removeprefix("/ask ").strip()
            return self._format_answer(question)
        if cleaned.startswith(("/add", "/update", "/ingest", "/link")):
            return "为避免误写知识库，飞书入口暂不直接执行写操作。请改用 REST 接口并显式传 confirm_write=true。"
        return self._format_answer(cleaned)

    def _handle_url_verification(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        token = str(payload.get("token", ""))
        if self.settings.lark_verification_token and token != self.settings.lark_verification_token:
            return {"error": "verification token mismatch"}
        return {"challenge": payload.get("challenge", "")}

    def _format_search_result(self, query: str) -> str:
        if not query:
            return "请在 /search 后输入关键词，例如：/search 空结果"
        result = self.service.search_knowledge(query=query, limit=5)
        items = result.get("items", [])
        if not items:
            return f"没有检索到和“{query}”相关的知识。"
        lines = [f"检索到 {len(items)} 条相关知识："]
        for index, item in enumerate(items, start=1):
            lines.append(f"{index}. {item.get('title', '')}｜{item.get('summary', '')}")
        return "\n".join(lines)

    def _format_answer(self, question: str) -> str:
        if not question:
            return "请在 /ask 后输入问题，例如：/ask 导量空结果先看什么？"
        result = self.service.ask_knowledge(question=question, limit=3)
        local_answer = str(result.get("answer", ""))
        enhanced_answer = self.model_client.build_answer(
            question=question,
            local_answer=local_answer,
            items=list(result.get("items", [])),
        )
        return enhanced_answer

    def _help_text(self) -> str:
        return (
            "知识库机器人支持：\n"
            "1. 直接发送问题：自动检索并回答。\n"
            "2. /ask 问题：显式问答。\n"
            "3. /search 关键词：只检索知识摘要。\n"
            "写入类操作请使用 REST 接口，并显式确认写入。"
        )
