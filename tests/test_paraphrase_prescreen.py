"""Mechanical pre-screen of LLM-drafted paraphrases before the owner reviews them (0.3, 2.9).

Decision 0008: the owner approves or rejects; this test removes the mechanical defects first.
It reads the case file structurally. Failures name case IDs only, and the checks never look at
gold values to tune anything, so it does not count as held-out use (see eval/contamination.md).

A paraphrase may change wording only. So, against its seed:

P1 the gold answer is identical (same tool call, entities, value);
P2 it is not a duplicate of the seed or of a sibling or of any other case;
P3 every number, year and season in the seed is still there;
P4 it does not copy the seed's wording (long shared word run, near-identical text);
P5 it keeps the seed's season type, scope and rookie/career words, and adds none;
P6 it is a plausible user message (length, no LLM boilerplate);
P7 every proper-noun word in the seed (a player or team name) survives, unless the pair is on
   the reviewed ``ENTITY_REWORDINGS`` list below (nicknames, abbreviations).
"""

import re
from difflib import SequenceMatcher
from pathlib import Path

import duckdb

from app.entities import EntityResolver
from app.verifier import words_to_digits
from eval.schema import Case, CaseType, load
from metrics.rounding import STAT_NAME

CASES = load().cases
BY_ID = {c.id: c for c in CASES}
SEEDS = {c.seed_id: c for c in CASES if c.type == CaseType.seed and c.question}
PARAPHRASES = [c for c in CASES if c.type == CaseType.paraphrase and c.question]

# Reviewed pairs where the proper noun legitimately changes (nickname, abbreviation, surname
# only). Add an id with a note; do not loosen the check.
ENTITY_REWORDINGS: dict[str, str] = {}

# Flags raised by this pre-screen and handed to the owner (decision 0008). Each id stays here
# until the owner approves the wording or it is rewritten; the test fails on any NEW flag and on a
# stale entry whose flag no longer fires, so the list cannot rot.
KNOWN_FLAGS: dict[str, dict[str, str]] = {
    "p4": {
        "Q79-p2": "only 'Who' -> 'Which player'; adds no wording variety",
        "Q37-p2": "held-out: shares a long word run with its seed (owner to review)",
    },
    "p5": {
        "Q40-p2": "drops 'of all time' from the best-record question",
        "Q41-p1": "drops 'history'; 'holds the record' implies all-time (probably fine)",
        "Q41-p2": "drops 'history': reads as season-scoped or career, ambiguous",
    },
    "p7": {
        "Q08-p2": "held-out: a team in the seed is not found in the paraphrase (owner to review)",
    },
}


def check_flags(check: str, flags: dict[str, str]) -> None:
    known = KNOWN_FLAGS.get(check, {})
    new = {k: v for k, v in flags.items() if k not in known}
    stale = sorted(set(known) - set(flags))
    assert not new, f"new {check} flags (fix the paraphrase or hand to the owner): {new}"
    assert not stale, f"{check}: flags no longer fire, remove from KNOWN_FLAGS: {stale}"


STOP = {
    "who", "what", "how", "when", "where", "which", "is", "are", "was", "were", "did", "does",
    "do", "the", "a", "an", "in", "of", "for", "on", "at", "and", "or", "to", "by", "with",
    "this", "last", "next", "his", "her", "their", "has", "have", "had", "can", "will", "nba",
    "i", "me", "my", "show", "tell", "give", "list", "compare", "name", "per", "vs", "versus",
    "regular", "season", "playoffs", "finals", "east", "west", "eastern", "western", "all",
    "conference", "division",
    "star", "mvp", "rookie", "year", "player", "team", "game", "games", "points", "assists",
    "rebounds", "steals", "blocks", "if", "so", "it", "its", "that", "than", "from", "as",
}  # fmt: skip
SCOPE_WORDS = ["playoff", "career", "rookie", "regular season", "play-in", "all-time", "all time"]


def norm(s: str) -> str:
    return (
        re.sub(r"[^a-z0-9 ]+", " ", words_to_digits(s.lower().replace("'s", ""))).split().__str__()
    )


def words(s: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]+", " ", words_to_digits(s.lower().replace("'s", ""))).split()


def longest_shared_run(a: list[str], b: list[str]) -> int:
    m = SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b))
    return m.size


