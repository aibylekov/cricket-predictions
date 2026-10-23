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
    ITERATION-3 CHECKS (56-comment review): form claims ("won N of M")
    must carry a scope label; no sentence >= 8 words repeats
    verbatim; distinctive stats capped (see iteration 4); bands moderate/
    close_call must contain the one conditional-angle sentence (an "if"
    sentence naming a payload player); plus new house-banned families
    (prolific / notable / marginal, meta-prediction talk, ", the 32nd
    match of" appositives, any missing-data mention).
    ITERATION-4 CHECKS (38-comment v3 review - scope & attribution):
      * SCOPE ATTRIBUTION (C10 class): a sentence with a scope phrase
        ("this series", "the current tour", "this event") plus a win/
        loss count must use tour-scoped counts (current_event window,
        standings, or this event's last5 entries); the reverse - a
        cross-competition last5 count in an unscoped sentence - must
        carry "across competitions" or name the other events.
      * WIN-RECORD PAIRS (C10 class, unscoped level): every "won/lost
        N of M" claim is validated as a PAIR against one payload
        window per verb sense - "won 3 of their last 5" when the
        window holds 4 wins fails even though 3 and 5 both exist
        somewhere in the payload.
      * TOSS EMPHASIS (C12): "significant/decisive"-grade toss language
        (non-negated, in toss context) is allowed ONLY when the
        payload's deterministic conditions.toss_impact is "high".
      * FORM-CLAIM LABEL: franchise matches label form claims with the
        league name (payload match.form_label), never a redundant
        "T20"; internationals keep T20; venue-history claims are
        always "T20" (that sample spans competitions).
      * WIN CLAIMS COUNT+TOTAL (C36): a win percentage's sentence must
        contain "X of N", not just a bare sample size.
      * VENUE SAMPLE SCOPE: the Pitch section states the sample (count
        + first year of venue_stats.sample_first_match).
      * REPETITION (tightened): a distinctive stat at most once in
        Three Key Points and at most once elsewhere.
      * FINALS FRAMING: stage=final bans next-stage phrasing and the
        verdict section must carry title language; knockout matches
        attribute any "N points" to the group/league stage.

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

AUTHOR STYLE ROTATION (voice layer, author-independent checks):
    generate_article(..., author_id) builds the system prompt through
    prompt_template.build_system_prompt(author_id): the house VOICE block
    is swapped for the author's profile (src/content/author_profiles/),
    nothing else changes. generate_and_save() resolves the author through
    src/content/author_rotation.AuthorRotation - a shuffled deck dealt one
    profile per match, reshuffled only when exhausted, persisted per
    match_id in data/state/author_assignments.json - so same-day matches
    never share a voice (unless there are more matches than profiles) and
    retries / the pre_toss-post_toss pair of one match always use the same
    profile. The draft header stamps the author. EVERY validator in this
    file runs identically under every author: the profile changes how the
    prose sounds, never what it may say.

DEMO:
    venv/Scripts/python.exe -m src.content.generate_article [--modes
    post_toss|pre_toss|both] [--reset-authors]
generates the three payload-demo matches (confident England, moderate
MLC, close_call IPL) as ONE MATCH DAY: the rotation deals three different
author profiles up front (printed), then each draft is generated in the
requested mode(s) (default post_toss; saved as <match_id>_<mode>_draft.md),
validated, and printed with its report. --reset-authors starts a fresh
deck (otherwise persisted assignments are reused, by design).
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

from src.content.author_rotation import (AuthorRotation, draft_footer,
                                         format_audit, profile_display_name)
from src.content.payload import build_payload
from src.content.prompt_template import (
    BANNED_CONNECTORS,
    BANNED_HOUSE_TERMS,
    BANNED_WORDS,
    SYSTEM_PROMPT,
    TERMINOLOGY,
    build_system_prompt,
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
# iteration 4 (C36): a bare sample size no longer satisfies the rule -
# win claims give count AND total, "10 of the 17"
_OF_TOTAL_RE = re.compile(r"\b\d+\s+of\s+(?:the\s+)?\d+\b", re.IGNORECASE)


def _pct_without_count(article: str) -> list[str]:
    """Sentences that state a win percentage without count-and-total in
    "X of N" form (iteration-4 house rule: win claims give the count AND
    the total, not just the sample size). Returns short excerpts for the
    repair prompt."""
    out = []
    for raw in re.split(r"(?<=[.!?])\s+|\n+", article):
        s = raw.strip().lstrip("-*# ").strip()
        if s and _PCT_RE.search(s) and _WINNISH_RE.search(s) \
                and not _OF_TOTAL_RE.search(s):
            out.append(s[:90] + ("..." if len(s) > 90 else ""))
    return out


_EXCESS_DECIMALS_RE = re.compile(r"\b\d+\.\d{3,}\b")

# ---- iteration-3 checks --------------------------------------------------
# Form-claim sentences ("won/lost N of (their last) M", "won their last N")
# must carry the format word (house rule: FORMAT EVERYWHERE).
_FORM_CLAIM_RE = re.compile(
    r"\b(?:won|lost|winning|losing|unbeaten)\b[^.!?\n]*?"
    r"\b\d+\s+of\s+(?:\w+\s+){0,2}?\d+\b"
    r"|\b(?:won|lost)\s+(?:their|its|the)\s+last\s+\d+\b",
    re.IGNORECASE)
_FORMAT_TOKEN_RE = re.compile(r"\bT20I?s?\b|\btwenty20\b", re.IGNORECASE)


def _sentences(article: str) -> list[str]:
    out = []
    for raw in re.split(r"(?<=[.!?])\s+|\n+", article):
        s = raw.strip().lstrip("-*# ").strip()
        if s:
            out.append(s)
    return out


def _excerpt(s: str, n: int = 90) -> str:
    return s[:n] + ("..." if len(s) > n else "")


def _split_sections(article: str) -> list[tuple[str, str]]:
    """(heading, text) pairs split on '## ' headings; the title + intro
    before the first heading ride under heading ''."""
    sections, heading, buf = [], "", []
    for line in article.splitlines():
        if line.strip().startswith("## "):
            sections.append((heading, "\n".join(buf)))
            heading, buf = line.strip().lstrip("#").strip(), []
        else:
            buf.append(line)
    sections.append((heading, "\n".join(buf)))
    return sections


# venue-history claims ("won 10 of the 17 T20s here") keep the T20 label in
# every competition type - detect them so the franchise league-label rule
# doesn't fire on them
_VENUE_CLAIM_RE = re.compile(
    r"\bhere\b|\bat\s+this\s+(?:venue|ground|stadium)\b|"
    r"\bteams?\s+(?:batting|batting\s+first|chasing)\b|"
    r"\bbatting\s+first\s+ha(?:ve|s)\b|\bchasing\s+(?:teams|sides)\b",
    re.IGNORECASE)


def _is_venue_claim(s: str, payload: dict | None) -> bool:
    if _VENUE_CLAIM_RE.search(s):
        return True
    venue = ((payload or {}).get("match") or {}).get("venue")
    return bool(venue) and str(venue).lower() in s.lower()


def _form_claims_mislabelled(article: str, payload: dict | None) -> list[str]:
    """ITERATION 4 - form-claim sentences must carry the RIGHT scope label:
    franchise matches the league name (payload match.form_label /
    form_label_full; a bare "T20" is the redundancy the editor flagged),
    internationals the T20 token, venue-history claims always T20."""
    m = (payload or {}).get("match") or {}
    franchise = m.get("competition_type") == "franchise"
    league_res = [re.compile(r"\b" + re.escape(tok) + r"\b", re.IGNORECASE)
                  for tok in (m.get("form_label"), m.get("form_label_full"))
                  if tok]
    out = []
    for s in _sentences(article):
        if not _FORM_CLAIM_RE.search(s):
            continue
        if not franchise or _is_venue_claim(s, payload):
            if not _FORMAT_TOKEN_RE.search(s):
                out.append(f'"{_excerpt(s)}" -> add the format word T20')
        elif not any(r.search(s) for r in league_res):
            label = m.get("form_label") or "the league name"
            if _FORMAT_TOKEN_RE.search(s):
                out.append(f'"{_excerpt(s)}" -> franchise league: label the '
                           f"form claim with '{label}', not 'T20' "
                           "(redundant inside a T20 league)")
            else:
                out.append(f'"{_excerpt(s)}" -> add the league label '
                           f"'{label}'")
    return out


def _verbatim_repeats(article: str) -> list[str]:
    """Sentences (>= 8 words, headings excluded) that appear verbatim more
    than once after normalization - the fact-repetition cap's hard floor."""
    counts: dict[str, str] = {}
    hits = []
    for line in article.splitlines():
        if line.strip().startswith("#"):
            continue
        for s in _sentences(line):
            norm = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", s.lower())).strip()
            if len(norm.split()) < 8:
                continue
            if norm in counts and counts[norm] is not None:
                hits.append(counts[norm][:90])
                counts[norm] = None          # report once
            elif norm not in counts:
                counts[norm] = s
    return hits


_STAT_TOKEN_RE = re.compile(r"\b\d+\.\d+\b|\b\d+%")


def _overused_stats(article: str) -> list[str]:
    """ITERATION 4 (tightened repetition cap): a distinctive stat token
    (decimal like 164.4 / percentage like 59%) may appear at most ONCE in
    Three Key Points and at most ONCE elsewhere - which also enforces
    'never in 3+ sections' and the old 3+-total cap."""
    per = [(h, _STAT_TOKEN_RE.findall(t)) for h, t in _split_sections(article)]
    out = []
    for tok in sorted({t for _, toks in per for t in toks}):
        kp = sum(toks.count(tok) for h, toks in per
                 if "key points" in h.lower())
        rest = sum(toks.count(tok) for h, toks in per
                   if "key points" not in h.lower())
        if kp > 1 or rest > 1:
            out.append(f"{tok} (key points x{kp}, elsewhere x{rest})")
    return out


# --------------------------------------------------------------------------
# iteration-4 checks: scope attribution / toss emphasis / finals / venue
# --------------------------------------------------------------------------
# Win/loss COUNT phrasings. Integer captures reject decimal fragments
# (margins like 30.6 must never contribute a "30").
_INT = r"(?<![\d.])(\d+)(?!\.?\d)"
_WL_COUNT_PATTERNS = [re.compile(p.replace("<N>", _INT), re.IGNORECASE) for p in (
    r"\b(?:won|lost|winning|losing)\b[^.!?\n]{0,30}?<N>\s+of\s+"
    r"(?:(?!\d)\w+\s+){0,3}?<N>",
    r"\b(?:won|lost|winning|losing)\s+all\s+<N>\b",
    r"\b(?:won|lost)\s+(?:their|its|the)\s+(?:last|first|opening)\s+<N>\b",
    r"<N>\s+(?:consecutive|straight)\s+(?:\w+\s+)?"
    r"(?:wins|losses|defeats|victories)\b",
    r"<N>\s+(?:wins?|losses|defeats|victor(?:y|ies))\b"
    r"(?:\s+(?:in|from)\s+(?:their\s+)?(?:last\s+)?<N>\b)?",
    r"\bunbeaten\s+in\s+(?:their\s+)?(?:last\s+)?<N>\b",
)]

# "this series" / "the current tour" / "this event" ... - a claim scoped to
# the current competition
_SCOPE_PHRASE_RE = re.compile(
    r"\b(?:this|that|the\s+current|the\s+ongoing|the)\s+(?:series|tour|"
    r"tournament|season|event|campaign)\b"
    r"|\b(?:this|the\s+current|the\s+ongoing)\s+competition\b",
    re.IGNORECASE)

_GENERIC_EVENT_TOKENS = {"icc", "men", "mens", "cup", "league", "premier",
                         "cricket", "tour", "series", "tournament"}


def _wl_counts(sentence: str) -> list[float]:
    vals = []
    for pat in _WL_COUNT_PATTERNS:
        for m in pat.finditer(sentence):
            vals.extend(float(g) for g in m.groups() if g)
    return vals


def _scoped_counts(payload: dict) -> set[float]:
    """Every count a series/tour-scoped claim may legitimately use: the
    current_event window (wins/losses/n per side), the standings counts,
    and this event's own last5_results entries."""
    out: set[int] = set()
    form = payload.get("form") or {}
    for side in ("home", "away"):
        s = form.get(side) or {}
        p = (s.get("win_pct") or {}).get("current_event")
        n = (s.get("matches_in_window") or {}).get("current_event")
        if p is not None and n:
            wins = round(p * n)
            out |= {wins, n - wins, n}
    st = payload.get("standings") or {}
    for side in ("home", "away"):
        r = st.get(side) if isinstance(st, dict) else None
        if r:
            out |= {v for v in (r.get("won"), r.get("lost"), r.get("played"))
                    if v is not None}
    cur = (payload.get("match") or {}).get("tournament")
    l5 = (payload.get("match_context") or {}).get("last5_results") or {}
    for side in ("home", "away"):
        ent = [e for e in (l5.get(side) or []) if e.get("event") == cur]
        if ent:
            w = sum(1 for e in ent if e.get("won"))
            out |= {w, len(ent) - w, len(ent)}
    return {float(x) for x in out}


def _cross_counts(payload: dict, scoped: set[float]) -> set[float]:
    """Counts implied by a last5 window that SPANS competitions - the ones
    that must carry an 'across competitions' label. Counts that are also
    valid tour-scoped numbers are excluded (ambiguous, never flagged)."""
    out: set[int] = set()
    cur = (payload.get("match") or {}).get("tournament")
    l5 = (payload.get("match_context") or {}).get("last5_results") or {}
    for side in ("home", "away"):
        ent = l5.get(side) or []
        if ent and any(e.get("event") != cur for e in ent):
            w = sum(1 for e in ent if e.get("won"))
            out |= {w, len(ent) - w, len(ent)}
    return {float(x) for x in out} - scoped


def _other_event_tokens(payload: dict) -> set[str]:
    """Distinctive words of the OTHER events in last5_results - naming one
    of these in the sentence counts as labeling the cross-event claim."""
    cur = ((payload.get("match") or {}).get("tournament") or "")
    cur_toks = set(re.sub(r"[^a-z0-9 ]", " ", cur.lower()).split())
    toks: set[str] = set()
    l5 = (payload.get("match_context") or {}).get("last5_results") or {}
    for side in ("home", "away"):
        for e in l5.get(side) or []:
            ev = e.get("event")
            if ev and ev != cur:
                for w in re.sub(r"[^a-z0-9 ]", " ", ev.lower()).split():
                    if (len(w) > 3 and w not in cur_toks
                            and w not in _GENERIC_EVENT_TOKENS):
                        toks.add(w)
    return toks


def _scope_attribution_violations(article: str,
                                  payload: dict | None) -> list[str]:
    """ITERATION 4 root-cause fix (the C10 factual error): a sentence
    scoping a win/loss count to the current competition must use the
    tour-scoped counts; a cross-competition count must carry a label
    ('across ...' or another event's name)."""
    if not payload:
        return []
    scoped = _scoped_counts(payload)
    cross = _cross_counts(payload, scoped)
    other_toks = _other_event_tokens(payload)
    out = []
    for s in _sentences(article):
        nums = _wl_counts(s)
        if not nums:
            continue
        if _SCOPE_PHRASE_RE.search(s):
            bad = sorted({int(n) for n in nums if n not in scoped})
            if bad:
                out.append(f'"{_excerpt(s)}" -> the counts {bad} are not '
                           "this event's numbers; a series/tour-scoped "
                           "claim must use the current_event / standings "
                           "counts (or drop the scope phrase and label the "
                           "window 'across competitions')")
        elif cross and any(n in cross for n in nums):
            low = s.lower()
            if "across" not in low and not any(t in low for t in other_toks):
                out.append(f'"{_excerpt(s)}" -> this count spans '
                           "competitions; say 'across competitions' (or "
                           "name the events) in the same sentence")
    return out


# "won N of M" pair patterns: the verb decides whether N claims wins or
# losses; both numbers captured together so the PAIR is validated
_PAIR_OF_RE = re.compile(
    r"\b(won|win|wins|winning|lost|losing|lose|loses)\b[^.!?\n]{0,40}?"
    r"(?<![\d.])(\d+)(?!\.?\d)\s+(?:out\s+of|of)\s+"
    r"(?:the\s+|their\s+|its\s+)?(?:last\s+|first\s+|past\s+)?"
    r"(?<![\d.])(\d+)(?!\.?\d)", re.IGNORECASE)
_PAIR_FROM_RE = re.compile(
    r"(?<![\d.])(\d+)(?!\.?\d)\s+(wins?|losses|defeats|victories)\s+"
    r"(?:in|from)\s+(?:their\s+|the\s+)?(?:last\s+)?"
    r"(?<![\d.])(\d+)(?!\.?\d)", re.IGNORECASE)
_LOSS_VERBS = {"lost", "losing", "lose", "loses", "losses", "defeats"}


def _win_loss_pairs(payload: dict) -> tuple[set, set]:
    """Every (count, total) pair a "won/lost N of M" claim may use: the
    form windows, standings, venue splits, and the last5 windows (whole
    and this-event-only). Returns (win_pairs, loss_pairs)."""
    wins: set = set()
    losses: set = set()

    def add(w, n):
        if w is None or not n:
            return
        w = int(round(w))
        wins.add((w, int(n)))
        losses.add((int(n) - w, int(n)))

    form = payload.get("form") or {}
    for side in ("home", "away"):
        s = form.get(side) or {}
        for window in ("last5", "tournament", "current_event"):
            p = (s.get("win_pct") or {}).get(window)
            n = (s.get("matches_in_window") or {}).get(window)
            if p is not None and n:
                add(p * n, n)
    st = payload.get("standings") or {}
    for side in ("home", "away"):
        r = st.get(side) if isinstance(st, dict) else None
        if r and r.get("played"):
            add(r.get("won"), r.get("played"))
    vs = payload.get("venue_stats") or {}
    vn = vs.get("matches_at_venue_total")
    if vn:
        for key in ("batfirst_win_pct", "chase_win_pct"):
            p = vs.get(key)
            if p is not None:
                add(p * vn, vn)
    cur = (payload.get("match") or {}).get("tournament")
    l5 = (payload.get("match_context") or {}).get("last5_results") or {}
    for side in ("home", "away"):
        ent = l5.get(side) or []
        if ent:
            add(sum(1 for e in ent if e.get("won")), len(ent))
            ine = [e for e in ent if e.get("event") == cur]
            if ine:
                add(sum(1 for e in ine if e.get("won")), len(ine))
    return wins, losses


def _win_pair_violations(article: str, payload: dict | None) -> list[str]:
    """ITERATION 4 (the C10 class at the unscoped level): a "won/lost N of
    M" claim is validated as a PAIR against the payload's windows - "won 3
    of their last 5" when the window holds 4 wins is a factual error even
    though both numbers exist somewhere in the payload."""
    if not payload:
        return []
    wins, losses = _win_loss_pairs(payload)
    if not wins:
        return []
    out = []
    for s in _sentences(article):
        claims = []
        for m in _PAIR_OF_RE.finditer(s):
            claims.append((m.group(1).lower(), int(m.group(2)), int(m.group(3))))
        for m in _PAIR_FROM_RE.finditer(s):
            claims.append((m.group(2).lower(), int(m.group(1)), int(m.group(3))))
        for verb, cnt, total in claims:
            pool = losses if verb in _LOSS_VERBS else wins
            if (cnt, total) not in pool:
                out.append(f'"{_excerpt(s)}" -> "{verb} {cnt} of {total}" '
                           "matches no payload window (check the window's "
                           "actual win/loss count and total)")
    return out


# --------------------------------------------------------------------------
# iteration-5b checks (editor's v5 review): mirror facts / home scope /
# terminology
# --------------------------------------------------------------------------
_W, _L = "W", "L"
_LOSS_WORDS = _LOSS_VERBS | {"loss", "defeat", "defeated", "beaten"}
# "won all N", "won their last N", "N straight wins", "unbeaten in N"
# (the "won N of M" / "N wins in M" forms reuse _PAIR_OF_RE / _PAIR_FROM_RE)
_CLAIM_ALL_RE = re.compile(
    r"\b(won|win|wins|winning|lost|losing|lose|loses)\s+(?:all|each)\s+"
    r"(?:of\s+)?(?:their\s+|the\s+|its\s+)?(?<![\d.])(\d+)(?!\.?\d)",
    re.IGNORECASE)
_CLAIM_LASTN_RE = re.compile(
    r"\b(won|winning|lost|losing)\s+(?:their|its|the)\s+"
    r"(?:last|first|opening|previous)\s+(?<![\d.])(\d+)(?!\.?\d)"
    r"(?!\s+(?:of|out\s+of)\b)", re.IGNORECASE)
_CLAIM_STREAK_RE = re.compile(
    r"(?<![\d.])(\d+)(?!\.?\d)\s+(?:consecutive|straight|successive)\s+"
    r"(?:\w+\s+)?(wins|victories|losses|defeats)\b", re.IGNORECASE)
_CLAIM_UNBEATEN_RE = re.compile(
    r"\bunbeaten\s+in\s+(?:their\s+|its\s+)?(?:last\s+)?"
    r"(?<![\d.])(\d+)(?!\.?\d)", re.IGNORECASE)
_TEAM_STOP = {"royal", "super", "kings", "united", "city", "club", "cricket",
              "team", "women", "the", "new"}


def _kind(word: str) -> str:
    return _L if word.lower() in _LOSS_WORDS else _W


# spelled-out counts ("winning all three T20s") are the same claim as digits
_NUM_WORDS = {w: str(i) for i, w in enumerate(
    ("zero one two three four five six seven eight nine ten eleven twelve "
     "thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty"
     ).split())}
_NUM_WORD_RE = re.compile(r"\b(" + "|".join(_NUM_WORDS) + r")\b", re.IGNORECASE)


def _digits(sentence: str) -> str:
    """Number words -> digits, for the claim checks only (the numbers
    validator keeps reading the raw text)."""
    return _NUM_WORD_RE.sub(lambda m: _NUM_WORDS[m.group(1).lower()], sentence)


def _result_claims(sentence: str) -> list[tuple[int, str, int, int | None]]:
    """(position, W|L, count, total - None for a streak) per claim."""
    out = []
    for m in _PAIR_OF_RE.finditer(sentence):
        out.append((m.start(), _kind(m.group(1)), int(m.group(2)), int(m.group(3))))
    for m in _PAIR_FROM_RE.finditer(sentence):
        out.append((m.start(), _kind(m.group(2)), int(m.group(1)), int(m.group(3))))
    for m in _CLAIM_ALL_RE.finditer(sentence):
        n = int(m.group(2))
        out.append((m.start(), _kind(m.group(1)), n, n))
    for m in _CLAIM_LASTN_RE.finditer(sentence):
        n = int(m.group(2))
        out.append((m.start(), _kind(m.group(1)), n, n))
    for m in _CLAIM_STREAK_RE.finditer(sentence):
        out.append((m.start(), _kind(m.group(2)), int(m.group(1)), None))
    for m in _CLAIM_UNBEATEN_RE.finditer(sentence):
        n = int(m.group(1))
        out.append((m.start(), _W, n, n))
    seen, uniq = set(), []
    for c in sorted(out, key=lambda c: (c[0], c[1], c[2], c[3] or 0)):
        if c[1:] not in seen:
            seen.add(c[1:])
            uniq.append(c)
    return uniq


def _team_aliases(payload: dict) -> dict[str, list[re.Pattern]]:
    """side -> name patterns: the full name + its distinctive words that the
    other side's name does not share ('Titans', 'Bengaluru')."""
    m = payload.get("match") or {}
    names = {"home": m.get("home_team") or "", "away": m.get("away_team") or ""}
    words = {s: {w for w in re.findall(r"[a-z]+", n.lower())
                 if len(w) >= 4 and w not in _TEAM_STOP}
             for s, n in names.items()}
    out = {}
    for side, name in names.items():
        if not name:
            continue
        other = words["away" if side == "home" else "home"]
        alts = [re.escape(name)] + [re.escape(w) for w in sorted(words[side] - other)]
        out[side] = [re.compile(r"\b(?:" + a + r")\b", re.IGNORECASE) for a in alts]
    return out


def _subject_side(sentence: str, pos: int, aliases: dict) -> str | None:
    """The team a claim at `pos` is about: the nearest team mention before
    it, else the first one after it."""
    hits = []
    for side, pats in aliases.items():
        for p in pats:
            hits.extend((mm.start(), side) for mm in p.finditer(sentence))
    if not hits:
        return None
    before = [h for h in hits if h[0] <= pos]
    if before:
        return max(before)[1]
    return min(hits)[1]


def _is_agg(key: frozenset) -> bool:
    return any(isinstance(x, tuple) and x[:1] == ("agg",) for x in key)


def _result_sets(payload: dict, side: str) -> list[tuple[str, int, int | None, frozenset]]:
    """(W|L, count, total, result-set id) for every window of one side.
    Entry-backed windows (last5, this event's entries, the current streak)
    are identified by their MATCHES, so the other side's mirror - same
    matches, other verb - lands on the same id. Aggregate windows without
    entries (season / league history) use a (side, window) id."""
    m = payload.get("match") or {}
    me = m.get("home_team") if side == "home" else m.get("away_team")
    cur = m.get("tournament")
    ents = (((payload.get("match_context") or {}).get("last5_results") or {})
            .get(side) or [])
    out = []

    def ident(es):
        return frozenset((e.get("date"), frozenset({me, e.get("opponent")}))
                         for e in es)

    def add_window(es):
        if not es:
            return
        w = sum(1 for e in es if e.get("won"))
        n = len(es)
        out.append((_W, w, n, ident(es)))
        out.append((_L, n - w, n, ident(es)))

    add_window(ents)
    add_window([e for e in ents if e.get("event") == cur])
    if ents:                                     # the current streak
        first, run = ents[0].get("won"), 0
        for e in ents:
            if e.get("won") != first:
                break
            run += 1
        for k in range(1, run + 1):
            out.append((_W if first else _L, k, None, ident(ents[:k])))
    form = (payload.get("form") or {}).get(side) or {}
    st_all = payload.get("standings")
    st = st_all.get(side) if isinstance(st_all, dict) else None
    aggs = []
    for window in ("current_event", "tournament"):
        p = (form.get("win_pct") or {}).get(window)
        n = (form.get("matches_in_window") or {}).get(window)
        if p is not None and n:
            aggs.append((window, int(round(p * n)), int(n)))
    if st and st.get("played"):
        aggs.append(("current_event", int(st.get("won") or 0), int(st["played"])))
    for window, w, n in aggs:
        key = frozenset({("agg", side, window)})
        out.append((_W, w, n, key))
        out.append((_L, n - w, n, key))
    return out


def _mirror_fact_repeats(article: str, payload: dict | None) -> list[str]:
    """ITERATION 5b (editor's v5 Draft 1): ONE result set stated several
    times - directly or MIRRORED ("England winning all 3" + "India losing
    all 3 in the series" are the same three matches; "won 4 of 5" + "lost 1
    of 5" are the same window) - is held to the fact-repetition cap: at most
    once in Three Key Points, at most once elsewhere."""
    if not payload:
        return []
    aliases = _team_aliases(payload)
    if not aliases:
        return []
    sets = {side: _result_sets(payload, side) for side in aliases}
    claims = []          # (is_kp, sentence, side, kind, ids)
    for heading, text in _split_sections(article):
        is_kp = "key points" in heading.lower()
        for raw in _sentences(text):
            s = _digits(raw)
            for pos, kind, cnt, tot in _result_claims(s):
                side = _subject_side(s, pos, aliases)
                if side is None:
                    continue
                ids = {key for k, c, t, key in sets[side]
                       if k == kind and c == cnt and t == tot}
                if not ids:
                    continue     # not a payload window: the pair check owns it
                ids = {i for i in ids if not _is_agg(i)} or ids
                claims.append((is_kp, raw, side, kind, ids))
    groups: list[list[int]] = []
    for i, c in enumerate(claims):
        hit = [g for g in groups if any(claims[j][4] & c[4] for j in g)]
        groups = [g for g in groups if g not in hit] + [[i] + [j for g in hit for j in g]]
    out = []
    for g in groups:
        g = sorted(g)
        for where, cl in (("Three Key Points", [claims[j] for j in g if claims[j][0]]),
                          ("the rest of the article",
                           [claims[j] for j in g if not claims[j][0]])):
            # one sentence stating the set twice is still one statement
            sents = list(dict.fromkeys(c[1] for c in cl))
            if len(sents) > 1:
                mirrored = len({(c[2], c[3]) for c in cl}) > 1
                out.append(
                    f"{len(sents)}x in {where}"
                    f"{' (MIRRORED: the same matches told from both sides)' if mirrored else ''}"
                    ": " + " / ".join(f'"{_excerpt(s, 70)}"' for s in sents))
    return out


_HOME_SCOPE_RE = re.compile(
    r"\bat\s+home\b|\bon\s+home\s+(?:soil|turf|ground)\b|"
    r"\bhome\s+(?:record|form|run|ground|grounds|venue|soil|turf|crowd|"
    r"fixtures?|games?|matches|wins?|defeats?|losses|stretch|leg)\b|"
    r"\bin\s+front\s+of\s+their\s+(?:own\s+|home\s+)?(?:crowd|fans|supporters)\b",
    re.IGNORECASE)


def _home_scoped(payload: dict) -> tuple[set, set]:
    """(allowed counts, allowed (W|L, count, total) pairs). Home-scoped =
    last5_results entries played AT THIS VENUE for a side whose
    venue_ownership says at_own_ground. The payload has no other home
    record (no home W/L split exists in L2)."""
    counts, pairs = set(), set()
    m = payload.get("match") or {}
    venue = m.get("venue")
    vo = payload.get("venue_ownership") or {}
    if not isinstance(vo, dict) or vo.get("policy") == "shared_venues":
        return counts, pairs
    l5 = (payload.get("match_context") or {}).get("last5_results") or {}
    for side in ("home", "away"):
        own = vo.get(f"{side}_team") or {}
        if not own.get("at_own_ground"):
            continue
        es = [e for e in (l5.get(side) or []) if venue and e.get("venue") == venue]
        if es:
            w = sum(1 for e in es if e.get("won"))
            n = len(es)
            counts |= {float(w), float(n - w), float(n)}
            pairs |= {(_W, w, n), (_L, n - w, n)}
    return counts, pairs


def _window_label(payload: dict, kind: str, cnt: int, tot: int | None) -> str | None:
    for side in ("home", "away"):
        for k, c, t, key in _result_sets(payload, side):
            if k == kind and c == cnt and t == tot:
                tag = next(iter(key))
                if _is_agg(key):
                    return ("the season record" if tag[2] == "current_event"
                            else "the league-history record")
                return "a recent-results window, not filtered to this ground"
    return None


def _home_scope_violations(article: str, payload: dict | None) -> list[str]:
    """ITERATION 5b (editor's v5 Draft 3, KP2): "a solid record AT HOME,
    winning 10 of their 16 matches this season" - 10/16 is the season
    record. A sentence with home-scope language and a win/loss count must
    use home-scoped numbers only (see _home_scoped)."""
    if not payload:
        return []
    counts, pairs = _home_scoped(payload)
    out = []
    for s in _sentences(article):
        if not _HOME_SCOPE_RE.search(s):
            continue
        claims = _result_claims(_digits(s))
        nums = _wl_counts(_digits(s))
        if not claims and not nums:
            continue
        bad_pairs = [(k, c, t) for _, k, c, t in claims
                     if t is not None and (k, c, t) not in pairs]
        bad_nums = sorted({int(n) for n in nums if n not in counts})
        if not (bad_pairs or bad_nums):
            continue
        hint = next((h for h in (_window_label(payload, *bp) for bp in bad_pairs)
                     if h), None)
        what = (f"'{'won' if bad_pairs[0][0] == _W else 'lost'} {bad_pairs[0][1]} "
                f"of {bad_pairs[0][2]}'" if bad_pairs else f"the counts {bad_nums}")
        out.append(f'"{_excerpt(s)}" -> {what} is not a home-scoped number'
                   f"{f' (it is {hint})' if hint else ''}; home-scoped results "
                   "are only the last5 entries played at this ground by a team "
                   "whose at_own_ground is true. Call it the season record, or "
                   "drop the home framing.")
    return out


def _terminology_violations(article: str) -> list[str]:
    out = []
    for wrong, right, pattern in TERMINOLOGY:
        n = len(re.findall(pattern, article, flags=re.IGNORECASE))
        if n:
            out.append(f"'{wrong}' (x{n}) -> write '{right}'")
    return out


# non-negated strong toss language - allowed only when toss_impact = high
_TOSS_STRONG_RE = re.compile(
    r"\b(?:significant(?:ly)?|significance|decisive(?:ly)?|"
    r"decid(?:e|es|ed|ing)\s+the\s+(?:game|match|outcome|contest|result)|"
    r"massive|huge|major\s+(?:role|factor|impact|part))\b", re.IGNORECASE)
_TOSS_NEG_RE = re.compile(
    r"(?:\bnot|n[’']t|\bno|\bhardly|\bbarely|\brarely|\bnever|\bunlikely|"
    r"\bwithout|\bshouldn|\bwon)\W+(?:\w+\W+){0,2}$", re.IGNORECASE)


def _toss_emphasis_violations(article: str,
                              payload: dict | None) -> list[str]:
    """ITERATION 4 root-cause fix (the C12 inconsistency): the article may
    call the toss significant/decisive ONLY when the payload's
    deterministic conditions.toss_impact says 'high'. Negated mentions
    ('shouldn't be decisive') are downplay, not emphasis."""
    if not payload:
        return []
    impact = (payload.get("conditions") or {}).get("toss_impact")
    if impact == "high":
        return []
    out = []
    for heading, text in _split_sections(article):
        toss_section = "toss" in heading.lower()
        for s in _sentences(text):
            if not (toss_section or re.search(r"\btoss\b", s, re.IGNORECASE)):
                continue
            for m in _TOSS_STRONG_RE.finditer(s):
                if _TOSS_NEG_RE.search(s[:m.start()]):
                    continue
                out.append(f'"{_excerpt(s)}" -> "{m.group(0)}" overstates '
                           f"the toss (payload toss_impact is "
                           f"{impact or 'unknown'}); restate at exactly "
                           "that level")
                break
    return out


_FINALS_BANNED = [
    ("next-stage phrasing",
     re.compile(r"\bnext\s+(?:stage|game|match|round|fixture|hurdle|step)\b",
                re.IGNORECASE)),
    ("advance/progress talk",
     re.compile(r"\b(?:advanc(?:e|es|ing)|progress(?:es|ing)?)\s+"
                r"(?:to|into|past|further)\b", re.IGNORECASE)),
    ("qualification talk",
     re.compile(r"\bqualif(?:y|ies|ied|ying)\s+for\b", re.IGNORECASE)),
    ("spot in a next round",
     re.compile(r"\b(?:spot|place|berth)\s+in\s+the\s+(?:next|semi)",
                re.IGNORECASE)),
    ("semi-final spot",
     re.compile(r"\bsemi[- ]?finals?\s+(?:spot|berth|place)\b",
                re.IGNORECASE)),
]
_TITLE_TOKEN_RE = re.compile(
    r"\btitle\b|\btrophy\b|\bchampion\w*\b|\bsilverware\b|\bcrown\w*\b",
    re.IGNORECASE)


def _finals_language(article: str, payload: dict | None) -> list[str]:
    """ITERATION 4: a final has no next round - ban next-stage phrasing and
    require title-winning language in the closing verdict section."""
    stage = ((payload or {}).get("match_context") or {}).get("stage")
    if stage != "final":
        return []
    out = []
    for name, pat in _FINALS_BANNED:
        for m in pat.finditer(article):
            out.append(f"{name}: '{m.group(0)}' - a final has no next "
                       "match; recast as title-winning language")
    for heading, text in _split_sections(article):
        if "winning prediction" in heading.lower() \
                and not _TITLE_TOKEN_RE.search(text):
            out.append("the Our Winning Prediction section of a final must "
                       "carry title language (title / trophy / champions)")
    return out


_POINTS_RE = re.compile(r"\b\d+\s+points\b", re.IGNORECASE)
_STAGE_ATTR_RE = re.compile(
    r"\b(?:group|league|round[- ]robin|regular)[- ]?\s*"
    r"(?:stage|phase|season)\b", re.IGNORECASE)


def _knockout_points_attribution(article: str,
                                 payload: dict | None) -> list[str]:
    """ITERATION 4: in a knockout match, every 'N points' mention says
    where the points came from ('in the group stage')."""
    if not ((payload or {}).get("match_context") or {}).get("is_knockout"):
        return []
    return [f'"{_excerpt(s)}" -> attribute the points to the group/league '
            'stage in the same sentence ("in the group stage")'
            for s in _sentences(article)
            if _POINTS_RE.search(s) and not _STAGE_ATTR_RE.search(s)]


def _venue_sample_scope(article: str, payload: dict | None) -> list[str]:
    """ITERATION 4: the Pitch section states the venue sample - the match
    count and the period ('across the 11 T20s here since 2023'). Only
    checked when the section exists and the payload carries the sample."""
    vs = (payload or {}).get("venue_stats") or {}
    n, first = vs.get("matches_at_venue_total"), vs.get("sample_first_match")
    if not n or not first:
        return []
    pitch = [t for h, t in _split_sections(article) if "pitch" in h.lower()]
    if not pitch:
        return []
    text = "\n".join(pitch)
    year = str(first)[:4]
    out = []
    if not re.search(rf"\b{n}\b", text):
        out.append(f"the Pitch section must state the venue sample count "
                   f"({n} T20s)")
    if year not in text:
        out.append(f"the Pitch section must state the sample period "
                   f"(e.g. \"since {year}\"; first venue match {first})")
    return out


def _player_surnames(payload: dict) -> list[str]:
    """Last name token of every payload player (both sides)."""
    out = []
    for side in ("home", "away"):
        block = (payload.get("players") or {}).get(side) or {}
        for group in ("top_batters", "top_bowlers"):
            for p in block.get(group) or []:
                name = (p.get("name") or "").strip()
                if name:
                    sur = name.split()[-1]
                    if len(sur) > 2:
                        out.append(sur)
    return out


def _missing_conditional_angle(article: str, payload: dict | None) -> bool:
    """Band moderate/close_call requires ONE conditional-angle sentence
    ('If <key player(s)> misfire, the game tilts to <other team>') naming
    payload players. Satisfied by any sentence with 'if' + a payload
    player surname."""
    if not payload:
        return False
    band = (payload.get("prediction") or {}).get("confidence_band")
    if band not in ("moderate", "close_call"):
        return False
    surnames = _player_surnames(payload)
    if not surnames:
        return False
    for s in _sentences(article):
        low = s.lower()
        if re.search(r"\bif\b", low) and any(x.lower() in low for x in surnames):
            return False
    return True


def validate_style(article: str, payload: dict | None = None) -> dict:
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
    form_label = _form_claims_mislabelled(article, payload)
    repeats = _verbatim_repeats(article)
    overused = _overused_stats(article)
    no_conditional = _missing_conditional_angle(article, payload)
    scope_attr = _scope_attribution_violations(article, payload)
    win_pairs = _win_pair_violations(article, payload)
    toss_emph = _toss_emphasis_violations(article, payload)
    finals = _finals_language(article, payload)
    ko_points = _knockout_points_attribution(article, payload)
    venue_scope = _venue_sample_scope(article, payload)
    mirror = _mirror_fact_repeats(article, payload)
    home_scope = _home_scope_violations(article, payload)
    terminology = _terminology_violations(article)
    return {"passed": (em_dashes == 0 and not connectors and not banned_words
                       and not house_terms and not pct_no_count
                       and not excess_decimals and not form_label
                       and not repeats and not overused
                       and not no_conditional and not scope_attr
                       and not win_pairs and not toss_emph and not finals
                       and not ko_points and not venue_scope
                       and not mirror and not home_scope and not terminology),
            "em_dashes": em_dashes, "banned_connectors": connectors,
            "banned_words": banned_words, "house_terms": house_terms,
            "pct_without_count": pct_no_count,
            "excess_decimals": excess_decimals,
            "form_label": form_label,
            "verbatim_repeats": repeats,
            "overused_stats": overused,
            "missing_conditional_angle": no_conditional,
            "scope_attribution": scope_attr,
            "win_record_pairs": win_pairs,
            "toss_emphasis": toss_emph,
            "finals_language": finals,
            "knockout_points": ko_points,
            "venue_sample_scope": venue_scope,
            "mirror_facts": mirror,
            "home_scope": home_scope,
            "terminology": terminology}


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
            lines.append(f"  - win percentage without count AND total in "
                         f"the sentence: \"{s}\" -> write it as \"X of the "
                         "N\" (win count = the split times venue_stats."
                         "matches_at_venue_total, rounded; e.g. \"won 10 of "
                         "the 17 T20s here\"), keeping or dropping the "
                         "percentage.")
        for tok in style["excess_decimals"]:
            lines.append(f"  - raw payload precision leaked: {tok} -> round "
                         "to at most one decimal (two only for payload "
                         "economy/strike-rate figures copied exactly).")
        for s in style["form_label"]:
            lines.append(f"  - form-claim label: {s}")
        for s in style["verbatim_repeats"]:
            lines.append(f"  - sentence appears verbatim more than once: "
                         f"\"{s}\" -> keep one occurrence; reword or cut "
                         "the other (a fact appears at most twice, never "
                         "in the same wording).")
        for tok in style["overused_stats"]:
            lines.append(f"  - stat {tok} repeated too much -> a distinctive "
                         "stat appears at most ONCE in Three Key Points and "
                         "at most ONCE elsewhere; cut or replace the extra "
                         "mentions.")
        for s in style["scope_attribution"]:
            lines.append(f"  - scope attribution: {s}")
        for s in style["win_record_pairs"]:
            lines.append(f"  - win-record pair: {s}")
        for s in style["toss_emphasis"]:
            lines.append(f"  - toss emphasis: {s}")
        for s in style["finals_language"]:
            lines.append(f"  - finals framing: {s}")
        for s in style["knockout_points"]:
            lines.append(f"  - standings stage attribution: {s}")
        for s in style["venue_sample_scope"]:
            lines.append(f"  - venue sample scope: {s}")
        for s in style["mirror_facts"]:
            lines.append(f"  - repeated result set: {s} -> one result set is "
                         "ONE fact, whichever side or verb states it: keep a "
                         "single statement per place (at most once in Three "
                         "Key Points, once elsewhere) from the stronger angle "
                         "and cut or replace the other.")
        for s in style["home_scope"]:
            lines.append(f"  - home scope: {s}")
        for s in style["terminology"]:
            lines.append(f"  - terminology: {s}")
        if style["missing_conditional_angle"]:
            lines.append("  - missing the mandatory conditional-angle "
                         "sentence: add exactly ONE sentence of the shape "
                         "'If <key player(s)> misfire, the game tilts to "
                         "<other team>', naming players from the payload's "
                         "players block.")
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


def generate_article(payload: dict, client, mode: str = MODE,
                     author_id: str | None = None) -> tuple[str, dict, dict, int]:
    """Generate + validate, with up to MAX_RETRIES targeted repair rounds.
    author_id selects the voice layer (None = house voice); the validators
    below never see it. Returns (article, number_result, style_result,
    api_calls_used)."""
    payload = _lifecycle_view(payload, mode)
    messages = [
        {"role": "system", "content": build_system_prompt(author_id)},
        {"role": "user", "content": build_user_prompt(payload, mode=mode)},
    ]
    article = _call(client, messages)
    numbers = validate_article(article, payload)
    style = validate_style(article, payload)
    attempts = 1
    while not (numbers["passed"] and style["passed"]) and attempts <= MAX_RETRIES:
        print(f"  attempt {attempts}: numbers="
              f"{'ok' if numbers['passed'] else numbers['violations']} "
              f"style={'ok' if style['passed'] else 'FAIL'} -> repairing")
        messages.append({"role": "assistant", "content": article})
        messages.append({"role": "user", "content": _repair_prompt(numbers, style)})
        article = _call(client, messages)
        numbers = validate_article(article, payload)
        style = validate_style(article, payload)
        attempts += 1
    return article, numbers, style, attempts


def generate_and_save(match_id: int, client, mode: str = MODE,
                      author_id: str | None = None,
                      rotation: AuthorRotation | None = None,
                      ) -> tuple[Path, dict, dict, int, str]:
    """author_id: explicit voice; None -> the rotation's persisted assignment
    for this match_id (dealt now if the match has none yet), so retries and
    the pre_toss/post_toss pair share one author. Pass rotation=None with
    author_id=None to use the default state file."""
    position = None
    if author_id is None:
        rotation = rotation or AuthorRotation()
        author_id, _ = rotation.assign(match_id)
        position = rotation.position(match_id)
    elif rotation is not None and rotation.get(match_id) == author_id:
        position = rotation.position(match_id)
    payload = build_payload(match_id)
    article, numbers, style, attempts = generate_article(
        payload, client, mode, author_id=author_id)
    ok = numbers["passed"] and style["passed"]
    stamp = ("VALIDATION: PASSED" if ok else
             f"FAILED VALIDATION - numbers: {numbers['violations'] or 'ok'} | "
             f"style: em_dashes={style['em_dashes']}, "
             f"connectors={style['banned_connectors'] or 'ok'}, "
             f"words={style['banned_words'] or 'ok'}, "
             f"house_terms={style['house_terms'] or 'ok'}, "
             f"pct_no_count={style['pct_without_count'] or 'ok'}, "
             f"excess_decimals={style['excess_decimals'] or 'ok'}, "
             f"form_label={style['form_label'] or 'ok'}, "
             f"repeats={style['verbatim_repeats'] or 'ok'}, "
             f"overused={style['overused_stats'] or 'ok'}, "
             f"conditional={'MISSING' if style['missing_conditional_angle'] else 'ok'}, "
             f"scope={style['scope_attribution'] or 'ok'}, "
             f"win_pairs={style['win_record_pairs'] or 'ok'}, "
             f"toss_emphasis={style['toss_emphasis'] or 'ok'}, "
             f"finals={style['finals_language'] or 'ok'}, "
             f"ko_points={style['knockout_points'] or 'ok'}, "
             f"venue_scope={style['venue_sample_scope'] or 'ok'}, "
             f"mirror_facts={style['mirror_facts'] or 'ok'}, "
             f"home_scope={style['home_scope'] or 'ok'}, "
             f"terminology={style['terminology'] or 'ok'}")
    ARTICLES_DIR.mkdir(parents=True, exist_ok=True)
    out = ARTICLES_DIR / f"{match_id}_{mode}_draft.md"
    out.write_text(f"<!-- {stamp} | model={MODEL} | mode={mode} | "
                   f"author={author_id} | attempts={attempts} | "
                   f"payload_model={payload['prediction']['model_version']} -->\n\n"
                   + article.rstrip()
                   # DRAFT-ONLY footer, appended AFTER validation (its digits
                   # are metadata, not article numbers); src/publish.py
                   # strips it and guards that it never ships
                   + draft_footer(author_id, position), encoding="utf-8")
    return out, numbers, style, attempts, author_id


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

    import argparse
    ap = argparse.ArgumentParser(description="demo: the three demo matches "
                                 "generated as ONE match day under the "
                                 "author rotation")
    ap.add_argument("--modes", choices=("post_toss", "pre_toss", "both"),
                    default="post_toss")
    ap.add_argument("--reset-authors", action="store_true",
                    help="forget persisted assignments and the deck first "
                         "(a fresh match day)")
    args = ap.parse_args()
    modes = ("post_toss", "pre_toss") if args.modes == "both" else (args.modes,)

    # ONE MATCH DAY: deal the whole day up front, in generation order. The
    # deck guarantees three different profiles; the state file guarantees
    # a retry or the other toss mode of a match gets the same one.
    rotation = AuthorRotation()
    if args.reset_authors:
        rotation.reset()
    dealt = rotation.assign_day([m for _, m in DEMO_MATCHES])
    print("AUTHOR ROTATION - match day assignments "
          f"(state: {rotation.state_path.relative_to(ROOT).as_posix()})")
    for (band, match_id), (_, author, new) in zip(DEMO_MATCHES, dealt):
        print(f"  match {match_id} ({band:10s}) -> {author} "
              f"({profile_display_name(author)}) "
              f"[{'dealt now' if new else 'persisted'}]")
    print(f"  remaining in deck: {rotation.remaining_in_deck() or 'none'}")
    if len({a for _, a, _ in dealt}) < len(dealt):
        print("  WARNING: a profile repeats within the day (persisted "
              "assignments from an earlier run; use --reset-authors for a "
              "fresh day)")

    summary = []
    for (band, match_id), (_, author, _) in zip(DEMO_MATCHES, dealt):
        for mode in modes:
            print("\n" + "=" * 74)
            print(f"GENERATING - {band.upper()} "
                  f"(match_id={match_id}, mode={mode}, author={author})")
            print("=" * 74)
            path, numbers, style, attempts, used = generate_and_save(
                match_id, client, mode, rotation=rotation)
            assert used == author, (used, author)     # persistence contract
            summary.append((match_id, band, mode, used,
                            numbers["passed"] and style["passed"], attempts))
            print(f"saved: {path}  (API calls: {attempts}; author: {used})")
            print(f"numbers: {'PASSED' if numbers['passed'] else 'FAILED'} "
                  f"({numbers['numbers_checked']} distinct numbers checked; "
                  f"violations: {numbers['violations'] or 'none'})")
            print(f"style:   {'PASSED' if style['passed'] else 'FAILED'} "
                  f"(em_dashes: {style['em_dashes']}; "
                  f"connectors: {style['banned_connectors'] or 'none'}; "
                  f"Part E words: {style['banned_words'] or 'none'}; "
                  f"house terms: {style['house_terms'] or 'none'}; "
                  f"pct w/o count+total: {style['pct_without_count'] or 'none'}; "
                  f"excess decimals: {style['excess_decimals'] or 'none'}; "
                  f"form label: {style['form_label'] or 'none'}; "
                  f"verbatim repeats: {style['verbatim_repeats'] or 'none'}; "
                  f"overused stats: {style['overused_stats'] or 'none'}; "
                  f"conditional angle: "
                  f"{'MISSING' if style['missing_conditional_angle'] else 'ok'}; "
                  f"scope attribution: {style['scope_attribution'] or 'none'}; "
                  f"win-record pairs: {style['win_record_pairs'] or 'none'}; "
                  f"toss emphasis: {style['toss_emphasis'] or 'none'}; "
                  f"finals framing: {style['finals_language'] or 'none'}; "
                  f"knockout points: {style['knockout_points'] or 'none'}; "
                  f"venue sample scope: {style['venue_sample_scope'] or 'none'}; "
                  f"mirror facts: {style['mirror_facts'] or 'none'}; "
                  f"home scope: {style['home_scope'] or 'none'}; "
                  f"terminology: {style['terminology'] or 'none'})")
            print("-" * 74)
            print(path.read_text(encoding="utf-8"))

    print("\n" + "=" * 74)
    print("MATCH DAY SUMMARY")
    print("=" * 74)
    print(f"{'match':>6}  {'band':10s}  {'mode':9s}  {'author':9s}  "
          f"{'validation':10s}  calls")
    for match_id, band, mode, author, ok, attempts in summary:
        print(f"{match_id:>6}  {band:10s}  {mode:9s}  {author:9s}  "
              f"{'PASSED' if ok else 'FAILED':10s}  {attempts}")

    # the editor's proof over time: full history + deck state
    print("\n" + format_audit(rotation.audit()))


if __name__ == "__main__":
    main()
