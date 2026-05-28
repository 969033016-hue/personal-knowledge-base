from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.answerer import build_answer
from .core.classifier import classify_text, extract_tags, infer_query_categories, normalize_tags, summarize_content
from .core.retriever import KnowledgeRetriever
from .core.schema import KnowledgeItem
from .core.storage import KnowledgeStorage


class KnowledgeService:
    def __init__(self, db_path: str | Path, categories_path: str | Path):
        self.storage = KnowledgeStorage(db_path)
        self.categories_path = Path(categories_path)
        self.retriever = KnowledgeRetriever()
        self.storage.initialize()

    def add_knowledge(
        self,
        title: str,
        content: str,
        summary: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        project_scope: str = "通用",
        source_type: str = "manual",
        confidence: str = "medium",
    ) -> dict[str, Any]:
        final_summary = summary or summarize_content(content)
        final_category = category or classify_text(title, content)
        final_tags = normalize_tags(tags or extract_tags(title, content))
        item = KnowledgeItem(
            title=title,
            content=content,
            summary=final_summary,
            category=final_category,
            tags=final_tags,
            project_scope=project_scope,
            source_type=source_type,
            confidence=confidence,
        )
        saved_item = self.storage.add_item(item)
        return {"item": saved_item.to_dict()}

    def update_knowledge(self, item_id: int, **updates: Any) -> dict[str, Any]:
        if updates.get("content") and not updates.get("summary"):
            updates["summary"] = summarize_content(str(updates["content"]))
        if updates.get("title") or updates.get("content"):
            title = str(updates.get("title") or "")
            content = str(updates.get("content") or "")
            if title or content:
                updates["category"] = updates.get("category") or classify_text(title, content)
                merged_tags = list(updates.get("tags") or [])
                merged_tags.extend(extract_tags(title, content))
                updates["tags"] = normalize_tags(merged_tags)
        updated = self.storage.update_item(item_id, updates)
        if updated is None:
            return {"error": f"knowledge item {item_id} not found"}
        return {"item": updated.to_dict()}

    def get_knowledge(self, item_id: int) -> dict[str, Any]:
        item = self.storage.get_item(item_id)
        if item is None:
            return {"error": f"knowledge item {item_id} not found"}
        return {"item": item.to_dict()}

    def search_knowledge(self, query: str, category: str | None = None, tags: list[str] | None = None, limit: int = 5) -> dict[str, Any]:
        items = self.storage.search_rows(text=query, category=category, tags=tags)
        ranked = self.retriever.rank_items(query, items)[:limit]
        return {
            "guessed_categories": infer_query_categories(query),
            "items": [item.to_dict() for item in ranked],
        }

    def ask_knowledge(self, question: str, limit: int = 3) -> dict[str, Any]:
        items = self.storage.search_rows(text="")
        ranked = self.retriever.rank_items(question, items)[:limit]
        return {
            "guessed_categories": infer_query_categories(question),
            "answer": build_answer(question, ranked),
            "items": [item.to_dict() for item in ranked],
        }

    def list_categories(self) -> dict[str, Any]:
        return {"categories": self.storage.list_categories(self.categories_path)}
