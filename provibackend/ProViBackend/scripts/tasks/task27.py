"""
tasks/task27.py – Task ID 27: Explore / Identify / Conformant and non-conformant traces.

Identify WHICH variants/traces are conformant and which are not, and how they
differ. Unit = control-flow variant (shared.build_variant_df, reused from
task04); Conformant = fitness ≥ conformant_threshold (default 1.0). Encodings are status-centric
(frequency × status), unlike task04 (degree-centric) and task03 (behavioural
group comparison). Reuses the centrally computed alignments — nothing re-run.

Public API:
    generate(log, fitness_df, alignments, output_dir, model_path=None,
             conformant_threshold=CONFORMANT_DEFAULT, trace_ids=None,
             trace_count=1)
        log                  – PM4Py EventLog
        fitness_df           – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        alignments           – raw alignment results from io_helpers.run_alignments
        output_dir           – directory where SVGs are written
        model_path           – reference BPMN; without it flow_chart_elaborate is skipped
        conformant_threshold – fitness at or above which a variant is conformant
        trace_ids,
        trace_count          – which traces are shown. There is no pick rule: the
                               question is the contrast, so the count is per
                               status — 2 means 2 conformant and 2 non-conformant.
                               Named traces reach every idiom; under the automatic
                               rule the frequency and distribution idioms keep
                               aggregating over the log's variants
"""

import logging

logger = logging.getLogger(__name__)

#: The box plot is gone. It drew throughput time per status, which answers how
#: *long* the two groups take rather than how their behaviour differs, and a
#: distribution needs a population — over the handful of traces the admin names
#: it was a box built from one or two values.
IDIOMS = ["bar_chart", "table", "parallel_sets", "matrix",
          "flow_chart_basic", "flow_chart_elaborate",
          "stacked_bar", "heatmap"]

import trace_alignment
import trace_response

#: Which variants are shown is the same choice the rest of the class makes, with
#: one rule of its own: the task asks "what are conformant and what are
#: non-conformant traces", so the default picks both, in equal number.
#: No rule picker: this task's question *is* "what are conformant and what are
#: non-conformant traces", so the traces come one group at a time and any other
#: rule would answer a different question. The count is therefore per group.
PARAM_SPEC = [
    dict(trace_alignment.TRACE_SELECTION_MODE_PARAM),
    dict(trace_alignment.TRACE_IDS_PARAM),
    {**trace_alignment.trace_count_param(1, 1, 3),
     "label": "How many conformant and how many non-conformant traces to show",
     "hint": "This many of each, so two means two conformant and two non-conformant",
     "visible_if": {"trace_selection_mode": "auto"}},
    trace_response.CONFORMANT_THRESHOLD_PARAM,
]


def validate_params(log, params) -> list:
    """The threshold has to leave both groups non-empty — with every variant on
    one side the task has nothing to contrast. Checked against the log's own
    fitness values, which is why it cannot be a static rule."""
    errors = trace_alignment.validate_selection(log, params, min_traces=1, max_traces=6)
    raw = (params or {}).get("conformant_threshold")
    if raw not in (None, ""):
        try:
            value = float(raw)
        except (TypeError, ValueError):
            errors.append("The conformant threshold must be a number between 0 and 1.")
        else:
            if not 0.0 <= value <= 1.0:
                errors.append("The conformant threshold must be between 0 and 1.")
    return errors

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.colors import to_hex

