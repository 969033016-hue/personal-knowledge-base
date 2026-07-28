from __future__ import annotations

import argparse
import json

from knowledge_mcp.server import DEFAULT_CATEGORIES_PATH, DEFAULT_DB_PATH
from knowledge_mcp.service import KnowledgeService


SERVICE = KnowledgeService(DEFAULT_DB_PATH, DEFAULT_CATEGORIES_PATH)


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
    add_parser.add_argument("--knowledge-type", default="note")
    add_parser.add_argument("--status", default="active")

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
    update_parser.add_argument("--knowledge-type")
    update_parser.add_argument("--status")

    ingest_parser = subparsers.add_parser("ingest-source")
    ingest_parser.add_argument("--title", required=True)
    ingest_parser.add_argument("--content", required=True)
    ingest_parser.add_argument("--source-type", default="manual")
    ingest_parser.add_argument("--uri", default="")
    ingest_parser.add_argument("--owner", default="")
    ingest_parser.add_argument("--category")
    ingest_parser.add_argument("--tags", nargs="*")
    ingest_parser.add_argument("--project-scope", default="通用")
    ingest_parser.add_argument("--confidence", default="medium")
    ingest_parser.add_argument("--no-split", action="store_true")

    link_parser = subparsers.add_parser("link")
    link_parser.add_argument("--from-item-id", type=int, required=True)
    link_parser.add_argument("--to-item-id", type=int, required=True)
    link_parser.add_argument("--link-type", default="related")
    link_parser.add_argument("--note", default="")

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
    subparsers.add_parser("lint")

    args = parser.parse_args()

    # 这里保留显式分支，便于人工运行脚本时快速确认每个命令实际调用了哪个服务方法。
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
            knowledge_type=args.knowledge_type,
            status=args.status,
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
            knowledge_type=args.knowledge_type,
            status=args.status,
        )
    elif args.command == "ingest-source":
        payload = SERVICE.ingest_source(
            title=args.title,
            content=args.content,
            source_type=args.source_type,
            uri=args.uri,
            owner=args.owner,
            category=args.category,
            tags=args.tags,
            project_scope=args.project_scope,
            confidence=args.confidence,
            split_by_paragraph=not args.no_split,
        )
    elif args.command == "link":
        payload = SERVICE.link_knowledge(
            from_item_id=args.from_item_id,
            to_item_id=args.to_item_id,
            link_type=args.link_type,
            note=args.note,
        )
    elif args.command == "get":
        payload = SERVICE.get_knowledge(args.item_id)
    elif args.command == "search":
        payload = SERVICE.search_knowledge(args.query, category=args.category, tags=args.tags, limit=args.limit)
    elif args.command == "ask":
        payload = SERVICE.ask_knowledge(args.question, limit=args.limit)
    elif args.command == "lint":
        payload = SERVICE.lint_knowledge()
    else:
        payload = SERVICE.list_categories()

    print(json.dumps(payload, ensure_ascii=False, indent=2))
