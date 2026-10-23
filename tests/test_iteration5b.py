"""
test_iteration5b.py - the editor's iteration-5 verdict, mechanically (no API).

  1. DRAFT FOOTER: every saved draft ENDS with the author-style note and its
     deck position; the publish path strips it and its guard refuses any
     text that still carries draft-only metadata.
  2. ROTATION AUDIT: deck positions are recorded, the history/audit proves
     each deck deals every profile before any repeat, tampering is caught,
     and pre-5b state files still audit (positions derived).
  3. EDITOR'S v5 FIXES, each pinned to the exact sentence from the review:
     a) mirror facts ("England winning all 3" + "India losing all 3"),
     b) home scope ("record at home, winning 10 of their 16 ... season"),
     c) terminology ("striking rate").

Run:
  venv/Scripts/python.exe -m pytest tests/test_iteration5b.py -v
"""
from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from src import publish as pub
from src.content import generate_article as ga
from src.content.author_rotation import (FOOTER_MARKER, AuthorRotation,
                                         draft_footer, format_audit,
                                         list_profiles, profile_display_name)

PROFILES = list_profiles()


def _rot(tmp_path: Path, seed: int = 7) -> AuthorRotation:
    return AuthorRotation(state_path=tmp_path / "s.json", profiles=PROFILES,
                          rng=random.Random(seed))


class _FakeClient:
    """Returns a fixed article body for every call."""

    def __init__(self, body: str = "## Three Key Points\n\n- A plain line.\n"):
        outer = self

        class _Completions:
            def create(inner, **kw):
                class _Msg:
                    content = outer.body

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]
                return _Resp()

        class _Chat:
            completions = _Completions()

        self.body = body
        self.chat = _Chat()


def _fake_payload(mid):
    return {"prediction": {"confidence_band": "confident", "model_version": "t"},
            "match": {}}


# --------------------------------------------------------------------------
# 1. footer + publish strip/guard
# --------------------------------------------------------------------------
def test_draft_ends_with_author_footer(tmp_path, monkeypatch):
    monkeypatch.setattr(ga, "ARTICLES_DIR", tmp_path / "articles")
    monkeypatch.setattr(ga, "build_payload", _fake_payload)
    rot = _rot(tmp_path)
    paths = []
    for i, mid in enumerate((8731, 8250, 8032), 1):
        path, numbers, style, _, author = ga.generate_and_save(
            mid, _FakeClient(), "post_toss", rotation=rot)
        assert numbers["passed"] and style["passed"]   # footer never validated
        lines = path.read_text(encoding="utf-8").rstrip().splitlines()
        assert lines[-2] == "---"
        assert lines[-1] == (f"{FOOTER_MARKER} {author} "
                             f"({profile_display_name(author)}) | "
                             f"rotation deck position {i}/{len(PROFILES)}")
        paths.append(path)
    # the other toss mode of a match carries the SAME author and position
    p2, *_ = ga.generate_and_save(8250, _FakeClient(), "pre_toss", rotation=rot)
    assert p2.read_text(encoding="utf-8").rstrip().splitlines()[-1] == \
        paths[1].read_text(encoding="utf-8").rstrip().splitlines()[-1]


def test_explicit_author_and_house_voice_footers():
    assert "rotation deck position n/a" in draft_footer("author-03", None)
    assert draft_footer(None, None).strip().splitlines()[-1].startswith(
        "NOTE: Written in house voice")


DRAFT = ("<!-- VALIDATION: PASSED | model=gpt-4o | mode=post_toss | "
         "author=author-07 | attempts=1 | payload_model=v2 -->\n\n"
         "# RCB vs GT Prediction\n\n## Three Key Points\n\n- Kohli leads.\n\n"
         "---\n\n## Pitch\n\nA flat deck.\n"
         + draft_footer("author-07", (3, 8)))


def test_publish_strips_header_and_footer():
    clean = pub.prepare_for_publish(DRAFT)
    assert clean.startswith("# RCB vs GT Prediction")
    assert "## Pitch\n\nA flat deck." in clean
    assert "---\n\n## Pitch" in clean          # an in-article rule survives
    assert pub.publish_guard_violations(clean) == []
    assert "author-07" not in clean and "Written in author style" not in clean


@pytest.mark.parametrize("leak", [
    "\n\nNOTE: Written in author style: author-07 (Manish K.) | rotation deck position 3/8\n\n",
    "\nThis piece is in the author-04 voice.\n",
    "\n<!-- VALIDATION: PASSED -->\n",
])
def test_publish_guard_refuses_any_surviving_metadata(leak):
    # metadata moved INTO the article body, where the tail-strip can't reach
    text = DRAFT.replace("## Pitch", leak + "## Pitch")
    with pytest.raises(pub.PublishGuardError):
        pub.prepare_for_publish(text)


