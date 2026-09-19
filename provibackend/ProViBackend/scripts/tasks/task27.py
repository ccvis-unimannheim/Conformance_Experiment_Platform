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

IDIOMS = ["bar_chart", "table", "parallel_sets", "matrix",
          "flow_chart_basic", "flow_chart_elaborate",
          "stacked_bar", "box_plot", "heatmap"]

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
from matplotlib.colors import ListedColormap

from shared import (
    save_svg, draw_parallel_sets, alignment_pairs_to_rows, build_variant_df,
    draw_composition_stacked_bars, draw_grouped_box_plot, draw_value_heatmap,
    draw_cell_grid, render_empty_state_svg,
    GREY_MED, GREY_LIGHT, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

#: How many variants the aggregate idioms show when the admin names no traces.
TOP_N = 15
# Number of conformant / non-conformant variants shown as chevron strips
STRIPS_PER_STATUS = 3

# Two-colour status palette, consistent with task03/task04
_COLOR_CONFORM     = GREY_MED
_COLOR_NON_CONFORM = GREY_LIGHT
_STATUS_COLORS = {"Conformant": _COLOR_CONFORM, "Non-conformant": _COLOR_NON_CONFORM}


#: Fitness at or above which a variant counts as conformant when the admin
#: names none. Perfect conformance — any deviating move at all makes a variant
#: non-conformant, which is what task27 always assumed.
CONFORMANT_DEFAULT = 1.0


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

def task27_bar_chart(vdf: pd.DataFrame, output_dir: str,
                     threshold: float = CONFORMANT_DEFAULT, *,
                     selected: bool = False):
    """Bar chart by frequency, colour = status.

    ``selected``: one bar per named trace, height = how many traces in the log
    share its behaviour. Otherwise the top-N variants, height = #traces.
    """
    top = vdf if selected else vdf.head(TOP_N)
    colors = [_STATUS_COLORS[_status(f, threshold)] for f in top["fitness"]]
    ymax = max(int(top["count"].max()), 1)

    fig, ax = plt.subplots(figsize=(max(7, len(top) * 0.75), 5))
    bars = ax.bar(top["label"], top["count"], color=colors, edgecolor="white", width=0.65)
    for bar, val in zip(bars, top["count"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + ymax * 0.012,
                f"{int(val)}", ha="center", va="bottom", fontsize=FONT_ANNOT - 1)

    ax.legend(handles=_status_legend_handles(),
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    if selected:
        ax.set_xlabel("Selected trace", fontsize=FONT_LABEL)
        ax.set_ylabel("Traces in Log with This Behaviour", fontsize=FONT_LABEL)
        ax.set_title("Trace Behaviour Frequency by Conformance Status",
                     fontsize=FONT_TITLE)
    else:
        ax.set_xlabel(f"Variant (ranked by frequency, top {len(top)} of {len(vdf)})",
                      fontsize=FONT_LABEL)
        ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
        ax.set_title("Variant Frequency by Conformance Status", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_bar_chart.svg"))


def _frequency_bucket(count: int, q33: float, q67: float) -> str:
    if count > q67:
        return "Frequent"
    if count > q33:
        return "Mid"
    return "Rare"


def task27_parallel_sets(vdf: pd.DataFrame, output_dir: str,
                         threshold: float = CONFORMANT_DEFAULT, *,
                         selected: bool = False):
    """Parallel Sets: frequency bucket × conformance status; ribbon = #traces.

    ``selected`` reads the rows as named traces and buckets them by how common
    each one's behaviour is; otherwise they are the log's variants.

    (Deliberately different dimensions from task03's parallel sets.)
    """
    counts = vdf["count"].values.astype(float)
    q33, q67 = np.percentile(counts, [33, 67])

    buckets  = ["Frequent", "Mid", "Rare"]
    statuses = ["Conformant", "Non-conformant"]
    matrix = np.zeros((len(buckets), len(statuses)), dtype=int)
    for _, row in vdf.iterrows():
        bi = buckets.index(_frequency_bucket(int(row["count"]), q33, q67))
        si = statuses.index(_status(row["fitness"], threshold))
        matrix[bi, si] += int(row["count"])   # ribbon width = #traces

    bucket_totals = matrix.sum(axis=1)
    left_labels = [f"{b}\n(n={int(t)})" for b, t in zip(buckets, bucket_totals)]

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    noun = "Behaviour" if selected else "Variant"
    ax.set_title(f"Parallel Sets: {noun}-Frequency Bucket vs. Conformance Status",
                 fontsize=FONT_TITLE, pad=12)

    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=statuses,
        matrix=matrix,
        left_colors=["#555555", "#999999", "#CCCCCC"],
        right_colors=[_COLOR_CONFORM, _COLOR_NON_CONFORM],
        left_title=f"{noun} Frequency",
        right_title="Status",
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_parallel_sets.svg"))


# ---------------------------------------------------------------------------
# Matrix: variant × activity relation (the "how do they differ" view)
# ---------------------------------------------------------------------------

# Cell categories (code order = drawing precedence; higher code wins per cell)
_REL_ABSENT, _REL_CONFORM, _REL_UNEXPECTED, _REL_SKIPPED = 0, 1, 2, 3
#: What each category prints in its cell. The category used to be a fill colour,
#: which made this idiom a heatmap over a nominal variable — colour ranks, and
#: these four do not. A letter names the category instead and the cells stay
#: empty; an absent activity prints nothing, so the pattern of what a trace does
#: touch is what the reader sees first.
_REL_MARKS = ["", "C", "L", "M"]
_REL_LABELS = ["Absent", "Contained (conform)", "Unexpected (log move)",
               "Skipped (model move)"]


def _activity_order(alignments) -> list:
    """Activities ordered by their average alignment step position (≈ model order)."""
    positions = {}
    for result in alignments:
        for row in alignment_pairs_to_rows(result.get("alignment", [])):
            for side in ("model_move", "log_move"):
                act = str(row[side])
                if act in {"-", "None", "(skip)", ""}:
                    continue
                positions.setdefault(act, []).append(row["step"])
    return sorted(positions, key=lambda a: sum(positions[a]) / len(positions[a]))


def _variant_relations(rep_rows) -> dict:
    """Map activity -> relation code for one variant's alignment rows."""
    rel = {}

    def bump(act, code):
        act = str(act)
        if act in {"-", "None", "(skip)", ""}:
            return
        rel[act] = max(rel.get(act, _REL_ABSENT), code)

    for row in rep_rows:
        mt = row["moveType"]
        if mt == "Synchronous Move":
            bump(row["log_move"], _REL_CONFORM)
        elif mt == "Model Move":
            bump(row["model_move"], _REL_SKIPPED)
        elif mt == "Log Move":
            bump(row["log_move"], _REL_UNEXPECTED)
        else:  # Mismatch: model side skipped, log side unexpected
            bump(row["model_move"], _REL_SKIPPED)
            bump(row["log_move"], _REL_UNEXPECTED)
    return rel


def task27_matrix(vdf: pd.DataFrame, alignments, output_dir: str,
                  threshold: float = CONFORMANT_DEFAULT, *,
                  selected: bool = False):
    """Matrix: rows = named traces or the top-N variants, columns = activities;
    cell = that row's relation to the activity."""
    top = vdf if selected else vdf.head(TOP_N)
    activities = _activity_order(alignments)
    if not activities:
        logger.warning("      task27: no activities found for the matrix.")
        return

    data = np.full((len(top), len(activities)), _REL_ABSENT, dtype=int)
    row_labels = []
    for vi, (_, row) in enumerate(top.iterrows()):
        rep_rows = alignment_pairs_to_rows(
            alignments[int(row["rep_trace_index"])].get("alignment", []))
        rel = _variant_relations(rep_rows)
        for ci, act in enumerate(activities):
            data[vi, ci] = rel.get(act, _REL_ABSENT)
        mark = "✓" if _status(row["fitness"], threshold) == "Conformant" else "✗"
        row_labels.append(f"{row['label']} {mark} (n={int(row['count'])})")

    fig_h = max(3.8, 0.5 * len(top) + 2.2)
    fig_w = max(8.0, 0.85 * len(activities) + 3.2)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.imshow(np.zeros_like(data), cmap=ListedColormap(["white"]),
              vmin=0, vmax=1, aspect="auto")
    draw_cell_grid(ax, len(top), len(activities))

    for ri in range(len(top)):
        for ci in range(len(activities)):
            mark = _REL_MARKS[int(data[ri, ci])]
            if mark:
                ax.text(ci, ri, mark, ha="center", va="center",
                        fontsize=FONT_ANNOT, color=GREY_DARK)

    ax.set_xticks(range(len(activities)))
    ax.set_xticklabels(activities, rotation=40, ha="right", fontsize=FONT_ANNOT - 1)
    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(row_labels, fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Activity (model order)", fontsize=FONT_LABEL)
    ax.set_title(f"Trace × Activity Relation ({len(top)} selected traces)"
                 if selected else
                 f"Variant × Activity Relation (top-{len(top)} variants)",
                 fontsize=FONT_TITLE)
    key = "   ".join(f"{m or '(blank)'} = {l}"
                     for m, l in zip(_REL_MARKS, _REL_LABELS))
    ax.text(0.5, -0.32, key, transform=ax.transAxes, ha="center", va="top",
            fontsize=FONT_ANNOT - 1, color=GREY_DARK)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_matrix.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

def _task27_trace_df(log, fitness_df: pd.DataFrame,
                     threshold: float = CONFORMANT_DEFAULT,
                     indices=None) -> pd.DataFrame:
    """Per-trace length, fitness, status, start_time, throughput (timestamped only).

    ``indices`` restricts the frame to the selected traces, in selection order, so
    the distribution idioms describe the traces the rest of the task shows.
    """
    rows = []
    wanted = list(indices) if indices is not None else range(len(log))
    for i in wanted:
        if i >= len(fitness_df) or i >= len(log):
            continue
        trace = log[i]
        fit = float(fitness_df.iloc[i]["fitness"])
        times = []
        for e in trace:
            ts = e.get("time:timestamp")
            if ts is not None:
                try:
                    times.append(pd.Timestamp(ts))
                except Exception:
                    pass
        times.sort()
        throughput = ((times[-1] - times[0]).total_seconds() / 3600
                      if len(times) >= 2 else None)
        rows.append({
            "trace_index": i, "length": len(trace), "fitness": fit,
            "status": _status(fit, threshold),
            "start_time": times[0] if times else pd.NaT,
            "throughput_h": throughput,
        })
    return pd.DataFrame(rows)


def task27_stacked_bar(tdf: pd.DataFrame, output_dir: str):
    """Trace-length bucket × conformance-status composition (trace counts)."""
    lengths = tdf["length"].values.astype(float)
    q33, q67 = np.percentile(lengths, [33, 67])
    def bucket(n):
        return "Short" if n <= q33 else ("Medium" if n <= q67 else "Long")
    tdf = tdf.assign(bucket=[bucket(n) for n in tdf["length"]])

    buckets = ["Short", "Medium", "Long"]
    statuses = ["Conformant", "Non-conformant"]
    counts = np.zeros((len(statuses), len(buckets)))
    for si, s in enumerate(statuses):
        for bi, b in enumerate(buckets):
            counts[si, bi] = int(((tdf["status"] == s) & (tdf["bucket"] == b)).sum())

    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    draw_composition_stacked_bars(ax, buckets, statuses, counts,
                                  segment_colors=[_COLOR_CONFORM, _COLOR_NON_CONFORM])
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Conformance Status by Trace-Length Bucket", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    handles, labels = ax.get_legend_handles_labels()
    ax.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=max(1, len(handles)), frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_stacked_bar.svg"))


def task27_box_plot(tdf: pd.DataFrame, output_dir: str):
    """Throughput-time distribution per conformance-status group."""
    if tdf["throughput_h"].notna().sum() == 0:
        render_empty_state_svg(os.path.join(output_dir, "task27_box_plot.svg"),
                               "Throughput Time per Status", "No timestamp data.")
        return
    statuses = ["Conformant", "Non-conformant"]
    data = [tdf.loc[(tdf["status"] == s) & tdf["throughput_h"].notna(), "throughput_h"].values
            for s in statuses]
    fig, ax = plt.subplots(figsize=(5.5, 6))
    draw_grouped_box_plot(ax, data, statuses, [_COLOR_CONFORM, _COLOR_NON_CONFORM],
                          ylabel="Throughput time (hours)", ylim=None)
    ax.set_title("Throughput Time by Conformance Status", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_box_plot.svg"))


def task27_heatmap(vdf: pd.DataFrame, alignments, output_dir: str,
                   threshold: float = CONFORMANT_DEFAULT, *,
                   selected: bool = False):
    """Named traces or top-N variants × activities, occurrence count within the
    row (continuous)."""
    top = vdf if selected else vdf.head(TOP_N)
    activities = _activity_order(alignments)
    if not activities:
        render_empty_state_svg(
            os.path.join(output_dir, "task27_heatmap.svg"),
            "Trace × Activity Presence" if selected else "Variant × Activity Presence",
            "No activities found.")
        return
    data = np.zeros((len(top), len(activities)))
    labels = []
    for vi, (_, row) in enumerate(top.iterrows()):
        seq = list(row["variant"])
        for ci, act in enumerate(activities):
            data[vi, ci] = seq.count(act)
        mark = "✓" if _status(row["fitness"], threshold) == "Conformant" else "✗"
        labels.append(f"{row['label']} {mark}")
    fig_h = max(3.8, 0.5 * len(top) + 2.0)
    fig_w = max(8.0, 0.7 * len(activities) + 3.0)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    unit = "trace" if selected else "variant"
    draw_value_heatmap(fig, ax, data, labels, activities, xlabel="Activity (model order)",
                       cbar_label=f"Occurrences in {unit}", annotate=False, rotate_xticks=40)
    ax.set_title(f"Activity Presence Across {len(top)} Selected Traces" if selected else
                 f"Activity Presence Across Variants (top-{len(top)})",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_heatmap.svg"))


# ---------------------------------------------------------------------------
# Public entry point
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
                                   filename="task27_flow_chart_basic.svg")
    if model_path:
        task04.task04_flow_chart_elaborate(
            records, model_path, output_dir,
            filename="task27_flow_chart_elaborate.svg",
            title="Conformant and Non-Conformant Traces on the Process Model")
        # The table shows the traces the other two show. It used to list the
        # top-15 variants regardless of the selection, so an admin asking for one
        # conformant and one non-conformant variant got a table contradicting the
        # two strips beside it.
        task04.task04_table(
            records, model_path, output_dir,
            filename="task27_table.svg",
            title="Move Type by Activity — Conformant vs Non-Conformant")


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

    **When the admin names traces, every idiom draws those traces** — the whole
    figure set then answers one selection instead of contradicting itself. Under
    the automatic rule the frequency and distribution idioms keep aggregating over
    the log's variants: the rule picks two traces by default, and a box plot of
    one value per group, or three frequency buckets holding two variants, is not
    a narrower figure but a broken one.
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

    named = bool(trace_ids)
    frame = _selected_variant_df(log, vdf, fitness_df, indices) if named else vdf
    logger.info(f"      -> {len(vdf)} variants "
                f"({n_conform} conformant, {n_nonconf} non-conformant); "
                + (f"every idiom showing the {len(frame)} named trace(s)." if named
                   else f"aggregate idioms showing top-{min(TOP_N, len(vdf))}."))
    if n_conform == 0:
        logger.warning("      task27: no conformant variants — "
                       "status encodings degrade to one group.")
    if n_nonconf == 0:
        logger.warning("      task27: all variants conformant — "
                       "status encodings degrade to one group.")

    task27_bar_chart(frame, output_dir, conformant_threshold, selected=named)
    task27_parallel_sets(frame, output_dir, conformant_threshold, selected=named)
    task27_matrix(frame, alignments, output_dir, conformant_threshold, selected=named)

    _task27_alignment_figures(log, alignments, indices, model_path, output_dir)

    tdf = _task27_trace_df(log, fitness_df, conformant_threshold,
                           indices if named else None)
    task27_stacked_bar(tdf, output_dir)
    task27_box_plot(tdf, output_dir)
    task27_heatmap(frame, alignments, output_dir, conformant_threshold, selected=named)
