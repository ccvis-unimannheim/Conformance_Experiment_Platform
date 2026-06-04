"""
tasks/task4.py – Task 4: Root-cause indicators for non-conformance.

Public API:
    generate(log, alignments, output_dir)

Note: task6.py imports task4_trace_feature_dataframe, _task4_build_tree,
      _task4_gini from this module.
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["tile_metric", "table", "decision_tree"]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib import gridspec
from scipy import stats

from shared import (
    save_svg, make_table, draw_decision_tree, alignment_pairs_to_rows,
    format_threshold, wrap_text, BLUE, ORANGE, GREEN, RED, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Alias so that existing internal references still work
_task4_format_threshold = format_threshold


# ---------------------------------------------------------------------------
# Task 4 – Root-cause indicators for non-conformance
# ---------------------------------------------------------------------------

# Task 4 feature engineering helpers
TASK4_LABELS = {
    "num_events": "trace:number of events",
    "unique_activities": "trace:unique activities",
    "repeated_activities": "trace:repeated activities",
    "duration_hours": "time:duration hours",
    "resource_count": "resource:unique resources",
}


def _task4_key(prefix: str, value) -> str:
    raw = str(value)
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    return f"{prefix}_{cleaned}"[:90]


def _task4_value_to_float(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _task4_feature_label(feature: str) -> str:
    if feature in TASK4_LABELS:
        return TASK4_LABELS[feature]
    if feature.startswith("has_activity_"):
        return "activity:" + feature.replace("has_activity_", "") + " present"
    if feature.startswith("mean_"):
        return "data:mean " + feature.replace("mean_", "")
    if feature.startswith("max_"):
        return "data:max " + feature.replace("max_", "")
    return feature.replace("_", " ")


def task4_trace_feature_dataframe(log, alignments):
    """Build trace-level root-cause features from event attributes and alignment outcomes."""
    activity_counter = {}
    numeric_keys = {}
    trace_payloads = []

    for trace_idx, trace in enumerate(log):
        events = [{k: v for k, v in event.items()} for event in trace]
        activities = [str(event.get("concept:name", "")) for event in events if event.get("concept:name") is not None]
        for activity in activities:
            activity_counter[activity] = activity_counter.get(activity, 0) + 1

        timestamps = []
        resources = set()
        numeric_values = {}
        for event in events:
            ts = event.get("time:timestamp")
            if ts is not None and not pd.isna(ts):
                timestamps.append(pd.Timestamp(ts))
            resource = event.get("org:resource")
            if resource is not None and not pd.isna(resource):
                resources.add(str(resource))
            for key, value in event.items():
                if (
                    key in {"concept:name", "time:timestamp", "lifecycle:transition", "case:concept:name", "org:resource"}
                    or key.startswith("@@")
                    or key.lower().startswith("unnamed")
                ):
                    continue
                val = _task4_value_to_float(value)
                if val is None:
                    continue
                numeric_values.setdefault(key, []).append(val)
                numeric_keys[key] = numeric_keys.get(key, 0) + 1

        duration_hours = 0.0
        if len(timestamps) >= 2:
            duration_hours = (max(timestamps) - min(timestamps)).total_seconds() / 3600.0

        alignment_rows = alignment_pairs_to_rows(alignments[trace_idx].get("alignment", []))
        violation_count = sum(1 for row in alignment_rows if row["moveType"] != "Synchronous Move")
        model_moves = sum(1 for row in alignment_rows if row["moveType"] == "Model Move")
        log_moves = sum(1 for row in alignment_rows if row["moveType"] == "Log Move")

        trace_payloads.append({
            "trace_index": trace_idx,
            "fitness": float(alignments[trace_idx].get("fitness", 0.0)),
            "is_nonconformant": bool(alignments[trace_idx].get("fitness", 0.0) < 1.0),
            "num_events": len(events),
            "unique_activities": len(set(activities)),
            "repeated_activities": max(0, len(activities) - len(set(activities))),
            "duration_hours": duration_hours,
            "resource_count": len(resources),
            "violation_count": violation_count,
            "model_moves": model_moves,
            "log_moves": log_moves,
            "_activities": set(activities),
            "_numeric_values": numeric_values,
        })

    top_activities = [
        name for name, _ in sorted(activity_counter.items(), key=lambda item: item[1], reverse=True)[:14]
    ]
    top_numeric_keys = [
        key for key, _ in sorted(numeric_keys.items(), key=lambda item: item[1], reverse=True)[:6]
    ]

    rows = []
    for payload in trace_payloads:
        row = {k: v for k, v in payload.items() if not k.startswith("_")}
        for activity in top_activities:
            row[_task4_key("has_activity", activity)] = 1.0 if activity in payload["_activities"] else 0.0
        for key in top_numeric_keys:
            values = payload["_numeric_values"].get(key, [])
            if values:
                row[_task4_key("mean", key)] = float(np.mean(values))
                row[_task4_key("max", key)] = float(np.max(values))
            else:
                row[_task4_key("mean", key)] = np.nan
                row[_task4_key("max", key)] = np.nan
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.fillna(df.median(numeric_only=True)).fillna(0)
    return df


# Task 4 tree (model) helpers
def _task4_gini(y: np.ndarray) -> float:
    if len(y) == 0:
        return 0.0
    p = float(np.mean(y))
    return 1.0 - p ** 2 - (1.0 - p) ** 2


def _task4_thresholds(values: np.ndarray):
    unique = np.unique(values.astype(float))
    if len(unique) <= 1:
        return []
    if len(unique) == 2 and set(unique).issubset({0.0, 1.0}):
        return [0.5]
    if len(unique) > 12:
        return sorted(set(float(x) for x in np.quantile(unique, [0.2, 0.35, 0.5, 0.65, 0.8])))
    return [float((a + b) / 2.0) for a, b in zip(unique[:-1], unique[1:])]


def _task4_best_split(X: pd.DataFrame, y: np.ndarray, features, min_leaf: int):
    parent = _task4_gini(y)
    best = None
    for feature in features:
        values = X[feature].to_numpy(dtype=float)
        for threshold in _task4_thresholds(values):
            left = values <= threshold
            right = ~left
            if left.sum() < min_leaf or right.sum() < min_leaf:
                continue
            weighted = (left.sum() * _task4_gini(y[left]) + right.sum() * _task4_gini(y[right])) / len(y)
            gain = parent - weighted
            if best is None or gain > best["gain"]:
                best = {"feature": feature, "threshold": threshold, "gain": gain, "left": left, "right": right}
    return best


def _task4_build_tree(X: pd.DataFrame, y: np.ndarray, features, depth=0, max_depth=3, min_leaf=12, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    violations = int(y.sum())
    node = {
        "id": counter[0],
        "depth": depth,
        "gini": _task4_gini(y),
        "samples": int(len(y)),
        "value": [int(len(y) - violations), violations],
        "class": "non-conformant" if violations >= (len(y) - violations) else "conformant",
        "feature": None,
        "threshold": None,
        "gain": 0.0,
        "left": None,
        "right": None,
    }
    if depth >= max_depth or len(np.unique(y)) <= 1 or len(y) < min_leaf * 2:
        return node
    split = _task4_best_split(X, y, features, min_leaf)
    if split is None or split["gain"] <= 1e-9:
        return node
    node["feature"] = split["feature"]
    node["threshold"] = split["threshold"]
    node["gain"] = split["gain"]
    node["left"] = _task4_build_tree(X.loc[split["left"]], y[split["left"]], features, depth + 1, max_depth, min_leaf, counter)
    node["right"] = _task4_build_tree(X.loc[split["right"]], y[split["right"]], features, depth + 1, max_depth, min_leaf, counter)
    return node


def _task4_format_threshold(threshold: float) -> str:
    if abs(threshold - round(threshold)) < 1e-6:
        return str(int(round(threshold)))
    return f"{threshold:.2f}".rstrip("0").rstrip(".")


def _task4_condition_text(feature: str, threshold: float, side: str) -> str:
    label = _task4_feature_label(feature)
    if abs(threshold - 0.5) < 1e-9 and feature.startswith("has_activity_"):
        return label if side == "right" else label.replace(" present", " absent")
    op = "<=" if side == "left" else ">"
    return f"{label} {op} {_task4_format_threshold(threshold)}"


def _task4_collect_leaves(node: dict, path=None):
    path = [] if path is None else path
    if node.get("left") is None and node.get("right") is None:
        return [{"node": node, "path": path}]
    rows = []
    if node.get("left") is not None:
        rows.extend(_task4_collect_leaves(
            node["left"],
            path + [_task4_condition_text(node["feature"], node["threshold"], "left")],
        ))
    if node.get("right") is not None:
        rows.extend(_task4_collect_leaves(
            node["right"],
            path + [_task4_condition_text(node["feature"], node["threshold"], "right")],
        ))
    return rows


def task4_root_cause_analysis(log, alignments):
    """Create feature matrix, fit a small Gini tree, and summarize high-risk leaves."""
    df = task4_trace_feature_dataframe(log, alignments)
    if df.empty:
        return df, None, pd.DataFrame()

    target = df["is_nonconformant"].astype(int).to_numpy()
    excluded = {"trace_index", "fitness", "is_nonconformant", "violation_count", "model_moves", "log_moves"}
    features = [
        col for col in df.columns
        if col not in excluded and pd.api.types.is_numeric_dtype(df[col]) and df[col].nunique(dropna=True) > 1
    ]
    if not features or len(np.unique(target)) < 2:
        return df, None, pd.DataFrame()

    X = df[features].astype(float)
    min_leaf = max(6, int(len(df) * 0.015))
    tree = _task4_build_tree(X, target, features, max_depth=3, min_leaf=min_leaf)
    base_rate = float(target.mean())
    total_violations = max(int(target.sum()), 1)
    leaves = []
    for item in _task4_collect_leaves(tree):
        node = item["node"]
        fit_count, violation_count = node["value"]
        samples = node["samples"]
        rate = violation_count / samples if samples else 0.0
        leaves.append({
            "root_cause": " AND ".join(item["path"]) if item["path"] else "All traces",
            "cases": samples,
            "nonconformant_cases": violation_count,
            "violation_rate": rate,
            "lift": rate / base_rate if base_rate else 0.0,
            "coverage": violation_count / total_violations,
            "score": (rate / base_rate if base_rate else 0.0) * (violation_count / total_violations),
        })
    root_causes = pd.DataFrame(leaves)
    if not root_causes.empty:
        root_causes = root_causes.sort_values(
            ["score", "violation_rate", "nonconformant_cases"],
            ascending=False,
        ).reset_index(drop=True)
    logger.info(f"      -> Task 4 features: {len(features)} predictors, base non-conformance rate: {base_rate:.2%}")
    return df, tree, root_causes


# Task 4 visualizations
def _task4_tile_feature_label(feature: str) -> str:
    """Short label used in Task 4 insight tiles."""
    if feature == "num_events":
        return "Trace Length"
    if feature == "duration_hours":
        return "Case Duration"
    if feature == "resource_count":
        return "Resource Count"
    if "case_AMOUNT_REQ" in feature:
        return "Requested Amount"
    return _task4_feature_label(feature).replace("trace:", "").replace("time:", "").replace("data:", "")


def _task4_tile_condition(feature: str, threshold: float, risk_side: str) -> str:
    """Human-readable high-risk threshold condition."""
    label = _task4_tile_feature_label(feature)
    if abs(threshold - 0.5) < 1e-9 and feature.startswith("has_activity_"):
        return label if risk_side == "above" else label.replace(" present", " absent")
    op = ">" if risk_side == "above" else "<="
    return f"{label} {op} {_task4_format_threshold(threshold)}"


def _task4_tile_candidate_features(df_features: pd.DataFrame):
    """Numeric attributes eligible for one-variable tile insights."""
    excluded = {"trace_index", "fitness", "is_nonconformant", "violation_count", "model_moves", "log_moves"}
    candidates = []
    for feature in df_features.columns:
        if feature in excluded or feature.startswith("has_activity_"):
            continue
        if pd.api.types.is_numeric_dtype(df_features[feature]) and df_features[feature].nunique(dropna=True) > 1:
            candidates.append(feature)
    return candidates


def task4_attribute_tile_metrics(df_features: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Find top single-attribute thresholds for Task 4 tile metrics."""
    if df_features.empty or df_features["is_nonconformant"].nunique() < 2:
        return pd.DataFrame()

    y = df_features["is_nonconformant"].astype(int).to_numpy()
    total_violations = max(int(y.sum()), 1)
    min_leaf = max(6, int(len(df_features) * 0.015))
    tiles = []

    for feature in _task4_tile_candidate_features(df_features):
        values = df_features[feature].astype(float).to_numpy()
        best = None
        for threshold in _task4_thresholds(values):
            below = values <= threshold
            above = ~below
            if below.sum() < min_leaf or above.sum() < min_leaf:
                continue

            below_violations = int(y[below].sum())
            above_violations = int(y[above].sum())
            below_rate = below_violations / int(below.sum())
            above_rate = above_violations / int(above.sum())
            risk_side = "above" if above_rate >= below_rate else "below"
            risk_rate = above_rate if risk_side == "above" else below_rate
            other_rate = below_rate if risk_side == "above" else above_rate
            risk_violations = above_violations if risk_side == "above" else below_violations
            coverage = risk_violations / total_violations
            if other_rate > 0:
                likelihood_ratio = risk_rate / other_rate
                ratio_for_score = likelihood_ratio
            else:
                likelihood_ratio = np.inf if risk_rate > 0 else 1.0
                ratio_for_score = max(risk_rate * 100.0, 1.0)
            score = coverage * abs(risk_rate - other_rate) * max(ratio_for_score, 1.0)

            candidate = {
                "feature": feature,
                "label": _task4_tile_feature_label(feature),
                "threshold": threshold,
                "condition": _task4_tile_condition(feature, threshold, risk_side),
                "risk_side": risk_side,
                "coverage": coverage,
                "above_rate": above_rate,
                "below_rate": below_rate,
                "likelihood_ratio": likelihood_ratio,
                "score": score,
            }
            if best is None or candidate["score"] > best["score"]:
                best = candidate
        if best is not None:
            tiles.append(best)

    if not tiles:
        return pd.DataFrame()
    sorted_tiles = (
        pd.DataFrame(tiles)
        .sort_values(["score", "coverage", "likelihood_ratio"], ascending=False)
        .reset_index(drop=True)
    )
    deduped = []
    seen_signatures = set()
    for _, row in sorted_tiles.iterrows():
        signature = (
            round(float(row["coverage"]), 6),
            round(float(row["above_rate"]), 6),
            round(float(row["below_rate"]), 6),
            round(float(row["likelihood_ratio"]), 6) if not np.isinf(row["likelihood_ratio"]) else "inf",
        )
        if signature in seen_signatures:
            continue
        seen_signatures.add(signature)
        deduped.append(row)
        if len(deduped) >= top_n:
            break
    return pd.DataFrame(deduped).reset_index(drop=True)


