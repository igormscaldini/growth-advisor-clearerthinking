import json

import wix_ricos as wr


def runs(node):
    return [(r["textData"]["text"], sorted(d["type"] for d in r["textData"]["decorations"])) for r in node["nodes"]]


def test_paragraph_with_mixed_runs_and_link():
    nodes = wr.html_to_nodes('<p>Read <strong>this <em>now</em></strong> or <a href="https://x.org/a?b=1&amp;c=2">later</a>.</p>')
    assert len(nodes) == 1 and nodes[0]["type"] == "PARAGRAPH"
    assert runs(nodes[0]) == [
        ("Read ", []), ("this ", ["BOLD"]), ("now", ["BOLD", "ITALIC"]), (" or ", []), ("later", ["LINK"]), (".", []),
    ]
    link = nodes[0]["nodes"][4]["textData"]["decorations"][0]["linkData"]["link"]
    assert link == {"url": "https://x.org/a?b=1&c=2", "target": "BLANK"}  # entity decoded once


def test_headings_lists_quotes_nest_text_inside_paragraphs():
    html = ('<h2>Title</h2><ul><li>one</li><li><p>two <em>x</em></p></li></ul>'
            '<ol><li>first</li></ol><div class="ct-quote ct-italic"><strong>Q:</strong> why?</div>')
    nodes = wr.html_to_nodes(html)
    assert [n["type"] for n in nodes] == ["HEADING", "BULLETED_LIST", "ORDERED_LIST", "BLOCKQUOTE"]
    assert nodes[0]["headingData"]["level"] == 2
    items = nodes[1]["nodes"]
    assert [i["type"] for i in items] == ["LIST_ITEM", "LIST_ITEM"]
    assert items[0]["nodes"][0]["type"] == "PARAGRAPH"  # never a bare TEXT in a LIST_ITEM
    assert runs(items[1]["nodes"][0]) == [("two ", []), ("x", ["ITALIC"])]
    quote = nodes[3]
    assert quote["nodes"][0]["type"] == "PARAGRAPH"
    assert runs(quote["nodes"][0]) == [("Q:", ["BOLD", "ITALIC"]), (" why?", ["ITALIC"])]


def test_image_and_caption_and_byline_alignment():
    html = ('<p class="ct-byline">By A and B</p><img data-id="abc~mv2.png" data-w="800" data-h="400" alt="hero">'
            '<p class="ct-caption">Chart (<a href="https://doi.org/1">source</a>)</p><p>Body.</p>')
    nodes = wr.html_to_nodes(html)
    assert [n["type"] for n in nodes] == ["PARAGRAPH", "IMAGE", "PARAGRAPH", "PARAGRAPH"]
    assert nodes[0]["paragraphData"]["textStyle"]["textAlignment"] == "CENTER"
    img = nodes[1]["imageData"]
    assert img["image"] == {"src": {"id": "abc~mv2.png"}, "width": 800, "height": 400} and img["altText"] == "hero"
    assert all("ITALIC" in deco for _, deco in runs(nodes[2]))  # caption is italic throughout
    assert runs(nodes[3]) == [("Body.", [])]  # italic did not leak past the caption


def test_whitespace_collapses_and_empty_blocks_vanish():
    nodes = wr.html_to_nodes("<p>  a \n\t b  </p><p>   </p><ul></ul>")
    assert len(nodes) == 1 and runs(nodes[0]) == [("a b", [])]


def test_spacers_follow_images_lists_quotes_buttons_only():
    nodes = [wr.paragraph([wr.text_node("a")]), wr.image("i", 1, 1), wr.paragraph([wr.text_node("b")]),
             wr.button("Go", "https://x"), wr.paragraph([wr.text_node("c")])]
    types = [n["type"] for n in wr.with_spacers(nodes)]
    assert types == ["PARAGRAPH", "IMAGE", "PARAGRAPH", "PARAGRAPH", "BUTTON", "PARAGRAPH", "PARAGRAPH"]
    assert "nodes" not in wr.with_spacers(nodes)[2]  # the spacer is an empty paragraph


def test_document_is_json_serialisable_and_types_are_strings():
    doc = {"nodes": wr.with_spacers(wr.html_to_nodes("<h3>t</h3><p><b>x</b></p><img data-id='m' data-w='2' data-h='3'>"))}
    text = json.dumps(doc)
    assert '"type": {' not in text


def test_plain_text_round_trip():
    nodes = wr.html_to_nodes("<h2>T</h2><p>one <b>two</b></p><ul><li>three</li></ul>")
    assert wr.plain_text(nodes) == "T\none two\nthree"
