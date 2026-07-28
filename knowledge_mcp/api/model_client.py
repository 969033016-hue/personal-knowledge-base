from __future__ import annotations

from typing import Any, Dict, List

import httpx

from .config import ApiSettings


class ModelClient:
    """服务端模型调用客户端。

    阶段二先按 OpenAI 兼容 chat/completions 协议封装，便于后续切换 Claude、豆包或内部网关。
    没有配置模型环境变量时，上层会自动回退到本地规则回答，不影响基础服务启动。
    """

    def __init__(self, settings: ApiSettings):
        self.settings = settings

    def is_enabled(self) -> bool:
        """判断远端模型调用条件是否满足。"""

        return self.settings.model_enabled

    def build_answer(self, question: str, local_answer: str, items: List[Dict[str, Any]]) -> str:
        """基于本地检索结果生成增强回答。

        设计上只把摘要、分类、标签等必要上下文发给模型，避免把无关字段扩大传输面。
        如果远端调用失败，直接返回本地规则答案，保证问答链路可用性优先。
        """

        if not self.is_enabled():
            return local_answer
        context = self._format_context(items)
        messages = [
            {
                "role": "system",
                "content": "你是个人知识库助手。请只基于给定知识上下文回答，无法确定时明确说明缺少依据。",
            },
            {
                "role": "user",
                "content": f"问题：{question}\n\n本地规则答案：{local_answer}\n\n知识上下文：\n{context}",
            },
        ]
        try:
            response = httpx.post(
                self._chat_url(),
                headers={
                    "Authorization": f"Bearer {self.settings.model_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.model_name,
                    "messages": messages,
                    "temperature": 0.2,
                },
                timeout=self.settings.model_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            content = payload.get("choices", [{}])[0].get("message", {}).get("content", "")
            return str(content).strip() or local_answer
        except Exception:
            # 模型属于增强能力，失败时不能影响知识库主链路，直接回退本地答案。
            return local_answer

    def _chat_url(self) -> str:
        base = self.settings.model_api_base.rstrip("/")
        if base.endswith("/chat/completions"):
            return base
        return f"{base}/chat/completions"

    def _format_context(self, items: List[Dict[str, Any]]) -> str:
        if not items:
            return "暂无召回知识。"
        lines: List[str] = []
        for index, item in enumerate(items, start=1):
            tags = "、".join(item.get("tags") or []) or "无"
            lines.append(
                f"{index}. 标题：{item.get('title', '')}\n"
                f"   摘要：{item.get('summary', '')}\n"
                f"   分类：{item.get('category', '')}\n"
                f"   标签：{tags}"
            )
        return "\n".join(lines)