def _task4_format_ratio(value: float) -> str:
    """Format likelihood ratio for tile display."""
    if np.isinf(value):
        return "inf"
    return f"{value:.2f}x"


def task4_tile_metric(root_causes: pd.DataFrame, df_features: pd.DataFrame, output_dir: str):
    """Tile metric: top single-attribute thresholds for non-conformance."""
    tile_df = task4_attribute_tile_metrics(df_features, top_n=3)

    fig, ax = plt.subplots(figsize=(12.2, 3.7))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Key Non-Conformance Indicators", fontsize=FONT_TITLE, loc="left", pad=12)

    if tile_df.empty:
        ax.text(0.05, 0.55, "No discriminating attribute threshold found.", fontsize=FONT_ANNOT, color="#333333")
        fig.tight_layout()
        save_svg(fig, os.path.join(output_dir, "task4_tile_metric.svg"))
        return

    tile_w = 0.29
    gap = 0.035
    y0 = 0.16
    tile_h = 0.66
    for i, (_, row) in enumerate(tile_df.iterrows()):
        x0 = 0.04 + i * (tile_w + gap)
        ax.add_patch(mpatches.FancyBboxPatch(
            (x0, y0), tile_w, tile_h,
            boxstyle="round,pad=0.014",
            linewidth=1.2,
            edgecolor="#AAAAAA",
            facecolor="#F8F8F8",
            transform=ax.transAxes,
            clip_on=False,
        ))
        ax.text(x0 + 0.025, y0 + tile_h - 0.095, row["label"], transform=ax.transAxes,
                fontsize=FONT_TITLE, color="#333333")
        ax.text(x0 + 0.025, y0 + tile_h - 0.205, row["condition"], transform=ax.transAxes,
                fontsize=FONT_LABEL, color="#333333")
        ax.text(x0 + 0.025, y0 + tile_h - 0.330,
                f"Violations captured: {row['coverage']:.1%}", transform=ax.transAxes,
                fontsize=FONT_ANNOT, color="#555555")
        ax.text(x0 + 0.025, y0 + tile_h - 0.435,
                f"Above vs below: {row['above_rate']:.1%} vs {row['below_rate']:.1%}", transform=ax.transAxes,
                fontsize=FONT_ANNOT, color="#555555")
        ax.text(x0 + 0.025, y0 + tile_h - 0.540,
                f"Likelihood ratio: {_task4_format_ratio(row['likelihood_ratio'])}", transform=ax.transAxes,
                fontsize=FONT_ANNOT, color="#333333")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task4_tile_metric.svg"))


