# Prompt recipes — writing Ideogram image prompts for CT ads

## Ad-creative principles (apply to every concept)

1. **One ad, one idea.** A single focal subject. If you can't say the idea in one sentence, it's too busy.
2. **The scroll-stop = a curiosity gap.** The best CT ads pose a silent question or show a quiet contradiction the eye wants to resolve (a compass needle split in two; the same street lit two ways). Intrigue, not shock.
3. **Show the tension, don't illustrate the topic.** Translate the tool's *insight* into a concrete object/scene. Avoid literal depictions (no "person thinking," no labeled diagram).
4. **Negative space is a feature.** It makes the image feel premium AND leaves room for the headline overlay.
5. **Legible at thumbnail size.** Strong silhouette, high contrast, minimal clutter. Most impressions are tiny and on mobile.
6. **Authentic over stocky.** Real-feeling light, materials, imperfection. Avoid the glossy stock-photo / corporate look.
7. **Test variety.** Offer distinct metaphors, not recolors of one. Creative performance is found by testing, not by polishing one idea.
8. **Brand color as a deliberate accent** (minimalist mode) — see brand-spec.

## Avoid (negative-prompt vocabulary + concept-level don'ts)

- Concept clichés: lightbulb-over-head, brain-with-gears/cogs, glowing blue neural-network "AI" mesh, head silhouette filled with icons, generic smiling headshots, handshake, ladder-to-success, person-on-mountaintop (overused), word "BRAIN."
- Rendering tells: garbled text, distorted hands/fingers, extra limbs, warped faces, watermark, logo, signature, plastic skin, oversaturation, HDR halos, cluttered busy backgrounds, low contrast, cheesy 3D render (unless intended).
- **Invented text on in-scene objects:** the AI's incidental writing on props (book covers/spines, signage, posters, screens, magazine pages, labels) renders as garbled nonsense and looks weird. Keep those surfaces **blank, abstract, blurred, turned away, or text-free** — only the deliberate ad copy (and a real fed-in product cover) should carry legible words. Always include "garbled/invented text on in-scene objects (book covers, spines, signs, posters, screens, labels)" in the `Avoid:` line.
- Off-brand: neon pink/purple gradients, vaporwave, meme energy, clickbait arrows/circles, fake UI/chat bubbles, shocking or fear imagery.

Always end the prompt with a `Avoid:` line listing the relevant items above.

## Every prompt produces a FINISHED AD in the CT house layout

The output is a complete ad creative in CT's house layout (see `ad-layout.md`), fully composed by the AI. **Every prompt must embed (1) the self-contained brand block and (2) the house-layout block** (both are in `brand-spec.md` / `ad-layout.md` — the tool has zero context), and render all elements baked in:

1. **Logo** — top-center, "ClearerThinking.org" wordmark + magnifying-glass "C" mark.
2. **Headline** — big, bold, centered, with **one phrase in CT blue #0885f8**.
3. **Subhead** — short centered line, grey #737373.
4. **Hero image** — in a rounded-corner card; default = warm lifestyle photography (use saved page images as reference).
5. **CTA button** — rounded rectangle, orange #f8911b or blue #0885f8, white text.
6. **Optional badge** — blue #0885f8 circle, white text, for a secondary hook.

Specify **exact copy** in quotes so the model spells it right; demand accurate, well-kerned text. Default size is **square 1:1, 1200×1200** — only add other sizes on request. Always tell the user to proofread and re-roll garbled text.

## The prompt template (house layout — DEFAULT, warm lifestyle hero)

Paste-ready. Fill the brackets; keep the hero as flowing description, copy in quotes, technical tail at the end.

