"""
tasks/task03.py – Task ID 3: Describe / Compare / Conformant vs. non-conformant traces.

Every idiom contrasts the same 3 behavioral factors between the Conformant
(fitness == 1.0) and Non-conformant (fitness < 1.0) trace groups — activity
presence, throughput time and variant composition:
    * bar_chart            – 3-panel grouped bars, one per factor
    * table                – 3-section table, one per factor
    * table_and_bar_chart  – 3-section table + activity-presence bar panel
    * stacked_bar          – 3-panel 100%-stacked bars, one per factor
    * matrix               – 3 stacked annotated grids, one per factor

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "table_and_bar_chart", "stacked_bar", "matrix"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table,
    draw_composition_stacked_bars, draw_value_heatmap,
    render_empty_state_svg, format_threshold,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Top-N most differentiating activities to show in charts/tables
TOP_N = 10

# Top-K most differentiating variants to show in charts/tables
TOP_K_VARIANTS = 5

# Number of quartile buckets for the throughput-time bar panel
N_TIME_BUCKETS = 4

_COLOR_CONFORM     = GREY_MED    # medium-dark grey
_COLOR_NON_CONFORM = GREY_LIGHT  # medium grey
_GROUPS = ["Conformant", "Non-conformant"]


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _task03_build_trace_rows(log, fitness_df: pd.DataFrame) -> list:
    """Pair each trace with its conformance label and the behavioral features every
    Task 3 idiom compares between the Conformant and Non-conformant groups:
    activity presence (set + sequence), throughput time and trace length.
    """
    rows = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        fitness = float(fitness_df.iloc[i]["fitness"])
        group   = "Conformant" if fitness >= 1.0 else "Non-conformant"

        activity_seq = tuple(str(event.get("concept:name", "")) for event in trace)
        activities = {a for a in activity_seq if a}

        timestamps = []
        for event in trace:
            ts = event.get("time:timestamp")
            if ts is not None and not pd.isna(ts):
                timestamps.append(pd.Timestamp(ts))
        duration_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0 \
            if len(timestamps) >= 2 else 0.0

        rows.append({
            "trace_index":    i,
            "group":          group,
            "fitness":        fitness,
            "activities":     activities,
            "activity_seq":   activity_seq,
            "num_events":     len(trace),
            "duration_hours": duration_hours,
        })
    return rows


def _task03_activity_presence_df(trace_rows: list, top_n: int = TOP_N) -> pd.DataFrame:
    """Compute per-activity presence rate (% of group traces containing activity)."""
    all_acts = set()
    for r in trace_rows:
        all_acts.update(r["activities"])

    groups = ["Conformant", "Non-conformant"]
    group_rows = {g: [r for r in trace_rows if r["group"] == g] for g in groups}

    records = []
    for act in all_acts:
        row = {"activity": act}
        for g in groups:
            n = len(group_rows[g])
            row[g] = (sum(1 for r in group_rows[g] if act in r["activities"]) / n * 100) if n else 0.0
        row["difference"] = abs(row["Conformant"] - row["Non-conformant"])
        records.append(row)

    df = pd.DataFrame(records).sort_values("difference", ascending=False).reset_index(drop=True)
    return df.head(top_n)


def _task03_throughput_stats_df(trace_rows: list) -> pd.DataFrame:
    """Per-group throughput-time (h) distribution: Group | Mean | Median | Std | Min | Max."""
    records = []
    for g in _GROUPS:
        vals = np.array([r["duration_hours"] for r in trace_rows if r["group"] == g], dtype=float)
        if vals.size:
            records.append({"Group": g, "Mean": float(vals.mean()), "Median": float(np.median(vals)),
                             "Std": float(vals.std(ddof=0)), "Min": float(vals.min()), "Max": float(vals.max())})
        else:
            records.append({"Group": g, "Mean": 0.0, "Median": 0.0, "Std": 0.0, "Min": 0.0, "Max": 0.0})
    return pd.DataFrame(records)


def _task03_throughput_buckets(trace_rows: list, n_buckets: int = N_TIME_BUCKETS):
    """Quartile-bucket the throughput times; return (labels, {group: counts_per_bucket})
    or None if there's not enough variance to bucket."""
    durations = np.array([r["duration_hours"] for r in trace_rows], dtype=float)
    if durations.size < 2 or np.unique(durations).size < 2:
        return None
    edges = np.unique(np.quantile(durations, np.linspace(0, 1, n_buckets + 1)))
    if len(edges) < 2:
        return None
    labels = [f"{format_threshold(edges[i])}–{format_threshold(edges[i + 1])}h"
              for i in range(len(edges) - 1)]
    counts = {g: [0] * len(labels) for g in _GROUPS}
    for r in trace_rows:
        b = int(np.clip(np.digitize([r["duration_hours"]], edges[1:-1])[0], 0, len(labels) - 1))
        counts[r["group"]][b] += 1
    return labels, counts


