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

RUBRIC = (
    "A complete answer says which of the supplied candidate reasons relates to "
    "conformance, in which direction, and how strongly — reading the trend, the "
    "correlation, or each group's deviation from the overall mean — and, where "
    "the model idiom is shown, where conformance breaks down. Award full marks "
    "for the correct reason and direction with an approximate magnitude, partial "
    "marks for the correct direction alone, and no marks for the wrong direction "
    "or for a candidate the figures show as unrelated."
)

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "stacked_bar", "scatter_plot",
          "flow_chart_elaborate_table", "table", "table_bar_chart",
          "parallel_sets"]


# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "fitness"
SPLIT_STRATEGY = None  # admin chooses

_SPLIT_SUPTITLE = "Conformance Explained by Candidate Attribute"

import trace_features

def validate_params(log, params) -> list:
    return trace_features.validate_attribute_class(params, multi=True)


PARAM_SPEC = [
    *trace_features.attribute_params(),
    *trace_features.split_params_for(),
]
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

# ---------------------------------------------------------------------------
# Idiom 5: table_bar_chart — summary table (left) + mean-fitness bars (right)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Idiom 6: parallel_sets — reason value → fitness band (ribbon = trace count)
# ---------------------------------------------------------------------------

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

    table_cols = ["Sub-log (reason)", "N", "Mean Fitness", "Δ vs overall"]
    table_rows = [
        [str(row["group"]), str(int(row["n"])), f"{row['mean']:.4f}",
         f"{row['delta']:+.4f}"]
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


def generate(log, fitness_df, alignments, output_dir: str, model_path: str = None,
             attribute_set=None, split_strategy=None, group_cap=None):
    """Render Task ID 22 into output_dir.

    The panel idioms draw mean fitness per bucket of every chosen attribute,
    through the renderers task20 also uses. The distribution idioms need a
    single grouping, so they use the first attribute selected and name it in
    their own titles.
    """
    import trace_response
    import tasks.task20 as task20

    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 22 visualizations ---")

    feat = task20.task20_trace_feature_dataframe(log, alignments)
    attrs = list(attribute_set) if attribute_set else task20._default_attributes(log, feat)
    panels = trace_response.attribute_panels(
        log, attrs, "fitness", fitness_per_trace=fitness_df["fitness"],
        strategy=split_strategy, cap=group_cap,
    )
    logger.info(f"      -> attributes: {attrs}  ({len(panels)} panel(s))")

    fmt = dict(suptitle=_SPLIT_SUPTITLE, value_label="Mean fitness",
               value_fmt="{:.3f}", value_max=1.0)
    task20.task20_bar_chart(panels, output_dir, filename="task22_bar_chart.svg", **fmt)
    task20.task20_table(panels, output_dir, filename="task22_table.svg", **fmt)
    task20.task20_table_bar_chart(panels, output_dir,
                                  filename="task22_table_bar_chart.svg", **fmt)
    task20.task20_parallel_sets(panels, output_dir,
                                filename="task22_parallel_sets.svg", **fmt)

    compare_attribute = attrs[0] if attrs else ""
    groups, assignment, meta = split_by_attribute(
        log, compare_attribute, max_groups=group_cap or MAX_CATEGORICAL_GROUPS)
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
                    f"mean={row['mean']:.4f}  Δ={row['delta']:+.4f}")

    act_viol = _activity_violations(alignments)

    # One grouping only: these read a distribution, not a per-bucket summary.
    task22_stacked_bar(trace_df, groups, compare_attribute, output_dir)
    task22_scatter_plot(trace_df, groups, meta, compare_attribute, output_dir)
    task22_flow_chart_elaborate_table(stats_df, act_viol, model_path, compare_attribute, output_dir)
