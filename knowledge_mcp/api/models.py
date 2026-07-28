from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ConfirmedWriteRequest(BaseModel):
    """写操作基础请求。

    confirm_write 是阶段二的服务端安全阀。所有会改变 SQLite 数据的 REST 接口都必须显式传 true，
    否则接口只返回确认提示，不执行真实写入。
    """

    confirm_write: bool = Field(default=False, description="是否确认执行写操作")


class AddKnowledgeRequest(ConfirmedWriteRequest):
    title: str
    content: str
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    project_scope: str = "通用"
    source_type: str = "manual"
    confidence: str = "medium"
    knowledge_type: str = "note"
    status: str = "active"


class UpdateKnowledgeRequest(ConfirmedWriteRequest):
    title: Optional[str] = None
    content: Optional[str] = None
    summary: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    project_scope: Optional[str] = None
    source_type: Optional[str] = None
    confidence: Optional[str] = None
    knowledge_type: Optional[str] = None
    status: Optional[str] = None


class SearchKnowledgeRequest(BaseModel):
    query: str = ""
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    limit: int = 5


class AskKnowledgeRequest(BaseModel):
    question: str
    limit: int = 3
    use_model: bool = True


class IngestSourceRequest(ConfirmedWriteRequest):
    title: str
    content: str
    source_type: str = "manual"
    uri: str = ""
    owner: str = ""
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    project_scope: str = "通用"
    confidence: str = "medium"
    split_by_paragraph: bool = True
    metadata: Optional[Dict[str, Any]] = None


class LinkKnowledgeRequest(ConfirmedWriteRequest):
    from_item_id: int
    to_item_id: int
    link_type: str = "related"
    note: str = ""


class LarkEventRequest(BaseModel):
    """飞书事件回调原始载荷。

    飞书不同版本事件结构差异较大，因此这里先保留宽松字典，由 lark_bot 模块做兼容解析。
    """

    payload: Dict[str, Any]
