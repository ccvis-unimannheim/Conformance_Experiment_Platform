"""
tasks/task19.py – Task ID 19: Explain / Discover / Effects of goal deviations.

What is the effect of a guideline violation on overall process goals? A process
goal must first be formally defined; we relate each guideline violation (and the
activity it occurs at) to whether the trace meets that goal.

Goal definition (dataset-agnostic, auto-fallback):
    1. If the configured outcome activity occurs anywhere in the log, the goal is
       "trace reaches <outcome_activity>" (binary positive outcome).
    2. Otherwise the goal is "fast completion" — throughput time ≤ median (always
       computable from timestamps), so the task still works on logs without a
       known outcome activity.

Idioms (network_diagram intentionally dropped — no clear cause→effect graph; the
tree is a data-driven decision tree, not hierarchical clustering):
    bar_chart, scatter_plot, flow_chart_table, flow_chart_elaborate,
    flow_chart_elaborate_table, tree, table, table_bar_chart, parallel_sets

Building blocks reused: task20's trace-feature frame + Gini decision-tree builder,
shared chevron / BPMN / parallel-set / decision-tree renderers.

Public API:
    generate(log, alignments, output_dir, model_path=None,
             outcome_activity="A_ACTIVATED")
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "scatter_plot", "flow_chart_table", "flow_chart_elaborate",
          "flow_chart_elaborate_table", "tree", "table", "table_bar_chart",
          "parallel_sets"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec

from shared import (
    save_svg, make_table, draw_parallel_sets, draw_decision_tree, wrap_text,
    alignment_pairs_to_rows, parse_bpmn_model, render_bpmn_annotated,
    compose_bpmn_panels, chevron_figure_width, draw_chevron_strip,
    render_empty_state_svg,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

from tasks.task20 import (
    task20_trace_feature_dataframe, _task20_build_tree, _task20_split_question,
)

TOP_N = 10

# Goal-class colours (2 classes): met = light, missed = dark (risk stands out)
_GOAL_MET_COLOR    = "#BBBBBB"
_GOAL_MISSED_COLOR = "#444444"
_BAR_COLOR         = "#9A9A9A"


# ---------------------------------------------------------------------------
# Goal definition (formal, with auto-fallback)
# ---------------------------------------------------------------------------

def _trace_activities(trace) -> set:
    return {str(e.get("concept:name", "")) for e in trace}


def _trace_throughput_hours(trace) -> float:
    ts = [pd.Timestamp(e.get("time:timestamp")) for e in trace
          if e.get("time:timestamp") is not None and not pd.isna(e.get("time:timestamp"))]
    if len(ts) < 2:
        return 0.0
    return (max(ts) - min(ts)).total_seconds() / 3600.0


# Strong "positive terminal outcome" keywords, in priority order. Used only to
# auto-detect a goal activity when the caller's outcome_activity is absent — so a
# new dataset whose success activity is named differently still gets a meaningful
# business goal instead of silently dropping to throughput. Ambiguous mid-process
# words (accepted/registered/submitted) are deliberately excluded.
_POSITIVE_KEYWORDS = ["activat", "approv", "grant", "fulfil", "deliver",
                      "complet", "success", "paid", "won", "accept_final"]


def _detect_positive_activity(log):
    """Heuristically pick a positive-outcome activity by name keyword + terminality.

    Returns the activity name or None. Only returns a candidate that actually
    occurs as the LAST event in at least one trace (so it is a genuine terminal
    state, not a mid-process step that merely contains the keyword).
    """
    all_acts, terminal = {}, set()
    for tr in log:
        acts = [str(e.get("concept:name", "")) for e in tr if e.get("concept:name")]
        for a in acts:
            all_acts[a] = all_acts.get(a, 0) + 1
        if acts:
            terminal.add(acts[-1])
    if not all_acts:
        return None
    for kw in _POSITIVE_KEYWORDS:
        cands = [a for a in all_acts if kw in a.lower() and a in terminal]
        if cands:
            # most frequent matching terminal activity
            return max(cands, key=lambda a: all_acts[a])
    return None


def _build_goal(log, outcome_activity: str):
    """Return (goal_bool_array, goal_name, goal_kind, throughput_hours_array).

    Priority: explicit outcome_activity (if present) → auto-detected positive
    terminal activity → fast-completion throughput fallback.
    """
    throughput = np.array([_trace_throughput_hours(tr) for tr in log], dtype=float)

    # 1. Caller-configured outcome activity, if it actually occurs.
    chosen = outcome_activity if any(
        outcome_activity in _trace_activities(tr) for tr in log) else None
    # 2. Otherwise try to auto-detect a positive terminal activity.
    if chosen is None:
        chosen = _detect_positive_activity(log)
    if chosen is not None:
        goal = np.array([chosen in _trace_activities(tr) for tr in log], dtype=bool)
        return goal, f"reaches {chosen}", "outcome", throughput

    # 3. Fallback: fast completion (≤ median throughput) — always defined.
    positive = throughput[throughput > 0]
    if positive.size == 0:
        # No timestamps anywhere: degenerate, everyone "meets" the goal.
        return np.ones(len(log), dtype=bool), "no goal metric available", "none", throughput
    median = float(np.median(positive))
    goal = throughput <= median
    return goal, f"fast completion (≤ {median:.0f}h throughput)", "throughput", throughput


# ---------------------------------------------------------------------------
# Violation extraction
# ---------------------------------------------------------------------------

def _violation_long(alignments) -> pd.DataFrame:
    """Long frame of non-synchronous moves: {trace_index, pattern, activity}."""
    rows = []
    for i, result in enumerate(alignments):
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            if step["moveType"] == "Synchronous Move":
                continue
            activity = (step["model_move"] if step["moveType"] == "Model Move"
                        else step["log_move"])
            if not activity or activity in {"-", "None", "(skip)"}:
                continue
            rows.append({"trace_index": i, "activity": activity,
                         "pattern": f"{activity} ({step['moveType']})"})
    return pd.DataFrame(rows) if rows else pd.DataFrame(
        columns=["trace_index", "activity", "pattern"])


def _pattern_effects(viol_df, goal, baseline, top_n=TOP_N) -> pd.DataFrame:
    """Per violation pattern: #traces exhibiting it, goal-met rate, effect (Δ vs baseline)."""
    cols = ["pattern", "n_traces", "goal_rate", "effect"]
    if viol_df.empty:
        return pd.DataFrame(columns=cols)
    rows = []
    for pat, grp in viol_df.groupby("pattern"):
        idx = grp["trace_index"].unique()
        n = len(idx)
        rate = float(goal[idx].mean()) if n else 0.0
        rows.append({"pattern": pat, "n_traces": n,
                     "goal_rate": rate, "effect": rate - baseline})
    df = pd.DataFrame(rows)
    # Most harmful first (largest negative effect), then by reach
    df = df.sort_values(["effect", "n_traces"], ascending=[True, False])
    return df.head(top_n).reset_index(drop=True)


