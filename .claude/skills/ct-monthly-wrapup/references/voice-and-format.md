# Voice & Format Spec — CT Monthly Wrap-Up

The email has a settled structure and voice. Study `examples.md` alongside this. Match tone, not just skeleton.

---

## Copy rules (hard, apply to every edition)

1. **Never use em dashes (—) or en dashes (–). Ever.** Use commas, colons, parentheses, or split into two sentences. (`build_wrapup_docx.py` refuses to build if a dash slips into the content, so this is enforced.)
2. **Calibrate confidence down.** Unless a claim is firmly research-backed or plainly obvious, hedge it: "most people say" becomes "most people might say"; prefer "tends to / may / often / seems to / in our data / by one estimate." Apply this throughout, including the opening paragraph.
3. **Ground each bullet only in its own source.** Write each insight bullet from the content of *that bullet's cited piece alone*. Do not blend in claims from other pieces, outside knowledge, or your own extrapolation. If a detail isn't in that source, leave it out.
4. **Stick closely to the source's own language; do not invent imagery.** The sources are all CT's own work, so there is no plagiarism concern to write around, reuse the source's wording, framing, and examples directly. **Do not invent new metaphors, analogies, similes, or "clever" reframings that don't appear in the source.** If the source uses a metaphor, you may reuse it; if it doesn't, don't add one. Prefer the source's phrasing over a paraphrase.
5. **CT voice:** nuanced, curious, non-dogmatic, never hype.

---

## Full template

```
[logo wordmark: assets/image1.png, centered]

Some of Our Most Important Ideas From {Month}, In 2 Minutes

[header banner: assets/image2.jpg, full width]

{opening paragraph, plain, no joke}

{transition line}

{INSIGHT BULLET 1}
{INSIGHT BULLET 2}
...
{INSIGHT BULLET 7-11}

{Month}'s Actionable Insight: {Actionable title}

{Actionable steps / instructions}

From {emoji Type: Source title (hyperlinked)}

{closing boilerplate}
```

### Header line
`Some of Our Most Important Ideas From {Month}, In 2 Minutes`
- Newest editions use **"In 2 Minutes"** (older ones said "In 60 Seconds" — use 2 Minutes).
- Older editions prefixed "Clearer Thinking Monthly Debrief" — the newest ones (May, June 2026) **dropped it**. Omit it.

### Transition line (pick one, vary it)
- "A few ideas worth keeping:"
- "Here are a few of the useful ideas from our content that was published in {Month}:"
- "Here are some of them:"

---

## The opening paragraph (plain, no joke)

A short opening that frames the month's genuine throughline and hands off to the ideas. **No joke.** No puns, setups, wit-turns, or punchlines. (Earlier editions used a humorous opener; that is dropped.)

- Read the month's content first, then state the real common thread in plain, warm language.
- 2-3 sentences, in CT's voice: nuanced, clear, non-dogmatic. A light, honest observation is fine; a bit is not.
- Hedge confidence like the rest of the copy (see Copy rules). End by moving into the transition line.

