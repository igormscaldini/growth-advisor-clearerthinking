"""LinkedIn chart: cumulative emails received after Igor's last open, one line per newsletter.

Each line starts at Igor's last open before his longest no-open stretch and runs until he opened one again.
Input: the flattened Gmail header pickles from the scratchpad analysis (personal data, never committed).
Writes ~/Downloads/newsletter_emails_after_last_open.png (1200x1200).

Usage: python build_cumulative_chart.py <scratchpad dir holding mbrew/, mck/, skimm/>
"""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

SURFACE, INK, INK2, MUTED, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984", "#d9d8d3"
COLORS = {"theSkimm": "#2a78d6", "McKinsey & Company": "#eb6834", "Marketing Brew": "#1baf7a"}
# label offsets in points and alignment, placed so no label crosses another line
LABEL_POS = {"theSkimm": ((10, 0), "left"), "McKinsey & Company": ((0, 34), "center"), "Marketing Brew": ((14, -20), "left")}
OUT = Path.home() / "Downloads" / "newsletter_emails_after_last_open.png"


def load(scratch: Path) -> dict[str, pd.DataFrame]:
    mb = pd.read_pickle(scratch / "mbrew" / "mb2.pkl")
    mb = mb.assign(et=mb.hdr.dt.tz_convert("America/New_York"), read=~mb.labels.str.contains("UNREAD"))
    mck = pd.read_pickle(scratch / "mck" / "flat.pkl")
    mck = mck[mck.from_domain == "email.mckinsey.com"]
    skimm = pd.read_pickle(scratch / "skimm" / "flat.pkl")
    return {"theSkimm": skimm, "McKinsey & Company": mck, "Marketing Brew": mb}


def longest_stretch(df: pd.DataFrame) -> pd.DataFrame:
    """Emails received inside the longest gap between two opens, with days since the last open."""
    reads = df[df.read].et.sort_values().reset_index(drop=True)
    gaps = reads.diff()
    i = gaps.idxmax()
    start, end = reads[i - 1], reads[i]
    inside = df[(df.et > start) & (df.et < end)].sort_values("et")
    out = pd.DataFrame({"days": (inside.et - start).dt.total_seconds() / 86400})
    out["cum"] = range(1, len(out) + 1)
    out.attrs.update(start=start, end=end, gap=(end - start).days)
    return out


def main(scratch: Path) -> None:
    plt.rcParams["font.family"] = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]
    fig = plt.figure(figsize=(8, 8), dpi=150, facecolor=SURFACE)
    ax = fig.add_axes([0.10, 0.17, 0.62, 0.55], facecolor=SURFACE)
    series = {name: longest_stretch(df) for name, df in load(scratch).items()}
    for z, (name, s) in enumerate(series.items()):
        c = COLORS[name]
        xs = [0, *s.days, s.attrs["gap"]]
        ys = [0, *s.cum, s.cum.iloc[-1]]
        ax.step(xs, ys, where="post", color=c, lw=2, zorder=2 + z * 0.1, solid_joinstyle="round", solid_capstyle="round")
        x1, y1 = s.attrs["gap"], s.cum.iloc[-1]
        ax.scatter([x1], [y1], s=64, color=c, edgecolor=SURFACE, linewidth=2, zorder=4)
        ax.annotate(f"{name}\n{y1:,} emails in {x1:,} days", (x1, y1), xytext=LABEL_POS[name][0], textcoords="offset points",
                    va="center", ha=LABEL_POS[name][1], fontsize=12, color=INK, linespacing=1.35, annotation_clip=False)
        print(name, s.attrs["start"].date(), "->", s.attrs["end"].date(), x1, "days", y1, "emails")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK2, labelsize=11, length=0, pad=6)
    ax.set_xlim(0, 1150)
    ax.set_ylim(0, 760)
    ax.set_xticks([0, 250, 500, 750, 1000])
    ax.set_yticks([0, 200, 400, 600])
    ax.set_yticklabels(["0", "200", "400", "600"])
    ax.set_xlabel("Days since I last opened one of their emails", fontsize=12, color=INK2, labelpad=10)
    ax.set_ylabel("Emails received (cumulative)", fontsize=12, color=INK2, labelpad=10)

    fig.text(0.10, 0.90, "I stopped opening their emails.", fontsize=26, color=INK)
    fig.text(0.10, 0.855, "The emails kept coming at full speed.", fontsize=26, color=COLORS["theSkimm"])
    fig.text(0.10, 0.80, "Emails each newsletter sent me during my longest stretch of opening none.\n"
             "A slowdown would show up as a flattening line.",
             fontsize=13.5, color=INK2, va="top", linespacing=1.4)
    fig.text(0.10, 0.075, "Source: full headers of 6,454 emails in my Gmail, 2016 to 2026. 'Opened' = Gmail read flag.",
             fontsize=10.5, color=MUTED, va="top")
    fig.savefig(OUT, facecolor=SURFACE)
    print(OUT)


if __name__ == "__main__":
    main(Path(sys.argv[1]))
