"""
tasks/task20.py – Task ID 20: Explain / Discover / Reasons for guideline violations
(the Decision-Tree member of the Reasons triad).

Validated idiom mapping (9 idioms = 6 High + 3 Medium):
    HIGH:   bar_chart, table, table_bar_chart, flow_chart_table,
            flow_chart_elaborate_table, parallel_sets
    MEDIUM: flow_chart_elaborate, network_diagram, decision_tree

task20 is the tree companion to task13 (attribute evidence) and task18 (event
responsibility). The bar/table/table-bar/parallel/flow idioms are the SAME
attribute-evidence idioms as task13 — rendered here via task13's helpers (reuse, not
re-implement) — plus a co-occurrence network of violation patterns, the elaborate
model, and the existing Decision Tree (kept exactly as-is).

Public API:
    generate(log, alignments, output_dir, model_path=None)

Note: task31.py imports task20_trace_feature_dataframe, _task20_build_tree,
      _task20_gini from this module.
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "matrix", "table_bar_chart", "flow_chart_table",
          "flow_chart_elaborate_table", "parallel_sets",
          "flow_chart_elaborate", "network_diagram", "tree"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8; design doc §2 row 20)
#
# Task 20 (MANUAL): "Discover reasons / root causes" — which control-flow, data,
# resource, or time attributes lead to guideline violations. Like its sibling
# task13 (the attribute-evidence companion), the answer is irreducibly
# interpretive: the decision tree / attribute-evidence idioms surface candidate
# root causes, but naming THE reason is an analyst judgement, so no decisive GT
# value is auto-computed. Plan §6 classifies #20 under MANUAL; the admin provides
# a reference answer seeded from the static RUBRIC below.
#
# Mirrors task13's contract deliberately (same Reasons family): PARAM_SPEC = []
# (candidate attributes stay the shared hard-coded CANDIDATE_ATTRIBUTES set used
# by every idiom, guaranteeing GT-vs-visual consistency), free-text answer format.
# ---------------------------------------------------------------------------
GT_TIER = "MANUAL"

PARAM_SPEC = [
    {
        "key": "attribute_set",
        "label": "Attribute set to include in root-cause analysis (select relevant case / event attributes)",
        # Internal to reading the chart — the participant sees the analysed attributes directly.
        "hide_hint": True,
        "widget": "attribute-picker",
        "source": "log.case_attributes",
        "default": "",
        "required": False,
    },
]

ANSWER_FORMATS = [
    {"key": "free-text", "gt_shape": "reference", "decisive_default": False},
    {"key": "mc-multi",  "gt_shape": "mc",         "decisive_default": True},
]

RUBRIC = (
    "A strong answer identifies one or more concrete attributes — of the "
    "control-flow (e.g. trace length, a present/absent activity), data (e.g. a "
    "case-level value such as requested amount), resource, or time (e.g. case "
    "duration) — that distinguish violating from conforming cases, and states the "
    "direction of each effect (e.g. longer cases, or amounts above a threshold, "
    "exhibit more violations). The answer should read the evidence as a root cause "
    "(the attribute condition under which violations concentrate) rather than "
    "merely restating frequencies. Partial credit for correctly naming a "
    "discriminating attribute without giving its direction or threshold. No credit "
    "for vague claims unsupported by the visualized decision-tree / attribute "
    "evidence."
)


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """For mc-multi: candidate attributes ranked by correlation with violations as
    selectable options. The admin flags which attributes are the correct root-cause factors.
    For free-text: returns empty dict — the static RUBRIC is used as the reference.
    """
    if answer_format == "free-text":
        return {}

    feat = task20_trace_feature_dataframe(log, alignments)
    if feat.empty:
        return {"options": []}

    corr_df = task20_attribute_correlation_dataframe(feat)
    if corr_df.empty:
        return {"options": []}

    # Options are still the 8 most-correlated candidate attributes, but the label
    # shows only the attribute name and its (neutral) type — the correlation value
    # is withheld so the option text doesn't rank the answers for the participant,
    # who must read the strength of association off the visualization.
    return {
        "options": [
            {
                "label": f"{row['attribute']} ({row['type']})",
                "value": row["attribute"],
                "correct": False,
            }
            for _, row in corr_df.head(8).iterrows()
        ]
    }


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
    save_svg, make_table, auto_col_widths, draw_decision_tree, draw_value_heatmap,
    draw_parallel_sets, alignment_pairs_to_rows,
    render_empty_state_svg, parse_bpmn_model, render_bpmn_annotated,
    format_threshold, wrap_text, GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse the Reasons-triad siblings: task13 (attribute-evidence idioms) and task18
# (event responsibility, for the standalone elaborate model). These are imported
# LAZILY inside generate()/helpers — task13 imports task20 at module load, so a
# top-level import here would create a circular-import failure.

# Alias so that existing internal references still work
_task20_format_threshold = format_threshold


# ---------------------------------------------------------------------------
# Task 4 – Root-cause indicators for non-conformance
# ---------------------------------------------------------------------------

# Task 4 feature engineering helpers
TASK20_LABELS = {
    "num_events": "trace:number of events",
    "unique_activities": "trace:unique activities",
    "repeated_activities": "trace:repeated activities",
    "duration_hours": "time:duration hours",
    "resource_count": "resource:unique resources",
}


def _task20_key(prefix: str, value) -> str:
    raw = str(value)
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in raw).strip("_")
    return f"{prefix}_{cleaned}"[:90]


def _task20_value_to_float(value):
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


def _task20_feature_label(feature: str) -> str:
    if feature in TASK20_LABELS:
        return TASK20_LABELS[feature]
    if feature.startswith("has_activity_"):
        return "activity:" + feature.replace("has_activity_", "") + " present"
    if feature.startswith("mean_"):
        return "data:mean " + feature.replace("mean_", "")
    if feature.startswith("max_"):
        return "data:max " + feature.replace("max_", "")
    return feature.replace("_", " ")


def task20_trace_feature_dataframe(log, alignments):
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
                val = _task20_value_to_float(value)
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
            row[_task20_key("has_activity", activity)] = 1.0 if activity in payload["_activities"] else 0.0
        for key in top_numeric_keys:
            values = payload["_numeric_values"].get(key, [])
            if values:
                row[_task20_key("mean", key)] = float(np.mean(values))
                row[_task20_key("max", key)] = float(np.max(values))
            else:
                row[_task20_key("mean", key)] = np.nan
                row[_task20_key("max", key)] = np.nan
        rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.fillna(df.median(numeric_only=True)).fillna(0)
    return df


# Task 4 tree (model) helpers
def _task20_gini(y: np.ndarray) -> float:
    if len(y) == 0:
        return 0.0
    p = float(np.mean(y))
    return 1.0 - p ** 2 - (1.0 - p) ** 2


def _task20_thresholds(values: np.ndarray):
    unique = np.unique(values.astype(float))
    if len(unique) <= 1:
        return []
    if len(unique) == 2 and set(unique).issubset({0.0, 1.0}):
        return [0.5]
    if len(unique) > 12:
        return sorted(set(float(x) for x in np.quantile(unique, [0.2, 0.35, 0.5, 0.65, 0.8])))
    return [float((a + b) / 2.0) for a, b in zip(unique[:-1], unique[1:])]


def _task20_best_split(X: pd.DataFrame, y: np.ndarray, features, min_leaf: int):
    parent = _task20_gini(y)
    best = None
    for feature in features:
        values = X[feature].to_numpy(dtype=float)
        for threshold in _task20_thresholds(values):
            left = values <= threshold
            right = ~left
            if left.sum() < min_leaf or right.sum() < min_leaf:
                continue
            weighted = (left.sum() * _task20_gini(y[left]) + right.sum() * _task20_gini(y[right])) / len(y)
            gain = parent - weighted
            if best is None or gain > best["gain"]:
                best = {"feature": feature, "threshold": threshold, "gain": gain, "left": left, "right": right}
    return best


def _task20_build_tree(X: pd.DataFrame, y: np.ndarray, features, depth=0, max_depth=3, min_leaf=12, counter=None):
    if counter is None:
        counter = [0]
    counter[0] += 1
    violations = int(y.sum())
    node = {
        "id": counter[0],
        "depth": depth,
        "gini": _task20_gini(y),
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
    split = _task20_best_split(X, y, features, min_leaf)
    if split is None or split["gain"] <= 1e-9:
        return node
    node["feature"] = split["feature"]
    node["threshold"] = split["threshold"]
    node["gain"] = split["gain"]
    node["left"] = _task20_build_tree(X.loc[split["left"]], y[split["left"]], features, depth + 1, max_depth, min_leaf, counter)
    node["right"] = _task20_build_tree(X.loc[split["right"]], y[split["right"]], features, depth + 1, max_depth, min_leaf, counter)
    return node


def _task20_format_threshold(threshold: float) -> str:
    if abs(threshold - round(threshold)) < 1e-6:
        return str(int(round(threshold)))
    return f"{threshold:.2f}".rstrip("0").rstrip(".")


def _task20_condition_text(feature: str, threshold: float, side: str) -> str:
    label = _task20_feature_label(feature)
    if abs(threshold - 0.5) < 1e-9 and feature.startswith("has_activity_"):
        return label if side == "right" else label.replace(" present", " absent")
    op = "<=" if side == "left" else ">"
    return f"{label} {op} {_task20_format_threshold(threshold)}"


def _task20_collect_leaves(node: dict, path=None):
    path = [] if path is None else path
    if node.get("left") is None and node.get("right") is None:
        return [{"node": node, "path": path}]
    rows = []
    if node.get("left") is not None:
        rows.extend(_task20_collect_leaves(
            node["left"],
            path + [_task20_condition_text(node["feature"], node["threshold"], "left")],
        ))
    if node.get("right") is not None:
        rows.extend(_task20_collect_leaves(
            node["right"],
            path + [_task20_condition_text(node["feature"], node["threshold"], "right")],
        ))
    return rows


def task20_root_cause_analysis(log, alignments):
    """Create feature matrix, fit a small Gini tree, and summarize high-risk leaves."""
    df = task20_trace_feature_dataframe(log, alignments)
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
    tree = _task20_build_tree(X, target, features, max_depth=3, min_leaf=min_leaf)
    base_rate = float(target.mean())
    total_violations = max(int(target.sum()), 1)
    leaves = []
    for item in _task20_collect_leaves(tree):
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
    logger.info(f"      -> Feature set: {len(features)} predictors, base non-conformance rate: {base_rate:.2%}")
    return df, tree, root_causes


# Task 4 visualizations
def _task20_tile_feature_label(feature: str) -> str:
    """Short label used in Task 4 insight tiles."""
    if feature == "num_events":
        return "Trace Length"
    if feature == "duration_hours":
        return "Case Duration"
    if feature == "resource_count":
        return "Resource Count"
    if "case_AMOUNT_REQ" in feature:
        return "Requested Amount"
    return _task20_feature_label(feature).replace("trace:", "").replace("time:", "").replace("data:", "")


def _task20_tile_condition(feature: str, threshold: float, risk_side: str) -> str:
    """Human-readable high-risk threshold condition."""
    label = _task20_tile_feature_label(feature)
    if abs(threshold - 0.5) < 1e-9 and feature.startswith("has_activity_"):
        return label if risk_side == "above" else label.replace(" present", " absent")
    op = ">" if risk_side == "above" else "<="
    return f"{label} {op} {_task20_format_threshold(threshold)}"


def _task20_tile_candidate_features(df_features: pd.DataFrame):
    """Numeric attributes eligible for one-variable tile insights."""
    excluded = {"trace_index", "fitness", "is_nonconformant", "violation_count", "model_moves", "log_moves"}
    candidates = []
    for feature in df_features.columns:
        if feature in excluded or feature.startswith("has_activity_"):
            continue
        if pd.api.types.is_numeric_dtype(df_features[feature]) and df_features[feature].nunique(dropna=True) > 1:
            candidates.append(feature)
    return candidates


def task20_attribute_tile_metrics(df_features: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    """Find top single-attribute thresholds for Task 4 tile metrics."""
    if df_features.empty or df_features["is_nonconformant"].nunique() < 2:
        return pd.DataFrame()

    y = df_features["is_nonconformant"].astype(int).to_numpy()
    total_violations = max(int(y.sum()), 1)
    min_leaf = max(6, int(len(df_features) * 0.015))
    tiles = []

    for feature in _task20_tile_candidate_features(df_features):
        values = df_features[feature].astype(float).to_numpy()
        best = None
        for threshold in _task20_thresholds(values):
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
                "label": _task20_tile_feature_label(feature),
                "threshold": threshold,
                "condition": _task20_tile_condition(feature, threshold, risk_side),
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


def _task20_format_ratio(value: float) -> str:
    """Format likelihood ratio for tile display."""
    if np.isinf(value):
        return "inf"
    return f"{value:.2f}x"


def _task20_attribute_type(feature: str) -> str:
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


def _task20_table_label(feature: str) -> str:
    """Readable attribute label for the Task 4 table."""
    label = _task20_tile_feature_label(feature)
    label = label.replace("has activity ", "").replace(" present", "")
    return label


def _task20_table_candidate_features(df_features: pd.DataFrame):
    """Attributes eligible for correlation-strength summary rows."""
    excluded = {"trace_index", "fitness", "is_nonconformant", "violation_count", "model_moves", "log_moves"}
    return [
        feature for feature in df_features.columns
        if feature not in excluded
        and pd.api.types.is_numeric_dtype(df_features[feature])
        and df_features[feature].nunique(dropna=True) > 1
    ]


def _task20_format_p_value(value: float) -> str:
    """Format p-values compactly for the attribute table."""
    if pd.isna(value):
        return "-"
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


def task20_attribute_correlation_dataframe(df_features: pd.DataFrame) -> pd.DataFrame:
    """Build one row per attribute, sorted by correlation strength."""
    if df_features.empty or df_features["is_nonconformant"].nunique() < 2:
        return pd.DataFrame()

    y = df_features["is_nonconformant"].astype(int).to_numpy()
    rows = []
    for feature in _task20_table_candidate_features(df_features):
        values = df_features[feature].astype(float).to_numpy()
        conform_values = values[y == 0]
        nonconform_values = values[y == 1]
        if len(conform_values) == 0 or len(nonconform_values) == 0 or np.std(values) <= 1e-12:
            continue
        corr, p_value = stats.pearsonr(values, y)
        conform_avg = float(np.mean(conform_values))
        nonconform_avg = float(np.mean(nonconform_values))
        rows.append({
            "attribute": _task20_table_label(feature),
            "type": _task20_attribute_type(feature),
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


# Task 4 visualization layout helpers
def _task20_assign_tree_positions(tree: dict):
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


def _task20_plain_feature_name(feature: str) -> str:
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
    return _task20_feature_label(feature).replace("trace:", "").replace("time:", "").replace("data:", "")


def _task20_split_question(feature: str, threshold: float) -> str:
    """Compact split label whose True branch goes left."""
    if abs(threshold - 0.5) < 1e-9 and feature.startswith("has_activity_"):
        activity = _task20_plain_feature_name(feature)
        return f"{activity} absent"
    label = _task20_plain_feature_name(feature)
    threshold_text = _task20_format_threshold(threshold)
    return f"{label} <= {threshold_text}"


def _task20_tree_feature_importance(tree: dict) -> pd.DataFrame:
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
        {"feature": feature, "label": _task20_table_label(feature), "importance": gain}
        for feature, gain in rows.items()
    ])
    total = df["importance"].sum()
    if total > 0:
        df["importance"] = df["importance"] / total
    return df.sort_values("importance", ascending=True).reset_index(drop=True)


def _task20_draw_feature_importance(ax, tree: dict):
    """Draw a compact feature-importance bar chart for tree splits."""
    importance = _task20_tree_feature_importance(tree)
    ax.set_title("Feature Importance", fontsize=FONT_TITLE, loc="left", pad=10)
    if importance.empty:
        ax.axis("off")
        ax.text(0.5, 0.5, "No split features", ha="center", va="center", fontsize=10)
        return
    colors = [GREY_MED if val < 0.34 else GREY_LIGHT for val in importance["importance"]]
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


def task20_tree(tree: dict, output_dir: str):
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
            else _task20_split_question(node["feature"], node["threshold"])
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
    _task20_draw_feature_importance(ax_importance, tree)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task20_tree.svg"))


# ---------------------------------------------------------------------------
# Added valid idioms — attribute-evidence idioms reused verbatim from task13
# (same computation kernel + renderers), written under task20's stems.
# ---------------------------------------------------------------------------

def _reuse_task13(render_fn, output_dir, src_stem, dst_stem, *args):
    """Call a task13 renderer (writes task13_<src_stem>.svg) then rename it to the
    task20_<dst_stem>.svg stem so it lands under task20's output path/slug."""
    render_fn(*args)
    src = os.path.join(output_dir, f"task13_{src_stem}.svg")
    dst = os.path.join(output_dir, f"task20_{dst_stem}.svg")
    if os.path.exists(src):
        os.replace(src, dst)