def text(c: Case) -> str:
    assert c.question is not None
    return c.question


def seed_of(p: Case) -> Case:
    return SEEDS[p.seed_id]


def ids(cases: list[Case]) -> list[str]:
    return [c.id for c in cases]


def test_prescreen_covers_every_family() -> None:
    assert PARAPHRASES, "no paraphrases in eval/cases.yaml"
    missing = sorted({p.seed_id for p in PARAPHRASES} - set(SEEDS))
    assert not missing, f"paraphrases whose seed is missing: {missing}"


def test_p1_gold_is_identical_to_the_seed() -> None:
    bad = [p.id for p in PARAPHRASES if p.gold != seed_of(p).gold]
    assert not bad, f"gold differs from the seed (wording only may change): {bad}"


def test_p1_paraphrase_shares_split_critical_and_tags_with_its_seed() -> None:
    bad = [
        p.id
        for p in PARAPHRASES
        if p.split != seed_of(p).split or p.critical != seed_of(p).critical
    ]
    assert not bad, f"split/critical differs from seed (leaks across splits): {bad}"


def test_p2_no_duplicates() -> None:
    """Standalone questions only: a conversation may legitimately open like another one."""
    seen: dict[str, str] = {}
    dupes = []
    for c in CASES:
        if not c.question:
            continue
        key = " ".join(words(c.question))
        if key in seen:
            dupes.append(f"{c.id} == {seen[key]}")
        seen.setdefault(key, c.id)
    assert not dupes, f"duplicate questions: {dupes}"


def test_p3_numbers_years_and_seasons_survive() -> None:
    num = re.compile(r"\d{4}-\d{2}|\d+(?:\.\d+)?")

    def numbers(text: str) -> set[str]:
        t = STAT_NAME.sub(" ", words_to_digits(text))  # "3-pointers" == "threes"
        t = re.sub(r"\b(?:3|three)\s*(?:s|pt|pts)\b", " ", t, flags=re.IGNORECASE)
        return set(num.findall(t)) - {"1"}  # "one game" / "a single game" are idiom, not a count

    bad = []
    for p in PARAPHRASES:
        assert p.question is not None and seed_of(p).question is not None
        want, got = numbers(text(seed_of(p))), numbers(text(p))
        raw_want = set(num.findall(words_to_digits(text(seed_of(p)))))
        if want - got:
            bad.append(f"{p.id} lost {sorted(want - got)}")
        if got - want - raw_want:
            bad.append(f"{p.id} added {sorted(got - want)}")
    assert not bad, bad


def test_p4_does_not_copy_the_seed_wording() -> None:
    flags = {}
    for p in PARAPHRASES:
        assert p.question is not None and seed_of(p).question is not None
        a, b = words(text(seed_of(p))), words(text(p))
        run = longest_shared_run(a, b)
        ratio = SequenceMatcher(None, a, b).ratio()
        if ratio >= 0.9 or run >= max(7, int(0.75 * min(len(a), len(b)))):
            flags[p.id] = f"similarity {ratio:.2f}, shared run {run}"
    check_flags("p4", flags)


def test_p5_scope_words_are_kept_and_not_invented() -> None:
    strict = ["playoff", "rookie", "regular season", "play-in"]
    alltime = ["career", "all-time", "all time", "history", "ever", "of all time"]
    flags: dict[str, str] = {}
    for p in PARAPHRASES:
        assert p.question is not None and seed_of(p).question is not None
        s = text(seed_of(p)).lower().replace("-", " ")
        q = text(p).lower().replace("-", " ")
        for w in strict:
            w = w.replace("-", " ")
            in_s, in_q = bool(re.search(rf"\b{w}", s)), bool(re.search(rf"\b{w}", q))
            if w == "play in":  # "play-in game" only, not "to play in the playoffs"
                in_s, in_q = (
                    "play in game" in s or "play in tournament" in s,
                    ("play in game" in q or "play in tournament" in q),
                )
            if in_s != in_q:
                flags[p.id] = f"'{w}' {'dropped' if in_s else 'added'}"
        if any(w.replace("-", " ") in s for w in alltime) and not any(
            w.replace("-", " ") in q for w in alltime
        ):
            flags[p.id] = "all-time/career scope dropped"
    check_flags("p5", flags)


