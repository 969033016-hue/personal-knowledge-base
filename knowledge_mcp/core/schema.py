from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any


PREVIEW_FIELDS = (
    "item_id",
    "title",
    "summary",
    "category",
    "tags",
    "updated_at",
)


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class KnowledgeItem:
    title: str
    content: str
    summary: str = ""
    category: str = "未分类"
    tags: list[str] = field(default_factory=list)
    project_scope: str = "通用"
    source_type: str = "manual"
    confidence: str = "medium"
    related_items: list[str] = field(default_factory=list)
    item_id: int | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_preview_dict(self) -> dict[str, Any]:
        payload = self.to_dict()
        return {field: payload[field] for field in PREVIEW_FIELDS}

    @classmethod
    def from_row(cls, row: dict[str, Any], tags: list[str] | None = None) -> "KnowledgeItem":
        related_items = row.get("related_items") or ""
        parsed_related_items = [item for item in related_items.split(",") if item]
        return cls(
            item_id=row.get("id"),
            title=row["title"],
            summary=row.get("summary", ""),
            content=row["content"],
            category=row.get("category", "未分类"),
            tags=tags or [],
            project_scope=row.get("project_scope", "通用"),
            source_type=row.get("source_type", "manual"),
            confidence=row.get("confidence", "medium"),
            related_items=parsed_related_items,
            created_at=row.get("created_at", now_iso()),
            updated_at=row.get("updated_at", now_iso()),
        )
