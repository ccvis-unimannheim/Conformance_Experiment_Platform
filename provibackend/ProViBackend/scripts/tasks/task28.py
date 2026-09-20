"""
tasks/task28.py – task28: where exactly the process execution differs from the
guideline.

Trace level: the alignment of the chosen traces (see trace_ids / trace_pick_rule
below), drawn by task09's trace-alignment figures in the chosen perspective
(control flow, data or resource) — the same pictures task09 shows. Log level: an
exploratory overview of the deviations across the whole log.

Public API:
    generate(alignments, model_path, output_dir, log=None,
             perspective="control-flow", trace_ids=None,
             trace_pick_rule="first_nonconformant", trace_count=1,
             data_attribute="", conformant_values=(),
             conformant_resources=(), scoped_activity="")
        perspective          – "control-flow" | "data" | "resource": what the
                               shown traces are checked against
        trace_ids            – traces to show; empty = chosen by
                               trace_pick_rule, trace_count of them (see
                               trace_alignment.PICK_RULES)
        data_attribute,
        conformant_values    – the data rule (perspective "data")
        conformant_resources,
        scoped_activity      – the resource rule (perspective "resource")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_basic", "flow_chart_elaborate", "table", "bar_chart",
          "stacked_bar", "matrix", "heatmap"]

import trace_alignment

#: Same question as task09 — where does the execution differ from the guideline,
#: and in which perspective — explored rather than presented, so the parameters
#: are task09's. The difference is not a parameter: task28 does not hand the
#: participant the violations, which is HIGHLIGHT_VIOLATIONS below.
PARAM_SPEC = [
    trace_alignment.PERSPECTIVE_PARAM,
    *trace_alignment.selection_params(
        rules=["first_nonconformant", "worst_fitness", "violation_gap",
               "most_frequent_variants"],
        default_rule="first_nonconformant",
        count_default=1, count_min=1, count_max=4,
    ),
    {**trace_alignment.VIOLATION_PATTERN_PARAM,
     "visible_if": {**trace_alignment.VIOLATION_PATTERN_PARAM["visible_if"],
                    "perspective": "control-flow"}},
    trace_alignment.DATA_ATTRIBUTE_PARAM,
    trace_alignment.CONFORMANT_VALUES_PARAM,
    trace_alignment.CONFORMANT_RESOURCES_PARAM,
    trace_alignment.SCOPED_ACTIVITY_PARAM,
]

#: Explore · Identify: the means to find the violations are provided, the
#: violations themselves are not pointed out. A task property, not an admin
#: choice — the wording of the task fixes it.
HIGHLIGHT_VIOLATIONS = False


def validate_params(log, params) -> list:
    return (trace_alignment.validate_selection(log, params, min_traces=1, max_traces=4)
            + trace_alignment.validate_perspective(log, params))

import html
import math
import os
import xml.etree.ElementTree as ET

import numpy as np

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap, to_hex

from shared import (
    save_svg, make_table, GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    chevron_figure_width, chevron_nodes_from_alignment_rows, draw_chevron_strip,
    alignment_pairs_to_rows,
    draw_value_heatmap, draw_rate_matrix, CIVIDIS_R,
    parse_bpmn_model, render_bpmn_annotated,
    render_empty_state_svg, contrasting_text_color,
)


# Task 2 – Location / alignment visualizations (representative trace)
# ---------------------------------------------------------------------------

# Task 2 helpers
TASK28_HEADER_COLOR = GREY_DARK
TASK28_SYNC_ROW_COLOR = GREY_LIGHTER
TASK28_MODEL_ROW_COLOR = GREY_LIGHT
TASK28_LOG_ROW_COLOR = GREY_MED
TASK28_TABLE_EDGE_COLOR = "#FFFFFF"
TASK28_TABLE_COL_LABELS = ["Step", "Log Move", "Model Move", "Status"]
TASK28_TABLE_COL_WIDTHS = [0.065, 0.375, 0.375, 0.185]


def pick_representative_trace_index(alignments):
    """First trace with fitness < 1, else 0."""
    for i, result in enumerate(alignments):
        if float(result.get("fitness", 1.0)) < 1.0 - 1e-9:
            return i
    return 0


def build_task28_context(alignments):
    """Pick representative trace and build row list; returns None if no usable alignment."""
    if not alignments:
        return None
    idx = pick_representative_trace_index(alignments)
    result = alignments[idx]
    alignment = result.get("alignment")
    if not alignment:
        return None
    rows = alignment_pairs_to_rows(alignment)
    if not rows:
        return None
    return {
        "trace_index": idx,
        # "Trace 1", because this path draws exactly one trace. It used to be
        # the trace's position in the whole log — "Trace 4818" — while the table
        # beside it numbers the traces it shows from one, the way
        # trace_alignment.trace_records does for every task in this class.
        "trace_label": "Trace 1",
        "fitness": float(result.get("fitness", 0.0)),
        "cost": result.get("cost"),
        "rows": rows,
    }


def _task28_format_cost(cost):
    """Format PM4Py alignment cost for the table subtitle."""
    if cost is None:
        return None
    try:
        cost_num = float(cost)
    except (TypeError, ValueError):
        return str(cost)
    if abs(cost_num - round(cost_num)) < 1e-9:
        return str(int(round(cost_num)))
    return f"{cost_num:.4f}".rstrip("0").rstrip(".")


def _task28_status_color(move_type: str) -> str:
    """Map alignment move type to the reference table row color."""
    if move_type == "Model Move":
        return TASK28_MODEL_ROW_COLOR
    if move_type == "Log Move":
        return TASK28_LOG_ROW_COLOR
    return TASK28_SYNC_ROW_COLOR


def _task28_table_cell_text(rows):
    """Return table cells in the reference Step | Log | Model | Status order."""
    return [
        [str(row["step"]), str(row["log_move"]), str(row["model_move"]), str(row["status"])]
        for row in rows
    ]


def _task28_alignment_table_height(row_count: int, *, compact: bool = False) -> float:
    """Figure height that keeps table rows close to the reference density."""
    base = 3.8 if compact else 4.7
    row_h = 0.27 if compact else 0.31
    return max(base, base + row_count * row_h)


def _draw_task28_alignment_table(ax, rows, *, bbox, font_size=10.5, scale_y=1.4):
    """Standard zebra table, aligned with the platform's other tables: dark header,
    alternating white/light-grey rows, no per-status colour."""
    return make_table(
        ax,
        cell_text=_task28_table_cell_text(rows),
        col_labels=TASK28_TABLE_COL_LABELS,
        bbox=bbox,
        col_widths=TASK28_TABLE_COL_WIDTHS,
        font_size=font_size,
        scale_xy=(1, scale_y),
    )


def _add_task28_table_heading(fig, ctx, *, x=0.055, y=0.86, compact=False):
    """Add the trace title and alignment summary above the table."""
    fig.text(
        x,
        y,
        ctx["trace_label"],
        ha="left",
        va="top",
        fontsize=FONT_TITLE,
        color="#111111",
    )

    cost_text = _task28_format_cost(ctx.get("cost"))
    meta_parts = [f"Fitness: {ctx['fitness']:.4f}"]
    if cost_text is not None:
        meta_parts.append(f"Cost: {cost_text}")
    fig.text(
        x,
        y - (0.055 if compact else 0.065),
        "   |   ".join(meta_parts),
        ha="left",
        va="top",
        fontsize=FONT_ANNOT,
        color="#6C6C6C",
    )


# Chevron strip primitives moved to shared.py (chevron_layout, draw_chevron_strip,
# chevron_figure_width, chevron_nodes_from_alignment_rows) so task27 can reuse them.

def _task28_move_legend_elements():
    return [
        mpatches.Patch(facecolor=GREY_LIGHTER, edgecolor="black", linewidth=0.75, label="Synchronous move (Conform)"),
        mpatches.Patch(facecolor=GREY_MED, edgecolor="black", linewidth=0.75, label="Model move only"),
        mpatches.Patch(facecolor=GREY_DARK, edgecolor="black", linewidth=0.75, label="Log move only"),
    ]


# Task 2 visualizations
def task28_alignment_table(ctx: dict, output_dir: str):
    """Alignment detail table for representative trace."""
    rows = ctx["rows"]

    fig_h = _task28_alignment_table_height(len(rows))
    fig, ax = plt.subplots(figsize=(15.8, fig_h))
    ax.axis("off")
    _add_task28_table_heading(fig, ctx, x=0.06, y=0.86)
    _draw_task28_alignment_table(
        ax,
        rows,
        bbox=[0.045, 0.08, 0.91, 0.58],
        font_size=10.5,
    )
    fig.subplots_adjust(left=0.025, right=0.985, top=0.94, bottom=0.05)
    save_svg(fig, os.path.join(output_dir, "task28_table.svg"))


def task28_flow_chart_basic(ctx: dict, output_dir: str):
    """Chevron diagram (reference layout): titled flow strip + bottom move-type legend."""
    nodes = chevron_nodes_from_alignment_rows(ctx["rows"])

    fig_w = chevron_figure_width(nodes)
    fig_h = 4.15
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_chevron_strip(ax, nodes, fontsize=10)
    fig.subplots_adjust(left=0.045, right=0.985, top=0.55, bottom=0.28)
    fig.text(
        0.045,
        0.90,
        "Trace Alignment",
        ha="left",
        va="top",
        fontsize=FONT_TITLE,
        color="black",
    )
    fig.text(
        0.045,
        0.58,
        ctx["trace_label"],
        ha="left",
        va="center",
        fontsize=FONT_TITLE,
        color="#222222",
    )
    fig.legend(
        handles=_task28_move_legend_elements(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.075),
        ncol=3,
        fontsize=FONT_ANNOT,
        frameon=True,
        fancybox=False,
        edgecolor="#cccccc",
    )
    save_svg(fig, os.path.join(output_dir, "task28_flow_chart_basic.svg"))


_MISSING_MOVE_TOKENS = {"-", "None", "(skip)", ">>", ""}

def _trace_act_status(rows):
    """activity -> alignment status for one trace. Deviations override 'conform'."""
    status = {}
    for r in rows:
        mt = r["moveType"]
        if mt == "Synchronous Move":
            name = r["log_move"] if str(r["log_move"]) not in _MISSING_MOVE_TOKENS else r["model_move"]
            status.setdefault(str(name), "conform")
        elif mt == "Model Move":
            status[str(r["model_move"])] = "skipped"
        elif mt == "Log Move":
            status[str(r["log_move"])] = "extra"
    return status


def task28_flow_chart_elaborate_bpmn(ctx: dict, model_path: str, output_dir: str):
    """Annotate the BPMN model with this trace's alignment status, using the shared
    renderer (clean arrows + a legend whose colours match the node fills)."""
    out = os.path.join(output_dir, "task28_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Trace Alignment on the Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"      task28: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Trace Alignment on the Model", "Could not parse the BPMN model.")
        return

    status = _trace_act_status(ctx["rows"])
    fills = {"conform": GREY_LIGHTER, "skipped": GREY_LIGHT, "extra": GREY_DARK}

    def node_style_fn(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task" and name in status:
            fill = fills[status[name]]
            tc = contrasting_text_color(fill)
            return fill, GREY_DARK, 2.5, tc
        if elem.get("kind") == "task":
            return "white", GREY_MED, 1.5, GREY_DARK
        return "white", GREY_MED, 2, GREY_DARK

    legend = [
        (GREY_LIGHTER, GREY_DARK, 1.0, "Synchronous move"),
        (GREY_LIGHT,   GREY_DARK, 1.0, "Model move"),
        (GREY_DARK,    GREY_DARK, 1.0, "Log move"),
        ("white",      GREY_MED,  1.0, "Not in this trace"),
    ]
    render_bpmn_annotated(
        parsed, out,
        title=f"Trace Alignment on the Model — {ctx['trace_label']} "
              f"(fitness {ctx['fitness']:.4f})",
        summary="Task shade = this trace's alignment status; border colour matches the legend.",
        node_style_fn=node_style_fn, legend_items=legend)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

# ===========================================================================
# LOG-LEVEL EXPLORATORY IDIOMS (Explore · Identify)
#
# task28 is "Explore · Identify · Guideline violations": deviations are NOT
# pre-summarised for the analyst (that is task29's "Present" job). These overview
# idioms present the NEUTRAL facts — how often each deviation kind occurs, where,
# and which traces carry many — so the analyst scans, spots, and then drills into
# a single trace with the chevron / table / BPMN idioms above.
#
# A "deviation" is the conformance algorithm's own classification, not a value
# judgment: Model Move (activity skipped) or Log Move (extra activity).
# ===========================================================================

_BAR_WIDTH_TOTAL = 0.76
#: One title over all seven idioms. They used to carry four different ones —
#: task04's per-figure defaults on the trio, and on the aggregates a name for the
#: whole log ("Where Does the Log Deviate?", "top-12 activities") that stopped
#: being true when they moved onto the chosen traces.
_DEVIATION_TITLE = "Where the Shown Traces Differ from the Guideline"
MOVE_TYPES = ["Model Move", "Log Move"]


def _step_activity(row):
    """The activity a deviating step names: the side that carries a label."""
    return (row.get("model_move") if row.get("moveType") == "Model Move"
            else row.get("log_move"))


def _category(key) -> str:
    """"Ship Order (Model Move)" — where the step is, and what kind it is."""
    activity, move_type = key
    return f"{activity} ({move_type})"


def _wrap_category(key, width: int = 14) -> str:
    """The same label over several lines, the move type on its own."""
    activity, move_type = key
    words, lines, cur = str(activity).split(), [], ""
    for w in words:
        cand = f"{cur} {w}".strip()
        if len(cand) > width and cur:
            lines.append(cur)
            cur = w
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return "\n".join(lines) + f"\n({move_type})"


def _trace_colors(n: int) -> list:
    """One colour per shown trace, navy through cividis's yellow end."""
    return [to_hex(CIVIDIS_R(0.12 + 0.76 * i / max(n - 1, 1))) for i in range(n)]


