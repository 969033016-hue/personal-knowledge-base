from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Iterable

from .classifier import normalize_tags
from .schema import KnowledgeItem, now_iso


class KnowledgeStorage:
    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS knowledge_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    content TEXT NOT NULL,
                    category TEXT NOT NULL,
                    project_scope TEXT NOT NULL,
                    source_type TEXT NOT NULL,
                    confidence TEXT NOT NULL,
                    related_items TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS item_tags (
                    item_id INTEGER NOT NULL,
                    tag TEXT NOT NULL,
                    UNIQUE(item_id, tag),
                    FOREIGN KEY(item_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
                );
                """
            )
            connection.commit()

    def add_item(self, item: KnowledgeItem) -> KnowledgeItem:
        item.created_at = now_iso()
        item.updated_at = item.created_at
        related_items = ",".join(item.related_items)
        with self._connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO knowledge_items (
                    title, summary, content, category, project_scope, source_type,
                    confidence, related_items, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.title,
                    item.summary,
                    item.content,
                    item.category,
                    item.project_scope,
                    item.source_type,
                    item.confidence,
                    related_items,
                    item.created_at,
                    item.updated_at,
                ),
            )
            item.item_id = int(cursor.lastrowid)
            self._replace_tags(connection, item.item_id, item.tags)
            connection.commit()
        return item

    def update_item(self, item_id: int, updates: dict[str, Any]) -> KnowledgeItem | None:
        current = self.get_item(item_id)
        if current is None:
            return None

        merged = current.to_dict()
        merged.update({key: value for key, value in updates.items() if value is not None})
        merged["updated_at"] = now_iso()
        tags = normalize_tags(merged.get("tags", []))
        related_items = merged.get("related_items", [])
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE knowledge_items
                SET title = ?, summary = ?, content = ?, category = ?, project_scope = ?,
                    source_type = ?, confidence = ?, related_items = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    merged["title"],
                    merged["summary"],
                    merged["content"],
                    merged["category"],
                    merged["project_scope"],
                    merged["source_type"],
                    merged["confidence"],
                    ",".join(related_items),
                    merged["updated_at"],
                    item_id,
                ),
            )
            self._replace_tags(connection, item_id, tags)
            connection.commit()
        return self.get_item(item_id)

    def get_item(self, item_id: int) -> KnowledgeItem | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM knowledge_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if row is None:
                return None
            tags = self._fetch_tags(connection, item_id)
            return KnowledgeItem.from_row(dict(row), tags=tags)

    def list_items(self) -> list[KnowledgeItem]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM knowledge_items ORDER BY updated_at DESC, id DESC"
            ).fetchall()
            return [
                KnowledgeItem.from_row(dict(row), tags=self._fetch_tags(connection, int(row["id"])))
                for row in rows
            ]

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
            return [
                KnowledgeItem.from_row(dict(row), tags=self._fetch_tags(connection, int(row["id"])))
                for row in rows
            ]

    def list_categories(self, categories_file: str | Path) -> list[dict[str, str]]:
        import json

        path = Path(categories_file)
        if not path.exists():
            return []
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload.get("categories", [])

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
