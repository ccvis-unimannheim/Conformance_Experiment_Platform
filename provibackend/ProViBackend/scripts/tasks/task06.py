"""
tasks/task06.py – Task ID 6: Describe / Derive / Process conformance
(overall degree of conformance between a single log and the guidelines).

Validated idiom mapping (6 idioms = 1 High + 5 Medium):
    tile_metric          (High) – overall fitness headline value           [shared helper]
    bar_chart            (Med)  – conformant vs non-conformant count split
    scatter_plot         (Med)  – per-trace fitness (x = trace index, y = fitness)
    table                (Med)  – conformance summary row
    flow_chart_elaborate (Med)  – desired model annotated with aggregated deviation
                                  frequencies across all traces (where it deviates)
    decision_tree        (Med)  – tree predicting conformant vs non-conformant traces
                                  from case/event attributes (reuses task20)

Public API:
    generate(df, output_dir, log=None, alignments=None, model_path=None)
        df          – fitness summary DataFrame from io_helpers.fitness_summary_dataframe
        output_dir  – directory where SVGs are written
        log/alignments/model_path – needed for the flow_chart_elaborate + decision_tree
                                    idioms (the central run passes them; absent → empty state)
"""

import logging

logger = logging.getLogger(__name__)

# Validated mapping (the legacy box_plot/donut_chart/heatmap are still rendered for
# backward compatibility but intentionally excluded here so /task-idioms reports the
# validated set only).
IDIOMS = ["tile_metric", "bar_chart", "scatter_plot", "table",
          "flow_chart_elaborate", "tree"]

import os
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import LinearSegmentedColormap
from matplotlib.patches import FancyBboxPatch

