"""
author_rotation.py - AUTHOR STYLE ROTATION (shuffled-deck, persisted per match).

Replaces the single house voice with N rotating author voices so that
articles generated on the same match day never share a style. Voice only:
the mechanical checks in generate_article.py are author-independent.

PROFILES
    src/content/author_profiles/author-NN.md (version-controlled; produced
    by calibrate_author.py). A profile id is the file stem ("author-03").
    load_profile() strips the leading HTML header comment and returns the
    profile text that prompt_template injects as the AUTHOR VOICE block.

ROTATION (no-repeat shuffle)
    A deck is a shuffled order of all profile ids. Matches are dealt one
    profile each in generation order; the deck is reshuffled ONLY when it
    is exhausted (or when the profile set on disk changed - a new deck is
    the only sensible answer to a profile being added or removed). So any
    N consecutive assignments are N distinct profiles: same-day matches
    never share a style unless there are more matches than profiles.
    BOUNDARY GUARD: when a fresh deck is shuffled, its first card must not
    equal the last card dealt from the old deck (otherwise two consecutive
    matches - possibly the same day - would share a style at the seam).

PERSISTENCE
    data/state/author_assignments.json (gitignored working state, like the
    track record: never commit-back; in CI it rides the cache/artifact).
    The assignment is keyed by match_id, so retries, repair rounds and the
    pre_toss -> post_toss pair of the same match always get the same
    profile. Writes are atomic (temp file + os.replace).

    {
      "version": 1,
      "deck": {"order": ["author-05", ...], "next": 3, "shuffled_at": "..."},
      "last_dealt": "author-02",
      "assignments": {"8731": {"author": "author-05", "assigned_at": "...",
                               "day": "2026-09-26", "deck_shuffled_at": "..."}}
    }

    Iteration 5b additions (editor's verdict): every assignment records its
    deck position ("deck_position", "deck_size") and a global sequence number
    ("seq"); every shuffled deck is appended to "decks" (history), so the
    rotation can be AUDITED over time. Records written before 5b carry
    neither; their position is derived from the deck they were dealt from.

DRAFT FOOTER (draft-only metadata)
    draft_footer() renders the line generate_and_save appends to every draft:
        ---
        NOTE: Written in author style: author-07 (Manish K.) | rotation deck position 3/8
    It exists so the editor can check the rotation by eye. It is NEVER
    published: src/publish.py strips it mechanically and its guard refuses
    any text that still carries it (or any author id / draft stamp).

AUDIT
    venv/Scripts/python.exe -m src.content.author_rotation audit [--json]
    prints the assignment history (seq, match_id, day, author, deck
    position), a per-deck cycle check (every deck deals all profiles before
    any repeat; no back-to-back repeat at a deck seam) and the current deck.

RANDOMNESS
    random.SystemRandom by default. AUTHOR_ROTATION_SEED (env) or the rng
    argument makes a run reproducible (tests, demos).
"""
from __future__ import annotations

import json
import os
import random
import re
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROFILES_DIR = ROOT / "src" / "content" / "author_profiles"
STATE_PATH = ROOT / "data" / "state" / "author_assignments.json"

_PROFILE_ID_RE = re.compile(r"^author-\d{2}$")

# Draft-only footer. FOOTER_MARKER is what src/publish.py strips and guards.
FOOTER_SEPARATOR = "---"
FOOTER_MARKER = "NOTE: Written in author style:"
HOUSE_FOOTER_MARKER = "NOTE: Written in house voice"


# --------------------------------------------------------------------------
# profiles
# --------------------------------------------------------------------------
def list_profiles(profiles_dir: Path = PROFILES_DIR) -> list[str]:
    """Sorted profile ids ("author-01", ...) found on disk."""
    if not profiles_dir.exists():
        return []
    return sorted(p.stem for p in profiles_dir.glob("author-*.md")
                  if _PROFILE_ID_RE.match(p.stem))


def profile_path(author_id: str, profiles_dir: Path = PROFILES_DIR) -> Path:
    if not _PROFILE_ID_RE.match(author_id or ""):
        raise ValueError(f"bad author id {author_id!r} (expected 'author-NN')")
    return profiles_dir / f"{author_id}.md"


def load_profile(author_id: str, profiles_dir: Path = PROFILES_DIR) -> str:
    """Profile text without the header comment (what the prompt injects)."""
    raw = profile_path(author_id, profiles_dir).read_text(encoding="utf-8")
    return re.sub(r"^<!--.*?-->\s*", "", raw, flags=re.DOTALL).strip()


