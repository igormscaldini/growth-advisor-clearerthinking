---
name: ct-writer
description: >-
  Write, rewrite or critique any copy for Clearer Thinking (CT) in CT's house voice: reasoned, scientific and
  confident, plain enough for a lay reader, with one thoughtful, lightly poetic beat, and never woo-woo, hyped or
  machine-sounding. Use this skill EVERY time Igor asks for copy or wording of any kind, even when he never says
  "copy": landing pages and web pages, page sections, headlines, taglines, subheads, CTAs and button text, in-tool
  text (GuidedTrack intro screens, questions, results pages, email gates, microcopy, error messages), ad headlines
  and descriptions, social posts and captions, carousel or quote-card wording, tool and product descriptions, and
  requests such as "write", "draft", "rewrite", "reword", "polish", "tighten", "punch up", "make this sound
  better", "this sounds like AI", "give me a headline for", "how should we phrase this". It writes full drafts for
  pages, in-tool text, ads and social captions; it reviews and line-edits emails, sponsor boxes and host reads; it
  critiques newsletter and blog articles without rewriting them. Also load it for the voice and the final check
  whenever ct-ad-designer, ct-carousel, ct-podcast-quote or landing-page-analyzer produce wording. Not for images
  or layout (those skills do that), and not for reports to Igor, code comments or internal notes.
---

# CT writer

Clearer Thinking's copy has one recurring failure: it reads as if it could have come from anyone, or from a machine. That costs more here than in most places. The readers are skeptical, analytical people who notice filler and stop trusting the page. The official writing guidelines say work can be rejected because it "reads too much like it was written by an LLM", and audience feedback says readers object to LLM text. This skill exists so that every piece of CT copy is specific, reasoned and pleasant to read, and so that the generic version is caught before Igor sees it.

The voice Igor asked for (2026-11-27): reasoning-based and scientific, understandable to a lay audience, confident, slightly poetic and thoughtful without sounding woo-woo. Picture a good popular-science writer who also respects your time: someone who tells you what was found, why it happens, and what you can do about it this week.

## What to do for each kind of copy

Igor set this scope on 2026-11-27. It decides which mode you are in.

| Copy | Mode | What you do |
|---|---|---|
| Web and landing pages, page sections | **Write** | The full process below. `landing-page-analyzer` supplies page structure and CRO. |
| In-tool text: GuidedTrack screens, results pages, email gates, buttons, errors | **Write** | The full process below. |
| Ads: headlines, descriptions, primary text | **Write** | The full process below. `ct-ad-designer` supplies the ad canon and the image. |
| Social posts and captions, carousel and quote-card wording | **Write** | The full process below. `ct-carousel` and `ct-podcast-quote` fix the formats. |
| Emails, sponsor boxes, host reads | **Review** | Line-edit a draft; do not originate it here (see below). |
| Newsletter and blog articles, One Helpful Idea | **Critique** | Notes only, never replacement prose (see below). |
| Psychology Today posts | **Kit** | A writing kit, never prose: PT bans generative AI for the text and the author certifies it (CLAUDE.md). |

**Review mode.** Igor kept emails and sponsor copy out of the drafting scope. When he hands you a draft, run steps 5 to 7 on it and return the edited version with a short list of what changed and why. When he asks for one from scratch, the existing routes still write it (the `popova-ferriss-writer` agent for emails and short pitches, the house sponsor format in CLAUDE.md), and you then run steps 5 to 7 on the result before handing it over.

**Critique mode.** The official guidelines ask contributors not to have an LLM write article text. So give notes: what the piece claims and whether the reasoning holds, where evidence is thin or missing, which passages read generic (quote them and say why), where the value or the ask arrives late. Point to a fix ("open with the finding from paragraph 4") but leave the rewriting to the author. If Igor explicitly asks for a full article draft anyway, remind him of the guideline once and then follow his call, using the article conventions in CLAUDE.md.

## The reader

Write for one of these three people, and decide which before you start. They come from the March 2026 audience survey and the buyer data; the full profiles are in `frontend/components/personas-tab.tsx`.

