"""Tests for the "Get Coaching" floating button on the tool pages: gtm/coaching_fab_tools.html (the GTM tag body)
and gtm/coaching_fab_tools_list.py (the script that writes its list of tools).

The snippet's own JavaScript is run in Node with a minimal fake page, so the page rule under test is the real one.
Those tests are skipped where Node is not installed.
"""
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

GTM = Path(__file__).resolve().parents[1] / "gtm"
SNIPPET = GTM / "coaching_fab_tools.html"
spec = importlib.util.spec_from_file_location("coaching_fab_tools_list", GTM / "coaching_fab_tools_list.py")
fab = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fab)

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def card(title, link):
    return (f'<div><h2 class="t"><span>{title}</span></h2><p>Some description.</p><span>Minutes</span>'
            f'<a class="btn" href="{link}" target="_blank"><span>Start</span></a></div>')


PAGE = ('<nav><a href="https://programs.clearerthinking.org/cognitive-test-intro.html">Cognitive Assessment</a></nav>'
        + card("Life Changing Questions", "https://programs.clearerthinking.org/lcq.html")
        + card("Unique Traits Test", "https://programs.clearerthinking.org/unique-traits-test/")
        + card("Step Back From Your Thoughts", "https://programs.clearerthinking.org/Cognitive_Defusion")
        + card("Tom &amp; Jerry&#39;s Quiz", "https://programs.clearerthinking.org/quiz.html?a=1&amp;b=2")
        + card("Society Explained", "https://society.clearerthinking.org/")
        + card("Cognitive Assessment", "https://programs.clearerthinking.org/cognitive-test-intro.html"))


# ---- the list script: pure functions, answers worked out by hand ----

@pytest.mark.parametrize("raw, expected", [
    ("/lcq.html", "/lcq"),
    ("/unique-traits-test/", "/unique-traits-test"),
    ("/unique-traits-test/index.html", "/unique-traits-test"),
    ("/Cognitive_Defusion", "/cognitive_defusion"),
    ("/understanding-your-morality/report/", "/understanding-your-morality/report"),
    ("/cognitive-test-intro.html/", "/cognitive-test-intro"),
    ("/rationality-report/skeptic.html", "/rationality-report/skeptic"),
    ("/index.html", ""),
    ("/", ""),
])
def test_normalize_path(raw, expected):
    assert fab.normalize_path(raw) == expected


def test_parse_cards_reads_each_start_link_with_its_title_and_skips_the_menu():
    assert fab.parse_cards(PAGE) == [
        ("Life Changing Questions", "https://programs.clearerthinking.org/lcq.html"),
        ("Unique Traits Test", "https://programs.clearerthinking.org/unique-traits-test/"),
        ("Step Back From Your Thoughts", "https://programs.clearerthinking.org/Cognitive_Defusion"),
        ("Tom & Jerry's Quiz", "https://programs.clearerthinking.org/quiz.html?a=1&b=2"),
        ("Society Explained", "https://society.clearerthinking.org/"),
        ("Cognitive Assessment", "https://programs.clearerthinking.org/cognitive-test-intro.html"),
    ]


def test_tool_entries_keeps_the_tools_host_only_drops_kept_off_pages_and_sorts():
    entries = fab.tool_entries(fab.parse_cards(PAGE), keep_off={"/cognitive-test-intro": "paid page"})
    assert entries == [
        ("/cognitive_defusion", "Step Back From Your Thoughts"),
        ("/lcq", "Life Changing Questions"),
        ("/quiz", "Tom & Jerry's Quiz"),
        ("/unique-traits-test", "Unique Traits Test"),
    ]


def test_render_block_has_no_comma_after_the_last_entry_and_round_trips():
    entries = [("/a_tool", "A Tool"), ("/b", "B, the second")]
    block = fab.render_block(entries, keep_off={"/paid": "paid page"}, indent="  ")
    assert block.splitlines() == [
        "  // BEGIN TOOLS (written by gtm/coaching_fab_tools_list.py, do not edit by hand)",
        "  '/a_tool', // A Tool",                     # comments line up one space after the longest entry
        "  '/b'       // B, the second",
        "  // kept off on purpose: /paid: paid page",
        "  // END TOOLS",
    ]
    assert fab.block_entries(block) == entries
    before, found, after = fab.split_snippet("var T = [\n" + block + "\n];\n")
    assert (before, found, after) == ("var T = [\n", block, "\n];\n")


def test_split_snippet_complains_when_the_markers_are_missing():
    with pytest.raises(ValueError):
        fab.split_snippet("var T = [];")


# ---- the committed snippet ----

def snippet_script():
    return re.search(r"<script>(.*?)</script>", SNIPPET.read_text(encoding="utf-8"), re.S).group(1)


