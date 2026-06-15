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
IDIOMS = ["tile_metric", "bar_chart", "donut_chart", "scatter_plot",
          "table", "heatmap", "box_plot"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 6 (AUTO): no hyperparameters needed — log fitness is computed directly
# from the alignment output as mean per-trace fitness × 100, rounded.
# ---------------------------------------------------------------------------
GT_TIER = "AUTO"

PARAM_SPEC = []

ANSWER_FORMATS = [
    {"key": "pct",       "gt_shape": "scalar", "decisive_default": True},
    {"key": "mc-single", "gt_shape": "mc",     "decisive_default": True},
]


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Mean per-trace fitness × 100, rounded to the nearest integer percentage.

    For pct: returns a scalar string e.g. "87%".
    For mc-single: correct option + 3 distractors spread across low / high / mid
    zones relative to the true value, snapped to 5-pp multiples, clamped to [0, 100].
    """
    import random as _rnd

    mean_fit = float(fitness_df["fitness"].mean()) if len(fitness_df) > 0 else 0.0
    pct = round(mean_fit * 100)

    if answer_format == "pct":
        return {"value": f"{pct}%"}

    if answer_format == "mc-single":
        # Three distractors from distinct directional zones so they spread across the
        # scale rather than clustering on one side.
        # Snap all values to the nearest 5-pp multiple so options look natural.
        def snap5(v):
            return max(0, min(100, round(v / 5) * 5))

        # Zone targets: one clearly below, one clearly above, one moderately offset.
        zone_offsets = [-25, +25, -15 if pct >= 50 else +15]
        seen = {pct}
        distractors = []
        for base_delta in zone_offsets:
            candidate = snap5(pct + base_delta)
            # If snapping collides, nudge by ±5 until we find a free slot.
            step = 5
            while candidate in seen or candidate == pct:
                candidate = snap5(candidate + step)
                step = -(abs(step) + 5) if step > 0 else abs(step) + 5
                if abs(step) > 50:
                    break
            if candidate not in seen and 0 <= candidate <= 100:
                seen.add(candidate)
                distractors.append(candidate)

        # Fallback: fill remaining slots with simple ±10 pp offsets.
        for delta in range(10, 60, 10):
            if len(distractors) >= 3:
                break
            for sign in (+1, -1):
                c = snap5(pct + sign * delta)
                if c not in seen and 0 <= c <= 100:
                    seen.add(c)
                    distractors.append(c)
                    break

        options = [{"label": f"{pct}%", "value": f"{pct}%", "correct": True}] + [
            {"label": f"{d}%", "value": f"{d}%", "correct": False}
            for d in distractors[:3]
        ]
        _rnd.Random(pct).shuffle(options)
        return {"options": options}

    return {"options": []}

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
    """Bar chart showing count of conformant vs non-conformant traces."""
    conform    = int(df["is_fit"].sum())
    nonconform = len(df) - conform
    total      = len(df)

    labels = ["Conformant Traces", "Non-Conformant Traces"]
    values = [conform, nonconform]

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(labels, values, color=[GREY_MED, GREY_LIGHT], edgecolor="white", width=0.5)
    for bar, val in zip(bars, values):
        pct = val / total * 100 if total else 0
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + 0.5,
            f"{val:,}\n({pct:.1f}%)", ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Conformant vs. Non-Conformant Trace Count", fontsize=FONT_TITLE)
    ax.set_ylim(0, max(values) * 1.2 if values else 10)
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


def task06_donut_chart(df, output_dir: str):
    """Donut chart: conformant vs non-conformant trace counts."""
    conform     = int(df["is_fit"].sum())
    non_conform = len(df) - conform
    total       = len(df)

    pct_conform    = conform / total * 100 if total else 0
    pct_nonconform = non_conform / total * 100 if total else 0

    fig, ax = plt.subplots(figsize=(6, 5))
    wedges, texts = ax.pie(
        [conform, non_conform],
        colors=[GREY_MED, GREY_LIGHT],
        startangle=90,
        wedgeprops=dict(width=0.5),
    )
    ax.legend(
        wedges,
        [f"Conformant ({conform:,}, {pct_conform:.1f}%)",
         f"Non-Conformant ({non_conform:,}, {pct_nonconform:.1f}%)"],
        loc="lower center",
        bbox_to_anchor=(0.5, -0.12),
        fontsize=FONT_ANNOT,
        frameon=False,
    )
    ax.set_title("Conformant vs. Non-Conformant Cases", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.5)
    save_svg(fig, os.path.join(output_dir, "task06_donut_chart.svg"))


def task06_heatmap(df, output_dir: str):
    """Per-trace fitness grid heatmap — each cell is one trace, colour = fitness (light → dark)."""
    fitness = df.sort_values("trace_index")["fitness"].values
    n = len(fitness)

    ncols = max(1, int(np.ceil(np.sqrt(n))))
    nrows = max(1, int(np.ceil(n / ncols)))
    grid  = np.full(nrows * ncols, np.nan)
    grid[:n] = fitness
    grid = grid.reshape(nrows, ncols)

    cmap = LinearSegmentedColormap.from_list("grey_scale", [GREY_LIGHTER, GREY_DARK])
    fig_w = min(10, max(5, ncols * 0.35))
    fig_h = min(8,  max(4, nrows * 0.35))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    im = ax.imshow(grid, cmap=cmap, vmin=0, vmax=1, aspect="auto")
    ax.set_xlabel("Trace (column index)", fontsize=FONT_LABEL)
    ax.set_ylabel("Trace (row index)", fontsize=FONT_LABEL)
    ax.set_title("Per-Trace Fitness Heatmap (light = high fitness)", fontsize=FONT_TITLE)
    cbar = fig.colorbar(im, ax=ax, orientation="vertical", fraction=0.046, pad=0.04)
    cbar.set_label("Fitness (0–1)", fontsize=FONT_LABEL)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_heatmap.svg"))


def task06_box_plot(df, output_dir: str):
    """Boxplot of per-trace fitness values across the log."""
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.boxplot(
        df["fitness"].values,
        labels=["Log"],
        widths=0.4,
        medianprops=dict(color="#333333", linewidth=2),
        boxprops=dict(color="#555555"),
        whiskerprops=dict(color="#555555"),
        capprops=dict(color="#555555"),
        flierprops=dict(marker="o", markerfacecolor=GREY_MED, markersize=4, alpha=0.5),
    )
    ax.set_ylabel("Conformance Rate", fontsize=FONT_LABEL)
    ax.set_title("Distribution of Fitness Values", fontsize=FONT_TITLE)
    ax.set_ylim(-0.05, 1.1)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_box_plot.svg"))


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
    logger.info("\n--- Generating Task 6 visualizations ---")

    task06_tile_metric(df, output_dir)
    task06_bar_chart(df, output_dir)
    task06_donut_chart(df, output_dir)
    task06_scatter_plot(df, output_dir)
    task06_table(df, output_dir)
    task06_heatmap(df, output_dir)
    task06_box_plot(df, output_dir)
