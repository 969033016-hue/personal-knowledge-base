from __future__ import annotations

import re
from collections import Counter
from typing import Iterable

DEFAULT_CATEGORY = "项目知识"

CATEGORY_RULES: dict[str, list[str]] = {
    "业务知识": ["业务", "策略", "导量", "激励", "拉新", "拉活", "发奖", "金币", "现金", "用户增长"],
    "项目知识": ["项目", "需求", "接口", "实验", "上下游", "链路", "配置", "交付", "模块"],
    "测试方法": ["测试", "用例", "覆盖", "边界", "校验", "幂等", "并发", "频控", "回归"],
    "排障案例": ["故障", "异常", "报错", "排查", "根因", "日志", "空结果", "修复", "失败"],
    "平台工具": ["平台", "工具", "命中查询", "日志平台", "mock", "脚本", "控制台", "看板"],
    "规范流程": ["流程", "上线", "评审", "联调", "灰度", "规范", "准入", "发布"],
    "仓库代码知识": ["仓库", "代码", "函数", "模块", "目录", "脚本", "入口", "分支", "提交"],
}

STOP_WORDS = {
    "我们", "你们", "这个", "那个", "以及", "因为", "所以", "如果", "需要", "可以",
    "进行", "一个", "一些", "没有", "什么", "怎么", "如何", "然后", "就是", "优先",
}

TAG_KEYWORDS = [
    "导量", "激励", "拉新", "拉活", "发奖", "实验", "频控", "幂等", "并发", "日志", "mock",
    "接口", "配置", "规则", "命中", "排查", "空结果", "上线", "联调", "仓库", "脚本",
]


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def summarize_content(content: str, max_length: int = 80) -> str:
    normalized = _normalize_text(content)
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1] + "…"


def classify_text(title: str, content: str) -> str:
    text = f"{title} {content}"
    scores: dict[str, int] = {category: 0 for category in CATEGORY_RULES}
    for category, keywords in CATEGORY_RULES.items():
        for keyword in keywords:
            scores[category] += text.count(keyword)
    best_category = max(scores, key=scores.get)
    if scores[best_category] == 0:
        return DEFAULT_CATEGORY
    return best_category


def infer_query_categories(question: str) -> list[str]:
    matched: list[tuple[str, int]] = []
    for category, keywords in CATEGORY_RULES.items():
        score = sum(question.count(keyword) for keyword in keywords)
        if score > 0:
            matched.append((category, score))
    matched.sort(key=lambda item: item[1], reverse=True)
    return [category for category, _ in matched[:3]]


def extract_tags(title: str, content: str, limit: int = 8) -> list[str]:
    text = f"{title} {content}"
    tags: list[str] = []
    for keyword in TAG_KEYWORDS:
        if keyword in text and keyword not in tags:
            tags.append(keyword)

    english_tokens = re.findall(r"[A-Za-z][A-Za-z0-9_\-]{2,}", text)
    counter = Counter(
        token
        for token in english_tokens
        if token.lower() not in STOP_WORDS and not token.isdigit()
    )
    for token, _ in counter.most_common(limit * 2):
        if token not in tags:
            tags.append(token)
        if len(tags) >= limit:
            break
    return tags[:limit]


def normalize_tags(tags: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for tag in tags:
        clean_tag = _normalize_text(str(tag))
        if not clean_tag:
            continue
        if clean_tag not in seen:
            seen.add(clean_tag)
            normalized.append(clean_tag)
    return normalized
