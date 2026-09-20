"""
tasks/task22.py – Task ID 22: Explain / Summarize / Reasons for process conformance.

How can the overall process conformance be explained for different traces? The
analyst supplies one or more *candidate reasons* — case-level data attributes —
and we relate each trace's fitness to those reasons, summarising the explanation
per sub-log and presenting it (among others) on the process model.

Reason-first framing distinguishes task22 from task33 (which merely *compares*
conformance between attribute values): here fitness is the explained variable,
the attribute is the explanatory one, and every idiom below states the
deviation from the log's overall mean fitness, not just the raw per-bucket
value — bar_chart with a reference line, table with a "Δ vs Overall" column,
and the BPMN model localises *where* conformance breaks.

bar_chart/table/parallel_sets are task22's own rendering (only the *data*
helpers — task20_trace_feature_dataframe, _default_attributes,
trace_response.attribute_panels — are reused), so a future change to task20's
own idioms cannot silently change task22's, and vice versa. parallel_sets in
particular used to delegate to task20's shared renderer, which assumed its
`rate` was always a 0–100 percentage; task22 passes it mean fitness on a 0–1
scale instead, so that reuse silently produced near-zero, meaningless ribbon
splits. It is now its own correctly-scaled implementation.

Building blocks (sub-log split, violation extraction, annotated BPMN) are reused
from task30/shared, so a new dataset flows through unchanged: the admin picks the
candidate attributes, and each is cut by its own type unless a split strategy is
set (see trace_features).

Public API:
    generate(log, fitness_df, alignments, output_dir, model_path=None,
             attribute_set=None, split_strategy=None, group_cap=None)
        attribute_set  – candidate reasons (attributes); empty = the
                         discovered default set. The distribution idioms use
                         only the first one.
        split_strategy – "binary" | "nominal_n" | "ordered_bins"; None picks
                         by each attribute's type
        group_cap      – most groups named before the rest become "Other"
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart", "stacked_bar", "table",
    "parallel_sets",
]


# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "fitness"
SPLIT_STRATEGY = None  # admin chooses

_SPLIT_SUPTITLE = "Conformance Explained by Candidate Attribute"

import trace_features

def validate_params(log, params) -> list:
    return trace_features.validate_attribute_class(
        params, multi=True, levels=trace_features.TRACE_COMPARING_LEVELS)


# No log level: this task compares traces to each other, and a log-level
# attribute has the same value for all of them.
PARAM_SPEC = [*trace_features.grouping_params(
    levels=trace_features.TRACE_COMPARING_LEVELS)]
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, auto_col_widths, draw_parallel_sets,
    render_empty_state_svg, format_threshold,
    GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse the proven sub-log split + attribute helpers from task30.
from tasks.task30 import (split_by_attribute, _available_case_attributes,
                          MAX_CATEGORICAL_GROUPS)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GROUP_PALETTE = [GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER]

# Fitness bands: (label, lo, hi, fill_color, text_color) — shared look with task33
_FITNESS_BANDS = [
    ("0.00–0.25", 0.00, 0.25, "#333333", "white"),
    ("0.25–0.50", 0.25, 0.50, "#777777", "white"),
    ("0.50–0.75", 0.50, 0.75, "#AAAAAA", "#333333"),
    ("0.75–1.00", 0.75, 1.01, "#D9D9D9", "#333333"),
]

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
    """Per sub-log fitness summary plus this task's explanatory deviation."""
    import trace_response

    stats = trace_response.fitness_stats(
        trace_df["fitness"], trace_df["group"], groups,
    )
    return pd.DataFrame({
        "group":       stats["group"],
        "n":           stats["n"],
        "mean":        stats["mean"],
        "median":      stats["median"],
        "std":         stats["std"],
        "delta":       stats["mean"] - overall_mean,   # explanatory deviation
    })


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


# ---------------------------------------------------------------------------
# Idiom 1: bar_chart — mean fitness per reason group, vs. the overall mean
# ---------------------------------------------------------------------------

