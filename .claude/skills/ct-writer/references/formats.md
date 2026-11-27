# Formats in the Write scope

Structure and limits for the four kinds of copy this skill drafts. The voice is the same in all of them (`voice.md`); what changes is how much room there is and what the reader needs first.

## Web and landing pages

The first screen answers four questions before any scrolling: what is this, what do I get, what do I do, how long does it take (and what does it cost). A visitor who reads nothing else should be able to act.

A workable order for the rest, borrowed from `landing-page-analyzer` (which owns page structure and conversion research; read its references when the job is a whole page):

1. **Headline:** the promise or the finding, concrete. This or the line under it may carry the beat.
2. **Subhead:** what it is and what the reader gets, with the time and the price.
3. **How it works:** the real steps, in the order the reader will meet them. Mechanism, not adjectives.
4. **What it is based on:** who made it, which research, and the limits. Link the evidence.
5. **The real objections.** For CT these come from the survey, so answer them plainly where they apply: privacy (what happens to the answers and the email), price (what is free and what is not, since paywalls feel off-mission to this audience), and time.
6. **The call to action:** a verb and what the reader gets ("Take the free test", "See the 12 questions").

Length: as long as it takes to answer the objections a careful reader has, and no longer. Mine the reader's own words from the survey for the problem section instead of inventing how they talk.

## In-tool text (GuidedTrack)

Text inside a tool is read by someone in the middle of doing something. Be literal and brief.

- **Intro screen:** what the reader will get at the end, how long it takes, and what it is based on. A beat is allowed here if it helps them care.
- **Assessment questions and answer options:** neutral, literal, one idea per item, no leading words, no beat. The wording is a measuring instrument: a livelier phrasing can change what the item measures. Do not reword items from a validated scale; if one reads badly, flag it to Igor instead of fixing it.
- **Instructions:** one action per sentence, in the order the reader does them.
- **Results text:** describe, do not diagnose. "Your answers suggest ..." rather than "You are ...". Compare with other people only when the tool computes the comparison. Some readers arrive in distress, so a low or unwelcome score comes with what it does and does not mean and one thing they can do next.
- **Email gates and upsells:** say exactly what happens next and what the reader will receive. Never invent a privacy promise, a sending frequency or a price: mark `[fact needed]`.
- **Buttons:** a verb and its object, in sentence case ("See my results", "Start the timer").
- **Errors:** what happened and what to do now. No blame and no jokes.

GuidedTrack has syntax traps that turn a wording choice into a bug (a visible line starting `*Word:*` is parsed as a keyword; `{variables}` do not fill in inside an `*html` block that also holds `<style>`). The `guidedtrack-builder` skill and the GuidedTrack section of CLAUDE.md cover them. Pull the live program and diff before pushing any text change.

## Ads

`ct-ad-designer/references/copywriting.md` holds the ad canon (headline first, one idea per ad, match the reader's awareness, honest proof) and that skill builds the image. Use both; this skill adds the voice and the checks.

- The headline is a clear promise or a question the reader already has. Clarity beats cleverness, so a beat rarely belongs in a headline.
- Give three to five options that differ in angle (self-interest, curiosity plus self-interest, the finding, quick and easy), and label each with its angle so they can be tested against each other.
- Count characters and print the count beside each line. Google responsive search ads allow 30 characters per headline and 90 per description, and Performance Max adds a 90-character long headline; platforms change these, so confirm the current limit in the ad interface before finalizing.
- Title Case in a headline is the one place it is acceptable, because it is the platform's convention.
- Every claim in an ad must be true of the landing page it leads to.

## Social posts and captions

`ct-carousel` (section 4 of its SKILL.md) fixes the caption formats for LinkedIn, Instagram and X, including hashtags, link placement and character counts. `ct-podcast-quote` fixes the quote card. Follow them for format.

- The hook line is the finding or the reader's problem, never an announcement ("We're excited", "New post").
- The beat, if there is one, is the hook. Do not stack a beat and a finding before the reader knows the topic.
- State only what the article, slides or episode says. No added facts, numbers or examples.
- Takeaways Igor wrote and podcast quotes are verbatim: do not polish them. Tell him if one breaks a house rule and let him decide.
- One emoji at most, and only where the format calls for one.
