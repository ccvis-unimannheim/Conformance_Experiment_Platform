"""
tasks/task15.py – Task 15: Overall process conformance annotation.

Goal: Explain · Means: Annotate · Characteristics: Reasons for process conformance
"How can the overall process conformance be explained? Requires prior knowledge
of potential explanations."

The table, bar chart, table + bar chart and parallel sets split the log by each
selected attribute and show mean fitness per bucket; the scatter plot and the
model idioms stay log-level (fitness distribution, per-activity violation
counts). Either way the analyst matches the observed patterns to their prior
knowledge.

Public API:
    generate(log, fitness_df, alignments, output_dir, model_path=None,
             attribute_set=None, split_strategy=None, group_cap=None,
             missing_policy="drop")
        attribute_set  – attributes the split idioms cut the log by; empty =
                         every groupable attribute of
                         this log (task20._default_attributes), minus org:resource
        split_strategy – "binary" | "nominal_n" | "ordered_bins"; None picks
                         by each attribute's type (see trace_features)
        group_cap      – most groups named before the rest become "Other"
        missing_policy – "drop" traces lacking the attribute, or keep them as
                         their own "Missing" group ("own_group")
"""

RUBRIC = (
    "A complete answer names the attribute group(s) whose conformance departs "
    "most from the rest and states the direction and rough size of the gap (e.g. "
    "'traces in the longest-duration bucket average 0.82 against 0.95 "
    "elsewhere'), then relates that to prior knowledge as an explanation. Award "
    "full marks for the correct group and direction with an approximate "
    "magnitude, partial marks for the correct group and direction alone, and no "
    "marks for the wrong direction or for a group the figure shows as flat. The "
    "figure supports association only: an answer stated as a cause is not worth "
    "more than one stated as a pattern."
)

import logging

logger = logging.getLogger(__name__)

IDIOMS = [
    "table", "bar_chart", "parallel_sets",
    # "scatter_plot",
    # "flow_chart_elaborate",
    # "flow_chart_elaborate_table",
    # "table_bar_chart",
]


# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "fitness"
SPLIT_STRATEGY = None  # admin chooses

_SPLIT_SUPTITLE = "Process Conformance by Candidate Attribute"

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
    parse_bpmn_model, render_bpmn_annotated, compose_bpmn_panels,
    alignment_pairs_to_rows,
    render_empty_state_svg,
    GREY_MED, GREY_DARK, GREY_LIGHT, GREY_LIGHTER,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_FIT_THRESHOLD = 0.8

_MOVE_TYPES = ["Model Move", "Log Move", "Mismatch Move"]
_MOVE_COLOR = {"Model Move": GREY_MED, "Log Move": GREY_DARK, "Mismatch Move": GREY_LIGHT}

_FITNESS_BANDS = [
    ("0.00–0.25", 0.00, 0.25, "#333333", "white"),
    ("0.25–0.50", 0.25, 0.50, "#777777", "white"),
    ("0.50–0.75", 0.50, 0.75, "#AAAAAA", "#333333"),
    ("0.75–1.00", 0.75, 1.01, "#D9D9D9", "#333333"),
]

_MISSING = {"-", "None", "(skip)", ""}


# ---------------------------------------------------------------------------
# Overall stats helper
# ---------------------------------------------------------------------------

def _overall_stats(fitness_df: pd.DataFrame, viol_df: pd.DataFrame) -> dict:
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    n = len(fits)
    mean_fit = float(fits.mean()) if n else 0.0
    total_viol = int(viol_df["count"].sum()) if not viol_df.empty else 0
    return {"n": n, "mean": mean_fit, "total_viol": total_viol}


def _stats_line(s: dict) -> str:
    return (f"n = {s['n']}   mean fitness = {s['mean']:.3f}   "
            f"total violations = {s['total_viol']}")


def _add_stats_footer(fig, s: dict):
    """Add overall stats as a small grey line at the bottom of a matplotlib figure."""
    fig.text(0.5, 0.01, _stats_line(s), ha="center", va="bottom",
             fontsize=FONT_ANNOT - 1.5, color="#888888",
             transform=fig.transFigure)


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _build_violation_df(alignments) -> pd.DataFrame:
    """Return DataFrame: activity, move_type, count — aggregated across all traces."""
    rows = []
    for result in alignments:
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            mt = step["moveType"]
            if mt == "Synchronous Move":
                continue
            activity = (step["model_move"] if mt == "Model Move" else step["log_move"])
            if not activity or str(activity) in _MISSING:
                continue
            rows.append({"activity": str(activity), "move_type": mt})
    if not rows:
        return pd.DataFrame(columns=["activity", "move_type", "count"])
    df = pd.DataFrame(rows)
    agg = (df.groupby(["activity", "move_type"])
             .size()
             .reset_index(name="count")
             .sort_values("count", ascending=False))
    return agg