from shared import (
    save_svg, draw_parallel_sets, alignment_pairs_to_rows, build_variant_df,
    contrasting_text_color,
    draw_value_heatmap, render_empty_state_svg,
    GREY_DARK, PAIR_COLORS, CIVIDIS_R,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Number of conformant / non-conformant variants shown as chevron strips
STRIPS_PER_STATUS = 3

#: The platform's two-category pair — cividis navy and cividis bright yellow,
#: as task29, task31 and task32 use it. It was GREY_MED over GREY_LIGHT, two
#: neighbours in cividis's olive middle that read as one shade at a glance,
#: which is the worst possible reading for the contrast this task is about.
_COLOR_CONFORM, _COLOR_NON_CONFORM = PAIR_COLORS
_STATUS_COLORS = {"Conformant": _COLOR_CONFORM, "Non-conformant": _COLOR_NON_CONFORM}


#: Fitness at or above which a variant counts as conformant when the admin
#: names none. Perfect conformance — any deviating move at all makes a variant
#: non-conformant, which is what task27 always assumed.
CONFORMANT_DEFAULT = 1.0

#: One title over all eight idioms, in the words of the task. They used to carry
#: seven different ones, several of which named a unit ("Variant Frequency",
#: "top-15 variants") that stopped being true when every idiom moved onto the
#: selected traces.
_TASK27_TITLE = "How Conformant and Non-Conformant Traces Differ"


def _status(fitness: float, threshold: float = CONFORMANT_DEFAULT) -> str:
    return "Conformant" if fitness >= threshold else "Non-conformant"


def _split_by_status(vdf, threshold: float = CONFORMANT_DEFAULT):
    """(conformant, non-conformant) slices of a variant frame."""
    return vdf[vdf["fitness"] >= threshold], vdf[vdf["fitness"] < threshold]


def _status_legend_handles():
    return [
        mpatches.Patch(color=_COLOR_CONFORM,     label="Conformant (fitness = 1.0)"),
        mpatches.Patch(color=_COLOR_NON_CONFORM, label="Non-conformant (fitness < 1.0)"),
    ]


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def _activity_order(alignments) -> list:
    """Activities ordered by their average alignment step position (≈ model order).

    The row axis every aggregate idiom shares, so the five read down the same
    list in the same order.
    """
    positions = {}
    for result in alignments:
        for row in alignment_pairs_to_rows(result.get("alignment", [])):
            for side in ("model_move", "log_move"):
                act = str(row[side])
                if act in {"-", "None", "(skip)", ""}:
                    continue
                positions.setdefault(act, []).append(row["step"])
    return sorted(positions, key=lambda a: sum(positions[a]) / len(positions[a]))


def _activity_status_payload(frame, alignments, threshold):
    """(activities, statuses, counts) — the one thing all five
    aggregate idioms draw.

    A cell is how many of the selected traces of that conformance status
    touch that activity. Rows are the model's activities in model order,
    columns the two statuses, so the figure reads across as "these
    activities the two groups share, these only one of them does" — which
    is the task's question, in one grid.

    The five used to carry three different answers between them: the bar
    chart and the parallel sets said how *common* each selected behaviour
    is, the stacked bar how *long* the traces are, and only the matrix and
    the heatmap what the traces actually *do*. Frequency and length are
    differences, but not the behavioural difference this task asks about,
    and three payloads across eight idioms is not one figure set.
    """
    activities = _activity_order(alignments)
    statuses = ["Conformant", "Non-conformant"]
    counts = np.zeros((len(activities), len(statuses)), dtype=float)
    for _, row in frame.iterrows():
        si = statuses.index(_status(row["fitness"], threshold))
        touched = set(row["variant"])
        for ai, act in enumerate(activities):
            if act in touched:
                counts[ai, si] += 1
    return activities, statuses, counts


def _activity_ticks(ax, activities):
    """Activity names along the x axis, angled so long ones stay apart."""
    ax.set_xticks(np.arange(len(activities)))
    ax.set_xticklabels(activities, rotation=35, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Activity (model order)", fontsize=FONT_LABEL)


def _no_activities(output_dir, idiom_key):
    render_empty_state_svg(os.path.join(output_dir, f"task27_{idiom_key}.svg"),
                           _TASK27_TITLE, "No activities found.")


def task27_bar_chart(frame, alignments, output_dir: str,
                     threshold: float = CONFORMANT_DEFAULT):
    """Grouped bars: per activity, one bar per conformance status."""
    activities, statuses, counts = _activity_status_payload(frame, alignments, threshold)
    if not activities:
        _no_activities(output_dir, "bar_chart")
        return

    x = np.arange(len(activities))
    bw = 0.38
    ymax = max(float(counts.max()), 1.0)
    fig, ax = plt.subplots(figsize=(max(8.0, len(activities) * 1.05 + 2.0), 5.4))
    ax.set_facecolor("#fafbfc")
    for si, status in enumerate(statuses):
        off = (si - 0.5) * bw
        ax.bar(x + off, counts[:, si], bw * 0.92, color=_STATUS_COLORS[status],
               edgecolor="white", linewidth=0.6, label=status)
        for xi, val in zip(x, counts[:, si]):
            if val > 0:
                ax.text(xi + off, val + ymax * 0.02, f"{int(val)}", ha="center",
                        va="bottom", fontsize=FONT_ANNOT - 1, color=GREY_DARK)

    _activity_ticks(ax, activities)
    ax.set_ylabel("Selected traces containing it", fontsize=FONT_LABEL)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_ylim(0, ymax * 1.18)
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_bar_chart.svg"))


def task27_stacked_bar(frame, alignments, output_dir: str,
                       threshold: float = CONFORMANT_DEFAULT):
    """The bar chart's counts, stacked instead of side by side."""
    activities, statuses, counts = _activity_status_payload(frame, alignments, threshold)
    if not activities:
        _no_activities(output_dir, "stacked_bar")
        return

    x = np.arange(len(activities))
    fig, ax = plt.subplots(figsize=(max(8.0, len(activities) * 1.05 + 2.0), 5.4))
    ax.set_facecolor("#fafbfc")
    bottoms = np.zeros(len(activities))
    for si, status in enumerate(statuses):
        vals = counts[:, si]
        ax.bar(x, vals, 0.6, bottom=bottoms, color=_STATUS_COLORS[status],
               edgecolor="white", linewidth=0.5, label=status)
        for xi, (v, b) in enumerate(zip(vals, bottoms)):
            if v > 0:
                ax.text(xi, b + v / 2, f"{int(v)}", ha="center", va="center",
                        fontsize=FONT_ANNOT - 1,
                        color=contrasting_text_color(_STATUS_COLORS[status]))
        bottoms += vals

    ymax = max(float(bottoms.max()), 1.0)
    _activity_ticks(ax, activities)
    ax.set_ylabel("Selected traces containing it", fontsize=FONT_LABEL)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_ylim(0, ymax * 1.16)
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_stacked_bar.svg"))


def task27_parallel_sets(frame, alignments, output_dir: str,
                         threshold: float = CONFORMANT_DEFAULT):
    """The same counts as ribbons: activity on the left, status on the
    right."""
    activities, statuses, counts = _activity_status_payload(frame, alignments, threshold)
    if not activities:
        _no_activities(output_dir, "parallel_sets")
        return

    fig, ax = plt.subplots(figsize=(max(9.0, len(activities) * 0.55 + 5.0), 5.8))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE, pad=12)
    draw_parallel_sets(
        ax,
        left_labels=activities,
        right_labels=statuses,
        matrix=counts.astype(int),
        left_colors=[to_hex(CIVIDIS_R(0.15 + 0.7 * i / max(len(activities) - 1, 1)))
                     for i in range(len(activities))],
        right_colors=[_STATUS_COLORS[st] for st in statuses],
        left_title="Activity",
        right_title="Status",
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_parallel_sets.svg"))


def task27_matrix(frame, alignments, output_dir: str,
                  threshold: float = CONFORMANT_DEFAULT):
    """The same counts as numbers on white cells. The heatmap is the
    colour."""
    activities, statuses, counts = _activity_status_payload(frame, alignments, threshold)
    if not activities:
        _no_activities(output_dir, "matrix")
        return

    fig_h = max(3.4, len(activities) * 0.5 + 2.0)
    fig_w = max(6.0, 4.0 + max((len(a) for a in activities), default=10) * 0.105)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_value_heatmap(fig, ax, counts, activities, statuses,
                       xlabel="Conformance status", cell_fmt="{:.0f}",
                       annotate=True, rotate_xticks=0, colorless=True)
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_matrix.svg"))


def task27_heatmap(frame, alignments, output_dir: str,
                   threshold: float = CONFORMANT_DEFAULT):
    """The same counts as colour. The matrix is the numbers."""
    activities, statuses, counts = _activity_status_payload(frame, alignments, threshold)
    if not activities:
        _no_activities(output_dir, "heatmap")
        return

    fig_h = max(3.4, len(activities) * 0.5 + 2.0)
    fig_w = max(6.0, 4.0 + max((len(a) for a in activities), default=10) * 0.105)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    draw_value_heatmap(fig, ax, counts, activities, statuses,
                       xlabel="Conformance status",
                       cbar_label="Selected traces containing it",
                       annotate=False, rotate_xticks=0,
                       vmax=max(float(counts.max()), 1.0))
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_heatmap.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

def _selected_indices(log, vdf, *, threshold, trace_ids, count) -> list:
    """The trace indices this task shows — read by *every* idiom, not just some.

    ``count`` of each status, not ``count`` in total: the contrast is the
    question, so both sides are always on screen. Without named ids the variants
    are picked as representatives — one trace per variant (its
    ``rep_trace_index``) — conformant ones first, so "Trace 1" is the conformant
    exemplar.

    Resolved once in ``generate``. It used to live inside the chevron/BPMN/table
    path while every other idiom sliced the top-15 variants itself, so a *named*
    selection reached three idioms out of nine and the figures contradicted each
    other. A named selection now reaches all of them; the automatic rule still
    only drives the trace-level trio, because it picks two traces by default and
    the aggregate idioms need the log.
    """
    if vdf.empty:
        return []
    if trace_ids:
        index_of = trace_alignment.case_index(log)
        return [index_of[str(t)] for t in trace_ids if str(t) in index_of]
    conform, nonconf = _split_by_status(vdf, threshold)
    return ([int(r) for r in conform["rep_trace_index"].head(count)] +
            [int(r) for r in nonconf["rep_trace_index"].head(count)])


def _selected_variant_df(log, vdf, fitness_df, indices) -> pd.DataFrame:
    """``build_variant_df``'s schema with one row per *selected trace*.

    Same columns, so the frequency, matrix and heatmap renderers stay as they are.
    ``count`` / ``coverage`` remain the frequency of that trace's behaviour in the
    whole log: the trace itself is a single occurrence, but how common its
    behaviour is, is what those idioms report. ``label`` is the running
    "Trace 1".."Trace N" ``trace_records`` also assigns, so the bar chart and the
    move table name the same trace the same way.
    """
    by_seq = {tuple(variant): (int(count), float(coverage))
              for variant, count, coverage
              in zip(vdf["variant"], vdf["count"], vdf["coverage"])}
    rows = []
    for position, i in enumerate(indices):
        if i >= len(log) or i >= len(fitness_df):
            continue
        seq = trace_alignment.sequence_of(log, i)
        count, coverage = by_seq.get(seq, (1, 100.0 / max(len(log), 1)))
        rows.append({
            "rank": position + 1, "variant": seq,
            "count": count, "coverage": coverage,
            "fitness": float(fitness_df.iloc[i]["fitness"]),
            "length": len(seq), "label": f"Trace {position + 1}",
            "rep_trace_index": i,
        })
    return pd.DataFrame(rows, columns=["rank", "variant", "count", "coverage",
                                       "fitness", "length", "label",
                                       "rep_trace_index"])


def _task27_alignment_figures(log, alignments, indices, model_path, output_dir):
    """Chevron and BPMN of the compared traces, drawn by task04's renderers."""
    import tasks.task04 as task04

    records = trace_alignment.trace_records(log, alignments, indices)
    if not records:
        logger.warning("      task27: no variants to draw the alignment idioms from.")
        return

    task04.task04_flow_chart_basic(records, output_dir, model_path=model_path,
                                   filename="task27_flow_chart_basic.svg",
                                   title=_TASK27_TITLE)
    if model_path:
        task04.task04_flow_chart_elaborate(
            records, model_path, output_dir,
            filename="task27_flow_chart_elaborate.svg",
            title=_TASK27_TITLE)
        # The table shows the traces the other two show. It used to list the
        # top-15 variants regardless of the selection, so an admin asking for one
        # conformant and one non-conformant variant got a table contradicting the
        # two strips beside it.
        task04.task04_table(
            records, model_path, output_dir,
            filename="task27_table.svg",
            title=_TASK27_TITLE)


def generate(log, fitness_df, alignments, output_dir: str, model_path: str = None,
             conformant_threshold: float = CONFORMANT_DEFAULT, trace_ids=None,
             trace_count=1):
    """Generate all Task ID 27 SVGs into output_dir.

    model_path is required for the flow_chart_elaborate idiom (the annotated
    BPMN); when absent that idiom is skipped.

    ``conformant_threshold`` is the fitness at or above which a variant counts as
    conformant — the cut this task's whole question rests on, and previously
    fixed at 1.0 in code. ``trace_count`` is how many traces of *each* status the
    chevron, BPMN and table idioms show.

    **Every idiom draws the selected traces**, named by hand or picked by the
    rule. The frequency and distribution idioms used to fall back to the log's
    top-15 variants under the automatic rule, so the chevron showed two traces
    and the bar chart beside it fifteen variants. The objection to closing that
    gap was the box plot — one value per group is not a distribution — and the
    box plot is gone.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 27 visualizations ---")

    if fitness_df is None or fitness_df.empty:
        logger.warning("      Skipped Task 27: empty fitness DataFrame.")
        return

    vdf = build_variant_df(log, fitness_df, warn_prefix="task27")
    if vdf.empty:
        logger.warning("      Skipped Task 27: no trace data available.")
        return

    n_conform = int((vdf["fitness"] >= conformant_threshold).sum())
    n_nonconf = len(vdf) - n_conform

    indices = _selected_indices(log, vdf, threshold=conformant_threshold,
                                trace_ids=trace_ids, count=trace_count)
    if not indices:
        logger.warning("      Skipped Task 27: the selection names no trace.")
        return

    frame = _selected_variant_df(log, vdf, fitness_df, indices)
    logger.info(f"      -> {len(vdf)} variants "
                f"({n_conform} conformant, {n_nonconf} non-conformant); "
                f"every idiom showing the {len(frame)} selected trace(s).")
    if n_conform == 0:
        logger.warning("      task27: no conformant variants — "
                       "status encodings degrade to one group.")
    if n_nonconf == 0:
        logger.warning("      task27: all variants conformant — "
                       "status encodings degrade to one group.")

    task27_bar_chart(frame, alignments, output_dir, conformant_threshold)
    task27_stacked_bar(frame, alignments, output_dir, conformant_threshold)
    task27_parallel_sets(frame, alignments, output_dir, conformant_threshold)
    task27_matrix(frame, alignments, output_dir, conformant_threshold)
    task27_heatmap(frame, alignments, output_dir, conformant_threshold)

    _task27_alignment_figures(log, alignments, indices, model_path, output_dir)