def _selected_step_payload(records):
    """(keys, trace_labels, counts) over the traces the admin chose.

    A key is one deviating step's ``(activity, move type)`` {EMD} where it happened
    and what kind it was, which is what this task asks. ``counts`` is
    (n_keys {X} n_traces).

    The four aggregate idioms used to read ``_dev_df(alignments)``: the whole
    log's deviation patterns, ranked, capped at the top 12, and untouched by the
    trace selection. So the chevron, BPMN and table pinpointed the chosen traces
    while the bar chart beside them summarised thirteen thousand others. They
    also ranked by frequency, and this task does not ask how often {EMD} it asks
    where exactly, and how. Over one to four traces the cells hold 0, 1 or 2, so
    the number stops being a ranking and the figure reads as a location.
    """
    keys, seen = [], set()
    for rec in records:
        for r in rec.get("rows", []):
            mt = r.get("moveType")
            act = _step_activity(r)
            if mt not in MOVE_TYPES or not act or act in (">>", "-"):
                continue
            if (act, mt) not in seen:
                seen.add((act, mt))
                keys.append((act, mt))

    labels = [rec.get("label", f"Trace {i + 1}") for i, rec in enumerate(records)]
    at = {k: i for i, k in enumerate(keys)}
    counts = np.zeros((len(keys), len(records)), dtype=float)
    for ti, rec in enumerate(records):
        for r in rec.get("rows", []):
            i = at.get((_step_activity(r), r.get("moveType")))
            if i is not None:
                counts[i, ti] += 1
    return keys, labels, counts


