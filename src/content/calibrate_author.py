"""
calibrate_author.py - AUTHOR STYLE PROFILE EXTRACTION (author rotation, step 1).

For each docs/author-styles/author-NN-<name>.md (cleaned real articles by one
author) run the Style Calibration analysis from
docs/human-writing-style-ruleset.md Part 4 - the same analysis that produced
the house profile (src/content/style_profile.md) - and save the result as
src/content/author_profiles/author-NN.md (version-controlled).

WHAT A PROFILE IS (and is not):
    A profile captures VOICE ONLY: sentence rhythm, sentence-length habits,
    openers and closers, register, paragraph architecture, rhetorical
    devices, and ten checkable rules. It never carries facts or entities:
    no teams, players, venues, competitions, scores or statistics from the
    source articles. This is mechanically enforced (leak check below).

    A profile is a LAYER on top of the house rules, never a replacement.
    Every mechanical check in generate_article.py (numbers from the payload,
    scope attribution, banned words, repetition caps, toss_impact language,
    league-vs-format labels) stays author-independent. The profile's own
    section 7 lists the author's habits that those rules override, so the
    generator is told explicitly which habits NOT to reproduce.

MEASURED RHYTHM (mechanical, fed to the analysis):
    The LLM's numbers for sentence rhythm are not trusted to eyeballing.
    Sentence-length distribution, short/long sentence shares, paragraph
    sizes, opener classes, question/exclamation/contraction rates and the
    most common first words are computed here from the prose paragraphs
    (site-template lines such as playing-XI lists and stat one-liners are
    excluded) and handed to the model as the figures to use.

LEAK CHECK (mechanical, post-analysis):
    The profile must not contain: any team name from the article headings,
    any player name from the playing-XI lists, any capitalized two-word
    proper name from the source prose, any 3+-digit number, or any number
    with 2+ decimals. One repair round; still leaking -> the file is written
    with a LEAK CHECK FAILED header and the script exits non-zero.

RUN:
    venv/Scripts/python.exe -m src.content.calibrate_author            # all 8
    venv/Scripts/python.exe -m src.content.calibrate_author 03 07      # some
"""
from __future__ import annotations

import os
import re
import statistics
import sys
from collections import Counter
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
SOURCE_DIR = ROOT / "docs" / "author-styles"
PROFILES_DIR = ROOT / "src" / "content" / "author_profiles"

MODEL = "gpt-4o"
TEMPERATURE = 0.3          # analysis, not prose: little sampling room needed
MAX_TOKENS = 3000
MAX_REPAIRS = 2            # leak-check repair rounds (like the article loop)

# --------------------------------------------------------------------------
# source parsing
# --------------------------------------------------------------------------
_HEADING_RE = re.compile(r"^## Article \d+:\s*(.+?)\s*$", re.MULTILINE)
_XI_LINE_RE = re.compile(r"Playing XI:?\s*$", re.IGNORECASE | re.MULTILINE)


def read_source(path: Path) -> tuple[str, str]:
    """(author display name, article text without the file header)."""
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"^#\s*(.+?)\s+[—–-]+\s+reference articles", raw)
    name = m.group(1).strip() if m else path.stem
    body = raw[raw.find("## Article"):] if "## Article" in raw else raw
    return name, body


