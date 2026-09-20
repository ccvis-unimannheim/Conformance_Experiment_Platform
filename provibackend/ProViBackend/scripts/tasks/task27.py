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
                               Every idiom draws those traces, named by hand or
                               picked by the rule.
"""

import logging

logger = logging.getLogger(__name__)

#: The box plot is gone. It drew throughput time per status, which answers how
#: *long* the two groups take rather than how their behaviour differs, and a
#: distribution needs a population — over the handful of traces the admin names
#: it was a box built from one or two values.
#: The parallel sets went with it. They drew the same counts as ribbons, and
#: over a handful of selected traces every cell is 0, 1 or 2 — a ribbon of
#: width 1 beside one of width 2 is not a readable difference, and the thin
#: ones fall below draw_parallel_sets's label threshold and vanish. It was the
#: weakest carrier of a payload the matrix and the heatmap carry exactly.
IDIOMS = ["bar_chart", "table", "matrix",
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
#: Which non-conformant variants the automatic selection takes, ranked *inside*
#: the slice the threshold defines. Deliberately not the trace-alignment class's
#: PICK_RULES: those rank the whole log by violation count, which is a different
#: cut from this task's `fitness < conformant_threshold`. At a threshold below
#: 1.0 the two disagree — a trace at 0.9 violates the guideline but is
#: conformant here — and a rule reading the other cut would hand this task a
#: trace its own threshold puts on the opposite side. Ranking within the slice
#: makes that impossible rather than merely validated against.
NONCONFORMANT_PICK_RULES: dict[str, str] = {
    "most_frequent": "The most frequent non-conformant variants",
    "worst_fitness": "The worst-fitness non-conformant variants",
    "fitness_gap":   "Spread across the fitness range below the threshold",
    "first_in_log":  "The first non-conformant variant(s) in the log",
}

PARAM_SPEC = [
    dict(trace_alignment.TRACE_SELECTION_MODE_PARAM),
    dict(trace_alignment.TRACE_IDS_PARAM),
    {**trace_alignment.trace_count_param(1, 1, 3),
     "label": "How many conformant and how many non-conformant traces to show",
     "hint": "This many of each, so two means two conformant and two non-conformant",
     "visible_if": {"trace_selection_mode": "auto"}},
    {"key": "nonconformant_pick_rule",
     "label": "Which non-conformant traces to show",
     "hint": "How the deviating side is chosen; the conformant side is always "
             "the most frequent variants",
     "widget": "select-one",
     "options": [{"value": k, "label": v} for k, v in NONCONFORMANT_PICK_RULES.items()],
     "default": "most_frequent",
     "required": False,
     "visible_if": {"trace_selection_mode": "auto"}},
    trace_response.CONFORMANT_THRESHOLD_PARAM,
]


def validate_params(log, params) -> list:
    """Check what can be checked without replaying the log.

    Whether the threshold leaves both sides non-empty cannot be: it needs the
    per-trace fitness, which needs the alignments, and the hook is handed only
    the log — running them here would make the pre-flight check as expensive as
    the generation it guards. `generate` has the fitness already and says so
    there. The docstring used to claim this check; it never did it.
    """
    errors = trace_alignment.validate_selection(log, params, min_traces=1, max_traces=6)
    params = params or {}
    rule = params.get("nonconformant_pick_rule") or "most_frequent"
    if rule not in NONCONFORMANT_PICK_RULES:
        errors.append(f"Unknown rule for the non-conformant traces: '{rule}'.")

    raw = params.get("conformant_threshold")
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

from shared import (
    save_svg, alignment_pairs_to_rows, build_variant_df, make_table,
    auto_col_widths,
    draw_value_heatmap, render_empty_state_svg, format_threshold,
    contrasting_text_color,
    GREY_DARK, PAIR_COLORS,
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


#: The order the move types are listed in, so the rows of one activity always
#: come in the same sequence.
_MOVE_ORDER = {"Synchronous Move": 0, "Model Move": 1, "Log Move": 2}

#: Alignment labels that stand for "nothing on this side".
_NO_ACTIVITY = {"-", "None", "(skip)", ""}


def _row_activity(row) -> str:
    """The activity an alignment row is about, whichever side carries it."""
    return str(row["log_move"] if row["moveType"] == "Log Move"
               else row["model_move"])


def _category(key) -> str:
    activity, move_type = key
    return f"{activity} ({move_type})"


def _status_payload(frame, alignments, threshold):
    """(keys, statuses, counts) — the one thing every idiom but the two
    flow charts draws.

    A key is an (activity, move type) pair; a cell is how many traces of that
    conformance status perform that activity that way. Columns are the two
    statuses, which is the comparison the task asks for: the figure reads
    across as "this is what conformant traces do with Check Credit, this is
    what non-conformant ones do with it".

    The move type is in the row rather than dropped, because it is the *how*
    of the difference. Without it the two columns of a shared activity both
    read "2" and the figure says the groups are alike, when in truth one
    executed the activity and the other skipped it. With it the rows separate
    on their own: Synchronous Move rows fill the conformant column, Model Move
    and Log Move rows the other. Same construction as task34's payload.

    Counted per trace, not per occurrence: an activity a trace performs twice
    is still one trace doing it, and the columns hold trace counts so the two
    groups stay comparable.
    """
    statuses = ["Conformant", "Non-conformant"]
    rank = {a: i for i, a in enumerate(_activity_order(alignments))}
    tally, keys = {}, []
    for _, row in frame.iterrows():
        status = _status(row["fitness"], threshold)
        index = int(row["rep_trace_index"])
        if index >= len(alignments):
            continue
        seen = set()
        for pair in alignment_pairs_to_rows(alignments[index].get("alignment", [])):
            activity = _row_activity(pair)
            if activity in _NO_ACTIVITY:
                continue
            key = (activity, pair["moveType"])
            if key not in tally:
                tally[key] = {st: 0 for st in statuses}
                keys.append(key)
            seen.add(key)
        for key in seen:
            tally[key][status] += 1

    keys.sort(key=lambda k: (rank.get(k[0], len(rank)), _MOVE_ORDER.get(k[1], 9)))
    counts = np.array([[tally[k][st] for st in statuses] for k in keys],
                      dtype=float).reshape(len(keys), len(statuses))
    return keys, statuses, counts


def _category_ticks(ax, keys):
    """The activity/move-type pairs along the x axis, angled so they stay apart."""
    ax.set_xticks(np.arange(len(keys)))
    ax.set_xticklabels([_category(k) for k in keys], rotation=35, ha="right",
                       fontsize=FONT_ANNOT - 1)
    ax.set_xlabel("Activity (Move Type), in model order", fontsize=FONT_LABEL)


def _no_activities(output_dir, idiom_key):
    render_empty_state_svg(os.path.join(output_dir, f"task27_{idiom_key}.svg"),
                           _TASK27_TITLE, "No activities found.")


def _bar_figsize(keys):
    return (max(8.0, len(keys) * 1.05 + 2.0), 6.0)


def _grid_figsize(keys):
    widest = max((len(_category(k)) for k in keys), default=10)
    return (max(6.0, 3.6 + widest * 0.105), max(3.4, len(keys) * 0.46 + 2.0))


def task27_bar_chart(frame, alignments, output_dir: str,
                     threshold: float = CONFORMANT_DEFAULT):
    """Grouped bars: per activity and move type, one bar per status."""
    keys, statuses, counts = _status_payload(frame, alignments, threshold)
    if not keys:
        _no_activities(output_dir, "bar_chart")
        return

    x = np.arange(len(keys))
    bw = 0.38
    ymax = max(float(counts.max()), 1.0)
    fig, ax = plt.subplots(figsize=_bar_figsize(keys))
    ax.set_facecolor("#fafbfc")
    for si, status in enumerate(statuses):
        off = (si - 0.5) * bw
        ax.bar(x + off, counts[:, si], bw * 0.92, color=_STATUS_COLORS[status],
               edgecolor="white", linewidth=0.6, label=status)
        for xi, val in zip(x, counts[:, si]):
            if val > 0:
                ax.text(xi + off, val + ymax * 0.02, f"{int(val)}", ha="center",
                        va="bottom", fontsize=FONT_ANNOT - 1, color=GREY_DARK)

    _category_ticks(ax, keys)
    ax.set_ylabel("Traces performing it this way", fontsize=FONT_LABEL)
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
    keys, statuses, counts = _status_payload(frame, alignments, threshold)
    if not keys:
        _no_activities(output_dir, "stacked_bar")
        return

    x = np.arange(len(keys))
    fig, ax = plt.subplots(figsize=_bar_figsize(keys))
    ax.set_facecolor("#fafbfc")
    bottoms = np.zeros(len(keys))
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
    _category_ticks(ax, keys)
    ax.set_ylabel("Traces performing it this way", fontsize=FONT_LABEL)
    ax.yaxis.set_major_locator(plt.MaxNLocator(integer=True))
    ax.set_ylim(0, ymax * 1.16)
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_stacked_bar.svg"))


def task27_table(frame, alignments, output_dir: str,
                 threshold: float = CONFORMANT_DEFAULT):
    """The payload as text: the same crosstab the matrix draws.

    It used to be task04's per-trace move table, which put the traces across
    the top while every idiom beside it compared the two status groups — the
    one figure in the set that answered a different question. The per-trace
    resolution is what the chevron and the BPMN are for.
    """
    keys, statuses, counts = _status_payload(frame, alignments, threshold)
    if not keys:
        _no_activities(output_dir, "table")
        return

    cell_text = [[_category(k)] + [f"{int(v)}" if v else "—" for v in counts[i]]
                 for i, k in enumerate(keys)]
    col_labels = ["Activity (Move Type)"] + list(statuses)

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig_w = max(7.0, 4.2 + 1.8 * len(statuses))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.88],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=10.5,
        scale_xy=(1, 1.7),
        zebra=True,
    )
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_table.svg"))


def task27_matrix(frame, alignments, output_dir: str,
                  threshold: float = CONFORMANT_DEFAULT):
    """The same counts as numbers on white cells. The heatmap is the
    colour."""
    keys, statuses, counts = _status_payload(frame, alignments, threshold)
    if not keys:
        _no_activities(output_dir, "matrix")
        return

    fig, ax = plt.subplots(figsize=_grid_figsize(keys))
    draw_value_heatmap(fig, ax, counts, [_category(k) for k in keys], statuses,
                       xlabel="Conformance status", cell_fmt="{:.0f}",
                       annotate=True, rotate_xticks=0, colorless=True)
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_matrix.svg"))


def task27_heatmap(frame, alignments, output_dir: str,
                   threshold: float = CONFORMANT_DEFAULT):
    """The same counts as colour. The matrix is the numbers."""
    keys, statuses, counts = _status_payload(frame, alignments, threshold)
    if not keys:
        _no_activities(output_dir, "heatmap")
        return

    fig, ax = plt.subplots(figsize=_grid_figsize(keys))
    draw_value_heatmap(fig, ax, counts, [_category(k) for k in keys], statuses,
                       xlabel="Conformance status",
                       cbar_label="Traces performing it this way",
                       annotate=False, rotate_xticks=0,
                       vmax=max(float(counts.max()), 1.0))
    ax.set_title(_TASK27_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task27_heatmap.svg"))


# ---------------------------------------------------------------------------
# Medium idioms
# ---------------------------------------------------------------------------

def _rank_nonconformant(nonconf, rule: str):
    """The non-conformant variants in the order `rule` wants them shown.

    Every rule ranks *within* the slice the threshold cut, so whichever it
    returns is non-conformant by this task's own definition — the rule cannot
    contradict the threshold it is applied under.

    The axis is fitness rather than a count of deviating moves: it is the
    measure the threshold itself uses, and the variant frame carries it already
    (a per-variant violation count would mean replaying every representative
    trace for a spread the fitness axis already gives).
    """
    if nonconf.empty:
        return nonconf
    if rule == "worst_fitness":
        return nonconf.sort_values(["fitness", "rep_trace_index"])
    if rule == "first_in_log":
        return nonconf.sort_values("rep_trace_index")
    if rule == "fitness_gap":
        return nonconf.sort_values(["fitness", "rep_trace_index"])
    return nonconf           # most_frequent: build_variant_df's own order


def _spread_over_fitness(ranked, count: int) -> list:
    """`count` variants spread evenly over the fitness range, both ends included.

    Taking the head of a fitness-sorted slice would give the `count` worst,
    which is the worst_fitness rule again; the point here is contrast, so the
    picks are evenly spaced along the sorted slice.
    """
    n = len(ranked)
    if count >= n:
        return [int(r) for r in ranked["rep_trace_index"]]
    if count == 1:
        return [int(ranked["rep_trace_index"].iloc[0])]
    step = (n - 1) / (count - 1)
    seen, out = set(), []
    for k in range(count):
        pos = int(round(k * step))
        if pos not in seen:
            seen.add(pos)
            out.append(int(ranked["rep_trace_index"].iloc[pos]))
    return out


def _selected_indices(log, vdf, *, threshold, trace_ids, count, rule="most_frequent") -> list:
    """The trace indices this task shows — read by *every* idiom, not just some.

    ``count`` of each status, not ``count`` in total: the contrast is the
    question, so both sides are always on screen. Without named ids the variants
    are picked as representatives — one trace per variant (its
    ``rep_trace_index``) — conformant ones first, so "Trace 1" is the conformant
    exemplar. ``rule`` orders the deviating side only (see
    ``_rank_nonconformant``); the conformant side is always the most frequent
    variants, there being no second question to ask of the side that conforms.

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
    ranked = _rank_nonconformant(nonconf, rule)
    deviating = (_spread_over_fitness(ranked, count) if rule == "fitness_gap"
                 else [int(r) for r in ranked["rep_trace_index"].head(count)])
    return [int(r) for r in conform["rep_trace_index"].head(count)] + deviating


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
        # No table here: task27_table draws the status crosstab the rest of
        # the set draws. Only the chevron and the BPMN stay per trace.


