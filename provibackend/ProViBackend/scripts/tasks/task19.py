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
  * ``target_patterns`` (admin param): a checkbox selection of (activity, move-type)
    violation patterns from this dataset's full "log.violations" catalogue — the
    same source task11 uses. The admin explicitly picks which patterns to include
    (rather than an automatic top-N cut), so charts stay readable and every idiom
    renders exactly the chosen set. Leaving it empty shows every pattern found.

Scope = 6 idioms, all information-equivalent (per violation pattern: goal-achievement
rate with vs. without), restricted to the admin-selected ``target_patterns``. Stems →
canonical slug after the pipeline rename:
    task19_bar_chart.svg           → bar_chart
    task19_table.svg               → table
    task19_table_and_bar_chart.svg → table_bar_chart
    task19_matrix.svg              → matrix
    task19_heatmap.svg             → heatmap
    task19_parallel_sets.svg       → parallel_sets

Public API:
    generate(log, alignments, model_path, output_dir, outcome_activity="Activate Care")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "table_bar_chart", "matrix", "heatmap", "parallel_sets"]

GT_TIER = "MANUAL"

PARAM_SPEC = [
    {
        "key": "outcome_activity",
        "label": "Process goal activity (present in trace = goal achieved)",
        "hint": "A trace reaches the process goal when it contains this activity",
        "hide_hint": True,
        "widget": "activity-picker",
        "source": "log.activities",
        "default": "",
        "required": True,
    },
    {
        "key": "target_patterns",
        "label": "Violation pattern(s) to include",
        "hint": "Every idiom renders exactly this set of (activity, violation type) patterns — "
                "select as many or as few as should be shown",
        "hide_hint": True,
        "widget": "select-many",
        "source": "log.violations",
        "required": True,
    },
]

ANSWER_FORMATS = [
    {"key": "free-text",  "gt_shape": "reference", "decisive_default": False},
    {"key": "mc-single",  "gt_shape": "mc",         "decisive_default": True},
]

RUBRIC = (
    "A strong answer names at least one specific violation pattern (activity + move type) "
    "with a strong association with missing or achieving the process goal, and states the "
    "direction of the effect: negative risk difference = associated with missing the goal, "
    "positive = associated with achieving it. Full marks require an approximate magnitude "
    "(e.g. 'associated with a −35 pp drop in goal-achievement rate'). "
    "Award partial marks for naming the correct pattern and direction without the magnitude. "
    "Deduct marks for incorrect direction. "
    "No credit for vague claims not grounded in the risk-difference values shown."
)


def validate_params(log, params) -> list:
    errors = []
    act = params.get("outcome_activity")
    if not act:
        errors.append("A goal activity is required.")
    else:
        total = len(log)
        present = sum(1 for trace in log if act in {str(e.get("concept:name", "")) for e in trace})
        if present == 0:
            errors.append(f"Goal activity '{act}' is not present in any trace.")
        elif present == total:
            errors.append(f"Goal activity '{act}' is present in all traces — effect on outcome is undefined.")

    patterns = params.get("target_patterns")
    if not patterns or (isinstance(patterns, list) and len(patterns) == 0):
        errors.append("At least one violation pattern must be selected.")
    return errors


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """For mc-single: top violation patterns ranked by |risk difference| as selectable
    options. The admin flags which pattern is the correct answer (strongest effect).
    For free-text: returns empty dict — the static RUBRIC is used as the reference.
    """
    if answer_format == "free-text":
        return {}

    outcome_activity = params.get("outcome_activity", "")
    if not outcome_activity:
        outcome_activity = infer_outcome_activity(log)
    target_patterns = params.get("target_patterns")

    eff = task19_effects(log, alignments, outcome_activity, target_patterns=target_patterns)
    records = eff["records"]
    if not records:
        return {"options": []}

    return {
        "options": [
            {
                "label": f"{r['pattern']} (risk diff: {r['risk_diff']:+.1f} pp)",
                "value": r["pattern"],
                "correct": False,
            }
            for r in records[:4]
        ]
    }


import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec

from shared import (
    save_svg, make_table, auto_col_widths, draw_parallel_sets, draw_value_heatmap,
    render_empty_state_svg,
    classify_step, contrasting_text_color,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    infer_outcome_activity,
)


