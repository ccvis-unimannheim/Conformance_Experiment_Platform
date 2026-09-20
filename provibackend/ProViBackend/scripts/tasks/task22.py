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
and parallel_sets with a proportional conformant/deviating split. stacked_bar
was dropped: it read the fitness-band *distribution* per bucket rather than
its deviation from the overall mean, the one statistic every other idiom here
shares — a different analytical answer, not just a different rendering of the
same one.

bar_chart/table/parallel_sets are task22's own rendering (only the *data*
helpers — task20_trace_feature_dataframe, _default_attributes,
trace_response.attribute_panels — are reused), so a future change to task20's
own idioms cannot silently change task22's, and vice versa. parallel_sets in
particular used to delegate to task20's shared renderer, which assumed its
`rate` was always a 0–100 percentage; task22 passes it mean fitness on a 0–1
scale instead, so that reuse silently produced near-zero, meaningless ribbon
splits. It is now its own correctly-scaled implementation.

The admin picks the candidate attributes, and each is cut by its own type
unless a split strategy is set (see trace_features).

Public API:
    generate(log, fitness_df, alignments, output_dir, model_path=None,
             attribute_set=None, split_strategy=None, group_cap=None)
        attribute_set  – candidate reasons (attributes); empty = the
                         discovered default set.
        split_strategy – "binary" | "nominal_n" | "ordered_bins"; None picks
                         by each attribute's type
        group_cap      – most groups named before the rest become "Other"
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart", "table",
    "parallel_sets",
]


# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices.
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
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, auto_col_widths, draw_parallel_sets,
    render_empty_state_svg,
    GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GROUP_PALETTE = [GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER]

def _group_colors(groups: list) -> list:
    return [_GROUP_PALETTE[i % len(_GROUP_PALETTE)] for i in range(len(groups))]


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
    ("task22_table.svg",         "Conformance Summary by Reason"),
    ("task22_parallel_sets.svg", "Reason vs. Fitness Band"),
]


def generate(log, fitness_df, alignments, output_dir: str, model_path: str = None,
             attribute_set=None, split_strategy=None, group_cap=None):
    """Render Task ID 22 into output_dir.

    Own rendering — only the data helpers below are reused from task20. Each
    idiom draws mean fitness per bucket of every chosen attribute.
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
