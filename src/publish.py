"""
publish.py — pushes a finished article to TheTopBookies.

Reads the rendered article text and posts it via the site API.
Includes idempotency check to avoid duplicate publications.

Usage:
    python -m src.publish --match-id M2026_0001 --article-file article.html
"""


def publish(match_id: str, article_text: str) -> None:
    """Publish article for match_id.

    Idempotent: if the article is already published, do nothing.
    """
    raise NotImplementedError("Фаза 3: implement publish step")


if __name__ == "__main__":
    raise NotImplementedError("Фаза 3: implement CLI entry point")