# With/without colours for the grouped bar-chart idioms, reusing the platform's
# Conformant/Non-conformant palette from task03 (GREY_DARK = cividis blue #243c6e,
# GREY_LIGHTER = cividis yellow #e5cf52): "Without violation" = blue (conformant-like),
# "With violation" = yellow (the deviation). Still not a positive/negative signing —
# the participant derives the effect from the two rates themselves.
_C_WITH    = GREY_LIGHTER  # "With violation" series    (cividis yellow #e5cf52)
_C_WITHOUT = GREY_DARK     # "Without violation" series (cividis blue   #243c6e)

_EMPTY_STEMS = [
    ("task19_bar_chart.svg",           "Violation Effect on Successful Payment"),
    ("task19_table.svg",               "Violation Effect on Successful Payment"),
    ("task19_table_and_bar_chart.svg", "Violation Effect on Successful Payment"),
    ("task19_matrix.svg",              "Violation Effect on Successful Payment"),
    ("task19_heatmap.svg",             "Violation Effect on Successful Payment"),
    ("task19_parallel_sets.svg",       "Violation Effect on Successful Payment"),
]


# ---------------------------------------------------------------------------
# Goal labelling + per-pattern effect (reuses task31 outcome + task29 patterns)
# ---------------------------------------------------------------------------

def _trace_patterns(alignments):
    """Per trace: the set of (activity, move_type) violation patterns it exhibits.

    Uses the platform-standard classify_step() (also used by get_log_violations(),
    which powers the admin's "log.violations" checkbox source) so pattern keys here
    match the admin's selection specs ('activity|Move on Model' etc.) exactly.
    """
    out = []
    for result in alignments:
        patterns = set()
        for step in result.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            act, vtype = classify_step(step[0], step[1])
            if act is None:
                continue
            patterns.add((act, vtype))
        out.append(patterns)
    return out


def _resolve_target_patterns(target_patterns, universe):
    """Resolve a list of 'activity|move_type' specs (as emitted by get_log_violations,
    the admin's checkbox source) to (activity, move_type) keys present in universe.

    Returns None if target_patterns is empty (caller should then use the full
    universe); otherwise the resolved subset (specs not found in this dataset are
    silently dropped).
    """
    if not target_patterns:
        return None
    if isinstance(target_patterns, str):
        target_patterns = [target_patterns]
    resolved, seen = [], set()
    for spec in target_patterns:
        s = str(spec).strip()
        if "|" not in s:
            continue
        act, vt = s.rsplit("|", 1)
        key = (act.strip(), vt.strip())
        if key in universe and key not in seen:
            seen.add(key)
            resolved.append(key)
    return resolved


def task19_effects(log, alignments, outcome_activity="Activate Care", target_patterns=None):
    """Label each trace (goal achieved yes/no) + measure each violation pattern's
    association with the goal.

    ``target_patterns`` restricts ``records`` to the admin-selected (activity,
    move_type) patterns (checkbox picks from the full "log.violations" catalogue,
    resolved via _resolve_target_patterns) — applied once here so every idiom
    renders the exact same set and stays information-equivalent. Empty/None shows
    every pattern found.

    Returns a dict:
        records      – per-pattern dicts ranked by |risk_diff|:
                       {pattern, activity, move_type, support, rate_with, rate_without,
                        risk_diff, rel_risk}
        goal         – per-trace bool array (goal achieved)
        goal_rate    – overall goal rate (%)
        n_traces     – #traces
        outcome_activity – the activity whose presence defines the goal (for labels)
        patterns_per_trace – list[set] (reused by the parallel-sets idiom)
    """
    goal = np.array([
        outcome_activity in {str(e.get("concept:name", "")) for e in t}
        for t in log
    ], dtype=bool)

    patterns_per_trace = _trace_patterns(alignments)
    n = min(len(goal), len(patterns_per_trace))
    goal = goal[:n]
    patterns_per_trace = patterns_per_trace[:n]

    universe = set().union(*patterns_per_trace) if patterns_per_trace else set()
    selected = _resolve_target_patterns(target_patterns, universe)
    if selected is not None:
        universe = set(selected)
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
            "pattern": f"{activity} ({_display_move(move_type)})",
            "activity": activity,
            "move_type": move_type,
            "support": n_with,
            "rate_with": rate_with,
            "rate_without": rate_without,
            "risk_diff": risk_diff,
            "rel_risk": rel_risk,
        })
    records.sort(key=lambda r: abs(r["risk_diff"]), reverse=True)

    return {
        "records": records,
        "goal": goal,
        "goal_rate": float(goal.mean() * 100) if len(goal) else 0.0,
        "n_traces": int(len(goal)),
        "outcome_activity": outcome_activity,
        "patterns_per_trace": patterns_per_trace,
    }


