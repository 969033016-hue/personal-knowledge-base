from __future__ import annotations

from pathlib import Path
from typing import Any

from .core.answerer import build_answer
from .core.classifier import classify_text, extract_tags, infer_query_categories, normalize_tags, summarize_content
from .core.retriever import KnowledgeRetriever
from .core.schema import KnowledgeEvidence, KnowledgeItem, KnowledgeLink, KnowledgeSource
from .core.storage import DatabaseSyncAdapter, KnowledgeStorage


class KnowledgeService:
    def __init__(self, db_path: str | Path, categories_path: str | Path, sync_adapter: DatabaseSyncAdapter | None = None):
        # sync_adapter 只负责数据库文件同步，业务层仍然通过 KnowledgeStorage 读写知识卡片。
        # 在本地开发场景传 None 即可；函数计算场景会传入 TOS 同步适配器。
        self.storage = KnowledgeStorage(db_path, sync_adapter=sync_adapter)
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
        knowledge_type: str = "note",
        status: str = "active",
    ) -> dict[str, Any]:
        # 写入时仍保持 V1 的低成本体验：用户只给标题和正文，也能自动补摘要、分类和标签。
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
            knowledge_type=knowledge_type,
            status=status,
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

    def ingest_source(
        self,
        title: str,
        content: str,
        source_type: str = "manual",
        uri: str = "",
        owner: str = "",
        category: str | None = None,
        tags: list[str] | None = None,
        project_scope: str = "通用",
        confidence: str = "medium",
        split_by_paragraph: bool = True,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        # 来源导入分两步：先落来源记录，再把可复用片段转成知识卡片并补证据。
        source = self.storage.add_source(
            KnowledgeSource(
                title=title,
                source_type=source_type,
                uri=uri,
                owner=owner,
                metadata=metadata or {},
            )
        )
        chunks = self._split_source_content(content, split_by_paragraph=split_by_paragraph)
        created_items: list[dict[str, Any]] = []
        for index, chunk in enumerate(chunks, start=1):
            item_title = title if len(chunks) == 1 else f"{title} - 片段{index}"
            final_category = category or classify_text(item_title, chunk)
            final_tags = normalize_tags(tags or extract_tags(item_title, chunk))
            saved = self.storage.add_item(
                KnowledgeItem(
                    title=item_title,
                    content=chunk,
                    summary=summarize_content(chunk),
                    category=final_category,
                    tags=final_tags,
                    project_scope=project_scope,
                    source_type=source_type,
                    confidence=confidence,
                    knowledge_type="source_note",
                )
            )
            evidence = self.storage.add_evidence(
                KnowledgeEvidence(
                    item_id=int(saved.item_id),
                    source_id=int(source.source_id),
                    quote=chunk[:500],
                    locator=f"paragraph:{index}",
                    confidence=confidence,
                )
            )
            item_payload = saved.to_dict()
            item_payload["evidence"] = evidence.to_dict()
            created_items.append(item_payload)
        return {"source": source.to_dict(), "items": created_items}

    def link_knowledge(
        self,
        from_item_id: int,
        to_item_id: int,
        link_type: str = "related",
        note: str = "",
    ) -> dict[str, Any]:
        if from_item_id == to_item_id:
            return {"error": "from_item_id and to_item_id must be different"}
        link = self.storage.link_items(
            KnowledgeLink(
                from_item_id=from_item_id,
                to_item_id=to_item_id,
                link_type=link_type,
                note=note,
            )
        )
        if link is None:
            return {"error": "link failed, please check item ids or link_type"}
        return {"link": link.to_dict()}

    def lint_knowledge(self) -> dict[str, Any]:
        return self.storage.lint_knowledge()

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
            "items": [item.to_preview_dict() for item in ranked],
        }

    def ask_knowledge(self, question: str, limit: int = 3) -> dict[str, Any]:
        items = self.storage.search_rows(text="")
        ranked = self.retriever.rank_items(question, items)[:limit]
        return {
            "guessed_categories": infer_query_categories(question),
            "answer": build_answer(question, ranked),
            "items": [item.to_preview_dict() for item in ranked],
        }

    def list_categories(self) -> dict[str, Any]:
        return {"categories": self.storage.list_categories(self.categories_path)}

    def _split_source_content(self, content: str, split_by_paragraph: bool) -> list[str]:
        cleaned = content.strip()
        if not cleaned:
            return []
        if not split_by_paragraph:
            return [cleaned]
        chunks = [chunk.strip() for chunk in cleaned.split("\n\n") if chunk.strip()]
        return chunks or [cleaned]