def _records_from_context(ctx):
    """The fallback path's single trace, in the record shape."""
    return [] if ctx is None else [{"label": ctx["trace_label"], "rows": ctx["rows"]}]


# --- Idiom: bar_chart — the deviating steps of the chosen traces -----------

def task28_bar_chart(records, output_dir):
    """Grouped bars: one bar per chosen trace, per deviating step."""
    out = os.path.join(output_dir, "task28_bar_chart.svg")
    keys, labels, counts = _selected_step_payload(records)
    if not keys or not counts.any():
        render_empty_state_svg(out, _DEVIATION_TITLE, "No deviations found.")
        return

    colors = _trace_colors(len(labels))
    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(max(8.0, len(keys) * 1.35 + 2.0), 5.4))
    ax.set_facecolor("#fafbfc")

    bw = _BAR_WIDTH_TOTAL / max(len(labels), 1)
    offsets = (np.arange(len(labels)) - (len(labels) - 1) / 2.0) * bw
    vmax = float(counts.max())
    for ti, label in enumerate(labels):
        ax.bar(x + offsets[ti], counts[:, ti], bw * 0.92, color=colors[ti],
               edgecolor="white", linewidth=0.6, label=label)
        for xi in range(len(keys)):
            val = counts[xi, ti]
            if val > 0:
                ax.text(x[xi] + offsets[ti], val + vmax * 0.02, f"{int(val)}",
                        ha="center", va="bottom", fontsize=FONT_ANNOT - 1,
                        color=GREY_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_category(k) for k in keys], fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Deviating steps", fontsize=FONT_LABEL)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_ylim(0, max(vmax * 1.18, 1.0))
    ax.set_title(_DEVIATION_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    if len(labels) > 1:
        ax.legend(frameon=False, fontsize=FONT_ANNOT, ncol=min(len(labels), 4))
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# --- Idiom: stacked_bar — the same steps, each bar split by trace ------------

def task28_stacked_bar(records, output_dir):
    """The bar chart's steps, one bar per step split by which trace it
    happened in."""
    out = os.path.join(output_dir, "task28_stacked_bar.svg")
    keys, labels, counts = _selected_step_payload(records)
    if not keys or not counts.any():
        render_empty_state_svg(out, _DEVIATION_TITLE, "No deviations found.")
        return

    colors = _trace_colors(len(labels))
    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=(max(8.0, len(keys) * 1.35 + 2.0), 5.4))
    ax.set_facecolor("#fafbfc")

    bottoms = np.zeros(len(keys))
    for ti, label in enumerate(labels):
        vals = counts[:, ti]
        ax.bar(x, vals, bottom=bottoms, width=0.6, color=colors[ti],
               edgecolor="white", linewidth=0.5, label=label)
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 0:
                ax.text(xi, b + v / 2, f"{int(v)}", ha="center", va="center",
                        fontsize=FONT_ANNOT - 1,
                        color=contrasting_text_color(colors[ti]))
        bottoms += vals

    ymax = max(float(bottoms.max()), 1.0)
    ax.set_xticks(x)
    ax.set_xticklabels([_wrap_category(k) for k in keys], fontsize=FONT_ANNOT - 1)
    ax.set_ylabel("Deviating steps", fontsize=FONT_LABEL)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_ylim(0, ymax * 1.16)
    ax.set_title(_DEVIATION_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
              ncol=min(len(labels), 4))
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# --- Idiom: matrix / heatmap — the same grid, as numbers and as colour -------