# Display labels for move types in the visible pattern strings. The internal
# move_type (from classify_step) stays "Move on Model" / "Move on Log" so it keeps
# matching the admin's 'activity|Move on Model' selection specs; only the shown text
# is shortened to "Model Move" / "Log Move".
_MOVE_DISPLAY = {"Move on Model": "Model Move", "Move on Log": "Log Move"}


def _display_move(move_type: str) -> str:
    return _MOVE_DISPLAY.get(move_type, move_type)


def _goal_label(outcome_activity: str) -> str:
    return f"Reaches '{outcome_activity}' (%)"


# ---------------------------------------------------------------------------
# Idiom renderers (all "associated with" — observational, never causal)
# ---------------------------------------------------------------------------

def task19_bar_chart(eff, output_dir):
    """Grouped horizontal bars per violation pattern: goal-achievement rate WITH vs.
    WITHOUT the violation. Two neutral colours (no positive/negative pre-categorisation);
    the participant derives the effect from the two rates themselves."""
    path = os.path.join(output_dir, "task19_bar_chart.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Successful Payment", "No violation patterns found.")
        return
    recs = records[::-1]  # highest-|difference| pattern ends up on top
    labels    = [r["pattern"] for r in recs]
    with_vals = [r["rate_with"] for r in recs]
    wout_vals = [r["rate_without"] for r in recs]

    fig_h = max(4.0, len(recs) * 0.6 + 1.6)
    fig, ax = plt.subplots(figsize=(11, fig_h))
    y = np.arange(len(labels))
    bh = 0.38
    bars_with = ax.barh(y + bh / 2, with_vals, height=bh, color=_C_WITH,
                        edgecolor="white", label="With violation")
    bars_wout = ax.barh(y - bh / 2, wout_vals, height=bh, color=_C_WITHOUT,
                        edgecolor="white", label="Without violation")
    for bars, vals in ((bars_with, with_vals), (bars_wout, wout_vals)):
        for bar, v in zip(bars, vals):
            ax.text(min(v + 1.0, 101.5), bar.get_y() + bar.get_height() / 2,
                    f"{v:.1f}%", va="center", ha="left", fontsize=FONT_ANNOT - 1)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_xlim(0, 112)
    # Goal label goes ABOVE as a subtitle (not as an x-axis label) so the bottom is
    # free for the legend — otherwise the two collide. Point offsets keep the
    # title↔subtitle gap constant regardless of figure height.
    ax.set_title("Violation Effect on Successful Payment", fontsize=FONT_TITLE, pad=26)
    ax.annotate(_goal_label(eff["outcome_activity"]),
                xy=(0.5, 1.0), xytext=(0, 6), xycoords="axes fraction",
                textcoords="offset points", ha="center", va="bottom",
                fontsize=FONT_LABEL, color="#555555")
    # Bars carry label=... ; the legend itself is drawn by _bottom_legend below.
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)   # first: fit the long y-axis labels (left margin)
    _bottom_legend(fig, ax, fig_h)
    save_svg(fig, path)


def _pattern_table_data(records):
    """(col_labels, cell_text) for the plain 3-column pattern table: Violation Pattern |
    With Violation | Without Violation. Shared by Table and Table & Bar Chart. No "(%)"
    in the header — the unit is stated once, in the chart's goal-label subtitle/axis,
    matching Matrix/Heatmap's bare "With Violation" / "Without Violation" column names."""
    col_labels = ["Violation Pattern", "With Violation", "Without Violation"]
    cell_text = [
        [r["pattern"], f"{r['rate_with']:.1f}%", f"{r['rate_without']:.1f}%"]
        for r in records
    ]
    return col_labels, cell_text


def _fig_title_and_goal(fig, fig_h, eff, content_top):
    """Draw the main title + goal-label subtitle in FIGURE coordinates, stacked in the
    band above ``content_top`` (the axes-fraction below which the table/plot lives).
    Fixed *inch* offsets, so the title↔subtitle↔content spacing is identical no matter
    how tall the figure is (i.e. how many rows) — this is what avoids the earlier
    overlap, which came from positioning the subtitle by the table's bbox height
    instead of its true top edge."""
    fig.text(0.5, content_top + 0.44 / fig_h, "Violation Effect on Successful Payment",
             ha="center", va="bottom", fontsize=FONT_TITLE)
    fig.text(0.5, content_top + 0.14 / fig_h, _goal_label(eff["outcome_activity"]),
             ha="center", va="bottom", fontsize=FONT_LABEL, color="#555555")


