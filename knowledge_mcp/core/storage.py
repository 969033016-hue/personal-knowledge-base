from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Protocol

from .classifier import normalize_tags
from .schema import (
    ALLOWED_CONFIDENCE,
    ALLOWED_LINK_TYPES,
    ALLOWED_STATUS,
    KnowledgeDomain,
    KnowledgeEvidence,
    KnowledgeItem,
    KnowledgeLink,
    KnowledgeSource,
    now_iso,
)


class DatabaseSyncAdapter(Protocol):
    """数据库文件同步适配器。

    这个协议只关心 SQLite 文件的拉取和回写，不关心底层是 TOS、NAS 还是其他对象存储。
    这样可以让核心存储层继续复用 SQLite 表结构和 SQL 逻辑，同时把函数计算环境里的
    “本地磁盘不可靠”问题收敛到一个很薄的同步适配器里。
    """

    def pull(self, db_path: Path) -> None:
        """在读取或写入 SQLite 前，把远端数据库同步到当前函数实例本地。"""

    def push(self, db_path: Path) -> None:
        """在写事务提交后，把当前函数实例本地数据库回写到远端存储。"""


class KnowledgeStorage:
    def __init__(self, db_path: str | Path, sync_adapter: DatabaseSyncAdapter | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.sync_adapter = sync_adapter

    def _sync_before_access(self) -> None:
        # 函数计算实例可能随时被回收，本地 SQLite 文件不能作为最终数据源。
        # 每次访问数据库前先尝试从远端拉取，可降低冷启动或实例切换后的数据丢失风险。
        if self.sync_adapter is not None:
            self.sync_adapter.pull(self.db_path)

    def _sync_after_write(self) -> None:
        # 所有写事务提交完成后立即回写远端对象存储，确保下一次冷启动能拿到最新数据库。
        if self.sync_adapter is not None:
            self.sync_adapter.push(self.db_path)

    def _connect(self) -> sqlite3.Connection:
        self._sync_before_access()
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_domains (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT NOT NULL,
                    parent_id INTEGER,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(parent_id) REFERENCES knowledge_domains(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS knowledge_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    uri TEXT NOT NULL,
                    owner TEXT NOT NULL,
                    captured_at TEXT NOT NULL,
                    metadata_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(title, uri)
                );

                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    domain_id INTEGER,
                    project_scope TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    knowledge_type TEXT NOT NULL DEFAULT 'note',
                    status TEXT NOT NULL DEFAULT 'active',
                    related_items TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(domain_id) REFERENCES knowledge_domains(id) ON DELETE SET NULL
                );

                CREATE TABLE IF NOT EXISTS item_tags (
                    item_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    UNIQUE(item_id, tag),
                    FOREIGN KEY(item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_evidence (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    source_id INTEGER NOT NULL,
                    quote TEXT NOT NULL,
                    locator TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
                    FOREIGN KEY(source_id) REFERENCES knowledge_sources(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS knowledge_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_item_id INTEGER NOT NULL,
                    to_item_id INTEGER NOT NULL,
                    link_type TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(from_item_id, to_item_id, link_type),
                    FOREIGN KEY(from_item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
                    FOREIGN KEY(to_item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
                );
                """
            )
            self._migrate_knowledge_items(connection)
            connection.commit()
            self._sync_after_write()

    def _migrate_knowledge_items(self, connection: sqlite3.Connection) -> None:
        # 兼容 V1 数据库：如果本地已有旧表，只补字段，不要求用户删除数据库重建。
        existing_columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(knowledge_items)").fetchall()
        }
        migrations = {
            "domain_id": "ALTER TABLE knowledge_items ADD COLUMN domain_id INTEGER",
            "knowledge_type": "ALTER TABLE knowledge_items ADD COLUMN knowledge_type TEXT NOT NULL DEFAULT 'note'",
            "status": "ALTER TABLE knowledge_items ADD COLUMN status TEXT NOT NULL DEFAULT 'active'",
        }
        for column_name, statement in migrations.items():
            if column_name not in existing_columns:
                connection.execute(statement)

    def ensure_domain(self, name: str, description: str = "") -> KnowledgeDomain:
        clean_name = name.strip() or "未分类"
        current_time = now_iso()
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_domains WHERE name = ?",
                (clean_name,),
            ).fetchone()
            if row is not None:
                return KnowledgeDomain.from_row(dict(row))
            cursor = connection.execute(
                """
                INSERT INTO knowledge_domains (name, description, parent_id, created_at, updated_at)
                VALUES (?, ?, NULL, ?, ?)
                """,
                (clean_name, description, current_time, current_time),
            )
            connection.commit()
            self._sync_after_write()
            return KnowledgeDomain(
                domain_id=int(cursor.lastrowid),
                name=clean_name,
                description=description,
                created_at=current_time,
                updated_at=current_time,
            )

    def add_source(self, source: KnowledgeSource) -> KnowledgeSource:
        current_time = now_iso()
        source.created_at = current_time
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR IGNORE INTO knowledge_sources (
                    title, source_type, uri, owner, captured_at, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    source.title,
                    source.source_type,
                    source.uri,
                    source.owner,
                    source.captured_at,
                    json.dumps(source.metadata, ensure_ascii=False, sort_keys=True),
                    source.created_at,
                ),
            )
            if cursor.lastrowid:
                source.source_id = int(cursor.lastrowid)
            else:
                row = connection.execute(
                    "SELECT * FROM knowledge_sources WHERE title = ? AND uri = ?",
                    (source.title, source.uri),
                ).fetchone()
                source = self._source_from_row(dict(row))
            connection.commit()
            self._sync_after_write()
        return source

    def add_item(self, item: KnowledgeItem) -> KnowledgeItem:
        item.created_at = now_iso()
        item.updated_at = item.created_at
        item.confidence = item.confidence if item.confidence in ALLOWED_CONFIDENCE else "medium"
        item.status = item.status if item.status in ALLOWED_STATUS else "active"
        domain = self.ensure_domain(item.category)
        item.domain_id = domain.domain_id
        related_items = ",".join(item.related_items)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO knowledge_items (
                    title, summary, content, category, domain_id, project_scope, source_type,
                    confidence, knowledge_type, status, related_items, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.title,
                    item.summary,
                    item.content,
                    item.category,
                    item.domain_id,
                    item.project_scope,
                    item.source_type,
                    item.confidence,
                    item.knowledge_type,
                    item.status,
                    related_items,
                    item.created_at,
                    item.updated_at,
                ),
            )
            item.item_id = int(cursor.lastrowid)
            self._replace_tags(connection, item.item_id, item.tags)
            connection.commit()
            self._sync_after_write()
        return self.get_item(int(item.item_id)) or item

    def update_item(self, item_id: int, updates: dict[str, Any]) -> KnowledgeItem | None:
        current = self.get_item(item_id)
        if current is None:
            return None

        merged = current.to_dict()
        merged.update({key: value for key, value in updates.items() if value is not None})
        merged["updated_at"] = now_iso()
        merged["confidence"] = merged["confidence"] if merged["confidence"] in ALLOWED_CONFIDENCE else "medium"
        merged["status"] = merged["status"] if merged["status"] in ALLOWED_STATUS else "active"
        tags = normalize_tags(merged.get("tags", []))
        related_items = merged.get("related_items", [])
        domain = self.ensure_domain(str(merged.get("category") or "未分类"))
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE knowledge_items
                SET title = ?, summary = ?, content = ?, category = ?, domain_id = ?, project_scope = ?,
                    source_type = ?, confidence = ?, knowledge_type = ?, status = ?, related_items = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    merged["title"],
                    merged["summary"],
                    merged["content"],
                    merged["category"],
                    domain.domain_id,
                    merged["project_scope"],
                    merged["source_type"],
                    merged["confidence"],
                    merged.get("knowledge_type", "note"),
                    merged.get("status", "active"),
                    ",".join(related_items),
                    merged["updated_at"],
                    item_id,
                ),
            )
            self._replace_tags(connection, item_id, tags)
            connection.commit()
            self._sync_after_write()
        return self.get_item(item_id)

    def add_evidence(self, evidence: KnowledgeEvidence) -> KnowledgeEvidence:
        evidence.confidence = evidence.confidence if evidence.confidence in ALLOWED_CONFIDENCE else "medium"
        evidence.created_at = now_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO knowledge_evidence (
                    item_id, source_id, quote, locator, evidence_type, confidence, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.item_id,
                    evidence.source_id,
                    evidence.quote,
                    evidence.locator,
                    evidence.evidence_type,
                    evidence.confidence,
                    evidence.created_at,
                ),
            )
            evidence.evidence_id = int(cursor.lastrowid)
            connection.commit()
            self._sync_after_write()
        return evidence

    def link_items(self, link: KnowledgeLink) -> KnowledgeLink | None:
        if link.link_type not in ALLOWED_LINK_TYPES:
            return None
        if self.get_item(link.from_item_id) is None or self.get_item(link.to_item_id) is None:
            return None
        link.created_at = now_iso()
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT OR REPLACE INTO knowledge_links (
                    from_item_id, to_item_id, link_type, note, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (link.from_item_id, link.to_item_id, link.link_type, link.note, link.created_at),
            )
            link.link_id = int(cursor.lastrowid)
            connection.commit()
            self._sync_after_write()
        return link

    def get_item(self, item_id: int) -> KnowledgeItem | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if row is None:
                return None
            return self._item_from_row(connection, dict(row))

    def list_items(self) -> list[KnowledgeItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_items ORDER BY updated_at DESC, id DESC"
            ).fetchall()
            return [self._item_from_row(connection, dict(row)) for row in rows]

    def search_rows(self, text: str = "", category: str | None = None, tags: Iterable[str] | None = None) -> list[KnowledgeItem]:
        sql = ["SELECT DISTINCT ki.* FROM knowledge_items ki"]
        conditions: list[str] = []
        params: list[Any] = []

        normalized_tags = normalize_tags(tags or [])
        if normalized_tags:
            sql.append("JOIN item_tags it ON ki.id = it.item_id")
            placeholders = ",".join("?" for _ in normalized_tags)
            conditions.append(f"it.tag IN ({placeholders})")
            params.extend(normalized_tags)

        if text:
            conditions.append("(ki.title LIKE ? OR ki.summary LIKE ? OR ki.content LIKE ?)")
            wildcard = f"%{text}%"
            params.extend([wildcard, wildcard, wildcard])

        if category:
            conditions.append("ki.category = ?")
            params.append(category)

        if conditions:
            sql.append("WHERE " + " AND ".join(conditions))
        sql.append("ORDER BY ki.updated_at DESC, ki.id DESC")

        query = " ".join(sql)
        with self._connect() as connection:
            rows = connection.execute(query, params).fetchall()
            return [self._item_from_row(connection, dict(row)) for row in rows]

    def list_categories(self, categories_file: str | Path) -> list[dict[str, str]]:
        path = Path(categories_file)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        categories = payload.get("categories", [])
        for category in categories:
            self.ensure_domain(str(category.get("name", "")), str(category.get("description", "")))
        return categories

    def lint_knowledge(self) -> dict[str, Any]:
        # 质检逻辑保持直观：先返回明确问题，再给总体统计，方便 QA 人工查看。
        issues: list[dict[str, Any]] = []
        with self._connect() as connection:
            item_rows = connection.execute("SELECT * FROM knowledge_items ORDER BY id ASC").fetchall()
            source_rows = connection.execute("SELECT * FROM knowledge_sources ORDER BY id ASC").fetchall()
            for row in item_rows:
                item = dict(row)
                item_id = int(item["id"])
                evidence_count = self._fetch_evidence_count(connection, item_id)
                if len(str(item.get("title", "")).strip()) < 4:
                    issues.append(self._lint_issue("short_title", item_id, "标题过短，后续检索不够稳定"))
                if len(str(item.get("content", "")).strip()) < 12:
                    issues.append(self._lint_issue("short_content", item_id, "正文过短，缺少可复用结论"))
                if not str(item.get("summary", "")).strip():
                    issues.append(self._lint_issue("missing_summary", item_id, "摘要为空，摘要召回质量会下降"))
                if str(item.get("confidence", "")) not in ALLOWED_CONFIDENCE:
                    issues.append(self._lint_issue("invalid_confidence", item_id, "置信度只能是 low、medium、high"))
                if str(item.get("status", "")) not in ALLOWED_STATUS:
                    issues.append(self._lint_issue("invalid_status", item_id, "状态只能是 draft、active、archived"))
                if evidence_count == 0:
                    issues.append(self._lint_issue("missing_evidence", item_id, "缺少证据片段，建议补充来源"))

            for row in source_rows:
                source = dict(row)
                count = connection.execute(
                    "SELECT COUNT(1) AS count FROM knowledge_evidence WHERE source_id = ?",
                    (source["id"],),
                ).fetchone()["count"]
                if int(count) == 0:
                    issues.append(
                        {
                            "code": "orphan_source",
                            "source_id": int(source["id"]),
                            "message": "来源未关联任何知识卡片",
                            "severity": "warning",
                        }
                    )

        return {
            "summary": {
                "issue_count": len(issues),
                "error_count": sum(1 for issue in issues if issue.get("severity") == "error"),
                "warning_count": sum(1 for issue in issues if issue.get("severity") == "warning"),
            },
            "issues": issues,
        }

    def _lint_issue(self, code: str, item_id: int, message: str) -> dict[str, Any]:
        severity = "error" if code in {"invalid_confidence", "invalid_status"} else "warning"
        return {"code": code, "item_id": item_id, "message": message, "severity": severity}

    def _replace_tags(self, connection: sqlite3.Connection, item_id: int, tags: Iterable[str]) -> None:
        connection.execute("DELETE FROM item_tags WHERE item_id = ?", (item_id,))
        for tag in normalize_tags(tags):
            connection.execute(
                "INSERT OR IGNORE INTO item_tags (item_id, tag) VALUES (?, ?)",
                (item_id, tag),
            )

    def _fetch_tags(self, connection: sqlite3.Connection, item_id: int) -> list[str]:
        rows = connection.execute(
            "SELECT tag FROM item_tags WHERE item_id = ? ORDER BY tag ASC",
            (item_id,),
        ).fetchall()
        return [str(row["tag"]) for row in rows]

    def _fetch_source_titles(self, connection: sqlite3.Connection, item_id: int) -> list[str]:
        rows = connection.execute(
            """
            SELECT DISTINCT ks.title
            FROM knowledge_evidence ke
            JOIN knowledge_sources ks ON ks.id = ke.source_id
            WHERE ke.item_id = ?
            ORDER BY ks.title ASC
            """,
            (item_id,),
        ).fetchall()
        return [str(row["title"]) for row in rows]

    def _fetch_evidence_count(self, connection: sqlite3.Connection, item_id: int) -> int:
        row = connection.execute(
            "SELECT COUNT(1) AS count FROM knowledge_evidence WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        return int(row["count"])

    def _item_from_row(self, connection: sqlite3.Connection, row: dict[str, Any]) -> KnowledgeItem:
        return KnowledgeItem.from_row(
            row,
            tags=self._fetch_tags(connection, int(row["id"])),
            source_titles=self._fetch_source_titles(connection, int(row["id"])),
            evidence_count=self._fetch_evidence_count(connection, int(row["id"])),
        )

    def _source_from_row(self, row: dict[str, Any]) -> KnowledgeSource:
        payload = dict(row)
        metadata_json = payload.pop("metadata_json", "{}") or "{}"
        try:
            payload["metadata"] = json.loads(metadata_json)
        except json.JSONDecodeError:
            payload["metadata"] = {"raw": metadata_json}
        return KnowledgeSource.from_row(payload)