def _task03_variant_df(trace_rows: list, top_k: int = TOP_K_VARIANTS) -> pd.DataFrame:
    """Top-K most differentiating variants between groups.

    Columns: variant (Vx label, ranked by overall frequency), sequence (the raw
    activity tuple, used to build the parallel-sets flow matrix), Conformant /
    Non-conformant (share of that group's traces matching this variant, %),
    difference (|Conformant - Non-conformant|). Sorted by |difference|, top-K rows.
    """
    overall_counts = {}
    for r in trace_rows:
        overall_counts[r["activity_seq"]] = overall_counts.get(r["activity_seq"], 0) + 1
    ranked = sorted(overall_counts.items(), key=lambda kv: kv[1], reverse=True)
    variant_label = {seq: f"V{idx + 1}" for idx, (seq, _) in enumerate(ranked)}

    group_totals = {g: sum(1 for r in trace_rows if r["group"] == g) for g in _GROUPS}
    records = []
    for seq, _count in ranked:
        row = {"variant": variant_label[seq], "sequence": seq}
        for g in _GROUPS:
            n = group_totals[g]
            cnt = sum(1 for r in trace_rows if r["group"] == g and r["activity_seq"] == seq)
            row[g] = (cnt / n * 100) if n else 0.0
        row["difference"] = abs(row["Conformant"] - row["Non-conformant"])
        records.append(row)

    df = pd.DataFrame(records).sort_values("difference", ascending=False).reset_index(drop=True)
    return df.head(top_k)


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task03_bar_chart(presence_df: pd.DataFrame, throughput_buckets, variant_df: pd.DataFrame,
                      output_dir: str):
    """3-panel small multiples, one per behavioral factor (grouped bars, Conformant
    vs. Non-conformant): activity presence, throughput-time buckets, variant share."""
    fig, axes = plt.subplots(1, 3, figsize=(20, 5.5))
    width = 0.38

    # --- Panel 1: activity presence -----------------------------------------
    ax = axes[0]
    acts = presence_df["activity"].tolist()
    x = np.arange(len(acts))
    bars_c  = ax.bar(x - width / 2, presence_df["Conformant"],     width, color=_COLOR_CONFORM,
                     label="Conformant",     edgecolor="white")
    bars_nc = ax.bar(x + width / 2, presence_df["Non-conformant"], width, color=_COLOR_NON_CONFORM,
                     label="Non-conformant", edgecolor="white")
    for bars in (bars_c, bars_nc):
        for bar in bars:
            h = bar.get_height()
            if h > 1:
                ax.text(bar.get_x() + bar.get_width() / 2, h + 0.5,
                        f"{h:.0f}%", ha="center", va="bottom", fontsize=7)
    ax.set_xticks(x)
    ax.set_xticklabels(acts, rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Presence rate (% of traces)", fontsize=FONT_LABEL)
    ax.set_title(f"Activity Presence (top-{len(acts)})", fontsize=FONT_LABEL)
    if len(acts):
        ax.set_ylim(0, min(115, presence_df[["Conformant", "Non-conformant"]].values.max() * 1.18))
    ax.legend(frameon=False, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # --- Panel 2: throughput-time quartile buckets ---------------------------
    ax = axes[1]
    if throughput_buckets is not None:
        labels, counts = throughput_buckets
        x = np.arange(len(labels))
        ax.bar(x - width / 2, counts["Conformant"],     width, color=_COLOR_CONFORM,
               label="Conformant",     edgecolor="white")
        ax.bar(x + width / 2, counts["Non-conformant"], width, color=_COLOR_NON_CONFORM,
               label="Non-conformant", edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(labels, rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
        ax.set_ylabel("# traces", fontsize=FONT_LABEL)
        ax.legend(frameon=False, fontsize=FONT_ANNOT)
    else:
        ax.text(0.5, 0.5, "No throughput-time variance", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
    ax.set_title("Throughput Time (quartile buckets)", fontsize=FONT_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # --- Panel 3: variant composition ----------------------------------------
    ax = axes[2]
    if not variant_df.empty:
        variants = variant_df["variant"].tolist()
        x = np.arange(len(variants))
        ax.bar(x - width / 2, variant_df["Conformant"],     width, color=_COLOR_CONFORM,
               label="Conformant",     edgecolor="white")
        ax.bar(x + width / 2, variant_df["Non-conformant"], width, color=_COLOR_NON_CONFORM,
               label="Non-conformant", edgecolor="white")
        ax.set_xticks(x)
        ax.set_xticklabels(variants, fontsize=FONT_ANNOT - 1)
        ax.set_ylabel("Share of group (%)", fontsize=FONT_LABEL)
        ax.legend(frameon=False, fontsize=FONT_ANNOT)
    else:
        ax.text(0.5, 0.5, "No variants found", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
    ax.set_title(f"Variant Composition (top-{len(variant_df)})", fontsize=FONT_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    fig.suptitle("Conformant vs. Non-conformant: Behavioral Factors", fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_svg(fig, os.path.join(output_dir, "task03_bar_chart.svg"))


def task03_table(presence_df: pd.DataFrame, throughput_df: pd.DataFrame,
                  variant_df: pd.DataFrame, output_dir: str):
    """One figure, three labelled sections — Activity Presence | Throughput Time |
    Variant Composition — each its own table."""
    presence_rows = [
        [row["activity"], f"{row['Conformant']:.1f}%", f"{row['Non-conformant']:.1f}%",
         f"{row['difference']:.1f}pp"]
        for _, row in presence_df.iterrows()
    ] or [["—", "—", "—", "—"]]

    throughput_rows = [
        [row["Group"], f"{row['Mean']:.1f}", f"{row['Median']:.1f}", f"{row['Std']:.1f}",
         f"{row['Min']:.1f}", f"{row['Max']:.1f}"]
        for _, row in throughput_df.iterrows()
    ] or [["—", "—", "—", "—", "—", "—"]]

    variant_rows = [
        [row["variant"], f"{row['Conformant']:.1f}%", f"{row['Non-conformant']:.1f}%",
         f"{row['difference']:.1f}pp"]
        for _, row in variant_df.iterrows()
    ] or [["—", "—", "—", "—"]]

    height_ratios = [max(1, len(presence_rows)), max(1, len(throughput_rows)), max(1, len(variant_rows))]
    fig_h = max(8.0, 2.2 + sum(height_ratios) * 0.5)
    fig = plt.figure(figsize=(11, fig_h))
    gs = gridspec.GridSpec(3, 1, height_ratios=height_ratios, hspace=0.7)

    ax1 = fig.add_subplot(gs[0]); ax1.axis("off")
    make_table(
        ax1, cell_text=presence_rows,
        col_labels=["Activity", "Presence Conformant (%)", "Presence Non-conformant (%)", "Δ"],
        bbox=[0.02, 0.05, 0.96, 0.85], col_widths=[0.40, 0.22, 0.24, 0.14],
        font_size=9.5, cell_pad=0.08,
    )
    ax1.set_title(f"1. Activity Presence (top-{len(presence_rows)})", fontsize=FONT_TITLE, pad=8)

    ax2 = fig.add_subplot(gs[1]); ax2.axis("off")
    make_table(
        ax2, cell_text=throughput_rows,
        col_labels=["Group", "Mean (h)", "Median (h)", "Std (h)", "Min (h)", "Max (h)"],
        bbox=[0.02, 0.05, 0.96, 0.85], col_widths=[0.24, 0.15, 0.15, 0.15, 0.15, 0.16],
        font_size=9.5, cell_pad=0.08,
    )
    ax2.set_title("2. Throughput Time", fontsize=FONT_TITLE, pad=8)

    ax3 = fig.add_subplot(gs[2]); ax3.axis("off")
    make_table(
        ax3, cell_text=variant_rows,
        col_labels=["Variant", "Share Conformant (%)", "Share Non-conformant (%)", "Δ"],
        bbox=[0.02, 0.05, 0.96, 0.85], col_widths=[0.18, 0.30, 0.30, 0.14],
        font_size=9.5, cell_pad=0.08,
    )
    ax3.set_title(f"3. Variant Composition (top-{len(variant_rows)})", fontsize=FONT_TITLE, pad=8)

    fig.suptitle("Conformant vs. Non-conformant: Behavioral Factors", fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, os.path.join(output_dir, "task03_table.svg"))


def task03_table_and_bar_chart(presence_df: pd.DataFrame, throughput_df: pd.DataFrame,
                                variant_df: pd.DataFrame, output_dir: str):
    """Left: three-section table (Activity Presence | Throughput Time | Variant
    Composition), same as task03_table. Right: a single bar panel showing the
    top-N activity-presence differences (the most visually informative factor)."""
    presence_rows = [
        [row["activity"], f"{row['Conformant']:.1f}%", f"{row['Non-conformant']:.1f}%",
         f"{row['difference']:.1f}pp"]
        for _, row in presence_df.iterrows()
    ] or [["—", "—", "—", "—"]]

    throughput_rows = [
        [row["Group"], f"{row['Mean']:.1f}", f"{row['Median']:.1f}", f"{row['Std']:.1f}",
         f"{row['Min']:.1f}", f"{row['Max']:.1f}"]
        for _, row in throughput_df.iterrows()
    ] or [["—", "—", "—", "—", "—", "—"]]

    variant_rows = [
        [row["variant"], f"{row['Conformant']:.1f}%", f"{row['Non-conformant']:.1f}%",
         f"{row['difference']:.1f}pp"]
        for _, row in variant_df.iterrows()
    ] or [["—", "—", "—", "—"]]

    height_ratios = [max(1, len(presence_rows)), max(1, len(throughput_rows)), max(1, len(variant_rows))]
    fig_h = max(8.0, 2.2 + sum(height_ratios) * 0.5)
    fig = plt.figure(figsize=(18, fig_h))
    gs  = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], wspace=0.30)

    gs_left = gridspec.GridSpecFromSubplotSpec(3, 1, subplot_spec=gs[0],
                                                height_ratios=height_ratios, hspace=0.7)

    ax1 = fig.add_subplot(gs_left[0]); ax1.axis("off")
    make_table(
        ax1, cell_text=presence_rows,
        col_labels=["Activity", "Presence Conf. (%)", "Presence Non-conf. (%)", "Δ"],
        bbox=[0.01, 0.05, 0.98, 0.85], col_widths=[0.40, 0.22, 0.24, 0.14],
        font_size=9, cell_pad=0.08,
    )
    ax1.set_title(f"1. Activity Presence (top-{len(presence_rows)})", fontsize=FONT_TITLE, pad=8)

    ax2 = fig.add_subplot(gs_left[1]); ax2.axis("off")
    make_table(
        ax2, cell_text=throughput_rows,
        col_labels=["Group", "Mean (h)", "Median (h)", "Std (h)", "Min (h)", "Max (h)"],
        bbox=[0.01, 0.05, 0.98, 0.85], col_widths=[0.24, 0.15, 0.15, 0.15, 0.15, 0.16],
        font_size=9, cell_pad=0.08,
    )
    ax2.set_title("2. Throughput Time", fontsize=FONT_TITLE, pad=8)

    ax3 = fig.add_subplot(gs_left[2]); ax3.axis("off")
    make_table(
        ax3, cell_text=variant_rows,
        col_labels=["Variant", "Share Conf. (%)", "Share Non-conf. (%)", "Δ"],
        bbox=[0.01, 0.05, 0.98, 0.85], col_widths=[0.18, 0.30, 0.30, 0.14],
        font_size=9, cell_pad=0.08,
    )
    ax3.set_title(f"3. Variant Composition (top-{len(variant_rows)})", fontsize=FONT_TITLE, pad=8)

    ax_bar = fig.add_subplot(gs[1])
    acts  = presence_df["activity"].tolist()
    x     = np.arange(len(acts))
    w     = 0.38
    ax_bar.barh(x - w / 2, presence_df["Conformant"],     w,
                color=_COLOR_CONFORM,     label="Conformant",     edgecolor="white")
    ax_bar.barh(x + w / 2, presence_df["Non-conformant"], w,
                color=_COLOR_NON_CONFORM, label="Non-conformant", edgecolor="white")
    ax_bar.set_yticks(x)
    ax_bar.set_yticklabels(acts, fontsize=FONT_ANNOT - 1)
    ax_bar.set_xlabel("Presence rate (%)", fontsize=FONT_LABEL)
    ax_bar.set_title(f"Top-{len(acts)} Activity-Presence Differences", fontsize=FONT_TITLE, pad=8)
    ax_bar.legend(frameon=False, fontsize=FONT_ANNOT,
                  loc="lower right", bbox_to_anchor=(1.0, -0.12), ncol=2)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.5)
    ax_bar.set_axisbelow(True)

    fig.suptitle("Conformant vs. Non-conformant: Behavioral Factors", fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, os.path.join(output_dir, "task03_table_and_bar_chart.svg"))


def task03_stacked_bar(trace_rows: list, throughput_buckets, variant_df: pd.DataFrame,
                        output_dir: str):
    """3-panel small multiples, each a 100%-stacked bar per conformance group —
    one panel per behavioral factor:
      Panel 1 "Activity Presence": segments = top-N activities + 'Other',
              segment height = activity's share of the group's total presence mass.
      Panel 2 "Throughput Time": segments = throughput-time quartile buckets
              (from _task03_throughput_buckets), segment height = share of the
              group's traces falling in that bucket.
      Panel 3 "Variant Composition": segments = top-K variants + 'Other',
              segment height = share of the group's traces matching that variant.
    """
    path = os.path.join(output_dir, "task03_stacked_bar.svg")
    if not trace_rows:
        render_empty_state_svg(path, "Conformant vs. Non-conformant: Behavioral Factor Composition",
                               "No traces found.")
        return

    fig, axes = plt.subplots(1, 3, figsize=(16, 5.5))

    # --- Panel 1: activity presence composition -------------------------------
    ax = axes[0]
    full = _task03_activity_presence_df(trace_rows, top_n=10**9)
    if not full.empty:
        top = full.head(TOP_N)
        seg_labels = top["activity"].tolist() + (["Other"] if len(full) > len(top) else [])
        rates = np.zeros((len(seg_labels), len(_GROUPS)))
        for gi, g in enumerate(_GROUPS):
            tot = float(full[g].sum())
            if tot <= 0:
                continue
            for si, (_, row) in enumerate(top.iterrows()):
                rates[si, gi] = row[g] / tot * 100
            if len(seg_labels) > len(top):
                rates[-1, gi] = float(full[g].sum() - top[g].sum()) / tot * 100
        draw_composition_stacked_bars(ax, _GROUPS, seg_labels, rates)
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False,
                  fontsize=FONT_ANNOT - 2, title="Activity", title_fontsize=FONT_ANNOT - 1)
    else:
        ax.text(0.5, 0.5, "No activities found", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
    ax.set_ylabel("Share (%)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 100)
    ax.set_title("Activity Presence", fontsize=FONT_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # --- Panel 2: throughput-time quartile composition -------------------------
    ax = axes[1]
    if throughput_buckets is not None:
        labels, counts = throughput_buckets
        rates = np.zeros((len(labels), len(_GROUPS)))
        for gi, g in enumerate(_GROUPS):
            tot = float(sum(counts[g]))
            if tot <= 0:
                continue
            for si in range(len(labels)):
                rates[si, gi] = counts[g][si] / tot * 100
        draw_composition_stacked_bars(ax, _GROUPS, labels, rates)
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False,
                  fontsize=FONT_ANNOT - 2, title="Throughput time", title_fontsize=FONT_ANNOT - 1)
    else:
        ax.text(0.5, 0.5, "No throughput-time variance", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
    ax.set_ylabel("Share (%)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 100)
    ax.set_title("Throughput Time", fontsize=FONT_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    # --- Panel 3: variant composition ------------------------------------------
    ax = axes[2]
    if not variant_df.empty:
        seg_labels = variant_df["variant"].tolist() + ["Other"]
        rates = np.zeros((len(seg_labels), len(_GROUPS)))
        for gi, g in enumerate(_GROUPS):
            covered = 0.0
            for si, (_, row) in enumerate(variant_df.iterrows()):
                rates[si, gi] = row[g]
                covered += row[g]
            rates[-1, gi] = max(0.0, 100.0 - covered)
        draw_composition_stacked_bars(ax, _GROUPS, seg_labels, rates)
        ax.legend(loc="upper left", bbox_to_anchor=(1.02, 1.0), frameon=False,
                  fontsize=FONT_ANNOT - 2, title="Variant", title_fontsize=FONT_ANNOT - 1)
    else:
        ax.text(0.5, 0.5, "No variants found", ha="center", va="center",
                transform=ax.transAxes, fontsize=FONT_ANNOT)
    ax.set_ylabel("Share (%)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 100)
    ax.set_title("Variant Composition", fontsize=FONT_LABEL)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    fig.suptitle("Conformant vs. Non-conformant: Behavioral Factor Composition", fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    save_svg(fig, path)


def task03_matrix(presence_df: pd.DataFrame, throughput_buckets, variant_df: pd.DataFrame,
                   output_dir: str):
    """3 stacked annotated grids (Conformance Group on the x-axis), one per
    behavioral factor:
      Grid 1 "Activity Presence": rows = top-N activities, cells = presence rate (%).
      Grid 2 "Throughput Time": rows = throughput-time quartile buckets,
              cells = share of the group's traces in that bucket (%).
      Grid 3 "Variant Composition": rows = top-K variants, cells = share of the
              group's traces matching that variant (%).
    """
    path = os.path.join(output_dir, "task03_matrix.svg")

    acts = presence_df["activity"].tolist()
    presence_data = presence_df[["Conformant", "Non-conformant"]].values if acts else np.zeros((0, 2))

    if throughput_buckets is not None:
        tt_labels, counts = throughput_buckets
        tt_data = np.zeros((len(tt_labels), len(_GROUPS)))
        for gi, g in enumerate(_GROUPS):
            tot = float(sum(counts[g]))
            if tot <= 0:
                continue
            for si in range(len(tt_labels)):
                tt_data[si, gi] = counts[g][si] / tot * 100
    else:
        tt_labels, tt_data = ["—"], np.zeros((1, len(_GROUPS)))

    variants = variant_df["variant"].tolist()
    variant_data = variant_df[["Conformant", "Non-conformant"]].values if variants else np.zeros((0, 2))
    if not variants:
        variants, variant_data = ["—"], np.zeros((1, len(_GROUPS)))
    if not acts:
        acts, presence_data = ["—"], np.zeros((1, len(_GROUPS)))

    fig_h = 0.5 * (len(acts) + len(tt_labels) + len(variants)) + 4.0
    fig, axes = plt.subplots(3, 1, figsize=(6, fig_h))

    draw_value_heatmap(fig, axes[0], presence_data, acts, _GROUPS,
                       cbar_label="Presence rate (%)", cell_fmt="{:.0f}%", annotate=True)
    axes[0].set_title(f"Activity Presence (top-{len(acts)})", fontsize=FONT_LABEL)

    draw_value_heatmap(fig, axes[1], tt_data, tt_labels, _GROUPS,
                       cbar_label="Share of traces (%)", cell_fmt="{:.0f}%", annotate=True)
    axes[1].set_title("Throughput Time (quartile buckets)", fontsize=FONT_LABEL)

    draw_value_heatmap(fig, axes[2], variant_data, variants, _GROUPS, xlabel="Conformance Group",
                       cbar_label="Share of group (%)", cell_fmt="{:.0f}%", annotate=True)
    axes[2].set_title(f"Variant Composition (top-{len(variants)})", fontsize=FONT_LABEL)

    fig.suptitle("Conformant vs. Non-conformant: Behavioral Factors", fontsize=FONT_TITLE)
    fig.tight_layout(rect=[0, 0, 1, 0.96])
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str):
    """Generate all Task ID 3 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 3 visualizations ---")

    trace_rows = _task03_build_trace_rows(log, fitness_df)
    n_c  = sum(1 for r in trace_rows if r["group"] == "Conformant")
    n_nc = len(trace_rows) - n_c
    logger.info(f"      -> Conformant: {n_c}  |  Non-conformant: {n_nc}")

    if n_c == 0:
        logger.warning("      No conformant traces — Conformant group is empty.")
    if n_nc == 0:
        logger.warning("      No non-conformant traces — Non-conformant group is empty.")

    presence_df       = _task03_activity_presence_df(trace_rows)
    throughput_df     = _task03_throughput_stats_df(trace_rows)
    throughput_buckets = _task03_throughput_buckets(trace_rows)
    variant_df        = _task03_variant_df(trace_rows)
    logger.info(f"      -> Top-{len(presence_df)} activities, "
                f"top-{len(variant_df)} variants extracted.")

    task03_bar_chart(presence_df, throughput_buckets, variant_df, output_dir)
    task03_table(presence_df, throughput_df, variant_df, output_dir)
    task03_table_and_bar_chart(presence_df, throughput_df, variant_df, output_dir)

    task03_stacked_bar(trace_rows, throughput_buckets, variant_df, output_dir)
    task03_matrix(presence_df, throughput_buckets, variant_df, output_dir)
