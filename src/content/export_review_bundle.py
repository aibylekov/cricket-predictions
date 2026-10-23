"""
export_review_bundle.py - bundle the demo drafts for editorial review.

Collects data/articles/<match_id>_<mode>_draft.md for the demo matches,
their validation stamps (the header comment written by generate_article),
the author-rotation assignment for each match (data/state/
author_assignments.json) and the extracted profile of every author used,
into ONE Markdown file the editor can read top to bottom:

    docs/demo_drafts_review_v<N>.md

Iteration 5b: every draft in the bundle ENDS with its draft-only author
footer ("NOTE: Written in author style: author-NN (Name) | rotation deck
position N/8"), exactly as in the draft file (drafts written before 5b get
it rendered from the rotation state), and the bundle closes with the
rotation audit (assignment history + per-deck cycle check + deck state).

RUN:
    venv/Scripts/python.exe -m src.content.export_review_bundle 5
    venv/Scripts/python.exe -m src.content.export_review_bundle 5 --modes both
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from src.content.author_rotation import (FOOTER_MARKER, HOUSE_FOOTER_MARKER,
                                         AuthorRotation, draft_footer,
                                         format_audit, load_profile,
                                         profile_display_name)
from src.content.generate_article import ARTICLES_DIR, DEMO_MATCHES

ROOT = Path(__file__).resolve().parents[2]

FIXTURE_NAMES = {
    8731: "England v India (The Rose Bowl)",
    8250: "Washington Freedom v MI New York (MLC Eliminator)",
    8032: "Royal Challengers Bengaluru v Gujarat Titans (IPL Final)",
}


def _stamp_fields(header: str) -> dict:
    inner = header.strip()[4:-3].strip()                 # strip <!-- -->
    fields = {"validation": inner.split(" | ")[0]}
    for part in inner.split(" | ")[1:]:
        if "=" in part:
            k, v = part.split("=", 1)
            fields[k.strip()] = v.strip()
    return fields


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("version", type=int)
    ap.add_argument("--modes", choices=("post_toss", "pre_toss", "both"),
                    default="post_toss")
    args = ap.parse_args()
    modes = ("post_toss", "pre_toss") if args.modes == "both" else (args.modes,)

    rotation = AuthorRotation()
    rows, drafts, authors_used = [], [], []
    for band, match_id in DEMO_MATCHES:
        author = rotation.get(match_id) or "?"
        if author not in authors_used and author != "?":
            authors_used.append(author)
        for mode in modes:
            path = ARTICLES_DIR / f"{match_id}_{mode}_draft.md"
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            header, _, body = text.partition("\n\n")
            f = _stamp_fields(header)
            if FOOTER_MARKER not in body and HOUSE_FOOTER_MARKER not in body:
                # pre-5b draft: render the footer from the rotation state
                a = f.get("author") or author
                body = body.rstrip() + draft_footer(
                    None if a in ("None", "?") else a,
                    rotation.position(match_id) if a == author else None)
            rows.append((match_id, band, mode, f.get("author", author),
                         f["validation"], f.get("attempts", "?")))
            drafts.append((match_id, band, mode, f, body.strip()))

    out = [f"# Demo Drafts — Review Bundle v{args.version} (author style rotation)",
           "",
           "Generated from the iteration-5 demo drafts (data/articles/). The three "
           "demo matches were generated as ONE match day under the author "
           "rotation: a shuffled deck of the 8 extracted author profiles dealt "
           "one profile per match, so the three drafts carry three different "
           "voices. Every mechanical check (numbers, scope attribution, banned "
           "words, repetition caps, toss language, league-vs-format labels) ran "
           "unchanged under every voice. Validation stamps are summarized below "
           "and repeated above each draft; prose bodies are unchanged. The "
           "extracted profiles of the three authors used follow the drafts.",
           "",
           "| # | Fixture | Band | Mode | Author | Validation | API calls |",
           "|---|---------|------|------|--------|------------|-----------|"]
    for i, (mid, band, mode, author, val, calls) in enumerate(rows, 1):
        name = profile_display_name(author) if author != "?" else "?"
        out.append(f"| {i} | {FIXTURE_NAMES.get(mid, mid)} (match {mid}) | {band} "
                   f"| {mode} | {author} ({name}) | "
                   f"{'PASSED' if val == 'VALIDATION: PASSED' else val} | {calls} |")
    out.append("")
    out.append("Rotation state: " + rotation.state_path.relative_to(ROOT).as_posix()
               + f"; remaining in deck after this day: "
               f"{', '.join(rotation.remaining_in_deck()) or 'none'}.")
    out.append("")
    out.append("---")
    for i, (mid, band, mode, f, body) in enumerate(drafts, 1):
        out += ["", f"## Draft {i}: {FIXTURE_NAMES.get(mid, mid)} — {band} / "
                f"{mode} — {f.get('author')} "
                f"({profile_display_name(f.get('author'))})",
                "",
                f"> {f['validation']} | model={f.get('model')} | mode={mode} | "
                f"author={f.get('author')} | attempts={f.get('attempts')} | "
                f"payload_model={f.get('payload_model')}",
                "", body, "", "---"]
    out += ["", "# Rotation audit", "",
            "Assignment history from data/state/author_assignments.json "
            "(`python -m src.content.author_rotation audit`):", "", "```",
            format_audit(rotation.audit()), "```", "", "---"]
    out += ["", "# Extracted author profiles used on this match day", ""]
    for author in authors_used:
        raw = (ROOT / "src" / "content" / "author_profiles" / f"{author}.md"
               ).read_text(encoding="utf-8")
        status = re.search(r"LEAK CHECK[^\n]*", raw)
        out += [f"## {author} — {profile_display_name(author)}", "",
                f"> src/content/author_profiles/{author}.md | "
                f"{status.group(0) if status else ''}", "",
                load_profile(author), "", "---"]
    dest = ROOT / "docs" / f"demo_drafts_review_v{args.version}.md"
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {dest.relative_to(ROOT).as_posix()} ({len(drafts)} drafts, "
          f"{len(authors_used)} profiles)")


if __name__ == "__main__":
    main()