def test_p6_looks_like_a_user_message() -> None:
    boiler = re.compile(
        r"\b(paraphras|rephras|here is|here's a|sure[,!]|as an ai|variant|version \d|"
        r"original question)\b|^[\"'`*-]|\n",
        re.IGNORECASE,
    )
    bad = []
    for p in PARAPHRASES:
        assert p.question is not None
        n = len(text(p).split())
        if not 3 <= n <= 40 or boiler.search(text(p)) or text(p) != text(p).strip():
            bad.append(p.id)
    assert not bad, bad


def _flat(ids: dict[str, list[int]]) -> set[tuple[str, int]]:
    return {(k, i) for k, v in ids.items() for i in v}


def test_p7_entities_match_the_seed(fixture_db_path: Path) -> None:
    """Resolve names with the app's resolver over the fixture (current players and all teams).

    Wrong entity: the paraphrase resolves to someone the seed does not mean. Lost entity: the
    seed's resolved entity is gone. Names the fixture cannot resolve (retired players) fall back
    to a proper-noun check where a name survives if any word of it does ("LeBron" for "LeBron
    James").
    """
    con = duckdb.connect(str(fixture_db_path), read_only=True)
    resolver = EntityResolver(con)
    flags: dict[str, str] = {}
    for p in PARAPHRASES:
        assert p.question is not None and seed_of(p).question is not None and p.gold
        if p.id in ENTITY_REWORDINGS:
            continue
        seed_ids = _flat(resolver.resolve(text(seed_of(p))).ids())
        para_ids = _flat(resolver.resolve(text(p)).ids())
        gold_ids = _flat(p.gold.entities)
        if para_ids - seed_ids - gold_ids:
            flags[p.id] = f"wrong entity {sorted(para_ids - seed_ids - gold_ids)}"
        if seed_ids - para_ids:
            flags[p.id] = f"lost entity {sorted(seed_ids - para_ids)}"
        if not seed_ids:
            runs = re.findall(
                r"(?<!^)(?<![.?!] )[A-Z][\w'.-]*(?: [A-Z][\w'.-]*)*", text(seed_of(p))
            )
            q = text(p).lower()
            for run in runs:
                toks = [t.lower().rstrip("'s") for t in run.split() if t.lower() not in STOP]
                if toks and not any(t in q for t in toks):
                    flags[p.id] = f"name '{run}' not in paraphrase"
    con.close()
    check_flags("p7", flags)


# --- T-2.9 extension: duplicates, light copying, cross-family leaks -------------------------
NEAR_DUP = 0.9  # a paraphrase this close to a sibling or another family's case is a duplicate
SIBLING_DUP = 0.8  # the two paraphrases of one seed should not be near-copies of each other
LIGHT_COPY = 0.8  # advisory: below P4's 0.9 but still close to the seed wording


def _ratio(a: Case, b: Case) -> float:
    return SequenceMatcher(None, words(text(a)), words(text(b))).ratio()


def p8_flags() -> dict[str, str]:
    """Near-duplicates: sibling paraphrases, or a paraphrase close to another family's case."""
    flags: dict[str, str] = {}
    standalone = [c for c in CASES if c.question]
    for p in PARAPHRASES:
        for o in standalone:
            if o.id == p.id or (o.seed_id == p.seed_id and o.type != CaseType.paraphrase):
                continue
            r = _ratio(p, o)
            limit = SIBLING_DUP if o.seed_id == p.seed_id else NEAR_DUP
            if r >= limit:
                flags[p.id] = f"near-duplicate of {o.id} ({r:.2f})"
    return flags


def p9_flags() -> dict[str, str]:
    """Advisory: paraphrase is 0.80-0.90 similar to its seed (P4 catches >= 0.9)."""
    out: dict[str, str] = {}
    for p in PARAPHRASES:
        r = _ratio(p, seed_of(p))
        if r >= LIGHT_COPY:
            out[p.id] = f"similarity to seed {r:.2f}"
    return out


def test_p8_no_near_duplicates() -> None:
    flags = p8_flags()
    assert not flags, flags


def test_p9_light_copies_are_listed_for_the_owner() -> None:
    """Advisory, not a failure: the owner sees these in eval/reports/paraphrase-prescreen.md."""
    flags = p9_flags()
    assert len(flags) < len(PARAPHRASES) / 4, "over a quarter of paraphrases hug their seed"