**Model (June's real edition, a plain opener):**

> "This month, we looked at a few things that people often feel confident about: therapy, charity, IQ, self-help, and evidence. In each case, the answer was a bit more complicated than it first seemed. Some advice works only if it gives you something concrete to do. Some evidence is much stronger than other evidence. And some things that seem important, like IQ, matter in some ways but not in others."

---

## Insight bullets

Each bullet:
1. **Bold lead-in claim** — a crisp, curiosity-piquing statement of the idea (a sentence or a short label). Examples: "Painful thoughts are often persuasive, not necessarily accurate." / "IQ predicts some things, but not the thing everyone wants." / "Importance Hacking:"
2. **2-4 explaining sentences**, grounded in the actual content — the mechanism, the nuance, the caveat. CT voice: precise, nuanced, non-dogmatic, never hype. Prefer "tends to," "often," "may." **Stay in the source's own words and examples (Copy rule 4): reuse the source's phrasing and any metaphor it already uses; never invent a metaphor, analogy, or reframing the source didn't.**
3. **Attribution** in parentheses at the end, with the source title **hyperlinked**:
   - `(📝 Article: {title})`
   - `(📝 Newsletter: {title})`
   - `(🎧 Podcast: {title})` — include `#{episode}` and `with {Guest}` when natural, e.g. `(🎧 Podcast #305: What beats intuition when it comes to doing good?)`
   - `(▶️ Video: {title})`
   - `(👤 New Tool: {title})`

Order: lead with the strongest / most surprising ideas. A new tool or a founder milestone can go near the top. Aim for ~7-11 bullets (match the approved shortlist).

---

## The Actionable Insight

Format:
```
{Month}'s Actionable Insight: {Title}

{1-4 short steps or a short instruction the reader can do TODAY.}

From {emoji Type: Source title (hyperlinked)}
```
- Must be **concrete and immediately doable** — instructions for the reader's attention, thoughts, body, or speech. Not a vague destination.
- Keep the wry voice in one line if it fits ("No 'we should catch up sometime' fog machine required.").
- Sourced from one specific piece of the month's content.

---

## Closing boilerplate (use verbatim; light variation OK)

> Thank you for supporting our work. We truly hope you're enjoying these wrap-ups (please let us know if you have any feedback!).
> If someone shared this email with you and you're not currently a Clearer Thinking Plus member, you can check out our plans to receive the next edition.

**Always hyperlink the phrase "Clearer Thinking Plus" to https://www.clearerthinking.org/plus** in the closing. In the builder's `closing` JSON, write it as a markdown link, e.g. `... not currently a [Clearer Thinking Plus](https://www.clearerthinking.org/plus) member ...` (the builder renders markdown links inline).

Alternate (also real, slightly warmer, fine to use):
> A sincere thank you to our Clearer Thinking Plus members. Your support is essential to fund research, build new tools, and continue producing thoughtful content.
> If you're receiving this email because someone shared it with you, but you're not currently a Clearer Thinking Plus member, check out our plans to make sure you receive the next edition.

---

## Source-filtering rules (beehiiv)

The `Clearer Thinking` publication mixes real content with promo/ops sends. **Exclude** posts whose title matches any of:
- `One Helpful Idea:` (micro-tips, not features)
- coaching-session invites — "You're invited to a free coaching session"
- workshop announcements/reminders — "Workshop", "We're about to start", "You're invited to my upcoming workshop"
- study-participation invites — "Invitation to participate in a study"
- resend/fix markers — "[Link Fixed]", "[Resend]"
- the wrap-up itself — "Monthly Debrief", "Wrap Up"

**Dedupe resends:** titles differing only by a trailing `(1)`, `(2)`, `(3)` are the same piece re-sent — keep one (prefer the original / the one with the canonical article URL).

**Keep:** substantive essays/articles, and tool-launch announcements (→ 👤 New Tool). When in doubt, include it in the inventory and let Igor cut it at the Phase 2 gate.

---

## Output & delivery

**Primary output = a real `.docx`** built with `build_wrapup_docx.py`, because it embeds the logo (`assets/image1.png`) and header banner (`assets/image2.jpg`) exactly like Igor's example editions. HTML→Doc import cannot embed local images, so the `.docx` is the faithful path.

Steps:
1. Author the content as a JSON spec (see the docstring in `build_wrapup_docx.py` for the shape). Obey the **Copy rules** above; the script hard-fails on em/en dashes.
2. `python3 build_wrapup_docx.py content.json out.docx` (needs `python-docx`: `pip3 install python-docx`). It lays out logo + header + title + opener + bullets (bold lead-in, body, hyperlinked source) + Actionable + closing.
3. Deliver. **Igor's confirmed default (July 2026): save the local `.docx` to `~/Downloads/wrap ups/` and let him drag it into Drive himself** (it auto-converts to a Google Doc with images intact). Don't re-ask each month; just save it there and give him the path. The other routes below are only if he requests them.
   - **Local `.docx`** saved to `~/Downloads/wrap ups/` (matches his examples). He opens it, or drags it into Drive, where it auto-converts to a Google Doc **with images intact**. ← default
   - **Google Doc with images, created directly** — requires the two brand images to live at **public URLs**, then create the Doc via `Google_Drive.create_file` (`mimeType: application/vnd.google-apps.document`, `contentMimeType: text/html`, `textContent` = HTML with `<img src="PUBLIC_URL">`). Confirmed: Drive **fetches and embeds remote `<img>` on import** (the logo/header become real `word/media/*` entries). Hosting the images publicly needs Igor's explicit opt-in (it was blocked once as an unrequested public upload). Once hosted, bake the two URLs into this file and reuse them every month.
   - **Text-only Google Doc** (no images) via the HTML route is the quick fallback if he just wants to read/edit online.

Rendering gotchas learned:
- **Emoji (📝 🎧 ▶️ 👤):** in the `.docx` route they're just literal characters in the JSON, and embed fine. In the HTML route, `read_file_content` mangles 4-byte emoji to `ð` in its *preview* even when the Doc is fine, so don't trust read-back to judge emoji; and don't re-upload to "fix" a preview artifact.
- `create_file` reports `fileSize: 1` for native Google Docs even when populated (metadata quirk, not empty).
- No Drive delete/edit tool exists via MCP; if you re-create a Doc, tell Igor the older ones can be trashed.
- Always also paste the plain-text draft in chat so he can review without opening anything.