def generate(log, fitness_df, alignments, output_dir: str, model_path: str = None,
             conformant_threshold: float = CONFORMANT_DEFAULT, trace_ids=None,
             trace_count=1, nonconformant_pick_rule="most_frequent"):
    """Generate all Task ID 27 SVGs into output_dir.

    model_path is required for the flow_chart_elaborate idiom (the annotated
    BPMN); when absent that idiom is skipped.

    ``conformant_threshold`` is the fitness at or above which a variant counts as
    conformant — the cut this task's whole question rests on, and previously
    fixed at 1.0 in code. ``trace_count`` is how many traces of *each* status the
    chevron, BPMN and table idioms show, and ``nonconformant_pick_rule`` which
    of the deviating variants those are.

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
    if not n_conform or not n_nonconf:
        # The contrast is the question. A threshold that puts every variant on
        # one side leaves nothing to compare, and half a figure would read as a
        # finding about the log rather than about the threshold.
        side = "conformant" if not n_conform else "non-conformant"
        logger.warning(
            "      Skipped Task 27: a threshold of %s leaves no %s variant "
            "(fitness ranges %.3f–%.3f).",
            format_threshold(conformant_threshold), side,
            float(vdf["fitness"].min()), float(vdf["fitness"].max()))
        return

    indices = _selected_indices(log, vdf, threshold=conformant_threshold,
                                trace_ids=trace_ids, count=trace_count,
                                rule=nonconformant_pick_rule)
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
    task27_table(frame, alignments, output_dir, conformant_threshold)
    task27_matrix(frame, alignments, output_dir, conformant_threshold)
    task27_heatmap(frame, alignments, output_dir, conformant_threshold)

    _task27_alignment_figures(log, alignments, indices, model_path, output_dir)
