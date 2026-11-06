---
name: ct-infographic
description: >-
  Recreate or restyle any image, diagram, framework graphic, chart or infographic in the Clearer Thinking (CT) flat house style and export it as a PNG. Use this whenever Igor shares an image or screenshot and asks to "make this CT style", "follow our style", "create a graph like this", "redo this graphic", "make a version for social / 1:1 / the newsletter", or wants a new explanatory diagram (levels, steps, staircase, funnel, process, cycle, matrix, comparison) for an article, newsletter or social post, even if he never says "infographic". Input is usually an image, sometimes a description. Output is a PNG in ~/Downloads plus an HTML preview in reports/. Builds with HTML/CSS and inline SVG through the bundled kit (CT palette, Avenir, logo footer, PNG export), never with an image generator. Not for paid ad creatives (use ct-ad-designer) and not for data charts inside reports or dashboards (use dataviz).
---

# CT infographic

Turn a graphic someone else made (an AI illustration, a slide, a sketch, a competitor's diagram) into a clean one in Clearer Thinking's flat style, or build a new one from a description. The graphic is written as HTML/CSS with inline SVG and exported to PNG with headless Chrome.

Why code and not an image generator: the wording has to be exact, the text has to stay crisp, and Igor iterates in small steps ("make it 1:1", "lighter fonts"). In code each of those is a one-line change with everything else held still; in an image model it is a re-roll that changes everything.

The first graphic made this way is the worked example to copy from: `reports/integrative_complexity_staircase_2026-11-06_src/build.py` (a seven-level staircase, landscape and square layouts).

## Workflow

### 1. Read the source and transcribe it

Write down every word in the image exactly, and what each visual element encodes (what position, size, colour and line style mean). The redraw keeps the meaning and drops the decoration, so you need to know which is which.

- The source's wording is the content. Keep it as written; do not add claims, examples or labels of your own.
- If something is illegible, ask. Never guess text.
- If the source has no title, write one in the house pattern (a dark line ending in a colon, then a blue line naming the thing, like "How We Perceive Reality: / The 5 Layers of Perception") and tell Igor it is yours. Same if you name a concept the source does not name: say it is an inference.

### 2. Choose the format

| Use | Preset in the kit | Canvas | Export |
|---|---|---|---|
| Newsletter, blog | `landscape` | 1600 wide, height follows content | 3200 px wide |
| Social, 1:1 | `square` | 1600 x 1600 | 2160 x 2160 |
| Social, 4:5 | `portrait` | 1600 x 2000 | 2160 x 2700 |

If Igor names the use, follow it. Otherwise match the source's orientation and say which you chose. A new format of an existing graphic is a new entry in that script's `LAYOUTS`, not a new script, and already-approved PNGs stay untouched unless he asks for them to be redone.

### 3. Plan the translation into the house style

Pick the layout from the structure of the idea, then apply the style rules below.

- Levels or progression: rising columns (a staircase) or stacked rows
- Funnel: stacked bands that narrow
- Process: a row of cards joined by arrows
- Comparison: two columns
- Cycle: nodes on a ring
- Two-by-two: a grid with axis labels

When there are more than five items and each carries a sentence of text, stacked rows give roughly twice the type size of side-by-side columns. Prefer rows for anything that will be read on a phone, and say so if Igor asked for columns.

### 4. Build it with the kit

Create `reports/<slug>_<yyyy-mm-dd>_src/build.py`. Keep all wording in constants at the top so Igor can edit text without touching layout. The kit (`scripts/ct_infographic.py` in this skill) supplies everything shared, so the script only describes the middle of the page:

```python
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude/skills/ct-infographic/scripts"))
import ct_infographic as kit

fmt = kit.FORMATS["square"]
html = kit.page_html(
    title_line_1="Dark line of the title:", title_line_2="Blue line of the title",
    body_html='<div class="main">...</div>', css=".main { margin-top:auto; ... }",
    width=fmt["width"], height=fmt["height"], name="Short name", alt="One-sentence description",
    png_path=png_out)
kit.export(html, html_out, png_out, width=fmt["width"], height=fmt["height"], scale=fmt["scale"])
```

What the kit gives you: `BLUE`, `INK`, `ORANGE`, `DARK_ACCENT`, `BLUE_RAMP`, `BLUE_TINTS`, `FOOTER_GREY`, `FONT_STACK`, `FORMATS`, `page_html()` (title, logo footer, preview bar with the timestamp), `export()` (writes the HTML and the PNG), `contrast()`, `display_px()`, `timestamp()`, `logo_markup()`.

Run it with `.venv/bin/python <script>`.

### 5. Render, look, fix

Open the PNG with the Read tool: once shrunk to see the whole composition, then full-resolution crops of the dense parts. Layout problems are invisible in the code. Look for awkward line breaks, text close to an edge, uneven gaps, icons touching shapes, and large dead areas.

### 6. Check the three things that can be measured

- **Legibility.** `kit.display_px(font_px, canvas_width, display_width)` gives the size text ends up at. Check body text at 600 (newsletter column), about 550 (desktop social feed) and about 375 (phone). Under roughly 9 px at the intended size, tell Igor the number and propose the layout that fixes it. Do not ship it silently and do not silently redesign what he approved.
- **Contrast.** `kit.contrast(text, fill)` must be 4.5 or more for any text.
- **Colour-blind safety.** When two or more colours tell things apart, run the dataviz skill's validator: `node <dataviz skill dir>/scripts/validate_palette.js "#3b83f1,#ee8031" --mode light`. Blue with orange passes. Blue with the dark accent fails (the dark reads as grey), so the dark accent is for lines, not for identities.

### 7. Deliver

- PNG to `~/Downloads/ct_<slug>[_<format>]_<yyyy-mm-dd>.png`.
- Open the HTML preview in Chrome: `open -a "Google Chrome" <html path>`.
- Add a test for anything with logic to `tests/test_ct_infographic.py` and run `.venv/bin/python -m pytest -q`.
- Commit the build script and the preview HTML. Never the PNG: the repo is public and binaries stay out.
- Tell Igor, briefly: where the files are, what you kept from the source, what you invented (title, concept name), the format and size, and any legibility caveat with its number.

## House style

Taken from CT's "5 Layers of Perception" graphic (colours sampled from its pixels) and the January 2025 visual style guide.

| Element | Rule |
|---|---|
| Background | White. No gradients, shadows, glows, 3D, textures or photos. |
| Title | Centred, two lines of equal size (58 px landscape, 64 px square), weight 600. Line 1 in `INK`, line 2 in `BLUE`. |
| Font | Avenir Next (the brand font is Avenir). Weight 600 for the title, headings and labels, 400 for descriptions, 500 italic for secondary headings. Nothing heavier: Igor asked for a lighter look on 2026-11-06. |
| Small labels | 16 to 18 px, uppercase, weight 600, letter-spacing 2.4 px, 70% opacity. |
| Blue ramp | `BLUE_RAMP`, one hue from light to dark, for sequence or magnitude. Dark text on the first three steps, white text only on the last. |
| Orange | The single accent: the one thing to notice, or the second of two identities next to blue. |
| Dark accent | Arrows, connectors and rings. |
| Text colour | `INK` or white. Never coloured, except the blue title line. |
| Shapes | Flat fills, 12 px corner radius, 10 to 14 px gaps. |
| Lines | 2 px (2.4 px inside small icons). |
| Hinted or in-between things | Dashed outline with a near-white fill from `BLUE_TINTS`, and a dotted version of the icon. |
| Icons | Simple flat geometry drawn as inline SVG. No emoji, no icon fonts. |
| Footer | Full-width grey band with the ClearerThinking.org logo centred. The kit adds it. |
| Copy | No em dashes anywhere. Title Case headings, sentence case descriptions. |

### Translating a source into this style

| The source has | It becomes |
|---|---|
| Glossy or 3D objects, glows | Flat circles and shapes |
| A photo or illustrated background | White |
| Many colours for a sequence | The blue ramp |
| Two entities or viewpoints | Blue and orange |
| Faded, transparent or "ghost" elements | Dashed outlines |
| A gold or glowing highlight on the key element | The darkest blue fill, or a dark-accent ring |
| Headers floating far from what they label | Brackets or labels touching what they group |
| All-caps body text | Title Case headings, caps only for small labels |

If Igor supplies a different style reference, sample its colours with PIL instead of eyeballing them (that is how this palette was made), follow it, and keep the logo footer and the font.

## Things that will trip you up

- `Branding assets/` is gitignored, so always take the logo from `kit.logo_markup()`, which reads the copy bundled in this skill.
- Avenir Next exists on macOS only. Render on Igor's machine; on Linux or CI the fallback font changes every line break.
- A canvas with a fixed height is a flex column. Give the main block `margin-top:auto` (or `flex:1`), or it will sit under the title with a gap above the footer.
- Shared SVG markers (arrowheads) go in `page_html(svg_defs=...)` and are referenced as `url(#id)` from any inline SVG.
- `text-wrap: balance` on headings and descriptions avoids one-word last lines.
- White text on `BLUE_RAMP[3]` is only 3.7:1. Put white text on `BLUE_RAMP[4]`.
- The timestamp belongs in the preview bar, which the kit adds outside the exported canvas, never inside the image.
- After changing shared code, rebuild an existing graphic and compare it pixel by pixel with the old PNG (`PIL.ImageChops.difference(a, b).getbbox()` is `None` when identical).
