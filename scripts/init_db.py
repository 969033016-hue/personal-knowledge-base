from __future__ import annotations

from knowledge_mcp.server import DEFAULT_CATEGORIES_PATH, DEFAULT_DB_PATH
from knowledge_mcp.service import KnowledgeService


if __name__ == "__main__":
    service = KnowledgeService(DEFAULT_DB_PATH, DEFAULT_CATEGORIES_PATH)
    print(f"database initialized: {service.storage.db_path}")
