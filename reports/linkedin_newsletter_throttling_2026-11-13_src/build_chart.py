"""LinkedIn chart: longest no-open stretch per newsletter and the emails sent during it.

Numbers come from reports/newsletter_engagement_throttling_2026-11-13.html (Gmail header analysis).
Writes ~/Downloads/newsletter_no_open_stretch.png (1200x1200).
"""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

DATA = [  # (newsletter, longest stretch with zero opens in days, emails received in that stretch)
    ("theSkimm", 1083, 705),
    ("McKinsey & Company", 439, 396),
    ("Marketing Brew", 181, 110),
]
BLUE, SURFACE, INK, INK2, MUTED = "#2a78d6", "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984"
OUT = Path.home() / "Downloads" / "newsletter_no_open_stretch.png"


def main() -> None:
    plt.rcParams["font.family"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(8, 8), dpi=150, facecolor=SURFACE)
    ax = fig.add_axes([0.07, 0.17, 0.86, 0.52], facecolor=SURFACE)
    xmax = 1650
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.6, len(DATA) - 0.4)
    ax.axis("off")

    h, r = 0.30, 14  # bar thickness (data units), end rounding (days)
    for i, (name, days, emails) in enumerate(DATA):
        y = len(DATA) - 1 - i
        ax.add_patch(FancyBboxPatch((0, y - h / 2), days, h, boxstyle=f"round,pad=0,rounding_size={r}",
                                    mutation_aspect=h / (2 * r), fc=BLUE, ec="none"))
        ax.add_patch(Rectangle((0, y - h / 2), r * 2, h, fc=BLUE, ec="none"))  # square baseline end
        ax.text(0, y + h / 2 + 0.08, name, fontsize=17, color=INK, fontweight="bold", va="bottom")
        ax.text(days + 18, y + 0.02, f"{days:,} days", fontsize=17, color=INK, va="center", fontweight="bold")
        ax.text(days + 18, y - 0.17, f"they still sent {emails:,} emails", fontsize=13.5, color=INK2, va="center")
    ax.plot([0, 0], [-0.45, len(DATA) - 0.55], color="#d9d8d3", lw=1)

    fig.text(0.07, 0.90, "I stopped opening their emails.", fontsize=26, fontweight="bold", color=INK)
    fig.text(0.07, 0.855, "They never slowed down.", fontsize=26, fontweight="bold", color=BLUE)
    fig.text(0.07, 0.785, "Longest stretch in which I opened zero emails from each\nnewsletter, and how many it sent me during that stretch",
             fontsize=14, color=INK2, va="top", linespacing=1.4)
    fig.text(0.07, 0.085, "Source: full headers of 6,454 emails in my Gmail, 2016 to 2026. 'Opened' = Gmail read flag.\n"
             "Volume during each stretch matched their normal schedule.",
             fontsize=10.5, color=MUTED, va="top", linespacing=1.5)
    fig.savefig(OUT, facecolor=SURFACE)
    print(OUT)


if __name__ == "__main__":
    main()
