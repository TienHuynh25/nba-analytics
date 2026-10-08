"""The stat glossary (task 4.1): one chunk per metric and per qualification rule.

A curated ``metrics/glossary/<id>.md`` is used when it exists (its front matter is dropped);
otherwise the chunk is generated from the registry: label, description, formula, caveats. Chunk
IDs are metric or rule names, so the gold chunk IDs in the eval survive rewrites. PER has a
curated definition only; v1 does not compute it.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.interfaces import Chunk
from metrics.schema import Registry, load

GLOSSARY = Path(__file__).resolve().parent.parent.parent / "metrics" / "glossary"
_FRONT = re.compile(r"^---\n.*?\n---\n", re.DOTALL)


def _curated(cid: str) -> str | None:
    p = GLOSSARY / f"{cid}.md"
    return _FRONT.sub("", p.read_text()).strip() if p.exists() else None


def glossary_chunks(reg: Registry | None = None) -> list[Chunk]:
    reg = reg or load()
    out = []
    for m in reg.metrics:
        text = _curated(m.name) or (
            f"# {m.label}\n\n{m.description}\n\n**Formula:** {m.formula}"
            + (f"\n\n**Caveats:** {m.caveats}" if m.caveats else "")
        )
        out.append(Chunk(m.name, text, "glossary"))
    for q in reg.qualifications:
        out.append(
            Chunk(
                q.name,
                _curated(q.name) or f"# Qualification: {q.name}\n\n{q.description}",
                "glossary",
            )
        )
    known = {c.id for c in out}
    for p in sorted(GLOSSARY.glob("*.md")):
        if p.stem not in known:  # curated-only entries such as PER
            out.append(Chunk(p.stem, _curated(p.stem) or "", "glossary"))
    return out
