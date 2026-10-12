"""Knowledge answers with citations (task 4.5).

Retrieve glossary chunks, then the model answers citing chunk IDs in brackets
("[true_shooting_pct]"). The only numbers it may state are ones written in a chunk it cited;
the verifier checks that, regenerates once, then falls back to quoting the top chunk. RAG
never computes a stat.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.interfaces import Chunk, LLMClient, Message, Retriever
from app.verifier import Evidence, check

K = 6
_CITE = re.compile(r"\[([a-z0-9_]+)\]")

SYSTEM = """You explain NBA stats and rules using ONLY the passages given.
Cite the passages you use by their id in square brackets, like [true_shooting_pct].
Any number you write (a formula constant, a minimum) must appear in a passage you cite.
Answer in two to four plain sentences."""


@dataclass
class KnowledgeAnswer:
    text: str
    chunks: list[str]  # retrieved, ranked
    cited: list[str] = field(default_factory=list)
    status: str = ""


class KnowledgePath:
    def __init__(self, llm: LLMClient, retriever: Retriever) -> None:
        self.llm = llm
        self.retriever = retriever

    def answer(self, question: str) -> KnowledgeAnswer:
        hits = self.retriever.search(question, K)
        by_id = {c.id: c for c in hits}
        passages = "\n\n".join(f"[{c.id}]\n{c.text}" for c in hits)
        drafts: list[str] = []

        def generate(feedback: list[str] | None) -> str:
            msgs = [
                Message("system", SYSTEM),
                Message("user", f"Passages:\n{passages}\n\nQuestion: {question}"),
            ]
            if feedback:
                msgs.append(
                    Message(
                        "user",
                        "These numbers are not in the passages you cited: "
                        + ", ".join(feedback)
                        + ". Rewrite.",
                    )
                )
            drafts.append(self.llm.complete(msgs).strip())
            return drafts[-1]

        def cited_evidence(text: str) -> Evidence:
            cited = [by_id[i] for i in _CITE.findall(text) if i in by_id]
            return Evidence(chunks=[c.text for c in cited])

        # The evidence depends on which chunks a draft cites, so each draft is checked against
        # its own citations (citation brackets themselves are not numbers to check).
        first = generate(None)
        c1 = check(_CITE.sub("", first), cited_evidence(first))
        if c1.ok:
            text, status = first, "verified"
        else:
            second = generate(c1.unmatched)
            if check(_CITE.sub("", second), cited_evidence(second)).ok:
                text, status = second, "regenerated"
            else:
                top: Chunk | None = hits[0] if hits else None
                text = (
                    f"From the glossary [{top.id}]:\n{top.text}"
                    if top
                    else "I don't have a definition for that."
                )
                status = "fallback"
        cited = [i for i in dict.fromkeys(_CITE.findall(text)) if i in by_id]
        return KnowledgeAnswer(text, [c.id for c in hits], cited, status)
