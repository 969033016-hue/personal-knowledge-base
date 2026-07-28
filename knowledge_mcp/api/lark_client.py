from __future__ import annotations

from typing import Any, Dict

import json

import httpx

from .config import ApiSettings


class LarkClient:
    """飞书开放平台客户端。

    当前只封装机器人回复必需的 token 获取和消息回复能力。真实 AppID、Secret 从环境变量读取，
    测试环境未配置时不会调用外部接口，便于本地单测稳定运行。
    """

    def __init__(self, settings: ApiSettings):
        self.settings = settings
        self._tenant_access_token = ""

    def is_enabled(self) -> bool:
        """判断是否具备真实回复飞书消息的配置。"""

        return self.settings.lark_reply_enabled

    def reply_text(self, message_id: str, text: str) -> Dict[str, Any]:
        """回复飞书文本消息。

        如果未配置飞书凭证，只返回 skipped，避免本地开发和自动化测试误触发外部发送。
        """

        if not self.is_enabled():
            return {"skipped": True, "reason": "lark credentials are not configured"}
        token = self._get_tenant_access_token()
        response = httpx.post(
            f"https://open.feishu.cn/open-apis/im/v1/messages/{message_id}/reply",
            headers={"Authorization": f"Bearer {token}"},
            json={"msg_type": "text", "content": json.dumps({"text": text}, ensure_ascii=False)},
            timeout=10,
        )
        response.raise_for_status()
        return response.json()

    def _get_tenant_access_token(self) -> str:
        """获取 tenant_access_token，并在进程内做轻量缓存。"""

        if self._tenant_access_token:
            return self._tenant_access_token
        response = httpx.post(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self.settings.lark_app_id,
                "app_secret": self.settings.lark_app_secret,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        token = str(payload.get("tenant_access_token", ""))
        if not token:
            raise RuntimeError("tenant_access_token is empty")
        self._tenant_access_token = token
        return token
