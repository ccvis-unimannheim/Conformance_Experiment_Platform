"""
tasks/task21.py – Task ID 21: Explain / Identify / Reasons for guideline violations
(exploratory composite).

Goal **Explain** / Means **Identify** / Characteristics *Reasons for guideline
violations*:
    "What are the underlying reasons for guideline violations of traces? This task
     focuses on the analyst finding potential reasons through the visualization
     themselves."

The exploratory member of the Reasons family. Its siblings are ID 13
(attribute-centric, `task13.py`), ID 18 (event-centric, `task18.py`) and ID 20
(decision tree, `task20.py`). Here the means is **Identify through the
visualization**: the candidate reasons are ranked neutrally and **no single
conclusion is asserted**, so the analyst identifies the reasons.

Design (settled):
  * Reuse, never re-derive: built on `task13.py`'s attribute evidence. No new
    alignment runs.
  * Exploratory / neutral presentation: candidates are ranked but never
    pre-highlighted as "the" reason; no conclusion lines or labels. The viz lays
    out the evidence; the analyst concludes. (Same spirit as task25's discovery
    principle, applied to reasons.)
  * **Only the attributes the admin selected.** This used to rank responsible
    activities from task18 alongside them, under a score min-max-normalized
    within each kind. Both halves were problems: an activity is not an
    attribute, so the figure answered with rows the admin had not asked for,
    and the normalization made each kind's strongest candidate 1.00 whatever
    its real strength. Showing only what was selected outranks avoiding overlap
    with task13, and that overlap is accepted deliberately.
  * Top-N candidate reasons (TOP_N), ranked by association strength.
  * **Category-level breakdown, for every ranked candidate — not just the
    strongest one.** bar_chart, table and parallel_sets each render one panel
    per ranked candidate, showing that attribute's own buckets and their
    violation rates. A single association number was not enough on its own —
    the analyst needs to see *which* category of an attribute drives the
    association, for every candidate being compared, not only the top-ranked
    one.
  * **Own rendering, task13's data only.** The three idioms below are task21's
    own matplotlib code — they only reuse task13's small, pure data helpers
    (`_build_evidence_frame`, `_rank_attributes`, `_bucket_rates`,
    `_bucket_assign`), never task13's chart-drawing functions directly. That
    keeps the two tasks' figures independently changeable: a future tweak to
    task13's own bar_chart/table/parallel_sets does not silently change
    task21's, and vice versa, even though both currently look similar.

Scope = 3 idioms (bar_chart, table, parallel_sets). table_bar_chart,
flow_chart_table and flow_chart_elaborate_table were dropped: each just
bundled the same candidate ranking next to something unrelated to the
ranking itself (an arbitrary single trace's flow/BPMN), without adding new
information.
Stems → canonical slug after the pipeline rename:
    task21_bar_chart.svg     → bar_chart
    task21_table.svg         → table
    task21_parallel_sets.svg → parallel_sets

Public API:
    generate(log, alignments, model_path, output_dir, candidate_attributes=None)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "parallel_sets"]


# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "violation_rate"
SPLIT_STRATEGY = None  # admin chooses

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

from shared import (
    save_svg, make_table, draw_parallel_sets, render_empty_state_svg, wrap_text,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# This task builds on task13's attribute evidence. Fail loudly if it cannot be
# imported (per spec). Only task13's *data* helpers are reused (see the module
# docstring) — bar_chart/table/parallel_sets below are task21's own rendering.
try:
    from tasks.task13 import (
        _build_evidence_frame, _rank_attributes, _bucket_rates, _bucket_assign,
        discover_candidate_attributes,
    )
    from tasks.task20 import task20_trace_feature_dataframe
except ImportError as e:   # pragma: no cover - import-time guard
    raise ImportError(
        "task21 is the exploratory member of the Reasons family and depends on "
        f"task13.py's helpers, which could not be imported: {e}. Ensure "
        "tasks/task13.py is present and importable."
    ) from e


TOP_N = 12   # candidate reasons kept

# Shared heading for bar_chart/table/parallel_sets.
_TITLE = "Candidate Reasons for Guideline Violations"

# 4-shade rotation for a candidate's own buckets in parallel_sets (mirrors the
# same grey ramp task13 uses for its own per-attribute panels).
_GREY_PALETTE = [GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER]

_EMPTY_STEMS = [
    ("task21_bar_chart.svg",     "Candidate Reason Ranking"),
    ("task21_table.svg",         "Candidate Reasons"),
    ("task21_parallel_sets.svg", "Candidate Reason vs. Violation"),
]


# ---------------------------------------------------------------------------
# Idiom renderers (neutral, non-concluding). Own rendering code — only the
# data helpers above (_bucket_rates/_bucket_assign, from task13) are reused.
# ---------------------------------------------------------------------------

def task21_bar_chart(ranking, evidence_df, output_dir):
    """Small multiples: one bar-group panel per ranked candidate, showing that
    attribute's own buckets and violation rate — not just one aggregate
    association number. Panels stay in `ranking`'s order (strongest first)."""
    path = os.path.join(output_dir, "task21_bar_chart.svg")
    if not ranking or evidence_df is None or evidence_df.empty:
        render_empty_state_svg(path, "Candidate Reason Ranking", "No candidate reasons found.")
        return
    violation = evidence_df["violation"].to_numpy()
    panels = []
    for r in ranking:
        res = _bucket_rates(evidence_df[r["col"]].tolist(), r["type"], violation)
        if res is not None:
            panels.append((r, res))
    if not panels:
        render_empty_state_svg(path, _TITLE, "No candidate attribute had enough variance to bucket.")
        return

    ncols = len(panels)
    fig, axes = plt.subplots(1, ncols, figsize=(max(5.0, ncols * 4.2), 5.0), squeeze=False)
    for ax, (r, (labels, rates, counts)) in zip(axes[0], panels):
        pos = np.arange(len(labels))
        ax.bar(pos, rates, color=GREY_MED, edgecolor="white")
        for p, rate, c in zip(pos, rates, counts):
            ax.text(p, rate + 1.5, f"{rate:.0f}%\n(n={c})", ha="center", va="bottom",
                    fontsize=FONT_ANNOT - 1, color="#333333")
        ax.set_xticks(pos)
        ax.set_xticklabels(labels, fontsize=FONT_ANNOT - 1)
        ax.set_xlabel(f"{r['label']}  (assoc.={r['strength']:.2f})", fontsize=FONT_LABEL)
        ax.set_ylim(0, 100)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.45)
        ax.set_axisbelow(True)
    axes[0][0].set_ylabel("Violation rate (%)", fontsize=FONT_LABEL)
    fig.suptitle(_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task21_table(ranking, evidence_df, output_dir):
    """Small multiples: one bucket-breakdown table per ranked candidate
    (Bucket | # Traces | Violation Rate), instead of one row per candidate
    with just its aggregate score."""
    path = os.path.join(output_dir, "task21_table.svg")
    if not ranking or evidence_df is None or evidence_df.empty:
        render_empty_state_svg(path, "Candidate Reasons", "No candidate reasons found.")
        return
    violation = evidence_df["violation"].to_numpy()
    panels = []
    for r in ranking:
        res = _bucket_rates(evidence_df[r["col"]].tolist(), r["type"], violation)
        if res is not None:
            panels.append((r, res))
    if not panels:
        render_empty_state_svg(path, _TITLE, "No candidate attribute had enough variance to bucket.")
        return

    ncols = len(panels)
    max_rows = max(len(labels) for _, (labels, _, _) in panels)
    fig_h = max(3.2, 1.6 + max_rows * 0.5)
    fig, axes = plt.subplots(1, ncols, figsize=(max(5.0, ncols * 3.8), fig_h), squeeze=False)
    for ax, (r, (labels, rates, counts)) in zip(axes[0], panels):
        ax.axis("off")
        cell_text = [[lab, str(c), f"{rate:.0f}%"] for lab, rate, c in zip(labels, rates, counts)]
        make_table(
            ax,
            cell_text=cell_text,
            col_labels=["Bucket", "# Traces", "Violation Rate"],
            bbox=[0.02, 0.06, 0.96, 0.74],
            col_widths=[0.46, 0.27, 0.27],
            font_size=9.5,
            cell_pad=0.08,
        )
        ax.set_title(f"{r['label']}\n(assoc.={r['strength']:.2f})", fontsize=FONT_LABEL, pad=8)
    fig.suptitle(_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task21_parallel_sets(ranking, evidence_df, output_dir):
    """Small multiples: one parallel-sets diagram per ranked candidate (bucket
    vs. violation present), not just the single top-ranked one — every
    candidate being compared gets its category breakdown shown, side by side."""
    path = os.path.join(output_dir, "task21_parallel_sets.svg")
    if not ranking or evidence_df is None or evidence_df.empty:
        render_empty_state_svg(path, "Candidate Reason vs. Violation",
                               "No candidate reasons to explore.")
        return
    violation = evidence_df["violation"].to_numpy()
    right_labels = ["Violation", "No violation"]

    panels = []
    for r in ranking:
        res = _bucket_assign(evidence_df[r["col"]].tolist(), r["type"])
        if res is None:
            continue
        bucket_per_trace, left_labels = res
        matrix = np.zeros((len(left_labels), 2))
        index_of = {lab: i for i, lab in enumerate(left_labels)}
        for b, viol in zip(bucket_per_trace, violation):
            if b is None:
                continue
            matrix[index_of[b], 0 if viol else 1] += 1
        panels.append((r, left_labels, matrix))

    if not panels:
        render_empty_state_svg(path, "Candidate Reason vs. Violation",
                               "No candidate attribute could be bucketed.")
        return

    ncols = len(panels)
    fig, axes = plt.subplots(1, ncols, figsize=(max(7.0, ncols * 5.0), 6.0), squeeze=False)
    for ax, (r, left_labels, matrix) in zip(axes[0], panels):
        ax.axis("off")
        left_colors = [_GREY_PALETTE[i % len(_GREY_PALETTE)] for i in range(len(left_labels))]
        draw_parallel_sets(
            ax, left_labels, right_labels, matrix, left_colors,
            right_colors=[GREY_DARK, GREY_LIGHTER],
            # No right_title: the bars below are already individually labelled
            # "Violation"/"No violation", so a column header would be redundant
            # and, with panels this narrow, collide with a long left_title.
            left_title=wrap_text(r["label"].replace("_", " "), 14), right_title="",
        )
    fig.suptitle(_TITLE, fontsize=FONT_TITLE, y=0.99)
    fig.subplots_adjust(top=0.78, wspace=0.5)
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Fallback
# ---------------------------------------------------------------------------

def _emit_all_empty(output_dir, message: str):
    for fname, title in _EMPTY_STEMS:
        render_empty_state_svg(os.path.join(output_dir, fname), title, message)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, model_path, output_dir: str, candidate_attributes=None):
    """Generate all Task ID 21 SVGs into output_dir from task13's attribute
    evidence, as one neutral, exploratory ranking. Alignments are reused from the
    central run (never recomputed)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 21 visualizations ---")

    if not log or not alignments:
        logger.warning("      task21: empty log / alignments — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No log or alignment data available.")
        return

    # Attribute evidence (task13).
    feat = task20_trace_feature_dataframe(log, alignments)
    evidence_df, attr_meta = (None, [])
    if feat is not None and not feat.empty:
        if candidate_attributes is None:
            candidate_attributes = discover_candidate_attributes(log, feat)
        evidence_df, attr_meta = _build_evidence_frame(log, feat, candidate_attributes)

    n_viol = int(evidence_df["violation"].sum()) if evidence_df is not None else 0
    if n_viol == 0:
        logger.warning("      task21: no guideline violations — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "All traces conformant — no reasons to explore.")
        return

    attr_ranking = _rank_attributes(evidence_df, attr_meta) if attr_meta else []
    ranking = attr_ranking[:TOP_N]
    if not ranking:
        logger.warning("      task21: no candidate reasons assembled — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No candidate reasons could be assembled.")
        return

    logger.info(f"      -> attributes: {candidate_attributes}")
    logger.info("      task21: candidates — " +
                ", ".join(f"{r['label']}={r['strength']:.2f}" for r in ranking[:5]) +
                (" …" if len(ranking) > 5 else ""))

    task21_bar_chart(ranking, evidence_df, output_dir)
    task21_table(ranking, evidence_df, output_dir)
    task21_parallel_sets(ranking, evidence_df, output_dir)
