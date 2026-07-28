from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


PREVIEW_FIELDS = (
    "item_id",
    "title",
    "summary",
    "category",
    "tags",
    "project_scope",
    "source_titles",
    "evidence_count",
    "updated_at",
)

ALLOWED_CONFIDENCE = {"low", "medium", "high"}
ALLOWED_LINK_TYPES = {"related", "depends_on", "duplicates", "conflicts", "supersedes", "supplements"}
ALLOWED_STATUS = {"draft", "active", "archived"}


def now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


@dataclass
class KnowledgeSource:
    """来源层：记录原始材料，保证每条知识都能追溯出处。"""

    title: str
    source_type: str = "manual"
    uri: str = ""
    owner: str = ""
    captured_at: str = field(default_factory=now_iso)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_id: int | None = None
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "KnowledgeSource":
        return cls(
            source_id=row.get("id"),
            title=row.get("title", ""),
            source_type=row.get("source_type", "manual"),
            uri=row.get("uri", ""),
            owner=row.get("owner", ""),
            captured_at=row.get("captured_at", now_iso()),
            metadata=row.get("metadata") or {},
            created_at=row.get("created_at", now_iso()),
        )


@dataclass
class KnowledgeDomain:
    """知识域层：承载分类和后续父子领域扩展。"""

    name: str
    description: str = ""
    parent_id: int | None = None
    domain_id: int | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "KnowledgeDomain":
        return cls(
            domain_id=row.get("id"),
            name=row.get("name", ""),
            description=row.get("description", ""),
            parent_id=row.get("parent_id"),
            created_at=row.get("created_at", now_iso()),
            updated_at=row.get("updated_at", now_iso()),
        )


@dataclass
class KnowledgeEvidence:
    """证据层：记录支撑知识结论的片段、定位和置信度。"""

    item_id: int
    source_id: int
    quote: str
    locator: str = ""
    evidence_type: str = "text"
    confidence: str = "medium"
    evidence_id: int | None = None
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "KnowledgeEvidence":
        return cls(
            evidence_id=row.get("id"),
            item_id=row.get("item_id"),
            source_id=row.get("source_id"),
            quote=row.get("quote", ""),
            locator=row.get("locator", ""),
            evidence_type=row.get("evidence_type", "text"),
            confidence=row.get("confidence", "medium"),
            created_at=row.get("created_at", now_iso()),
        )


@dataclass
class KnowledgeLink:
    """关系层：描述两条知识之间的依赖、补充、冲突等关系。"""

    from_item_id: int
    to_item_id: int
    link_type: str = "related"
    note: str = ""
    link_id: int | None = None
    created_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "KnowledgeLink":
        return cls(
            link_id=row.get("id"),
            from_item_id=row.get("from_item_id"),
            to_item_id=row.get("to_item_id"),
            link_type=row.get("link_type", "related"),
            note=row.get("note", ""),
            created_at=row.get("created_at", now_iso()),
        )


@dataclass
class KnowledgeItem:
    """知识卡片层：面向检索和问答的最小知识单元。"""

    title: str
    content: str
    summary: str = ""
    category: str = "未分类"
    tags: list[str] = field(default_factory=list)
    project_scope: str = "通用"
    source_type: str = "manual"
    confidence: str = "medium"
    related_items: list[str] = field(default_factory=list)
    knowledge_type: str = "note"
    status: str = "active"
    domain_id: int | None = None
    source_titles: list[str] = field(default_factory=list)
    evidence_count: int = 0
    item_id: int | None = None
    created_at: str = field(default_factory=now_iso)
    updated_at: str = field(default_factory=now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_preview_dict(self) -> dict[str, Any]:
        payload = self.to_dict()
        return {field: payload[field] for field in PREVIEW_FIELDS}

    @classmethod
    def from_row(
        cls,
        row: dict[str, Any],
        tags: list[str] | None = None,
        source_titles: list[str] | None = None,
        evidence_count: int = 0,
    ) -> "KnowledgeItem":
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
            knowledge_type=row.get("knowledge_type", "note"),
            status=row.get("status", "active"),
            domain_id=row.get("domain_id"),
            source_titles=source_titles or [],
            evidence_count=evidence_count,
            created_at=row.get("created_at", now_iso()),
            updated_at=row.get("updated_at", now_iso()),
        )
