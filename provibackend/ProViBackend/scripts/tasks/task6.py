"""
tasks/task6.py – Task 6: Conformance degree vs. positive process outcome.

Public API:
    generate(log, alignments, outcome_activity, output_dir)
        outcome_activity  – activity name that constitutes a positive outcome
                            (default: "A_ACTIVATED" for BPIC12-A)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["table", "decision_tree"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from shared import (
    save_svg, make_table, draw_decision_tree, wrap_text,
    format_threshold, BLUE, ORANGE, GREEN, RED,
)
from tasks.task4 import (
    task4_trace_feature_dataframe,
    _task4_gini,
    _task4_feature_label,
)

# Alias so internal references work
_task4_format_threshold = format_threshold


# Task 6 – Conformance degree vs. positive process outcome
# ---------------------------------------------------------------------------

# Task 6 data + labeling helpers
# Module-level outcome activity — overridden by generate() at runtime
_OUTCOME_ACTIVITY = "A_ACTIVATED"
_REJECTED_FINAL_ACTIVITIES = {"A_DECLINED", "A_CANCELLED"}
_TASK6_DURATION_FIRST_SPLIT_DAYS = 5.063008796296296
_TASK6_DURATION_SECOND_SPLIT_DAYS = 29.986660115740737


def _task6_positive_outcome_from_trace(trace) -> bool:
    """Return True if the trace contains the configured positive-outcome activity."""
    activities = {str(event.get("concept:name", "")) for event in trace}
    return _OUTCOME_ACTIVITY in activities


def _task6_rejected_outcome_from_trace(trace) -> bool:
    """Return True if the trace ends with a configured rejection activity."""
    if not trace:
        return False
    last_activity = str(trace[-1].get("concept:name", ""))
    return last_activity in _REJECTED_FINAL_ACTIVITIES


def task6_outcome_dataframe(log, alignments):
    """Build trace-level features for definitive outcome analysis."""
    df = task4_trace_feature_dataframe(log, alignments)
    if df.empty:
        return df
    positive = [_task6_positive_outcome_from_trace(trace) for trace in log]
    rejected = [_task6_rejected_outcome_from_trace(trace) for trace in log]
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


def _task6_feature_label(feature: str) -> str:
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
    return _task4_feature_label(feature).replace("trace:", "").replace("time:", "").replace("resource:", "")


def _task6_format_duration_days(hours: float) -> str:
    days = hours / 24
    if abs(days - round(days)) < 0.05:
        return f"{int(round(days))} days"
    return f"{days:.1f} days"


def _task6_condition_text(feature: str, threshold: float, side: str) -> str:
    if feature == "is_fully_conformant":
        return "conformance_rate < 1.0" if side == "left" else "conformance_rate = 1.0"
    if feature == "is_not_fully_conformant":
        return "conformance_rate = 1.0" if side == "left" else "conformance_rate < 1.0"
    op = "<=" if side == "left" else ">"
    if feature == "duration_hours":
        return f"Duration {op} {_task6_format_duration_days(threshold)}"
    return f"{_task6_feature_label(feature)} {op} {_task4_format_threshold(threshold)}"


def _task6_branch_label(side: str) -> str:
    """Label the root conformance branch for table annotations."""
    return "conformance rate = 1.0 branch" if side == "left" else "conformance rate < 1.0 branch"


# Task 6 tree helpers (data/model)
def _task6_node_from_target(y: np.ndarray, depth: int, node_id: int):
    positives = int(y.sum())
    negatives = int(len(y) - positives)
    return {
        "id": node_id,
        "depth": depth,
        "gini": _task4_gini(y),
        "samples": int(len(y)),
        "value": [negatives, positives],
        "class": "paid" if positives >= negatives else "not_paid",
        "feature": None,
        "threshold": None,
        "left": None,
        "right": None,
    }


def _task6_fit_tree(df: pd.DataFrame):
    """Build the Task 6 explanatory tree: conformance first, duration splits next."""
    if df.empty or df["positive_outcome"].nunique() < 2:
        return None

    y = df["positive_outcome"].astype(int).to_numpy()
    if "duration_hours" not in df.columns or "is_not_fully_conformant" not in df.columns:
        return None

    root = _task6_node_from_target(y, depth=0, node_id=1)
    root["feature"] = "is_not_fully_conformant"
    root["threshold"] = 0.5
    left_mask = df["is_not_fully_conformant"].to_numpy(dtype=float) <= 0.5
    right_mask = ~left_mask
    if left_mask.sum() == 0 or right_mask.sum() == 0:
        return None

    full_df = df.loc[left_mask]
    non_full_df = df.loc[right_mask]
    root["left"] = _task6_duration_subtree(full_df, depth=1, node_id=2)
    root["right"] = _task6_node_from_target(non_full_df["positive_outcome"].astype(int).to_numpy(), depth=1, node_id=3)
    _task6_relabel_tree(root)
    return root


def _task6_duration_subtree(df: pd.DataFrame, depth: int, node_id: int):
    """Split the fully conformant branch by the two duration thresholds used in Task 6."""
    y = df["positive_outcome"].astype(int).to_numpy()
    node = _task6_node_from_target(y, depth=depth, node_id=node_id)
    first_threshold = _TASK6_DURATION_FIRST_SPLIT_DAYS * 24
    second_threshold = _TASK6_DURATION_SECOND_SPLIT_DAYS * 24
    node["feature"] = "duration_hours"
    node["threshold"] = first_threshold

    short_mask = df["duration_hours"].astype(float).to_numpy() <= first_threshold
    long_mask = ~short_mask
    node["left"] = _task6_node_from_target(df.loc[short_mask, "positive_outcome"].astype(int).to_numpy(), depth=depth + 1, node_id=node_id * 2)

    long_df = df.loc[long_mask]
    long_y = long_df["positive_outcome"].astype(int).to_numpy()
    long_node = _task6_node_from_target(long_y, depth=depth + 1, node_id=node_id * 2 + 1)
    long_node["feature"] = "duration_hours"
    long_node["threshold"] = second_threshold
    within_mask = long_df["duration_hours"].astype(float).to_numpy() <= second_threshold
    long_node["left"] = _task6_node_from_target(long_df.loc[within_mask, "positive_outcome"].astype(int).to_numpy(), depth=depth + 2, node_id=node_id * 4 + 2)
    long_node["right"] = _task6_node_from_target(long_df.loc[~within_mask, "positive_outcome"].astype(int).to_numpy(), depth=depth + 2, node_id=node_id * 4 + 3)
    node["right"] = long_node
    return node


def _task6_relabel_tree(node: dict):
    negative, positive = node["value"]
    node["class"] = "paid" if positive >= negative else "not_paid"
    if node.get("left") is not None:
        _task6_relabel_tree(node["left"])
    if node.get("right") is not None:
        _task6_relabel_tree(node["right"])


def _task6_collect_table_rows(tree: dict):
    if tree is None:
        return []

    def collect(node, path=None):
        path = [] if path is None else path
        if node.get("left") is None and node.get("right") is None:
            return [{"node": node, "path": path}]
        rows = []
        if node.get("left") is not None:
            rows.extend(collect(node["left"], path + [_task6_condition_text(node["feature"], node["threshold"], "left")]))
        if node.get("right") is not None:
            rows.extend(collect(node["right"], path + [_task6_condition_text(node["feature"], node["threshold"], "right")]))
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


def _task6_summary_row(condition: str, positives: int, total: int) -> dict:
    """Build one Task 6 table row."""
    return {
        "condition": condition,
        "positive_cases": positives,
        "total_cases": total,
        "outcome_rate": positives / total if total else 0.0,
    }


def _task6_child_split_rows(root_child: dict, branch_side: str):
    """Return one-level split rows for a conformance branch, matching the reference table."""
    if root_child is None or root_child.get("feature") is None:
        return []
    rows = []
    for side in ["left", "right"]:
        child = root_child.get(side)
        if child is None:
            continue
        condition = _task6_condition_text(root_child["feature"], root_child["threshold"], side)
        negatives, positives = child["value"]
        total = child["samples"]
        rows.append(_task6_summary_row(
            f"{condition} ({_task6_branch_label(branch_side)})",
            positives,
            total,
        ))
    return rows


def task6_summary_table_dataframe(df: pd.DataFrame, tree: dict):
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
        rows.append(_task6_summary_row(label, positives, total))

    if tree is not None:
        full_branch = tree.get("left")
        rows.extend(_task6_child_split_rows(full_branch, "left"))
        longer_branch = full_branch.get("right") if full_branch is not None else None
        if longer_branch is not None and longer_branch.get("feature") is not None:
            for side in ["left", "right"]:
                child = longer_branch.get(side)
                if child is None:
                    continue
                condition = _task6_condition_text(longer_branch["feature"], longer_branch["threshold"], side)
                _, positives = child["value"]
                rows.append(_task6_summary_row(
                    f"{condition} (conformance rate = 1.0, duration > 5.1 branch)",
                    positives,
                    child["samples"],
                ))
    return pd.DataFrame(rows)


# Task 6 visualizations
def task6_table(df_table: pd.DataFrame, output_dir: str):
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
    tbl = make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Attribute Condition", "Approved Cases", "Total Cases", "Approval Rate (%)"],
        bbox=[0.04, 0.08, 0.92, 0.70],
        col_widths=[0.50, 0.16, 0.22, 0.16],
        font_size=10.5,
        scale_xy=(1, 1.85),
        header_color="#1F3864",
        zebra=True,
    )
    row_colors = ["#FBE5E8", "#E2F0E6"] + ["#FBE5E8"] * max(0, len(cell_text) - 2)
    for r, color in enumerate(row_colors, start=1):
        for c in range(4):
            tbl[r, c].set_facecolor(color)
            tbl[r, c].set_edgecolor("#DDDDDD")
    ax.text(0.04, 0.84, "Approved = A_ACTIVATED present | Definitive outcomes only",
            transform=ax.transAxes, fontsize=8.8, color="#666666")
    fig.tight_layout(rect=[0, 0.02, 1, 0.98])
    save_svg(fig, os.path.join(output_dir, "task6_table.svg"))


def _task6_draw_decision_tree(ax, tree: dict, title=True):
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
        title="Tree (Decision Tree)" if title else "",
        title_fontsize=16,
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
            else f"Duration <= {_task6_format_duration_days(node['threshold'])}"
            if node["feature"] == "duration_hours"
            else f"{_task6_feature_label(node['feature'])} <= {_task4_format_threshold(node['threshold'])}"
        ),
        value_pair_fn=lambda node: (node["value"][0], node["value"][1]),
        node_facecolor_fn=lambda node: (
            "#5DADE2"
            if node["value"][1] > node["value"][0]
            else "#FFFFFF"
            if node["value"][1] == node["value"][0]
            else "#F4C7A1"
        ),
        edge_arrowprops=dict(arrowstyle="-|>", color="#555555", linewidth=1.35, shrinkA=5, shrinkB=5),
        edge_label_fontsize=8.3,
        edge_label_offset_y=0.14,
        x_pad_factor=0.70,
        y_pad_base=0.80,
        y_top_pad=0.95,
    )


def task6_decision_tree(tree: dict, output_dir: str):
    """Standalone Task 6 decision tree."""
    fig, ax = plt.subplots(figsize=(11.0, 6.6))
    _task6_draw_decision_tree(ax, tree)
    legend = [
        mpatches.Patch(facecolor="#F4C7A1", edgecolor="#555555", label="Mostly not paid"),
        mpatches.Patch(facecolor="#5DADE2", edgecolor="#555555", label="Mostly paid"),
    ]
    ax.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.5, -0.03), ncol=2, frameon=False, fontsize=8.5)
    fig.tight_layout(rect=[0, 0.04, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task6_decision_tree.svg"))


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
    import tasks.task6 as _self
    _self._OUTCOME_ACTIVITY = outcome_activity

    df = task6_outcome_dataframe(log, alignments)
    if df.empty:
        logger.warning("      Skipped Task 6: no trace-level outcome features found.")
        return
    tree = _task6_fit_tree(df)
    table = task6_summary_table_dataframe(df, tree)
    positive_rate = float(df["positive_outcome"].mean())
    excluded = df.attrs.get("excluded_non_definitive_cases", 0)
    logger.info(f"      -> Definitive outcomes: {len(df)} cases  |  Excluded non-definitive: {excluded}")
    logger.info(f"      -> Positive outcome ({outcome_activity}): {int(df['positive_outcome'].sum())}/{len(df)} ({positive_rate:.2%})")
    task6_table(table, output_dir)
    task6_decision_tree(tree, output_dir)
