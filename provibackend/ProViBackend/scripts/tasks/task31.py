"""
tasks/task31.py – Task 6: Conformance degree vs. positive process outcome.

Public API:
    generate(log, alignments, outcome_activity, output_dir)
        outcome_activity  – activity name that constitutes a positive outcome
                            (default: "A_ACTIVATED" for BPIC12-A)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["table", "tree", "bar_chart", "stacked_bar", "scatter_plot", "matrix", "heatmap"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates

from shared import (
    save_svg, make_table, draw_decision_tree, wrap_text,
    format_threshold, BLUE, ORANGE, GREEN, RED, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    draw_value_heatmap, render_empty_state_svg,
)
from tasks.task20 import (
    task20_trace_feature_dataframe,
    _task20_gini,
    _task20_feature_label,
)

# Alias so internal references work
_task20_format_threshold = format_threshold


# Task 6 – Conformance degree vs. positive process outcome
# ---------------------------------------------------------------------------

# Task 6 data + labeling helpers
# Module-level outcome activity — overridden by generate() at runtime
_OUTCOME_ACTIVITY = "A_ACTIVATED"
_REJECTED_FINAL_ACTIVITIES = {"A_DECLINED", "A_CANCELLED"}
_TASK6_DURATION_FIRST_SPLIT_DAYS = 5.063008796296296
_TASK6_DURATION_SECOND_SPLIT_DAYS = 29.986660115740737

# ---------------------------------------------------------------------------
# Shared fitness-band constants  (used by bar_chart, stacked_bar, matrix, heatmap)
# ---------------------------------------------------------------------------
_FITNESS_BIN_EDGES        = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
_FITNESS_BIN_LABELS       = ["0.0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–1.0"]
_FITNESS_BIN_LABELS_EXACT = ["0.0–0.2", "0.2–0.4", "0.4–0.6", "0.6–0.8", "0.8–<1.0", "= 1.0"]


def _assign_fitness_band(fitness, include_exact_one=False):
    """Bin a fitness Series into 5 (or 6 with exact-1.0) labelled categories."""
    s = fitness.astype(float).clip(0.0, 1.0)
    if not include_exact_one:
        return pd.cut(s, bins=_FITNESS_BIN_EDGES, labels=_FITNESS_BIN_LABELS,
                      include_lowest=True, right=True)
    result = pd.cut(s.clip(upper=0.9999999), bins=_FITNESS_BIN_EDGES,
                    labels=_FITNESS_BIN_LABELS_EXACT[:5], include_lowest=True, right=False)
    result = result.cat.add_categories("= 1.0")
    result[s >= 1.0] = "= 1.0"
    return result


def _task31_positive_outcome_from_trace(trace) -> bool:
    """Return True if the trace contains the configured positive-outcome activity."""
    activities = {str(event.get("concept:name", "")) for event in trace}
    return _OUTCOME_ACTIVITY in activities


def _task31_rejected_outcome_from_trace(trace) -> bool:
    """Return True if the trace ends with a configured rejection activity."""
    if not trace:
        return False
    last_activity = str(trace[-1].get("concept:name", ""))
    return last_activity in _REJECTED_FINAL_ACTIVITIES


def task31_outcome_dataframe(log, alignments):
    """Build trace-level features for definitive outcome analysis."""
    df = task20_trace_feature_dataframe(log, alignments)
    if df.empty:
        return df
    positive = [_task31_positive_outcome_from_trace(trace) for trace in log]
    rejected = [_task31_rejected_outcome_from_trace(trace) for trace in log]
    definitive = [pos or rej for pos, rej in zip(positive, rejected)]
    df["positive_outcome"] = positive
    df["rejected_outcome"] = rejected
    df["definitive_outcome"] = definitive
    df["conformance_rate"] = df["fitness"].astype(float)
    df["is_fully_conformant"] = (df["fitness"] >= 1.0).astype(float)
    df["is_not_fully_conformant"] = (df["fitness"] < 1.0).astype(float)
    filtered = df.loc[df["definitive_outcome"]].reset_index(drop=True)
    filtered.attrs["total_cases_before_filter"] = len(df)
    filtered.attrs["definitive_cases"] = len(filtered)
    filtered.attrs["excluded_non_definitive_cases"] = len(df) - len(filtered)
    return filtered


def _task31_feature_label(feature: str) -> str:
    if feature == "is_fully_conformant":
        return "conformance_rate = 1.0"
    if feature == "is_not_fully_conformant":
        return "conformance_rate = 1.0"
    if feature == "conformance_rate":
        return "conformance_rate"
    if feature == "duration_hours":
        return "Duration"
    if feature == "resource_count":
        return "unique_resources"
    if feature == "num_events":
        return "number_of_events"
    if feature.startswith("mean_case_AMOUNT_REQ") or feature.startswith("max_case_AMOUNT_REQ"):
        return "requested_amount"
    return _task20_feature_label(feature).replace("trace:", "").replace("time:", "").replace("resource:", "")


def _task31_format_duration_days(hours: float) -> str:
    days = hours / 24
    if abs(days - round(days)) < 0.05:
        return f"{int(round(days))} days"
    return f"{days:.1f} days"


def _task31_condition_text(feature: str, threshold: float, side: str) -> str:
    if feature == "is_fully_conformant":
        return "conformance_rate < 1.0" if side == "left" else "conformance_rate = 1.0"
    if feature == "is_not_fully_conformant":
        return "conformance_rate = 1.0" if side == "left" else "conformance_rate < 1.0"
    op = "<=" if side == "left" else ">"
    if feature == "duration_hours":
        return f"Duration {op} {_task31_format_duration_days(threshold)}"
    return f"{_task31_feature_label(feature)} {op} {_task20_format_threshold(threshold)}"


def _task31_branch_label(side: str) -> str:
    """Label the root conformance branch for table annotations."""
    return "conformance rate = 1.0 branch" if side == "left" else "conformance rate < 1.0 branch"


# Task 6 tree helpers (data/model)
def _task31_node_from_target(y: np.ndarray, depth: int, node_id: int):
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    return {
        "id": node_id,
        "depth": depth,
        "gini": _task20_gini(y),
        "samples": int(len(y)),
        "value": [negatives, positives],
        "class": "paid" if positives >= negatives else "not_paid",
        "feature": None,
        "threshold": None,
        "left": None,
        "right": None,
    }


def _task31_fit_tree(df: pd.DataFrame):
    """Build the Task 6 explanatory tree: conformance first, duration splits next."""
    if df.empty or df["positive_outcome"].nunique() < 2:
        return None

    y = df["positive_outcome"].astype(int).to_numpy()
    if "duration_hours" not in df.columns or "is_not_fully_conformant" not in df.columns:
        return None

    root = _task31_node_from_target(y, depth=0, node_id=1)
    root["feature"] = "is_not_fully_conformant"
    root["threshold"] = 0.5
    left_mask = df["is_not_fully_conformant"].to_numpy(dtype=float) <= 0.5
    right_mask = ~left_mask
    if left_mask.sum() == 0 or right_mask.sum() == 0:
        return None

    full_df = df.loc[left_mask]
    non_full_df = df.loc[right_mask]
    root["left"] = _task31_duration_subtree(full_df, depth=1, node_id=2)
    root["right"] = _task31_node_from_target(non_full_df["positive_outcome"].astype(int).to_numpy(), depth=1, node_id=3)
    _task31_relabel_tree(root)
    return root


def _task31_duration_subtree(df: pd.DataFrame, depth: int, node_id: int):
    """Split the fully conformant branch by the two duration thresholds used in Task 6."""
    y = df["positive_outcome"].astype(int).to_numpy()
    node = _task31_node_from_target(y, depth=depth, node_id=node_id)
    first_threshold = _TASK6_DURATION_FIRST_SPLIT_DAYS * 24
    second_threshold = _TASK6_DURATION_SECOND_SPLIT_DAYS * 24
    node["feature"] = "duration_hours"
    node["threshold"] = first_threshold

    short_mask = df["duration_hours"].astype(float).to_numpy() <= first_threshold
    long_mask = ~short_mask
    node["left"] = _task31_node_from_target(df.loc[short_mask, "positive_outcome"].astype(int).to_numpy(), depth=depth + 1, node_id=node_id * 2)

    long_df = df.loc[long_mask]
    long_y = long_df["positive_outcome"].astype(int).to_numpy()
    long_node = _task31_node_from_target(long_y, depth=depth + 1, node_id=node_id * 2 + 1)
    long_node["feature"] = "duration_hours"
    long_node["threshold"] = second_threshold
    within_mask = long_df["duration_hours"].astype(float).to_numpy() <= second_threshold
    long_node["left"] = _task31_node_from_target(long_df.loc[within_mask, "positive_outcome"].astype(int).to_numpy(), depth=depth + 2, node_id=node_id * 4 + 2)
    long_node["right"] = _task31_node_from_target(long_df.loc[~within_mask, "positive_outcome"].astype(int).to_numpy(), depth=depth + 2, node_id=node_id * 4 + 3)
    node["right"] = long_node
    return node


def _task31_relabel_tree(node: dict):
    negative, positive = node["value"]
    node["class"] = "paid" if positive >= negative else "not_paid"
    if node.get("left") is not None:
        _task31_relabel_tree(node["left"])
    if node.get("right") is not None:
        _task31_relabel_tree(node["right"])


def _task31_collect_table_rows(tree: dict):
    if tree is None:
        return []

    def collect(node, path=None):
        path = [] if path is None else path
        if node.get("left") is None and node.get("right") is None:
            return [{"node": node, "path": path}]
        rows = []
        if node.get("left") is not None:
            rows.extend(collect(node["left"], path + [_task31_condition_text(node["feature"], node["threshold"], "left")]))
        if node.get("right") is not None:
            rows.extend(collect(node["right"], path + [_task31_condition_text(node["feature"], node["threshold"], "right")]))
        return rows

    leaves = []
    for item in collect(tree):
        node = item["node"]
        negatives, positives = node["value"]
        total = node["samples"]
        leaves.append({
            "condition": " AND ".join(item["path"]),
            "positive_cases": positives,
            "total_cases": total,
            "outcome_rate": positives / total if total else 0.0,
        })
    return leaves


def _task31_summary_row(condition: str, positives: int, total: int) -> dict:
    """Build one Task 6 table row."""
    return {
        "condition": condition,
        "positive_cases": positives,
        "total_cases": total,
        "outcome_rate": positives / total if total else 0.0,
    }


def _task31_child_split_rows(root_child: dict, branch_side: str):
    """Return one-level split rows for a conformance branch, matching the reference table."""
    if root_child is None or root_child.get("feature") is None:
        return []
    rows = []
    for side in ["left", "right"]:
        child = root_child.get(side)
        if child is None:
            continue
        condition = _task31_condition_text(root_child["feature"], root_child["threshold"], side)
        negatives, positives = child["value"]
        total = child["samples"]
        rows.append(_task31_summary_row(
            f"{condition} ({_task31_branch_label(branch_side)})",
            positives,
            total,
        ))
    return rows


def task31_summary_table_dataframe(df: pd.DataFrame, tree: dict):
    """Summarize success rate by conformance root branches and branch split conditions."""
    if df.empty:
        return pd.DataFrame(columns=["condition", "positive_cases", "total_cases", "outcome_rate"])

    rows = []
    for label, mask in [
        ("Conformance rate = 1.0", df["is_fully_conformant"] > 0.5),
        ("Conformance rate < 1.0", df["is_fully_conformant"] <= 0.5),
    ]:
        subset = df.loc[mask]
        total = len(subset)
        positives = int(subset["positive_outcome"].sum())
        rows.append(_task31_summary_row(label, positives, total))

    if tree is not None:
        full_branch = tree.get("left")
        rows.extend(_task31_child_split_rows(full_branch, "left"))
        longer_branch = full_branch.get("right") if full_branch is not None else None
        if longer_branch is not None and longer_branch.get("feature") is not None:
            for side in ["left", "right"]:
                child = longer_branch.get(side)
                if child is None:
                    continue
                condition = _task31_condition_text(longer_branch["feature"], longer_branch["threshold"], side)
                _, positives = child["value"]
                rows.append(_task31_summary_row(
                    f"{condition} (conformance rate = 1.0, duration > 5.1 branch)",
                    positives,
                    child["samples"],
                ))
    return pd.DataFrame(rows)


# Task 6 visualizations
def task31_table(df_table: pd.DataFrame, output_dir: str):
    """Task 6 table: approval rate by conformance and duration branch conditions."""
    cell_text = []
    for _, row in df_table.iterrows():
        cell_text.append([
            wrap_text(row["condition"], 46),
            f"{int(row['positive_cases']):,}",
            f"{int(row['total_cases']):,}",
            f"{row['outcome_rate'] * 100:.1f}",
        ])

    fig_h = max(3.3, 1.35 + len(cell_text) * 0.52)
    fig, ax = plt.subplots(figsize=(10.6, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Attribute Condition", "Approved Cases", "Total Cases", "Approval Rate (%)"],
        bbox=[0.04, 0.08, 0.92, 0.70],
        col_widths=[0.50, 0.16, 0.22, 0.16],
        font_size=10.5,
        scale_xy=(1, 1.85),
        header_color="#555555",
        zebra=True,
    )
    ax.set_title("Conformance and Approval Rates", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(rect=[0, 0.02, 1, 0.96])
    save_svg(fig, os.path.join(output_dir, "task31_table.svg"))


def _task31_draw_decision_tree(ax, tree: dict, title=True):
    def wrap_width(text: str) -> int:
        n = len("" if text is None else str(text))
        if n <= 22:
            return 30
        if n <= 36:
            return 26
        return 22

    draw_decision_tree(
        ax,
        tree,
        title="Conformance and Outcome Predictors" if title else "",
        title_fontsize=FONT_TITLE,
        title_pad=8,
        box_w=2.42,
        base_font=7.8,
        min_font=6.1,
        line_height=0.18,
        box_padding_h=0.16,
        wrap_width_fn=wrap_width,
        first_line_fn=lambda node: (
            ""
            if node.get("feature") is None
            else "conformance_rate < 1.0"
            if node["feature"] == "is_fully_conformant"
            else "conformance_rate = 1.0"
            if node["feature"] == "is_not_fully_conformant"
            else f"Duration <= {_task31_format_duration_days(node['threshold'])}"
            if node["feature"] == "duration_hours"
            else f"{_task31_feature_label(node['feature'])} <= {_task20_format_threshold(node['threshold'])}"
        ),
        value_pair_fn=lambda node: (node["value"][0], node["value"][1]),
        node_facecolor_fn=lambda node: (
            "#888888"
            if node["value"][1] > node["value"][0]
            else "#F4F4F4"
            if node["value"][1] == node["value"][0]
            else "#E0E0E0"
        ),
        edge_arrowprops=dict(arrowstyle="-|>", color="#555555", linewidth=1.35, shrinkA=5, shrinkB=5),
        edge_label_fontsize=FONT_ANNOT,
        edge_label_offset_y=0.14,
        x_pad_factor=0.70,
        y_pad_base=0.80,
        y_top_pad=0.95,
    )


def task31_tree(tree: dict, output_dir: str):
    """Standalone Task 31 decision tree."""
    fig, ax = plt.subplots(figsize=(11.0, 6.6))
    _task31_draw_decision_tree(ax, tree)
    legend = [
        mpatches.Patch(facecolor="#E0E0E0", edgecolor="#555555", label="Mostly not paid"),
        mpatches.Patch(facecolor="#888888", edgecolor="#555555", label="Mostly paid"),
    ]
    ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.03), ncol=2, frameon=False, fontsize=FONT_ANNOT)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task31_tree.svg"))


# ---------------------------------------------------------------------------
# New idiom 1: Bar chart — outcome rate per conformance band
# ---------------------------------------------------------------------------

def task31_bar_chart(df: pd.DataFrame, output_dir: str):
    """Bar chart: positive outcome rate per conformance degree band (6 bands incl. exact 1.0)."""
    out_path = os.path.join(output_dir, "task31_bar_chart.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Conformance Degree vs. Positive Outcome Rate")
        return

    bands = _assign_fitness_band(df["fitness"], include_exact_one=True)
    agg_rows = []
    for label in _FITNESS_BIN_LABELS_EXACT:
        mask = bands == label
        n = int(mask.sum())
        n_pos = int(df.loc[mask, "positive_outcome"].sum()) if n > 0 else 0
        rate = n_pos / n * 100 if n > 0 else float("nan")
        agg_rows.append({"band": label, "n": n, "n_pos": n_pos, "rate": rate})
    agg = pd.DataFrame(agg_rows)

    x = np.arange(len(_FITNESS_BIN_LABELS_EXACT))

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    ax.set_facecolor("#fafbfc")

    bars = ax.bar(x, agg["rate"].fillna(0), width=0.58, color=BLUE, zorder=3)

    # Annotate each non-empty bar with "rate% (n=N)" above bar
    max_rate = float(agg["rate"].fillna(0).max())
    for i, row in agg.iterrows():
        n = row["n"]
        rate = row["rate"]
        if n == 0 or np.isnan(rate):
            continue
        ax.text(i, rate + max_rate * 0.02 + 0.5,
                f"{rate:.1f}%  (n={n})",
                ha="center", va="bottom", fontsize=FONT_ANNOT, color="#222222")

    ax.set_ylim(0, max(max_rate * 1.20, 10))
    ax.set_xlim(-0.6, len(_FITNESS_BIN_LABELS_EXACT) - 0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(_FITNESS_BIN_LABELS_EXACT, fontsize=FONT_ANNOT)
    ax.set_xlabel("Conformance Degree (fitness)", fontsize=FONT_LABEL)
    ax.set_ylabel("Positive Outcome Rate (%)", fontsize=FONT_LABEL)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    ax.set_title("Conformance Degree vs. Positive Outcome Rate", fontsize=FONT_TITLE, pad=10)

    caption = "Definitive outcomes only  ·  Bin '= 1.0' = fitness exactly 1.0"
    fig.text(0.0, 0.01, caption, ha="left", fontsize=FONT_ANNOT - 1, color="#888888")
    fig.tight_layout(rect=[0, 0.06, 1, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 2: Stacked bar — outcome composition per conformance band
# ---------------------------------------------------------------------------

def task31_stacked_bar(df: pd.DataFrame, output_dir: str):
    """100%-stacked bar: positive vs negative outcome proportion per conformance band."""
    out_path = os.path.join(output_dir, "task31_stacked_bar.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Outcome Composition by Conformance Band")
        return

    bands = _assign_fitness_band(df["fitness"], include_exact_one=True)
    band_data = []
    for label in _FITNESS_BIN_LABELS_EXACT:
        mask = bands == label
        n = int(mask.sum())
        if n == 0:
            continue
        n_pos = int(df.loc[mask, "positive_outcome"].sum())
        prop_pos = n_pos / n
        prop_neg = 1.0 - prop_pos
        band_data.append({"band": label, "n": n, "prop_pos": prop_pos, "prop_neg": prop_neg})

    if not band_data:
        render_empty_state_svg(out_path, "Outcome Composition by Conformance Band")
        return

    n_nonempty = len(band_data)
    fig_w = max(6.5, min(11.0, 1.3 * n_nonempty + 2.0))
    fig, ax = plt.subplots(figsize=(fig_w, 5.2))
    ax.set_facecolor("#fafbfc")

    x = np.arange(n_nonempty)
    # Encode n= into x-tick labels (avoids below-axis collision)
    band_labels = [f"{d['band']}\n(n={d['n']})" for d in band_data]
    prop_pos_arr = np.array([d["prop_pos"] for d in band_data])
    prop_neg_arr = np.array([d["prop_neg"] for d in band_data])

    # Bottom segment = positive (darker), top = negative (lighter)
    bars_pos = ax.bar(x, prop_pos_arr, color="#555555", label="Positive outcome")
    bars_neg = ax.bar(x, prop_neg_arr, bottom=prop_pos_arr, color="#CCCCCC", label="Negative outcome")

    # Annotate segments
    for i in range(n_nonempty):
        # Positive segment
        if prop_pos_arr[i] >= 0.08:
            ax.text(i, prop_pos_arr[i] / 2, f"{prop_pos_arr[i] * 100:.0f}%",
                    ha="center", va="center", fontsize=FONT_ANNOT, color="#ffffff")
        # Negative segment
        if prop_neg_arr[i] >= 0.08:
            ax.text(i, prop_pos_arr[i] + prop_neg_arr[i] / 2, f"{prop_neg_arr[i] * 100:.0f}%",
                    ha="center", va="center", fontsize=FONT_ANNOT, color="#222222")

    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=FONT_ANNOT)
    ax.set_xticks(x)
    ax.set_xticklabels(band_labels, fontsize=FONT_ANNOT)
    ax.set_xlabel("Conformance Band (fitness)", fontsize=FONT_LABEL)
    ax.set_ylabel("Proportion of Cases", fontsize=FONT_LABEL)
    ax.set_xlim(-0.6, n_nonempty - 0.4)
    ax.set_ylim(0, 1.0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)

    legend_patches = [
        mpatches.Patch(facecolor="#555555", label="Positive outcome"),
        mpatches.Patch(facecolor="#CCCCCC", label="Negative outcome"),
    ]
    ax.legend(handles=legend_patches,
              loc="upper left", bbox_to_anchor=(1.01, 1),
              frameon=True, framealpha=0.9, fontsize=FONT_ANNOT,
              borderaxespad=0)
    ax.set_title("Outcome Composition by Conformance Band", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout(rect=[0, 0, 0.88, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 3: Scatter plot — trace-level fitness vs outcome + temporal panel
# ---------------------------------------------------------------------------

def _task31_extract_start_times(log, df):
    """Extract start timestamps for traces in df, keyed by trace_index."""
    ts_map = {}
    for i, trace in enumerate(log):
        if not trace:
            continue
        ts = trace[0].get("time:timestamp")
        if ts is not None:
            ts_map[i] = ts
    if "trace_index" not in df.columns:
        return {}
    result = {}
    for _, row in df.iterrows():
        idx = int(row["trace_index"])
        if idx in ts_map:
            result[idx] = ts_map[idx]
    return result


def task31_scatter_plot(df: pd.DataFrame, log, output_dir: str):
    """Scatter: trace-level fitness vs outcome with bin-mean trend line."""
    out_path = os.path.join(output_dir, "task31_scatter_plot.svg")
    if len(df) < 15:
        render_empty_state_svg(out_path, "Conformance Degree vs. Outcome")
        return

    fitness = df["fitness"].astype(float).to_numpy()
    outcome = df["positive_outcome"].astype(int).to_numpy()

    # Downsample for scatter if needed
    sampled = False
    if len(df) > 2000:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(df), size=2000, replace=False)
        idx.sort()
        fit_s = fitness[idx]
        out_s = outcome[idx]
        sampled = True
    else:
        fit_s = fitness
        out_s = outcome

    # Compute 10-bin trend line (use full data, not sampled)
    bins = np.linspace(0, 1, 11)
    bin_idx = np.digitize(fitness, bins[1:-1])
    midpoints, rates, ses = [], [], []
    for b in range(10):
        mask = bin_idx == b
        n_b = mask.sum()
        if n_b >= 5:
            mid = (bins[b] + bins[b + 1]) / 2
            r = outcome[mask].mean()
            se = np.sqrt(r * (1 - r) / n_b)
            midpoints.append(mid)
            rates.append(r)
            ses.append(se)
    midpoints = np.array(midpoints)
    rates = np.array(rates)
    ses = np.array(ses)

    fig, ax = plt.subplots(figsize=(9.0, 5.2))

    jitter = np.random.default_rng(42).uniform(-0.07, 0.07, size=len(out_s))
    pos_mask_s = out_s == 1
    neg_mask_s = out_s == 0
    ax.scatter(fit_s[neg_mask_s], jitter[neg_mask_s],
               color="#BBBBBB", s=18, alpha=0.35, marker="o", label="Negative outcome")
    ax.scatter(fit_s[pos_mask_s], 1 + jitter[pos_mask_s],
               color="#333333", s=18, alpha=0.35, marker="o", label="Positive outcome")

    ax.set_ylim(-0.45, 1.45)
    ax.set_yticks([-0.35, 1.35])
    ax.set_yticklabels(["Negative", "Positive"], fontsize=FONT_ANNOT)
    ax.set_xlim(-0.03, 1.03)
    ax.set_xlabel("Conformance Degree (fitness)", fontsize=FONT_LABEL)
    ax.set_ylabel("Outcome", fontsize=FONT_LABEL)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.set_title("Conformance Degree vs. Outcome", fontsize=FONT_TITLE, pad=8)
    legend_patches = [
        mpatches.Patch(color="#333333", label="Positive outcome"),
        mpatches.Patch(color="#BBBBBB", label="Negative outcome"),
    ]
    ax.legend(handles=legend_patches, loc="upper left", frameon=False, fontsize=FONT_ANNOT)

    caption = "Definitive outcomes only"
    if sampled:
        caption += "  ·  Scatter shows 2,000 sampled traces"
    fig.text(0.0, 0.01, caption, ha="left", fontsize=FONT_ANNOT - 1, color="#888888")

    fig.tight_layout(rect=[0, 0.05, 1, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 4: Matrix — P(outcome | fitness band) exact rates
# ---------------------------------------------------------------------------

def task31_matrix(df: pd.DataFrame, output_dir: str):
    """Annotated matrix: outcome rate (negative/positive) per 5 conformance bands + totals row."""
    out_path = os.path.join(output_dir, "task31_matrix.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Outcome Rate by Conformance Band")
        return

    bands = _assign_fitness_band(df["fitness"], include_exact_one=False)
    counts = np.zeros((5, 2), dtype=int)
    for i, label in enumerate(_FITNESS_BIN_LABELS):
        mask = bands == label
        n = int(mask.sum())
        n_pos = int(df.loc[mask, "positive_outcome"].sum()) if n > 0 else 0
        counts[i, 0] = n - n_pos  # negative
        counts[i, 1] = n_pos      # positive

    # Check that at least 2 bands are non-empty
    row_totals = counts.sum(axis=1)
    if (row_totals > 0).sum() < 2:
        render_empty_state_svg(out_path, "Outcome Rate by Conformance Band")
        return

    # Totals row
    totals_row = counts.sum(axis=0, keepdims=True)
    counts_full = np.vstack([counts, totals_row])
    row_totals_full = counts_full.sum(axis=1)

    # Rate matrix (row-normalized)
    rate_matrix = np.where(
        row_totals_full[:, np.newaxis] > 0,
        counts_full / row_totals_full[:, np.newaxis] * 100,
        0.0,
    )

    fig_h = max(3.8, min(7.0, 1.3 + 6 * 0.72))
    fig, ax = plt.subplots(figsize=(6.0, fig_h))

    draw_value_heatmap(
        fig, ax,
        data=np.nan_to_num(rate_matrix, nan=0.0),
        row_labels=_FITNESS_BIN_LABELS + ["All bands"],
        col_labels=["Negative Outcome", "Positive Outcome"],
        xlabel="Outcome Category",
        cbar_label="% of traces in band",
        annotate=False,   # manual two-line annotations added below
        rotate_xticks=0,
    )

    # Set colorbar limits
    images = ax.get_images()
    if images:
        images[0].set_clim(0, 100)

    # Manual cell annotation
    n_rows, n_cols = rate_matrix.shape
    for r in range(n_rows):
        rt = row_totals_full[r]
        for c in range(n_cols):
            rate = rate_matrix[r, c]
            count = counts_full[r, c]
            if rt == 0:
                ax.text(c, r, "—", ha="center", va="center",
                        fontsize=FONT_ANNOT, color="#AAAAAA")
            else:
                text_color = "#ffffff" if rate > 55 else "#222222"
                ax.text(c, r, f"{rate:.1f}%\n(n={int(count)})",
                        ha="center", va="center", fontsize=FONT_ANNOT - 1,
                        color=text_color, linespacing=1.4)

    # Dashed separator above totals row
    ax.axhline(y=4.5, color="#AAAAAA", lw=1.0, ls="--")

    ax.set_ylabel("Fitness Band", fontsize=FONT_LABEL)
    # Matrix convention: keep all four spines (bounding box of the color grid)
    ax.set_title("Outcome Rate by Conformance Band", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout()
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 5: Heatmap — outcome rate by conformance band and calendar period
# ---------------------------------------------------------------------------

_HEATMAP_MIN_CELL_N = 5


def task31_heatmap(df: pd.DataFrame, log, output_dir: str):
    """Heatmap: positive outcome rate per fitness band x calendar period."""
    out_path = os.path.join(output_dir, "task31_heatmap.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Positive Outcome Rate by Conformance Band and Period")
        return

    # Extract timestamps
    ts_map = _task31_extract_start_times(log, df)
    if "trace_index" not in df.columns or len(ts_map) < 10:
        render_empty_state_svg(out_path, "Positive Outcome Rate by Conformance Band and Period")
        return

    try:
        ts_series = df["trace_index"].map(ts_map)
        valid_mask = ts_series.notna()
        if valid_mask.sum() < 10:
            render_empty_state_svg(out_path, "Positive Outcome Rate by Conformance Band and Period")
            return
        df_t = df.loc[valid_mask].copy()
        # Normalize to tz-naive UTC so mixed-tz timestamps don't raise TypeError
        raw_ts = pd.to_datetime(ts_series[valid_mask], utc=True, errors="coerce")
        df_t["_start_time"] = raw_ts.dt.tz_localize(None)
    except Exception:
        render_empty_state_svg(out_path, "Positive Outcome Rate by Conformance Band and Period")
        return

    # Determine granularity
    min_ts = df_t["_start_time"].min()
    max_ts = df_t["_start_time"].max()
    n_quarters = (max_ts.year - min_ts.year) * 4 + (max_ts.quarter - min_ts.quarter) + 1
    if n_quarters >= 3:
        granularity = "Q"
        granularity_label = "quarterly"
        df_t["_period"] = df_t["_start_time"].dt.to_period("Q")
        def fmt_period(p):
            return f"Q{p.quarter} '{str(p.year)[-2:]}"
    else:
        granularity = "M"
        granularity_label = "monthly"
        df_t["_period"] = df_t["_start_time"].dt.to_period("M")
        _month_abbr = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
        def fmt_period(p):
            return f"{_month_abbr[p.month - 1]} '{str(p.year)[-2:]}"

    periods_sorted = sorted(df_t["_period"].unique())
    if len(periods_sorted) < 2:
        render_empty_state_svg(out_path, "Positive Outcome Rate by Conformance Band and Period")
        return

    period_labels = [fmt_period(p) for p in periods_sorted]
    n_periods = len(periods_sorted)

    # 5-band binning
    bands = _assign_fitness_band(df_t["fitness"], include_exact_one=False)
    df_t["_band"] = bands

    # Build matrix: rows = bands (low→high), cols = periods
    matrix_counts = np.zeros((5, n_periods), dtype=int)
    matrix_pos = np.zeros((5, n_periods), dtype=int)
    period_to_idx = {p: i for i, p in enumerate(periods_sorted)}
    for bi, blabel in enumerate(_FITNESS_BIN_LABELS):
        band_mask = df_t["_band"] == blabel
        sub = df_t.loc[band_mask]
        for _, row in sub.iterrows():
            pi = period_to_idx.get(row["_period"])
            if pi is not None:
                matrix_counts[bi, pi] += 1
                if row["positive_outcome"]:
                    matrix_pos[bi, pi] += 1

    # Rate matrix with NaN for insufficient cells
    rate_matrix = np.full((5, n_periods), np.nan)
    for bi in range(5):
        for pi in range(n_periods):
            n = matrix_counts[bi, pi]
            if n >= _HEATMAP_MIN_CELL_N:
                rate_matrix[bi, pi] = matrix_pos[bi, pi] / n * 100

    # Display order: high fitness at top → reverse rows
    matrix_disp = rate_matrix[::-1, :]
    counts_disp = matrix_counts[::-1, :]
    pos_disp = matrix_pos[::-1, :]
    row_labels_disp = list(reversed(_FITNESS_BIN_LABELS))

    fig_w = max(7.0, min(18.0, 1.8 + n_periods * 1.1))
    fig_h = max(4.0, min(7.0, 1.5 + 5 * 0.75))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))

    draw_value_heatmap(
        fig, ax,
        data=np.nan_to_num(matrix_disp, nan=0.0),
        row_labels=row_labels_disp,
        col_labels=period_labels,
        xlabel="Period",
        cbar_label="Positive Outcome Rate (%)",
        annotate=False,
        rotate_xticks=30,
    )

    images = ax.get_images()
    if images:
        images[0].set_clim(0, 100)

    # NaN cell overlay (grey rectangle)
    for bi in range(5):
        for pi in range(n_periods):
            n = counts_disp[bi, pi]
            rate = matrix_disp[bi, pi]
            if np.isnan(rate):
                rect = plt.Rectangle(
                    (pi - 0.5, bi - 0.5), 1, 1,
                    facecolor="#F0F0F0", edgecolor="none", zorder=2,
                )
                ax.add_patch(rect)

    # Manual cell annotations
    for bi in range(5):
        for pi in range(n_periods):
            n = counts_disp[bi, pi]
            rate = matrix_disp[bi, pi]
            if n >= _HEATMAP_MIN_CELL_N:
                text_color = "#ffffff" if rate > 55 else "#222222"
                ax.text(pi, bi, f"{rate:.0f}%\n(n={n})",
                        ha="center", va="center", fontsize=FONT_ANNOT,
                        color=text_color, linespacing=1.4, zorder=3)
            elif n > 0:
                ax.text(pi, bi, f"n={n}", ha="center", va="center",
                        fontsize=FONT_ANNOT, color="#AAAAAA", zorder=3)
            else:
                ax.text(pi, bi, "—", ha="center", va="center",
                        fontsize=FONT_ANNOT, color="#DDDDDD", zorder=3)

    ax.set_ylabel("Conformance Band (fitness)", fontsize=FONT_LABEL)
    # Heatmap convention: keep all four spines (bounding box of the color matrix)
    ax.set_title("Positive Outcome Rate by Conformance Band and Period", fontsize=FONT_TITLE, pad=10)

    footnote = (
        f"Definitive outcomes only  ·  Cells with n < {_HEATMAP_MIN_CELL_N} shown in grey"
        f"  ·  Granularity: {granularity_label}"
    )
    fig.text(0.01, 0.01, footnote, ha="left",
             fontsize=FONT_ANNOT - 1, color="#888888")

    fig.tight_layout(rect=[0, 0.07, 1, 1])
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str, outcome_activity: str = "A_ACTIVATED"):
    """Generate all Task 6 SVGs into output_dir.

    outcome_activity: the activity name that marks a positive process outcome.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 6 visualizations ---")
    # Patch the outcome detection to use the provided activity name
    import tasks.task31 as _self
    _self._OUTCOME_ACTIVITY = outcome_activity

    df = task31_outcome_dataframe(log, alignments)
    if df.empty:
        logger.warning("      Skipped Task 6: no trace-level outcome features found.")
        return
    tree = _task31_fit_tree(df)
    table = task31_summary_table_dataframe(df, tree)
    positive_rate = float(df["positive_outcome"].mean())
    excluded = df.attrs.get("excluded_non_definitive_cases", 0)
    logger.info(f"      -> Definitive outcomes: {len(df)} cases  |  Excluded non-definitive: {excluded}")
    logger.info(f"      -> Positive outcome ({outcome_activity}): {int(df['positive_outcome'].sum())}/{len(df)} ({positive_rate:.2%})")
    task31_table(table, output_dir)
    task31_tree(tree, output_dir)
    task31_bar_chart(df, output_dir)
    task31_stacked_bar(df, output_dir)
    task31_scatter_plot(df, log, output_dir)
    task31_matrix(df, output_dir)
    task31_heatmap(df, log, output_dir)