def _task4_attribute_type(feature: str) -> str:
    """Classify a trace-level feature for the Task 4 attribute table."""
    if feature.startswith("has_activity_"):
        return "Activity flag"
    if "case_AMOUNT_REQ" in feature:
        return "Requested amount"
    if feature == "duration_hours":
        return "Case duration"
    if feature == "resource_count":
        return "Resources"
    if feature in {"num_events", "unique_activities", "repeated_activities"}:
        return "Trace length"
    if feature.startswith("mean_") or feature.startswith("max_"):
        return "Data attribute"
    return "Attribute"


def _task4_table_label(feature: str) -> str:
    """Readable attribute label for the Task 4 table."""
    label = _task4_tile_feature_label(feature)
    label = label.replace("has activity ", "").replace(" present", "")
    return label


def _task4_table_candidate_features(df_features: pd.DataFrame):
    """Attributes eligible for correlation-strength summary rows."""
    excluded = {"trace_index", "fitness", "is_nonconformant", "violation_count", "model_moves", "log_moves"}
    return [
        feature for feature in df_features.columns
        if feature not in excluded
        and pd.api.types.is_numeric_dtype(df_features[feature])
        and df_features[feature].nunique(dropna=True) > 1
    ]


def _task4_format_p_value(value: float) -> str:
    """Format p-values compactly for the attribute table."""
    if pd.isna(value):
        return "-"
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def task4_attribute_correlation_dataframe(df_features: pd.DataFrame) -> pd.DataFrame:
    """Build one row per attribute, sorted by correlation strength."""
    if df_features.empty or df_features["is_nonconformant"].nunique() < 2:
        return pd.DataFrame()

    y = df_features["is_nonconformant"].astype(int).to_numpy()
    rows = []
    for feature in _task4_table_candidate_features(df_features):
        values = df_features[feature].astype(float).to_numpy()
        conform_values = values[y == 0]
        nonconform_values = values[y == 1]
        if len(conform_values) == 0 or len(nonconform_values) == 0 or np.std(values) <= 1e-12:
            continue
        corr, p_value = stats.pearsonr(values, y)
        conform_avg = float(np.mean(conform_values))
        nonconform_avg = float(np.mean(nonconform_values))
        rows.append({
            "attribute": _task4_table_label(feature),
            "type": _task4_attribute_type(feature),
            "conform_avg": conform_avg,
            "nonconform_avg": nonconform_avg,
            "difference": nonconform_avg - conform_avg,
            "correlation": float(corr),
            "p_value": float(p_value),
            "strength": abs(float(corr)),
        })

    if not rows:
        return pd.DataFrame()
    return (
        pd.DataFrame(rows)
        .sort_values(["strength", "correlation"], ascending=[False, False])
        .reset_index(drop=True)
    )


