"""SVG pieces for the report: a tall segmented bar and a single-series weekly line with event markers.

No background gridlines and no frame around the plot (Igor's chart rule): y ticks, the end label, the hover
readout and the table view carry the values.

Colours are CSS custom properties defined once in the page (light and dark), so nothing here holds a hex.
"""
from __future__ import annotations

from html import escape


def segmented_bar(parts: list[dict], total: int) -> str:
    """One whole split into parts. parts = [{label, value, slot, ink}] in display order.

    A block prints its amount only when the text fits; the legend below carries every name and amount.
    """
    blocks = []
    for p in parts:
        if not p["value"]:
            continue
        share = 100 * p["value"] / total
        text = f'{p["value"]:,}' if share >= 7 else ""
        blocks.append(
            f'<div class="seg" tabindex="0" style="flex:{p["value"]} 1 0;background:var(--series-{p["slot"]});color:{p.get("ink", "#fff")}" '
            f'data-tip="{escape(p["label"])}|{p["value"]:,} posts ({share:.1f}%)">{text}</div>')
    legend = "".join(
        f'<span class="key"><i style="background:var(--series-{p["slot"]})"></i>{escape(p["label"])} '
        f'<b>{p["value"]:,}</b> <em>{100 * p["value"] / total:.1f}%</em></span>' for p in parts if p["value"])
    name = "; ".join(f'{p["label"]}: {p["value"]}' for p in parts if p["value"])
    return f'<div class="segbar" role="img" aria-label="{escape(name)}">{"".join(blocks)}</div><div class="legend">{legend}</div>'


def _nice_max(v: float) -> int:
    for step in (5, 10, 15, 20, 25, 50, 100, 150, 200, 250, 500, 1000, 1500, 2000, 2500, 5000, 10000, 20000, 50000):
        if v <= step * 4:
            return step * 4
    return int(v)


def line_chart(points: list[tuple[str, float]], unit: str, events: list[tuple[str, str]], cid: str,
               width: int = 720, height: int = 250) -> str:
    """points = [(week 'YYYY-MM-DD', value)]; events = [(week, label)] drawn as labelled vertical rules."""
    left, right, top, bottom = 44, 64, 34, 30
    pw, ph = width - left - right, height - top - bottom
    ymax = _nice_max(max(v for _, v in points) or 1)
    xs = {w: left + pw * i / (len(points) - 1) for i, (w, _) in enumerate(points)}

    def y(v):
        return top + ph * (1 - v / ymax)

    grid = "".join(
        f'<text x="{left - 8}" y="{y(t) + 4:.1f}" class="tick" text-anchor="end">{int(t):,}</text>'
        for t in (ymax / 4, ymax / 2, 3 * ymax / 4, ymax))
    base = f'<line x1="{left}" x2="{left + pw}" y1="{y(0):.1f}" y2="{y(0):.1f}" class="axis"/>' \
           f'<text x="{left - 8}" y="{y(0) + 4:.1f}" class="tick" text-anchor="end">0</text>'
    months, seen = "", set()
    for w, _ in points:
        if w[:7] not in seen and (not seen or w[8:10] <= "07"):
            seen.add(w[:7])
            label = ("", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")[int(w[5:7])]
            months += f'<text x="{xs[w]:.1f}" y="{height - 8}" class="tick" text-anchor="middle">{label}</text>'
    marks = ""
    for i, (w, label) in enumerate(events):
        if w not in xs:
            continue
        marks += (f'<line x1="{xs[w]:.1f}" x2="{xs[w]:.1f}" y1="{top - 6}" y2="{y(0):.1f}" class="event"/>'
                  f'<text x="{xs[w] - 5:.1f}" y="{top - 12 + (0 if i % 2 == 0 else 0)}" class="evlabel" text-anchor="end">{escape(label)}</text>')
    path = " ".join(f'{"M" if i == 0 else "L"}{xs[w]:.1f},{y(v):.1f}' for i, (w, v) in enumerate(points))
    lw, lv = points[-1]
    end = (f'<circle cx="{xs[lw]:.1f}" cy="{y(lv):.1f}" r="5" class="dot"/>'
           f'<text x="{xs[lw] + 10:.1f}" y="{y(lv) + 4:.1f}" class="endlabel">{lv:,.0f}</text>')
    data = ";".join(f"{w},{v:g},{xs[w]:.1f},{y(v):.1f}" for w, v in points)
    return (f'<div class="scroll"><svg class="line" id="{cid}" viewBox="0 0 {width} {height}" role="img" data-unit="{escape(unit)}" data-points="{data}" '
            f'data-top="{top}" data-bottom="{y(0):.1f}" aria-label="{escape(unit)} per week">'
            f'{grid}{base}{months}{marks}<path d="{path}" class="series"/>{end}'
            f'<line class="cross" y1="{top}" y2="{y(0):.1f}" x1="0" x2="0" visibility="hidden"/>'
            f'<circle class="hoverdot" r="5" visibility="hidden"/>'
            f'<rect x="{left}" y="{top}" width="{pw}" height="{ph}" fill="transparent" class="hit"/></svg></div>')


def data_table(headers: list[str], rows: list[list], summary: str) -> str:
    head = "".join(f"<th>{escape(h)}</th>" for h in headers)
    body = "".join("<tr>" + "".join(f"<td>{escape(str(c))}</td>" for c in r) + "</tr>" for r in rows)
    return f'<details class="tableview"><summary>{escape(summary)}</summary><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></details>'
