"""
tasks/task22.py – Task ID 22: Explain / Summarize / Reasons for process conformance.

How can the overall process conformance be explained for different traces? The
analyst supplies one or more *candidate reasons* — case-level data attributes —
and we relate each trace's fitness to those reasons, summarising the explanation
per sub-log and presenting it (among others) on the process model.

Reason-first framing distinguishes task22 from task33 (which merely *compares*
conformance between attribute values): here fitness is the explained variable,
the attribute is the explanatory one, the scatter carries a trend + correlation,
the table carries each group's deviation from the overall mean, and the BPMN
model localises *where* conformance breaks.

Building blocks (sub-log split, violation extraction, annotated BPMN) are reused
from task30/shared, so a new dataset flows through unchanged: the compare
attribute is auto-detected upstream and split_by_attribute adapts to numeric
(median split) or categorical values.

Public API:
    generate(log, fitness_df, alignments, output_dir,
             model_path=None, compare_attribute="AMOUNT_REQ")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "scatter_plot",
          "flow_chart_elaborate_table", "table", "table_bar_chart",
          "parallel_sets"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets,
    parse_bpmn_model, compose_bpmn_panels, alignment_pairs_to_rows,
    render_empty_state_svg, format_threshold,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse the proven sub-log split + attribute helpers from task30.
from tasks.task30 import split_by_attribute, _available_case_attributes

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GROUP_PALETTE = [GREY_MED, GREY_LIGHT, "#333333", "#CCCCCC", "#888888"]

# Fitness bands: (label, lo, hi, fill_color, text_color) — shared look with task33
_FITNESS_BANDS = [
    ("0.00–0.25", 0.00, 0.25, "#333333", "white"),
    ("0.25–0.50", 0.25, 0.50, "#777777", "white"),
    ("0.50–0.75", 0.50, 0.75, "#AAAAAA", "#333333"),
    ("0.75–1.00", 0.75, 1.01, "#D9D9D9", "#333333"),
]

_FIT_THRESHOLD = 0.8


def _group_colors(groups: list) -> list:
    return [_GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i in range(len(groups))]


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def _build_trace_df(fitness_df: pd.DataFrame, assignment: list, meta: dict) -> pd.DataFrame:
    n = min(len(fitness_df), len(assignment))
    df = fitness_df.iloc[:n].copy()
    df["group"] = assignment[:n]
    if meta["type"] == "numeric":
        df["value"] = meta["numeric_values"][:n]
    return df[df["group"].notna()].reset_index(drop=True)


def _group_stats(trace_df: pd.DataFrame, groups: list, overall_mean: float) -> pd.DataFrame:
    rows = []
    for g in groups:
        sub = trace_df[trace_df["group"] == g]["fitness"]
        n = len(sub)
        mean = float(sub.mean()) if n else 0.0
        rows.append({
            "group":       g,
            "n":           n,
            "pct_conform": float((sub >= _FIT_THRESHOLD).sum() / n * 100) if n else 0.0,
            "mean":        mean,
            "median":      float(sub.median()) if n else 0.0,
            "std":         float(sub.std())    if n else 0.0,
            "delta":       mean - overall_mean,   # explanatory deviation
        })
    return pd.DataFrame(rows)


def _band_rates(trace_df: pd.DataFrame, groups: list) -> np.ndarray:
    """(n_bands × n_groups): % of sub-log traces per fitness band."""
    data = np.zeros((len(_FITNESS_BANDS), len(groups)), dtype=float)
    for gi, g in enumerate(groups):
        sub = trace_df[trace_df["group"] == g]["fitness"]
        n = len(sub)
        if n == 0:
            continue
        for bi, (_, lo, hi, _, _) in enumerate(_FITNESS_BANDS):
            data[bi, gi] = float(((sub >= lo) & (sub < hi)).sum() / n * 100)
    return data


def _band_counts(trace_df: pd.DataFrame, groups: list) -> np.ndarray:
    """(n_groups × n_bands) raw counts — for parallel sets ribbons."""
    data = np.zeros((len(groups), len(_FITNESS_BANDS)), dtype=int)
    for gi, g in enumerate(groups):
        sub = trace_df[trace_df["group"] == g]["fitness"]
        for bi, (_, lo, hi, _, _) in enumerate(_FITNESS_BANDS):
            data[gi, bi] = int(((sub >= lo) & (sub < hi)).sum())
    return data


def _activity_violations(alignments) -> dict:
    """activity name -> total non-synchronous move count across the log."""
    counts: dict = {}
    for result in alignments:
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            if step["moveType"] == "Synchronous Move":
                continue
            activity = (step["model_move"] if step["moveType"] == "Model Move"
                        else step["log_move"])
            if not activity or activity in {"-", "None", "(skip)"}:
                continue
            counts[activity] = counts.get(activity, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Idiom 1: bar_chart — mean fitness per reason group
# ---------------------------------------------------------------------------

def task22_bar_chart(trace_df, groups, attr, output_dir):
    colors = _group_colors(groups)
    fig, ax = plt.subplots(figsize=(max(6, len(groups) * 2.2), 5.5))

    means = []
    for i, (g, color) in enumerate(zip(groups, colors)):
        sub = trace_df[trace_df["group"] == g]["fitness"]
        mean = float(sub.mean()) if len(sub) else 0.0
        std  = float(sub.std())  if len(sub) else 0.0
        means.append(mean)
        ax.bar(i, mean, color=color, edgecolor="white", linewidth=0.6, width=0.6)
        yerr_lo, yerr_hi = min(std, mean), min(std, 1.0 - mean)
        ax.errorbar(i, mean, yerr=[[yerr_lo], [yerr_hi]],
                    color="#555555", capsize=5, linewidth=1.2)
        txt_y = max(mean / 2, 0.03)
        txt_c = "white" if mean > 0.12 else "#444444"
        ax.text(i, txt_y, f"n={len(sub)}", ha="center", va="center",
                fontsize=FONT_ANNOT - 1, color=txt_c)

    # Explanatory signal: how much of the conformance spread this reason accounts for
    if means:
        spread = max(means) - min(means)
        ax.text(0.99, 0.98, f"mean spread = {spread:.3f}",
                transform=ax.transAxes, ha="right", va="top",
                fontsize=FONT_ANNOT - 1, color="#777777")

    ax.set_xticks(range(len(groups)))
    ax.set_xticklabels(groups, rotation=0, ha="center", fontsize=FONT_ANNOT)
    ax.set_ylabel("Mean Fitness (± 1 std)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 1.15)
    ax.set_title(f"Conformance Explained by {attr}", fontsize=FONT_TITLE)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task22_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 2: stacked_bar — fitness-band composition per reason group
# ---------------------------------------------------------------------------

def task22_stacked_bar(trace_df, groups, attr, output_dir):
    band_names   = [b[0] for b in _FITNESS_BANDS]
    band_colors  = [b[3] for b in _FITNESS_BANDS]
    band_txtcols = [b[4] for b in _FITNESS_BANDS]
    rates = _band_rates(trace_df, groups)

    fig, ax = plt.subplots(figsize=(max(6, len(groups) * 2.2), 5.5))
    bottoms = np.zeros(len(groups))
    x = np.arange(len(groups))
    for bi, (band, fill, tc) in enumerate(zip(band_names, band_colors, band_txtcols)):
        vals = rates[bi]
        lbl = band if np.any(vals > 0) else "_nolegend_"
        bars = ax.bar(x, vals, bottom=bottoms, color=fill,
                      edgecolor="white", linewidth=0.5, label=lbl, width=0.6)
        for rect, val in zip(bars, vals):
            if val >= 6:
                ax.text(rect.get_x() + rect.get_width() / 2,
                        rect.get_y() + rect.get_height() / 2,
                        f"{val:.0f}%", ha="center", va="center",
                        fontsize=FONT_ANNOT - 1, color=tc)
        bottoms += vals

    ax.set_xticks(x)
    ax.set_xticklabels(groups, rotation=0, ha="center", fontsize=FONT_ANNOT)
    ax.set_ylabel("% of sub-log traces", fontsize=FONT_LABEL)
    ax.set_ylim(0, 105)
    ax.set_title(f"Fitness Band Composition by {attr}", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task22_stacked_bar.svg"))


# ---------------------------------------------------------------------------
# Idiom 3: scatter_plot — fitness vs reason, with trend + correlation
# ---------------------------------------------------------------------------

def task22_scatter_plot(trace_df, groups, meta, attr, output_dir):
    colors = dict(zip(groups, _group_colors(groups)))
    rng = np.random.default_rng(42)

    fig, ax = plt.subplots(figsize=(10, 5))
    if meta["type"] == "numeric":
        for g in groups:
            sub = trace_df[trace_df["group"] == g]
            if sub.empty:
                continue
            ax.scatter(sub["value"], sub["fitness"], c=colors[g], s=14,
                       alpha=0.55, linewidths=0, label=g)
        # Explanatory trend line + Pearson correlation over all traces
        vals = trace_df["value"].to_numpy(dtype=float)
        fits = trace_df["fitness"].to_numpy(dtype=float)
        ok = np.isfinite(vals) & np.isfinite(fits)
        if ok.sum() >= 2 and np.ptp(vals[ok]) > 0:
            slope, intercept = np.polyfit(vals[ok], fits[ok], 1)
            xs = np.linspace(vals[ok].min(), vals[ok].max(), 50)
            ax.plot(xs, slope * xs + intercept, color="#222222",
                    linewidth=1.6, linestyle="--", zorder=6)
            if np.std(fits[ok]) > 0:
                r = float(np.corrcoef(vals[ok], fits[ok])[0, 1])
                ax.text(0.99, 0.04, f"Pearson r = {r:+.2f}",
                        transform=ax.transAxes, ha="right", va="bottom",
                        fontsize=FONT_ANNOT, color="#222222")
        ax.axvline(meta["median"], color="#555555", linestyle=":", linewidth=1.0)
        ax.set_xlabel(f"{attr} (candidate reason)", fontsize=FONT_LABEL)
    else:
        for gi, g in enumerate(groups):
            sub = trace_df[trace_df["group"] == g]
            if sub.empty:
                continue
            jitter = rng.uniform(-0.18, 0.18, size=len(sub))
            ax.scatter(gi + jitter, sub["fitness"], c=colors[g], s=14,
                       alpha=0.55, linewidths=0, label=g)
            ax.hlines(sub["fitness"].mean(), gi - 0.3, gi + 0.3,
                      colors="#222222", linewidth=2.0, zorder=6)
        ax.set_xticks(range(len(groups)))
        ax.set_xticklabels(groups, rotation=0, ha="center", fontsize=FONT_ANNOT)
        ax.set_xlabel(f"{attr} (candidate reason)", fontsize=FONT_LABEL)

    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(f"Per-trace Fitness vs {attr}", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, title="Sub-log",
              title_fontsize=FONT_ANNOT,
              loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task22_scatter_plot.svg"))


# ---------------------------------------------------------------------------
# Idiom 4: table — per-group conformance summary with deviation column
# ---------------------------------------------------------------------------

def task22_table(stats_df, attr, output_dir):
    cell_text = [
        [
            row["group"],
            str(int(row["n"])),
            f"{row['pct_conform']:.1f}%",
            f"{row['mean']:.4f}",
            f"{row['median']:.4f}",
            f"{row['std']:.4f}",
            f"{row['delta']:+.4f}",
        ]
        for _, row in stats_df.iterrows()
    ]
    fig_h = max(2.6, 1.2 + len(stats_df) * 0.55)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Sub-log (reason)", "N", "% Conform.", "Mean",
                    "Median", "Std Dev", "Δ vs overall"],
        bbox=[0.02, 0.08, 0.96, 0.82],
        col_widths=[0.34, 0.08, 0.12, 0.11, 0.11, 0.11, 0.13],
        font_size=10,
        scale_xy=(1, 1.4),
    )
    ax.set_title(f"Conformance Summary by {attr} (Δ explains the spread)",
                 fontsize=FONT_TITLE, pad=10)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task22_table.svg"))


# ---------------------------------------------------------------------------
# Idiom 5: table_bar_chart — summary table (left) + mean-fitness bars (right)
# ---------------------------------------------------------------------------

def task22_table_bar_chart(stats_df, groups, attr, output_dir):
    colors = _group_colors(groups)
    fig_h = max(4.5, len(groups) * 0.9 + 2.5)
    fig = plt.figure(figsize=(16, fig_h), layout="constrained")
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.4, 1.0], figure=fig)
    ax_tbl = fig.add_subplot(gs[0])
    ax_bar = fig.add_subplot(gs[1])

    ax_tbl.axis("off")
    cell_text = [
        [row["group"], str(int(row["n"])),
         f"{row['mean']:.4f}", f"{row['delta']:+.4f}", f"{row['pct_conform']:.1f}%"]
        for _, row in stats_df.iterrows()
    ]
    # Size the table to its row count (≈0.55"/row) and anchor it to the top so
    # rows stay the same height as standalone tables instead of stretching to
    # fill the tall combined figure.
    n_rows = len(cell_text) + 1
    tbl_frac = min(0.84, 0.55 * n_rows / fig_h)
    tbl_y0 = max(0.04, 0.86 - tbl_frac)
    make_table(
        ax_tbl,
        cell_text=cell_text,
        col_labels=["Sub-log (reason)", "N", "Mean Fitness", "Δ vs overall", "% Conform."],
        bbox=[0.02, tbl_y0, 0.96, tbl_frac],
        col_widths=[0.34, 0.12, 0.20, 0.18, 0.16],
        font_size=10,
        scale_xy=(1, 1.4),
    )
    ax_tbl.set_title(f"Reason Summary ({attr})", fontsize=FONT_TITLE, pad=10)

    means = [float(stats_df.loc[stats_df["group"] == g, "mean"].iloc[0])
             if (stats_df["group"] == g).any() else 0.0 for g in groups]
    stds  = [float(stats_df.loc[stats_df["group"] == g, "std"].iloc[0])
             if (stats_df["group"] == g).any() else 0.0 for g in groups]
    y = np.arange(len(groups))
    bars = ax_bar.barh(y, means, color=colors, edgecolor="white",
                       linewidth=0.6, height=0.5)
    ax_bar.errorbar(means, y, xerr=stds, fmt="none",
                    color="#555555", capsize=4, linewidth=1.0)
    for bar, val, std in zip(bars, means, stds):
        label_x = min(val + std + 0.025, 1.08)
        ax_bar.text(label_x, bar.get_y() + bar.get_height() / 2,
                    f"{val:.3f}", va="center", fontsize=FONT_ANNOT - 1, color="#444444")
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels(groups, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Mean Fitness (± 1 std)", fontsize=FONT_LABEL)
    ax_bar.set_xlim(0, 1.15)
    ax_bar.set_title("Mean Fitness by Reason", fontsize=FONT_TITLE, pad=10)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)
    ax_bar.set_ylim(len(groups) - 1 + 0.8, -0.8)

    save_svg(fig, os.path.join(output_dir, "task22_table_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 6: parallel_sets — reason value → fitness band (ribbon = trace count)
# ---------------------------------------------------------------------------

def task22_parallel_sets(trace_df, groups, attr, output_dir):
    counts = _band_counts(trace_df, groups)            # (n_groups × n_bands)
    band_names = [b[0] for b in _FITNESS_BANDS]
    # Keep only bands that occur in at least one group (avoid empty columns)
    keep = [bi for bi in range(len(band_names)) if counts[:, bi].sum() > 0]
    if not keep:
        render_empty_state_svg(os.path.join(output_dir, "task22_parallel_sets.svg"),
                               "Reason vs. Fitness Band", "No traces to display.")
        return
    matrix = counts[:, keep]
    right_labels = [band_names[bi] for bi in keep]
    right_colors = [_FITNESS_BANDS[bi][3] for bi in keep]

    group_n = {g: int((trace_df["group"] == g).sum()) for g in groups}
    left_labels = [f"{g}\n(n={group_n.get(g, 0)})" for g in groups]

    fig, ax = plt.subplots(figsize=(11, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(f"Parallel Sets: {attr} (reason) vs. Fitness Band",
                 fontsize=FONT_TITLE, pad=12)
    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=right_labels,
        matrix=matrix,
        left_colors=_group_colors(groups),
        right_colors=right_colors,
        left_title="Sub-log (reason)",
        right_title="Fitness band",
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task22_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Idiom 7: flow_chart_elaborate_table — violations on the BPMN model + reason table
# ---------------------------------------------------------------------------

def _violation_shade(rate: float) -> str:
    """Light grey (few) → dark grey (many) — platform heatmap scale."""
    rate = max(0.0, min(1.0, rate))
    lo, hi = 0xF0, 0x44  # #F0F0F0 → #444444
    v = int(round(lo + (hi - lo) * rate))
    return f"#{v:02X}{v:02X}{v:02X}"


def task22_flow_chart_elaborate_table(stats_df, act_viol, model_path, attr, output_dir):
    out_path = os.path.join(output_dir, "task22_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out_path, "Conformance on the Process Model",
                               "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001 — parse failure should not abort the task
        logger.warning(f"      task22: BPMN parse failed: {e}")
        render_empty_state_svg(out_path, "Conformance on the Process Model",
                               "Could not parse the BPMN model.")
        return

    max_v = max(act_viol.values()) if act_viol else 0

    def node_style_fn(eid, elem):
        kind = elem.get("kind", "task")
        name = elem.get("name", "")
        if kind == "task":
            rate = (act_viol.get(name, 0) / max_v) if max_v else 0.0
            fill = _violation_shade(rate)
            tc = "white" if int(fill[1:3], 16) < 0x99 else "#222222"
            return fill, "#777777", 1.2, tc
        if kind in {"exclusiveGateway", "parallelGateway"}:
            return "#FFFFFF", "#777777", 1.2, "#333333"
        return "#EFEFEF", "#777777", 1.5, "#333333"

    legend_items = [
        ("#F0F0F0", "#777777", 1.0, "Few / no violations"),
        ("#9A9A9A", "#777777", 1.0, "Some violations"),
        ("#444444", "#777777", 1.0, "Most violations"),
    ]

    table_cols = ["Sub-log (reason)", "N", "Mean Fitness", "Δ vs overall", "% Conform."]
    table_rows = [
        [str(row["group"]), str(int(row["n"])), f"{row['mean']:.4f}",
         f"{row['delta']:+.4f}", f"{row['pct_conform']:.1f}%"]
        for _, row in stats_df.iterrows()
    ]

    panels = [{
        "parsed": parsed,
        "node_style_fn": node_style_fn,
        "subtitle": "Activity shade: lighter = fewer violations · darker = more violations",
    }]
    compose_bpmn_panels(
        panels, out_path,
        title=f"Conformance Explained on the Model — by {attr}",
        legend_items=legend_items,
        table_rows=table_rows, table_cols=table_cols,
        legend_below_panels=True, legend_center=True,
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task22_bar_chart.svg",                  "Conformance Explained by Reason"),
    ("task22_stacked_bar.svg",                "Fitness Band Composition by Reason"),
    ("task22_scatter_plot.svg",               "Per-trace Fitness vs Reason"),
    ("task22_flow_chart_elaborate_table.svg", "Conformance on the Process Model"),
    ("task22_table.svg",                      "Conformance Summary by Reason"),
    ("task22_table_bar_chart.svg",            "Reason Summary & Mean Fitness"),
    ("task22_parallel_sets.svg",              "Reason vs. Fitness Band"),
]


def generate(log, fitness_df, alignments, output_dir: str,
             model_path: str = None, compare_attribute: str = "AMOUNT_REQ"):
    """Generate all Task ID 22 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 22 visualizations ---")

    groups, assignment, meta = split_by_attribute(log, compare_attribute)
    if groups is None:
        available = _available_case_attributes(log)
        logger.error(
            f"      task22: attribute '{compare_attribute}' not found in any trace. "
            f"Available case attributes: {available}"
        )
        for fname, title in _ALL_FNAMES_TITLES:
            render_empty_state_svg(
                os.path.join(output_dir, fname), title,
                f"Attribute '{compare_attribute}' not found in the event log.")
        return

    if meta["type"] == "numeric":
        logger.info(f"      -> numeric reason '{compare_attribute}', "
                    f"median split at {format_threshold(meta['median'])}")
    else:
        logger.info(f"      -> categorical reason '{compare_attribute}', "
                    f"{len(groups)} sub-logs")
    if meta["n_missing"]:
        logger.warning(f"      task22: {meta['n_missing']} traces without "
                       f"'{compare_attribute}' — excluded.")

    trace_df = _build_trace_df(fitness_df, assignment, meta)
    overall_mean = float(trace_df["fitness"].mean()) if len(trace_df) else 0.0
    stats_df = _group_stats(trace_df, groups, overall_mean)
    for _, row in stats_df.iterrows():
        g_ascii = str(row["group"]).replace("≤", "<=")
        logger.info(f"         {g_ascii:<30} n={int(row['n']):>6}  "
                    f"mean={row['mean']:.4f}  Δ={row['delta']:+.4f}  "
                    f"conform={row['pct_conform']:.1f}%")

    act_viol = _activity_violations(alignments)

    task22_bar_chart(trace_df, groups, compare_attribute, output_dir)
    task22_stacked_bar(trace_df, groups, compare_attribute, output_dir)
    task22_scatter_plot(trace_df, groups, meta, compare_attribute, output_dir)
    task22_flow_chart_elaborate_table(stats_df, act_viol, model_path, compare_attribute, output_dir)
    task22_table(stats_df, compare_attribute, output_dir)
    task22_table_bar_chart(stats_df, groups, compare_attribute, output_dir)
    task22_parallel_sets(trace_df, groups, compare_attribute, output_dir)