def _paragraphs(body: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", body) if p.strip()]


def _is_template_line(p: str) -> bool:
    """Site-structure lines that are not the author's prose: headings,
    playing-XI name lists, one-line stat bullets, 'X to win' lines."""
    if p.startswith("#"):
        return True
    if p.isupper():
        return True
    if _XI_LINE_RE.search(p) or p.endswith(":"):
        return True
    if p.count(",") >= 7 and len(re.findall(r"[.!?]", p)) <= 1:
        return True                                     # comma list of names
    return False


_ANALYSIS_START_RE = re.compile(r"Match Prediction\s*&\s*Analysis", re.IGNORECASE)


def prose_paragraphs(body: str) -> list[str]:
    """Paragraphs of the author's own prose (>= 12 words, not template).
    Each article's key-point one-liners (everything before its 'Match
    Prediction & Analysis' line) are template, not prose, and are skipped."""
    out = []
    in_prose = False
    for p in _paragraphs(body):
        if p.startswith("## Article"):
            in_prose = False                    # new article: back in the header
            continue
        if _ANALYSIS_START_RE.search(p):
            in_prose = True
            continue
        if not in_prose or _is_template_line(p):
            continue
        if len(p.split()) < 12:
            continue
        out.append(re.sub(r"^\d+\.\s+", "", p))
    return out


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", text.strip())
    return [s.strip() for s in parts if s.strip()]


_OPENER_CLASSES = {
    "question": set(),
    "conjunction": {"and", "but", "so", "yet", "or", "nor"},
    "preposition/adverbial": {"with", "in", "on", "at", "after", "before",
                              "despite", "for", "from", "by", "under", "over",
                              "against", "during", "since", "without",
                              "having", "given", "elsewhere", "meanwhile",
                              "however", "still", "then", "now",
                              "here", "there", "incredibly", "interestingly",
                              "unfortunately", "fortunately", "overall",
                              "again", "once", "also", "while", "although",
                              "though", "if", "when", "as", "to"},
    "the/this/these": {"the", "this", "these", "that", "those"},
    "pronoun": {"he", "she", "they", "it", "we", "you", "his", "her",
                "their", "its", "our"},
}


def _opener_class(sentence: str) -> str:
    words = sentence.split()
    w = re.sub(r"[^A-Za-z']", "", words[0]).lower() if words else ""
    if sentence.endswith("?"):
        return "question"
    for cls, vocab in _OPENER_CLASSES.items():
        if w in vocab:
            return cls
    if sentence[:1].isupper():
        return "proper noun / subject"
    return "other"


def rhythm_stats(body: str) -> dict:
    paras = prose_paragraphs(body)
    sents = [s for p in paras for s in split_sentences(p)]
    lens = [len(s.split()) for s in sents]
    if not lens:
        return {}
    lens_sorted = sorted(lens)

    def pct(q):
        return lens_sorted[min(len(lens_sorted) - 1, int(q * len(lens_sorted)))]

    runs = 0
    for i in range(2, len(lens)):
        a, b, c = lens[i - 2], lens[i - 1], lens[i]
        if abs(a - b) <= 3 and abs(b - c) <= 3 and abs(a - c) <= 3:
            runs += 1
    per_para = [len(split_sentences(p)) for p in paras]
    para_dist = Counter(min(n, 5) for n in per_para)
    openers = Counter(_opener_class(s) for s in sents)
    first_words = Counter(re.sub(r"[^A-Za-z']", "", s.split()[0]).lower()
                          for s in sents if s.split())
    n = len(sents)
    contractions = sum(1 for s in sents
                       if re.search(r"\b\w+n't\b|\b\w+'(?:ll|re|ve|d|m)\b", s))
    we = sum(1 for s in sents if re.search(r"\b(?:we|our|us)\b", s, re.I))
    you = sum(1 for s in sents if re.search(r"\byou(?:r)?\b", s, re.I))
    numerals = sum(1 for s in sents if re.search(r"\d", s))
    exclaim = sum(1 for s in sents if s.endswith("!"))
    questions = sum(1 for s in sents if s.endswith("?"))
    return {
        "prose_paragraphs": len(paras),
        "sentences": n,
        "words_mean": round(statistics.mean(lens), 1),
        "words_median": statistics.median(lens),
        "words_sd": round(statistics.pstdev(lens), 1),
        "words_min": min(lens), "words_max": max(lens),
        "words_p10": pct(0.10), "words_p90": pct(0.90),
        "pct_under_8_words": round(100 * sum(l < 8 for l in lens) / n),
        "pct_8_to_15_words": round(100 * sum(8 <= l <= 15 for l in lens) / n),
        "pct_16_to_25_words": round(100 * sum(16 <= l <= 25 for l in lens) / n),
        "pct_over_25_words": round(100 * sum(l > 25 for l in lens) / n),
        "pct_over_35_words": round(100 * sum(l > 35 for l in lens) / n),
        "same_length_runs_of_3_per_100_sentences": round(100 * runs / n, 1),
        "paragraph_sentence_count_pct": {
            ("5+" if k == 5 else str(k)): round(100 * v / len(paras))
            for k, v in sorted(para_dist.items())},
        "opener_class_pct": {k: round(100 * v / n)
                             for k, v in openers.most_common()},
        "top_first_words": [f"{w} ({c})" for w, c in first_words.most_common(12)],
        "pct_sentences_with_contraction": round(100 * contractions / n),
        "pct_sentences_first_person_plural": round(100 * we / n),
        "pct_sentences_second_person": round(100 * you / n),
        "pct_sentences_with_a_numeral": round(100 * numerals / n),
        "questions_per_100_sentences": round(100 * questions / n, 1),
        "exclamations_per_100_sentences": round(100 * exclaim / n, 1),
        "em_dashes_in_source": body.count("—"),
    }


def format_stats(stats: dict) -> str:
    lines = []
    for k, v in stats.items():
        if isinstance(v, dict):
            lines.append(f"- {k}: " + ", ".join(f"{a}: {b}%" for a, b in v.items()))
        elif isinstance(v, list):
            lines.append(f"- {k}: " + ", ".join(v))
        else:
            lines.append(f"- {k}: {v}")
    return "\n".join(lines)


# --------------------------------------------------------------------------
# entity inventory (for the leak check) - from the SOURCE, never the profile
# --------------------------------------------------------------------------
_STOP_CAPS = {
    "The", "This", "That", "These", "Those", "In", "On", "At", "With", "For",
    "From", "By", "After", "Before", "Despite", "But", "And", "So", "Yet",
    "If", "When", "While", "As", "To", "Of", "A", "An", "It", "He", "She",
    "They", "We", "You", "His", "Her", "Their", "Our", "Its", "Both", "All",
    "Match", "Prediction", "Analysis", "Betting", "Tips", "Preview", "Teams",
    "Interesting", "Stats", "Facts", "Predicted", "Playing", "Weather",
    "Conditions", "Pitch", "Report", "Toss", "Winning", "Today", "Bowl",
    "Bat", "Key", "Points", "Expect", "Captain", "Host", "Hosts",
    "Group", "South", "North", "East", "West", "Women", "Men", "Cup",
    "League", "Series", "World", "Premier", "Super", "Blast", "Vitality",
    "Big", "Bash", "Indian", "Hundred", "Trophy", "Final", "Eliminator",
    "Qualifier", "Sunday", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "January", "February", "March", "April", "May",
    "June", "July", "August", "September", "October", "November",
    "December", "Overs", "Powerplay", "Test", "Twenty", "There", "Here",
    "However", "Elsewhere", "Meanwhile", "Incredibly", "Overall", "Also",
    "Still", "Then", "Now", "Again", "Once", "Having", "Given", "Under",
    "Over", "Against", "During", "Since", "Without", "Will", "Can", "Could",
    "Should", "Would", "Has", "Have", "Had", "Is", "Are", "Was", "Were",
    "Not", "No", "Yes", "One", "Two", "Three", "Four", "Five", "Six",
    "Seven", "Eight", "Nine", "Ten", "First", "Second", "Third", "Last",
    "Top", "Best", "Good", "Poor", "Strong", "Only", "Even", "Just",
    "Some", "Many", "Most", "Each", "Every", "Another", "Other", "Such",
    "New", "Old", "Young", "Home", "Away", "Batting", "Bowling", "Fielding",
    "Spin", "Pace", "Fast", "Left", "Right", "Runs", "Wickets", "Balls",
    "Set", "Sub", "Chasing", "Defending", "T", "Kg", "XI", "Predicted",
}


def entity_inventory(body: str) -> dict[str, set[str]]:
    teams: set[str] = set()
    for m in _HEADING_RE.finditer(body):
        head = m.group(1)
        fixture = head.split(",")[0]
        for t in re.split(r"\s+vs?\.?\s+", fixture, flags=re.I):
            t = t.strip()
            if len(t) > 3:
                teams.add(t)
                for w in t.split():
                    if w not in _STOP_CAPS and len(w) > 3 and w[0].isupper():
                        teams.add(w)
    players: set[str] = set()
    paras = _paragraphs(body)
    for i, p in enumerate(paras):
        if _XI_LINE_RE.search(p) and i + 1 < len(paras):
            for nm in paras[i + 1].split(","):
                nm = re.sub(r"\([^)]*\)", "", nm).strip(" .")
                if len(nm.split()) >= 2:
                    players.add(nm)
    bigrams: set[str] = set()
    for a, b in re.findall(r"\b([A-Z][a-zA-Z'\-]+)\s+([A-Z][a-zA-Z'\-]+)\b", body):
        if a in _STOP_CAPS or b in _STOP_CAPS:
            continue
        bigrams.add(f"{a} {b}")
    return {"teams": teams, "players": players, "bigrams": bigrams}


def _profile_sections(profile: str) -> dict[int, str]:
    """{section number: text} split on the '**N. HEADING**' lines."""
    out: dict[int, str] = {}
    cur = 0
    for line in profile.splitlines():
        m = re.match(r"^\*{0,2}(\d)\.\s+[A-Z]{2,}", line)   # bold UPPERCASE heads only
        if m:
            cur = int(m.group(1))
            out[cur] = ""
            continue
        if cur:
            out[cur] += line + "\n"
    return out


def _banned_vocab_recommended(profile: str) -> list[str]:
    """A profile must never steer the writer toward banned vocabulary: the
    'reaches for' list (section 2, bullets not about avoidance) and the
    TEN RULES (section 6, incl. their examples) are scanned against the
    house lists. Section 7 (conflicts) and the 'avoids' bullet may name
    banned words - that is their job."""
    from src.content.prompt_template import (BANNED_CONNECTORS,
                                             BANNED_HOUSE_TERMS, BANNED_WORDS)
    secs = _profile_sections(profile)
    scan = [l for l in secs.get(2, "").splitlines()
            if l.strip() and not re.search(r"\bavoid", l, re.I)]
    scan.append(secs.get(6, ""))
    text = "\n".join(scan)
    hits = []
    for phrase in BANNED_CONNECTORS:
        if re.search(r"\b" + r"\s+".join(map(re.escape, phrase.split())) + r"\b",
                     text, re.I):
            hits.append(f"recommends banned word: {phrase}")
    for name, pat in list(BANNED_WORDS) + list(BANNED_HOUSE_TERMS):
        if re.search(pat, text, re.I):
            hits.append(f"recommends banned word: {name}")
    for name, pat in _HEDGE_PATTERNS + _PROFILE_ONLY_BANS:
        if re.search(pat, text, re.I):
            hits.append(f"recommends banned hedge/connector: {name}")
    for name, pat in _ANTI_HOUSE_RULES:
        if re.search(pat, secs.get(6, ""), re.I):
            hits.append(f"rule contradicts a house rule: {name}")
    return hits


# TEN RULES that would instruct the writer AGAINST a mandatory house rule
# (contractions everywhere, short-sentence bursts and fragments, a stated
# position per section). They belong in section 7 as conflicts, never in
# section 6 as rules - checked mechanically, dropped as a last resort.
_ANTI_HOUSE_RULES = [
    ("no contractions",
     r"\b(?:no|without|avoid(?:s|ing)?|never\s+use[sd]?|zero|minimal|"
     r"few|rarely\s+use[sd]?)\s+(?:\w+\s+){0,2}contractions?\b"
     r"|\bcontractions?\s+(?:are\s+)?(?:avoided|absent|not\s+used)\b"
     r"|\bno\s+contractions\b"),
    ("no short sentences / fragments",
     r"\b(?:no|without|avoid(?:s|ing)?|never)\s+(?:\w+\s+){0,3}"
     r"(?:sentences?\s+under\s+\d+\s+words|short\s+sentences?|fragments?)\b"
     r"|\bsentences?\s+under\s+\d+\s+words\b[^.\n]{0,20}\b(?:avoid|never|none)\b"),
    ("no stated opinion",
     r"\b(?:no|without|avoid(?:s|ing)?|never|minimal)\s+(?:\w+\s+){0,2}"
     r"(?:personal\s+|stated\s+|direct\s+)?opinions?\b"
     r"|\bopinions?\s+(?:are\s+)?(?:avoided|absent|never\s+stated)\b"),
]


_NUM_EXAMPLE_RE = re.compile(
    r"\s*\*?_?\(?Example:?\s*[\"“][^\"”]*\d[^\"”]*[\"”]\.?\)?_?\*?",
    re.IGNORECASE)


def strip_numeric_examples(profile: str) -> tuple[str, int]:
    """LAST RESORT after the repair rounds: an illustration inside the TEN
    RULES that still carries an invented figure loses the illustration
    (the rule itself stays). Returns (text, examples removed)."""
    out, count, cur = [], 0, 0
    for line in profile.splitlines():
        m = re.match(r"^\*{0,2}(\d)\.\s+[A-Z]{2,}", line)
        if m:
            cur = int(m.group(1))
        if cur == 6:
            line, k = _NUM_EXAMPLE_RE.subn("", line)
            count += k
        out.append(line)
    return "\n".join(out), count


def drop_anti_house_rules(profile: str) -> tuple[str, list[str]]:
    """LAST RESORT after the repair rounds: remove any remaining section-6
    rule that contradicts a house rule and record it in section 7 as a
    conflict. Deterministic, so the saved profile never instructs against
    the house. Returns (text, dropped rule lines)."""
    lines = profile.splitlines()
    out, dropped, cur = [], [], 0
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\*{0,2}(\d)\.\s+[A-Z]{2,}", line)
        if m:
            cur = int(m.group(1))
        if cur == 6 and re.match(r"^\s*\d+\.\s", line) \
                and any(re.search(p, line, re.I) for _, p in _ANTI_HOUSE_RULES):
            dropped.append(line.strip())
            # swallow the rule's indented continuation / example lines
            while i + 1 < len(lines) and lines[i + 1].strip() \
                    and not re.match(r"^\s*\d+\.\s|^\*{0,2}\d\.\s+[A-Z]{2,}",
                                     lines[i + 1]):
                i += 1
            i += 1
            continue
        out.append(line)
        i += 1
    if dropped:
        out.append("- Rules dropped from section 6 because they contradict a "
                   "house rule (the house rule wins; the habit is a conflict, "
                   "not an instruction):")
        out.extend(f"  - {d}" for d in dropped)
    return "\n".join(out), dropped


# hedges/connectors the ruleset bans (B4, E) that the article-level regex
# lists don't carry verbatim - a profile must not recommend them either
_PROFILE_ONLY_BANS = [
    ("as previously mentioned / as mentioned",
     r"\bas\s+(?:previously\s+)?(?:mentioned|stated|noted|discussed)\b"),
    ("it will be interesting", r"\bit\s+will\s+be\s+interesting\b"),
]


def banned_vocabulary_summary() -> str:
    """One compact line of every banned word/phrase, for the prompts."""
    from src.content.prompt_template import (BANNED_CONNECTORS,
                                             BANNED_HOUSE_TERMS, BANNED_WORDS)
    names = list(BANNED_CONNECTORS) + [n for n, _ in BANNED_WORDS] \
        + [n for n, _ in BANNED_HOUSE_TERMS
           if n not in ("meta-prediction talk", "match-number appositive",
                        "missing-data mention", "no-data mention",
                        "model mention", "rated/considered low-high")] \
        + [n for n, _ in _HEDGE_PATTERNS] + [n for n, _ in _PROFILE_ONLY_BANS]
    return ", ".join(names)


# --------------------------------------------------------------------------
# deterministic vocabulary scrub (descriptive text only)
# --------------------------------------------------------------------------
# gpt-4o describes habits with the very words the house bans ("often opens
# with", "to highlight strengths", "ensure cohesion") and, asked to remove
# one, swaps in another. Descriptive synonyms are safe to substitute
# mechanically, so the scrub does it: sections 1-6, never section 7 (the
# conflicts list must name the banned words) and never an "avoids" bullet.
_SCRUB_MAP = [
    (r"\boften\b", "usually"),
    (r"\bhighlighting\b", "pointing to"), (r"\bhighlights\b", "points to"),
    (r"\bhighlighted\b", "pointed to"), (r"\bhighlight\b", "point to"),
    (r"\bensuring\b", "keeping"), (r"\bensures\b", "keeps"),
    (r"\bensured\b", "kept"), (r"\bensure\b", "keep"),
    (r"\bcrucial(?:ly)?\b", "central"), (r"\bpivotal\b", "central"),
    (r"\bvital(?:ly)?\b", "essential"), (r"\brobust\b", "solid"),
    (r"\bcomprehensive(?:ly)?\b", "thorough"), (r"\bdynamic\b", "lively"),
    (r"\bnotable\b", "noteworthy"), (r"\bnotably\b", "in particular"),
    (r"\bprolific(?:ally)?\b", "high-scoring"), (r"\bboasts?\b", "has"),
    (r"\bboasting\b", "having"), (r"\bsuggests\b", "indicates"),
    (r"\bsuggest(?:ed|ing)?\b", "indicate"), (r"\bimplies\b", "means"),
    (r"\bimpl(?:y|ied|ying)\b", "mean"), (r"\bpoised\s+to\b", "set to"),
    (r"\breveals?\b", "shows"), (r"\brevealing\b", "showing"),
    (r"\breflect(?:s|ing)?\b", "shows"), (r"\bimpeccabl(?:e|y)\b", "flawless"),
    (r"\berratic(?:ally)?\b", "inconsistent"), (r"\bmarginal(?:ly)?\b", "narrow"),
    (r"\btestament\b", "proof"), (r"\blandscape\b", "picture"),
    (r"\bleverag(?:e|es|ed|ing)\b", "use"), (r"\bdelv(?:e|es|ed|ing)\b", "dig"),
    (r"\bfoster(?:s|ed|ing)?\b", "build"), (r"\bfacilitat(?:e|es|ed|ing)\b", "enable"),
    (r"\butili[sz](?:e|es|ed|ing)\b", "use"), (r"\bstreamlin(?:e|es|ed|ing)\b", "simplify"),
    (r"\bunderscor(?:e|es|ed|ing)\b", "stress"), (r"\bharness(?:es|ed|ing)?\b", "use"),
    (r"\bembark(?:s|ed|ing)?\b", "start"), (r"\bseamless(?:ly)?\b", "smooth"),
    (r"\bmoreover\b|\bfurthermore\b|\badditionally\b|\bin\s+addition\b", "also"),
    (r"\bimportantly\b", "in particular"), (r"\bthat\s+said\b", "still"),
    (r"\bin\s+conclusion\b", "finally"), (r"\bkey\s+factor\b", "key element"),
    (r"\bsetting\s+the\s+tone\b", "setting the terms"),
    (r"\bset(?:s)?\s+the\s+tone\b", "sets the terms"),
]


def scrub_descriptive_vocab(profile: str) -> tuple[str, int]:
    """Substitute banned vocabulary in the DESCRIPTIVE text of sections
    1-6 (case-preserving on the first letter). Returns (text, count)."""
    out, count, cur = [], 0, 0
    for line in profile.splitlines():
        m = re.match(r"^\*{0,2}(\d)\.\s+[A-Z]{2,}", line)
        if m:
            cur = int(m.group(1))
        if cur == 7 or re.search(r"\bavoid", line, re.I) or not (1 <= cur <= 6):
            out.append(line)
            continue
        for pat, rep in _SCRUB_MAP:
            def _sub(mm, rep=rep):
                w = mm.group(0)
                return rep[0].upper() + rep[1:] if w[0].isupper() else rep
            line, k = re.subn(pat, _sub, line, flags=re.IGNORECASE)
            count += k
        out.append(line)
    return "\n".join(out), count


def leak_check(profile: str, inv: dict[str, set[str]]) -> list[str]:
    leaks = []
    for kind in ("teams", "players", "bigrams"):
        for ent in sorted(inv[kind]):
            if re.search(r"(?<![A-Za-z])" + re.escape(ent) + r"(?![A-Za-z])",
                         profile):
                leaks.append(f"{kind[:-1]}: {ent}")
    leaks.extend(_banned_vocab_recommended(profile))
    for tok in re.findall(r"\b\d+\.\d{2,}\b", profile):
        leaks.append(f"statistic: {tok}")
    # 3+-digit numbers are source figures (runs, strike rates) - except the
    # "per 100 sentences" rate phrasing that the measured stats use
    for m in re.finditer(r"(?<![\d.])(\d{3,})(?![\d.])", profile):
        ctx = profile[max(0, m.start() - 4):m.end() + 10].lower()
        if m.group(1) == "100" and ("per 100" in ctx or "100 sentence" in ctx):
            continue
        leaks.append(f"number: {m.group(1)}")
    return sorted(set(leaks))


# --------------------------------------------------------------------------
# measured conflicts with the house rules (mechanical, fed to the analysis)
# --------------------------------------------------------------------------
_HEDGE_PATTERNS = [
    ("it will be interesting to see", r"\bit\s+will\s+be\s+interesting\s+to\s+see\b"),
    ("it is worth noting / mentioning", r"\bit\s+is\s+worth\s+(?:noting|mentioning)\b"),
    ("in many cases / generally speaking",
     r"\bin\s+many\s+cases\b|\bgenerally\s+speaking\b"),
    ("remains to be seen", r"\bremains\s+to\s+be\s+seen\b"),
]
_PCT_WIN_RE = re.compile(r"\d+(?:\.\d+)?\s*%[^.!?\n]{0,40}\b(?:win|won|success)",
                         re.IGNORECASE)


def measured_conflicts(body: str) -> list[str]:
    """Counts, in the author's prose, of every habit the house rules
    override - so section 7 of the profile is evidence, not opinion."""
    from src.content.prompt_template import (BANNED_CONNECTORS,
                                             BANNED_HOUSE_TERMS, BANNED_WORDS)
    prose = "\n".join(prose_paragraphs(body))
    sents = split_sentences(prose)
    n = max(1, len(sents))
    out = []
    em = body.count("—")
    out.append(f"em dashes: {em}")
    hits = []
    for phrase in BANNED_CONNECTORS:
        k = len(re.findall(r"\b" + r"\s+".join(map(re.escape, phrase.split()))
                           + r"\b", prose, flags=re.IGNORECASE))
        if k:
            hits.append(f"{phrase} x{k}")
    out.append("banned connectors: " + (", ".join(hits) or "none"))
    for label, table in (("banned words (Part E)", BANNED_WORDS),
                         ("house-banned terms", BANNED_HOUSE_TERMS)):
        hits = []
        for name, pat in table:
            k = len(re.findall(pat, prose, flags=re.IGNORECASE))
            if k:
                hits.append(f"{name} x{k}")
        out.append(f"{label}: " + (", ".join(hits) or "none"))
    hits = []
    for name, pat in _HEDGE_PATTERNS:
        k = len(re.findall(pat, prose, flags=re.IGNORECASE))
        if k:
            hits.append(f"{name} x{k}")
    out.append("hedging chains: " + (", ".join(hits) or "none"))
    out.append(f"win rates written as percentages: {len(_PCT_WIN_RE.findall(prose))}")
    contractions = sum(1 for s in sents
                       if re.search(r"\b\w+n't\b|\b\w+'(?:ll|re|ve|d|m)\b", s))
    out.append(f"sentences with a contraction: {round(100 * contractions / n)}% "
               "(house rule: contractions throughout)")
    short = sum(1 for s in sents if len(s.split()) < 8)
    out.append(f"sentences under 8 words: {round(100 * short / n)}% "
               "(house rule: one per paragraph of 3+ sentences)")
    out.append(f"playing-XI lists in the texts: {len(_XI_LINE_RE.findall(body))}; "
               f"weather blocks: {len(re.findall(r'Weather Conditions', body))} "
               "(no payload data for either: never written)")
    return out


# --------------------------------------------------------------------------
# the calibration prompt (ruleset Part 4, verbatim, plus voice-only addenda)
# --------------------------------------------------------------------------
PART4_PROMPT = """Below are {n} texts written by the author whose voice I want to replicate.

Analyse them and produce a STYLE PROFILE with these sections:

1. SENTENCE RHYTHM — average length, range, how variance is distributed, typical
   opening constructions.
2. LEXICAL SIGNATURE — 15 words or phrases this author reaches for repeatedly, and
   10 common words they conspicuously avoid.
3. REGISTER — formality level, how they address the reader, how much opinion they
   allow themselves, whether they use humour and of what kind.
4. PARAGRAPH ARCHITECTURE — typical length, how paragraphs open and close, how they
   transition between them.
5. DEVICES — recurring rhetorical moves (rhetorical questions, asides, callbacks,
   understatement, direct challenges to the reader).
6. TEN RULES — ten concrete, checkable instructions that would let another writer
   reproduce this voice.

Rules must be specific and testable. Not "writes conversationally" but "opens roughly
one paragraph in four with a question, answers it in the next sentence".

Do not summarise the content of the texts. Only the voice."""

ADDENDA = """
ADDITIONAL CONSTRAINTS FOR THIS PROFILE (they override nothing above; they narrow it):

A. VOICE ONLY, NEVER ENTITIES. The profile must contain NO team names, NO player
   names, NO venue names, NO competition or league names, NO scores and NO
   statistics from the texts. Describe habits abstractly ("names the captain
   in the first sentence of a team preview", "quotes a bowler's economy in
   brackets") without the names or figures. Any leaked entity fails the
   profile mechanically.

B. MEASURED RHYTHM. The figures below were computed mechanically from the
   author's prose paragraphs (site-template lines such as playing-XI lists and
   one-line stat bullets excluded). Use THESE figures in sections 1 and 4; do
   not estimate your own.

{stats}

C. SITE TEMPLATE IS NOT VOICE. The texts share a site template (key-point
   one-liners, "Predicted Playing XI" lists, "Interesting Stats" bullets,
   weather blocks, "X to win" lines). Ignore the template's existence; analyse
   how THIS author writes prose within it: openers, closers, how the verdict
   is phrased, how a player is introduced, how a stat is attached to a claim.

D. THE TEN RULES will be handed to a writer who works from a data payload under
   a fixed section structure and a fixed set of house rules. So each rule must
   be about prose habits only: sentence shape, openers, closers, how claims
   are attached to numbers, register, opinion, devices. No rules about playing
   XIs, team news, weather, odds, betting tips, or facts the writer may not
   have. Each rule must be checkable by reading a draft.
   - At most THREE of the ten may be pure frequency targets ("one sentence in
     four under 12 words"). The other seven describe a CONSTRUCTION: the shape
     of an opener, how a player is introduced, how a stat is attached to a
     claim, how a preview paragraph closes, how the verdict is phrased. Each
     of those seven carries a one-line invented illustration in the author's
     manner using placeholder entities only ("Team A", "the opener", "their
     left-arm quick") and NO DIGITS AT ALL (write "a big score", "a strong
     strike rate", "several wickets" - never an invented number).
   - NEVER make a rule out of a habit that conflicts with the house rules
     (section 7 below). "No contractions", "no sentences under 8 words", "no
     stated opinion" and the like are conflicts, not rules: they go in
     section 7 and nowhere else. The house rules mandate contractions,
     short-sentence bursts, fragments and a stated position per section.
   - BANNED VOCABULARY (mechanically checked in sections 2 and 6): none of
     these words or phrases, in any inflection, may appear in the "reaches
     for" list, in a rule, or in a rule's example. They may appear only in
     the "avoids" bullet and in section 7: {banned}

E. Add a seventh section:

7. CONFLICTS WITH HOUSE RULES — the author's habits that the house rules
   override. List every habit of this author that matches one of these house
   rules, so the writer knows NOT to reproduce it: em dashes (banned); the
   words moreover / furthermore / additionally / notably / importantly /
   in addition / that said / in conclusion (banned); delve / leverage / crucial /
   vital / pivotal / robust / comprehensive / dynamic / landscape / testament
   (banned); boasts / suggests / implies / often / poised to / reveals /
   highlighting / reflecting / prime / prolific / notable / marginal /
   impeccable / erratic (house-banned); hedging chains ("it is worth noting",
   "it will be interesting to see"); win records as percentages for a handful
   of games (house writes counts: "won 4 of their last 5"); playing-XI, team
   news, weather or odds talk (no payload data); summary conclusions that
   restate the intro (banned); calling the toss decisive without data; few or
   no contractions (house mandates them); few or no sentences under 8 words
   and no fragments (house mandates bursts); no stated opinion (house mandates
   one per section).
   The counts below were measured mechanically in this author's prose. Every
   non-zero count is a conflict and MUST be listed with its count; "none
   observed" is allowed only where the count is zero or the house threshold
   is met. Keep the section itemised, one line per habit.

   MEASURED CONFLICTS:
{conflicts}

OUTPUT FORMAT: Markdown. Start with the line "**STYLE PROFILE — {name}**", then
the seven numbered sections in order, each as a bold heading followed by short
bullet points. No preamble, no closing remarks.
"""


def build_messages(name: str, body: str, stats: dict) -> list[dict]:
    n = len(_HEADING_RE.findall(body))
    conflicts = "\n".join(f"   - {c}" for c in measured_conflicts(body))
    user = (PART4_PROMPT.format(n=n)
            + "\n"
            + ADDENDA.format(stats=format_stats(stats), name=name,
                             conflicts=conflicts,
                             banned=banned_vocabulary_summary())
            + "\n\n=== SAMPLE TEXTS ===\n\n" + body)
    return [
        {"role": "system",
         "content": "You are a prose-style analyst. You extract the VOICE of a "
                    "writer (rhythm, register, devices) as explicit, testable "
                    "rules. You never restate the content of the texts and you "
                    "never carry over names or figures from them."},
        {"role": "user", "content": user},
    ]


def _client():
    load_dotenv(ROOT / ".env")
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key or key.startswith("your_"):
        return None
    from openai import OpenAI
    return OpenAI(api_key=key)


def _call(client, messages):
    resp = client.chat.completions.create(
        model=MODEL, temperature=TEMPERATURE,
        max_completion_tokens=MAX_TOKENS, messages=messages)
    return (resp.choices[0].message.content or "").strip()


def calibrate(path: Path, client) -> tuple[Path, list[str]]:
    author_id = path.stem[:9]                       # "author-NN"
    name, body = read_source(path)
    stats = rhythm_stats(body)
    inv = entity_inventory(body)
    messages = build_messages(name, body, stats)
    profile, scrubbed = scrub_descriptive_vocab(_call(client, messages))
    if scrubbed:
        print(f"  scrub: {scrubbed} descriptive banned word(s) substituted")
    leaks = leak_check(profile, inv)
    rounds = 0
    while leaks and rounds < MAX_REPAIRS:
        rounds += 1
        print(f"  leak check: {len(leaks)} hit(s) -> repair round {rounds}: {leaks}")
        messages.append({"role": "assistant", "content": profile})
        messages.append({"role": "user", "content":
                         "The profile leaked source entities or figures, or "
                         "recommends house-banned vocabulary. Fix every item "
                         "below and change nothing else: describe a leaked "
                         "entity abstractly; drop a banned word from the "
                         "'reaches for' list and from any rule or example "
                         "(such a word belongs only in section 7, as a "
                         "conflict). Do NOT replace a banned word with "
                         "another word from this list (any inflection): "
                         + banned_vocabulary_summary()
                         + ". Rule examples carry NO digits at all. A rule "
                         "that contradicts a house rule (no contractions, no "
                         "short sentences or fragments, no stated opinion) is "
                         "REMOVED from section 6 and listed in section 7 as a "
                         "conflict; replace it with a construction rule so "
                         "there are still ten. Return the full profile.\n"
                         + "\n".join(f"  - {x}" for x in leaks)})
        profile, _ = scrub_descriptive_vocab(_call(client, messages))
        leaks = leak_check(profile, inv)
    if any(l.startswith("rule contradicts") for l in leaks):
        profile, dropped = drop_anti_house_rules(profile)
        print(f"  dropped {len(dropped)} anti-house rule(s) into section 7: "
              f"{dropped}")
        leaks = leak_check(profile, inv)
    if any(l.startswith(("number:", "statistic:")) for l in leaks):
        profile, k = strip_numeric_examples(profile)
        print(f"  stripped {k} rule example(s) carrying invented figures")
        leaks = leak_check(profile, inv)
    status = "LEAK CHECK: PASSED" if not leaks else f"LEAK CHECK FAILED: {leaks}"
    header = (
        f"<!--\n{author_id}.md - AUTHOR VOICE profile ({name}) for the content "
        f"generator.\n\n"
        f"Extracted via the Style Calibration prompt (docs/human-writing-style-"
        f"ruleset.md Part 4)\nfrom {path.relative_to(ROOT).as_posix()} by "
        f"src/content/calibrate_author.py\non {date.today().isoformat()} "
        f"(model={MODEL}, temperature={TEMPERATURE}).\n\n"
        f"LAYERING RULE: this profile is a voice layer ON TOP of the house rules, "
        f"never a\nreplacement. All mechanical checks in generate_article.py "
        f"apply unchanged under\nthis voice; where a habit below conflicts with "
        f"a mechanical rule, the rule wins.\nVoice only: no facts, no entities "
        f"(mechanically checked).\n\n{status}\n-->\n\n"
    )
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    out = PROFILES_DIR / f"{author_id}.md"
    out.write_text(header + profile + "\n", encoding="utf-8")
    return out, leaks


def main(argv: list[str]) -> int:
    client = _client()
    if client is None:
        print("STOP: no usable OPENAI_API_KEY in .env")
        return 1
    sources = sorted(SOURCE_DIR.glob("author-*.md"))
    if argv:
        want = {a.zfill(2) for a in argv}
        sources = [s for s in sources if s.stem[7:9] in want]
    failed = []
    for src in sources:
        print(f"\n== {src.name}")
        stats = rhythm_stats(read_source(src)[1])
        print(f"  measured: {stats.get('sentences')} sentences, mean "
              f"{stats.get('words_mean')} words (sd {stats.get('words_sd')}), "
              f"<8w {stats.get('pct_under_8_words')}%, >25w "
              f"{stats.get('pct_over_25_words')}%")
        out, leaks = calibrate(src, client)
        print(f"  saved: {out.relative_to(ROOT).as_posix()}  "
              f"({'leak check PASSED' if not leaks else 'LEAK CHECK FAILED'})")
        if leaks:
            failed.append((src.name, leaks))
    if failed:
        print("\nFAILED leak check:", failed)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