from shared import (
    save_svg, make_table, render_fitness_tile_metric, render_empty_state_svg,
    alignment_pairs_to_rows, parse_bpmn_model, render_bpmn_annotated, contrasting_text_color,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse: task20's tree-building + decision-tree renderer for the Tree idiom.
import tasks.task20 as task20


def task06_bar_chart(df, output_dir: str):
    conform     = int(df["is_fit"].sum())
    non_conform = len(df) - conform

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(
        ["Conform Traces", "Non-Conform Traces"],
        [conform, non_conform],
        color=[GREY_MED, GREY_LIGHT], edgecolor="white", width=0.5,
    )
    for bar, val in zip(bars, [conform, non_conform]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + max(conform, non_conform) * 0.015,
            str(val), ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Conform vs. Non-Conform Traces", fontsize=FONT_TITLE)
    ax.set_ylim(0, max(conform, non_conform) * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_bar_chart.svg"))


def task06_scatter_plot(df, output_dir: str):
    colors = [GREY_LIGHTER if fit else GREY_DARK for fit in df["is_fit"]]
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.scatter(df["trace_index"], df["fitness"], c=colors, s=15, alpha=0.6, linewidths=0)
    ax.set_xlabel("Traces in Log ordered by time", fontsize=FONT_LABEL)
    ax.set_ylabel("Conformance Rate", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Conformance Rate per Trace", fontsize=FONT_TITLE)
    ax.legend(
        handles=[mpatches.Patch(color=GREY_LIGHTER, label="Conform: True"),
                 mpatches.Patch(color=GREY_DARK,   label="Conform: False")],
        frameon=False, fontsize=FONT_ANNOT,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_scatter_plot.svg"))


def task06_table(df, output_dir: str):
    """Conformance summary row: #Traces | #Conformant | % Conformant | Overall Fitness.

    Note: '% Conformant' is the share of fully-conformant traces, while 'Overall
    Fitness' is the mean per-trace fitness (0–1) — two distinct measures."""
    total          = len(df)
    conform        = int(df["is_fit"].sum())
    pct_conform    = (conform / total * 100) if total else 0.0
    overall_fitness = float(df["fitness"].mean()) if total else 0.0

    cell_text = [[str(total), str(conform), f"{pct_conform:.2f}%", f"{overall_fitness:.4f}"]]
    # Taller canvas + wrapped headers so cell text is not clipped (mpl table centers text; PAD is weak for center)
    fig_h = max(3.6, 1.45 + len(cell_text) * 0.58)

    fig, ax = plt.subplots(figsize=(10.0, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=[
            "#Traces",
            "#Conformant",
            "% Conformant",
            "Overall Fitness",
        ],
        bbox=[0.03, 0.04, 0.94, 0.80],
        col_widths=[0.24, 0.26, 0.26, 0.24],
        font_size=11,
        scale_xy=(1.12, 2.05),
        cell_pad=0.14,
    )
    ax.set_title("Conformance Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_table.svg"))


def task06_tile_metric(df, output_dir: str):
    avg = float(df["fitness"].mean()) * 100
    render_fitness_tile_metric(avg, os.path.join(output_dir, "task06_tile_metric.svg"))


# ---------------------------------------------------------------------------
# Flow Chart+ (Med) — desired model annotated with aggregated deviation frequencies
# ---------------------------------------------------------------------------

def _task06_deviation_counts(alignments) -> dict:
    """Aggregate per-activity deviation count across ALL traces (non-synchronous moves)."""
    counts = {}
    for result in alignments:
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            mt = step["moveType"]
            if mt == "Synchronous Move":
                continue
            activity = step["model_move"] if mt == "Model Move" else step["log_move"]
            if not activity or str(activity) in {"-", "None", "(skip)"}:
                continue
            counts[str(activity)] = counts.get(str(activity), 0) + 1
    return counts


def _task06_deviation_node_style(counts: dict):
    """Colour each model task by aggregated deviation frequency (white → dark grey)."""
    top = max(counts.values()) if counts else 0

    def _style(eid, elem):
        if elem.get("kind") == "task" and top:
            c = counts.get(elem.get("name", ""), 0)
            if c > 0:
                shade = int(round(225 - 160 * (c / top)))   # 225 (light) .. 65 (dark)
                fill = f"#{shade:02x}{shade:02x}{shade:02x}"
                return (fill, "#333333", 3, contrasting_text_color(fill))
        return ("white", "#888888", 2, "#333333")
    return _style


def task06_flow_chart_elaborate_bpmn(alignments, model_path, output_dir: str):
    """Flow Chart+ (Med): the desired model annotated with aggregated deviation
    frequencies across all traces — the structural companion to the numeric fitness
    (shows *where* the process deviates). Reuses the shared elaborate-model renderer
    (task24/task35 machinery). Stem → canonical slug 'flow_chart_elaborate'."""
    path = os.path.join(output_dir, "task06_flow_chart_elaborate_bpmn.svg")
    if not alignments or not model_path:
        render_empty_state_svg(path, "Where the Process Deviates from the Guideline",
                               "No alignments or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task06: BPMN parse failed: {e}")
        render_empty_state_svg(path, "Where the Process Deviates from the Guideline",
                               "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, "Where the Process Deviates from the Guideline",
                               "No BPMN geometry to render.")
        return

    counts = _task06_deviation_counts(alignments)
    total = sum(counts.values())
    render_bpmn_annotated(
        parsed, path,
        title="Where the Process Deviates from the Guideline (all traces)",
        summary=f"Aggregated deviation moves: {total}. Darker = more deviations on that activity.",
        node_style_fn=_task06_deviation_node_style(counts),
        legend_items=[
            ("#414141", "#333333", 3, "More deviations"),
            ("#c8c8c8", "#333333", 3, "Fewer deviations"),
            ("white",   "#888888", 2, "No deviations"),
        ],
    )


# ---------------------------------------------------------------------------
# Tree (Med) — decision tree explaining conformant vs non-conformant traces
# ---------------------------------------------------------------------------

def task06_tree(log, alignments, output_dir: str):
    """Tree (Med): a Decision Tree predicting conformant vs non-conformant traces from
    case/event attributes — the explanatory companion (which attributes explain the
    fitness). Reuses task20's tree-building + rendering verbatim, then renames the
    output to the task06 stem. Stem → canonical slug 'tree'."""
    path = os.path.join(output_dir, "task06_tree.svg")
    if not log or not alignments:
        render_empty_state_svg(path, "Attributes Explaining Conformance",
                               "No log or alignments available.")
        return
    _df, tree, _root_causes = task20.task20_root_cause_analysis(log, alignments)
    if tree is None:
        render_empty_state_svg(path, "Attributes Explaining Conformance",
                               "No attribute split separates conformant from non-conformant traces.")
        return
    task20.task20_tree(tree, output_dir)
    src = os.path.join(output_dir, "task20_tree.svg")
    if os.path.exists(src):
        os.replace(src, path)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(df, output_dir: str, log=None, alignments=None, model_path=None):
    """Generate all Task ID 6 SVGs into output_dir.

    The four df-only idioms always render; flow_chart_elaborate + decision_tree need
    the central log/alignments/model_path (absent → empty-state)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 6 visualizations ---")

    task06_tile_metric(df, output_dir)
    task06_bar_chart(df, output_dir)
    task06_scatter_plot(df, output_dir)
    task06_table(df, output_dir)
    task06_flow_chart_elaborate_bpmn(alignments, model_path, output_dir)
    task06_tree(log, alignments, output_dir)
