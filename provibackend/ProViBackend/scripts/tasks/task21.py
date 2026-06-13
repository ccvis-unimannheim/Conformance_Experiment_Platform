"""
tasks/task21.py – Task ID 21: Explain / Identify / Reasons for guideline violations
(exploratory composite).

Goal **Explain** / Means **Identify** / Characteristics *Reasons for guideline
violations*:
    "What are the underlying reasons for guideline violations of traces? This task
     focuses on the analyst finding potential reasons through the visualization
     themselves."

The exploratory composite of the Reasons family. Distinct from its siblings:
ID 13 (attribute-centric, `task13.py`), ID 18 (event-centric, `task18.py`),
ID 20 (decision tree, `task20.py`). Here the means is **Identify through the
visualization**: surface candidate reasons of BOTH kinds — attributes (from
task13) and responsible events (from task18) — side by side, neutrally ranked,
**without asserting a single conclusion**, so the analyst identifies the reasons.

Design (settled):
  * Reuse + compose, never re-derive: built on top of `task13.py` (attribute
    evidence) and `task18.py` (event responsibility). No new alignment runs.
  * Exploratory / neutral presentation: candidates are ranked but never
    pre-highlighted as "the" reason; no conclusion lines or labels. The viz lays
    out the evidence; the analyst concludes. (Same spirit as task25's discovery
    principle, applied to reasons.)
  * Unified candidate-reason set: attribute candidates (association strength) and
    event candidates (responsibility share) are combined into ONE ranking. The two
    native scales are made comparable by **min-max normalization within each kind**
    onto a common [0, 1] axis (each kind's strongest candidate maps to 1.0), so
    neither kind is structurally favoured; candidates are then ranked together.
  * Top-N unified candidate reasons (TOP_N).

Scope = the 7 "High" idioms. Stems → canonical slug after the pipeline rename:
    task21_bar_chart.svg                       → bar_chart
    task21_scatter_plot.svg                    → scatterplot   (reuses task13's scatter)
    task21_table.svg                           → table
    task21_table_and_bar_chart.svg             → table_bar_chart
    task21_parallel_sets.svg                   → parallel_sets
    task21_flow_chart_and_table.svg            → flow_chart_table
    task21_flow_chart_elaborate_bpmn_table.svg → flow_chart_elaborate_table

Public API:
    generate(log, alignments, model_path, output_dir, candidate_attributes=None)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table", "table_bar_chart",
          "parallel_sets", "flow_chart_table", "flow_chart_elaborate_table"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets, render_empty_state_svg, wrap_text,
    chevron_nodes_from_alignment_rows, draw_chevron_strip, chevron_figure_width,
    parse_bpmn_model, compose_bpmn_panels, alignment_violation_node_style,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# This task is a composite — it depends on task13/task18 helpers. Fail loudly if
# they cannot be imported (per spec).
try:
    import tasks.task13 as task13
    from tasks.task13 import _build_evidence_frame, _rank_attributes, _bucket_assign, CANDIDATE_ATTRIBUTES
    from tasks.task18 import task18_responsibility
    from tasks.task20 import task20_trace_feature_dataframe
    from tasks.task28 import build_task28_context
except ImportError as e:   # pragma: no cover - import-time guard
    raise ImportError(
        "task21 is the exploratory composite of the Reasons family and depends on "
        "task13.py and task18.py helpers, which could not be imported: "
        f"{e}. Ensure tasks/task13.py and tasks/task18.py are present and importable."
    ) from e


TOP_N = 12   # unified candidate reasons kept

# Neutral two-tone palette for the two candidate kinds (no kind is emphasised).
_KIND_COLORS = {"attribute": GREY_MED, "event": GREY_LIGHT}

_EMPTY_STEMS = [
    ("task21_bar_chart.svg",                       "Candidate Reason Ranking"),
    ("task21_scatter_plot.svg",                    "Attribute Value vs. Violations"),
    ("task21_table.svg",                           "Candidate Reasons"),
    ("task21_table_and_bar_chart.svg",             "Candidate Reasons"),
    ("task21_parallel_sets.svg",                   "Candidate Reason vs. Violation"),
    ("task21_flow_chart_and_table.svg",            "Violation Flow & Candidate Reasons"),
    ("task21_flow_chart_elaborate_bpmn_table.svg", "Violation Locations & Candidate Reasons"),
]


# ---------------------------------------------------------------------------
# Unified candidate-reason assembly
# ---------------------------------------------------------------------------

def _unified_candidates(attr_ranking, resp, top_n=TOP_N):
    """Combine attribute candidates (task13) + event candidates (task18) into one
    ranked list. Scores are min-max-normalized within each kind so the two scales
    (association strength vs. responsibility share) share a common [0, 1] axis."""
    candidates = []

    max_attr = max((r["strength"] for r in attr_ranking), default=0.0) or 1.0
    for r in attr_ranking:
        candidates.append({
            "reason": r["label"],
            "kind": "attribute",
            "score": r["strength"] / max_attr,
            "raw": f"{r['measure']} {r['strength']:.2f}",
            "evidence": r["direction"],
            "_attr_col": r["col"],
            "_attr_type": r["type"],
        })

    recs = resp.get("records", [])
    max_share = max((r["n_violations"] for r in recs), default=0) or 1
    for r in recs:
        candidates.append({
            "reason": f"{r['activity']} ({r['move_type']})",
            "kind": "event",
            "score": r["n_violations"] / max_share,
            "raw": f"{r['pct']:.1f}% of violations",
            "evidence": f"{r['n_traces']} traces; {r['context']}",
            "_event_rec": r,
        })

    candidates.sort(key=lambda c: c["score"], reverse=True)
    return candidates[:top_n]


def _candidate_table_data(candidates):
    """(cell_text, col_labels, col_widths) for the unified candidate-reasons table.
    Long cells are wrapped so they stay within their column (matplotlib tables don't
    auto-wrap)."""
    col_labels = ["Candidate reason", "Kind", "Score", "Evidence note"]
    col_widths = [0.27, 0.10, 0.10, 0.53]
    cell_text = [[wrap_text(c["reason"], 22), c["kind"], f"{c['score']:.2f}",
                  wrap_text(f"{c['raw']} — {c['evidence']}", 40)] for c in candidates]
    return cell_text, col_labels, col_widths


def _candidate_rows_singleline(candidates, note_max: int = 46):
    """Single-line rows for the SVG (compose_bpmn_panels) table, which can't wrap;
    the evidence note is truncated instead."""
    def _short(s):
        return s if len(s) <= note_max else s[:note_max - 1] + "…"
    rows = [[c["reason"], c["kind"], f"{c['score']:.2f}",
             _short(f"{c['raw']} — {c['evidence']}")] for c in candidates]
    return rows, ["Candidate reason", "Kind", "Score", "Evidence note"]


def _parallel_matrix(bucket_per_trace, left_labels, violation):
    """Build a (len(left_labels) x 2) matrix: Dim2 = violation present (yes/no)."""
    matrix = np.zeros((len(left_labels), 2))
    index_of = {lab: i for i, lab in enumerate(left_labels)}
    for b, viol in zip(bucket_per_trace, violation):
        if b is None or b not in index_of:
            continue
        matrix[index_of[b], 0 if viol else 1] += 1
    return matrix


# ---------------------------------------------------------------------------
# Idiom renderers (neutral, non-concluding)
# ---------------------------------------------------------------------------

def task21_bar_chart(candidates, output_dir):
    """Unified candidate-reason ranking on a single axis (attributes AND events
    together). Colour encodes kind only; no candidate is pre-highlighted."""
    path = os.path.join(output_dir, "task21_bar_chart.svg")
    if not candidates:
        render_empty_state_svg(path, "Candidate Reason Ranking", "No candidate reasons found.")
        return
    labels = [c["reason"] for c in candidates][::-1]
    scores = [c["score"] for c in candidates][::-1]
    colors = [_KIND_COLORS.get(c["kind"], GREY_MED) for c in candidates][::-1]

    fig, ax = plt.subplots(figsize=(11, max(4.0, len(candidates) * 0.5 + 1.5)))
    y = np.arange(len(labels))
    ax.barh(y, scores, color=colors, edgecolor="white")
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_xlim(0, 1.0)
    ax.set_xlabel("Normalized candidate score (within-kind min-max)", fontsize=FONT_LABEL)
    for i, s in enumerate(scores):
        ax.text(min(s + 0.01, 0.99), i, f"{s:.2f}", va="center", fontsize=FONT_ANNOT - 1)
    ax.set_title("Candidate Reasons for Guideline Violations (attributes + events)",
                 fontsize=FONT_TITLE)
    ax.legend(handles=[mpatches.Patch(color=c, label=k) for k, c in _KIND_COLORS.items()],
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task21_scatter_plot(attr_meta, evidence_df, output_dir):
    """Reuse task13's scatter (x = strongest numeric attribute candidate, y =
    violation count, colour = conformant / non-conformant), renamed to the task21
    stem. Evidence to explore — no trend line."""
    path = os.path.join(output_dir, "task21_scatter_plot.svg")
    if not attr_meta or evidence_df is None or evidence_df.empty:
        render_empty_state_svg(path, "Attribute Value vs. Violations",
                               "No attribute evidence to plot.")
        return
    # Reuse the task13 renderer verbatim, then rename its output stem.
    task13.task13_scatter_plot(attr_meta, evidence_df, output_dir)
    src = os.path.join(output_dir, "task13_scatter_plot.svg")
    if os.path.exists(src):
        os.replace(src, path)


def task21_table(candidates, output_dir):
    """Unified candidate-reasons table: Candidate reason | Kind | Score | Evidence note."""
    path = os.path.join(output_dir, "task21_table.svg")
    if not candidates:
        render_empty_state_svg(path, "Candidate Reasons", "No candidate reasons found.")
        return
    cell_text, col_labels, col_widths = _candidate_table_data(candidates)
    fig_h = max(3.0, 1.4 + len(cell_text) * 0.48)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    make_table(ax, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.05, 0.96, 0.84], col_widths=col_widths,
               font_size=9.5, cell_pad=0.08)
    ax.set_title("Candidate Reasons for Guideline Violations (ranked, for exploration)",
                 fontsize=FONT_TITLE, pad=10)
    save_svg(fig, path)


def task21_table_and_bar_chart(candidates, output_dir):
    """Unified candidate-reasons table (left) + the unified ranking bar (right)."""
    path = os.path.join(output_dir, "task21_table_and_bar_chart.svg")
    if not candidates:
        render_empty_state_svg(path, "Candidate Reasons", "No candidate reasons found.")
        return
    cell_text, col_labels, col_widths = _candidate_table_data(candidates)

    fig = plt.figure(figsize=(17, max(3.4, 1.6 + len(candidates) * 0.5)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.7, 1.0], wspace=0.40)

    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    make_table(ax_t, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.05, 0.96, 0.84], col_widths=col_widths,
               font_size=9, cell_pad=0.07)
    ax_t.set_title("Candidate Reasons (ranked)", fontsize=FONT_TITLE, pad=8)

    ax_b = fig.add_subplot(gs[1])
    labels = [c["reason"] for c in candidates][::-1]
    scores = [c["score"] for c in candidates][::-1]
    colors = [_KIND_COLORS.get(c["kind"], GREY_MED) for c in candidates][::-1]
    y = np.arange(len(labels))
    ax_b.barh(y, scores, color=colors, edgecolor="white")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
    ax_b.set_xlim(0, 1.0)
    ax_b.set_xlabel("Normalized score", fontsize=FONT_LABEL)
    for i, s in enumerate(scores):
        ax_b.text(min(s + 0.02, 0.98), i, f"{s:.2f}", va="center", fontsize=FONT_ANNOT - 1)
    ax_b.legend(handles=[mpatches.Patch(color=c, label=k) for k, c in _KIND_COLORS.items()],
                frameon=False, fontsize=FONT_ANNOT - 1, loc="lower right")
    ax_b.spines[["top", "right"]].set_visible(False)
    ax_b.set_title("Unified ranking", fontsize=FONT_TITLE, pad=8)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task21_parallel_sets(candidates, evidence_df, attr_meta, resp, output_dir):
    """Dimension 1 = the top candidate-reason bucket (top attribute's bucket OR the
    responsible-activity group), Dimension 2 = violation present (yes / no);
    ribbon width = #traces."""
    path = os.path.join(output_dir, "task21_parallel_sets.svg")
    if not candidates or evidence_df is None or evidence_df.empty:
        render_empty_state_svg(path, "Candidate Reason vs. Violation",
                               "No candidate reasons to explore.")
        return

    top = candidates[0]
    violation = evidence_df["violation"].to_numpy()

    if top["kind"] == "attribute":
        res = _bucket_assign(evidence_df[top["_attr_col"]].tolist(), top["_attr_type"])
        if res is None:
            render_empty_state_svg(path, "Candidate Reason vs. Violation",
                                   "Top attribute candidate cannot be bucketed.")
            return
        bucket_per_trace, left_labels = res
        left_title = top["reason"]
    else:
        rec = top["_event_rec"]
        affected = rec["traces"]
        present_lbl = f"{rec['activity']} responsible"
        left_labels = [present_lbl, "Other traces"]
        bucket_per_trace = [present_lbl if ti in affected else "Other traces"
                            for ti in evidence_df["trace_index"]]
        left_title = f"{rec['activity']} ({rec['move_type']})"

    matrix = _parallel_matrix(bucket_per_trace, left_labels, violation)
    fig, ax = plt.subplots(figsize=(9, max(6, len(left_labels) * 0.5 + 2)))
    ax.axis("off")
    left_colors = [GREY_MED if i % 2 == 0 else GREY_LIGHT for i in range(len(left_labels))]
    draw_parallel_sets(
        ax, left_labels, ["Violation", "No violation"], matrix, left_colors,
        right_colors=[GREY_DARK, GREY_LIGHTER],
        left_title=left_title, right_title="Guideline violation",
    )
    # Title above the column headers (which draw_parallel_sets places at y=1.08).
    fig.suptitle("Top Candidate Reason vs. Guideline Violation", fontsize=FONT_TITLE, y=0.99)
    fig.subplots_adjust(top=0.80)
    save_svg(fig, path)


