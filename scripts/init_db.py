from __future__ import annotations

from pathlib import Path

from knowledge_mcp.server import DEFAULT_CATEGORIES_PATH, DEFAULT_DB_PATH
from knowledge_mcp.service import KnowledgeService


if __name__ == "__main__":
    root = Path(__file__).resolve().parent.parent
    service = KnowledgeService(root / DEFAULT_DB_PATH.relative_to(root), root / DEFAULT_CATEGORIES_PATH.relative_to(root))
    print(f"database initialized: {service.storage.db_path}")
