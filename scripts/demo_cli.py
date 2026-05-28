from __future__ import annotations

import argparse
import json
from pathlib import Path

from knowledge_mcp.server import DEFAULT_CATEGORIES_PATH, DEFAULT_DB_PATH
from knowledge_mcp.service import KnowledgeService


ROOT_DIR = Path(__file__).resolve().parent.parent
SERVICE = KnowledgeService(ROOT_DIR / DEFAULT_DB_PATH.relative_to(ROOT_DIR), ROOT_DIR / DEFAULT_CATEGORIES_PATH.relative_to(ROOT_DIR))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Knowledge base demo CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add_parser = subparsers.add_parser("add")
    add_parser.add_argument("--title", required=True)
    add_parser.add_argument("--content", required=True)
    add_parser.add_argument("--summary")
    add_parser.add_argument("--category")
    add_parser.add_argument("--tags", nargs="*")
    add_parser.add_argument("--project-scope", default="通用")
    add_parser.add_argument("--source-type", default="manual")
    add_parser.add_argument("--confidence", default="medium")

    update_parser = subparsers.add_parser("update")
    update_parser.add_argument("--item-id", type=int, required=True)
    update_parser.add_argument("--title")
    update_parser.add_argument("--content")
    update_parser.add_argument("--summary")
    update_parser.add_argument("--category")
    update_parser.add_argument("--tags", nargs="*")
    update_parser.add_argument("--project-scope")
    update_parser.add_argument("--source-type")
    update_parser.add_argument("--confidence")

    get_parser = subparsers.add_parser("get")
    get_parser.add_argument("--item-id", type=int, required=True)

    search_parser = subparsers.add_parser("search")
    search_parser.add_argument("--query", required=True)
    search_parser.add_argument("--category")
    search_parser.add_argument("--tags", nargs="*")
    search_parser.add_argument("--limit", type=int, default=5)

    ask_parser = subparsers.add_parser("ask")
    ask_parser.add_argument("--question", required=True)
    ask_parser.add_argument("--limit", type=int, default=3)

    subparsers.add_parser("categories")

    args = parser.parse_args()

    if args.command == "add":
        payload = SERVICE.add_knowledge(
            title=args.title,
            content=args.content,
            summary=args.summary,
            category=args.category,
            tags=args.tags,
            project_scope=args.project_scope,
            source_type=args.source_type,
            confidence=args.confidence,
        )
    elif args.command == "update":
        payload = SERVICE.update_knowledge(
            args.item_id,
            title=args.title,
            content=args.content,
            summary=args.summary,
            category=args.category,
            tags=args.tags,
            project_scope=args.project_scope,
            source_type=args.source_type,
            confidence=args.confidence,
        )
    elif args.command == "get":
        payload = SERVICE.get_knowledge(args.item_id)
    elif args.command == "search":
        payload = SERVICE.search_knowledge(args.query, category=args.category, tags=args.tags, limit=args.limit)
    elif args.command == "ask":
        payload = SERVICE.ask_knowledge(args.question, limit=args.limit)
    else:
        payload = SERVICE.list_categories()

    print(json.dumps(payload, ensure_ascii=False, indent=2))
