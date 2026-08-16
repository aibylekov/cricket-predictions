"""
generate_article.py - Phase 3, final step: CONTENT GENERATOR.

payload dict (from build_payload) + prompt template -> TopBookies-format
article draft (Markdown), saved to data/articles/<match_id>_draft.md
(data/articles/ is gitignored - drafts are working output, not code).

Generation calls the OpenAI API. The API key comes from .env as
OPENAI_API_KEY (never hardcoded; in CI it will come from GitHub Actions
Secrets). Model and temperature are CONFIG values at the top:
    MODEL       - "gpt-4o" for now; "gpt-4o-mini" to be cost-tested later.
    TEMPERATURE - 0.7: the human-writing style rules (burstiness, varied
                  openers, fragments) need sampling room to vary rhythm;
                  low temperatures collapse into the uniform cadence the
                  ruleset exists to break. Facts are safe regardless -
                  numbers come from the payload and are validated below.

ANTI-HALLUCINATION VALIDATOR (mechanical, post-generation):
    Every number in the generated article must appear in - or be derivable
    by simple rounding from - the payload. Derivations accepted per payload
    value v: v itself; round(v, 0/1/2); |v| and its roundings (margins are
    written as positive "runs"); and for v in [0,1] the percentage forms
    round(100v, 0/1). Date components (year, month, day) of payload dates
    are allowed. WIN-RECORD COUNTS (iteration 1): the house rule "won 4 of
    their last 5" requires the win count round(win_pct * matches_in_window)
    and its complement (losses) per side and window - both are added to the
    allowed set. A minimal cricket-structural whitelist {20} covers
    "T20"/"20 overs" (documented here; nothing else is whitelisted).
    Any number that fails -> VIOLATION.

STYLE VALIDATOR (mechanical, post-generation):
    Zero em dashes (the ruleset's zero-tolerance tell), zero banned
    connectors (Part E list) and zero house-banned terms (iteration-1
    editorial list, incl. a "model mention" guard for the no-probability
    rule) - both lists imported from prompt_template so prompt and check
    never drift apart. Case-insensitive, word-bounded, inflection families
    covered for house terms. Any hit -> VIOLATION, reported alongside the
    number violations.

GENERATION MODE (toss lifecycle): MODE config below, "post_toss" (default;
    completed matches, toss reported) or "pre_toss" (preview article, toss
    result never mentioned, section argues captains' likely choices from
    venue stats). Passed through to build_user_prompt.

REGENERATE-ON-FAILURE RETRY LOOP:
    If either check fails, the model is re-prompted IN the same
    conversation (its failing draft as an assistant turn) with the
    specific violations listed and the instruction to fix ONLY those,
    changing nothing else. Max MAX_RETRIES (2) repair rounds, i.e. at
    most 3 API calls per article. Still failing after that -> the draft
    is stamped "FAILED VALIDATION" in its header comment and in the
    console report, and generation stops for that match.

DEMO:
    venv/Scripts/python.exe -m src.content.generate_article
generates drafts for the three payload-demo matches (confident England,
moderate MLC, close_call IPL) in BOTH toss modes (6 drafts, saved as
<match_id>_<mode>_draft.md), validates each, prints drafts + results.
In pre_toss mode the toss result is mechanically stripped from the
payload before the model sees it (_lifecycle_view), so a leak is
impossible rather than merely instructed against.
Stops with clear instructions if OPENAI_API_KEY is missing.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from src.content.payload import build_payload
from src.content.prompt_template import (
    BANNED_CONNECTORS,
    BANNED_HOUSE_TERMS,
    BANNED_WORDS,
    SYSTEM_PROMPT,
    build_user_prompt,
)

ROOT = Path(__file__).resolve().parents[2]
ARTICLES_DIR = ROOT / "data" / "articles"

# ---- generation config ---------------------------------------------------
MODEL = "gpt-4o"          # candidate for later cost test: "gpt-4o-mini"
TEMPERATURE = 0.7         # rationale in the module docstring (style rhythm)
MAX_TOKENS = 2500
MAX_RETRIES = 2           # repair rounds after a failed validation
MODE = "post_toss"        # toss lifecycle: "post_toss" | "pre_toss"

# The SAME three matches as the payload demo (band verified at runtime).
DEMO_MATCHES = [
    ("confident", 8731),    # England v India, Rose Bowl 2026 (p_home 0.77)
    ("moderate", 8250),     # Washington Freedom v MI New York, MLC 2026
    ("close_call", 8032),   # RCB v Gujarat Titans, IPL 2026 (the IPL case)
]

# Cricket-structural numbers allowed without payload support (T20, 20 overs).
STRUCTURAL_WHITELIST = {20.0}


# --------------------------------------------------------------------------
# anti-hallucination validator (numbers)
# --------------------------------------------------------------------------
def _numeric_leaves(obj) -> list[float]:
    """All numeric leaf values in a nested payload dict/list."""
    out = []
    if isinstance(obj, dict):
        for v in obj.values():
            out.extend(_numeric_leaves(v))
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out.extend(_numeric_leaves(v))
    elif isinstance(obj, bool):
        pass                                   # bools are not article numbers
    elif isinstance(obj, (int, float)):
        out.append(float(obj))
    elif isinstance(obj, str):
        # date strings ("2026-07-11") and timestamps: allow their components
        for part in re.findall(r"\d+(?:\.\d+)?", obj):
            out.append(float(part))
    return out


def _win_count_derivations(payload: dict) -> set[float]:
    """Win/loss counts implied by win_pct x matches_in_window, per side and
    window - the house phrasing "won 4 of their last 5" needs the 4."""
    out: set[float] = set()
    form = payload.get("form") or {}
    for side in ("home", "away"):
        s = form.get(side) or {}
        pct = s.get("win_pct") or {}
        win = s.get("matches_in_window") or {}
        for window in ("last5", "tournament", "current_event"):
            p, n = pct.get(window), win.get(window)
            if p is not None and n:
                wins = round(p * n)
                out.add(float(wins))
                out.add(float(n - wins))
    return out


def _venue_count_derivations(payload: dict) -> set[float]:
    """If the article renders a venue split as a count ("won 35 of the 59
    matches here"), the implied count round(pct * matches_sample) must be
    an allowed number."""
    out: set[float] = set()
    vs = payload.get("venue_stats") or {}
    n = vs.get("matches_at_venue_total")
    if n:
        for key in ("batfirst_win_pct", "chase_win_pct"):
            p = vs.get(key)
            if p is not None:
                wins = round(p * n)
                out.add(float(wins))
                out.add(float(n - wins))
    return out


def allowed_numbers(payload: dict) -> set[float]:
    allowed = (set(STRUCTURAL_WHITELIST) | _win_count_derivations(payload)
               | _venue_count_derivations(payload))
    for v in _numeric_leaves(payload):
        for base in (v, abs(v)):
            allowed.add(base)
            allowed.add(round(base))
            allowed.add(round(base, 1))
            allowed.add(round(base, 2))
            if 0.0 <= base <= 1.0:
                allowed.add(round(base * 100))
                allowed.add(round(base * 100, 1))
    return allowed


def extract_numbers(text: str) -> list[str]:
    """Numbers as they appear in the article (dedup preserves order)."""
    seen, out = set(), []
    for m in re.findall(r"\d+(?:\.\d+)?", text):
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out


def validate_article(article: str, payload: dict) -> dict:
    allowed = allowed_numbers(payload)
    violations = []
    for tok in extract_numbers(article):
        val = float(tok)
        if not any(abs(val - a) < 1e-9 for a in allowed):
            violations.append(tok)
    return {"passed": not violations, "violations": violations,
            "numbers_checked": len(extract_numbers(article))}


# --------------------------------------------------------------------------
# style validator (em dashes + full Part E + house terms + pct-with-count)
# --------------------------------------------------------------------------
_PCT_RE = re.compile(r"\d+(?:\.\d+)?\s*%")
_WINNISH_RE = re.compile(r"\b(?:win|wins|winning|won|victor\w*|chas\w+|"
                         r"success\w*)\b", re.IGNORECASE)
# a match count in the same sentence: "35 of 69" or "... 58 matches/games"
_COUNT_RE = re.compile(r"\b\d+\s+of\s+\d+\b|\b\d+\s+(?:matches|games|"
                       r"meetings|fixtures|encounters)\b", re.IGNORECASE)


def _pct_without_count(article: str) -> list[str]:
    """Sentences that state a win percentage but no match count (house rule:
    percentages carry their sample). Returns short excerpts for the repair
    prompt."""
    out = []
    for raw in re.split(r"(?<=[.!?])\s+|\n+", article):
        s = raw.strip().lstrip("-*# ").strip()
        if s and _PCT_RE.search(s) and _WINNISH_RE.search(s) \
                and not _COUNT_RE.search(s):
            out.append(s[:90] + ("..." if len(s) > 90 else ""))
    return out


_EXCESS_DECIMALS_RE = re.compile(r"\b\d+\.\d{3,}\b")


def validate_style(article: str) -> dict:
    em_dashes = article.count("\u2014")
    excess_decimals = _EXCESS_DECIMALS_RE.findall(article)
    connectors = []
    for phrase in BANNED_CONNECTORS:
        pattern = r"\b" + r"\s+".join(map(re.escape, phrase.split())) + r"\b"
        n = len(re.findall(pattern, article, flags=re.IGNORECASE))
        if n:
            connectors.append(f"{phrase} (x{n})")
    banned_words = []
    for name, pattern in BANNED_WORDS:
        n = len(re.findall(pattern, article, flags=re.IGNORECASE))
        if n:
            banned_words.append(f"{name} (x{n})")
    house_terms = []
    for name, pattern in BANNED_HOUSE_TERMS:
        n = len(re.findall(pattern, article, flags=re.IGNORECASE))
        if n:
            house_terms.append(f"{name} (x{n})")
    pct_no_count = _pct_without_count(article)
    return {"passed": (em_dashes == 0 and not connectors and not banned_words
                       and not house_terms and not pct_no_count
                       and not excess_decimals),
            "em_dashes": em_dashes, "banned_connectors": connectors,
            "banned_words": banned_words, "house_terms": house_terms,
            "pct_without_count": pct_no_count,
            "excess_decimals": excess_decimals}


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------
def get_client():
    load_dotenv(ROOT / ".env")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        return None
    from openai import OpenAI
    return OpenAI(api_key=key)


def _call(client, messages: list[dict]) -> str:
    resp = client.chat.completions.create(
        model=MODEL,
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_TOKENS,
        messages=messages,
    )
    return resp.choices[0].message.content or ""


def _repair_prompt(numbers: dict, style: dict) -> str:
    lines = [
        "Your draft failed mechanical validation. Fix ONLY the issues listed "
        "below and change nothing else: keep every other word, number and "
        "heading exactly as it is. Return the full corrected article.",
    ]
    if not numbers["passed"]:
        lines.append("")
        lines.append("NUMBER VIOLATIONS - these numbers are not derivable from "
                     "the payload under the rounding discipline (nearest whole "
                     "number for percentages/rates, at most one decimal, never "
                     "truncate). Replace each with the correctly rounded "
                     "payload value, or drop the number:")
        lines.extend(f"  - {tok}" for tok in numbers["violations"])
    if not style["passed"]:
        lines.append("")
        lines.append("STYLE VIOLATIONS:")
        if style["em_dashes"]:
            lines.append(f"  - {style['em_dashes']} em dash(es) present; "
                         "replace each with a period, comma, colon or "
                         "parentheses.")
        for hit in style["banned_connectors"]:
            lines.append(f"  - banned connector: {hit}; rewrite those "
                         "sentences without it.")
        for hit in style["banned_words"]:
            lines.append(f"  - banned word: {hit}; rewrite those sentences "
                         "without it (any inflection is banned).")
        for hit in style["house_terms"]:
            lines.append(f"  - house-banned term: {hit}; rewrite those "
                         "sentences without it (any inflection is banned).")
        for s in style["pct_without_count"]:
            lines.append(f"  - win percentage with no match count in the "
                         f"sentence: \"{s}\" -> add the count from "
                         "venue_stats.matches_at_venue_total (e.g. \"59% of "
                         "the 58 matches here\") or rewrite as counts.")
        for tok in style["excess_decimals"]:
            lines.append(f"  - raw payload precision leaked: {tok} -> round "
                         "to at most one decimal (two only for payload "
                         "economy/strike-rate figures copied exactly).")
    return "\n".join(lines)


def _lifecycle_view(payload: dict, mode: str) -> dict:
    """The payload as the generation mode is allowed to see it. pre_toss
    mechanically strips the toss result (prompt discipline alone is not a
    guarantee): conditions.toss -> None, toss_known -> False."""
    if mode != "pre_toss":
        return payload
    import copy
    view = copy.deepcopy(payload)
    (view.get("conditions") or {})["toss"] = None
    ((view.get("meta") or {}).get("data_completeness") or {})["toss_known"] = False
    return view


def generate_article(payload: dict, client,
                     mode: str = MODE) -> tuple[str, dict, dict, int]:
    """Generate + validate, with up to MAX_RETRIES targeted repair rounds.
    Returns (article, number_result, style_result, api_calls_used)."""
    payload = _lifecycle_view(payload, mode)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": build_user_prompt(payload, mode=mode)},
    ]
    article = _call(client, messages)
    numbers = validate_article(article, payload)
    style = validate_style(article)
    attempts = 1
    while not (numbers["passed"] and style["passed"]) and attempts <= MAX_RETRIES:
        print(f"  attempt {attempts}: numbers="
              f"{'ok' if numbers['passed'] else numbers['violations']} "
              f"style={'ok' if style['passed'] else 'FAIL'} -> repairing")
        messages.append({"role": "assistant", "content": article})
        messages.append({"role": "user", "content": _repair_prompt(numbers, style)})
        article = _call(client, messages)
        numbers = validate_article(article, payload)
        style = validate_style(article)
        attempts += 1
    return article, numbers, style, attempts


def generate_and_save(match_id: int, client,
                      mode: str = MODE) -> tuple[Path, dict, dict, int]:
    payload = build_payload(match_id)
    article, numbers, style, attempts = generate_article(payload, client, mode)
    ok = numbers["passed"] and style["passed"]
    stamp = ("VALIDATION: PASSED" if ok else
             f"FAILED VALIDATION - numbers: {numbers['violations'] or 'ok'} | "
             f"style: em_dashes={style['em_dashes']}, "
             f"connectors={style['banned_connectors'] or 'ok'}, "
             f"words={style['banned_words'] or 'ok'}, "
             f"house_terms={style['house_terms'] or 'ok'}, "
             f"pct_no_count={style['pct_without_count'] or 'ok'}, "
             f"excess_decimals={style['excess_decimals'] or 'ok'}")
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTICLES_DIR / f"{match_id}_{mode}_draft.md"
    out.write_text(f"<!-- {stamp} | model={MODEL} | mode={mode} | "
                   f"attempts={attempts} | "
                   f"payload_model={payload['prediction']['model_version']} -->\n\n"
                   + article, encoding="utf-8")
    return out, numbers, style, attempts


# --------------------------------------------------------------------------
def main() -> None:
    client = get_client()
    if client is None:
        print("STOP: no usable OPENAI_API_KEY found in .env")
        print()
        print("Add this line to C:\\Users\\Corsair\\cricket-predictions\\.env")
        print("(same pattern as the DB creds; the key itself never enters git):")
        print()
        print("    OPENAI_API_KEY=sk-...your real key...")
        print()
        print("(.env.example already lists the variable. In GitHub Actions it")
        print(" will come from Settings -> Secrets and variables -> Actions.)")
        sys.exit(1)

    for band, match_id in DEMO_MATCHES:
        for mode in ("post_toss", "pre_toss"):
            print("\n" + "=" * 74)
            print(f"GENERATING - {band.upper()} "
                  f"(match_id={match_id}, mode={mode})")
            print("=" * 74)
            path, numbers, style, attempts = generate_and_save(
                match_id, client, mode)
            print(f"saved: {path}  (API calls: {attempts})")
            print(f"numbers: {'PASSED' if numbers['passed'] else 'FAILED'} "
                  f"({numbers['numbers_checked']} distinct numbers checked; "
                  f"violations: {numbers['violations'] or 'none'})")
            print(f"style:   {'PASSED' if style['passed'] else 'FAILED'} "
                  f"(em_dashes: {style['em_dashes']}; "
                  f"connectors: {style['banned_connectors'] or 'none'}; "
                  f"Part E words: {style['banned_words'] or 'none'}; "
                  f"house terms: {style['house_terms'] or 'none'}; "
                  f"pct w/o count: {style['pct_without_count'] or 'none'}; "
                  f"excess decimals: {style['excess_decimals'] or 'none'})")
            print("-" * 74)
            print(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
