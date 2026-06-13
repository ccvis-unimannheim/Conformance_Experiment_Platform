"""
tasks/task19.py – Task ID 19: Explain / Discover / Effects of goal deviations.

Goal **Explain** / Means **Discover** / Characteristics *Effects of goal
deviations*:
    "What is the effect of a guideline violation on overall process goals? We first
     need to formally define the process goal."

Design (settled):
  * Formal process goal := reaching the configured ``outcome_activity`` (reuses the
    exact outcome logic from task31.py; --outcome-activity, default A_ACTIVATED).
    A trace "achieves the goal" iff the outcome activity occurs in it.
  * Effect of a violation pattern v = outcome_rate(traces WITH v) −
    outcome_rate(traces WITHOUT v): the signed **risk difference** (the relative
    risk is kept alongside). Computed per violation pattern from task29's
    (activity, move-type) classification. Alignments are never re-run.
  * Demarcation: legacy task31 (ID 31) presents conformance→outcome overall;
    task19 discovers the per-violation effect on the goal. task19's unit is the
    violation pattern, its measure is the effect size.
  * Honesty constraint: every title/label says "associated with", never causal
    language — these are observational associations.
  * Top-N patterns by |risk difference| (TOP_N); patterns with tiny support
    (< MIN_SUPPORT traces) are flagged visually as low-confidence.

Scope = 7 High + 1 Medium idiom. Stems → canonical slug after the pipeline rename:
    task19_bar_chart.svg                       → bar_chart
    task19_scatter_plot.svg                    → scatterplot
    task19_table.svg                           → table
    task19_table_and_bar_chart.svg             → table_bar_chart
    task19_parallel_sets.svg                   → parallel_sets
    task19_flow_chart_and_table.svg            → flow_chart_table            (chevron exemplars + effect table)
    task19_flow_chart_elaborate_bpmn_table.svg → flow_chart_elaborate_table  (effect-coloured model + table)
    task19_flow_chart_elaborate_bpmn.svg       → flow_chart_elaborate        (Medium: effect-coloured model alone)

Public API:
    generate(log, alignments, model_path, output_dir, outcome_activity="A_ACTIVATED")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "table", "table_bar_chart", "parallel_sets",
          "flow_chart_table", "flow_chart_elaborate_table", "flow_chart_elaborate"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets, render_empty_state_svg,
    alignment_pairs_to_rows, chevron_nodes_from_alignment_rows, draw_chevron_strip,
    chevron_figure_width, parse_bpmn_model, compose_bpmn_panels, render_bpmn_annotated,
    contrasting_text_color, place_scatter_labels,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse: the exact process-goal (outcome activity) logic from task31.
import tasks.task31 as task31
# Reuse: representative-trace fallback for the chevron flow idiom.
from tasks.task28 import build_task28_context


TOP_N = 10          # patterns shown where an idiom would otherwise crowd
MIN_SUPPORT = 5     # below this #traces a pattern's effect is flagged low-confidence

_EMPTY_STEMS = [
    ("task19_bar_chart.svg",                       "Goal Effect by Violation Pattern"),
    ("task19_scatter_plot.svg",                    "Support vs. Goal Effect"),
    ("task19_table.svg",                           "Violation Effect on Process Goal"),
    ("task19_table_and_bar_chart.svg",             "Violation Effect on Process Goal"),
    ("task19_parallel_sets.svg",                   "Violation Pattern vs. Goal"),
    ("task19_flow_chart_and_table.svg",            "Goal-missing Violations & Effect Table"),
    ("task19_flow_chart_elaborate_bpmn_table.svg", "Goal Effect on the Model & Table"),
    ("task19_flow_chart_elaborate_bpmn.svg",       "Goal Effect on the Model"),
]


# ---------------------------------------------------------------------------
# Goal labelling + per-pattern effect (reuses task31 outcome + task29 patterns)
# ---------------------------------------------------------------------------

def _trace_patterns(alignments):
    """Per trace: the set of (activity, move_type) violation patterns it exhibits."""
    out = []
    for result in alignments:
        patterns = set()
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            mt = step["moveType"]
            if mt == "Synchronous Move":
                continue
            activity = step["model_move"] if mt == "Model Move" else step["log_move"]
            if not activity or str(activity) in {"-", "None", "(skip)"}:
                continue
            patterns.add((str(activity), mt))
        out.append(patterns)
    return out


def task19_effects(log, alignments, outcome_activity="A_ACTIVATED"):
    """Label each trace (goal achieved yes/no) + measure each violation pattern's
    association with the goal.

    Returns a dict:
        records      – per-pattern dicts ranked by |risk_diff|:
                       {pattern, activity, move_type, support, rate_with, rate_without,
                        risk_diff, rel_risk, low_support}
        goal         – per-trace bool array (goal achieved)
        goal_rate    – overall goal rate (%)
        n_traces     – #traces
        patterns_per_trace – list[set] (reused by the parallel-sets / flow idioms)
    """
    # Reuse task31's outcome definition (module-level activity override pattern).
    task31._OUTCOME_ACTIVITY = outcome_activity
    goal = np.array([task31._task31_positive_outcome_from_trace(t) for t in log], dtype=bool)

    patterns_per_trace = _trace_patterns(alignments)
    n = min(len(goal), len(patterns_per_trace))
    goal = goal[:n]
    patterns_per_trace = patterns_per_trace[:n]

    universe = set().union(*patterns_per_trace) if patterns_per_trace else set()
    records = []
    for (activity, move_type) in universe:
        with_mask = np.array([(activity, move_type) in s for s in patterns_per_trace], dtype=bool)
        n_with = int(with_mask.sum())
        if n_with == 0:
            continue
        without_mask = ~with_mask
        rate_with = float(goal[with_mask].mean() * 100) if n_with else 0.0
        rate_without = float(goal[without_mask].mean() * 100) if int(without_mask.sum()) else 0.0
        risk_diff = rate_with - rate_without
        rel_risk = (rate_with / rate_without) if rate_without > 0 else None  # guard div-by-zero
        records.append({
            "pattern": f"{activity} ({move_type})",
            "activity": activity,
            "move_type": move_type,
            "support": n_with,
            "rate_with": rate_with,
            "rate_without": rate_without,
            "risk_diff": risk_diff,
            "rel_risk": rel_risk,
            "low_support": n_with < MIN_SUPPORT,
        })
    records.sort(key=lambda r: abs(r["risk_diff"]), reverse=True)

    return {
        "records": records,
        "goal": goal,
        "goal_rate": float(goal.mean() * 100) if len(goal) else 0.0,
        "n_traces": int(len(goal)),
        "patterns_per_trace": patterns_per_trace,
    }


def _activity_effect_map(records):
    """activity -> signed risk_diff (in [-100,100]) of its strongest-|effect| pattern.
    Drives the diverging colouring of the elaborate model."""
    best = {}
    for r in records:
        a = r["activity"]
        if a not in best or abs(r["risk_diff"]) > abs(best[a]):
            best[a] = r["risk_diff"]
    return best


def _effect_node_style(activity_effect):
    """Diverging node_style_fn: fill darkness encodes |effect|; a heavy dark border
    marks 'associated with MISSING the goal' (negative), a lighter border 'associated
    with ACHIEVING the goal' (positive). Greyscale-only (project palette)."""
    def _style(eid, elem):
        if elem.get("kind") == "task":
            name = elem.get("name", "")
            if name in activity_effect:
                rd = activity_effect[name]
                mag = min(abs(rd) / 100.0, 1.0)
                shade = int(round(235 - 150 * mag))          # white-ish → dark grey by |effect|
                fill = f"#{shade:02x}{shade:02x}{shade:02x}"
                if rd < 0:
                    return (fill, "#111111", 3.2, contrasting_text_color(fill))   # missing goal
                return (fill, "#888888", 2.0, contrasting_text_color(fill))       # achieving goal
        return ("white", "#888888", 2, "#333333")
    return _style


# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def _fmt_rel_risk(rr):
    return "—" if rr is None else f"{rr:.2f}×"


def _effect_table_data(records, top_n=TOP_N):
    """(cell_text, col_labels, col_widths). Low-support patterns get a trailing '*'."""
    recs = records[:top_n]
    col_labels = ["Violation pattern", "#Traces with", "Outcome rate with",
                  "without", "Risk diff", "Relative risk"]
    col_widths = [0.34, 0.12, 0.15, 0.12, 0.12, 0.15]
    cell_text = []
    for r in recs:
        name = r["pattern"] + (" *" if r["low_support"] else "")
        cell_text.append([
            name, str(r["support"]), f"{r['rate_with']:.1f}%",
            f"{r['rate_without']:.1f}%", f"{r['risk_diff']:+.1f} pp",
            _fmt_rel_risk(r["rel_risk"]),
        ])
    return cell_text, col_labels, col_widths


def _effect_colors(records):
    """Signed bar colours: negative (missing goal) = GREY_DARK, positive = GREY_MED."""
    return [GREY_DARK if r["risk_diff"] < 0 else GREY_MED for r in records]


# ---------------------------------------------------------------------------
# Idiom renderers (all "associated with" — observational, never causal)
# ---------------------------------------------------------------------------

def task19_bar_chart(eff, output_dir):
    """Top-N patterns by |risk difference|, signed horizontal bars (negative =
    associated with missing the goal); low-support patterns hatched + faded."""
    path = os.path.join(output_dir, "task19_bar_chart.svg")
    records = eff["records"][:TOP_N]
    if not records:
        render_empty_state_svg(path, "Goal Effect by Violation Pattern", "No violation patterns found.")
        return
    recs = records[::-1]
    labels = [r["pattern"] for r in recs]
    diffs = [r["risk_diff"] for r in recs]
    colors = _effect_colors(recs)

    fig, ax = plt.subplots(figsize=(11, max(4.0, len(recs) * 0.5 + 1.5)))
    y = np.arange(len(labels))
    for i, (r, d) in enumerate(zip(recs, diffs)):
        ax.barh(i, d, color=colors[i], edgecolor="white",
                hatch="//" if r["low_support"] else None,
                alpha=0.55 if r["low_support"] else 1.0)
    ax.axvline(0, color="#333333", linewidth=1.0)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_xlabel("Risk difference in goal rate (percentage points)", fontsize=FONT_LABEL)
    ax.set_title("Violation Patterns Associated with the Process Goal", fontsize=FONT_TITLE)
    ax.legend(handles=[
        mpatches.Patch(color=GREY_DARK, label="Associated with missing the goal (−)"),
        mpatches.Patch(color=GREY_MED, label="Associated with achieving the goal (+)"),
        mpatches.Patch(facecolor="#cccccc", hatch="//", label=f"Low support (< {MIN_SUPPORT} traces)"),
    ], loc="lower center", bbox_to_anchor=(0.5, -0.35),
       ncol=3, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task19_scatter_plot(eff, output_dir):
    """One dot per pattern: x = support (#traces), y = risk difference; zero line.
    Reveals which FREQUENT violations are associated with goal failure."""
    path = os.path.join(output_dir, "task19_scatter_plot.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Support vs. Goal Effect", "No violation patterns found.")
        return

    fig, ax = plt.subplots(figsize=(10, 6))
    for r in records:
        low = r["low_support"]
        ax.scatter(r["support"], r["risk_diff"],
                   s=60, c=(GREY_DARK if r["risk_diff"] < 0 else GREY_MED),
                   alpha=0.35 if low else 0.85,
                   edgecolors="#333333", linewidths=0.8,
                   marker="o" if not low else "D")
    ax.axhline(0, color="#333333", linewidth=1.0)
    # Label the strongest-|effect| patterns with cluster-aware, non-crossing callouts.
    labeled = sorted(records, key=lambda r: abs(r["risk_diff"]), reverse=True)[:6]
    place_scatter_labels(ax, [(r["support"], r["risk_diff"], r["pattern"]) for r in labeled])
    ax.set_xlabel("Support (# traces exhibiting the pattern)", fontsize=FONT_LABEL)
    ax.set_ylabel("Risk difference in goal rate (pp)", fontsize=FONT_LABEL)
    ax.set_title("Which Frequent Violations Are Associated with Goal Failure", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task19_table(eff, output_dir):
    """Pattern | #Traces with | Outcome rate with | without | Risk diff | Relative risk."""
    path = os.path.join(output_dir, "task19_table.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Process Goal", "No violation patterns found.")
        return
    cell_text, col_labels, col_widths = _effect_table_data(records)
    fig_h = max(3.0, 1.6 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(13.5, fig_h))
    ax.axis("off")
    make_table(ax, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.05, 0.96, 0.82], col_widths=col_widths,
               font_size=9.5, cell_pad=0.08)
    ax.set_title("Violation Patterns Associated with the Process Goal (ranked by |risk diff|)",
                 fontsize=FONT_TITLE, pad=10)
    ax.text(0.02, 0.02, f"* low support (< {MIN_SUPPORT} traces) — interpret with caution. "
                        "Associations are observational, not causal.",
            transform=ax.transAxes, fontsize=FONT_ANNOT - 1, color="#666666")
    save_svg(fig, path)


def task19_table_and_bar_chart(eff, output_dir):
    """Effect table (left) + signed effect bar (right)."""
    path = os.path.join(output_dir, "task19_table_and_bar_chart.svg")
    records = eff["records"][:TOP_N]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Process Goal", "No violation patterns found.")
        return
    cell_text, col_labels, col_widths = _effect_table_data(records)

    fig = plt.figure(figsize=(18, max(3.4, 1.6 + len(records) * 0.5)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.8, 1.0], wspace=0.40)

    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    make_table(ax_t, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.05, 0.96, 0.84], col_widths=col_widths,
               font_size=9, cell_pad=0.07)
    ax_t.set_title("Violation Effect on Goal (ranked)", fontsize=FONT_TITLE, pad=8)

    ax_b = fig.add_subplot(gs[1])
    recs = records[::-1]
    labels = [r["pattern"] for r in recs]
    diffs = [r["risk_diff"] for r in recs]
    colors = _effect_colors(recs)
    for i, (r, d) in enumerate(zip(recs, diffs)):
        ax_b.barh(i, d, color=colors[i], edgecolor="white",
                  hatch="//" if r["low_support"] else None,
                  alpha=0.55 if r["low_support"] else 1.0)
    ax_b.axvline(0, color="#333333", linewidth=1.0)
    ax_b.set_yticks(np.arange(len(labels)))
    ax_b.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
    ax_b.set_xlabel("Risk diff (pp)", fontsize=FONT_LABEL)
    ax_b.spines[["top", "right"]].set_visible(False)
    ax_b.set_title("Signed goal effect", fontsize=FONT_TITLE, pad=8)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task19_parallel_sets(eff, output_dir):
    """Dimension 1 = top pattern present (each trace → its strongest top-N pattern, or
    'none of top-N'), Dimension 2 = goal achieved (yes/no); ribbon = #traces."""
    path = os.path.join(output_dir, "task19_parallel_sets.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Pattern vs. Goal", "No violation patterns found.")
        return

    top = records[:TOP_N]
    top_keys = [(r["activity"], r["move_type"]) for r in top]
    rank_of = {k: i for i, k in enumerate(top_keys)}
    left_labels = [r["pattern"] for r in top] + ["none of top-N"]

    # Assign each trace to its highest-ranked top-N pattern (else 'none of top-N').
    assign = []
    for s in eff["patterns_per_trace"]:
        best_rank, best_key = None, None
        for k in s:
            if k in rank_of and (best_rank is None or rank_of[k] < best_rank):
                best_rank, best_key = rank_of[k], k
        assign.append(top[best_rank]["pattern"] if best_key is not None else "none of top-N")

    goal = eff["goal"]
    matrix = np.zeros((len(left_labels), 2))
    index_of = {lab: i for i, lab in enumerate(left_labels)}
    for lab, g in zip(assign, goal):
        matrix[index_of[lab], 0 if g else 1] += 1

    fig, ax = plt.subplots(figsize=(10, max(6, len(left_labels) * 0.5 + 2)))
    ax.axis("off")
    left_colors = [GREY_MED if i % 2 == 0 else GREY_LIGHT for i in range(len(left_labels))]
    draw_parallel_sets(
        ax, left_labels, ["Goal achieved", "Goal missed"], matrix, left_colors,
        right_colors=[GREY_LIGHTER, GREY_DARK],
        left_title="Top violation pattern present", right_title="Process goal",
    )
    # Title above the column headers (which draw_parallel_sets places at y=1.08).
    fig.suptitle("Violation Pattern vs. Process Goal (ribbon = # traces)",
                 fontsize=FONT_TITLE, y=0.99)
    fig.subplots_adjust(top=0.80)
    save_svg(fig, path)