def _grid_size(row_labels, col_labels):
    """(height, width) for the matrix and the heatmap, which share a grid."""
    longest = max((len(r) for r in row_labels), default=10)
    return (max(3.4, len(row_labels) * 0.5 + 2.0),
            max(5.2, len(col_labels) * 1.5 + 1.6 + longest * 0.105))


def task28_matrix(records, output_dir):
    """The payload as numbers on white cells. The heatmap is the colour."""
    out = os.path.join(output_dir, "task28_matrix.svg")
    keys, labels, counts = _selected_step_payload(records)
    if not keys or not counts.any():
        render_empty_state_svg(out, _DEVIATION_TITLE, "No deviations found.")
        return
    rows = [_category(k) for k in keys]
    fig_h, fig_w = _grid_size(rows, labels)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_rate_matrix(fig, ax, counts, rows, labels, xlabel="Trace",
                     cell_fmt="{:.0f}", colorless=True)
    ax.set_title(_DEVIATION_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


def task28_heatmap(records, output_dir):
    """The same grid as colour. The matrix is the numbers."""
    out = os.path.join(output_dir, "task28_heatmap.svg")
    keys, labels, counts = _selected_step_payload(records)
    if not keys or not counts.any():
        render_empty_state_svg(out, _DEVIATION_TITLE, "No deviations found.")
        return
    rows = [_category(k) for k in keys]
    fig_h, fig_w = _grid_size(rows, labels)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_value_heatmap(fig, ax, counts, rows, labels, xlabel="Trace",
                       cbar_label="Deviating steps", annotate=False,
                       vmax=max(float(counts.max()), 1.0))
    ax.set_title(_DEVIATION_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, out)


# ===========================================================================
# Public entry point
# ===========================================================================

_AGGREGATE_FNAMES = [
    "task28_bar_chart.svg",
    "task28_stacked_bar.svg",
    "task28_matrix.svg",
    "task28_heatmap.svg",
]


def generate(alignments, model_path: str, output_dir: str, log=None,
             perspective="control-flow", trace_ids=None,
             trace_pick_rule="first_nonconformant", trace_count=1,
             violation_pattern="", data_attribute="", conformant_values=(),
             conformant_resources=(), scoped_activity=""):
    """Generate all Task 28 SVGs into output_dir (trace-level deep-dive + log-level
    exploratory overview).

    The trace-level trio is task09's, in whichever perspective the admin chose —
    the two tasks ask the same question of the same traces, one presenting the
    answer and one leaving it to be explored, so they must not show two
    different pictures of it.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 28 visualizations ---")

    # Trace-level deep-dive (the chosen traces)
    ctx = build_task28_context(alignments)
    records = trace_alignment.select_records(
        log, alignments, view=perspective, trace_ids=trace_ids,
        rule=trace_pick_rule, count=trace_count, pattern=violation_pattern,
        attribute=data_attribute, conformant_values=conformant_values,
        resources=conformant_resources, scoped_activity=scoped_activity,
    ) if log is not None else []

    if records:
        import tasks.task09 as task09
        logger.info(f"      -> {len(records)} trace(s) shown, {perspective} perspective.")
        task09.alignment_figures(output_dir, model_path, view=perspective,
                                 records=records, attribute=data_attribute,
                                 prefix="task28", title=_DEVIATION_TITLE,
                                 show_order=False)
    elif ctx is not None:
        logger.info(f"      Using {ctx['trace_label']} (log index {ctx['trace_index']}, "
                    f"fitness={ctx['fitness']:.4f})")
        task28_alignment_table(ctx, output_dir)
        task28_flow_chart_basic(ctx, output_dir)
        task28_flow_chart_elaborate_bpmn(ctx, model_path, output_dir)
    else:
        logger.warning("      task28: no deviating trace — trace-level idioms skipped.")

    # The same traces again, as four aggregates over their deviating steps.
    drawn = records or _records_from_context(ctx)
    keys, labels, counts = _selected_step_payload(drawn)
    if not keys:
        logger.warning("      task28: the shown traces have no deviating step.")
        for fname in _AGGREGATE_FNAMES:
            render_empty_state_svg(os.path.join(output_dir, fname),
                                   _DEVIATION_TITLE, "No deviations found.")
        return

    logger.info(f"      -> {len(keys)} deviating step(s) over {len(labels)} trace(s).")
    task28_bar_chart(drawn, output_dir)
    task28_stacked_bar(drawn, output_dir)
    task28_matrix(drawn, output_dir)
    task28_heatmap(drawn, output_dir)
