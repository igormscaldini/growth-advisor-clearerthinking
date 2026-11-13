"""LinkedIn chart: emails received per calendar month, one line per newsletter, with a dot at the last email
Igor opened before his longest stretch of opening none.

Reuses the loaders of build_cumulative_chart.py (scratchpad pickles, personal data, never committed).
Writes ~/Downloads/newsletter_timeline_stopped_opening.png (1200x1200).

Usage: python build_timeline_chart.py <scratchpad dir holding mbrew/, mck/, skimm/>
"""
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from build_cumulative_chart import AXIS, INK, INK2, MUTED, SURFACE, load, longest_stretch  # noqa: E402

BLUE, ORANGE = "#2a78d6", "#eb6834"
OUT = Path.home() / "Downloads" / "newsletter_timeline_stopped_opening.png"


def monthly_series(df: pd.DataFrame) -> pd.Series:
    """Emails per calendar month (US Eastern), without the partial first and current months."""
    s = df.set_index("et").sort_index().resample("MS").size()
    first = df.et.min()
    if first.day > 3:  # the subscription started mid-month
        s = s.iloc[1:]
    s.index = s.index.tz_localize(None)
    s = s[s.index < pd.Timestamp.now(tz="America/New_York").tz_localize(None).to_period("M").start_time]
    return s


def main(scratch: Path) -> None:
    plt.rcParams["font.family"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(8, 8), dpi=150, facecolor=SURFACE)
    data = load(scratch)
    series = {name: monthly_series(df) for name, df in data.items()}
    stretch = {name: longest_stretch(df).attrs for name, df in data.items()}
    y_max = max(s.max() for s in series.values()) * 1.2
    x_min, x_max = pd.Timestamp("2016-01-01"), pd.Timestamp("2027-01-01")
    left, width, height, gap, bottom0 = 0.09, 0.86, 0.15, 0.065, 0.13

    for i, (name, s) in enumerate(series.items()):
        bottom = bottom0 + (len(series) - 1 - i) * (height + gap)
        ax = fig.add_axes([left, bottom, width, height], facecolor=SURFACE)
        ax.plot(s.index, s.values, color=BLUE, lw=2, solid_joinstyle="round", solid_capstyle="round")
        st = stretch[name]
        dot_month = st["start"].tz_localize(None).to_period("M").start_time
        dot_y = s.get(dot_month)
        ax.scatter([dot_month], [dot_y], s=90, color=ORANGE, edgecolor=SURFACE, linewidth=2, zorder=4)
        # the label sits above the line's highest point under its own width, so it never crosses the line
        frac = (dot_month - x_min) / (x_max - x_min)
        ha, lo, hi = ("right", -30, 1) if frac > 0.7 else ("left", -1, 30) if frac < 0.2 else ("center", -15, 15)
        under_label = s[(s.index >= dot_month + pd.DateOffset(months=lo)) & (s.index <= dot_month + pd.DateOffset(months=hi))]
        ax.annotate(f"I stopped opening, {st['start'].strftime('%b %Y')}", (mdates.date2num(dot_month), under_label.max()),
                    xytext=(0, 10), textcoords="offset points", ha=ha, va="bottom", fontsize=11, color=INK)
        ax.text(0, 1.08, name, transform=ax.transAxes, fontsize=14, fontweight="bold", color=INK, va="bottom")
        ax.text(1, 1.08, f"After the dot: {st['gap']:,} days without opening one, {len(longest_stretch(data[name])):,} emails",
                transform=ax.transAxes, fontsize=10.5, color=INK2, ha="right", va="bottom")
        ax.set_xlim(x_min, x_max)
        ax.set_ylim(0, y_max)
        ax.set_yticks([0, 20, 40, 60])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=INK2, labelsize=10, length=0, pad=5)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        if i == len(series) - 1:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        else:
            ax.set_xticklabels([])
        print(name, "months", len(s), s.index.min().date(), s.index.max().date(), "dot", dot_month.date(), dot_y)

    fig.text(0.09, 0.925, "I stopped opening their emails.", fontsize=25, fontweight="bold", color=INK)
    fig.text(0.09, 0.885, "The emails kept coming.", fontsize=25, fontweight="bold", color=BLUE)
    fig.text(0.09, 0.84, "Emails I received per month from each newsletter. The dot is the last one I opened\n"
             "before my longest stretch of opening none. After each dot, the line carries on as before.",
             fontsize=13, color=INK2, va="top", linespacing=1.4)
    fig.text(0.09, 0.05, "Source: full headers of 6,454 emails in my Gmail, 2016 to 2026. 'Opened' = Gmail read flag.",
             fontsize=10, color=MUTED, va="top")
    fig.savefig(OUT, facecolor=SURFACE)
    print(OUT)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
