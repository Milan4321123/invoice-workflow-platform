"""
Answers regulation questions from the knowledge base, with citations.

Live: the retrieved paragraphs are passed to Claude as documents with
citations enabled, so every statement in the answer points at the passage
it rests on. Offline: the user gets the retrieved paragraphs themselves.
"""
import re
from typing import Any, Dict, List

from services.ai import llm
from services.ai.retrieval import Passage, search

TOP_K = 6

SYSTEM = (
    "You answer questions from the accounts payable team of a German construction company. "
    "Use only the provided documents: German statutes and the company's own procedure documentation. "
    "Cite the passages you rely on and name the paragraph in the text, e.g. (§ 14 Abs. 4 UStG). "
    "If the documents don't answer the question, say so plainly instead "
    "of filling the gap. Answer in the language of the question, briefly. This is information, not tax "
    "advice: for unusual cases, suggest checking with the tax advisor."
)

_ENGLISH = set("""
the is are what does do did how which when why who where an for of with from this that these will would can
invoice invoices discount discounts expire expires soon next week month show list me my our have has must need
should wrong about tell please
""".split())


def is_english(text: str) -> bool:
    words = re.findall(r"[a-z]+", text.lower())
    return sum(w in _ENGLISH for w in words) >= 2


def _passage_dict(p: Passage) -> Dict[str, Any]:
    return {"citation": p.citation, "text": p.text, "source": p.source, "score": p.score}


def ask(question: str) -> Dict[str, Any]:
    passages = search(question, TOP_K)
    if llm.mode() != "live":
        return _offline_answer(question, passages)
    if not passages:
        return {"mode": "live", "answer": _nothing_found(question), "citations": [], "passages": []}

    documents = [{
        "type": "document",
        "source": {"type": "text", "media_type": "text/plain", "data": p.text},
        "title": p.citation,
        "citations": {"enabled": True},
    } for p in passages]
    response = llm.create(
        "rag",
        max_tokens=4000,
        output_config={"effort": "medium"},
        system=SYSTEM,
        messages=[{"role": "user", "content": [*documents, {"type": "text", "text": question}]}],
    )

    answer, citations = [], []
    for block in response.content:
        if block.type != "text":
            continue
        answer.append(block.text)
        for citation in getattr(block, "citations", None) or []:
            passage = passages[citation.document_index]
            citations.append({"citation": passage.citation, "quote": citation.cited_text, "source": passage.source})
    if not citations:
        # Providers without document citations (Gemini): show what the answer was based on
        citations = [{"citation": p.citation, "quote": p.text.split("\n", 1)[-1][:400], "source": p.source}
                     for p in passages[:3]]
    return {"mode": "live", "answer": "".join(answer).strip(), "citations": _unique(citations),
            "passages": [_passage_dict(p) for p in passages]}


def _unique(citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen, unique = set(), []
    for c in citations:
        key = (c["citation"], c["quote"])
        if key not in seen:
            seen.add(key)
            unique.append(c)
    return unique


def _nothing_found(question: str) -> str:
    return ("The knowledge base has nothing on this question." if is_english(question)
            else "Dazu enthält die Wissensbasis nichts.")


def _offline_answer(question: str, passages: List[Passage]) -> Dict[str, Any]:
    if not passages:
        answer = _nothing_found(question)
    elif is_english(question):
        answer = "AI answers are switched off, so here are the most relevant passages: " + ", ".join(
            p.citation for p in passages[:3]) + "."
    else:
        answer = "KI-Antworten sind ausgeschaltet. Die relevantesten Fundstellen: " + ", ".join(
            p.citation for p in passages[:3]) + "."
    return {
        "mode": "offline",
        "answer": answer,
        "citations": [{"citation": p.citation, "quote": p.text.split("\n", 1)[-1][:400], "source": p.source}
                      for p in passages[:3]],
        "passages": [_passage_dict(p) for p in passages],
    }