def _bottom_legend(fig, ax, fig_h, center_x=0.5, fontsize=FONT_ANNOT):
    """Place ax's series legend in a fixed-height band BELOW the x tick labels, anchored
    in figure coordinates. An axes-fraction offset (bbox_to_anchor y<0) can't do this
    reliably: the same fraction is a different number of inches on a short vs. tall
    figure, so it lands on the tick labels on some pattern counts and floats far on
    others. Reserving a constant 0.8" band and anchoring at a constant 0.12" keeps the
    gap identical everywhere."""
    ax.set_position([ax.get_position().x0, 0.8 / fig_h,
                     ax.get_position().width, ax.get_position().y1 - 0.8 / fig_h])
    fig.legend(*ax.get_legend_handles_labels(), loc="lower center",
               bbox_to_anchor=(center_x, 0.12 / fig_h),
               ncol=2, frameon=True, framealpha=0.9, fontsize=fontsize)


def task19_table(eff, output_dir):
    """Violation Pattern | With Violation | Without Violation (goal-achievement rate, %).

    Info-equivalent with the bar_chart / matrix / parallel_sets idioms: only the
    two raw goal-achievement rates per pattern, no derived metrics (risk diff,
    relative risk) and no trace counts."""
    path = os.path.join(output_dir, "task19_table.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Successful Payment", "No violation patterns found.")
        return
    col_labels, cell_text = _pattern_table_data(records)
    fig_h = max(3.0, 1.5 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(11, fig_h))
    ax.axis("off")
    make_table(ax, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.0, 0.0, 1.0, 1.0],
               col_widths=auto_col_widths(col_labels, cell_text),
               font_size=10, cell_pad=0.09)
    # Position the table axes, reserving a fixed 0.85" band at the top for the two
    # title lines; then draw them into that band in figure coords.
    content_top = 1.0 - 0.85 / fig_h
    fig.subplots_adjust(left=0.03, right=0.97, top=content_top, bottom=0.03)
    _fig_title_and_goal(fig, fig_h, eff, content_top)
    save_svg(fig, path)


