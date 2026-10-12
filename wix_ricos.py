"""Convert a small, well-formed HTML subset into a Wix Ricos document (the Blog API's richContent).

Wix's own HTML-to-Ricos converter needs a "Manage Ricos Document" scope that the Blog-only API
key does not have (HTTP 403, checked 2026-10-12), so this does the job locally. It covers what
Clearer Thinking articles use: p, h1-h6, ul/ol/li, strong/b, em/i, a, sup, br, blockquote or a
div with class ct-quote, and img. Images must already be in the Wix Media Manager: an <img>
carries data-id (the media id), data-w, data-h and alt, because Ricos IMAGE nodes do not render
external URLs. Node shapes follow https://dev.wix.com/docs/api-reference/assets/rich-content/skills/author-ricos-rich-content.
"""
from __future__ import annotations

import re
from html.parser import HTMLParser

CENTER = {"textStyle": {"textAlignment": "CENTER"}}
AUTO = {"textStyle": {"textAlignment": "AUTO"}}
SPACER = {"type": "PARAGRAPH"}
HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


def text_node(text: str, bold: bool = False, italic: bool = False, url: str | None = None) -> dict:
    decorations = []
    if bold:
        decorations.append({"type": "BOLD", "fontWeightValue": 700})
    if italic:
        decorations.append({"type": "ITALIC", "italicData": True})
    if url:
        decorations.append({"type": "LINK", "linkData": {"link": {"url": url, "target": "BLANK"}}})
    return {"type": "TEXT", "textData": {"text": text, "decorations": decorations}}


def paragraph(runs: list[dict], center: bool = False) -> dict:
    return {"type": "PARAGRAPH", "nodes": runs, "paragraphData": CENTER if center else AUTO}


def heading(runs: list[dict], level: int, center: bool = False) -> dict:
    return {"type": "HEADING", "nodes": runs, "headingData": {"level": level, **(CENTER if center else AUTO)}}


def image(media_id: str, width: int, height: int, alt: str = "") -> dict:
    return {
        "type": "IMAGE",
        "nodes": [],
        "imageData": {
            "containerData": {"width": {"size": "CONTENT"}, "alignment": "CENTER"},
            "image": {"src": {"id": media_id}, "width": width, "height": height},
            "altText": alt,
        },
    }


def button(text: str, url: str, background: str = "#F8911B") -> dict:
    return {
        "type": "BUTTON",
        "buttonData": {
            "type": "LINK",
            "text": text,
            "link": {"url": url, "target": "BLANK"},
            "containerData": {"alignment": "CENTER", "width": {"size": "ORIGINAL"}, "textWrap": True},
            "styles": {"borderRadius": 8, "borderWidth": 0, "backgroundColor": background, "textColor": "#FFFFFF"},
        },
    }