def task4_table(df_features: pd.DataFrame, output_dir: str):
    """Table: attribute averages and correlation with non-conformance."""
    summary = task4_attribute_correlation_dataframe(df_features)
    cols = ["Attribute", "Type", "Conform avg", "Non-conform avg", "Difference", "Correlation", "p-value"]
    if summary.empty:
        cell_text = [["No discriminating attribute found", "-", "-", "-", "-", "-", "-"]]
    else:
        cell_text = []
        for _, row in summary.iterrows():
            cell_text.append([
                wrap_text(row["attribute"], 24, break_long_words=False),
                row["type"],
                f"{row['conform_avg']:.2f}",
                f"{row['nonconform_avg']:.2f}",
                f"{row['difference']:+.2f}",
                f"{row['correlation']:+.3f}",
                _task4_format_p_value(row["p_value"]),
            ])

    fig_h = max(4.0, 1.35 + len(cell_text) * 0.43)
    fig, ax = plt.subplots(figsize=(12.8, fig_h))
    ax.axis("off")
    table = ax.table(
        cellText=cell_text,
        colLabels=cols,
        cellLoc="center",
        bbox=[0.025, 0.04, 0.95, 0.84],
        colWidths=[0.25, 0.15, 0.13, 0.15, 0.12, 0.11, 0.09],
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8.2)
    for (r_idx, c_idx), cell in table.get_celld().items():
        cell.set_edgecolor("#FFFFFF")
        cell.set_linewidth(1.0)
        if r_idx == 0:
            cell.set_facecolor("#555555")
            cell.set_text_props(color="white")
            continue
        if summary.empty:
            cell.set_facecolor("#F0F0F0")
            continue
        corr = float(summary.iloc[r_idx - 1]["correlation"])
        cell.set_facecolor("#E8E8E8" if corr >= 0 else "#F2F2F2")
        cell.set_text_props(color="#222222")

    ax.set_title("Attribute Correlation Summary", fontsize=FONT_TITLE, pad=12)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task4_table.svg"))


