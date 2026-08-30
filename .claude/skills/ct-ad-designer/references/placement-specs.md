# Placement specs — aspect ratios, dimensions, safe zones

Generate the prompt per requested placement with the right ratio AND a composition note that fits that placement. Request the largest clean resolution from Ideogram; the user crops/exports per channel.

**Ideogram aspect-ratio mapping:** Meta feed **4:5** and Stories/Reels **9:16** are native Ideogram ratios. Google PMax **1.91:1** is not native — use **16:9** (closest) or a custom landscape size and keep the subject centered so hard crops are safe. Pass the ratio as an Ideogram parameter, not just in the prompt text.

## Meta — Facebook & Instagram feed
| Ratio | Pixels | Notes |
|---|---|---|
| **4:5** (portrait) | 1080 × 1350 | **Preferred** for feed — biggest mobile real estate. Default to this for Meta. |
| 1:1 (square) | 1080 × 1080 | Safe everywhere; good for Google too. |

- Headline overlay: upper third works well; keep faces/hero clear of the very bottom (caption/CTA UI sits below the image, not on it, for feed).
- Meta historically penalized heavy in-image text; keep any baked-in text minimal and let the overlay headline do the work.

## Meta — Stories & Reels
| Ratio | Pixels | Notes |
|---|---|---|
| **9:16** (full vertical) | 1080 × 1920 | Full-screen immersive. |

- **Safe zone is critical.** Keep the hero subject and all text within the central ~1080 × 1420 area. Reserve roughly the **top ~250 px** (profile/handle) and **bottom ~340 px** (caption, CTA button, Reels UI) as empty — do not place key subject or headline there.
- In the prompt: "vertical composition, hero element centered in the middle band, generous clean space top and bottom for platform UI and a headline overlay."

## Google — Display & Performance Max
PMax/responsive display want all three orientations; provide each when Google is requested:
| Ratio | Pixels | Role |
|---|---|---|
| **1.91:1** (landscape) | 1200 × 628 | Primary landscape asset. |
| **1:1** (square) | 1200 × 1200 | Required square. |
| **4:5 / 0.8** (portrait) | 960 × 1200 | Portrait slot. |

- These get cropped hard across the Google network — keep the hero subject centered with margin on all sides so no crop kills it.
- Logo + text are added as separate PMax assets, so the image itself can stay clean; still leave a calm zone for an optional headline overlay.

## Reframing one concept across ratios
Keep the SAME visual idea; change composition, not concept:
- **4:5 / 9:16 (tall):** stack vertically — hero lower-center, text space above; let empty sky/surface fill the extra height.
- **1:1:** centered, balanced.
- **1.91:1 (wide):** hero to one side (e.g. right third), text space on the other; use the width for the contrast/split or a long surface.

Always restate the aspect ratio explicitly in each prompt (`Aspect ratio 4:5`) and adjust where the negative space / text-safe zone sits accordingly.
