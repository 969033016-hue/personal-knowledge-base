from __future__ import annotations

from typing import Any, Dict, Optional, Set

import uvicorn
from fastapi import FastAPI

from knowledge_mcp.service import KnowledgeService

from .config import ApiSettings, load_settings
from .lark_bot import LarkBotHandler
from .lark_client import LarkClient
from .model_client import ModelClient
from .models import (
    AddKnowledgeRequest,
    AskKnowledgeRequest,
    IngestSourceRequest,
    LinkKnowledgeRequest,
    SearchKnowledgeRequest,
    UpdateKnowledgeRequest,
)


def create_app(settings: Optional[ApiSettings] = None) -> FastAPI:
    """创建 FastAPI 应用。

    create_app 便于单测传入临时数据库路径；生产或本地启动时直接使用环境变量配置。
    """

    final_settings = settings or load_settings()
    service = KnowledgeService(
        final_settings.db_path,
        final_settings.categories_path,
        sync_adapter=final_settings.build_sync_adapter(),
    )
    model_client = ModelClient(final_settings)
    lark_client = LarkClient(final_settings)
    lark_bot = LarkBotHandler(final_settings, service, lark_client, model_client)

    app = FastAPI(title=final_settings.service_name, version="0.3.0")
    app.state.settings = final_settings
    app.state.service = service
    app.state.model_client = model_client
    app.state.lark_client = lark_client
    app.state.lark_bot = lark_bot

    @app.get("/health")
    def health() -> Dict[str, Any]:
        """服务健康检查，便于部署平台探活。"""

        return {
            "ok": True,
            "service": final_settings.service_name,
            "model_enabled": model_client.is_enabled(),
            "lark_reply_enabled": lark_client.is_enabled(),
            "storage_backend": final_settings.storage_backend,
            "tos_enabled": final_settings.tos_enabled,
        }

    @app.get("/api/categories")
    def list_categories() -> Dict[str, Any]:
        return service.list_categories()

    @app.post("/api/knowledge")
    def add_knowledge(request: AddKnowledgeRequest) -> Dict[str, Any]:
        confirmation = _require_confirmed_write(request.confirm_write, "add_knowledge")
        if confirmation:
            return confirmation
        return service.add_knowledge(
            title=request.title,
            content=request.content,
            summary=request.summary,
            category=request.category,
            tags=request.tags,
            project_scope=request.project_scope,
            source_type=request.source_type,
            confidence=request.confidence,
            knowledge_type=request.knowledge_type,
            status=request.status,
        )

    @app.patch("/api/knowledge/{item_id}")
    def update_knowledge(item_id: int, request: UpdateKnowledgeRequest) -> Dict[str, Any]:
        confirmation = _require_confirmed_write(request.confirm_write, "update_knowledge")
        if confirmation:
            return confirmation
        updates = _model_to_dict(request, exclude={"confirm_write"}, exclude_none=True)
        return service.update_knowledge(item_id, **updates)

    @app.get("/api/knowledge/{item_id}")
    def get_knowledge(item_id: int) -> Dict[str, Any]:
        return service.get_knowledge(item_id)

    @app.post("/api/knowledge/search")
    def search_knowledge(request: SearchKnowledgeRequest) -> Dict[str, Any]:
        return service.search_knowledge(
            query=request.query,
            category=request.category,
            tags=request.tags,
            limit=request.limit,
        )

    @app.post("/api/knowledge/ask")
    def ask_knowledge(request: AskKnowledgeRequest) -> Dict[str, Any]:
        result = service.ask_knowledge(question=request.question, limit=request.limit)
        if request.use_model and model_client.is_enabled():
            result["answer"] = model_client.build_answer(
                question=request.question,
                local_answer=str(result.get("answer", "")),
                items=list(result.get("items", [])),
            )
            result["answer_source"] = "model"
        else:
            result["answer_source"] = "local"
        return result

    @app.post("/api/sources/ingest")
    def ingest_source(request: IngestSourceRequest) -> Dict[str, Any]:
        confirmation = _require_confirmed_write(request.confirm_write, "ingest_source")
        if confirmation:
            return confirmation
        return service.ingest_source(
            title=request.title,
            content=request.content,
            source_type=request.source_type,
            uri=request.uri,
            owner=request.owner,
            category=request.category,
            tags=request.tags,
            project_scope=request.project_scope,
            confidence=request.confidence,
            split_by_paragraph=request.split_by_paragraph,
            metadata=request.metadata,
        )

    @app.get("/api/lint")
    def lint_knowledge() -> Dict[str, Any]:
        return service.lint_knowledge()

    @app.post("/api/links")
    def link_knowledge(request: LinkKnowledgeRequest) -> Dict[str, Any]:
        confirmation = _require_confirmed_write(request.confirm_write, "link_knowledge")
        if confirmation:
            return confirmation
        return service.link_knowledge(
            from_item_id=request.from_item_id,
            to_item_id=request.to_item_id,
            link_type=request.link_type,
            note=request.note,
        )

    @app.post("/api/lark/events")
    def handle_lark_event(payload: Dict[str, Any]) -> Dict[str, Any]:
        return lark_bot.handle_event(payload)

    return app


def _require_confirmed_write(confirm_write: bool, operation: str) -> Optional[Dict[str, Any]]:
    """写操作统一确认门禁。

    返回 None 表示允许继续执行；返回字典表示需要调用方二次确认，本次请求不会写库。
    """

    if confirm_write:
        return None
    return {
        "need_confirm": True,
        "operation": operation,
        "message": "这是写操作。请确认风险后重新请求，并传 confirm_write=true。",
    }


def _model_to_dict(model: Any, exclude: Set[str], exclude_none: bool) -> Dict[str, Any]:
    """兼容 Pydantic v1/v2 的模型转字典方法。"""

    if hasattr(model, "model_dump"):
        return model.model_dump(exclude=exclude, exclude_none=exclude_none)
    return model.dict(exclude=exclude, exclude_none=exclude_none)


app = create_app()


if __name__ == "__main__":
    uvicorn.run("knowledge_mcp.api.app:app", host="0.0.0.0", port=8000, reload=False)