def test_snippet_list_is_exactly_what_the_script_writes():
    _, block, _ = fab.split_snippet(SNIPPET.read_text(encoding="utf-8"))
    entries = fab.block_entries(block)
    assert fab.render_block(entries) == block                       # nobody edited the list by hand
    paths = [path for path, _ in entries]
    assert paths == sorted(set(paths)) and len(paths) >= 90         # sorted, no duplicates, the full tools page
    assert all(path == fab.normalize_path(path) and path.startswith("/") for path in paths)
    assert not set(paths) & set(fab.KEEP_OFF)


def test_snippet_script_stays_es5_for_the_gtm_compiler():
    code = re.sub(r"(^|\s)//[^\n]*", r"\1", snippet_script())        # drop comments (URLs have no space before //)
    assert "=>" not in code and "`" not in code
    assert not re.search(r"\b(let|const|class)\s+[A-Za-z_$]", code)
    assert not re.search(r"^\s*function\s+[A-Za-z_$]", code, re.M)   # no function declaration inside the try block


HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const script = fs.readFileSync(process.argv[2], 'utf8').match(/<script>([\s\S]*?)<\/script>/)[1];
const cases = JSON.parse(process.argv[3]);
const shown = cases.map(function (c) {
  let appended = 0;
  const element = function () {
    return { className: '', style: {}, href: '', classList: { add() {}, toggle() {} },
             setAttribute() {}, addEventListener() {} };
  };
  const document = {
    querySelector: function (sel) { return sel === '.ct-coaching-fab' && c.existing ? {} : null; },
    getElementById: function () { return null; },
    createElement: element,
    body: { contains: function () { return false; }, appendChild: function () { appended += 1; } },
    documentElement: { classList: { add() {}, toggle() {} } },
  };
  const top = {};
  const window = { top: top, self: c.framed ? {} : top, innerWidth: 1200, addEventListener() {} };
  vm.runInNewContext(script, {
    window: window, document: document,
    location: { hostname: c.hostname || 'programs.clearerthinking.org', pathname: c.pathname },
    MutationObserver: function () { this.observe = function () {}; },
    requestAnimationFrame: function () {},
  });
  return appended;
});
console.log(JSON.stringify(shown));
"""


def run_snippet(cases, tmp_path):
    """How many times the snippet adds its button to the page, for each case."""
    harness = tmp_path / "harness.js"
    harness.write_text(HARNESS)
    out = subprocess.run([NODE, str(harness), str(SNIPPET), json.dumps(cases)], capture_output=True, text=True, timeout=60)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


SHOWN = [
    "/lcq.html",                                    # a listed tool
    "/personality-test.html",
    "/who_attracts_you_study.html",
    "/unique-traits-test/",                         # listed with a trailing slash
    "/unique-traits-test/index.html",
    "/Cognitive_Defusion",                          # listed with capitals and no .html
    "/understanding-your-morality",
    "/understanding-your-morality/report/",         # a tool's sub-page counts as the tool
    "/personality_report.html",                     # result pages kept by hand
    "/rationality-report/skeptic.html",
    "/pathkeeper.html",
    "/pathkeeper_intro.html",
]
HIDDEN = [
    "/",
    "/dashboard.html",
    "/mailing-list/unsubscribe/",
    "/productivity-workshop/",
    "/unanswered-questions-in-psychology/",
    "/cognitive-test-intro.html",                   # on the tools page, kept off on purpose
    "/cognitive-test.html",
    "/personality-test-pdf-generator/",             # not a sub-page of /personality-test
    "/personality-test-for-teams.html",
    "/p/hive/worlds-biggest-problems-quiz/",        # partner-branded copy of a listed tool
    "/perk_request/",
    "/lcq_something_else.html",
]


@needs_node
def test_button_shows_on_listed_tools_and_their_result_pages_only(tmp_path):
    cases = [{"pathname": p} for p in SHOWN + HIDDEN]
    assert run_snippet(cases, tmp_path) == [1] * len(SHOWN) + [0] * len(HIDDEN)


@needs_node
def test_every_listed_tool_shows_the_button_in_all_its_address_forms(tmp_path):
    _, block, _ = fab.split_snippet(SNIPPET.read_text(encoding="utf-8"))
    paths = [path for path, _ in fab.block_entries(block)]
    cases = [{"pathname": p + suffix} for p in paths for suffix in ("", ".html", "/", "/index.html")]
    assert run_snippet(cases, tmp_path) == [1] * len(cases)


@needs_node
def test_guards_still_hold_on_a_listed_tool(tmp_path):
    cases = [
        {"pathname": "/lcq.html", "hostname": "www.clearerthinking.org"},   # the Wix site has its own button
        {"pathname": "/lcq.html", "framed": True},                          # tool framed inside another page
        {"pathname": "/lcq.html", "existing": True},                        # tag fired twice
    ]
    assert run_snippet(cases, tmp_path) == [0, 0, 0]