def _activity_total_violations(viol_df: pd.DataFrame) -> dict:
    """activity -> total violation count across all move types."""
    if viol_df.empty:
        return {}
    return dict(viol_df.groupby("activity")["count"].sum())


def _fitness_band_counts(fitness_df: pd.DataFrame) -> list:
    """Return list of (label, count) for each fitness band."""
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    result = []
    for label, lo, hi, _, _ in _FITNESS_BANDS:
        n = int(((fits >= lo) & (fits < hi)).sum())
        result.append((label, n))
    return result


def _violation_shade(rate: float) -> str:
    rate = max(0.0, min(1.0, rate))
    lo, hi = 0xF0, 0x44
    v = int(round(lo + (hi - lo) * rate))
    return f"#{v:02X}{v:02X}{v:02X}"


# ---------------------------------------------------------------------------
# Idiom 1: table — per-activity violation counts by move type
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Idiom 2: bar_chart — total violations per activity (top N)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Idiom 3: scatter_plot — per-trace fitness (sorted by fitness)
# ---------------------------------------------------------------------------

def task15_scatter_plot(fitness_df, s, output_dir):
    out_path = os.path.join(output_dir, "task15_scatter_plot.svg")
    fits = fitness_df["fitness"].to_numpy(dtype=float)
    if len(fits) == 0:
        render_empty_state_svg(out_path, "Per-trace Fitness", "No data.")
        return

    sorted_fits = np.sort(fits)
    n = len(sorted_fits)
    x = np.arange(n)

    colors = np.where(sorted_fits >= _FIT_THRESHOLD, GREY_LIGHTER, GREY_DARK)

    fig, ax = plt.subplots(figsize=(12, 4.5))
    ax.scatter(x, sorted_fits, c=colors, s=6, alpha=0.55, linewidths=0)
    ax.axhline(_FIT_THRESHOLD, color="#555555", linestyle="--",
               linewidth=1.0, zorder=5)
    ax.text(n * 0.01, _FIT_THRESHOLD + 0.02,
            f"threshold = {_FIT_THRESHOLD:.1f}", fontsize=FONT_ANNOT - 1,
            color="#555555")

    n_conf = int((sorted_fits >= _FIT_THRESHOLD).sum())
    ax.text(0.99, 0.96,
            f"mean = {sorted_fits.mean():.3f}   conformant = {n_conf/n*100:.1f}%",
            transform=ax.transAxes, ha="right", va="top",
            fontsize=FONT_ANNOT, color="#444444")

    ax.set_xlabel("Trace (sorted by fitness)", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Per-trace Fitness Distribution", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    _add_stats_footer(fig, s)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 4: flow_chart_elaborate — BPMN annotated with violation frequency
# ---------------------------------------------------------------------------

def task15_flow_chart_elaborate(act_totals, s, model_path, output_dir):
    out_path = os.path.join(output_dir, "task15_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out_path, "Violations on Process Model",
                               "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task15: BPMN parse failed: {e}")
        render_empty_state_svg(out_path, "Violations on Process Model",
                               "Could not parse the BPMN model.")
        return

    max_v = max(act_totals.values()) if act_totals else 0

    def node_style_fn(eid, elem):
        kind = elem.get("kind", "task")
        name = elem.get("name", "")
        if kind == "task":
            rate = (act_totals.get(name, 0) / max_v) if max_v else 0.0
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
    render_bpmn_annotated(
        parsed, out_path,
        title="Violations on the Process Model",
        summary=("Activity shade: lighter = fewer violations · darker = more violations"
                 f"   |   {_stats_line(s)}"),
        node_style_fn=node_style_fn,
        legend_items=legend_items,
        legend_center=True,
    )


# ---------------------------------------------------------------------------
# Idiom 5: flow_chart_elaborate_table — BPMN + top-activity table
# ---------------------------------------------------------------------------

def task15_flow_chart_elaborate_table(act_totals, viol_df, s, model_path, output_dir):
    out_path = os.path.join(output_dir, "task15_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out_path, "Violations on Process Model & Summary",
                               "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task15: BPMN parse failed: {e}")
        render_empty_state_svg(out_path, "Violations on Process Model & Summary",
                               "Could not parse the BPMN model.")
        return

    max_v = max(act_totals.values()) if act_totals else 0

    def node_style_fn(eid, elem):
        kind = elem.get("kind", "task")
        name = elem.get("name", "")
        if kind == "task":
            rate = (act_totals.get(name, 0) / max_v) if max_v else 0.0
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

    top_acts = sorted(act_totals, key=lambda a: -act_totals[a])[:8]
    table_cols = ["Activity", "Total Violations"]
    table_rows = [[a, str(act_totals[a])] for a in top_acts]

    panels = [{
        "parsed": parsed,
        "node_style_fn": node_style_fn,
        "subtitle": "Activity shade: lighter = fewer violations · darker = more violations",
    }]
    compose_bpmn_panels(
        panels, out_path,
        title=f"Violations on the Process Model   |   {_stats_line(s)}",
        legend_items=legend_items,
        table_rows=table_rows, table_cols=table_cols,
        legend_below_panels=True, legend_center=True,
    )


# ---------------------------------------------------------------------------
# Idiom 7: table_bar_chart — violation summary table + fitness band bar
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Idiom 8: parallel_sets — fitness band → move type proportion
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task15_table.svg",                      "Mean Fitness by Attribute"),
    ("task15_bar_chart.svg",                  "Mean Fitness by Attribute"),
    ("task15_scatter_plot.svg",               "Per-trace Fitness Distribution"),
    ("task15_flow_chart_elaborate.svg",       "Violations on the Process Model"),
    ("task15_flow_chart_elaborate_table.svg", "Violations on the Process Model & Summary"),
    ("task15_tree.svg",                       "Violation Hierarchy"),
    ("task15_table_bar_chart.svg",            "Violation Type Summary & Fitness Bands"),
    ("task15_parallel_sets.svg",              "Fitness Band vs. Violation Move Type"),
]


