"""Guards the astrology prize landing page (landing_pages/astrology_prize/).

The page's copy is static HTML, while the prize, the pass mark and the 2024 study figures live in
logic.js. These tests keep the two in step, re-derive the odds independently in Python, and run the
JavaScript unit tests so CI covers them too.
"""
import json
import math
import re
import shutil
import struct
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

LP = Path(__file__).resolve().parents[1] / "landing_pages" / "astrology_prize"
HTML = (LP / "index.html").read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


class _Page(HTMLParser):
    """Collects the text a reader sees, the meta tags and the local files the page loads."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.text, self.meta, self.links, self.assets = [], {}, {}, []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style"):
            self._skip += 1
        if tag == "meta" and (a.get("property") or a.get("name")):
            self.meta[a.get("property") or a.get("name")] = a.get("content", "")
        if tag == "link" and a.get("rel"):
            self.links[a["rel"]] = a.get("href", "")
        for key in ("src", "href"):
            value = a.get(key, "")
            if tag in ("script", "img") and value and "://" not in value:
                self.assets.append(value)
        for key in ("data-stat", "aria-label", "alt"):
            if a.get(key):
                self.text.append(a[key])

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)


@pytest.fixture(scope="module")
def page():
    parser = _Page()
    parser.feed(HTML)
    parser.copy = re.sub(r"\s+", " ", " ".join(parser.text + list(parser.meta.values())))
    return parser


@pytest.fixture(scope="module")
def logic():
    """CONFIG and STUDY_2024 as the page's own JavaScript defines them."""
    if NODE is None:
        pytest.skip("node is not installed")
    script = "const L = require('./logic.js'); console.log(JSON.stringify({config: L.CONFIG, study: L.STUDY_2024}))"
    out = subprocess.run([NODE, "-e", script], cwd=LP, capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def money(amount):
    return f"${amount:,.0f}"


@needs_node
def test_javascript_unit_tests_pass():
    run = subprocess.run([NODE, "--test", "logic.test.js"], cwd=LP, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout[-3000:] + run.stderr[-1000:]


@pytest.mark.parametrize("name", ["index.html", "og_card.html", "logic.js"])
def test_no_em_or_en_dashes(name):
    source = (LP / name).read_text(encoding="utf-8")
    found = re.findall(r".{0,30}(?:—|–|&mdash;|&ndash;|\\u2014|\\u2013).{0,30}", source)
    assert not found, found


def test_copy_states_the_configured_prize_and_pass_mark(page, logic):
    config, study = logic["config"], logic["study"]
    prize, bar = money(config["prize"]), f'{config["bar"]} of {config["questions"]}'
    assert page.copy.count(prize) >= 5
    assert page.copy.count(bar) >= 5
    assert prize in page.meta["og:description"] and bar in page.meta["og:description"]
    assert prize in page.meta["description"] and bar in page.meta["description"]
    # every dollar figure on the page is the prize, the 2024 prize, the unpaid $0 or Randi's million
    allowed = {prize, money(study["prize"]), "$0", "$1,000,000"}
    assert set(re.findall(r"\$[\d,]*\d", page.copy)) <= allowed
    # no other "match N of 12" crept in (5 = the best 2024 score, 10 = what experts believed they got)
    marks = set(re.findall(r"match(?:ed)? (?:at least |about )?(\d+) of %d\b" % config["questions"], page.copy))
    assert str(config["bar"]) in marks
    assert marks <= {str(config["bar"]), str(study["bestScore"]), "10"}, marks


def test_odds_claim_matches_an_independent_calculation(page, logic):
    config = logic["config"]
    n, bar, p = config["questions"], config["bar"], 1 / config["options"]
    tail = sum(math.comb(n, k) * p**k * (1 - p) ** (n - k) for k in range(bar, n + 1))
    one_in = 1 / tail
    assert 4.9e6 < one_in < 5.1e6            # by hand: 1 / (12 * 0.2^11 * 0.8 + 0.2^12) = 4,982,462
    claims = re.findall(r"once in ([\d.]+) million tries", page.copy)
    assert len(claims) >= 2
    assert all(float(c) == float(f"{one_in / 1e6:.1g}") for c in claims), claims


def test_copy_states_the_2024_study_figures(page, logic):
    config, study = logic["config"], logic["study"]
    assert f'{study["astrologers"]} astrologers' in page.copy
    assert str(study["meanScore"]) in page.copy
    chance_mean = config["questions"] / config["options"]
    assert chance_mean == 2.4 and f"averages {chance_mean}" in page.copy
    assert f'matched {study["bestScore"]} of {config["questions"]}' in page.copy
    assert f'{config["questions"]} real people' in page.copy
    assert "multiplied the prize by %d" % (config["prize"] / study["prize"]) in page.copy


def test_social_sharing_tags(page):
    for key in ("og:title", "og:description", "og:image", "og:url", "twitter:title", "twitter:description", "twitter:image"):
        assert page.meta.get(key), key
    assert page.meta["twitter:card"] == "summary_large_image"
    assert page.meta["og:url"] == page.links["canonical"]
    assert page.meta["og:image"] == page.meta["twitter:image"]
    assert page.meta["og:image"].startswith(page.links["canonical"].rstrip("/") + "/")
    assert len(page.meta["og:title"]) <= 60
    assert len(page.meta["og:description"]) <= 160


def test_share_image_exists_at_the_declared_size(page):
    png = LP / page.meta["og:image"].rsplit("/", 1)[1]
    header = png.read_bytes()[:24]
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", header[16:24])
    assert (str(width), str(height)) == (page.meta["og:image:width"], page.meta["og:image:height"]) == ("1200", "630")
    assert png.stat().st_size < 1_000_000


def test_local_files_the_page_loads_exist(page):
    assert "logic.js" in page.assets
    for asset in page.assets:
        assert (LP / asset).is_file(), asset


def test_draft_ribbon_and_noindex_travel_together():
    # Launching means removing both; one without the other is a half-published page.
    is_draft = 'class="is-draft"' in HTML
    assert is_draft == (page_robots() == "noindex")


def page_robots():
    match = re.search(r'<meta name="robots" content="([^"]*)"', HTML)
    return match.group(1) if match else ""