class _Converter(HTMLParser):
    """Streams HTML into Ricos nodes. Text runs merge while their formatting stays the same."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.nodes: list[dict] = []
        self.containers: list[dict] = []  # open BLOCKQUOTE / list / LIST_ITEM nodes
        self.block: dict | None = None  # the PARAGRAPH or HEADING being filled
        self.bold = 0
        self.italic = 0
        self.links: list[str] = []
        self.pending_center = False

    # -- helpers -------------------------------------------------------------------------------
    def _target(self) -> list[dict]:
        return self.containers[-1]["nodes"] if self.containers else self.nodes

    def _open_block(self, node: dict) -> None:
        self._close_block()
        self.block = node

    def _close_block(self) -> None:
        if self.block is None:
            return
        runs = self.block["nodes"]
        if runs:
            runs[0]["textData"]["text"] = runs[0]["textData"]["text"].lstrip()
            runs[-1]["textData"]["text"] = runs[-1]["textData"]["text"].rstrip()
            runs = [r for r in runs if r["textData"]["text"]]
            self.block["nodes"] = runs
        if runs:
            self._target().append(self.block)
        self.block = None

    def _append_text(self, text: str) -> None:
        if self.block is None:
            if not text.strip():
                return
            self.block = paragraph([])  # stray text outside any block gets its own paragraph
        run = text_node(text, bool(self.bold), bool(self.italic), self.links[-1] if self.links else None)
        runs = self.block["nodes"]
        if runs and runs[-1]["textData"]["decorations"] == run["textData"]["decorations"]:
            runs[-1]["textData"]["text"] += text
        else:
            runs.append(run)

    # -- parser callbacks ------------------------------------------------------------------------
    def handle_starttag(self, tag: str, attrs: list) -> None:
        a = dict(attrs)
        classes = (a.get("class") or "").split()
        center = "ct-byline" in classes or "ct-caption" in classes
        if tag == "p":
            self._open_block(paragraph([], center=center))
            if "ct-caption" in classes:
                self.italic += 1
        elif tag in HEADINGS:
            self._open_block(heading([], HEADINGS[tag], center=center))
        elif tag in ("ul", "ol"):
            self._close_block()
            key = "bulletedListData" if tag == "ul" else "orderedListData"
            node = {"type": "BULLETED_LIST" if tag == "ul" else "ORDERED_LIST", "nodes": [], key: {"indentation": 0}}
            self.containers.append(node)
        elif tag == "li":
            self._close_block()
            item = {"type": "LIST_ITEM", "nodes": []}
            self.containers.append(item)
            self.block = paragraph([])
        elif tag == "blockquote" or (tag == "div" and "ct-quote" in classes):
            self._close_block()
            self.containers.append({"type": "BLOCKQUOTE", "nodes": [], "blockquoteData": {"indentation": 1}})
            self.block = paragraph([])
            if "ct-italic" in classes:
                self.italic += 1
                self.containers[-1]["_italic"] = True
        elif tag in ("strong", "b"):
            self.bold += 1
        elif tag in ("em", "i"):
            self.italic += 1
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"])
        elif tag == "br":
            self._append_text(" ")
        elif tag == "img":
            self._close_block()
            self._target().append(image(a["data-id"], int(a["data-w"]), int(a["data-h"]), a.get("alt", "")))

    def handle_endtag(self, tag: str) -> None:
        if tag == "p":
            if self.block is not None and self.block["paragraphData"] is CENTER and self.italic:
                self.italic -= 1  # closes the caption's italic
            self._close_block()
        elif tag in HEADINGS:
            self._close_block()
        elif tag == "li":
            self._close_block()
            item = self.containers.pop()
            if item["nodes"]:
                self._target().append(item)
        elif tag in ("ul", "ol"):
            self._close_block()
            lst = self.containers.pop()
            if lst["nodes"]:
                self._target().append(lst)
        elif tag == "blockquote" or (tag == "div" and self.containers and self.containers[-1]["type"] == "BLOCKQUOTE"):
            self._close_block()
            quote = self.containers.pop()
            if quote.pop("_italic", False):
                self.italic -= 1
            if quote["nodes"]:
                self._target().append(quote)
        elif tag in ("strong", "b"):
            self.bold = max(0, self.bold - 1)
        elif tag in ("em", "i"):
            self.italic = max(0, self.italic - 1)
        elif tag == "a" and self.links:
            self.links.pop()

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data)
        if text:
            self._append_text(text)

    def close(self) -> None:
        super().close()
        self._close_block()


def html_to_nodes(html: str) -> list[dict]:
    """Ricos block nodes for an HTML fragment (no spacers; add them where the layout needs air)."""
    conv = _Converter()
    conv.feed(html)
    conv.close()
    return conv.nodes


def with_spacers(nodes: list[dict]) -> list[dict]:
    """An empty paragraph after every image, list, quote and button: Ricos adds no gap by itself."""
    out: list[dict] = []
    for node in nodes:
        out.append(node)
        if node["type"] in ("IMAGE", "BULLETED_LIST", "ORDERED_LIST", "BLOCKQUOTE", "BUTTON"):
            out.append(dict(SPACER))
    return out


def plain_text(nodes: list[dict]) -> str:
    """The document's text, one block per line (for checks and excerpts)."""
    lines = []
    for node in nodes:
        if node["type"] in ("PARAGRAPH", "HEADING"):
            lines.append("".join(r["textData"]["text"] for r in node.get("nodes", [])))
        elif node["type"] in ("BULLETED_LIST", "ORDERED_LIST", "BLOCKQUOTE", "LIST_ITEM"):
            lines.append(plain_text(node["nodes"]))
    return "\n".join(line for line in lines if line)
