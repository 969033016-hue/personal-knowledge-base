from __future__ import annotations

from typing import Iterable

from .schema import KnowledgeItem


def _join_tags(tags: Iterable[str]) -> str:
    return "、".join(tag for tag in tags if tag)


def build_answer(question: str, items: list[KnowledgeItem]) -> str:
    if not items:
        return (
            f"问题：{question}\n\n"
            "当前知识库里还没有检索到足够相关的内容。\n"
            "建议补充这个主题的背景、现象、排查路径或结论后再查询。"
        )

    lines: list[str] = [f"问题：{question}", "", "结论："]
    top_item = items[0]
    lines.append(f"- 最相关的知识来自《{top_item.title}》，主分类为“{top_item.category}”。")
    if top_item.summary:
        lines.append(f"- 核心摘要：{top_item.summary}")

    lines.extend(["", "依据："])
    for index, item in enumerate(items[:3], start=1):
        lines.append(
            f"{index}. 《{item.title}》 | 分类：{item.category} | 标签：{_join_tags(item.tags) or '无'}"
        )
        content_preview = item.content.strip().replace("\n", " ")
        if len(content_preview) > 120:
            content_preview = content_preview[:119] + "…"
        lines.append(f"   - 内容要点：{content_preview}")

    lines.extend(["", "建议下一步："])
    lines.append("- 如果这是排障问题，优先对照最相关知识中的关键条件逐项核对。")
    lines.append("- 如果这是新项目接手问题，可以继续追问“项目背景、核心链路、测试重点、常见故障”四个方向。")
    return "\n".join(lines)
