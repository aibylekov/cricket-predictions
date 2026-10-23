"""
publish.py — pushes a finished article to TheTopBookies.

DRAFT-ONLY METADATA NEVER SHIPS (iteration 5b, editor's requirement):
a draft file (data/articles/<match_id>_<mode>_draft.md) carries two pieces of
metadata that exist only for editorial review:

  * the header comment   <!-- VALIDATION: PASSED | model=... | author=... -->
  * the author footer    ---
                         NOTE: Written in author style: author-07 (Manish K.)
                         | rotation deck position 3/8

A draft whose header says FAILED VALIDATION is refused outright, before
anything is stripped (it never ships, whatever its body looks like).

The publish path removes both MECHANICALLY (prepare_for_publish) and then
runs a guard (publish_guard_violations) over the text that would be sent:
any surviving trace - the footer marker, an author-NN id, "rotation deck",
a validation stamp - refuses the publish. The guard runs on the FINAL text,
so a note that was moved, duplicated or pasted mid-article cannot leak even
if the strip step misses it.

Usage:
    python -m src.publish --match-id 8731 --article-file data/articles/8731_post_toss_draft.md
    (--check-only: strip + guard, print the clean text, never post)
"""
from __future__ import annotations

import re
from typing import Callable

from src.content.author_rotation import (FOOTER_MARKER, FOOTER_SEPARATOR,
                                         HOUSE_FOOTER_MARKER)

# leading draft header comment(s) written by generate_and_save
_HEADER_RE = re.compile(r"\A\s*(?:<!--.*?-->\s*)+", re.DOTALL)
# trailing footer: separator line, then the NOTE line(s), at the very end
_FOOTER_RE = re.compile(
    r"\n*^[ \t]*" + re.escape(FOOTER_SEPARATOR) + r"[ \t]*\n+"
    r"[ \t]*(?:" + re.escape(FOOTER_MARKER) + "|" + re.escape(HOUSE_FOOTER_MARKER)
    + r")[^\n]*(?:\n[^\n]+)*\s*\Z",
    re.MULTILINE)

# anything that must never reach the site
GUARD_PATTERNS = [
    ("author-style note", re.compile(r"written\s+in\s+(?:author\s+style|house\s+voice)",
                                     re.IGNORECASE)),
    ("author profile id", re.compile(r"\bauthor-\d{2}\b", re.IGNORECASE)),
    ("rotation deck metadata", re.compile(r"\brotation\s+deck\b", re.IGNORECASE)),
    ("validation stamp", re.compile(r"(?:FAILED\s+)?VALIDATION:\s*(?:PASSED|FAILED)?",
                                    re.IGNORECASE)),
    ("draft header comment", re.compile(r"<!--")),
]


class PublishGuardError(RuntimeError):
    """The text about to be published still carries draft-only metadata."""


def strip_draft_metadata(text: str) -> str:
    """Remove the draft header comment and the trailing author footer."""
    text = _HEADER_RE.sub("", text, count=1)
    text = _FOOTER_RE.sub("", text, count=1)
    return text.rstrip() + "\n"


def publish_guard_violations(text: str) -> list[str]:
    """Every draft-only trace left in `text` (empty list = publishable)."""
    out = []
    for name, pat in GUARD_PATTERNS:
        for m in pat.finditer(text):
            line = text.count("\n", 0, m.start()) + 1
            out.append(f"{name} at line {line}: {m.group(0)!r}")
    return out


def failed_validation_reason(draft_text: str) -> str | None:
    """The FAILED VALIDATION stamp from the draft header, if the header has
    one (None = no failed stamp). Only the leading header comment(s) count:
    that is where generate_and_save records the validation verdict."""
    m = _HEADER_RE.match(draft_text)
    if not m:
        return None
    hit = re.search(r"FAILED\s+VALIDATION[^|>]*(?:\|[^>]*)?", m.group(0),
                    re.IGNORECASE)
    return hit.group(0).strip().rstrip("-").strip() if hit else None


def prepare_for_publish(draft_text: str) -> str:
    """Refuse a draft that failed validation, strip draft-only metadata,
    then guard the result. Raises PublishGuardError on either."""
    failed = failed_validation_reason(draft_text)
    if failed:
        raise PublishGuardError(
            "refusing to publish - the draft FAILED VALIDATION (fix and "
            f"regenerate it first): {failed[:400]}")
    clean = strip_draft_metadata(draft_text)
    bad = publish_guard_violations(clean)
    if bad:
        raise PublishGuardError(
            "refusing to publish - draft-only metadata survived the strip:\n  "
            + "\n  ".join(bad))
    return clean


def _post_to_site(match_id: str, article_text: str) -> None:
    raise NotImplementedError("Фаза 3.4: TheTopBookies publish API not wired yet")


def publish(match_id: str, article_text: str,
            poster: Callable[[str, str], None] | None = None) -> str:
    """Publish article for match_id. The draft text is cleaned and guarded
    BEFORE anything is sent; the poster only ever receives clean text.
    Idempotency (already-published check) belongs to the poster."""
    clean = prepare_for_publish(article_text)
    (poster or _post_to_site)(str(match_id), clean)
    return clean


def main() -> None:
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser(description="publish a draft (strip + guard first)")
    ap.add_argument("--match-id", required=True)
    ap.add_argument("--article-file", required=True)
    ap.add_argument("--check-only", action="store_true",
                    help="strip + guard and print the clean text; never post")
    args = ap.parse_args()
    text = Path(args.article_file).read_text(encoding="utf-8")
    if args.check_only:
        print(prepare_for_publish(text))
        print("\nPUBLISH GUARD: PASS (no draft-only metadata in the output)")
        return
    publish(args.match_id, text)


if __name__ == "__main__":
    main()
