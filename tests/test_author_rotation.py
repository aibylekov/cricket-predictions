"""
test_author_rotation.py - AUTHOR STYLE ROTATION contracts (no API calls).

  1. PROFILES: every extracted profile exists, passed the leak check, has
     the seven sections, and carries no team/player entity from its source.
  2. LAYERING: the system prompt under any author is byte-identical to the
     house prompt outside the single voice slot - every mechanical rule text
     survives; the validators take no author argument at all and behave the
     same on the same text.
  3. ROTATION: a deck deals N distinct profiles before any repeat; the
     reshuffle happens only on exhaustion; the boundary guard prevents a
     repeat across the seam; a changed profile set forces a new deck.
  4. PERSISTENCE: the same match_id always returns the same author - across
     retries, across a fresh AuthorRotation instance on the same state
     file, and for the pre_toss/post_toss pair.
  5. GENERATOR WIRING: generate_article() puts the author block into the
     system message; generate_and_save() stamps the assigned author.

Run:
  venv/Scripts/python.exe -m pytest tests/test_author_rotation.py -v
"""
from __future__ import annotations

import inspect
import random
import re
from pathlib import Path

import pytest

from src.content import generate_article as ga
from src.content.author_rotation import (
    PROFILES_DIR,
    AuthorRotation,
    list_profiles,
    load_profile,
    profile_display_name,
)
from src.content.calibrate_author import SOURCE_DIR, entity_inventory, read_source
from src.content.prompt_template import (
    BANNED_CONNECTORS,
    BANNED_HOUSE_TERMS,
    BANNED_WORDS,
    SYSTEM_PROMPT,
    _VOICE_SLOT,
    author_voice_block,
    build_system_prompt,
)

PROFILES = list_profiles()
SECTION_HEADS = ["SENTENCE RHYTHM", "LEXICAL SIGNATURE", "REGISTER",
                 "PARAGRAPH ARCHITECTURE", "DEVICES", "TEN RULES",
                 "CONFLICTS WITH HOUSE RULES"]


# --------------------------------------------------------------------------
# 1. profiles
# --------------------------------------------------------------------------
def test_eight_profiles_on_disk():
    assert len(PROFILES) == 8, PROFILES
    assert PROFILES == [f"author-{i:02d}" for i in range(1, 9)]


@pytest.mark.parametrize("author_id", PROFILES)
def test_profile_is_complete_and_leak_free(author_id):
    raw = (PROFILES_DIR / f"{author_id}.md").read_text(encoding="utf-8")
    assert "LEAK CHECK: PASSED" in raw, f"{author_id}: leak check not passed"
    text = load_profile(author_id)
    assert text.startswith("**STYLE PROFILE"), text[:60]
    for head in SECTION_HEADS:
        assert head in text, f"{author_id}: missing section {head}"
    assert profile_display_name(author_id) != author_id


@pytest.mark.parametrize("author_id", PROFILES)
def test_profile_leak_check_against_source(author_id):
    """Independent re-run of the leak check against the source articles.
    docs/author-styles/ is local-only (gitignored, not in the repo), so on a
    clone without it this skips; the profile's own LEAK CHECK: PASSED stamp
    is still asserted above."""
    src = next(SOURCE_DIR.glob(f"{author_id}-*.md"), None)
    if src is None:
        pytest.skip(f"source articles for {author_id} not present in "
                    f"{SOURCE_DIR} (local-only, gitignored)")
    text = load_profile(author_id)
    inv = entity_inventory(read_source(src)[1])
    for kind in ("teams", "players"):
        for ent in inv[kind]:
            assert not re.search(r"(?<![A-Za-z])" + re.escape(ent) + r"(?![A-Za-z])",
                                 text), f"{author_id}: leaked {kind[:-1]} {ent!r}"


# --------------------------------------------------------------------------
# 2. layering: the author changes the voice slot and nothing else
# --------------------------------------------------------------------------
def _outside_slot(prompt: str) -> tuple[str, str]:
    """(text before the voice block, text from the self-check on) - the
    voice block is whatever sits between the '=== ... VOICE' marker and
    the MANDATORY SELF-CHECK heading."""
    start = prompt.index("\n=== ")
    end = prompt.index("MANDATORY SELF-CHECK")
    return prompt[:start], prompt[end:]


