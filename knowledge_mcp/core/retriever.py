from __future__ import annotations

from .classifier import infer_query_categories
from .schema import KnowledgeItem


class KnowledgeRetriever:
    def rank_items(self, question: str, items: list[KnowledgeItem]) -> list[KnowledgeItem]:
        guessed_categories = infer_query_categories(question)
        scored_items: list[tuple[int, KnowledgeItem]] = []
        for item in items:
            score = 0
            score += question_overlap_score(question, item.title) * 5
            score += question_overlap_score(question, item.summary) * 4
            score += question_overlap_score(question, item.content) * 2
            score += sum(question_overlap_score(question, tag) * 3 for tag in item.tags)
            if item.category in guessed_categories:
                score += 8
            scored_items.append((score, item))

        scored_items.sort(key=lambda pair: (pair[0], pair[1].updated_at), reverse=True)
        return [item for score, item in scored_items if score > 0] or [item for _, item in scored_items]



def question_overlap_score(question: str, text: str) -> int:
    score = 0
    for fragment in split_fragments(question):
        if fragment and fragment in text:
            score += 1
    return score



def split_fragments(text: str) -> list[str]:
    separators = [" ", "，", "。", "、", ",", ".", "？", "?", "：", ":", "；", ";", "\n"]
    fragments = [text]
    for separator in separators:
        next_fragments: list[str] = []
        for fragment in fragments:
            next_fragments.extend(fragment.split(separator))
        fragments = next_fragments
    result = [fragment.strip() for fragment in fragments if len(fragment.strip()) >= 2]
    return list(dict.fromkeys(result))