def task19_matrix(eff, output_dir):
    """Side-by-side With / Without panels, rows = violation patterns — same layout
    as Heatmap, but a flat, non-value-encoded colour wash per panel. Reuses task03's
    matrix palette (GREY_LIGHTER = cividis yellow #e5cf52 for "With Violation",
    GREY_DARK = cividis blue #243c6e for "Without Violation" — matching the bar_chart's
    With=yellow / Without=blue mapping). The colour here carries no data; the number is
    the only thing being read (that's Heatmap's job)."""
    path = os.path.join(output_dir, "task19_matrix.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Successful Payment", "No violation patterns found.")
        return
    labels = [r["pattern"] for r in records]
    cols = [("With Violation", [r["rate_with"] for r in records]),
            ("Without Violation", [r["rate_without"] for r in records])]
    panel_colors = [GREY_LIGHTER, GREY_DARK]  # With=yellow #e5cf52, Without=blue #243c6e
    n = len(labels)
    fig_h = max(3.0, 0.5 * n + 1.8)
    fig, axes = plt.subplots(1, 2, figsize=(7.5, fig_h), squeeze=False,
                             gridspec_kw={"wspace": 0.0})
    for i, (ax, (col_label, vals)) in enumerate(zip(axes[0], cols)):
        face = panel_colors[i % len(panel_colors)]
        text_color = contrasting_text_color(face)
        for ri, v in enumerate(vals):
            ax.add_patch(plt.Rectangle((0, ri), 1, 1, facecolor=face,
                                       edgecolor="white", linewidth=1.2))
            ax.text(0.5, ri + 0.5, f"{v:.1f}%", ha="center", va="center",
                    fontsize=FONT_ANNOT, color=text_color)
        ax.set_xlim(0, 1)
        ax.set_ylim(0, n)
        ax.invert_yaxis()
        ax.set_xticks([0.5])
        ax.set_xticklabels([_goal_label(eff["outcome_activity"])], fontsize=FONT_ANNOT - 1)
        ax.set_yticks([r + 0.5 for r in range(n)])
        ax.set_yticklabels(labels if i == 0 else [], fontsize=FONT_ANNOT - 1)
        ax.tick_params(length=0)
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_title(col_label, fontsize=FONT_LABEL)
    fig.suptitle("Violation Effect on Successful Payment", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    fig.subplots_adjust(wspace=0.0)  # tight_layout() re-adds a gap; force it back to 0
    save_svg(fig, path)


def task19_heatmap(eff, output_dir):
    """Rows = violation patterns, columns = With / Without violation; each cell's
    colour intensity encodes the goal-achievement rate (%) on a fixed 0→100 scale —
    no numbers (platform convention: Matrix = numbers only, Heatmap = colour only)."""
    path = os.path.join(output_dir, "task19_heatmap.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Successful Payment", "No violation patterns found.")
        return
    labels = [r["pattern"] for r in records]
    data = np.array([[r["rate_with"], r["rate_without"]] for r in records], dtype=float)

    fig_h = max(3.0, 0.5 * len(labels) + 1.8)
    fig, ax = plt.subplots(figsize=(7.5, fig_h))
    draw_value_heatmap(
        fig, ax, data, labels, ["With Violation", "Without Violation"],
        cbar_label=_goal_label(eff["outcome_activity"]), cell_fmt="{:.1f}%",
        annotate=False, vmax=100.0,
    )
    ax.set_title("Violation Effect on Successful Payment", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task19_table_and_bar_chart(eff, output_dir):
    """Table & Bar Chart combo: the same 3-column pattern table as Table, beside the
    same grouped With/Without bars as Bar Chart — a native combination of the two
    existing simple idioms, no derived measures."""
    path = os.path.join(output_dir, "task19_table_and_bar_chart.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Successful Payment", "No violation patterns found.")
        return
    col_labels, cell_text = _pattern_table_data(records)

    n = len(records)
    fig_h = max(3.6, 1.8 + n * 0.5)
    fig = plt.figure(figsize=(18, fig_h))
    # Wider gap so the bar chart's long y-tick labels sit clear of the table column.
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.35, 1.0], wspace=0.45)

    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    make_table(ax_t, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.0, 0.0, 1.0, 1.0],
               col_widths=auto_col_widths(col_labels, cell_text),
               font_size=9, cell_pad=0.07)

    ax_b = fig.add_subplot(gs[1])
    recs = records[::-1]  # highest-|difference| pattern ends up on top, matches Table row order
    labels    = [r["pattern"] for r in recs]
    with_vals = [r["rate_with"] for r in recs]
    wout_vals = [r["rate_without"] for r in recs]
    y = np.arange(len(labels))
    bh = 0.38
    ax_b.barh(y + bh / 2, with_vals, height=bh, color=_C_WITH,
              edgecolor="white", label="With violation")
    ax_b.barh(y - bh / 2, wout_vals, height=bh, color=_C_WITHOUT,
              edgecolor="white", label="Without violation")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels(labels, fontsize=FONT_ANNOT - 1)
    ax_b.set_xlim(0, 112)
    # No x-axis label — the shared goal-label subtitle at the figure top states the
    # metric; the legend is drawn below in the reserved bottom band. (Bars keep label=.)
    ax_b.spines[["top", "right"]].set_visible(False)
    ax_b.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax_b.set_axisbelow(True)
    # Fixed top band for the two title lines + fixed 0.8" bottom band for the legend;
    # both subplots share the extent so table rows and bars stay aligned. (No
    # tight_layout — it would fight subplots_adjust and re-introduce the gaps.)
    content_top = 1.0 - 0.85 / fig_h
    fig.subplots_adjust(left=0.03, right=0.985, top=content_top, bottom=0.8 / fig_h)
    _fig_title_and_goal(fig, fig_h, eff, content_top)
    pos_b = ax_b.get_position()
    fig.legend(*ax_b.get_legend_handles_labels(), loc="lower center",
               bbox_to_anchor=((pos_b.x0 + pos_b.x1) / 2, 0.12 / fig_h),
               ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT - 1)
    save_svg(fig, path)