def generate(log, fitness_df, alignments, output_dir: str, model_path: str = None,
             attribute_set=None, split_strategy=None, group_cap=None,
             missing_policy="drop"):
    """Render Task 15 into output_dir.

    The attribute-split idioms draw mean fitness per bucket of each chosen
    attribute through the shared panel renderers; the model and per-trace
    idioms stay log-level, having no per-bucket form.
    """
    import trace_response
    import tasks.task20 as task20

    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 15 visualizations ---")

    viol_df = _build_violation_df(alignments)
    # act_totals = _activity_total_violations(viol_df)  # only flow_chart_elaborate needed this
    s = _overall_stats(fitness_df, viol_df)
    logger.info(f"      -> {_stats_line(s)}")

    feat   = task20.task20_trace_feature_dataframe(log, alignments)
    attrs  = list(attribute_set) if attribute_set else task20._default_attributes(log, feat)
    panels = trace_response.attribute_panels(
        log, attrs, "fitness", fitness_per_trace=fitness_df["fitness"],
        strategy=split_strategy, cap=group_cap, missing_policy=missing_policy,
    )
    logger.info(f"      -> attributes: {attrs}  ({len(panels)} panel(s))")

    # Fitness is a 0–1 ratio, so it is drawn on its own scale with three
    # decimals rather than as a percentage: "0.98" invites a different reading
    # from "98%", which would suggest 98% of cases were fine.
    fmt = dict(suptitle=_SPLIT_SUPTITLE, value_label="Mean fitness",
               value_fmt="{:.3f}", value_max=1.0)
    task20.task20_table(panels, output_dir, filename="task15_table.svg", **fmt)
    task20.task20_bar_chart(panels, output_dir, filename="task15_bar_chart.svg", **fmt)
    # task20.task20_table_bar_chart(panels, output_dir,
    #                               filename="task15_table_bar_chart.svg", **fmt)
    task20.task20_parallel_sets(panels, output_dir,
                                filename="task15_parallel_sets.svg", **fmt)

    # task15_scatter_plot(fitness_df, s, output_dir)
    # task15_flow_chart_elaborate(act_totals, s, model_path, output_dir)
    # task15_flow_chart_elaborate_table(act_totals, viol_df, s, model_path, output_dir)
