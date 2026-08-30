---
name: ct-monthly-wrapup
description: >-
  Build the Clearer Thinking monthly "Wrap Up" / "Monthly Debrief" email that
  recaps everything CT published in a calendar month, for CT+ (Clearer Thinking
  Plus) members. Use when the user wants to create the monthly wrap-up, monthly
  debrief, "most important ideas from {month}" email, or the month-in-review /
  recap email. Crawls the month's newsletter articles + new tools (beehiiv),
  podcast episodes (podcast.clearerthinking.org RSS), and YouTube explainer
  videos (Spencer Greenberg channel), then drafts the email in CT's exact house
  format: a short plain opening paragraph, ~7-11 sourced insight bullets, and one
  do-it-now Actionable Insight. Builds the draft as a formatted .docx with the CT
  logo and header image embedded (and optionally a Google Doc). Runs as a gated
  process: crawl -> user approves the content shortlist -> user picks the
  actionable insight -> draft.
---

# CT Monthly Wrap-Up Email Builder

You build Clearer Thinking's monthly recap email (titled **"Some of Our Most Important Ideas From {Month}, In 2 Minutes"**, internally the "Wrap Up" / "Monthly Debrief"). It goes to **CT+ (Clearer Thinking Plus)** members on the first weekend of a month and summarizes everything CT published in the **previous calendar month**.

Read `references/voice-and-format.md` (the template, voice rules, source-filtering rules, boilerplate) and `references/examples.md` (five real past editions) before drafting. Match them closely — this email has a settled format and voice.

## Period

Default period = the **previous calendar month** relative to today (the email ships the first weekend of the following month). Today's date is available in context. Confirm the target month with the user if it's ambiguous (e.g. run early/late). All date filters below use this month's [first 00:00, last 23:59] window in UTC.

## Process (gated — do not skip the gates)

### Phase 1 — Crawl the month's content

Pull from all three sources in parallel, then read the survivors in full.

**1a. Newsletter articles + new tools (beehiiv)**
- Publication: `Clearer Thinking` = `pub_d0ed5a5f-0bca-4054-ab2c-73fd51707f71`.
- `list_posts` (status `published`, `newest_first`, `per_page: 100`); keep posts whose `scheduled_at` falls in the target month.
- **Filter out the noise** (see denylist in `references/voice-and-format.md`): "One Helpful Idea" posts, coaching-session invites, workshop announcements/reminders, study-participation invites, "[Link Fixed]" resends, and the "Monthly Debrief"/wrap-up itself. **Dedupe resends**: titles ending in `(1)`, `(2)`, etc. are re-sends of the same piece — keep one.
- For each surviving post, `get_post_content` (format `text`) to read the full body, and capture its canonical `clearerthinking.org` article URL (the beehiiv web URL is a fallback). Classify as 📝 Article / 📝 Newsletter, or 👤 New Tool if it announces a tool.

**1b. Podcast episodes**
- Fetch `https://podcast.clearerthinking.org/rss.xml`. Keep `<item>`s whose `pubDate` is in the target month. Capture episode number, title, guest, and the item `<link>` (the full slugged episode URL, e.g. `/episode/317/eric-zimmer-how-small-actions-rewrite-identity/`).
- **Read each kept episode's page in full.** Every episode page carries (a) show notes listing ~4-8 key ideas and (b) the **full inline transcript** (`SPENCER: … GUEST: …`). Use the show-notes ideas + transcript to write an accurate, specific bullet — pull the actual claim/mechanism, not a paraphrase of the title.

**1c. YouTube explainer videos**
- **Only Spencer Greenberg's channel** (`https://www.youtube.com/@SpencerGreenberg` = channel `UC1FD7JbC1p6PvlL0NBIiDtQ`) — the short research-backed explainer videos, e.g. "Debunking Four Personality Myths". Fetch `https://www.youtube.com/feeds/videos.xml?channel_id=UC1FD7JbC1p6PvlL0NBIiDtQ`. Keep entries published in the month. Capture title, link, description.
- Do **not** pull from any other channel. In particular, `UC5UG3sUWF2MQiQ6alZ-jzZw` is the *podcast* re-uploaded to YouTube — excluding it avoids double-counting episodes already caught in 1b.

**Deduplicate across sources by topic.** A single topic often ships as both an article and a video (e.g. "The Strangest Things that Correlate with IQ" is both). Keep both only if each adds a distinct angle; the examples do this. List them as separate bullets with the correct emoji each.

Produce a **content inventory**: a table grouped by type (Article / New Tool / Podcast / Video), one row each = title, source URL, and a one-line gist of the key idea.

### Phase 2 — GATE: user approves the shortlist

Show the inventory and ask the user to confirm/trim which items make the cut. Past editions run **~7-11 insight bullets**. Note any obvious hero item (a new tool, a founder's book, a milestone episode). Wait for approval before drafting.

### Phase 3 — GATE: user picks the Actionable Insight

Scan the approved content for the most **practical, do-it-today** techniques. Present **2-3 candidate Actionable Insights** — each with a title, the concrete steps, and its source piece — and let the user choose. A good candidate gives concrete instructions ("do X to your attention/body/speech now"), not a vague destination. See the actionable examples in `references/examples.md`.

### Phase 4 — Draft the email

Write the full draft per `references/voice-and-format.md`:
1. Header line.
2. **Opening paragraph (plain, no joke)** — a short, straightforward 2-3 sentence framing of the month's real throughline, in CT voice. No joke, puns, or wit-turns. See "The opening paragraph" in `references/voice-and-format.md`.
3. Transition line.
4. Insight bullets — **bold lead-in claim** + 2-4 explaining sentences grounded in the actual content you read + `(emoji Type: Title)` attribution with a hyperlink. Stick to the source's own wording and examples; do not invent metaphors/analogies the source didn't use (Copy rule 4).
5. **{Month}'s Actionable Insight** — the chosen one, with steps + source.
6. Closing boilerplate (exact text in references). **Hyperlink "Clearer Thinking Plus" to https://www.clearerthinking.org/plus.**

### Phase 5 — Build the `.docx` and deliver

Author the draft as a JSON content spec and build a real `.docx` with `build_wrapup_docx.py` (see `references/voice-and-format.md` → "Output & delivery" for the full method and the shape of the JSON):
- The builder embeds the **logo** (`assets/image1.png`) and **header banner** (`assets/image2.jpg`) at the top, exactly like Igor's example editions, then lays out title, opener, bullets (bold lead-in + body + hyperlinked source), Actionable, and closing.
- It **hard-fails on any em/en dash**, enforcing the Copy rules.
- File name: `[CT Wrap Up Email] - {Month} {Year} (to be sent in {NextMonth} {Year}).docx`.

Then deliver per Igor's preference (local `.docx` in `~/Downloads/wrap ups/`, or a Google Doc with images which needs the brand images hosted at public URLs first, see the reference). **Always also paste the plain-text draft in chat** so he can review without opening anything.

## Notes
- Per user preference, don't add analytical commentary while crawling/wiring sources — just confirm and move to the gate.
- Ground every claim in content you actually read. Do not invent findings, guest names, or episode numbers.
