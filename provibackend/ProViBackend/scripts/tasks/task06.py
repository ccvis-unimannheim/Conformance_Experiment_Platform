"""
tasks/task06.py – Task ID 6: Describe / Derive / Process conformance
(overall degree of conformance between a single log and the guidelines).

The task asks a single question — the overall degree of conformance, i.e. the
fitness value between 0 (no conformance) and 1 (perfect). Every idiom therefore
speaks one vocabulary ("Fitness" / "Mean Fitness", 0–1); no conformant-vs-non-
conformant split, no percentages, no trace counts beyond "# of Traces".

Idiom mapping:
    tile_metric – overall mean-fitness headline value (0–1)        [shared helper]
    bar_chart   – single bar of the overall mean fitness (0–1), value labelled
    table       – fitness summary (# traces, mean/min/max/std fitness)
    heatmap     – single-cell mean-fitness value (0–1)
    box_plot    – distribution of per-trace fitness (mean annotated)

Public API:
    generate(df, output_dir, log=None, alignments=None, model_path=None)
        df          – fitness summary DataFrame from io_helpers.fitness_summary_dataframe
        output_dir  – directory where SVGs are written
        log/alignments/model_path – accepted for signature compatibility with the
                                    central run (currently unused by the rendered idioms)
"""

import logging

logger = logging.getLogger(__name__)

# Validated mapping. scatter_plot and donut_chart were removed on request: the
# task is purely about fitness, so the per-trace scatter and the conformant-vs-
# non-conformant donut (which mixed counts with fitness) did not fit.
IDIOMS = ["tile_metric", "bar_chart",
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
    """Single bar of the overall mean fitness (0–1), value labelled — so the
    fitness reads off as a number, exactly as clearly as on the tile / heatmap /
    table (no binning, no fitness bands)."""
    mean_fitness = float(df["fitness"].mean()) if len(df) else 0.0

    fig, ax = plt.subplots(figsize=(4.5, 5))
    bar = ax.bar(["Overall"], [mean_fitness], color=GREY_MED, edgecolor="white", width=0.4)[0]
    ax.text(bar.get_x() + bar.get_width() / 2, mean_fitness + 0.018, f"{mean_fitness:.3f}",
            ha="center", va="bottom", fontsize=FONT_TITLE, fontweight="bold", color=GREY_DARK)
    ax.set_ylim(0, 1.12)
    ax.set_yticks([0.0, 0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_ylabel("Mean Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_title("Overall Mean Fitness", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_bar_chart.svg"))


def task06_table(df, output_dir: str):
    """Fitness summary row (fitness only — Task 6 is purely about the fitness value):
    # of Traces | Mean Fitness | Min Fitness | Max Fitness | Std Fitness (all 0–1)."""
    total = len(df)
    vals  = df["fitness"].values
    mean_fitness = float(np.mean(vals)) if total else 0.0
    min_fitness  = float(np.min(vals))  if total else 0.0
    max_fitness  = float(np.max(vals))  if total else 0.0
    std_fitness  = float(np.std(vals))  if total else 0.0

    cell_text = [[str(total), f"{mean_fitness:.3f}", f"{min_fitness:.3f}",
                  f"{max_fitness:.3f}", f"{std_fitness:.3f}"]]
    # Taller canvas + wrapped headers so cell text is not clipped (mpl table centers text; PAD is weak for center)
    fig_h = max(3.6, 1.45 + len(cell_text) * 0.58)

    fig, ax = plt.subplots(figsize=(10.0, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=[
            "# of Traces",
            "Mean Fitness",
            "Min Fitness",
            "Max Fitness",
            "Std Fitness",
        ],
        bbox=[0.03, 0.04, 0.94, 0.80],
        col_widths=[0.20, 0.20, 0.20, 0.20, 0.20],
        font_size=11,
        scale_xy=(1.12, 2.05),
        cell_pad=0.14,
    )
    ax.set_title("Fitness Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_table.svg"))


def task06_tile_metric(df, output_dir: str):
    mean_fitness = float(df["fitness"].mean()) if len(df) else 0.0
    render_fitness_tile_metric(
        mean_fitness, os.path.join(output_dir, "task06_tile_metric.svg"),
        metric_label="Mean Fitness", as_fraction=True)


def task06_heatmap(df, output_dir: str):
    """Single-cell heatmap of the overall mean fitness, light→dark grey.

    Colour-encodes the mean fitness on a fixed 0–1 scale and labels the cell with
    the actual fitness value (0–1). Drawn as a tidy square cell (aspect='equal')
    so it reads as one metric tile, not a stretched block.
    """
    fitness = float(df["fitness"].mean()) if len(df) else 0.0

    cmap = LinearSegmentedColormap.from_list("grey_scale", [GREY_LIGHTER, GREY_DARK])
    fig, ax = plt.subplots(figsize=(4.5, 4.5))
    im = ax.imshow([[fitness]], cmap=cmap, vmin=0.0, vmax=1.0, aspect="equal")
    text_color = "white" if fitness > 0.55 else GREY_DARK
    ax.text(0, 0, f"{fitness:.3f}", ha="center", va="center",
            fontsize=28, fontweight="bold", color=text_color)
    ax.set_xticks([])
    ax.set_yticks([])
    cbar = fig.colorbar(im, ax=ax, orientation="vertical", fraction=0.046, pad=0.04)
    cbar.set_label("Mean Fitness (0–1)", fontsize=FONT_LABEL)
    cbar.set_ticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.set_title("Overall Mean Fitness", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task06_heatmap.svg"))


def task06_box_plot(df, output_dir: str):
    """Boxplot of per-trace fitness values across the log, annotated with the
    mean fitness so the idiom shows an actual fitness number."""
    vals = df["fitness"].values
    mean_fit = float(np.mean(vals)) if len(vals) else 0.0

    fig, ax = plt.subplots(figsize=(5, 5))
    ax.boxplot(
        vals,
        labels=["Log"],
        widths=0.4,
        medianprops=dict(color="#333333", linewidth=2),
        boxprops=dict(color="#555555"),
        whiskerprops=dict(color="#555555"),
        capprops=dict(color="#555555"),
        flierprops=dict(marker="o", markerfacecolor=GREY_MED, markersize=4, alpha=0.5),
    )
    # Numeric fitness readout: mean as a marker + label.
    ax.scatter([1], [mean_fit], marker="D", s=28, color=GREY_DARK, zorder=5)
    ax.annotate(f"Mean = {mean_fit:.3f}", (1.18, mean_fit),
                textcoords="offset points", xytext=(0, 0),
                va="center", ha="left", fontsize=FONT_ANNOT, color=GREY_DARK)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
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

    The df-only idioms (tile_metric, bar_chart, table, heatmap, box_plot) always
    render; flow_chart_elaborate + decision_tree need the central
    log/alignments/model_path (absent → empty-state)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 6 visualizations ---")

    task06_tile_metric(df, output_dir)
    task06_bar_chart(df, output_dir)
    task06_table(df, output_dir)
    task06_heatmap(df, output_dir)
    task06_box_plot(df, output_dir)