def test_house_prompt_is_the_default():
    assert build_system_prompt(None) == SYSTEM_PROMPT
    assert _VOICE_SLOT not in SYSTEM_PROMPT
    assert "=== HOUSE VOICE" in SYSTEM_PROMPT


@pytest.mark.parametrize("author_id", PROFILES)
def test_author_prompt_identical_outside_the_voice_slot(author_id):
    author_block = author_voice_block(author_id)
    prompt = build_system_prompt(author_id)
    assert author_block in prompt
    assert "=== HOUSE VOICE" not in prompt             # replaced, not stacked
    assert "=== AUTHOR VOICE" in SYSTEM_PROMPT[:0] + prompt
    assert _outside_slot(SYSTEM_PROMPT) == _outside_slot(prompt)
    # the mechanical-rule text is all still there
    for phrase in BANNED_CONNECTORS:
        assert phrase in prompt
    for marker in ("ROLE 1: FACTS (THE HARD WALL", "SCOPE ATTRIBUTION",
                   "TOSS IMPACT (mechanically checked)", "FORM-CLAIM LABEL",
                   "FACT-REPETITION CAP", "NEVER USE EM DASHES",
                   "MANDATORY SELF-CHECK BEFORE DELIVERY"):
        assert marker in prompt, marker
    # the block states the layering rule and carries no em dash
    assert "LAYERING RULE" in author_block
    assert "—" not in author_block
    assert "CONFLICTS WITH HOUSE RULES" in author_block


def test_validators_take_no_author():
    for fn in (ga.validate_style, ga.validate_article):
        assert "author" not in inspect.signature(fn).parameters
    bad = ("# Title\n\nThey won — moreover the pitch is robust. Our model "
           "says so.\n")
    res = ga.validate_style(bad, None)
    assert not res["passed"]
    assert res["em_dashes"] == 1
    assert any(h.startswith("moreover") for h in res["banned_connectors"])
    assert any(h.startswith("robust") for h in res["banned_words"])
    assert any(h.startswith("model mention") for h in res["house_terms"])
    assert len(BANNED_WORDS) >= 30 and len(BANNED_HOUSE_TERMS) >= 20


# --------------------------------------------------------------------------
# 3. rotation
# --------------------------------------------------------------------------
def _rot(tmp_path: Path, seed: int = 7, profiles=None) -> AuthorRotation:
    return AuthorRotation(state_path=tmp_path / "s.json",
                          profiles=profiles or PROFILES,
                          rng=random.Random(seed))


def test_deck_deals_all_profiles_before_any_repeat(tmp_path):
    rot = _rot(tmp_path)
    first_deck = [rot.assign(m)[0] for m in range(100, 108)]
    assert sorted(first_deck) == PROFILES                 # 8 distinct
    assert rot.remaining_in_deck() == []
    second_deck = [rot.assign(m)[0] for m in range(200, 208)]
    assert sorted(second_deck) == PROFILES
    assert second_deck[0] != first_deck[-1]               # boundary guard


def test_boundary_guard_across_many_reshuffles(tmp_path):
    for seed in range(40):
        rot = _rot(tmp_path / str(seed), seed=seed)
        seq = [rot.assign(m)[0] for m in range(1000, 1000 + 8 * 6)]
        for i in range(1, len(seq)):
            assert seq[i] != seq[i - 1], (seed, i, seq)
        for k in range(0, len(seq), 8):
            assert sorted(seq[k:k + 8]) == PROFILES


def test_reshuffle_only_on_exhaustion(tmp_path):
    rot = _rot(tmp_path)
    rot.assign(1)
    order = list(rot.state["deck"]["order"])
    for m in range(2, 9):
        rot.assign(m)
    assert rot.state["deck"]["order"] == order            # same deck all day
    assert rot.state["deck"]["next"] == 8
    rot.assign(9)                                          # exhausted -> new deck
    assert rot.state["deck"]["next"] == 1
    assert sorted(rot.state["deck"]["order"]) == sorted(order)


