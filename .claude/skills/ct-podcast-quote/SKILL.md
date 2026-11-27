---
name: ct-podcast-quote
description: >-
  Turn a Clearer Thinking Podcast episode into a single Instagram quote post (4:5, 1080 x 1350 PNG): read the transcript from podcast.clearerthinking.org (the latest episode by default), pick 10 verbatim quotes for the CT audience, have 10 independent subagents vote on the most interesting one (a unique perspective), let Igor choose from the top 3, then render it in CT's minimalist look with the attribution "NAME on the Clearer Thinking Podcast, "Episode N: Title"" and www.clearerthinking.org/podcast at the bottom. Use whenever Igor asks for a podcast quote, a quote card or quote image, an Instagram post from a podcast episode, or "the best quote" from an episode, even if he only pastes an episode URL or says "latest podcast". Not for article carousels (use ct-carousel), diagrams (ct-infographic) or ad creatives (ct-ad-designer).
---

# CT podcast quote post

One episode in, one PNG out. The look is fixed in `scripts/ct_podcast_quote.py` (Igor approved it on 2026-11-20 with episode 328) and each post is only a `spec.json`. Never copy the layout into a new script. `tests/test_ct_podcast_quote.py` pins a hash of the CSS: change the look only when Igor asks, show him the result, then re-pin.

Worked example: `reports/podcast_quote_ep328_2026-11-20_src/spec.json`.

The non-negotiable rule: **the quote on the image is word for word from the transcript.** No paraphrase, no tidying, no cutting filler. The only changes allowed are typographic (curly quotes and apostrophes) and an optional blue highlight on part of the quote. `verify` and `render` both refuse a quote that is not in the transcript.

All commands are run from the repo root:

```bash
Q=".venv/bin/python .claude/skills/ct-podcast-quote/scripts/ct_podcast_quote.py"
```

## 1. Fetch the transcript

`$Q fetch` takes the latest episode, or `$Q fetch <episode URL>` takes a specific one. It writes `reports/podcast_quote_ep<N>_<today>_src/` with:
- `transcript.txt`: the speaker turns only. It is gitignored.
- `spec.json`: the episode number, title and URL, plus a map from speaker label to full name (Spencer plus the guests named in "(with ...)").

Read the whole of `transcript.txt` before you pick anything.

## 2. Pick 10 candidates

Choose quotes that would interest CT's audience: curious, analytical readers interested in psychology, rationality and self-improvement, who are allergic to platitudes. Aim for a mix of host and guest.

What makes a good candidate:
- It stands alone with no context.
- It is ideally 15 to 40 words. 55 is the hard cap, because the text gets too small on a phone.
- It starts at a sentence start where possible. A quote that starts mid-sentence (with its first letter capitalised) is allowed, but prefer the whole sentence.
- It does not describe a view the speaker is criticising. Read the surrounding lines: the same words out of context can claim the opposite.

Write them into `spec.json` as `candidates`, with ids A to J, the speaker's full name (from `episode.speakers`) and the exact text. Then run `$Q verify <spec>`. Every line must say `verbatim`. Fix any that don't by copying from the transcript again, never by editing the transcript.

## 3. Run the 10-voter vote

`$Q ballots <spec>` prints 10 shuffled orders of the candidates, one per voter, which cancels out position bias. Launch **10 Agent calls in one message** (`model: "sonnet"`, which is enough for a vote), one per ballot. Every voter gets the same prompt, with only the order changed:

> You are one of 10 independent judges voting on podcast quotes. Audience: Clearer Thinking (clearerthinking.org) readers, curious and analytical people interested in psychology, rationality and self-improvement, who are allergic to platitudes. The quotes come from the Clearer Thinking Podcast, Episode N, "TITLE" (Spencer Greenberg with GUEST). If you want context, the full transcript is at <absolute path to transcript.txt> (reading it is optional; use no other tools).
>
> Criterion: the MOST INTERESTING quote = the one offering the most UNIQUE PERSPECTIVE: an idea the reader probably has not heard before, one that reframes how they see something. Not just well phrased, agreeable or true. It must also stand alone on an Instagram post with no context.
>
> <the ballot>
>
> Reply in exactly this format and nothing else:
> VOTE: <one letter>
> RANKING: <your top 3 letters, best first, comma-separated>
> REASON: <one sentence>

Do not tell the voters which quote you prefer. Record each reply in `spec.json` as `votes`, for example `{"vote": "A", "ranking": ["A", "B", "D"]}`. Then run `$Q tally <spec>`, which ranks by first-place votes and then by 3/2/1 points.

## 4. Let Igor choose before rendering

Igor turned down the vote winner the first time (episode 328), so don't render straight away. Show him the **top 3** by the tally. For each one, give the exact text, who said it, its votes and points, and one line for it and one line against it. Recommend one. If a quote outside the top 3 is clearly a better fit for CT (for example a short, punchy question), mention it as a wildcard. Then set `chosen` to the id Igor picks.

`highlight` is optional. It is an exact substring of the chosen quote that gets drawn in CT blue. Use it for the phrase that carries the idea, and leave it out if no single phrase does. If you used one, tell Igor.

## 5. Render and check

Run `$Q render <spec>`. It writes `~/Downloads/ct_podcast_quote_ep<N>.png` and a preview at `reports/podcast_quote_ep<N>_<date>.html`. Open the preview in Chrome (`open -a "Google Chrome" <file>`). The type size steps down automatically with the quote's length (96, then 84, then 74 px).

**Look at the PNG** with Read before you report. Check for:
- a word stranded alone on the last line of the quote or the attribution
- the quote crowding the attribution or the footer

The fix is a different `highlight` or a different quote, never cutting words. If the look itself needs to change, that is Igor's call (see the top of this file).

Commit `spec.json` and the preview HTML, but never the PNG or `transcript.txt`.

## Fixed parts of the look

The layout, top to bottom:
- the CT logo at the top
- an orange opening quote mark
- the quote in Avenir semibold, dark ink, with the optional blue highlight
- a short orange rule
- the attribution: **Name** on the Clearer Thinking Podcast, "Episode N: Title" (the title without the "(with ...)" tail, in muted ink)
- a grey footer band with www.clearerthinking.org/podcast in CT blue

There are no em dashes anywhere. Offer to write the Instagram caption afterwards (same rules as ct-carousel: hook line, two sentences, "link in bio", about 6 lowercase hashtags ending #clearerthinking), but don't write it unasked. When you do, write it with the `ct-writer` skill (voice and `copy_lint.py`); the quote itself stays verbatim.