```
Create a polished, professional square social media ADVERTISEMENT (a finished ad, Clearer Thinking house style).

Brand: Clearer Thinking (ClearerThinking.org) is a science-based personal-development project. Its brand feels intelligent, calm, curious, trustworthy, and quietly optimistic — never loud, salesy, or clickbait. Brand colors: primary blue #0885f8, gold #fecb02, orange #f8911b, deep navy #233b47; backgrounds white or warm off-white #f9f1e3; text near-black #303030, secondary grey #737373. Typography: a clean rounded geometric sans-serif (Avenir style) for all text. Logo: a magnifying-glass icon forming a "C" with a bright blue (#0885f8) inner arc, beside the wordmark "ClearerThinking.org" in dark grey.

Layout (render crisply, correctly spelled, generous white space, rounded corners, centered hierarchy):
- Background: clean white.
- Logo at the TOP-CENTER: the magnifying-glass "C" mark with blue #0885f8 inner arc + "ClearerThinking.org" wordmark in dark grey.
- Headline below it, large and bold, centered, rounded geometric sans-serif: "<HEADLINE>" — in dark #303030 with the phrase "<BLUE PHRASE>" in CT blue #0885f8.
- Subhead beneath the headline, smaller, centered, medium grey #737373: "<SUBHEAD>".
- Hero image in the lower-center inside a rounded-corner card: <warm, natural golden-hour lifestyle photograph of [relevant real person/scene/product], authentic and optimistic, soft warm light>.
- CTA button at the bottom-center overlapping the image's lower edge: a rounded-rectangle button in [orange #f8911b / blue #0885f8] with white bold text "<CTA>".
- [Optional badge: a filled blue #0885f8 circle in a top corner of the image with white bold text "<BADGE>".]

Square 1:1 composition, 1200x1200, high resolution, mobile-first, legible at small thumbnail size, clear flow logo → headline → subhead → image → button.
Render all text exactly as written, correctly spelled and well-kerned; no gibberish, no extra or duplicated words.
Avoid: misspelled or garbled text, garbled or invented text on in-scene objects (book covers, spines, signs, posters, screens, labels) — keep those surfaces blank/abstract/blurred/text-free, distorted or off-brand logo, extra fake UI/icons, watermark, cluttered layout, low contrast, off-brand neon/purple/pink colors, cold corporate stock-photo look.
```

## Swapping the hero treatment

Keep the entire layout block above; replace ONLY the "Hero image" line:
- **Minimalist conceptual:** `Hero image in a rounded card: <one concrete object/scene with a quiet visual twist>, editorial product photography, soft daylight, mostly neutral with a single blue #0885f8 accent.`
- **Branded colorful:** `Hero image in a rounded card: warm orange-and-blue duotone digital illustration (orange #f8911b + blue #0885f8) of <scene>, dramatic warm backlight, gold #fecb02 highlights, painterly.`

## Gold-standard examples (CT's actual top ads — match this caliber)

These are real `ImageConcept` entries from `meta_ads_copy.csv`. Study the move each one makes.