# Task 4 visualization layout helpers
def _task4_assign_tree_positions(tree: dict):
    leaves = []
    max_depth = 0

    def collect(node):
        nonlocal max_depth
        max_depth = max(max_depth, node["depth"])
        if node.get("left") is None and node.get("right") is None:
            leaves.append(node)
            return
        collect(node["left"])
        collect(node["right"])

    collect(tree)
    x_gap = 3.15
    y_gap = 1.85
    leaf_positions = {node["id"]: idx * x_gap for idx, node in enumerate(leaves)}

    def assign(node):
        if node["id"] in leaf_positions:
            node["_x"] = leaf_positions[node["id"]]
        else:
            assign(node["left"])
            assign(node["right"])
            node["_x"] = (node["left"]["_x"] + node["right"]["_x"]) / 2.0
        node["_y"] = (max_depth - node["depth"]) * y_gap

    assign(tree)
    tree["_leaf_count"] = len(leaves)
    tree["_max_depth"] = max_depth
    tree["_x_gap"] = x_gap
    tree["_y_gap"] = y_gap


def _task4_plain_feature_name(feature: str) -> str:
    """Plain-English feature name for Task 4 decision-tree nodes."""
    if feature == "num_events":
        return "trace length"
    if feature == "unique_activities":
        return "unique activities"
    if feature == "repeated_activities":
        return "repeated activities"
    if feature == "duration_hours":
        return "duration"
    if feature == "resource_count":
        return "resources"
    if "case_AMOUNT_REQ" in feature:
        return "requested amount"
    if feature.startswith("has_activity_"):
        return feature.replace("has_activity_", "")
    return _task4_feature_label(feature).replace("trace:", "").replace("time:", "").replace("data:", "")