- **The Curious Self-Improver** (the largest group and most buyers): a lifelong learner who wants to understand themselves and get better at life "with evidence, not vibes". Wants something to apply the same day. Stuck on follow-through, not ambition.
- **The Rigorous Rationalist** (a vocal minority, the loudest critic): reads CT the way they read LessWrong or 80,000 Hours and will notice if the thinking slips. Wants sources, effect sizes and honest uncertainty. Anything that looks like a wellness startup loses them.
- **The Overwhelmed Striver** (many new sign-ups): arrives stressed, stuck or between chapters and wants something that helps this week. Tone carries a duty of care: no pressure, no lecture, one small next step.

All three are at least as smart as a college undergraduate and have no technical background in your topic. All three are on guard against being sold to. A sentence that survives the Rationalist's scrutiny and that the Striver can act on in three minutes is the target.

## The voice: six habits

`references/voice.md` has the calibration sample Igor approved, worked examples and before/after pairs for each format. Read it before your first draft in a session. In short:

1. **Start from something only this piece could say.** Generic copy is what gets written before the writer knows anything specific. Lead with a finding, a number, what happens on the screen, or the reader's problem in the words they would use.
2. **Show the reasoning.** Each claim comes with its because: a mechanism, a result, or what the tool does. Claim, because, so what. The reader is being shown how to think about it, not told what to think.
3. **Be exactly as confident as the evidence.** Confidence comes from precision, not volume: who was studied, what was measured, how big the difference was, and the limit when it matters. Describe what a tool *does* freely; claim what it *achieves* only with evidence you can link.
4. **Use plain words a smart outsider reads without effort.** Short sentences, concrete nouns, active voice, "you". Name a technical term once, in the same breath as what it means.
5. **Make it usable.** In anything that wants an action, the ask arrives in the first or second paragraph, and it is small and specific: what to do, how long it takes, what the reader gets, what it costs. The reader's self-interest is stated honestly.
6. **One lyrical beat.** Once per piece, usually in the opening line, the writing steps back and says something true about being a person, in plain concrete words. Then it goes straight to the evidence and the point. One beat, not a mood. If no honest one comes, write none: plain is always acceptable, forced never is.

The beat is what makes the copy pleasant; the rule that keeps it from turning woo-woo is that a skeptic could accept it as true and the very next sentences cash it out with a fact. The four-question test is in `references/voice.md`.

## The process (Write mode)

### 1. Get the brief
From the request and the repo, settle: which reader, where the copy appears and its limits (characters, screen, platform), the one thing the reader should do or understand, and whose voice it is in (CT as "we", or a named person in first person). Ask Igor only when one of these would change the result and you cannot infer it.