- **Overconfidence** → "A single weathered brass compass on a clean white surface, its needle subtly split into two faint ghosted directions, shot top-down in soft daylight; the quiet contradiction makes the eye linger and question its own certainty." *(Move: one object + a subtle impossibility = doubt about certainty.)*
- **Primal World Beliefs** → "Split-screen of the exact same city street, one half warm and golden, the other cool and shadowed, divided by a crisp vertical line; same-scene-two-moods contrast poses the question of how you read the world." *(Move: identical scene, two readings = the tool's premise.)*
- **Mental Traps** → "A clean geometric paper maze in soft neutral tones viewed from above, one tiny figure-shaped marble resting mid-path; minimalist, promises a puzzle about your own thinking." *(Move: elegant object stands in for the mind.)*
- **Skeptical Seekers** → "A single magnifying glass on a plain matte surface, its lens bending light into a sharp focused circle on the paper below; signals scrutiny without cliché." *(Move: on-brand lens motif, done subtly.)*

Common thread: ONE object, clean surface, soft daylight, a quiet conceptual twist, room for text. Aim here.

## The scroll-stop is the whole job — be bold and inventive

These are paid social ads competing against an infinite feed. A *tasteful but forgettable* image fails. Every concept must earn a half-second double-take. Push harder than "nice photo":

- **Lead with a pattern interrupt.** Something the eye is not expecting in a feed: an impossible object, an everyday thing doing something it shouldn't, a scale that's wrong, a perfect symmetry suddenly broken, a familiar object made strange.
- **Engineer a "wait, what?" beat.** The viewer should need a second look to resolve it (the compass needle that points two ways). Curiosity gap > clarity. Mystery is the hook; the headline closes it.
- **Use tension devices:** visual paradox, optical illusion, forced perspective, unexpected juxtaposition, a single anomaly in a uniform field (one red marble in a grid of grey), before/after in one frame, a hidden second reading, extreme close-up of an unexpected texture.
- **Make the hook *specific to this tool's insight*** — surprise for its own sake is noise; the twist should pay off the idea so the click is qualified.
- **Go past the first idea.** The first concept you think of is usually the cliché. Brainstorm 5–6, throw out the obvious ones, keep the ones that made *you* pause. When in doubt, make it weirder and smarter, never louder or more clickbait.
- Still inside CT's voice: intriguing and intelligent, never shock-bait, fear, fake urgency, or meme energy. Surprising *and* classy.

## Text-on-image best practices (whether overlaid or, rarely, generated)

Prefer to **overlay** text in the ad tool rather than have the model generate it (image models garble type, and clean Avenir/Inter looks more professional). But wherever text appears on the ad, it must follow these practices — bake these requirements into the text-safe zone you describe in the prompt:

- **One message, few words.** A short headline (≈3–7 words) beats a sentence. One idea per ad; let the image carry the rest.
- **Legible at thumbnail size.** Large type, generous weight, ample line spacing. If it's not readable on a phone at a glance, it's too small/busy.
- **High contrast against its zone.** That's why the prompt reserves a *clean, low-detail, high-contrast* area — text needs a calm background (or a subtle scrim/solid color block) so it never sits on busy detail.
- **Clear hierarchy.** One dominant headline; a CTA or sub-line is secondary and smaller. Don't compete two big texts against each other.
- **On-brand type & color.** Avenir (or Inter) in CT dark `#303030` / white, or a single brand accent (`#0885f8`, `#fecb02`). No decorative or off-brand fonts.
- **Respect placement safe zones.** Keep text out of the Stories/Reels UI bands and away from hard crop edges on Google (see `placement-specs.md`).
- **Keep baked-in text minimal** (esp. Meta feed, which favors low text-density images). Let the visual be the scroll-stop and the headline be the payoff.
- **CT voice in the copy:** curiosity, not clickbait; never talk down, no fake urgency, no ALL-CAPS shouting beyond a stylistic accent word.

## Writing the ad copy (all baked into the image)

Every ad needs this copy, all specified in the prompt as exact quoted text:

- **Headline** — the scroll-stopping line, with **one phrase set in CT blue #0885f8** for emphasis (call out which phrase). Pull from `ImgHeadline1/2/3` in `meta_ads_copy.csv` when the tool exists there, or write 2–3 in CT voice (curiosity, no clickbait, e.g. "How sure are you?", "Safe world or dangerous one?"). ≈3–7 words.
- **Subhead** — one short supporting line in grey #737373 that states the offer/benefit plainly (e.g. "A free, science-based 5-minute test."). ~6–10 words.
- **CTA button** — short action label: "Take the free test", "Pre-order now", "Get matched with a coach", "Learn more". Rounded button in orange #f8911b OR blue #0885f8 with white text.
- **Logo** — Clearer Thinking logo, top-center (Ideogram renders the wordmark well; composite the real file afterward for perfection; see brand-spec).
- **Optional badge** — a few words in a blue #0885f8 circle for a secondary hook (e.g. "Affordable Monthly Access"), only when there's a strong second selling point.

Placement follows the house layout (logo top-center → headline → subhead → hero card → CTA bottom-center); see `ad-layout.md`. Keep total text light — the headline + image do the work. Always tell the user to proofread rendered text and re-roll if any of it is garbled.

## From brief to concepts — quick procedure

1. State the tool's core insight/tension in one sentence.
2. Brainstorm 4–6 concrete objects/scenes that embody it; cut the literal/cliché ones.
3. Keep the 2–3 with the strongest curiosity gap and cleanest silhouette.
4. For each, write the prompt(s) per requested placement.
5. Pair each with a suggested headline + placement.