def profile_display_name(author_id: str,
                         profiles_dir: Path = PROFILES_DIR) -> str:
    """Author display name from the profile's first line, else the id."""
    text = load_profile(author_id, profiles_dir)
    m = re.match(r"\*\*STYLE PROFILE\s*[—–-]\s*(.+?)\*\*", text)
    return m.group(1).strip() if m else author_id


# --------------------------------------------------------------------------
# rotation
# --------------------------------------------------------------------------
def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _rng_from_env() -> random.Random:
    seed = os.environ.get("AUTHOR_ROTATION_SEED")
    if seed:
        return random.Random(int(seed))
    return random.SystemRandom()


class AuthorRotation:
    """Shuffled-deck dealer with a per-match_id memory."""

    def __init__(self, state_path: Path = STATE_PATH,
                 profiles: list[str] | None = None,
                 rng: random.Random | None = None):
        self.state_path = Path(state_path)
        self.profiles = list(profiles) if profiles is not None else list_profiles()
        if not self.profiles:
            raise RuntimeError(
                f"no author profiles found in {PROFILES_DIR} - run "
                "src/content/calibrate_author.py first")
        self.rng = rng or _rng_from_env()
        self.state = self._load()

    # ---- state -----------------------------------------------------------
    def _empty(self) -> dict:
        return {"version": 1, "deck": {"order": [], "next": 0,
                                       "shuffled_at": None},
                "last_dealt": None, "assignments": {},
                "decks": [], "seq": 0}

    def _load(self) -> dict:
        if not self.state_path.exists():
            return self._empty()
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return self._empty()
        base = self._empty()
        base.update({k: v for k, v in state.items() if k in base})
        # pre-5b state: seed the deck history with the live deck
        deck = base["deck"]
        if not base["decks"] and deck.get("order"):
            base["decks"] = [{"shuffled_at": deck.get("shuffled_at"),
                              "order": list(deck["order"])}]
        if not base["seq"]:
            base["seq"] = len(base["assignments"])
        return base

    def _save(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=self.state_path.parent,
                                   prefix=".author_assignments.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(self.state, fh, indent=2, sort_keys=True)
            os.replace(tmp, self.state_path)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)

    def reset(self) -> None:
        """Forget every assignment and the deck (a fresh match day)."""
        self.state = self._empty()
        self._save()

    # ---- deck ------------------------------------------------------------
    def _deck_exhausted(self) -> bool:
        deck = self.state["deck"]
        order = deck.get("order") or []
        if not order or deck.get("next", 0) >= len(order):
            return True
        # the profile set changed on disk -> the old deck is meaningless
        return set(order) != set(self.profiles)

    def _reshuffle(self) -> None:
        order = list(self.profiles)
        self.rng.shuffle(order)
        last = self.state.get("last_dealt")
        if len(order) > 1 and order[0] == last:
            j = self.rng.randrange(1, len(order))          # boundary guard
            order[0], order[j] = order[j], order[0]
        shuffled_at = _now()
        # two reshuffles inside one second must stay distinguishable
        if any(d.get("shuffled_at") == shuffled_at
               for d in self.state.get("decks") or []):
            shuffled_at = f"{shuffled_at}#{len(self.state['decks'])}"
        self.state["deck"] = {"order": order, "next": 0,
                              "shuffled_at": shuffled_at}
        self.state.setdefault("decks", []).append(
            {"shuffled_at": shuffled_at, "order": list(order)})

    def _deal(self) -> str:
        if self._deck_exhausted():
            self._reshuffle()
        deck = self.state["deck"]
        author = deck["order"][deck["next"]]
        deck["next"] += 1
        self.state["last_dealt"] = author
        return author

    # ---- public API ------------------------------------------------------
    def get(self, match_id: int | str) -> str | None:
        rec = self.state["assignments"].get(str(match_id))
        return rec["author"] if rec else None

    def assign(self, match_id: int | str,
               day: str | None = None) -> tuple[str, bool]:
        """The profile for this match: the persisted one if it exists (a
        retry, or the other toss mode of the same match), else the next
        card of the deck. Returns (author_id, newly_dealt)."""
        key = str(match_id)
        existing = self.state["assignments"].get(key)
        if existing:
            return existing["author"], False
        author = self._deal()
        deck = self.state["deck"]
        self.state["seq"] = int(self.state.get("seq") or 0) + 1
        self.state["assignments"][key] = {
            "author": author,
            "assigned_at": _now(),
            "day": day or date.today().isoformat(),
            "deck_shuffled_at": deck["shuffled_at"],
            "deck_position": deck["next"],           # 1-based, after the deal
            "deck_size": len(deck["order"]),
            "seq": self.state["seq"],
        }
        self._save()
        return author, True

    def assign_day(self, match_ids: list[int | str],
                   day: str | None = None) -> list[tuple[str, str, bool]]:
        """Deal a whole match day in generation order.
        Returns [(match_id, author_id, newly_dealt), ...]."""
        return [(str(m), *self.assign(m, day)) for m in match_ids]

    def remaining_in_deck(self) -> list[str]:
        deck = self.state["deck"]
        if self._deck_exhausted():
            return []
        return list(deck["order"][deck["next"]:])

    # ---- audit -----------------------------------------------------------
    def _deck_order(self, shuffled_at) -> list[str] | None:
        for d in self.state.get("decks") or []:
            if d.get("shuffled_at") == shuffled_at:
                return list(d.get("order") or [])
        if self.state["deck"].get("shuffled_at") == shuffled_at:
            return list(self.state["deck"].get("order") or [])
        return None

    def position(self, match_id: int | str) -> tuple[int, int] | None:
        """(deck position, deck size) of this match's card, 1-based.
        Recorded at deal time; derived from the deck history for pre-5b
        records (a deck holds each profile once, so the index is exact)."""
        rec = self.state["assignments"].get(str(match_id))
        if not rec:
            return None
        if rec.get("deck_position") and rec.get("deck_size"):
            return int(rec["deck_position"]), int(rec["deck_size"])
        order = self._deck_order(rec.get("deck_shuffled_at"))
        if order and rec["author"] in order:
            return order.index(rec["author"]) + 1, len(order)
        return None

    def history(self) -> list[dict]:
        """Every assignment in dealing order: seq when recorded, else
        (deck shuffle time, deck position) - the order the cards left the
        deck."""
        deck_rank = {d.get("shuffled_at"): i
                     for i, d in enumerate(self.state.get("decks") or [])}
        rows = []
        for mid, rec in self.state["assignments"].items():
            pos = self.position(mid)
            rows.append({
                "match_id": mid, "day": rec.get("day"),
                "author": rec["author"],
                "deck": deck_rank.get(rec.get("deck_shuffled_at")),
                "deck_shuffled_at": rec.get("deck_shuffled_at"),
                "deck_position": pos[0] if pos else None,
                "deck_size": pos[1] if pos else None,
                "seq": rec.get("seq"),
                "assigned_at": rec.get("assigned_at"),
            })
        rows.sort(key=lambda r: (
            r["deck"] if r["deck"] is not None else 10**6,
            r["deck_position"] or 10**6, r["assigned_at"] or "",
            int(r["match_id"]) if str(r["match_id"]).isdigit() else 0))
        for i, r in enumerate(rows, 1):
            r["order"] = i
        return rows

    def audit(self) -> dict:
        """History + mechanical cycle checks:
          * within_deck_repeats: a profile dealt twice from one deck (must
            be empty - the no-repeat guarantee),
          * incomplete_closed_decks: a deck that was replaced before all its
            cards were dealt WITHOUT a profile-set change (must be empty),
          * seam_repeats: the same profile on both sides of a deck seam
            (boundary guard; must be empty)."""
        rows = self.history()
        decks = self.state.get("decks") or []
        per_deck = []
        within, seams, incomplete = [], [], []
        prev_last = None
        for i, d in enumerate(decks):
            dealt = [r for r in rows if r["deck"] == i]
            authors = [r["author"] for r in dealt]
            dup = sorted({a for a in authors if authors.count(a) > 1})
            if dup:
                within.append({"deck": i + 1, "repeated": dup})
            size = len(d.get("order") or [])
            is_live = d.get("shuffled_at") == self.state["deck"].get("shuffled_at")
            if (not is_live and len(dealt) < size and i + 1 < len(decks)
                    and set(decks[i + 1].get("order") or []) == set(d.get("order") or [])):
                incomplete.append({"deck": i + 1, "dealt": len(dealt), "size": size})
            if dealt and prev_last is not None and dealt[0]["author"] == prev_last:
                seams.append({"deck": i + 1, "author": prev_last})
            if dealt:
                prev_last = dealt[-1]["author"]
            per_deck.append({"deck": i + 1, "shuffled_at": d.get("shuffled_at"),
                             "size": size, "dealt": len(dealt),
                             "distinct": len(set(authors)),
                             "complete": len(dealt) == size and not dup,
                             "live": is_live, "order": d.get("order")})
        deck = self.state["deck"]
        return {
            "state_path": str(self.state_path),
            "profiles": list(self.profiles),
            "assignments": rows,
            "decks": per_deck,
            "checks": {"within_deck_repeats": within,
                       "incomplete_closed_decks": incomplete,
                       "seam_repeats": seams,
                       "passed": not (within or incomplete or seams)},
            "current_deck": {"shuffled_at": deck.get("shuffled_at"),
                             "order": deck.get("order"),
                             "next": deck.get("next"),
                             "remaining": self.remaining_in_deck()},
        }