def test_publish_posts_only_clean_text():
    sent = {}
    pub.publish("8032", DRAFT, poster=lambda mid, t: sent.update(mid=mid, t=t))
    assert sent["mid"] == "8032" and pub.publish_guard_violations(sent["t"]) == []
    with pytest.raises(pub.PublishGuardError):
        pub.publish("8032", DRAFT + "\nauthor-07\n", poster=lambda *a: None)


# --------------------------------------------------------------------------
# 2. rotation audit
# --------------------------------------------------------------------------
def test_positions_recorded_and_audit_passes_over_many_decks(tmp_path):
    rot = _rot(tmp_path, seed=11)
    for m in range(1, 8 * 3 + 4):                  # 3 full decks + 3 cards
        rot.assign(m, day=f"2026-10-{(m // 4) + 1:02d}")
    hist = rot.history()
    assert [r["match_id"] for r in hist] == [str(m) for m in range(1, 28)]
    assert [r["deck_position"] for r in hist[:9]] == [1, 2, 3, 4, 5, 6, 7, 8, 1]
    audit = rot.audit()
    assert audit["checks"]["passed"], audit["checks"]
    assert [d["complete"] for d in audit["decks"]] == [True, True, True, False]
    assert audit["decks"][-1]["live"] and audit["decks"][-1]["dealt"] == 3
    text = format_audit(audit)
    assert "ROTATION AUDIT: PASS" in text and "next card: position 4/8" in text


def test_audit_catches_a_within_deck_repeat(tmp_path):
    rot = _rot(tmp_path)
    for m in range(1, 5):
        rot.assign(m)
    rot.state["assignments"]["4"]["author"] = rot.state["assignments"]["1"]["author"]
    assert not rot.audit()["checks"]["passed"]
    assert rot.audit()["checks"]["within_deck_repeats"]


def test_pre_5b_state_audits_with_derived_positions(tmp_path):
    order = PROFILES[::-1]
    legacy = {"version": 1, "last_dealt": order[2],
              "deck": {"order": order, "next": 3, "shuffled_at": "T0"},
              "assignments": {str(m): {"author": order[i], "day": "2026-09-26",
                                       "assigned_at": "T0", "deck_shuffled_at": "T0"}
                              for i, m in enumerate((8731, 8250, 8032))}}
    (tmp_path / "s.json").write_text(json.dumps(legacy), encoding="utf-8")
    rot = AuthorRotation(state_path=tmp_path / "s.json", profiles=PROFILES,
                         rng=random.Random(1))
    assert [rot.position(m) for m in (8731, 8250, 8032)] == [(1, 8), (2, 8), (3, 8)]
    assert rot.audit()["checks"]["passed"]
    a, _ = rot.assign(9999)                        # dealing continues the deck
    assert a == order[3] and rot.position(9999) == (4, 8)


# --------------------------------------------------------------------------
# 3. the editor's v5 fixes
# --------------------------------------------------------------------------
def _series_payload():
    """8731-shaped: England 3-0 up in the series, India 0-5 overall."""
    dates = ["2026-07-01", "2026-07-04", "2026-07-07"]
    eng = [{"opponent": "India", "won": True, "date": d,
            "event": "India tour of England, 2026", "venue": "X"} for d in dates]
    eng += [{"opponent": "South Africa", "won": False, "date": "2026-03-01",
             "event": "World Cup", "venue": "Y"},
            {"opponent": "Sri Lanka", "won": True, "date": "2026-02-20",
             "event": "World Cup", "venue": "Z"}]
    ind = [{"opponent": "England", "won": False, "date": d,
            "event": "India tour of England, 2026", "venue": "X"} for d in dates]
    ind += [{"opponent": "Ireland", "won": False, "date": d,
             "event": "India tour of Ireland, 2026", "venue": "W"}
            for d in ("2026-06-01", "2026-06-03")]
    return {"match": {"home_team": "England", "away_team": "India",
                      "tournament": "India tour of England, 2026",
                      "venue": "The Rose Bowl, Southampton"},
            "form": {"home": {"win_pct": {"current_event": 1.0, "last5": 0.8},
                              "matches_in_window": {"current_event": 3, "last5": 5}},
                     "away": {"win_pct": {"current_event": 0.0, "last5": 0.0},
                              "matches_in_window": {"current_event": 3, "last5": 5}}},
            "standings": None,
            "match_context": {"last5_results": {"home": eng, "away": ind}},
            "venue_ownership": {"policy": "derived",
                                "home_team": {"at_own_ground": False},
                                "away_team": {"at_own_ground": False}}}


V5_DRAFT1_KP = """## Three Key Points

- England has dominated the series, winning all 3 T20 matches against India, with an average margin of 37.7 runs.
- India's performance has been lackluster, losing all 3 T20 matches in the series.
- Something about the pitch.

## England Preview

England swept the series so far.
"""