# ---------------------------------------------------------------------------
# Network Diagram (Med) — co-occurrence network of violation patterns
# ---------------------------------------------------------------------------

def _violation_pattern_sets(alignments):
    """Per trace: set of (activity, move_type) violation patterns."""
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
            patterns.add(f"{activity} ({mt.split()[0]})")
        out.append(patterns)
    return out


def task20_network_diagram(alignments, output_dir: str, top_n: int = 12):
    """Med: co-occurrence network of violation patterns. Nodes = violation patterns
    (size = #traces exhibiting it), edges = co-occurrence in the same trace
    (width = count). Circular layout (no external graph library)."""
    path = os.path.join(output_dir, "task20_network_diagram.svg")
    pattern_sets = _violation_pattern_sets(alignments)
    freq = {}
    for s in pattern_sets:
        for p in s:
            freq[p] = freq.get(p, 0) + 1
    if not freq:
        render_empty_state_svg(path, "Violation Pattern Co-occurrence Network",
                               "No violation patterns found.")
        return

    nodes = [p for p, _ in sorted(freq.items(), key=lambda kv: kv[1], reverse=True)[:top_n]]
    node_set = set(nodes)
    co = {}
    for s in pattern_sets:
        present = [p for p in s if p in node_set]
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                key = tuple(sorted((present[i], present[j])))
                co[key] = co.get(key, 0) + 1

    n = len(nodes)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    pos = {p: (np.cos(a), np.sin(a)) for p, a in zip(nodes, angles)}
    max_freq = max(freq[p] for p in nodes)
    max_co = max(co.values()) if co else 1

    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_aspect("equal")
    ax.axis("off")
    # Edges first (so nodes sit on top)
    for (a, b), w in co.items():
        x0, y0 = pos[a]; x1, y1 = pos[b]
        ax.plot([x0, x1], [y0, y1], color="#999999",
                linewidth=0.6 + 4.0 * (w / max_co), alpha=0.45, zorder=1)
    # Nodes
    for p in nodes:
        x, y = pos[p]
        size = 200 + 1400 * (freq[p] / max_freq)
        ax.scatter([x], [y], s=size, color=GREY_MED, edgecolors="#333333",
                   linewidths=1.0, alpha=0.9, zorder=2)
        ha = "left" if x >= 0 else "right"
        ax.annotate(f"{p}\n({freq[p]})", (x, y), xytext=(x * 1.18, y * 1.18),
                    textcoords="data", ha=ha, va="center", fontsize=FONT_ANNOT - 1,
                    zorder=3)
    ax.set_xlim(-1.7, 1.7)
    ax.set_ylim(-1.45, 1.45)
    ax.set_title("Violation Pattern Co-occurrence Network\n(node size = #traces, edge width = co-occurrence)",
                 fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


# ---------------------------------------------------------------------------
# Info-equivalent attribute idioms (task20-native, decoupled from task13).
#
# All four render the SAME data — violation rate (%) per bucket for every
# candidate attribute — reusing task13's DATA helpers (_build_evidence_frame,
# _bucket_rates) but task20's own renderers, so no derived measures (correlation,
# direction), no sample sizes, and no colour-coding by direction leak in. The
# quartile / top-category buckets are exactly those of task13's bar/parallel.
# ---------------------------------------------------------------------------

# Uniform bar/matrix colour — no coding by violation direction.
_ATTR_BAR_COLOR = GREY_MED
_ATTR_SUPTITLE = "Guideline-Violation Rate by Candidate Attribute"

# Candidate attributes excluded from task20's info-equivalent idioms. org:resource
# is an identifier (not a magnitude): its buckets add no interpretable root-cause
# signal here, so the four idioms show only AMOUNT_REQ and Throughput time.
_EXCLUDE_ATTRIBUTES = {"org:resource"}


def _task20_attribute_panels(log, alignments):
    """[(meta, (bucket_labels, violation_rate_pct, trace_counts)), …] — one entry
    per bucketable candidate attribute; the shared data for all 4 info-equivalent
    idioms. Empty list when there is no attribute evidence / no violations."""
    import tasks.task13 as task13  # lazy: task13 imports task20 at module load
    feat = task20_trace_feature_dataframe(log, alignments)
    if feat.empty:
        return []
    candidates = [a for a in task13.CANDIDATE_ATTRIBUTES if a not in _EXCLUDE_ATTRIBUTES]
    evidence_df, attr_meta = task13._build_evidence_frame(log, feat, candidates)
    if not attr_meta or int(evidence_df["violation"].sum()) == 0:
        return []
    violation = evidence_df["violation"].to_numpy()
    panels = []
    for m in attr_meta:
        res = task13._bucket_rates(evidence_df[m["col"]].tolist(), m["type"], violation)
        if res is not None:
            panels.append((m, res))
    return panels


def task20_bar_chart(panels, output_dir):
    """One sub-panel per attribute: violation rate (%) per bucket, uniform colour,
    fixed 0–100 scale, rate labelled above each bar (no sample sizes)."""
    path = os.path.join(output_dir, "task20_bar_chart.svg")
    if not panels:
        render_empty_state_svg(path, _ATTR_SUPTITLE, "No candidate attribute could be bucketed.")
        return
    ncols = len(panels)
    fig, axes = plt.subplots(1, ncols, figsize=(max(5.0, ncols * 4.2), 5.0), squeeze=False)
    for ax, (m, (labels, rates, _counts)) in zip(axes[0], panels):
        pos = np.arange(len(labels))
        ax.bar(pos, rates, color=_ATTR_BAR_COLOR, edgecolor="white")
        for p, rate in zip(pos, rates):
            ax.text(p, rate + 1.5, f"{rate:.1f}%", ha="center", va="bottom",
                    fontsize=FONT_ANNOT - 1, color="#333333")
        ax.set_xticks(pos)
        ax.set_xticklabels(labels, fontsize=FONT_ANNOT - 1, rotation=20, ha="right")
        ax.set_title(m["label"], fontsize=FONT_LABEL)
        ax.set_ylim(0, 100)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.45)
        ax.set_axisbelow(True)
    axes[0][0].set_ylabel("Violation rate (%)", fontsize=FONT_LABEL)
    fig.suptitle(_ATTR_SUPTITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task20_table(panels, output_dir):
    """One section per attribute (header = attribute name): Bucket | Violation Rate (%)."""
    path = os.path.join(output_dir, "task20_table.svg")
    if not panels:
        render_empty_state_svg(path, _ATTR_SUPTITLE, "No candidate attribute could be bucketed.")
        return
    col_labels = ["Bucket", "Violation Rate (%)"]
    height_ratios = [max(1, len(labels)) for (_m, (labels, _r, _c)) in panels]
    fig_h = max(4.0, 1.0 + sum(height_ratios) * 0.42 + len(panels) * 0.55)
    fig = plt.figure(figsize=(8, fig_h))
    gs = gridspec.GridSpec(len(panels), 1, height_ratios=height_ratios, hspace=0.7)
    for i, (m, (labels, rates, _counts)) in enumerate(panels):
        ax = fig.add_subplot(gs[i]); ax.axis("off")
        cell_text = [[lab, f"{rate:.1f}%"] for lab, rate in zip(labels, rates)]
        make_table(ax, cell_text=cell_text, col_labels=col_labels,
                   bbox=[0.04, 0.02, 0.92, 0.82],
                   col_widths=auto_col_widths(col_labels, cell_text),
                   font_size=10, cell_pad=0.09)
        ax.set_title(m["label"], fontsize=FONT_TITLE, pad=4, loc="left")
    fig.suptitle(_ATTR_SUPTITLE, fontsize=FONT_TITLE, y=0.99)
    save_svg(fig, path)


def task20_matrix(panels, output_dir):
    """One sub-matrix per attribute: rows = buckets, single Violation Rate (%)
    column on a fixed 0→100 colour scale, numeric annotation per cell."""
    path = os.path.join(output_dir, "task20_matrix.svg")
    if not panels:
        render_empty_state_svg(path, _ATTR_SUPTITLE, "No candidate attribute could be bucketed.")
        return
    ncols = len(panels)
    max_rows = max(len(labels) for (_m, (labels, _r, _c)) in panels)
    fig_h = max(3.0, 0.5 * max_rows + 1.8)
    fig, axes = plt.subplots(1, ncols, figsize=(max(5.0, ncols * 3.6), fig_h), squeeze=False)
    for ax, (m, (labels, rates, _counts)) in zip(axes[0], panels):
        data = np.asarray(rates, dtype=float).reshape(-1, 1)
        draw_value_heatmap(
            fig, ax, data, labels, ["Violation Rate (%)"],
            cbar_label="Violation Rate (%)", cell_fmt="{:.1f}%", annotate=True, vmax=100.0,
        )
        ax.set_title(m["label"], fontsize=FONT_LABEL)
    fig.suptitle(_ATTR_SUPTITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task20_parallel_sets(panels, output_dir):
    """One flow per attribute: bucket → Violation / No violation; ribbon = #traces.
    Percentage labels on the axis segments (per-bucket violation rate on the left,
    overall split on the right) bring it closer to the other idioms' density."""
    path = os.path.join(output_dir, "task20_parallel_sets.svg")
    if not panels:
        render_empty_state_svg(path, _ATTR_SUPTITLE, "No candidate attribute could be bucketed.")
        return
    ncols = len(panels)
    max_rows = max(len(labels) for (_m, (labels, _r, _c)) in panels)
    # Wide panels keep the two column axes far enough apart that their titles do
    # not collide once draw_parallel_sets reserves side-label room; tall panels give
    # small (imbalanced) category slivers enough vertical space to label cleanly.
    fig_h = max(7.5, max_rows * 0.75 + 3.5)
    fig, axes = plt.subplots(1, ncols, figsize=(max(7.0, ncols * 5.8), fig_h), squeeze=False)
    for ax, (m, (labels, rates, counts)) in zip(axes[0], panels):
        ax.axis("off")
        mat = np.zeros((len(labels), 2))
        for i, (rate, cnt) in enumerate(zip(rates, counts)):
            viol = round(rate / 100.0 * cnt)          # exact: rate = mean*100
            mat[i, 0] = viol
            mat[i, 1] = cnt - viol
        left_labels = [f"{lab}  ({rate:.1f}% viol.)" for lab, rate in zip(labels, rates)]
        total = float(mat.sum())
        overall = mat[:, 0].sum() / total * 100 if total else 0.0
        right_labels = [f"Violation ({overall:.1f}%)", f"No violation ({100 - overall:.1f}%)"]
        left_colors = [_GREY_PALETTE[i % len(_GREY_PALETTE)] for i in range(len(labels))]
        draw_parallel_sets(
            ax, left_labels, right_labels, mat, left_colors,
            right_colors=[GREY_DARK, GREY_LIGHTER],
            left_title=m["label"], right_title="Guideline",
            label_min_frac=0.0,  # label every present bucket (info equivalence)
        )
    fig.suptitle("Attribute Bucket vs. Guideline Violation (ribbon = # traces)",
                 fontsize=FONT_TITLE, y=0.99)
    fig.subplots_adjust(top=0.82)
    save_svg(fig, path)


# Grey palette for the left (bucket) axis of the parallel-sets idiom.
_GREY_PALETTE = [GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str, model_path=None):
    """Generate all Task ID 20 SVGs into output_dir.

    The Decision Tree (kept exactly as-is) plus the attribute-evidence idioms
    (reused from task13), the elaborate model (reused from task18), and a
    violation-pattern co-occurrence network. Legacy extras still rendered."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 20 visualizations ---")
    # Lazy imports to avoid the task13↔task20 circular import at module load.
    import tasks.task13 as task13
    from tasks.task28 import build_task28_context

    df, tree, root_causes = task20_root_cause_analysis(log, alignments)
    if df.empty:
        logger.warning("      Skipped Task 20: no trace-level features found.")
        return

    # Decision Tree — the module's original rendering, unchanged.
    task20_tree(tree, output_dir)
    # Network Diagram (new)
    task20_network_diagram(alignments, output_dir)

    # Attribute-evidence idioms. The four spec idioms (bar_chart, table, matrix,
    # parallel_sets) are task20-native and information-equivalent (violation rate
    # per bucket per attribute). The kept extras (table_bar_chart + the two flow
    # charts) still reuse task13's renderers unchanged.
    feat = task20_trace_feature_dataframe(log, alignments)
    evidence_df, attr_meta = task13._build_evidence_frame(log, feat, list(task13.CANDIDATE_ATTRIBUTES))
    if attr_meta and int(evidence_df["violation"].sum()) > 0:
        ranking = task13._rank_attributes(evidence_df, attr_meta)
        ctx = build_task28_context(alignments)

        panels = _task20_attribute_panels(log, alignments)
        task20_bar_chart(panels, output_dir)
        task20_table(panels, output_dir)
        task20_matrix(panels, output_dir)
        task20_parallel_sets(panels, output_dir)

        _reuse_task13(task13.task13_table_and_bar_chart, output_dir, "table_and_bar_chart", "table_and_bar_chart", ranking, output_dir)
        _reuse_task13(task13.task13_flow_chart_and_table, output_dir, "flow_chart_and_table", "flow_chart_and_table", ctx, ranking, output_dir)
        _reuse_task13(task13.task13_flow_chart_elaborate_bpmn_table, output_dir,
                      "flow_chart_elaborate_bpmn_table", "flow_chart_elaborate_bpmn_table",
                      ctx, ranking, model_path, output_dir)
    else:
        logger.warning("      task20: no attribute evidence / no violations — attribute idioms skipped.")

    # Flow Chart+ standalone — reuse task18's responsibility model annotation.
    _task20_flow_chart_elaborate(log, alignments, model_path, output_dir)


def _task20_flow_chart_elaborate(log, alignments, model_path, output_dir):
    """Flow Chart+ (Med standalone): the desired model with responsible activities
    highlighted by violation frequency (reuses task18's responsibility + node style)."""
    path = os.path.join(output_dir, "task20_flow_chart_elaborate_bpmn.svg")
    if not model_path:
        render_empty_state_svg(path, "Responsible Activities on the Model",
                               "No model available.")
        return
    import tasks.task18 as task18   # lazy (avoids circular import at module load)
    resp = task18.task18_responsibility(log, alignments)
    if not resp["records"]:
        render_empty_state_svg(path, "Responsible Activities on the Model",
                               "No guideline violations found.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task20: BPMN parse failed: {e}")
        render_empty_state_svg(path, "Responsible Activities on the Model",
                               "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, "Responsible Activities on the Model",
                               "No BPMN geometry to render.")
        return
    share_map = task18._activity_share_map(resp["records"])
    render_bpmn_annotated(
        parsed, path,
        title="Activities Responsible for Guideline Violations",
        summary="Darker = higher responsibility share (more violation moves on that activity).",
        node_style_fn=task18._responsibility_node_style(share_map),
        legend_items=[
            ("#414141", "#333333", 3, "High responsibility"),
            ("#c8c8c8", "#333333", 3, "Lower responsibility"),
            ("white",   "#888888", 2, "Not responsible"),
        ],
    )