def _goal_missing_ctx(alignments, goal):
    """ctx (task28 shape) for a representative violating trace that MISSED the goal;
    falls back to task28's default representative trace if none qualifies."""
    for i, result in enumerate(alignments):
        if i < len(goal) and not goal[i] and float(result.get("fitness", 1.0)) < 1.0 - 1e-9:
            rows = alignment_pairs_to_rows(result.get("alignment", []))
            if rows:
                return {"trace_index": i, "trace_label": f"Trace {i + 1}",
                        "fitness": float(result.get("fitness", 0.0)),
                        "cost": result.get("cost"), "rows": rows}
    return build_task28_context(alignments)


def task19_flow_chart_and_table(eff, alignments, output_dir):
    """Chevron exemplar of a goal-missing violating trace + the effect table.
    Stem 'flow_chart_and_table' → canonical slug 'flow_chart_table'."""
    path = os.path.join(output_dir, "task19_flow_chart_and_table.svg")
    records = eff["records"]
    ctx = _goal_missing_ctx(alignments, eff["goal"])
    if ctx is None or not records:
        render_empty_state_svg(path, "Goal-missing Violations & Effect Table",
                               "No usable alignment / no violation patterns.")
        return

    nodes = chevron_nodes_from_alignment_rows(ctx["rows"])
    cell_text, col_labels, col_widths = _effect_table_data(records)

    fig_w = max(14.0, chevron_figure_width(nodes))
    fig_h = max(7.0, 3.4 + min(len(records), TOP_N) * 0.5)
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.0, max(1.4, 0.5 * min(len(records), TOP_N) + 0.8)],
                           hspace=0.30)

    ax_flow = fig.add_subplot(gs[0])
    draw_chevron_strip(ax_flow, nodes, fontsize=10)
    ax_flow.set_title(
        f"Goal-missing Violating Trace ({ctx['trace_label']}, fitness={ctx['fitness']:.3f})",
        fontsize=FONT_TITLE, pad=6)

    ax_tab = fig.add_subplot(gs[1])
    ax_tab.axis("off")
    make_table(ax_tab, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.05, 0.96, 0.84], col_widths=col_widths,
               font_size=9, cell_pad=0.07)
    ax_tab.set_title("Violation Patterns Associated with the Goal (ranked)", fontsize=FONT_TITLE, pad=6)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def _effect_legend_items():
    return [
        ("#414141", "#111111", 3.2, "Stronger effect, assoc. missing goal"),
        ("#cdcdcd", "#888888", 2.0, "Stronger effect, assoc. achieving goal"),
        ("white",   "#888888", 2,   "No measured effect"),
    ]