def format_audit(audit: dict) -> str:
    """Human-readable rotation audit (the editor's proof over time)."""
    out = [f"AUTHOR ROTATION AUDIT  (state: {audit['state_path']})",
           f"profiles on disk: {len(audit['profiles'])}  "
           f"assignments: {len(audit['assignments'])}  "
           f"decks shuffled: {len(audit['decks'])}", "",
           f"{'#':>3}  {'match_id':>8}  {'day':10s}  {'author':9s}  "
           f"{'name':22s}  {'deck':>4}  {'pos':>5}"]
    for r in audit["assignments"]:
        try:
            name = profile_display_name(r["author"])
        except (OSError, ValueError):
            name = "?"
        pos = (f"{r['deck_position']}/{r['deck_size']}"
               if r["deck_position"] else "?")
        out.append(f"{r['order']:>3}  {r['match_id']:>8}  {str(r['day']):10s}  "
                   f"{r['author']:9s}  {name[:22]:22s}  "
                   f"{(r['deck'] + 1) if r['deck'] is not None else '?':>4}  {pos:>5}")
    out += ["", "PER-DECK CYCLE CHECK (each deck = every profile once)"]
    for d in audit["decks"]:
        state = ("complete" if d["complete"] else
                 "LIVE" if d["live"] else "closed early")
        out.append(f"  deck {d['deck']} (shuffled {d['shuffled_at']}): "
                   f"dealt {d['dealt']}/{d['size']}, distinct {d['distinct']} "
                   f"-> {state}")
    c = audit["checks"]
    out += ["",
            f"  within-deck repeats ......... {c['within_deck_repeats'] or 'none'}",
            f"  decks closed before complete  {c['incomplete_closed_decks'] or 'none'}",
            f"  repeats across a deck seam .. {c['seam_repeats'] or 'none'}",
            f"  ROTATION AUDIT: {'PASS' if c['passed'] else 'FAIL'}",
            "", "CURRENT DECK"]
    cd = audit["current_deck"]
    order = cd.get("order") or []
    nxt = cd.get("next") or 0
    out.append("  order: " + ", ".join(
        (f"[{a}]" if i < nxt else a) for i, a in enumerate(order)) +
        "   ([dealt])")
    out.append(f"  next card: position {nxt + 1}/{len(order)}"
               if nxt < len(order) else
               "  deck exhausted: the next match triggers a reshuffle")
    out.append(f"  remaining: {', '.join(cd['remaining']) or 'none'}")
    return "\n".join(out)


def draft_footer(author_id: str | None,
                 position: tuple[int, int] | None) -> str:
    """The draft-only footer block (leading blank line + separator)."""
    if author_id is None:
        note = f"{HOUSE_FOOTER_MARKER} (no author profile) | rotation not used"
    else:
        try:
            name = profile_display_name(author_id)
        except (OSError, ValueError):
            name = author_id
        pos = (f"rotation deck position {position[0]}/{position[1]}"
               if position else "rotation deck position n/a (author set explicitly)")
        note = f"{FOOTER_MARKER} {author_id} ({name}) | {pos}"
    return f"\n\n{FOOTER_SEPARATOR}\n{note}\n"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="author rotation tools")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("audit", help="print assignment history + deck state")
    a.add_argument("--state", default=str(STATE_PATH))
    a.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rot = AuthorRotation(state_path=Path(args.state))
    audit = rot.audit()
    if args.json:
        print(json.dumps(audit, indent=2))
    else:
        print(format_audit(audit))
    raise SystemExit(0 if audit["checks"]["passed"] else 1)


if __name__ == "__main__":
    main()
