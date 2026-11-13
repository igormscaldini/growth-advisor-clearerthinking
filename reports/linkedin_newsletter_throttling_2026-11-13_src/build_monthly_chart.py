"""LinkedIn chart: emails received per 30-day month after Igor's last open, one panel per newsletter.

Each panel covers Igor's longest stretch with zero opens. A dotted line marks that newsletter's monthly
average in the 365 days before the stretch, so a throttle would show as columns dropping below it.
Reuses the loaders of build_cumulative_chart.py (scratchpad pickles, personal data, never committed).
Writes ~/Downloads/newsletter_emails_per_month_after_last_open.png (1200x1200).

Usage: python build_monthly_chart.py <scratchpad dir holding mbrew/, mck/, skimm/>
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import FancyBboxPatch, Rectangle

sys.path.insert(0, str(Path(__file__).parent))
from build_cumulative_chart import AXIS, INK, INK2, MUTED, SURFACE, load, longest_stretch  # noqa: E402

BLUE = "#2a78d6"
BIN = 30  # days per "month"
FIG_PX = 1200
OUT = Path.home() / "Downloads" / "newsletter_emails_per_month_after_last_open.png"


def monthly(df: pd.DataFrame) -> tuple[pd.Series, float, dict]:
    """Emails per full 30-day bin inside the longest no-open stretch, plus the per-30-day rate of the year before."""
    s = longest_stretch(df)
    full_bins = s.attrs["gap"] // BIN  # a trailing partial bin is dropped, it would read as a drop
    counts = (s.days // BIN).astype(int).value_counts().reindex(range(full_bins), fill_value=0).sort_index()
    start = s.attrs["start"]
    before = df[(df.et >= start - pd.Timedelta(days=365)) & (df.et <= start)]
    attrs = dict(s.attrs, total=len(s), rate=len(s) / s.attrs["gap"] * BIN)
    return counts, len(before) / 365 * BIN, attrs


def rounded_column(ax, x, height, width, px_w, px_h, x_span, y_span, color):
    """A column with a 4px rounded top and a square baseline end (dataviz mark spec)."""
    r_x = 4 * x_span / px_w  # 4 px in x data units
    aspect = (y_span / px_h) / (x_span / px_w)
    ax.add_patch(FancyBboxPatch((x - width / 2, 0), width, height, boxstyle=f"round,pad=0,rounding_size={r_x}",
                                mutation_aspect=aspect, fc=color, ec="none"))
    ax.add_patch(Rectangle((x - width / 2, 0), width, min(height, r_x * aspect), fc=color, ec="none"))


def main(scratch: Path) -> None:
    plt.rcParams["font.family"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(8, 8), dpi=150, facecolor=SURFACE)
    panels = {name: monthly(df) for name, df in load(scratch).items()}
    x_max = max(len(c) for c, _, _ in panels.values())
    y_max = max(max(c.max(), b) for c, b, _ in panels.values()) * 1.25
    left, width, height, gap, bottom0 = 0.09, 0.86, 0.145, 0.065, 0.135
    x_lim = (-0.7, x_max - 0.3)

    for i, (name, (counts, baseline, attrs)) in enumerate(panels.items()):
        bottom = bottom0 + (len(panels) - 1 - i) * (height + gap)
        ax = fig.add_axes([left, bottom, width, height], facecolor=SURFACE)
        px_w, px_h = width * FIG_PX, height * FIG_PX
        for m, c in counts.items():
            rounded_column(ax, m, c, 0.64, px_w, px_h, x_lim[1] - x_lim[0], y_max, BLUE)
        ax.axhline(baseline, color=INK2, lw=1, ls=(0, (2, 3)))
        ax.text(0, 1.06, name, transform=ax.transAxes, fontsize=14, fontweight="bold", color=INK, va="bottom")
        ax.text(1, 1.06, f"{baseline:.0f} a month before  →  {attrs['rate']:.0f} a month during "
                f"({attrs['total']:,} emails in {attrs['gap']:,} days)",
                transform=ax.transAxes, fontsize=10, color=INK2, ha="right", va="bottom")
        ax.set_xlim(*x_lim)
        ax.set_ylim(0, y_max)
        ax.set_yticks([0, 20, 40])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=INK2, labelsize=10, length=0, pad=5)
        if i == len(panels) - 1:
            ax.set_xticks(range(0, x_max + 1, 6))
            ax.set_xticklabels([str(t) for t in range(0, x_max + 1, 6)])
            ax.set_xlabel("Months since I last opened one of their emails", fontsize=12, color=INK2, labelpad=8)
        else:
            ax.set_xticks([])
        print(name, attrs["start"].date(), "->", attrs["end"].date(), "bins", len(counts),
              "per month", counts.tolist(), "baseline", round(baseline, 1))

    fig.text(0.09, 0.925, "I stopped opening their emails.", fontsize=25, fontweight="bold", color=INK)
    fig.text(0.09, 0.885, "They kept sending at the same pace.", fontsize=25, fontweight="bold", color=BLUE)
    fig.text(0.09, 0.84, "Emails received per month during my longest stretch of opening none.\n"
             "The dotted line is that newsletter's monthly average from the year before.",
             fontsize=13, color=INK2, va="top", linespacing=1.4)
    fig.text(0.09, 0.05, "Source: full headers of 6,454 emails in my Gmail, 2016 to 2026. 'Opened' = Gmail read flag.\n"
             "Months are 30-day bins; a final partial month is not drawn.", fontsize=10, color=MUTED, va="top",
             linespacing=1.5)
    fig.savefig(OUT, facecolor=SURFACE)
    print(OUT)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
