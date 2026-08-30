# Clearer Thinking — visual identity (for ad image prompts)

Source: *Clearer Thinking Visual Design Guidelines* (Jan 2025) + the brand assets in `Branding assets/` and `assets/`.

## ⭐ Portable brand block — PASTE INTO EVERY PROMPT

Ideogram (and any image AI) has **none** of this context. Every prompt you write must embed a self-contained description of the CT brand so the output is on-brand without external knowledge. Use this block verbatim (lightly adapt wording), near the top of each prompt:

> **Brand:** Clearer Thinking (ClearerThinking.org) is a science-based personal-development project. Its brand feels intelligent, calm, curious, trustworthy, and quietly optimistic — never loud, salesy, or clickbait. **Brand colors:** primary blue #0885f8, gold #fecb02, orange #f8911b, deep navy #233b47; backgrounds are warm off-white #f9f1e3 or light grey #f5f5f5; body text is near-black #303030. **Typography:** a clean geometric sans-serif (Avenir / Inter style) for all text. **Logo:** a magnifying-glass icon that forms the letter "C" with a bright blue (#0885f8) inner arc, beside the wordmark "CLEARER THINKING" set in dark-grey (#303030) geometric capitals.

Always spell out the actual hex colors and describe the logo in words — never assume the tool knows what "CT blue" or "the Clearer Thinking logo" means.

## Color palette

**Primary**
| Name | HEX | RGB | Use in ads |
|---|---|---|---|
| Gold | `#fecb02` | 254, 203, 2 | High-energy accent, highlight, "aha" pops |
| Main Blue | `#0885f8` | 8, 133, 248 | The signature CT accent; trust + clarity |
| Orange | `#f8911b` | 248, 145, 27 | Warmth, the dominant hue of the colorful illustration style |
| Dark Accent | `#233b47` | 35, 59, 71 | Deep, calm backgrounds; sophisticated contrast |

**Accent / neutral**
| Name | HEX | Use |
|---|---|---|
| Light Accent | `#f9f1e3` | Warm off-white background — great clean canvas for minimalist ads |
| Main Grey | `#f5f5f5` | Cool clean background |
| Main Dark | `#303030` | Near-black text / heavy contrast |
| Text Dark / Middle / Light greys | `#737373`, `#A6A6A6` | Secondary text tones |

**How to use color in prompts**
- **Minimalist mode:** keep the scene largely neutral (white, `#f9f1e3` warm-paper, soft daylight, matte surfaces) and introduce ONE brand accent — typically CT Blue `#0885f8` (a glint, an object, a light) or Gold `#fecb02`. Restraint reads as premium and on-brand.
- **Colorful mode:** lead with the Orange↔Blue duotone of the official gallery, warm dramatic backlight, gold highlights.
- Never introduce off-brand colors (neon pink, magenta, purple gradients).

## Typography (for the overlay text the user adds later, not for the AI image)
- **Avenir** — primary, used on website / advertising banners. Use for ad headlines.
- **IBM Plex Sans / Inter** — secondary (Inter is a close, free Avenir substitute when Avenir isn't available).
- Arial for Mailchimp emails.
- Keep overlay headlines short, sentence/title case, high contrast. Don't bake type into the image — overlay it.

## Logo
- The mark is a **magnifying glass forming a "C"**, with a bright CT-blue inner arc; wordmark "CLEARER THINKING" in a clean geometric sans (dark grey `#303030`).
- **ALWAYS use a real logo file from this project's `Branding assets/` folder — never an AI-drawn logo.** Background-matched variants:
  - White/light bg (default): `Branding assets/04 Logo/04 Logo/Clearer Thinking Logo/01 MAIN LOGO (on WHITE bg)/Logo-02.png` (mark + wordmark lockup; `Logo-01.png` is the mark only).
  - Blue bg: `…/Clearer Thinking Logo/02 on BLUE bg/Logo on blue-02.png`.
  - Black/dark bg: `…/Clearer Thinking Logo/03 on BLACK bg/Logo on black-02.png`.
  - Square/tools lockup: `…/Clearer Thinking Logo/Square Layout - for TOOLS/Logo - Square Layout (large).png`.
  - Convenience mirrors: `assets/ct-logo-horizontal.png`, `assets/ct-mark.png` (the `Branding assets/` originals are source of truth).
- **The logo must appear in every ad.** Get the real pixels in by **feeding the file into the generation** via Ideogram `upload_image` → `edit_image` (pass it alongside the product cover as references), and/or **compositing** the real file over the result for a pixel-perfect finish. The house ads place the logo **top-center** (see `references/ad-layout.md`).
- Describing the logo in words alone is a **last resort only** (no file available). If you must, describe it precisely (magnifying-glass "C" with a bright blue #0885f8 inner arc + "CLEARER THINKING" wordmark in dark-grey geometric capitals), warn that AI-drawn logos are approximate, and swap in the real `Branding assets/` file afterward.
- Optional motif: a magnifying glass / lens / circle-of-focus can also appear *in* the hero scene as a conceptual nod (e.g. the "Skeptical Seekers" magnifying-glass ad), distinct from the corner logo.

## Iconography style (reference for the "feel")
- Linear icons: clean single-weight blue line icons.
- Tool illustrations: simple flat blue/grey figures, brains, maps, rockets — friendly, not corporate.
- This is the in-product vocabulary; ads lean more cinematic/conceptual than these, but stay in the same calm, intelligent family.

## Brand voice → visual translation
CT's content is **evidence-based, nuanced, optimistic, never prescriptive or arrogant, never clickbait**. The visuals must match:
- Intriguing, not shouting. Curiosity over hype.
- Smart and a little understated — respects the viewer's intelligence.
- Optimistic/practical undertone (these tools help you).
- Never condescending, never fear-baiting, never fake-urgency.