def task19_flow_chart_elaborate_bpmn_table(eff, model_path, output_dir):
    """Desired model with violation locations coloured by signed goal effect +
    the effect table. Stem → canonical slug 'flow_chart_elaborate_table'."""
    path = os.path.join(output_dir, "task19_flow_chart_elaborate_bpmn_table.svg")
    records = eff["records"]
    if not records or not model_path:
        render_empty_state_svg(path, "Goal Effect on the Model & Table",
                               "No violation patterns or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task19: BPMN parse failed: {e}")
        render_empty_state_svg(path, "Goal Effect on the Model & Table",
                               "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, "Goal Effect on the Model & Table", "No BPMN geometry to render.")
        return

    activity_effect = _activity_effect_map(records)
    cell_text, col_labels, _ = _effect_table_data(records)
    panels = [{
        "parsed": parsed,
        "node_style_fn": _effect_node_style(activity_effect),
        "subtitle": "Activities coloured by the signed goal effect of their violations (associated with, not causal)",
    }]
    compose_bpmn_panels(
        panels, path,
        title="Goal Effect of Violations on the Desired Model",
        legend_items=_effect_legend_items(),
        table_rows=cell_text,
        table_cols=col_labels,
    )


def task19_flow_chart_elaborate_bpmn(eff, model_path, output_dir):
    """MEDIUM idiom: the effect-coloured model alone (no table).
    Stem → canonical slug 'flow_chart_elaborate'."""
    path = os.path.join(output_dir, "task19_flow_chart_elaborate_bpmn.svg")
    records = eff["records"]
    if not records or not model_path:
        render_empty_state_svg(path, "Goal Effect on the Model",
                               "No violation patterns or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task19: BPMN parse failed: {e}")
        render_empty_state_svg(path, "Goal Effect on the Model", "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, "Goal Effect on the Model", "No BPMN geometry to render.")
        return

    activity_effect = _activity_effect_map(records)
    render_bpmn_annotated(
        parsed, path,
        title="Goal Effect of Violations on the Desired Model",
        summary=f"Overall goal rate {eff['goal_rate']:.1f}%. Darker = stronger association; "
                "heavy border = associated with missing the goal. Observational, not causal.",
        node_style_fn=_effect_node_style(activity_effect),
        legend_items=_effect_legend_items(),
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

def generate(log, alignments, model_path, output_dir: str, outcome_activity: str = "A_ACTIVATED"):
    """Generate all Task ID 19 SVGs into output_dir. The process goal reuses task31's
    outcome activity; effects are per-violation-pattern risk differences computed from
    the central alignment run (never recomputed)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 19 visualizations ---")

    if not log or not alignments:
        logger.warning("      task19: empty log / alignments — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No log or alignment data available.")
        return

    eff = task19_effects(log, alignments, outcome_activity)

    if not eff["records"]:
        logger.warning("      task19: no guideline violations — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No guideline violations — no goal effects to show.")
        return
    if not eff["goal"].any() or eff["goal"].all():
        state = "never" if not eff["goal"].any() else "always"
        logger.warning(f"      task19: outcome activity '{outcome_activity}' {state} occurs — "
                       f"goal effects are undefined; emitting empty-state SVGs.")
        _emit_all_empty(output_dir,
                        f"Process goal ('{outcome_activity}') {state} achieved — effect undefined.")
        return

    logger.info(f"      task19: {len(eff['records'])} violation patterns; overall goal rate "
                f"{eff['goal_rate']:.1f}% over {eff['n_traces']} traces.")

    task19_bar_chart(eff, output_dir)
    task19_scatter_plot(eff, output_dir)
    task19_table(eff, output_dir)
    task19_table_and_bar_chart(eff, output_dir)
    task19_parallel_sets(eff, output_dir)
    task19_flow_chart_and_table(eff, alignments, output_dir)
    task19_flow_chart_elaborate_bpmn_table(eff, model_path, output_dir)
    task19_flow_chart_elaborate_bpmn(eff, model_path, output_dir)
