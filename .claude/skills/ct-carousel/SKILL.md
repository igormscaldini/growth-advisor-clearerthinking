---
name: ct-carousel
description: >-
  Turn a Clearer Thinking (CT) article or blog post into a "key takeaways" carousel for Instagram and LinkedIn (4:5, 1080 x 1350 PNG slides: cover, one slide per takeaway, closing slide with the CT owl pointing to ClearerThinking.org/Blog), plus the post captions for LinkedIn and Instagram and a link post for X. Use whenever Igor asks for a carousel, slides for Instagram or LinkedIn, "key takeaways" images, a social post from an article, or captions/descriptions for sharing an article, even if he only pastes a post URL or a list of takeaways. The look is fixed and must match the approved job-change carousel of 2026-11-20 exactly; the skill's script draws it, so only the wording changes. Not for single infographics or diagrams (use ct-infographic) and not for paid ad creatives (use ct-ad-designer).
---

# CT carousel + captions

One article in, three things out: a set of slide PNGs in `~/Downloads` (Instagram), one PDF of the same slides (LinkedIn document post), and ready-to-paste captions for LinkedIn, Instagram and X.

The look is the point of this skill. Igor approved it on 2026-11-20 (the job-change carousel), and every carousel must look the same. All of it lives in `scripts/ct_carousel.py`: layout, type sizes, colours, icons, owl, dots, footer logo. A new carousel is only a JSON file of wording, so the look cannot drift. **Never copy the layout code into a new script, and never change the CSS, the owl or an existing icon.** `tests/test_ct_carousel.py` pins a hash of the look and fails if any of it changes. If Igor asks for a style change, make it in the script, show him, and re-pin the hash only after he approves it. That change then applies to every future carousel.

Worked example: `reports/job_change_carousel_2026-11-20_src/carousel.json`.

## 1. Get the takeaways

- **Igor gives the takeaways:** they are his copy and go in **word for word**. Each one is split at its first sentence: that sentence is the headline, the rest is the body. If a takeaway opens with an emoji, replace it with a matching icon (no emoji on the slides). A list inside a takeaway, like "Three things you might want to improve include:", becomes the pale-blue chips (`list`), drawn after the first paragraph.
- **Igor gives only the article:** read the full post first. On Wix pages, read until the head is complete, because `<title>` can sit ~127 KB in. Then draft 5 to 7 takeaways. Every claim must come from the article: no added facts, examples or numbers. The headline is one declarative sentence and the body is 1 to 2 sentences on why or how. Show Igor the draft text and get his approval **before** you render anything.

Wording rules, from CT's house style: no em dashes anywhere, smart reader, no marketing hype. Any wording you draft yourself (takeaways from an article, the captions in step 4) follows the `ct-writer` skill: load it for the voice, and run its `scripts/copy_lint.py` on the final text. Igor's own takeaways stay word for word.

Size limits, enforced by `validate()`: at most 8 takeaways (10 slides is Instagram's maximum), a headline of at most 75 characters (about 3 lines), and a body of at most 330 characters, paragraphs and chips together. If a takeaway is over the limit and it is Igor's verbatim copy, tell him which one and let him cut it. Never shorten it silently.

## 2. Write the spec

Create `reports/<slug>_carousel_<yyyy-mm-dd>_src/carousel.json`:

```json
{
  "slug": "job_change",
  "date": "2026-11-20",
  "article_url": "https://www.clearerthinking.org/post/...",
  "title": ["What to Think About When You’re", "Thinking About a Job Change"],
  "takeaways": [
    {"icon": "compass", "headline": "One sentence.", "paragraphs": ["Body.", "More body."], "list": ["chip", "chip"]}
  ]
}
```

- `title`: the article title split into two lines. The first line is dark and the second is blue, on both the cover and the closing slide. Split it where it reads naturally, with the second line carrying the subject.
- `cover_label` is optional and defaults to "<n> Key Takeaways". `end_lines` is optional and defaults to "Read the full article on" / "ClearerThinking.org/Blog". Keep "on" on the first line, because on its own it gets stranded on a line by itself.
- `icon`: pick from `ICONS` in the script (compass, puzzle, search, coins, flask, sun, brain, note, wrench, flame). If none fits, **add** a new icon to `ICONS` in the same style: a 100 x 100 grid, blue line work with `S.format(c=BLUE)` (stroke 4, round caps), exactly one orange detail, no text. Do not restyle the existing icons. Adding an icon does not break the look test, which pins only the original six. `S` already sets `stroke-width="4"` and the browser keeps the FIRST of two duplicate attributes, so a `stroke-width="7"` written after `S` does nothing (checked 2026-11-27): for another width, write the attributes out by hand.
- **The article has its own "key takeaways" box** (most CT articles do, under "Short of time? Read the key takeaways."): treat it like Igor's copy. Use those takeaways word for word, split at the first sentence, and render without a draft round.

## 3. Render and check

```bash
.venv/bin/python .claude/skills/ct-carousel/scripts/ct_carousel.py reports/<slug>_carousel_<date>_src/carousel.json
```

The output is `~/Downloads/ct_<slug>_carousel_<date>/slide_01.png ...`, a PDF named after the folder beside them (one page per slide, vector text, printed from the same pages the PNGs are screenshots of; Igor's request 2026-11-27: LinkedIn gets the PDF), plus an overview page at `reports/<slug>_carousel_<date>.html`. Open the overview in Chrome (`open -a "Google Chrome" <file>`).

Then **look at every PNG** with Read before you report. Check for:
- text running into the dots or the footer
- a single word stranded on its own line, in a headline or on the closing slide
- an icon that does not match its takeaway

Fix the wording or the line split in the JSON, not the layout. To move a line break without touching the words, join two words with a non-breaking space (` ` in the JSON): it fixed a cover title breaking as "Debunking 3 / More Myths" and a body ending on the lone word "change." (2026-11-27). Commit the JSON and the overview HTML, but never the PNGs.

## 4. Write the captions

Deliver all three in chat, each labelled, ready to paste. Also save them to `captions.md` beside the JSON. Hand them over with one line naming the audience ("Written for: CT's followers on LinkedIn, Instagram and X").

The article URL is `article_url`. No em dashes. Open with the reader's question or problem, never with "We're excited" or "New post". Only state claims that are in the slides or the article.

- **LinkedIn** (posted with the PDF as a document; LinkedIn asks for a document title, so give one: the article title plus "N Key Takeaways"): a hook question in one line, 2 to 3 short sentences giving the core idea, then "The carousel covers N takeaways from our article, including:" with 3 to 4 bullets (•) that tease without giving away every answer, then "Full article: <url>", then 3 hashtags (for example #CareerChange #DecisionMaking).
- **Instagram** (posted with the carousel): a hook line with at most one emoji, 2 sentences of substance ending with "Swipe for N key takeaways on ...", then "Full article at ClearerThinking.org/Blog (link in bio).", then about 6 lowercase hashtags ending with #clearerthinking. Captions cannot carry clickable links, so remind Igor that "link in bio" only works if the bio points to the blog.
- **X** (link post, no carousel): at most 280 characters, where the URL counts as 23. Use a hook plus the core idea in 1 to 2 sentences, then "N takeaways on <topic>:" and the URL on its own line. No hashtags. State the character count.

Offer UTM-tagged links (`utm_source=linkedin|instagram|x&utm_medium=social`) if Igor wants each platform's traffic to show separately in GA4. Do not add them unasked.
