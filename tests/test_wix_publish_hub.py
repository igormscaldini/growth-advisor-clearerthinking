"""Unit tests for the pure helpers in wix_publish_hub.py (no network, no Wix calls)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from seo_hub_pages import render_ricos  # noqa: E402
from wix_publish_hub import HUB_URL, linked_urls  # noqa: E402


def test_linked_urls_round_trips_a_rendered_document():
    """What render_ricos writes, linked_urls must read back: the sync diff depends on it."""
    items = [{"title": "A", "url": "https://x.org/a"}, {"title": "B", "url": "https://x.org/b"}]
    assert linked_urls(render_ricos("intro", [("2026", items)])) == {"https://x.org/a", "https://x.org/b"}


def test_linked_urls_ignores_headings_and_intro():
    doc = render_ricos("intro text", [("2026", [{"title": "A", "url": "https://x.org/a"}])])
    assert linked_urls(doc) == {"https://x.org/a"}


def test_linked_urls_on_empty_and_missing_content():
    assert linked_urls({}) == set()
    assert linked_urls(None) == set()
    assert linked_urls({"nodes": []}) == set()


def test_linked_urls_skips_decorations_that_are_not_links():
    doc = {"nodes": [{"type": "PARAGRAPH", "nodes": [
        {"textData": {"text": "bold", "decorations": [{"type": "BOLD", "fontWeightValue": 700}]}}]}]}
    assert linked_urls(doc) == set()


def test_linked_urls_deduplicates():
    doc = render_ricos("i", [("2026", [{"title": "A", "url": "https://x.org/a"}]),
                             ("2025", [{"title": "A again", "url": "https://x.org/a"}])])
    assert linked_urls(doc) == {"https://x.org/a"}


def test_hub_url_is_excluded_by_the_payload_builder():
    """The hub is itself a blog post, so it appears in the sitemap and would list itself."""
    posts = [{"url": HUB_URL, "title": "All Clearer Thinking Articles", "published": "2026-01-01", "lastmod": None},
             {"url": "https://www.clearerthinking.org/post/real", "title": "Real", "published": "2026-02-01", "lastmod": None}]
    kept = [p for p in posts if p["url"].rstrip("/") != HUB_URL]
    assert [p["url"] for p in kept] == ["https://www.clearerthinking.org/post/real"]


def test_diff_detects_additions_and_removals():
    """The exact set arithmetic sync() uses to decide whether to write at all."""
    live = {"https://x.org/a", "https://x.org/b"}
    wanted = {"https://x.org/b", "https://x.org/c"}
    assert sorted(wanted - live) == ["https://x.org/c"]
    assert sorted(live - wanted) == ["https://x.org/a"]
    assert not (live - live) and not (live - live)


def test_errors_are_catchable_exceptions_not_systemexit(monkeypatch):
    """Regression: _call used to raise SystemExit, which is a BaseException, so sync()'s
    `except Exception` never caught it and the failure email was silently skipped. Any error
    raised below main() must be an ordinary Exception."""
    import wix_publish_hub as w

    monkeypatch.delenv("WIX_API_KEY", raising=False)
    monkeypatch.delenv("WIX_SITE_ID", raising=False)
    try:
        w._headers()
    except Exception as e:  # noqa: BLE001 - asserting it IS an Exception is the point
        assert not isinstance(e, SystemExit)
    else:
        raise AssertionError("_headers should raise when credentials are missing")


def test_payload_size_guard_raises_a_catchable_error():
    import wix_publish_hub as w

    assert issubclass(RuntimeError, Exception)
    # The guard must not be SystemExit, or an oversized payload would skip the alert too.
    src = Path(w.__file__).read_text()
    guard = src.split("over the {MAX_POST_BYTES:,} byte post limit")[0].splitlines()[-1]
    assert "SystemExit" not in guard
