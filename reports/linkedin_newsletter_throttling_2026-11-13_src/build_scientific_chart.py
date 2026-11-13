"""Figure for the report: monthly email volume from three newsletters against the recipient's open activity.

Per newsletter (one panel each): emails received per calendar month (line), every email flagged as read
in Gmail (rug ticks under the panel), the longest interval with no read email (shaded) with the email rate
inside it and in the 365 days before it. Reuses the loaders of the sibling scripts (scratchpad pickles,
personal data, never committed). Writes ~/Downloads/newsletter_volume_vs_opens_figure.png.

Usage: python build_scientific_chart.py <scratchpad dir holding mbrew/, mck/, skimm/>
"""
import sys
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

sys.path.insert(0, str(Path(__file__).parent))
from build_cumulative_chart import AXIS, INK, INK2, MUTED, SURFACE, load, longest_stretch  # noqa: E402
from build_timeline_chart import monthly_series  # noqa: E402

LINE, BAND, TICK = "#1c5cab", "#e9e9e5", "#c2410c"
OUT = Path.home() / "Downloads" / "newsletter_volume_vs_opens_figure.png"
X_MIN, X_MAX = pd.Timestamp("2016-01-01"), pd.Timestamp("2027-01-01")
CAPTION = (
    "Figure 1. Emails received per calendar month from theSkimm (A), McKinsey & Company (B) and Marketing Brew (C) "
    "in one Gmail account, from the first full month of each subscription to October 2026 (n = 6,454 messages, "
    "identified from full message headers). Ticks mark the emails flagged as read in Gmail (a proxy for opens: a "
    "read flag can be missed in Gmail and set without reading in other clients). The shaded band is the longest "
    "interval with no read email; its annotation gives the email rate per 30 days inside the band and in the 365 "
    "days before it. Partial first and current months are excluded. Promotional and event emails are included."
)


def wrap(text: str, width: int) -> str:
    import textwrap
    return "\n".join(textwrap.wrap(text, width))


def main(scratch: Path) -> None:
    plt.rcParams["font.family"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(9, 8), dpi=200, facecolor=SURFACE)
    data = load(scratch)
    series = {name: monthly_series(df) for name, df in data.items()}
    y_max = 70
    left, width, height, rug_h, gap, bottom0 = 0.08, 0.88, 0.16, 0.022, 0.05, 0.20

    for i, (name, s) in enumerate(series.items()):
        df = data[name]
        st = longest_stretch(df)
        start, end, gap_days = st.attrs["start"], st.attrs["end"], st.attrs["gap"]
        rate_in = len(st) / gap_days * 30
        before = df[(df.et >= start - pd.Timedelta(days=365)) & (df.et <= start)]
        rate_before = len(before) / 365 * 30
        bottom = bottom0 + (len(series) - 1 - i) * (height + rug_h + gap)
        ax = fig.add_axes([left, bottom + rug_h, width, height], facecolor=SURFACE)
        rug = fig.add_axes([left, bottom, width, rug_h], facecolor=SURFACE, sharex=ax)

        s_naive, e_naive = start.tz_localize(None), end.tz_localize(None)
        ax.axvspan(s_naive, e_naive, color=BAND, lw=0, zorder=0)
        ax.plot(s.index, s.values, color=LINE, lw=1.4, zorder=2)
        band_years = (e_naive - s_naive).days / 365
        label = f"{gap_days:,} d without a read email\n{rate_in:.1f} emails / 30 d (prior 365 d: {rate_before:.1f})"
        if band_years >= 1.5:
            ax.text(s_naive + (e_naive - s_naive) / 2, y_max * 0.97, label, ha="center", va="top", fontsize=8.5,
                    color=INK2, linespacing=1.35)
        else:
            ax.text(s_naive - pd.Timedelta(days=40), y_max * 0.97, label, ha="right", va="top", fontsize=8.5,
                    color=INK2, linespacing=1.35)
        reads = df[df.read].et.dt.tz_localize(None)
        rug.vlines(reads, 0, 1, color=TICK, lw=0.8)
        rug.set_ylim(0, 1)
        rug.set_yticks([])
        for spine in rug.spines.values():
            spine.set_visible(False)
        last = i == len(series) - 1
        rug.xaxis.set_major_locator(mdates.YearLocator())
        rug.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        rug.tick_params(axis="x", colors=INK2, labelsize=9, length=3 if last else 0, color=AXIS, pad=4, labelbottom=last)
        if last:
            rug.set_xlabel("Year", fontsize=10, color=INK2, labelpad=4)
        ax.text(0, 1.04, f"{'ABC'[i]}", transform=ax.transAxes, fontsize=12, fontweight="bold", color=INK, va="bottom")
        ax.text(0.022, 1.04, name, transform=ax.transAxes, fontsize=11, color=INK, va="bottom")
        ax.set_xlim(X_MIN, X_MAX)
        ax.set_ylim(0, y_max)
        ax.set_yticks([0, 20, 40, 60])
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(axis="y", colors=INK2, labelsize=9, length=3, color=AXIS, pad=3)
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.tick_params(axis="x", length=0, labelbottom=False)  # years are labelled under the rug strip
        print(name, f"band {start.date()} to {end.date()} ({gap_days} d): {rate_in:.1f}/30d, before {rate_before:.1f}/30d, "
              f"reads {len(reads)}")

    fig.text(0.02, 0.5, "Emails received per calendar month", rotation=90, va="center", fontsize=10, color=INK2)
    fig.text(0.08, 0.955, "Monthly email volume from three newsletters and the recipient's open activity, 2016 to 2026",
             fontsize=12.5, fontweight="bold", color=INK, va="bottom")
    handles = [Line2D([], [], color=LINE, lw=1.4, label="Emails received per month"),
               Line2D([], [], color=TICK, lw=0.8, marker="|", markersize=9, linestyle="none", label="Email flagged as read"),
               Patch(color=BAND, label="Longest interval with no read email")]
    fig.legend(handles=handles, loc="upper left", bbox_to_anchor=(0.075, 0.95), ncol=3, frameon=False, fontsize=9,
               handlelength=1.6, columnspacing=1.6, labelcolor=INK2)
    fig.text(0.08, 0.13, wrap(CAPTION, 150), fontsize=8.2, color=INK2, va="top", linespacing=1.45)
    fig.savefig(OUT, facecolor=SURFACE)
    print(OUT)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
