"""Guards Unstuck: the web prototype (unstuck/index.html) and its GuidedTrack version
(guidedtrack/Unstuck.gt + guidedtrack/Unstuck - owl.gt).

Three groups:
- GuidedTrack source checks for mistakes that either do not compile or fail silently
  (found while building it: *service inside *click, {variables} next to <style>, the
  audio file extension).
- The two versions carry the same copy; these tests keep them in step.
- The web prototype's flow, driven in a real browser when Playwright and Chrome are
  available (skipped otherwise, e.g. in CI), plus the proxy's own Node tests.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WEB = (ROOT / "unstuck" / "index.html").read_text(encoding="utf-8")
GT_MAIN = (ROOT / "guidedtrack" / "Unstuck.gt").read_text(encoding="utf-8")
GT_OWL = (ROOT / "guidedtrack" / "Unstuck - owl.gt").read_text(encoding="utf-8")
GT_FILES = {"Unstuck.gt": GT_MAIN, "Unstuck - owl.gt": GT_OWL}
NODE = shutil.which("node")


# ---------- helpers ----------
def gt_lines(text):
    """(indent, content) for every line that is neither blank nor a comment."""
    out = []
    for raw in text.split("\n"):
        content = raw.strip()
        if content and not content.startswith("--"):
            out.append((len(raw) - len(raw.lstrip("\t")), content))
    return out


def gt_children(text, parent_starts_with):
    """Contents of the lines indented exactly one level under the first matching line."""
    lines = gt_lines(text)
    for i, (indent, content) in enumerate(lines):
        if content.startswith(parent_starts_with):
            kids = []
            for child_indent, child in lines[i + 1:]:
                if child_indent <= indent:
                    break
                if child_indent == indent + 1:
                    kids.append(child)
            return kids
    raise AssertionError(f"no line starts with {parent_starts_with!r}")


def gt_options(text, question_starts_with):
    """Answer options of a question: its direct children that are not keywords or code."""
    return [k for k in gt_children(text, question_starts_with) if not k.startswith(("*", ">>"))]


def gt_collection(text, name):
    body = re.search(r">> %s = \[(.*)\]" % re.escape(name), text).group(1)
    return re.findall(r'"([^"]*)"', body)


def js_array(name):
    body = re.search(r"var %s = \[(.*?)\];" % re.escape(name), WEB, flags=re.S).group(1)
    return re.findall(r'"([^"]*)"', body)


def html_blocks(text):
    """The raw body of every *html block."""
    raw = text.split("\n")
    blocks = []
    for i, line in enumerate(raw):
        if line.strip() == "*html":
            indent = len(line) - len(line.lstrip("\t"))
            body = []
            for nxt in raw[i + 1:]:
                if nxt.strip() and (len(nxt) - len(nxt.lstrip("\t"))) <= indent:
                    break
                body.append(nxt)
            blocks.append("\n".join(body))
    return blocks


# ---------- helper self-checks on hand-made input ----------
def test_helpers_on_a_tiny_program():
    tiny = "*question: Pick\n\t*tip: a tip\n\tOne\n\t\t>> x = 1\n\tTwo\n-- note\n*html\n\t<p>{x}</p>\nAfter"
    assert gt_lines(tiny)[0] == (0, "*question: Pick")
    assert (2, ">> x = 1") in gt_lines(tiny)
    assert all(not content.startswith("--") for _, content in gt_lines(tiny))
    assert gt_options(tiny, "*question: Pick") == ["One", "Two"]
    assert html_blocks(tiny) == ["\t<p>{x}</p>"]
    assert gt_collection('>> things = ["a", "b c"]', "things") == ["a", "b c"]


# ---------- GuidedTrack source ----------
@pytest.mark.parametrize("name", GT_FILES)
def test_gt_indentation_is_tabs_only_and_prose_has_no_em_dashes(name):
    text = GT_FILES[name]
    assert not [l for l in text.split("\n") if l.startswith(" ")], "GuidedTrack blocks are tab-indented"
    assert "—" not in text


def test_every_goto_points_at_exactly_one_label():
    labels = re.findall(r"^\t*\*label: (\w+)$", GT_MAIN, flags=re.M)
    gotos = set(re.findall(r"^\t*\*goto: (\w+)$", GT_MAIN, flags=re.M))
    assert len(labels) == len(set(labels)), "duplicate label"
    assert gotos and gotos <= set(labels)


def test_service_is_never_inside_a_click_block():
    """*service under *click fails with 'Could not compile' (verified on guidedtrack.com)."""
    stack, found = [], 0
    for indent, content in gt_lines(GT_MAIN):
        while stack and stack[-1][0] >= indent:
            stack.pop()
        if content.startswith("*service"):
            found += 1
            assert not any(parent.startswith("*click") for _, parent in stack)
        stack.append((indent, content))
    assert found == 1


@pytest.mark.parametrize("name", GT_FILES)
def test_html_blocks_with_a_style_tag_use_no_variables(name):
    """GuidedTrack leaves {variables} unfilled in an *html block that also holds <style>."""
    for block in html_blocks(GT_FILES[name]):
        if "<style" in block:
            outside_css = re.sub(r"<style.*?</style>", "", block, flags=re.S)
            assert "{" not in outside_css, outside_css.strip()[:120]


def test_chime_is_an_mp3():
    """*audio rewrites the extension and requests only .mp3 and .ogg."""
    url = re.search(r"^\*audio: (\S+)$", GT_MAIN, flags=re.M).group(1)
    assert url == "https://programs.clearerthinking.org/unstuck/chime.mp3"


def test_owl_subprogram_covers_all_seven_stages():
    for name in ("owlLabels", "owlCaptions", "owlDotRows"):
        assert len(gt_collection(GT_OWL, name)) == 7, name
    assert [row.count("●") for row in gt_collection(GT_OWL, "owlDotRows")] == [1, 2, 3, 4, 5, 6, 7]
    for stage in range(7):
        assert f".uo.s{stage} " in GT_OWL, f"no CSS for stage {stage}"
    assert 'class="uo s{owlStage}"' in GT_OWL


def test_fast_mode_shortens_every_timer():
    for name in ("timerLength", "stretchLength", "breathLength", "inhaleLength"):
        assert len(re.findall(r">> %s = \d+\.(?:seconds|minutes)" % name, GT_MAIN)) == 2, name
        assert f"*countdown: {name}" in GT_MAIN


# ---------- the two versions say the same thing ----------
def test_owl_stage_names_and_captions_match():
    assert gt_collection(GT_OWL, "owlLabels") == js_array("OWL_STAGES")
    assert gt_collection(GT_OWL, "owlCaptions") == js_array("OWL_CAPTIONS")


def test_encouragement_messages_match():
    assert gt_collection(GT_MAIN, "owlMessages") == js_array("MESSAGES")


def test_causes_match():
    web = [m[1] for m in re.findall(r"label:\s*(['\"])(.*?)\1", WEB)]
    assert gt_options(GT_MAIN, "*question: What's keeping you stuck right now?") == web
    assert web == ["Anxiety", "Low motivation", "Tiredness", "Difficulty focusing", "Not sure"]


def test_anxiety_presets_match():
    assert gt_options(GT_MAIN, "*question: Briefly describe what you're feeling") == js_array("FEAR_PRESETS")


def test_checklists_match():
    def web_items(prefix):
        return re.findall(r'id="%s\d"[^>]*>\s*<span>(.*?)</span>' % prefix, WEB)

    fatigue = gt_options(GT_MAIN, "*question: A few more quick pick-me-ups.")
    focusing = gt_options(GT_MAIN, "*question: What will you do before you start?")
    assert fatigue == web_items("fatigueCheck") and len(fatigue) == 3
    assert focusing == web_items("distractionCheck") and len(focusing) == 5


# ---------- Travis's review (2026-10-23), static side ----------
def test_no_one_minute_promise_and_no_water_warning():
    for text in (WEB, GT_MAIN):
        assert "one-minute" not in text
        assert "near water" not in text
        assert "stay seated" in text


def test_motivation_technique_does_not_ask_for_the_tiny_step():
    web_block = WEB[WEB.index('id="step-technique-motivation"'):WEB.index('id="step-technique-fatigue"')]
    assert "tiny step" not in web_block and "<textarea" not in web_block
    gt_start = GT_MAIN.index('*if: cause = "motivation"')
    gt_block = GT_MAIN[gt_start:GT_MAIN.index('*if: cause = "fatigue"')]
    assert "tiny step" not in gt_block
    assert GT_MAIN.count("What's one tiny step you could take right now") == 1


def test_tiredness_times_only_the_stretch_and_the_breathing():
    stages = re.search(r"var FATIGUE_STAGES = \[(.*?)\n  \];", WEB, flags=re.S).group(1)
    assert stages.count("seconds:") == 2
    gt_start = GT_MAIN.index('*if: cause = "fatigue"')
    gt_block = GT_MAIN[gt_start:GT_MAIN.index('*if: cause = "distraction"')]
    assert gt_block.count("*countdown:") == 2


def test_ai_error_says_to_try_again():
    assert "Try again, or just describe it yourself." in WEB
    assert "Try again, or just describe it yourself." in GT_MAIN


# ---------- the proxy's own tests ----------
@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_suggest_api_node_tests_pass():
    result = subprocess.run([NODE, "--test"], cwd=ROOT / "unstuck" / "unstuck-suggest-api",
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]


# ---------- the web prototype in a real browser ----------
@pytest.fixture(scope="module")
def page():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except Exception as exc:  # Chrome is not installed (e.g. CI)
            pytest.skip(f"Chrome is not available: {exc}")
        pg = browser.new_page(viewport={"width": 1100, "height": 900})
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e)))
        yield pg
        browser.close()


def _open(page, route_body=None, route_status=200):
    page.unroute("**/api/suggest")
    if route_body is not None:
        page.route("**/api/suggest", lambda r: r.fulfill(
            status=route_status, content_type="application/json", body=route_body,
            headers={"Access-Control-Allow-Origin": "*"}))
    page.goto((ROOT / "unstuck" / "index.html").as_uri() + "?fast=1")
    page.evaluate("localStorage.clear()")
    page.reload()


def _step(page):
    return page.evaluate("document.querySelector('.step.active').id")


def test_browser_task_comes_first_then_cause_then_technique(page):
    _open(page)
    assert _step(page) == "step-task"
    page.fill("#taskInput", "Write the quarterly report")
    page.click("#taskContinue")
    assert _step(page) == "step-cause"
    assert "Write the quarterly report" in page.inner_text("#causeTaskRecap")

    page.click(".cause-card:nth-child(2)")  # Low motivation
    assert _step(page) == "step-technique-motivation"
    assert "Write the quarterly report" in page.inner_text("#motivationTaskRecap")
    assert "imagine this task is already done" in page.inner_text("#motivationStage1")
    page.click("#motivationStage1Continue")
    page.click("#motivationWorthChips .chip")
    page.click("#motivationStage2Continue")
    assert _step(page) == "step-action"
    assert page.inner_text("#actionTitle").startswith("What's one tiny step")
    page.click("#actionBack")
    assert _step(page) == "step-cause"

    page.click(".cause-card:nth-child(5)")  # Not sure goes straight to the step
    assert _step(page) == "step-action"
    assert page.errors == []


def test_browser_tiredness_has_two_timers_then_a_checklist(page):
    _open(page)
    page.fill("#taskInput", "Clean the garage")
    page.click("#taskContinue")
    page.click(".cause-card:nth-child(3)")
    assert "stretch" in page.inner_text("#fatigueMsg")
    page.click("#fatigueSkipTimer")
    assert "breathe fast" in page.inner_text("#fatigueMsg")
    assert page.is_hidden("#fatigueChecklistStage")
    page.click("#fatigueSkipTimer")
    assert page.is_visible("#fatigueChecklistStage") and page.is_hidden("#fatigueTimerStage")
    assert page.locator("#fatigueChecklistStage input[type=checkbox]").count() == 3
    page.click("#fatigueChecklistNext")  # nothing ticked: the items are optional
    page.click("#fatigueFeelChips .chip")
    assert _step(page) == "step-action"
    assert page.errors == []


def test_browser_owl_grows_in_seven_distinct_stages_and_can_be_hatched_again(page):
    _open(page)
    page.fill("#taskInput", "Study for the exam")
    page.click("#taskContinue")
    page.click(".cause-card:nth-child(5)")
    drawings, feet = [], []
    for stage in range(7):
        drawings.append(page.inner_html("#owlSvgHolder"))
        feet.append(page.locator("#owlSvgHolder path[stroke='#f8911b'][stroke-width='5']").count())
        assert page.is_visible("#hatchNewOwl") == (stage == 6)
        if stage == 6:
            break
        page.fill("#actionInput", f"step {stage}")
        page.click("#actionContinue")
        page.click("#confirmStart")
        page.click("#timerSkip")
        assert _step(page) == "step-cycledone"
        page.click("#cycleContinue")
    assert len(set(drawings)) == 7
    assert feet == [0, 0, 2, 2, 2, 2, 2], "every hatched owl has exactly two feet"
    scales = [float(re.search(r"scale\(([\d.]+)\)", d).group(1)) for d in drawings[2:]]
    assert scales == sorted(scales) and len(set(scales)) == 5, "each stage is bigger than the last"

    assert page.inner_text("#owlShelf").startswith("Owls grown today: 1")
    page.click("#hatchNewOwl")
    assert page.inner_text("#owlStageLabel").strip().lower() == "egg"
    assert page.inner_text("#owlShelf").startswith("Owls grown today: 1")
    assert page.is_hidden("#hatchNewOwl")
    assert page.errors == []


def test_browser_ai_suggestion_fills_the_step_and_failure_says_try_again(page):
    _open(page, '{"suggestion": "Open the doc and write three bullet points.", "tooBroad": false}')
    page.fill("#taskInput", "Write the report")
    page.click("#taskContinue")
    page.click(".cause-card:nth-child(5)")
    page.click("#aiSuggestBtn")
    page.wait_for_function("document.getElementById('actionInput').value.length > 0")
    assert page.input_value("#actionInput") == "Open the doc and write three bullet points."
    assert page.is_enabled("#actionContinue")

    _open(page, '{"error": "AI suggestion failed (Gemini 503 UNAVAILABLE)"}', 502)
    page.fill("#taskInput", "Write the report")
    page.click("#taskContinue")
    page.click(".cause-card:nth-child(5)")
    page.click("#aiSuggestBtn")
    page.wait_for_selector("#aiErrorNote", state="visible")
    note = page.inner_text("#aiErrorNote")
    assert "Gemini 503 UNAVAILABLE" in note and note.endswith("Try again, or just describe it yourself.")
