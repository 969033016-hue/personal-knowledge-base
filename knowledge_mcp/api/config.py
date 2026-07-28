from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from knowledge_mcp.core.storage import DatabaseSyncAdapter
from knowledge_mcp.core.tos_sync import TosDatabaseSyncAdapter
from knowledge_mcp.server import DEFAULT_CATEGORIES_PATH, DEFAULT_DB_PATH


@dataclass(frozen=True)
class ApiSettings:
    """HTTP 服务配置。

    所有敏感配置只从环境变量读取，仓库中只保留变量名和占位说明，避免把真实密钥写入代码。
    storage_backend 用于区分本地 SQLite 和函数计算场景下的 TOS 对象存储。
    """

    db_path: Path
    categories_path: Path
    service_name: str
    lark_app_id: str
    lark_app_secret: str
    lark_verification_token: str
    lark_encrypt_key: str
    model_api_base: str
    model_api_key: str
    model_name: str
    model_timeout_seconds: float
    storage_backend: str = "sqlite"
    tos_endpoint: str = ""
    tos_region: str = ""
    tos_bucket: str = ""
    tos_object_key: str = ""
    tos_access_key_id: str = ""
    tos_secret_access_key: str = ""
    tos_security_token: str = ""

    @property
    def model_enabled(self) -> bool:
        """只有模型地址、密钥和模型名都配置后，才启用远端模型回答。"""

        return bool(self.model_api_base and self.model_api_key and self.model_name)

    @property
    def lark_reply_enabled(self) -> bool:
        """只有 AppID 和 Secret 都配置后，才真正调用飞书 OpenAPI 回复消息。"""

        return bool(self.lark_app_id and self.lark_app_secret)

    @property
    def tos_enabled(self) -> bool:
        """显式选择 TOS 后才启用对象存储同步，避免影响本地开发和单测。"""

        return self.storage_backend.lower() == "tos"

    def build_sync_adapter(self) -> DatabaseSyncAdapter | None:
        """按配置创建数据库同步适配器。

        本地开发默认返回 None；函数计算部署时返回 TOS 适配器，由存储层在读写 SQLite 前后自动同步。
        """

        if not self.tos_enabled:
            return None
        return TosDatabaseSyncAdapter(
            endpoint=self.tos_endpoint,
            region=self.tos_region,
            bucket=self.tos_bucket,
            object_key=self.tos_object_key,
            access_key_id=self.tos_access_key_id,
            secret_access_key=self.tos_secret_access_key,
            security_token=self.tos_security_token,
        )


def load_settings() -> ApiSettings:
    """从环境变量加载配置，并为本地开发提供安全默认值。"""

    storage_backend = os.getenv("KNOWLEDGE_STORAGE_BACKEND", "sqlite").strip().lower()
    default_db_path = "/tmp/knowledge.db" if storage_backend == "tos" else str(DEFAULT_DB_PATH)
    return ApiSettings(
        db_path=Path(os.getenv("KNOWLEDGE_DB_PATH", default_db_path)),
        categories_path=Path(os.getenv("KNOWLEDGE_CATEGORIES_PATH", str(DEFAULT_CATEGORIES_PATH))),
        service_name=os.getenv("KNOWLEDGE_SERVICE_NAME", "personal-knowledge-base"),
        lark_app_id=os.getenv("LARK_APP_ID", ""),
        lark_app_secret=os.getenv("LARK_APP_SECRET", ""),
        lark_verification_token=os.getenv("LARK_VERIFICATION_TOKEN", ""),
        lark_encrypt_key=os.getenv("LARK_ENCRYPT_KEY", ""),
        model_api_base=os.getenv("MODEL_API_BASE", ""),
        model_api_key=os.getenv("MODEL_API_KEY", ""),
        model_name=os.getenv("MODEL_NAME", ""),
        model_timeout_seconds=float(os.getenv("MODEL_TIMEOUT_SECONDS", "20")),
        storage_backend=storage_backend,
        tos_endpoint=os.getenv("TOS_ENDPOINT", ""),
        tos_region=os.getenv("TOS_REGION", ""),
        tos_bucket=os.getenv("TOS_BUCKET", ""),
        tos_object_key=os.getenv("TOS_OBJECT_KEY", "knowledge/knowledge.db"),
        tos_access_key_id=os.getenv("TOS_ACCESS_KEY_ID", ""),
        tos_secret_access_key=os.getenv("TOS_SECRET_ACCESS_KEY", ""),
        tos_security_token=os.getenv("TOS_SECURITY_TOKEN", ""),
    )