def task21_flow_chart_and_table(ctx, candidates, output_dir):
    """Chevron of a representative violating trace + the unified candidate-reasons table.
    Stem 'flow_chart_and_table' → canonical slug 'flow_chart_table'."""
    path = os.path.join(output_dir, "task21_flow_chart_and_table.svg")
    if ctx is None or not candidates:
        render_empty_state_svg(path, "Violation Flow & Candidate Reasons",
                               "No usable alignment / no candidate reasons.")
        return

    nodes = chevron_nodes_from_alignment_rows(ctx["rows"])
    cell_text, col_labels, col_widths = _candidate_table_data(candidates)

    fig_w = max(14.0, chevron_figure_width(nodes))
    fig_h = max(7.0, 3.4 + len(candidates) * 0.48)
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.0, max(1.4, 0.48 * len(candidates) + 0.8)],
                           hspace=0.30)

    ax_flow = fig.add_subplot(gs[0])
    draw_chevron_strip(ax_flow, nodes, fontsize=10)
    ax_flow.set_title(
        f"Representative Violating Trace ({ctx['trace_label']}, fitness={ctx['fitness']:.3f})",
        fontsize=FONT_TITLE, pad=6)

    ax_tab = fig.add_subplot(gs[1])
    ax_tab.axis("off")
    make_table(ax_tab, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.03, 0.05, 0.94, 0.84], col_widths=col_widths,
               font_size=9, cell_pad=0.07)
    ax_tab.set_title("Candidate Reasons to Explore (ranked, attributes + events)",
                     fontsize=FONT_TITLE, pad=6)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task21_flow_chart_elaborate_bpmn_table(ctx, candidates, model_path, output_dir):
    """Desired model with violation locations annotated + the unified candidate-reasons
    table. Stem → canonical slug 'flow_chart_elaborate_table'."""
    path = os.path.join(output_dir, "task21_flow_chart_elaborate_bpmn_table.svg")
    if ctx is None or not model_path or not candidates:
        render_empty_state_svg(path, "Violation Locations & Candidate Reasons",
                               "No alignment, model, or candidate reasons available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task21: BPMN parse failed: {e}")
        render_empty_state_svg(path, "Violation Locations & Candidate Reasons",
                               "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, "Violation Locations & Candidate Reasons",
                               "No BPMN geometry to render.")
        return

    panels = [{
        "parsed": parsed,
        "node_style_fn": alignment_violation_node_style(ctx["rows"]),
        "subtitle": (f"Violation locations on the desired model "
                     f"({ctx['trace_label']}, fitness={ctx['fitness']:.3f})"),
    }]
    table_rows, table_cols = _candidate_rows_singleline(candidates)
    compose_bpmn_panels(
        panels,
        path,
        title="Where Violations Sit (flow) & Candidate Reasons to Explore (table)",
        legend_items=[
            (GREY_MED,    "#444444", 3, "Model move (skipped step)"),
            (GREY_LIGHT,  "#444444", 3, "Mismatch move"),
            (GREY_LIGHTER,   "#666666", 2, "Conform (synchronous)"),
            ("white", "#888888", 2, "Not on this trace"),
        ],
        table_rows=table_rows,
        table_cols=table_cols,
    )


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
    """Generate all Task ID 21 SVGs into output_dir by composing task13's attribute
    evidence and task18's event responsibility into one neutral, exploratory ranking.
    Alignments are reused from the central run (never recomputed)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 21 visualizations ---")

    if not log or not alignments:
        logger.warning("      task21: empty log / alignments — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No log or alignment data available.")
        return

    if candidate_attributes is None:
        candidate_attributes = list(CANDIDATE_ATTRIBUTES)

    # Attribute evidence (task13) + event responsibility (task18).
    feat = task20_trace_feature_dataframe(log, alignments)
    evidence_df, attr_meta = (None, [])
    if feat is not None and not feat.empty:
        evidence_df, attr_meta = _build_evidence_frame(log, feat, candidate_attributes)

    resp = task18_responsibility(log, alignments, candidate_attributes)

    n_viol = int(evidence_df["violation"].sum()) if evidence_df is not None else 0
    if n_viol == 0 and not resp.get("records"):
        logger.warning("      task21: no guideline violations — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "All traces conformant — no reasons to explore.")
        return

    attr_ranking = _rank_attributes(evidence_df, attr_meta) if attr_meta else []
    candidates = _unified_candidates(attr_ranking, resp)
    if not candidates:
        logger.warning("      task21: no candidate reasons assembled — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No candidate reasons could be assembled.")
        return

    logger.info("      task21: unified candidates — " +
                ", ".join(f"{c['reason']}[{c['kind']}]={c['score']:.2f}" for c in candidates[:5]) +
                (" …" if len(candidates) > 5 else ""))

    ctx = build_task28_context(alignments)

    task21_bar_chart(candidates, output_dir)
    task21_scatter_plot(attr_meta, evidence_df, output_dir)
    task21_table(candidates, output_dir)
    task21_table_and_bar_chart(candidates, output_dir)
    task21_parallel_sets(candidates, evidence_df, attr_meta, resp, output_dir)
    task21_flow_chart_and_table(ctx, candidates, output_dir)
    task21_flow_chart_elaborate_bpmn_table(ctx, candidates, model_path, output_dir)