def task19_parallel_sets(eff, output_dir):
    """Dimension 1 = violation pattern present, Dimension 2 = goal achieved (yes/no);
    ribbon = #traces. Scoped to the same admin-selected pattern set as every other
    idiom — traces that exhibit none of the shown patterns simply don't contribute
    a ribbon."""
    path = os.path.join(output_dir, "task19_parallel_sets.svg")
    records = eff["records"]
    if not records:
        render_empty_state_svg(path, "Violation Effect on Successful Payment", "No violation patterns found.")
        return

    pattern_keys = [(r["activity"], r["move_type"]) for r in records]
    left_labels_base = [r["pattern"] for r in records]

    # Presence-based rows: every trace contributes to EACH shown pattern it exhibits
    # (its "WITH" set), so all patterns shown by the table/bar/matrix idioms also
    # appear here — rather than assigning each trace to a single strongest pattern,
    # which would drop patterns that never rank highest. A trace with several
    # patterns is counted once per pattern (same as the other idioms, which
    # evaluate each pattern over all traces containing it).
    goal = eff["goal"]
    matrix = np.zeros((len(pattern_keys), 2))
    for s, g in zip(eff["patterns_per_trace"], goal):
        col = 0 if g else 1
        for i, k in enumerate(pattern_keys):
            if k in s:
                matrix[i, col] += 1

    # Percentage on each left segment so participants can read the rate, not just
    # eyeball ribbon widths. It is the share of traces WITH this pattern that reach
    # the goal — i.e. exactly the pattern's "With Violation" value in the table/matrix.
    # Phrased "reaches goal: X%" to match the "Reaches '<goal>'" wording those idioms
    # and the right-axis "Goal achieved" label use.
    row_tot = matrix.sum(axis=1)
    left_labels = [
        f"{lab}  (reaches goal: {(matrix[i, 0] / row_tot[i] * 100) if row_tot[i] else 0.0:.1f}%)"
        for i, lab in enumerate(left_labels_base)
    ]
    right_labels = ["Goal achieved", "Goal missed"]

    fig_h = max(5.0, len(left_labels) * 0.8 + 2.0)
    fig, ax = plt.subplots(figsize=(11.5, fig_h))
    ax.axis("off")
    left_colors = [GREY_MED if i % 2 == 0 else GREY_LIGHT for i in range(len(left_labels))]
    draw_parallel_sets(
        ax, left_labels, right_labels, matrix, left_colors,
        right_colors=[GREY_LIGHTER, GREY_DARK],
        left_title="Violation Pattern", right_title="Process Goal",
        # Label every present pattern (h > 0), not just those above the default
        # 3% threshold — keeps information equivalence with the table / bar_chart /
        # matrix idioms, none of which drop small-but-present patterns either.
        label_min_frac=0.0,
        left_label_fontsize=FONT_ANNOT - 2,
    )
    # draw_parallel_sets fills the axes with data-y in [-0.03, 1.11] and puts the
    # column headers at data-y=1.04. Push the axes top near the figure top, then stack
    # the same main-title + goal-subtitle as the other idioms a *fixed* distance above
    # those headers (in inches) so the block hugs the diagram at any figure height.
    top = 0.99
    fig.subplots_adjust(top=top, bottom=0.04, left=0.02, right=0.98)
    header_frac = (1.04 - (-0.03)) / (1.11 - (-0.03))     # header axes-fraction
    header_figy = 0.04 + header_frac * (top - 0.04)
    fig.text(0.5, header_figy + 0.50 / fig_h, "Violation Effect on Successful Payment",
             ha="center", va="bottom", fontsize=FONT_TITLE)
    fig.text(0.5, header_figy + 0.24 / fig_h, _goal_label(eff["outcome_activity"]),
             ha="center", va="bottom", fontsize=FONT_LABEL, color="#555555")
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

def generate(log, alignments, model_path, output_dir: str, outcome_activity: str = "",
             target_patterns=None):
    """Generate all Task ID 19 SVGs into output_dir. The process goal reuses task31's
    outcome activity; effects are per-violation-pattern risk differences computed from
    the central alignment run (never recomputed). ``model_path`` is accepted for calling
    convention only — no model-level idiom is produced anymore. ``target_patterns`` is
    the admin's checkbox selection of violation patterns to show (None/empty = all)."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 19 visualizations ---")
    if not outcome_activity:
        outcome_activity = infer_outcome_activity(log)
        logger.info(f"      task19: outcome_activity inferred as '{outcome_activity}'")

    if not log or not alignments:
        logger.warning("      task19: empty log / alignments — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No log or alignment data available.")
        return

    eff = task19_effects(log, alignments, outcome_activity, target_patterns=target_patterns)

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
    task19_table(eff, output_dir)
    task19_table_and_bar_chart(eff, output_dir)
    task19_matrix(eff, output_dir)
    task19_heatmap(eff, output_dir)
    task19_parallel_sets(eff, output_dir)