def task22_bar_chart(panels, overall_mean, output_dir):
    """One panel per candidate attribute: mean fitness per bucket, with a
    dashed reference line at the log's overall mean fitness so a bucket's
    deviation reads directly off the bar height instead of a remembered
    baseline."""
    path = os.path.join(output_dir, "task22_bar_chart.svg")
    if not panels:
        render_empty_state_svg(path, "Conformance Explained by Reason",
                               "No candidate attribute could be bucketed.")
        return
    ncols = len(panels)
    fig, axes = plt.subplots(1, ncols, figsize=(max(5.0, ncols * 4.2), 5.0), squeeze=False)
    for ax, (m, (labels, rates, _counts)) in zip(axes[0], panels):
        pos = np.arange(len(labels))
        ax.bar(pos, rates, color=GREY_MED, edgecolor="white")
        for p, rate in zip(pos, rates):
            if rate + 0.08 > 1.0:
                ax.text(p, rate - 0.015, f"{rate:.3f}", ha="center", va="top",
                        fontsize=FONT_ANNOT - 1, color="white")
            else:
                ax.text(p, rate + 0.015, f"{rate:.3f}", ha="center", va="bottom",
                        fontsize=FONT_ANNOT - 1, color="#333333")
        ax.axhline(overall_mean, color="#555555", linestyle="--", linewidth=1.2,
                  alpha=0.85, zorder=2, label=f"Overall mean: {overall_mean:.3f}")
        ax.set_xticks(pos)
        ax.set_xticklabels(labels, fontsize=FONT_ANNOT - 1, rotation=20, ha="right")
        ax.set_title(m["label"], fontsize=FONT_LABEL)
        ax.set_ylim(0, 1.0)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.45)
        ax.set_axisbelow(True)
    axes[0][0].set_ylabel("Mean fitness", fontsize=FONT_LABEL)
    fig.legend(*axes[0][0].get_legend_handles_labels(),
              loc="lower center", bbox_to_anchor=(0.5, -0.06),
              frameon=False, fontsize=FONT_ANNOT)
    fig.suptitle(_SPLIT_SUPTITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2, rect=[0, 0.04, 1, 1])
    save_svg(fig, path)


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

def task22_table(panels, overall_mean, output_dir):
    """One section per candidate attribute: Attribute Value | Mean Fitness |
    Δ vs Overall."""
    path = os.path.join(output_dir, "task22_table.svg")
    if not panels:
        render_empty_state_svg(path, "Conformance Summary by Reason",
                               "No candidate attribute could be bucketed.")
        return
    col_labels = ["Attribute Value", "Mean Fitness", "Δ vs Overall"]
    height_ratios = [max(1, len(labels)) for (_m, (labels, _r, _c)) in panels]
    fig_h = max(4.0, 1.0 + sum(height_ratios) * 0.42 + len(panels) * 0.55)
    fig = plt.figure(figsize=(9, fig_h))
    gs = gridspec.GridSpec(len(panels), 1, height_ratios=height_ratios, hspace=0.7)
    for i, (m, (labels, rates, _counts)) in enumerate(panels):
        ax = fig.add_subplot(gs[i]); ax.axis("off")
        cell_text = [
            [lab, f"{rate:.3f}",
             ("+" if rate >= overall_mean else "-") + f"{abs(rate - overall_mean):.3f}"]
            for lab, rate in zip(labels, rates)
        ]
        make_table(ax, cell_text=cell_text, col_labels=col_labels,
                  bbox=[0.04, 0.02, 0.92, 0.82],
                  col_widths=auto_col_widths(col_labels, cell_text),
                  font_size=10, cell_pad=0.09)
        ax.set_title(m["label"], fontsize=FONT_TITLE, pad=4, loc="left")
    fig.suptitle(_SPLIT_SUPTITLE, fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Idiom 6: parallel_sets — reason value → conformant/deviating share (≈),
# derived from the bucket's mean fitness (ribbon = trace count)
# ---------------------------------------------------------------------------

def task22_parallel_sets(panels, output_dir):
    """One flow per candidate attribute: bucket → conformant/deviating share
    (≈), ribbon = #traces.

    The bucket's mean fitness is not a literal per-trace count, so there is no
    exact per-trace split to draw — only the aggregate mean. This splits each
    bucket's ribbon in that same proportion (a bucket with mean 0.85 sends
    ~85% of its traces to "Conformant share"): an honest visualisation of the
    mean, labelled "(≈)" because it approximates the underlying distribution
    rather than reconstructing it exactly."""
    path = os.path.join(output_dir, "task22_parallel_sets.svg")
    if not panels:
        render_empty_state_svg(path, "Reason vs. Fitness Band",
                               "No candidate attribute could be bucketed.")
        return
    ncols = len(panels)
    max_rows = max(len(labels) for (_m, (labels, _r, _c)) in panels)
    fig_h = max(5.0, max_rows * 0.75 + 2.5)
    fig, axes = plt.subplots(1, ncols, figsize=(max(7.0, ncols * 5.8), fig_h), squeeze=False)
    for ax, (m, (labels, rates, counts)) in zip(axes[0], panels):
        ax.axis("off")
        mat = np.zeros((len(labels), 2))
        for i, (rate, cnt) in enumerate(zip(rates, counts)):
            conform = round(rate * cnt)   # rate is already 0..1 (mean fitness)
            mat[i, 0] = conform
            mat[i, 1] = cnt - conform
        left_labels = [f"{lab}  ({rate:.3f} mean fitness)" for lab, rate in zip(labels, rates)]
        right_labels = ["Conformant share (≈)", "Deviating share (≈)"]
        left_colors = [_GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i in range(len(labels))]
        draw_parallel_sets(
            ax, left_labels, right_labels, mat, left_colors,
            right_colors=[GREY_DARK, GREY_LIGHTER],
            left_title=m["label"], right_title="Fitness (≈)",
            label_min_frac=0.0,
            emphasize_left_head=True,
        )
    fig.suptitle(_SPLIT_SUPTITLE, fontsize=FONT_TITLE, y=0.98)
    fig.subplots_adjust(top=0.84)
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task22_bar_chart.svg",     "Conformance Explained by Reason"),
    ("task22_stacked_bar.svg",   "Fitness Band Composition by Reason"),
    ("task22_table.svg",         "Conformance Summary by Reason"),
    ("task22_parallel_sets.svg", "Reason vs. Fitness Band"),
]