def _task4_split_question(feature: str, threshold: float) -> str:
    """Compact split label whose True branch goes left."""
    if abs(threshold - 0.5) < 1e-9 and feature.startswith("has_activity_"):
        activity = _task4_plain_feature_name(feature)
        return f"{activity} absent"
    label = _task4_plain_feature_name(feature)
    threshold_text = _task4_format_threshold(threshold)
    return f"{label} <= {threshold_text}"


def _task4_tree_feature_importance(tree: dict) -> pd.DataFrame:
    """Summarize split gain by feature for the feature-importance chart."""
    rows = {}

    def collect(node):
        feature = node.get("feature")
        if feature:
            gain = float(node.get("gain", 0.0))
            rows[feature] = rows.get(feature, 0.0) + gain
        if node.get("left") is not None:
            collect(node["left"])
        if node.get("right") is not None:
            collect(node["right"])

    if tree is not None:
        collect(tree)
    if not rows:
        return pd.DataFrame(columns=["feature", "label", "importance"])
    df = pd.DataFrame([
        {"feature": feature, "label": _task4_table_label(feature), "importance": gain}
        for feature, gain in rows.items()
    ])
    total = df["importance"].sum()
    if total > 0:
        df["importance"] = df["importance"] / total
    return df.sort_values("importance", ascending=True).reset_index(drop=True)


