"""
test_form_label.py - cross-competition form windows never carry a league name
(no API, no DB).

The WBBL demo (5923, WBBL 2025 opener) passed validation with "won 3 of their
last 5 WBBL matches across competitions" - but the Heat's last 5 were all
T20 Spring Challenge games and the Renegades' mixed Spring Challenge with a
WBBL 2024 final. A last5 window that includes another competition is not
league form: the league name is wrong there, whatever else the sentence says.

  1. the four 5923 draft sentences are caught, naming the other event;
  2. the honest rewrites ("across competitions" / naming the event) pass the
     form-label, scope and win-pair checks together (no rule conflict);
  3. league-only windows keep the old rule (league name required, "T20"
     redundant), and earlier editions of the same league count as league form;
  4. the rule is in every author's prompt.

Run:
  venv/Scripts/python.exe -m pytest tests/test_form_label.py -v
"""
from __future__ import annotations

from src.content import generate_article as ga

SC, WBBL24, WBBL25 = ("T20 Spring Challenge, 2025", "Womens Big Bash League, 2024",
                      "Womens Big Bash League, 2025")


def _ent(opp, won, date, event):
    return {"opponent": opp, "won": won, "date": date, "event": event}


def _payload(home=None, away=None):
    """5923-shaped: last5 entries as in the WBBL 2025 opener payload."""
    heat = home if home is not None else [
        _ent("Hobart Hurricanes Women", False, "2025-10-30", SC),
        _ent("Hobart Hurricanes Women", False, "2025-10-26", SC),
        _ent("Melbourne Stars Women", True, "2025-10-25", SC),
        _ent("Perth Scorchers Women", True, "2025-10-23", SC),
        _ent("Melbourne Renegades Women", True, "2025-10-21", SC)]
    gades = away if away is not None else [
        _ent("ACT Meteors Women", True, "2025-10-27", SC),
        _ent("Sydney Sixers Women", True, "2025-10-26", SC),
        _ent("Adelaide Strikers Women", True, "2025-10-24", SC),
        _ent("Brisbane Heat Women", False, "2025-10-21", SC),
        _ent("Brisbane Heat Women", True, "2024-12-01", WBBL24)]
    return {"match": {"home_team": "Brisbane Heat Women",
                      "away_team": "Melbourne Renegades Women",
                      "tournament": WBBL25, "competition_type": "franchise",
                      "form_label": "WBBL",
                      "form_label_full": "Womens Big Bash League",
                      "venue": "Allan Border Field"},
            "form": {}, "standings": {},
            "match_context": {"last5_results": {"home": heat, "away": gades}}}


# the four sentences from the 5923 draft that passed on 2026-10-26
DRAFT_5923 = [
    "- Brisbane Heat Women have won 3 of their last 5 WBBL matches across "
    "competitions, showcasing resilience in recent games.",
    "- Melbourne Renegades Women have displayed impressive form, winning 4 of "
    "their last 5 WBBL matches across competitions.",
    "Brisbane Heat Women have experienced a mixed bag of results recently, "
    "winning 3 of their last 5 WBBL matches across competitions.",
    "Melbourne Renegades Women enter this match with strong momentum, having "
    "won 4 of their last 5 WBBL matches across competitions.",
]


def test_wbbl_demo_sentences_are_caught():
    p = _payload()
    for s in DRAFT_5923:
        hits = ga._form_claims_mislabelled(s, p)
        assert len(hits) == 1, s
        assert "T20 Spring Challenge" in hits[0] and "not 'WBBL' form" in hits[0]
    # the mixed Renegades window names both events
    assert "Womens Big Bash League, 2024" in ga._form_claims_mislabelled(DRAFT_5923[1], p)[0]


def test_league_name_without_across_is_caught_too():
    hits = ga._form_claims_mislabelled(
        "The Heat have won 3 of their last 5 WBBL games.", _payload())
    assert len(hits) == 1 and "not 'WBBL' form" in hits[0]


def test_whole_draft_fails_style_on_form_label():
    st = ga.validate_style("\n\n".join(DRAFT_5923), _payload())
    assert not st["passed"] and len(st["form_label"]) == 4


def test_honest_rewrites_pass_every_form_check():
    p = _payload()
    for s in ("Brisbane Heat Women have won 3 of their last 5 across competitions.",
              "Melbourne Renegades Women have won 4 of their last 5 T20s across "
              "competitions.",
              "The Heat won 3 of their 5 games in the T20 Spring Challenge in "
              "October 2025."):
        assert ga._form_claims_mislabelled(s, p) == [], s
        assert ga._scope_attribution_violations(s, p) == [], s
        assert ga._win_pair_violations(s, p) == [], s


def test_unlabelled_cross_competition_count_still_needs_a_label():
    # the scope check (not the form-label check) owns "across competitions"
    s = "Brisbane Heat Women have won 3 of their last 5."
    p = _payload()
    assert ga._form_claims_mislabelled(s, p) == []
    assert len(ga._scope_attribution_violations(s, p)) == 1


def test_league_only_window_keeps_the_league_rule():
    # last 5 all WBBL (2024 + 2025 editions): that IS league form
    league = [_ent("Sydney Sixers Women", True, "2025-11-12", WBBL25),
              _ent("Perth Scorchers Women", True, "2025-11-10", WBBL25),
              _ent("Hobart Hurricanes Women", False, "2024-12-01", WBBL24),
              _ent("Sydney Thunder Women", True, "2024-11-28", WBBL24),
              _ent("Adelaide Strikers Women", True, "2024-11-24", WBBL24)]
    # away's mixed 4-of-5 equals home's league-only 4-of-5: ambiguous, dropped
    assert (4, 5) not in ga._cross_competition_windows(_payload(home=league))
    p = _payload(home=league, away=league)
    assert ga._cross_competition_windows(p) == {}
    assert ga._form_claims_mislabelled(
        "Brisbane Heat Women have won 4 of their last 5 WBBL matches.", p) == []
    t20 = ga._form_claims_mislabelled(
        "Brisbane Heat Women have won 4 of their last 5 T20 matches.", p)
    assert len(t20) == 1 and "not 'T20'" in t20[0]


def test_ambiguous_pair_is_not_flagged():
    # 3 of 5 is ALSO the side's WBBL tournament record -> never flagged
    p = _payload()
    p["form"] = {"home": {"win_pct": {"tournament": 0.6},
                          "matches_in_window": {"tournament": 5}}}
    assert ga._form_claims_mislabelled(
        "Brisbane Heat Women have won 3 of their last 5 WBBL matches.", p) == []


def test_rule_is_in_every_prompt():
    from src.content.author_rotation import list_profiles
    from src.content.prompt_template import build_system_prompt
    for author in [None] + list_profiles():
        assert "CROSS-COMPETITION WINDOWS TAKE NO LEAGUE NAME" in \
            build_system_prompt(author), author
