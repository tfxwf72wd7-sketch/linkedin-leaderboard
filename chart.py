"""Render the LinkedIn Leaderboard chart in the established format.

Replicates the Excel chart: Alex's daily points (out of 8) as bars above zero,
Elizabeth's below zero, a net-result marker per day (left axis), and a trailing
7-day net line on the secondary axis (+/-21). Shows the last 14 days.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

# Palette sampled from the original Excel chart
ALEX = "#FF6F59"
LIZ = "#2CA6A4"
NET = "#2B2B2B"
PASTWEEK = "#C9B8E8"
BG = "#F4F4F6"
GRID = "#DDDDDE"
TEXT = "#595959"
TITLE = "#404040"

N_DAYS = 14


def load_history(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def render(history: dict, out_path: Path, end_day: date | None = None) -> Path:
    days_map = history["days"]
    end_day = end_day or max(date.fromisoformat(d) for d in days_map)
    window = [end_day - timedelta(days=i) for i in range(N_DAYS - 1, -1, -1)]

    alex, liz, net = [], [], []
    for d in window:
        rec = days_map.get(d.isoformat())
        if rec is None:
            alex.append(None)
            liz.append(None)
            net.append(None)
        else:
            alex.append(rec["alex"])
            liz.append(rec["liz"])
            net.append(rec["alex"] - rec["liz"])

    # Trailing 7-day net sum (including the day itself); needs history before window
    pastweek = []
    for d in window:
        total = 0.0
        seen = False
        for i in range(7):
            rec = days_map.get((d - timedelta(days=i)).isoformat())
            if rec is not None:
                total += rec["alex"] - rec["liz"]
                seen = True
        pastweek.append(total if seen else None)

    x = range(N_DAYS)
    fig, ax = plt.subplots(figsize=(6.85, 3.90), dpi=100)
    fig.patch.set_facecolor(BG)
    ax.set_facecolor(BG)

    # Gridlines
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=0.8)

    # Bars
    bar_w = 0.72
    for i, (a, l) in enumerate(zip(alex, liz)):
        if a is not None:
            ax.bar(i, a, width=bar_w, color=ALEX, zorder=3)
        if l is not None:
            ax.bar(i, -l, width=bar_w, color=LIZ, zorder=3)

    # Past-week line (secondary axis) drawn beneath the net markers
    ax2 = ax.twinx()
    xs = [i for i, v in enumerate(pastweek) if v is not None]
    ys = [v for v in pastweek if v is not None]
    ax2.plot(xs, ys, linestyle=(0, (6, 4)), linewidth=2.2, color=PASTWEEK, zorder=4)
    ax2.set_ylim(-21, 21)
    ax2.set_yticks(range(-21, 22, 3))
    ax2.tick_params(axis="y", labelsize=8.5, colors=PASTWEEK, length=0)
    for t in ax2.get_yticklabels():
        t.set_color("#B3A2D6")

    # Net result markers
    for i, v in enumerate(net):
        if v is not None:
            ax.plot(i, v, marker="o", markersize=6.5, color=NET,
                    markeredgecolor="white", markeredgewidth=1.2, zorder=6)

    # Left axis
    ax.set_ylim(-8.6, 7.6)
    ax.set_yticks(range(-8, 8))
    ax.tick_params(axis="y", labelsize=8.5, colors=TEXT, length=0)

    # X labels along the zero line, Excel-style
    ax.set_xlim(-0.7, N_DAYS - 0.3)
    ax.set_xticks([])
    for i, d in enumerate(window):
        ax.text(i, -0.45, d.strftime("%d/%b"), ha="center", va="top",
                fontsize=8, color=TEXT, zorder=5)

    # Heavy axis lines like the Excel original
    for spine in list(ax.spines.values()) + list(ax2.spines.values()):
        spine.set_visible(False)
    ax.axhline(0, color="#BFBFBF", linewidth=0.8, zorder=2)
    ax.axvline(-0.7, color="black", linewidth=3, zorder=7)
    ax.axhline(-8.6, color="black", linewidth=3, zorder=7)

    ax.set_title("LinkedIn Leaderboard", fontsize=17, fontweight="bold",
                 color=TITLE, pad=14)

    # Legend
    handles = [
        Patch(facecolor=ALEX, label="Alex"),
        Patch(facecolor=LIZ, label="Elizabeth"),
        Line2D([], [], marker="o", color="none", markerfacecolor=NET,
               markeredgecolor="white", markersize=7, label="Net Result"),
        Line2D([], [], linestyle=(0, (6, 4)), linewidth=2.2, color=PASTWEEK,
               label="PastWeek"),
    ]
    leg = ax.legend(handles=handles, loc="upper center",
                    bbox_to_anchor=(0.5, -0.10), ncol=4, frameon=True,
                    fontsize=8.5, handlelength=1.6, borderpad=0.6)
    leg.get_frame().set_facecolor(BG)
    leg.get_frame().set_edgecolor("#CCCCCC")
    for t in leg.get_texts():
        t.set_color(TEXT)

    fig.subplots_adjust(left=0.055, right=0.945, top=0.86, bottom=0.16)
    fig.savefig(out_path, facecolor=BG)
    plt.close(fig)
    return out_path


if __name__ == "__main__":
    import sys

    hist = load_history(Path("data/history.json"))
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("chart.png")
    render(hist, out)
    print(f"wrote {out}")