def _task4_draw_feature_importance(ax, tree: dict):
    """Draw a compact feature-importance bar chart for tree splits."""
    importance = _task4_tree_feature_importance(tree)
    ax.set_title("Feature Importance", fontsize=FONT_TITLE, loc="left", pad=10)
    if importance.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, "No split features", ha="center", va="center", fontsize=10)
        return
    colors = [BLUE if val < 0.34 else ORANGE for val in importance["importance"]]
    ax.barh(importance["label"], importance["importance"], color=colors, alpha=0.88)
    ax.set_xlabel("Normalized split gain", fontsize=FONT_ANNOT)
    ax.set_xlim(0, max(importance["importance"].max() * 1.18, 0.05))
    ax.tick_params(axis="y", labelsize=FONT_ANNOT)
    ax.tick_params(axis="x", labelsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    for y, val in enumerate(importance["importance"]):
        ax.text(val + max(importance["importance"].max(), 0.01) * 0.02, y, f"{val:.2f}", va="center", fontsize=FONT_ANNOT)


def task4_decision_tree(tree: dict, output_dir: str):
    """Decision tree: shallow Gini tree fitted on trace/event attributes."""
    fig = plt.figure(figsize=(19.2, 8.0))
    gs = gridspec.GridSpec(1, 2, width_ratios=[3.7, 1.0], wspace=0.16)
    ax_tree = fig.add_subplot(gs[0])
    ax_importance = fig.add_subplot(gs[1])
    draw_decision_tree(
        ax_tree,
        tree,
        title="Root Cause Analysis",
        title_fontsize=FONT_TITLE,
        title_pad=8,
        box_w=2.55,
        base_font=7.0,
        min_font=5.6,
        line_height=0.17,
        box_padding_h=0.18,
        wrap_width_fn=lambda _text: 24,
        first_line_fn=lambda node: (
            "leaf"
            if node.get("feature") is None
            else _task4_split_question(node["feature"], node["threshold"])
        ),
        value_pair_fn=lambda node: (node["value"][0], node["value"][1]),
        node_facecolor_fn=lambda node: (
            "#888888"
            if node["value"][1] > node["value"][0]
            else "#E0E0E0"
        ),
        legend_items=[
            mpatches.Patch(facecolor="#E0E0E0", edgecolor="#555555", label="Mostly conformant"),
            mpatches.Patch(facecolor="#888888", edgecolor="#555555", label="Mostly non-conformant"),
        ],
        legend_kwargs=dict(loc="lower center", bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False, fontsize=FONT_ANNOT),
        edge_arrowprops=dict(arrowstyle="-|>", color="#555555", linewidth=1.35, shrinkA=5, shrinkB=5),
        edge_label_fontsize=FONT_ANNOT,
        edge_label_offset_y=0.02,
        edge_label_clearance=0.16,
        edge_label_perp_offset=0.23,
        x_pad_factor=0.62,
        y_pad_base=0.90,
        y_top_pad=1.00,
        x_gap=2.85,
        y_gap=2.05,
    )
    _task4_draw_feature_importance(ax_importance, tree)
    fig.tight_layout(rect=[0, 0.03, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task4_decision_tree.svg"))


# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str):
    """Generate all Task 4 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 4 visualizations ---")
    df, tree, root_causes = task4_root_cause_analysis(log, alignments)
    if df.empty:
        logger.warning("      Skipped Task 4: no trace-level features found.")
        return
    task4_tile_metric(root_causes, df, output_dir)
    task4_decision_tree(tree, output_dir)
    task4_table(df, output_dir)