def _activity_effects(viol_df, goal, baseline) -> dict:
    """activity -> {'n','goal_rate','effect','harm'}.

    effect = goal_rate - baseline (signed, consistent with the pattern idioms);
    harm   = max(0, -effect) — only the downside, used to shade the model/chevron.
    """
    out = {}
    if viol_df.empty:
        return out
    for act, grp in viol_df.groupby("activity"):
        idx = grp["trace_index"].unique()
        n = len(idx)
        rate = float(goal[idx].mean()) if n else 0.0
        effect = rate - baseline
        out[act] = {"n": n, "goal_rate": rate, "effect": effect,
                    "harm": max(0.0, -effect)}
    return out


def _effect_shade(harm: float, max_harm: float) -> str:
    """Light grey (no harm) → dark grey (max harm)."""
    frac = (harm / max_harm) if max_harm > 0 else 0.0
    frac = max(0.0, min(1.0, frac))
    lo, hi = 0xF0, 0x44
    v = int(round(lo + (hi - lo) * frac))
    return f"#{v:02X}{v:02X}{v:02X}"


# ---------------------------------------------------------------------------
# Idiom 1: bar_chart — goal-met rate per violation pattern vs baseline
# ---------------------------------------------------------------------------

def task19_bar_chart(eff_df, baseline, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_bar_chart.svg")
    if eff_df.empty:
        render_empty_state_svg(out, "Effect of Violations on Goal", "No violations found.")
        return
    patterns = eff_df["pattern"].tolist()
    rates = eff_df["goal_rate"].values * 100
    x = np.arange(len(patterns))

    fig, ax = plt.subplots(figsize=(max(6.5, len(patterns) * 2.0), 5.8))
    ax.bar(x, rates, color=_BAR_COLOR, edgecolor="white", linewidth=0.6, width=0.55)
    for xi, r, eff in zip(x, rates, eff_df["effect"].values):
        ax.text(xi, r + 1.5, f"{eff*100:+.0f}pp", ha="center", va="bottom",
                fontsize=FONT_ANNOT - 1, color="#444444")
    ax.axhline(baseline * 100, color="#222222", linestyle="--", linewidth=1.1)
    ax.text(len(patterns) - 0.5, baseline * 100 + 1.5,
            f"baseline {baseline*100:.0f}%", ha="right", va="bottom",
            fontsize=FONT_ANNOT - 1, color="#222222")
    ax.set_xticks(x)
    ax.set_xticklabels([p.replace(" (", "\n(", 1) for p in patterns],
                       rotation=0, ha="center", fontsize=FONT_ANNOT - 2)
    ax.set_ylabel(f"% meeting goal ({goal_name})", fontsize=FONT_LABEL)
    ax.set_ylim(0, 109)
    ax.set_title("Effect of Each Violation on Goal Attainment", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 2: scatter_plot — violations per trace vs throughput, coloured by goal
# ---------------------------------------------------------------------------

def task19_scatter_plot(viol_df, goal, throughput, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_scatter_plot.svg")
    n_traces = len(goal)
    vcount = np.zeros(n_traces, dtype=float)
    if not viol_df.empty:
        vc = viol_df.groupby("trace_index").size()
        for idx, c in vc.items():
            if idx < n_traces:
                vcount[idx] = c

    if not np.any(throughput > 0):
        render_empty_state_svg(out, "Violations vs Goal", "No timestamps to derive throughput.")
        return

    rng = np.random.default_rng(42)
    jitter = rng.uniform(-0.18, 0.18, size=n_traces)
    fig, ax = plt.subplots(figsize=(10, 5))
    for met, color, lbl in [(True, _GOAL_MET_COLOR, "goal met"),
                            (False, _GOAL_MISSED_COLOR, "goal missed")]:
        m = goal == met
        ax.scatter(vcount[m] + jitter[m], throughput[m], c=color, s=14,
                   alpha=0.55, linewidths=0, label=lbl)
    ax.set_xlabel("Guideline violations per trace", fontsize=FONT_LABEL)
    ax.set_ylabel("Throughput time (hours)", fontsize=FONT_LABEL)
    ax.set_title("Violations vs Throughput, coloured by Goal", fontsize=FONT_TITLE)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, title=f"Goal: {goal_name}",
              title_fontsize=FONT_ANNOT,
              loc="upper left", bbox_to_anchor=(1.01, 1), borderaxespad=0)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout()
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Table data shared by Idioms 7 & 8
# ---------------------------------------------------------------------------

def _effect_table_data(eff_df):
    col_labels = ["Violation Pattern", "Traces", "Goal-met %", "Effect (pp)"]
    col_widths = [0.52, 0.14, 0.17, 0.17]
    cell_text = [
        [row["pattern"], str(int(row["n_traces"])),
         f"{row['goal_rate']*100:.1f}%", f"{row['effect']*100:+.1f}"]
        for _, row in eff_df.iterrows()
    ]
    return cell_text, col_labels, col_widths


# ---------------------------------------------------------------------------
# Idiom 7: table — per-violation effect on the goal
# ---------------------------------------------------------------------------

def task19_table(eff_df, baseline, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_table.svg")
    if eff_df.empty:
        render_empty_state_svg(out, "Effect of Violations on Goal", "No violations found.")
        return
    cell_text, col_labels, col_widths = _effect_table_data(eff_df)
    fig_h = max(2.6, 1.3 + len(eff_df) * 0.46)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.axis("off")
    make_table(ax, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, 0.06, 0.96, 0.82], col_widths=col_widths,
               font_size=10, scale_xy=(1, 1.4))
    ax.set_title(f"Effect of Violations on Goal  (baseline {baseline*100:.0f}% — {goal_name})",
                 fontsize=FONT_TITLE, pad=10)
    fig.tight_layout()
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 8: table_bar_chart — effect table (left) + effect bars (right)
# ---------------------------------------------------------------------------

def task19_table_bar_chart(eff_df, baseline, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_table_bar_chart.svg")
    if eff_df.empty:
        render_empty_state_svg(out, "Effect of Violations on Goal", "No violations found.")
        return
    patterns = eff_df["pattern"].tolist()
    effects = eff_df["effect"].values * 100

    fig_h = max(4.5, 1.3 + len(eff_df) * 0.5)
    fig = plt.figure(figsize=(16, fig_h))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.5)

    ax_tbl = fig.add_subplot(gs[0])
    ax_tbl.axis("off")
    cell_text, col_labels, col_widths = _effect_table_data(eff_df)
    n_rows = len(cell_text) + 1
    tbl_frac = min(0.84, 0.55 * n_rows / fig_h)
    tbl_y0 = max(0.04, 0.86 - tbl_frac)
    make_table(ax_tbl, cell_text=cell_text, col_labels=col_labels,
               bbox=[0.02, tbl_y0, 0.96, tbl_frac], col_widths=col_widths,
               font_size=9, scale_xy=(1, 1.4))
    ax_tbl.set_title(f"Violation Effects ({goal_name})", fontsize=FONT_TITLE, pad=10)

    ax_bar = fig.add_subplot(gs[1])
    y = np.arange(len(patterns))
    colors = [_GOAL_MISSED_COLOR if e < 0 else _GOAL_MET_COLOR for e in effects]
    ax_bar.barh(y, effects, color=colors, edgecolor="white", linewidth=0.6, height=0.62)
    for yi, e in zip(y, effects):
        ax_bar.text(e + (0.4 if e >= 0 else -0.4), yi, f"{e:+.0f}",
                    va="center", ha="left" if e >= 0 else "right",
                    fontsize=FONT_ANNOT - 1, color="#444444")
    ax_bar.axvline(0, color="#222222", linewidth=1.0)
    ax_bar.set_yticks(y)
    ax_bar.set_yticklabels([p.replace(" (", "\n(", 1) for p in patterns],
                           fontsize=FONT_ANNOT - 1)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Effect on goal (percentage points)", fontsize=FONT_LABEL)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.4)
    ax_bar.set_axisbelow(True)
    ax_bar.set_title("Effect Size", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout()
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 9: parallel_sets — violation pattern → goal class (ribbon = trace count)
# ---------------------------------------------------------------------------

def task19_parallel_sets(eff_df, viol_df, goal, output_dir):
    out = os.path.join(output_dir, "task19_parallel_sets.svg")
    patterns = eff_df["pattern"].tolist() if not eff_df.empty else []
    if not patterns:
        render_empty_state_svg(out, "Violation vs. Goal", "No violations found.")
        return

    # rows = patterns, cols = [goal met, goal missed]; cell = #traces
    matrix = np.zeros((len(patterns), 2), dtype=int)
    for pi, pat in enumerate(patterns):
        idx = viol_df.loc[viol_df["pattern"] == pat, "trace_index"].unique()
        met = int(goal[idx].sum())
        matrix[pi, 0] = met
        matrix[pi, 1] = len(idx) - met

    left_labels = [p.replace(" (", "\n(", 1) for p in patterns]
    fig, ax = plt.subplots(figsize=(11, max(5.0, len(patterns) * 0.55 + 2)))
    ax.axis("off")
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(-0.05, 1.15)
    ax.set_title("Parallel Sets: Violation → Goal", fontsize=FONT_TITLE, pad=12)
    draw_parallel_sets(
        ax,
        left_labels=left_labels,
        right_labels=["goal met", "goal missed"],
        matrix=matrix,
        left_colors=[_BAR_COLOR] * len(patterns),
        right_colors=[_GOAL_MET_COLOR, _GOAL_MISSED_COLOR],
        left_title="Violation pattern",
        right_title="Goal",
    )
    fig.tight_layout()
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idiom 3: flow_chart_table — activity chevron (most-common variant) + effect table
# ---------------------------------------------------------------------------

def _representative_variant(log, prefer_activities):
    """Most-frequent variant that traverses at least one violated activity (so the
    chevron actually surfaces the activities whose violation affects the goal);
    falls back to the most common variant."""
    counts = {}
    for tr in log:
        key = tuple(str(e.get("concept:name", "")) for e in tr)
        if key:
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return []
    ranked = sorted(counts, key=counts.get, reverse=True)
    prefer = set(prefer_activities)
    for key in ranked:
        if prefer & set(key):
            return list(key)
    return list(ranked[0])


def task19_flow_chart_table(log, act_eff, baseline, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_flow_chart_table.svg")
    violated = {a for a, v in act_eff.items() if v["n"] > 0}
    variant = _representative_variant(log, violated)
    if not variant:
        render_empty_state_svg(out, "Goal Effect along the Process", "No activity sequence found.")
        return
    # de-duplicate consecutive repeats for a readable chevron
    seq = [a for i, a in enumerate(variant) if i == 0 or a != variant[i - 1]]
    max_harm = max((v["harm"] for v in act_eff.values()), default=0.0)
    nodes = [{"label": a, "color": _effect_shade(act_eff.get(a, {}).get("harm", 0.0), max_harm)}
             for a in seq]

    # Effect table: activities that carry violations, most harmful first
    harmed = sorted(act_eff.items(), key=lambda kv: kv[1]["harm"], reverse=True)
    harmed = [(a, v) for a, v in harmed if v["n"] > 0][:TOP_N]

    fig_w = max(11.0, chevron_figure_width(nodes))
    n_tbl = len(harmed) + 1
    fig = plt.figure(figsize=(fig_w, max(5.5, 2.4 + n_tbl * 0.42)))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.0, max(1.0, n_tbl * 0.5)], hspace=0.32)

    ax_flow = fig.add_subplot(gs[0])
    draw_chevron_strip(ax_flow, nodes, fontsize=10)
    ax_flow.set_title("Goal Effect along a Representative Variant  (darker = larger goal drop)",
                      fontsize=FONT_TITLE)

    ax_tbl = fig.add_subplot(gs[1])
    ax_tbl.axis("off")
    if harmed:
        # Signed effect (goal_rate - baseline), consistent with the other idioms.
        cell_text = [[a, str(int(v["n"])), f"{v['goal_rate']*100:.1f}%", f"{v['effect']*100:+.1f}"]
                     for a, v in harmed]
        make_table(ax_tbl, cell_text=cell_text,
                   col_labels=["Activity (violated)", "Traces", "Goal-met %", "Effect (pp)"],
                   bbox=[0.05, 0.04, 0.90, 0.86], col_widths=[0.46, 0.16, 0.19, 0.19],
                   font_size=9.5, scale_xy=(1, 1.4))
    else:
        ax_tbl.text(0.5, 0.5, "No activity-localised violations.", ha="center",
                    va="center", fontsize=11, color="#888888", transform=ax_tbl.transAxes)
    ax_tbl.set_title(f"Activity Violation Effect on Goal  (baseline {baseline*100:.0f}% — {goal_name})",
                     fontsize=FONT_TITLE, pad=8)
    fig.tight_layout()
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Idioms 4 & 5: flow_chart_elaborate (+ table) — goal effect on the BPMN model
# ---------------------------------------------------------------------------

def _bpmn_node_style_fn(act_eff, max_harm):
    def style(eid, elem):
        kind = elem.get("kind", "task")
        name = elem.get("name", "")
        if kind == "task":
            harm = act_eff.get(name, {}).get("harm", 0.0)
            fill = _effect_shade(harm, max_harm)
            tc = "white" if int(fill[1:3], 16) < 0x99 else "#222222"
            return fill, "#777777", 1.2, tc
        if kind in {"exclusiveGateway", "parallelGateway"}:
            return "#FFFFFF", "#777777", 1.2, "#333333"
        return "#EFEFEF", "#777777", 1.5, "#333333"
    return style


_BPMN_LEGEND = [
    ("#F0F0F0", "#777777", 1.0, "No / small goal effect"),
    ("#9A9A9A", "#777777", 1.0, "Moderate goal drop"),
    ("#444444", "#777777", 1.0, "Large goal drop"),
]


def task19_flow_chart_elaborate(act_eff, model_path, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_flow_chart_elaborate.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Goal Effect on the Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"      task19: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Goal Effect on the Model", "Could not parse the BPMN model.")
        return
    max_harm = max((v["harm"] for v in act_eff.values()), default=0.0)
    render_bpmn_annotated(
        parsed, out,
        title=f"Goal Effect on the Process Model  (goal: {goal_name})",
        summary="Activity shade: darker = violating it coincides with a larger goal drop",
        node_style_fn=_bpmn_node_style_fn(act_eff, max_harm),
        legend_items=_BPMN_LEGEND,
    )


def task19_flow_chart_elaborate_table(eff_df, act_eff, model_path, baseline, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_flow_chart_elaborate_table.svg")
    if not model_path or not os.path.exists(model_path):
        render_empty_state_svg(out, "Goal Effect on the Model", "No BPMN model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"      task19: BPMN parse failed: {e}")
        render_empty_state_svg(out, "Goal Effect on the Model", "Could not parse the BPMN model.")
        return
    max_harm = max((v["harm"] for v in act_eff.values()), default=0.0)

    table_cols = ["Violation Pattern", "Traces", "Goal-met %", "Effect (pp)"]
    table_rows = [
        [row["pattern"], str(int(row["n_traces"])),
         f"{row['goal_rate']*100:.1f}%", f"{row['effect']*100:+.1f}"]
        for _, row in eff_df.iterrows()
    ] or [["No violations found.", "", "", ""]]

    panels = [{
        "parsed": parsed,
        "node_style_fn": _bpmn_node_style_fn(act_eff, max_harm),
        "subtitle": f"Goal: {goal_name} · baseline {baseline*100:.0f}% · darker = larger goal drop",
    }]
    compose_bpmn_panels(
        panels, out,
        title="Goal Effect on the Model — with Violation Effects",
        legend_items=_BPMN_LEGEND,
        table_rows=table_rows, table_cols=table_cols,
    )


# ---------------------------------------------------------------------------
# Idiom 6: tree — data-driven decision tree predicting the goal
# ---------------------------------------------------------------------------

def _relabel_goal_tree(node):
    neg, pos = node["value"]               # [not_met, met]
    node["class"] = "goal met" if pos >= neg else "goal missed"
    if node.get("left"):
        _relabel_goal_tree(node["left"])
    if node.get("right"):
        _relabel_goal_tree(node["right"])


def _fit_goal_tree(log, alignments, goal):
    feats = task20_trace_feature_dataframe(log, alignments)
    if feats.empty:
        return None
    feats = feats.sort_values("trace_index").reset_index(drop=True)
    n = min(len(feats), len(goal))
    feats = feats.iloc[:n]
    y = goal[:n].astype(int)
    if len(np.unique(y)) < 2:
        return None
    # Restrict to VIOLATION-related features so the tree explains the goal through
    # guideline violations (the task's intent) rather than incidental trace size.
    violation_features = {"fitness", "is_nonconformant", "violation_count",
                          "model_moves", "log_moves"}
    feature_cols = [c for c in feats.columns
                    if c in violation_features or c.startswith("has_activity_")]
    if not feature_cols:
        return None
    X = feats[feature_cols].astype(float).reset_index(drop=True)
    min_leaf = max(12, n // 50)
    tree = _task20_build_tree(X, y, feature_cols, max_depth=3, min_leaf=min_leaf)
    if tree.get("feature") is None:
        return None
    _relabel_goal_tree(tree)
    return tree


def task19_tree(tree, goal_name, output_dir):
    out = os.path.join(output_dir, "task19_tree.svg")
    fig, ax = plt.subplots(figsize=(11.5, 6.8))

    def wrap_width(text):
        n = len("" if text is None else str(text))
        return 30 if n <= 22 else 26 if n <= 36 else 22

    draw_decision_tree(
        ax, tree,
        title=f"What Predicts Meeting the Goal? ({goal_name})",
        title_fontsize=FONT_TITLE, title_pad=8,
        box_w=2.42, base_font=7.8, min_font=6.1, line_height=0.18,
        box_padding_h=0.16, wrap_width_fn=wrap_width,
        first_line_fn=lambda node: ("" if node.get("feature") is None
                                    else _task20_split_question(node["feature"], node["threshold"])),
        value_pair_fn=lambda node: (node["value"][0], node["value"][1]),
        node_facecolor_fn=lambda node: (
            _GOAL_MISSED_COLOR if node["value"][0] > node["value"][1]
            else "#888888" if node["value"][1] > node["value"][0]
            else "#F4F4F4"
        ),
        edge_arrowprops=dict(arrowstyle="-|>", color="#555555", linewidth=1.35, shrinkA=5, shrinkB=5),
        edge_label_fontsize=FONT_ANNOT, edge_label_offset_y=0.14,
        x_pad_factor=0.70, y_pad_base=0.80, y_top_pad=0.95,
    )
    if tree is not None:
        legend = [
            mpatches.Patch(facecolor="#888888", edgecolor="#555555", label="Mostly goal met"),
            mpatches.Patch(facecolor=_GOAL_MISSED_COLOR, edgecolor="#555555", label="Mostly goal missed"),
        ]
        ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.03),
                  ncol=2, frameon=False, fontsize=FONT_ANNOT)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    save_svg(fig, out)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

_ALL_FNAMES_TITLES = [
    ("task19_bar_chart.svg",                  "Effect of Violations on Goal"),
    ("task19_scatter_plot.svg",               "Violations vs Goal"),
    ("task19_flow_chart_table.svg",           "Goal Effect along the Process"),
    ("task19_flow_chart_elaborate.svg",       "Goal Effect on the Model"),
    ("task19_flow_chart_elaborate_table.svg", "Goal Effect on the Model + Table"),
    ("task19_tree.svg",                       "Goal Predictors (Decision Tree)"),
    ("task19_table.svg",                      "Effect of Violations on Goal"),
    ("task19_table_bar_chart.svg",            "Violation Effects & Sizes"),
    ("task19_parallel_sets.svg",              "Violation vs. Goal"),
]


def generate(log, alignments, output_dir: str, model_path: str = None,
             outcome_activity: str = "A_ACTIVATED"):
    """Generate all Task ID 19 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 19 visualizations ---")

    goal, goal_name, goal_kind, throughput = _build_goal(log, outcome_activity)
    baseline = float(goal.mean()) if len(goal) else 0.0
    logger.info(f"      -> goal: {goal_name} ({goal_kind}); baseline met-rate {baseline:.1%}")

    viol_df = _violation_long(alignments)
    eff_df = _pattern_effects(viol_df, goal, baseline)
    act_eff = _activity_effects(viol_df, goal, baseline)
    logger.info(f"      -> {len(viol_df)} violation rows; top-{len(eff_df)} patterns by effect.")
    for _, row in eff_df.iterrows():
        pat = str(row["pattern"]).encode("ascii", "replace").decode()
        logger.info(f"         {pat:<40} n={int(row['n_traces']):>6}  "
                    f"goal={row['goal_rate']:.1%}  effect={row['effect']*100:+.1f}pp")

    tree = _fit_goal_tree(log, alignments, goal)

    task19_bar_chart(eff_df, baseline, goal_name, output_dir)
    task19_scatter_plot(viol_df, goal, throughput, goal_name, output_dir)
    task19_flow_chart_table(log, act_eff, baseline, goal_name, output_dir)
    task19_flow_chart_elaborate(act_eff, model_path, goal_name, output_dir)
    task19_flow_chart_elaborate_table(eff_df, act_eff, model_path, baseline, goal_name, output_dir)
    task19_tree(tree, goal_name, output_dir)
    task19_table(eff_df, baseline, goal_name, output_dir)
    task19_table_bar_chart(eff_df, baseline, goal_name, output_dir)
    task19_parallel_sets(eff_df, viol_df, goal, output_dir)