def test_profile_set_change_forces_new_deck(tmp_path):
    rot = _rot(tmp_path, profiles=PROFILES[:4])
    rot.assign(1)
    assert set(rot.state["deck"]["order"]) == set(PROFILES[:4])
    rot2 = AuthorRotation(state_path=tmp_path / "s.json", profiles=PROFILES,
                          rng=random.Random(1))
    rot2.assign(2)
    assert set(rot2.state["deck"]["order"]) == set(PROFILES)
    assert rot2.get(1) in PROFILES[:4]                    # old assignment kept


def test_assign_day_three_distinct(tmp_path):
    rot = _rot(tmp_path)
    day = rot.assign_day([8731, 8250, 8032], day="2026-09-26")
    assert len({a for _, a, _ in day}) == 3
    assert all(new for _, _, new in day)
    assert rot.state["assignments"]["8731"]["day"] == "2026-09-26"


# --------------------------------------------------------------------------
# 4. persistence
# --------------------------------------------------------------------------
def test_same_match_same_author_across_retries_modes_and_instances(tmp_path):
    rot = _rot(tmp_path)
    a, new = rot.assign(8731)
    assert new
    assert rot.assign(8731) == (a, False)                 # retry
    assert rot.assign("8731") == (a, False)               # str/int key
    # the other toss mode is generated by a fresh process on the same state
    rot2 = AuthorRotation(state_path=tmp_path / "s.json", profiles=PROFILES,
                          rng=random.Random(99))
    assert rot2.assign(8731) == (a, False)
    assert rot2.get(8731) == a
    # and the deck position carried over: the next match gets a new card
    b, new = rot2.assign(8250)
    assert new and b != a


def test_reset_forgets_everything(tmp_path):
    rot = _rot(tmp_path)
    rot.assign(1)
    rot.reset()
    assert rot.get(1) is None
    assert (tmp_path / "s.json").exists()


def test_state_file_is_gitignored():
    gi = (Path(__file__).resolve().parents[1] / ".gitignore").read_text()
    assert "data/state/" in gi.splitlines()


# --------------------------------------------------------------------------
# 5. generator wiring (fake client, no API)
# --------------------------------------------------------------------------
class _FakeClient:
    def __init__(self):
        self.messages = None

        class _Completions:
            def create(inner, **kw):
                self.messages = kw["messages"]

                class _Msg:
                    content = ""

                class _Choice:
                    message = _Msg()

                class _Resp:
                    choices = [_Choice()]
                return _Resp()

        class _Chat:
            completions = _Completions()

        self.chat = _Chat()


def test_generate_article_uses_author_block():
    client = _FakeClient()
    payload = {"prediction": {"confidence_band": "confident"}, "match": {}}
    article, numbers, style, calls = ga.generate_article(
        payload, client, "post_toss", author_id="author-02")
    assert calls == 1 and numbers["passed"] and style["passed"]
    system = client.messages[0]["content"]
    assert "=== AUTHOR VOICE" in system and "(author-02)" in system
    assert "=== HOUSE VOICE" not in system
    # default: house voice
    ga.generate_article(payload, client, "post_toss")
    assert "=== HOUSE VOICE" in client.messages[0]["content"]


def test_generate_and_save_stamps_persisted_author(tmp_path, monkeypatch):
    client = _FakeClient()
    monkeypatch.setattr(ga, "ARTICLES_DIR", tmp_path / "articles")
    monkeypatch.setattr(ga, "build_payload", lambda mid: {
        "prediction": {"confidence_band": "confident",
                       "model_version": "test"}, "match": {}})
    rot = _rot(tmp_path)
    out1 = ga.generate_and_save(8731, client, "post_toss", rotation=rot)
    out2 = ga.generate_and_save(8731, client, "pre_toss", rotation=rot)
    assert out1[4] == out2[4] == rot.get(8731)
    for p in (out1[0], out2[0]):
        head = p.read_text(encoding="utf-8").splitlines()[0]
        assert f"author={rot.get(8731)}" in head and "VALIDATION: PASSED" in head
    out3 = ga.generate_and_save(8250, client, "post_toss", rotation=rot)
    assert out3[4] != out1[4]