def test_mirror_fact_from_v5_draft1_is_caught():
    hits = ga._mirror_fact_repeats(V5_DRAFT1_KP, _series_payload())
    assert len(hits) == 1 and "MIRRORED" in hits[0] and "Three Key Points" in hits[0]
    assert not ga.validate_style(V5_DRAFT1_KP, _series_payload())["passed"]


def test_mirror_fact_allows_once_in_kp_once_elsewhere():
    ok = """## Three Key Points

- England have won all 3 T20s in this series.

## India Preview

India lost all 3 T20 matches of the series so far.
"""
    assert ga._mirror_fact_repeats(ok, _series_payload()) == []


def test_same_window_complement_counts_as_one_fact():
    art = """## England Preview

England won 4 of their last 5 T20s across competitions.

## Our Winning Prediction

England lost only 1 of their last 5 T20 matches across competitions.
"""
    hits = ga._mirror_fact_repeats(art, _series_payload())
    assert len(hits) == 1 and "rest of the article" in hits[0]


def test_spelled_out_counts_are_the_same_claim():
    art = """## England Preview

England have won all 3 T20s in this series.

## India Preview

India lost all three T20 matches of the series so far.
"""
    hits = ga._mirror_fact_repeats(art, _series_payload())
    assert len(hits) == 1 and "MIRRORED" in hits[0]
    assert ga._home_scope_violations(
        "At home the Titans have won ten of their sixteen this season.",
        _season_payload(True))


def test_different_result_sets_are_not_mirrors():
    art = """## Three Key Points

- England have won all 3 T20s in this series.
- India have lost all 5 of their recent T20s across competitions.
"""
    assert ga._mirror_fact_repeats(art, _series_payload()) == []


def _season_payload(at_own_ground: bool):
    """8032-shaped: Titans at their own ground, 10-6 in the season."""
    gt = [{"opponent": "Punjab Kings", "won": True, "date": "2026-05-25",
           "event": "IPL 2026", "venue": "Narendra Modi Stadium"},
          {"opponent": "Kolkata", "won": False, "date": "2026-05-20",
           "event": "IPL 2026", "venue": "Eden Gardens"},
          {"opponent": "Delhi", "won": True, "date": "2026-05-15",
           "event": "IPL 2026", "venue": "Narendra Modi Stadium"}]
    return {"match": {"home_team": "Royal Challengers Bengaluru",
                      "away_team": "Gujarat Titans", "tournament": "IPL 2026",
                      "venue": "Narendra Modi Stadium"},
            "form": {"away": {"win_pct": {"current_event": 0.625},
                              "matches_in_window": {"current_event": 16}}},
            "standings": {"away": {"played": 16, "won": 10, "lost": 6}},
            "match_context": {"last5_results": {"home": [], "away": gt}},
            "venue_ownership": {"policy": "derived", "home_team": None,
                                "away_team": {"at_own_ground": at_own_ground}}}


V5_DRAFT3_KP2 = ("- Gujarat Titans hold a solid record at home, winning 10 of "
                 "their 16 matches in this IPL season.")


def test_home_scope_from_v5_draft3_is_caught():
    hits = ga._home_scope_violations(V5_DRAFT3_KP2, _season_payload(True))
    assert len(hits) == 1 and "season record" in hits[0]


def test_home_scope_accepts_home_scoped_numbers_and_season_label():
    p = _season_payload(True)
    assert ga._home_scope_violations(
        "At home the Titans have won 2 of their last 2 here.", p) == []
    assert ga._home_scope_violations(
        "Gujarat Titans have won 10 of their 16 matches this IPL season.", p) == []
    # not their ground -> no home-scoped numbers at all
    assert ga._home_scope_violations(
        "At home the Titans have won 2 of their last 2 here.", _season_payload(False))


def test_striking_rate_is_off_glossary():
    v5 = "He has amassed 375 runs at a striking rate of 200.5."
    st = ga.validate_style(v5, None)
    assert not st["passed"] and st["terminology"] == ["'striking rate' (x1) -> write 'strike rate'"]
    # the cricket verb and the right term are fine
    ok = ga.validate_style("He is striking at 166.7, a strike rate of 162.7.", None)
    assert ok["terminology"] == []


def test_new_rules_are_in_every_prompt():
    from src.content.prompt_template import build_system_prompt
    for author in [None] + PROFILES:
        prompt = build_system_prompt(author)
        for marker in ("NO MIRROR-FACTS (mechanically checked)",
                       "HOME-SCOPED CLAIMS (mechanically checked)",
                       "write 'strike rate', never 'striking rate'"):
            assert marker in prompt, (author, marker)