def generate(log, fitness_df, alignments, output_dir: str, model_path: str = None,
             attribute_set=None, split_strategy=None, group_cap=None):
    """Render Task ID 22 into output_dir.

    The panel idioms draw mean fitness per bucket of every chosen attribute
    (own rendering — only the data helpers below are reused from task20). The
    distribution idioms need a single grouping, so they use the first
    attribute selected and name it in their own titles.
    """
    import trace_response
    import tasks.task20 as task20   # data helpers only — see module docstring

    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 22 visualizations ---")

    overall_mean = float(fitness_df["fitness"].mean()) if len(fitness_df) else 0.0

    feat = task20.task20_trace_feature_dataframe(log, alignments)
    attrs = list(attribute_set) if attribute_set else task20._default_attributes(log, feat)
    panels = trace_response.attribute_panels(
        log, attrs, "fitness", fitness_per_trace=fitness_df["fitness"],
        strategy=split_strategy, cap=group_cap,
    )
    logger.info(f"      -> attributes: {attrs}  ({len(panels)} panel(s))  "
                f"overall mean fitness={overall_mean:.3f}")

    task22_bar_chart(panels, overall_mean, output_dir)
    task22_table(panels, overall_mean, output_dir)
    task22_parallel_sets(panels, output_dir)

    compare_attribute = attrs[0] if attrs else ""
    groups, assignment, meta = split_by_attribute(
        log, compare_attribute, max_groups=group_cap or MAX_CATEGORICAL_GROUPS,
        strategy=split_strategy)
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
    # Scoped to this attribute's own non-missing traces — deliberately not the
    # same `overall_mean` bar_chart/table use above, which is the whole log's.
    attr_overall_mean = float(trace_df["fitness"].mean()) if len(trace_df) else 0.0
    stats_df = _group_stats(trace_df, groups, attr_overall_mean)
    for _, row in stats_df.iterrows():
        g_ascii = str(row["group"]).replace("≤", "<=")
        logger.info(f"         {g_ascii:<30} n={int(row['n']):>6}  "
                    f"mean={row['mean']:.4f}  Δ={row['delta']:+.4f}")

    # One grouping only: this reads a distribution, not a per-bucket summary.
    task22_stacked_bar(trace_df, groups, compare_attribute, output_dir)
