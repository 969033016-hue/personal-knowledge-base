from __future__ import annotations

from pathlib import Path
from threading import RLock


class TosDatabaseSyncAdapter:
    """把 SQLite 数据库文件同步到火山引擎 TOS。

    函数计算实例是无状态运行环境，本地磁盘只适合作为一次请求或一个热实例周期内的临时缓存。
    当前项目的数据层仍然复用 SQLite 的成熟表结构和查询能力，但把 SQLite 文件本身托管到 TOS，
    通过“访问前拉取、写入后回传”的方式降低实例回收导致的数据丢失风险。

    适用边界：个人知识库、低并发后台服务、机器人问答等轻量场景。如果后续出现高并发写入，
    建议升级到 RDS、veDB 或其他具备事务锁能力的托管数据库，避免对象存储覆盖写带来的竞态。
    """

    def __init__(
        self,
        endpoint: str,
        region: str,
        bucket: str,
        object_key: str,
        access_key_id: str,
        secret_access_key: str,
        security_token: str = "",
    ):
        self.endpoint = endpoint.strip()
        self.region = region.strip()
        self.bucket = bucket.strip()
        self.object_key = object_key.strip().lstrip("/")
        self.access_key_id = access_key_id.strip()
        self.secret_access_key = secret_access_key.strip()
        self.security_token = security_token.strip()
        self._lock = RLock()
        self._client = self._build_client()

    def pull(self, db_path: Path) -> None:
        """从 TOS 拉取数据库文件。

        如果远端对象还不存在，说明这是首次部署或首次初始化，此时保留本地空库创建流程。
        其他异常直接抛出，让函数计算平台记录错误日志，避免静默使用过期数据。
        """

        with self._lock:
            db_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                response = self._client.get_object(self.bucket, self.object_key)
                db_path.write_bytes(response.read())
            except Exception as exc:  # noqa: BLE001 - TOS SDK 不同版本异常类型不完全一致，需要兼容处理。
                if self._is_not_found_error(exc):
                    return
                raise

    def push(self, db_path: Path) -> None:
        """把本地 SQLite 数据库上传到 TOS。"""

        with self._lock:
            if not db_path.exists():
                return
            self._client.put_object(self.bucket, self.object_key, content=db_path.read_bytes())

    def _build_client(self):
        """延迟导入 TOS SDK，避免本地 SQLite 模式强依赖对象存储依赖。"""

        if not all([self.endpoint, self.region, self.bucket, self.object_key, self.access_key_id, self.secret_access_key]):
            raise ValueError("TOS 存储已启用，但 endpoint、region、bucket、object_key、access_key_id 或 secret_access_key 未配置完整")
        try:
            import tos
        except ImportError as exc:
            raise RuntimeError("TOS 存储已启用，但未安装 tos SDK，请先安装 requirements.txt 中的依赖") from exc
        return tos.TosClientV2(
            self.access_key_id,
            self.secret_access_key,
            self.endpoint,
            self.region,
            security_token=self.security_token or None,
        )

    def _is_not_found_error(self, exc: Exception) -> bool:
        """兼容判断 TOS 对象不存在错误。

        不同 SDK 版本暴露的异常字段可能有差异，这里同时检查 status_code、code 和 message，
        只把明确的 404 / NoSuchKey 当作“首次初始化”处理。
        """

        status_code = getattr(exc, "status_code", None)
        error_code = str(getattr(exc, "code", ""))
        message = str(exc)
        return status_code == 404 or "NoSuchKey" in error_code or "not found" in message.lower()
