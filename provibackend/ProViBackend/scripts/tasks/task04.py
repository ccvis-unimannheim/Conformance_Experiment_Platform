"""
tasks/task04.py – Task ID 4: Describe / Compare / Process conformance across variants.

Group traces into control-flow variants (distinct activity sequences) and compare
their conformance fitness. Top-N variants by frequency.

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import save_svg, make_table, BLUE, ORANGE, FONT_TITLE, FONT_LABEL, FONT_ANNOT

TOP_N = 15


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task04_build_variant_df(log, fitness_df: pd.DataFrame) -> pd.DataFrame:
    """Group traces by activity sequence; compute count, coverage, fitness per variant."""
    records = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        seq = tuple(str(e.get("concept:name", "")) for e in trace)
        records.append({
            "trace_index": i,
            "variant":     seq,
            "length":      len(seq),
            "fitness":     float(fitness_df.iloc[i]["fitness"]),
        })

    if not records:
        return pd.DataFrame(columns=["rank", "variant", "count", "coverage",
                                      "fitness", "length", "label"])

    df = pd.DataFrame(records)
    total = len(df)

    groups = []
    for variant, sub in df.groupby("variant", sort=False):
        fits = sub["fitness"].values
        mean_fit = float(fits.mean())
        if fits.max() - fits.min() > 1e-6:
            logger.warning(
                f"task04: fitness not constant within variant "
                f"(len={len(variant)}, n={len(sub)}); using mean {mean_fit:.4f}"
            )
        groups.append({
            "variant": variant,
            "count":   len(sub),
            "fitness": mean_fit,
            "length":  int(sub["length"].iloc[0]),
        })

    vdf = pd.DataFrame(groups).sort_values("count", ascending=False).reset_index(drop=True)
    vdf["rank"]     = vdf.index + 1
    vdf["coverage"] = vdf["count"] / total * 100
    vdf["label"]    = vdf["rank"].apply(lambda r: f"V{r}")
    return vdf


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task04_bar_chart(vdf: pd.DataFrame, output_dir: str):
    """Bar chart: top-N variants × fitness; bars coloured by conformant / non-conformant."""
    top = vdf.head(TOP_N)
    colors = [BLUE if f >= 1.0 else ORANGE for f in top["fitness"]]

    fig, ax = plt.subplots(figsize=(max(7, len(top) * 0.75), 5))
    bars = ax.bar(top["label"], top["fitness"], color=colors, edgecolor="white", width=0.65)

    for bar, val in zip(bars, top["fitness"]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.012,
            f"{val:.3f}",
            ha="center", va="bottom", fontsize=FONT_ANNOT - 1,
        )

    import matplotlib.patches as mpatches
    ax.legend(
        handles=[
            mpatches.Patch(color=BLUE,   label="Conformant (fitness = 1.0)"),
            mpatches.Patch(color=ORANGE, label="Non-conformant (fitness < 1.0)"),
        ],
        frameon=False, fontsize=FONT_ANNOT,
        loc="lower right", bbox_to_anchor=(1.0, -0.18), ncol=2,
    )
    ax.set_xlabel(f"Variant (ranked by frequency, top {len(top)} of {len(vdf)})",
                  fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Conformance Fitness by Process Variant", fontsize=FONT_TITLE)
    ax.set_ylim(0, 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task04_bar_chart.svg"))


def task04_table(vdf: pd.DataFrame, output_dir: str):
    """Table: Rank | #Traces | Coverage% | Fitness | Length for top-N variants."""
    top = vdf.head(TOP_N)
    cell_text = [
        [
            row["label"],
            str(int(row["count"])),
            f"{row['coverage']:.1f}%",
            f"{row['fitness']:.4f}",
            str(int(row["length"])),
        ]
        for _, row in top.iterrows()
    ]
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Variant", "#Traces", "Coverage (%)", "Fitness", "Length (#act.)"],
        bbox=[0.03, 0.05, 0.94, 0.92],
        col_widths=[0.14, 0.18, 0.22, 0.24, 0.22],
        font_size=10.5,
        scale_xy=(1, 1.75),
        cell_pad=0.11,
    )
    ax.set_title(
        f"Top-{len(top)} Process Variants by Frequency (of {len(vdf)} total)",
        fontsize=FONT_TITLE, pad=3,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task04_table.svg"))


def task04_scatter_plot(vdf: pd.DataFrame, output_dir: str):
    """Scatter: all variants; x = trace count (log scale if wide), y = fitness."""
    counts  = vdf["count"].values.astype(float)
    fitness = vdf["fitness"].values
    colors  = [BLUE if f >= 1.0 else ORANGE for f in fitness]

    use_log = counts.max() / max(counts.min(), 1) > 20

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(counts, fitness, c=colors, s=40, alpha=0.75, edgecolors="white", linewidths=0.5)

    # Label top-5 most frequent variants; alternate y-offset when x-positions are close
    prev_log_x   = None
    prev_y_off   = 3
    for _, row in vdf.head(5).iterrows():
        log_x = np.log10(max(row["count"], 1))
        if prev_log_x is not None and abs(log_x - prev_log_x) < 0.15:
            y_off = -13 if prev_y_off >= 0 else 6
        else:
            y_off = 3
        prev_log_x = log_x
        prev_y_off = y_off
        ax.annotate(
            row["label"],
            (row["count"], row["fitness"]),
            textcoords="offset points", xytext=(5, y_off),
            fontsize=FONT_ANNOT - 1, color="#333333",
        )

    if use_log:
        ax.set_xscale("log")
        ax.set_xlabel("Variant size (#traces, log scale)", fontsize=FONT_LABEL)
    else:
        ax.set_xlabel("Variant size (#traces)", fontsize=FONT_LABEL)

    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Variant Frequency vs. Conformance Fitness", fontsize=FONT_TITLE)

    import matplotlib.patches as mpatches
    ax.legend(
        handles=[
            mpatches.Patch(color=BLUE,   label="Conformant"),
            mpatches.Patch(color=ORANGE, label="Non-conformant"),
        ],
        frameon=False, fontsize=FONT_ANNOT,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task04_scatter_plot.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str):
    """Generate all Task ID 4 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 4 visualizations ---")

    vdf = _task04_build_variant_df(log, fitness_df)
    if vdf.empty:
        logger.warning("      Skipped Task ID 4: no trace data available.")
        return

    logger.info(f"      -> {len(vdf)} unique variants; showing top-{min(TOP_N, len(vdf))}.")
    if len(vdf) == 1:
        logger.warning("      Only one variant found — charts will show a single entry.")

    task04_bar_chart(vdf, output_dir)
    task04_table(vdf, output_dir)
    task04_scatter_plot(vdf, output_dir)