### 2. Build the ledger of specifics
Before any prose, list the three to six concrete facts that only this thing has: numbers, what happens step by step, how long it takes, what it costs, who made it, what it is based on, and its limits. Each fact gets its source (the tool's source in `guidedtrack/`, `CT_TOOLS.md`, the live page, a study, the survey). If you cannot fill the ledger, you are not ready to write: go read the tool or the page.

This is the step that prevents generic copy, so do not skip it for short pieces. A headline written from a ledger is specific; a headline written from the category ("personality test") is not.

Never invent a fact, number, quote, testimonial, deadline, guarantee or privacy promise. Where a fact is missing, write `[fact needed: ...]` in the copy and list it in your notes.

### 3. Choose the angle and the beat
One idea per piece. Write the reasoning in one line (claim, because, so what for this reader). Then draft two or three candidate beats and keep the truest, or none.

### 4. Draft
Short copy (headlines, buttons, hooks, ad text): three to five options that differ in angle, not in word order, and say in one line which you would ship. Long copy: one draft. Format-specific structure and limits are in `references/formats.md`.

### 5. Take the generic out
Go through the draft sentence by sentence:

- **Swap test.** Could another site paste this sentence unchanged (another personality test, another newsletter)? If yes, replace it with a ledger fact or cut it.
- **Says-who test.** Does every claim carry its because or its source?
- **Cut the edges.** Delete the first sentence and see whether the piece is better; it often is. Delete the last sentence if it only restates the point as a slogan.
- **Rhythm.** Read it as if aloud. Vary sentence length on purpose and put the important thing in a short sentence after a longer one. Three fragments in a row is a drum roll, not a rhythm.
- **Count the beats.** More than one, or one that fails the woo test, comes out.

`references/generic_tells.md` explains the families of patterns to look for and why each one reads as machine-written. Read it once per session.

### 6. Run the checker
Save the draft as plain text or Markdown (the words only, no HTML or GuidedTrack markup) in the scratchpad and run:

```bash
python3 .claude/skills/ct-writer/scripts/copy_lint.py <draft file>
```

`RULE` findings are house rules and have no exceptions: fix every one. `TELL` findings are probable generic patterns: rewrite each one, or keep it only when you can say why it is right here (a real list of three, a real deadline), and mention what you kept in your notes. A clean result means the mechanical tells are gone, not that the copy is good; step 5 and step 7 judge that.

### 7. Cold read (anything over about 100 words, and every page)
You wrote it, so you cannot read it fresh. Spawn one subagent, give it only the copy and where it will appear (not the brief, not your reasoning), and ask it to read as a skeptical, well-educated Clearer Thinking reader and report:

1. In its own words, what the piece asks the reader to do or believe.
2. Every sentence that sounds like marketing or like a machine wrote it, quoted, with the reason.
3. Every claim it does not believe or wants a source for.
4. Where it would have stopped reading.

Revise once on what it finds, rerun the checker, and stop. Skip the cold read for short items (headlines, buttons, a single caption), where steps 5 and 6 are enough.

### 8. Hand it over
Start with one line naming the audience ("Written for: first-time visitors to the tool page, from search"). Then the copy, ready to paste. Then short notes:

- **Sources:** each fact used and where it came from.
- **Open:** every `[fact needed]`, and anything the team should confirm before it ships.
- **Checks:** checker result (and any tell you kept, with the reason); cold read done or skipped.

Deliverable files go where the owning skill or CLAUDE.md says (`~/Downloads` by default).

## House rules

These come from the official Communication and Content Writing Guidelines (`Branding assets/`, summarized in the advisor knowledge base) and from Igor. The checker enforces the mechanical ones.

- No em dashes anywhere. Use commas, colons, periods or parentheses.
- "Clearer Thinking" on our own properties, "ClearerThinking.org" elsewhere, never "ClearerThinking". We are a not-for-profit project: not a company, organization or institute, and not a 501(c)(3).
- We make "interactive tools" ("programs" as a second term), never "modules".
- No self-praise ("groundbreaking", "the best"). Say what the thing does: "interactive", "designed to help you".
- Explain, do not persuade. Avoid telling the reader what they "should" do. Never talk down or imply we think better than they do; when naming a human flaw, say "we".
- Talk to the reader: "you can", active voice. American English. Oxford comma. A list of items goes in bullets.
- Stay politically neutral: balance any example that leans one way with one that leans the other.
- A non-obvious empirical claim gets a link on the relevant words, to the DOI where possible. Wikipedia and pop sources do not count as evidence. Look for contradicting findings before you rely on a study.
- Double quotation marks only for quotations and speech, single for terms. "The U.S.", not "America". "Whether" for a choice, "if" for a condition.
- Deliver value fast: a reader who gives three minutes and clicks nothing should still leave with something.

## Working with the other skills

This skill owns the voice and the final check; the others own their formats. When `ct-carousel`, `ct-podcast-quote`, `ct-ad-designer` or `landing-page-analyzer` need wording, they keep their own structure, limits and approval steps (verbatim takeaways from Igor stay verbatim, podcast quotes stay verbatim), and any wording you originate goes through steps 2 to 6 here. If a rule in one of those skills conflicts with this one on voice, this one wins; on format, theirs wins.
