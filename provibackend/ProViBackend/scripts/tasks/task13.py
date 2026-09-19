"""
tasks/task13.py – Task ID 13: Explain / Reasons for guideline violations.

Goal **Explain** / Means *(undefined in the taxonomy)* / Characteristics
*Reasons for guideline violations*:
    "What are the underlying reasons for guideline violations?"

Realized deliberately as the **attribute-evidence companion** to Task ID 20
(`task20.py`, the decision tree for *Discover reasons*). Where task20 answers the
question with a single tree, task13 answers "which case/event attributes are
*associated* with guideline violations?" using the generic statistical idioms —
same underlying per-trace attribute data + violation label, different (non-tree)
presentations. It complements, it does not duplicate, task20.

Design (settled):
  * Candidate attributes (the "reasons") = the admin's selection, or by default
    every attribute the log actually carries that can be bucketed, plus the
    derived throughput time (discover_candidate_attributes). Nothing is keyed
    to a particular dataset's attribute names.
  * Target label = guideline violations per trace, REUSED from the already
    computed alignment data via task20's per-trace feature frame
    (`task20_trace_feature_dataframe`). No alignments are re-run, nothing is
    recomputed.
  * Association measure (one per candidate, interpretable, documented inline):
      - numeric attribute   → point-biserial correlation r between the attribute
                              value and the binary violation label. Strength
                              = |r| in [0, 1]; sign gives the direction.
      - categorical attribute → Cramér's V between the (top-k + "Other") category
                              and the binary violation label. Strength in [0, 1];
                              direction = the category with the highest violation
                              rate.
    Attributes are ranked by strength.

Scope = the 7 "High" idioms (Priority column of docs/TASK_IDIOM_MAPPING.md). Stems written here → canonical slug after the
pipeline rename (see create_all_visualizations._FILE_RENAME):
    task13_bar_chart.svg                      → bar_chart
    task13_table.svg                          → table
    task13_parallel_sets.svg                  → parallel_sets

    Commented out of IDIOMS/generate() for now:
    task13_scatter_plot.svg                   → scatterplot
    task13_table_and_bar_chart.svg            → table_bar_chart
    task13_flow_chart_and_table.svg           → flow_chart_table            (basic chevron + table)
    task13_flow_chart_elaborate_bpmn_table.svg→ flow_chart_elaborate_table  (annotated BPMN + table)

The two flow combos therefore carry DISTINCT canonical slugs:
`flow_chart_table` (basic) vs `flow_chart_elaborate_table` (elaborate).

Public API:
    generate(log, alignments, model_path, output_dir, candidate_attributes=None)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table", "parallel_sets",
          # "scatter_plot",
          # "table_bar_chart",
          ]

# What this task measures per group, and how it cuts the log — task
# properties rather than admin choices (see TRACE_FEATURE_REGISTRY.md).
RESPONSE_MEASURE = "violation_rate"
SPLIT_STRATEGY = None  # admin chooses

import trace_features

def validate_params(log, params) -> list:
    return trace_features.validate_attribute_class(params, multi=True)


PARAM_SPEC = [
    *trace_features.attribute_params(),
    *trace_features.split_params_for(),
]
          # "flow_chart_table", "flow_chart_elaborate_table"  # commented out


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
    save_svg, make_table, draw_parallel_sets, render_empty_state_svg, wrap_text,
    chevron_nodes_from_alignment_rows, draw_chevron_strip, chevron_figure_width,
    parse_bpmn_model, compose_bpmn_panels, alignment_violation_node_style, format_threshold,
    GREY_MED, GREY_LIGHT, GREY_LIGHTER, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Reuse: violation label + per-trace numeric features (incl. throughput time).
from tasks.task20 import task20_trace_feature_dataframe
# Reuse: attribute-existence verification + case-attribute reading.
from tasks.task30 import (
    _trace_attribute_value, _available_case_attributes, _as_float,
)
# Reuse: representative-trace picker + alignment-row builder for the flow idioms.
from tasks.task28 import build_task28_context


# ---------------------------------------------------------------------------
# Configuration (settled design decisions, kept as module constants)
# ---------------------------------------------------------------------------

# Sentinel for the derived "throughput time" reason (no raw log key; taken from
# task20's per-trace ``duration_hours``).
THROUGHPUT_KEY = "__throughput_hours__"

NUMERIC_BUCKETS = 4   # quantile buckets for a numeric attribute's bar/parallel dim
MAX_CATEGORIES  = 5   # top categories kept for a categorical attribute (rest -> "Other")

_GREY_PALETTE = [GREY_MED, GREY_LIGHT, GREY_DARK, GREY_LIGHTER]

# Stems + titles for the empty-state fallback (one per idiom).
_EMPTY_STEMS = [
    ("task13_bar_chart.svg",                       "Violation Rate by Attribute"),
    ("task13_scatter_plot.svg",                    "Attribute Value vs. Violations"),
    ("task13_table.svg",                           "Attributes Associated with Violations"),
    ("task13_table_and_bar_chart.svg",             "Attribute Evidence"),
    ("task13_parallel_sets.svg",                   "Attribute Bucket vs. Violation"),
    ("task13_flow_chart_and_table.svg",            "Violation Flow & Attribute Evidence"),
    ("task13_flow_chart_elaborate_bpmn_table.svg", "Violation Locations & Attribute Evidence"),
]


# ---------------------------------------------------------------------------
# Attribute extraction (verification reuses task30 helpers)
# ---------------------------------------------------------------------------

def _safe(key: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in str(key)).strip("_")


def _available_attributes(log) -> list:
    """Case- and event-level attribute names visible on the first trace."""
    attrs = set(_available_case_attributes(log))
    if len(log) > 0 and len(log[0]) > 0:
        attrs.update(log[0][0].keys())
    return sorted(attrs)


def _collect_attribute_column(log, key: str):
    """Per-trace representative value for *key* + the column type.

    A case-level value (with or without 'case:' prefix) is taken as-is; otherwise
    the event-level values are aggregated per trace — numeric attributes by mean,
    categorical attributes by mode. The whole column is classified numeric only if
    every observed value coerces to float (mirrors task30's split logic).

    Returns (values_per_trace, kind) with kind in {"numeric","categorical","missing"}.
    """
    per_trace_raw = []
    for trace in log:
        cv = _trace_attribute_value(trace, key)
        if cv is not None:
            per_trace_raw.append([cv])
        else:
            per_trace_raw.append([ev[key] for ev in trace if key in ev])

    flat = [v for lst in per_trace_raw for v in lst]
    if not flat:
        return None, "missing"

    numeric = all(_as_float(v) is not None for v in flat)
    if numeric:
        values = []
        for lst in per_trace_raw:
            floats = [f for f in (_as_float(v) for v in lst) if f is not None]
            values.append(float(np.mean(floats)) if floats else np.nan)
        return values, "numeric"

    values = []
    for lst in per_trace_raw:
        if not lst:
            values.append(None)
        else:
            values.append(pd.Series([str(v) for v in lst]).mode().iloc[0])
    return values, "categorical"


def _build_evidence_frame(log, feat: pd.DataFrame, candidate_attributes: list):
    """Per-trace evidence frame + kept-attribute metadata.

    Columns: trace_index, violation_count, violation(bool), one value column per
    kept candidate attribute. The violation label is reused from task20's frame
    (violation_count > 0) — alignments are never re-run here.
    """
    n = len(feat)
    base = pd.DataFrame({
        "trace_index": feat["trace_index"].to_numpy(),
        "violation_count": feat["violation_count"].to_numpy(),
        "violation": feat["violation_count"].to_numpy() > 0,
    })

    import trace_features

    attr_meta = []
    for key in candidate_attributes:
        label = trace_features.label_for(key)
        if key == THROUGHPUT_KEY and "duration_hours" in feat:
            # Already in task20's frame; reuse rather than walking every trace's
            # timestamps a second time for the same number.
            values, kind = feat["duration_hours"].to_numpy(dtype=float), "numeric"
        else:
            try:
                values, value_type = trace_features.extract(log, key)
                values, kind = trace_features.as_bucketable(values, value_type, key=key)
            except (KeyError, ValueError) as e:
                logger.warning(f"      task13: skipping attribute '{key}' — {e}")
                continue
            values = (list(values) + [None] * n)[:n]   # guard length

        col = f"attr__{_safe(key)}"
        base[col] = values
        attr_meta.append({"key": key, "label": label, "type": kind, "col": col})

    return base, attr_meta


# ---------------------------------------------------------------------------
# Bucketing (shared by bar chart + parallel sets)
# ---------------------------------------------------------------------------

def _bucket_categories(values, max_categories: int):
    """Top (max_categories-1) categories by frequency; the rest -> 'Other'."""
    s = pd.Series([str(v) for v in values])
    top = s.value_counts().head(max_categories - 1).index.tolist()
    return [v if v in top else "Other" for v in s]


def _bucket_assign(values, kind: str, strategy: str = None, cap: int = None):
    """Assign each trace to a bucket label.

    Thin wrapper over the shared splitter (trace_features.split), which unified
    this with task30's median split — the two were the same operation under
    different numeric strategies. Defaults here keep this call site's original
    behaviour: quantile ranges for numeric, top categories + 'Other' otherwise.

    Returns (label_per_trace, ordered_labels) or None when the values cannot be
    bucketed. label_per_trace entries are None for missing values.
    """
    import trace_features

    if cap is None:
        cap = NUMERIC_BUCKETS if kind == "numeric" else MAX_CATEGORIES - 1
    result = trace_features.split(values, kind, strategy=strategy, cap=cap)
    if not result:
        return None
    return result.assignment, result.labels


# Structural / format-level keys that are never candidate reasons. The check is
# dataset-independent: a key that isn't in a given log simply won't appear, so this
# set is safe across datasets (REG_DATE is a raw registration timestamp — bucketable
# but not an interpretable violation driver).
_NON_CANDIDATE_KEYS = {
    "concept:name", "time:timestamp", "lifecycle:transition",
    "case:concept:name",
}


def _is_structural_key(key: str) -> bool:
    return (key in _NON_CANDIDATE_KEYS
            or str(key).startswith("@@")
            or str(key).lower().startswith("unnamed"))


def discover_candidate_attributes(log, feat=None) -> list:
    """Dataset-independent default candidate attributes ("reasons").

    Now `trace_features.default_keys`: the registry's canonical features for this
    log. The key-scanning this replaces read a raw column's *first event* as the
    trace's value — a fallback meant for case attributes replicated onto events,
    which cannot tell those apart from an attribute that genuinely varies within
    the trace. On BPIC12 every trace's `org:resource` came back as 112, the
    automatic submitter of the first event, so the column looked constant and the
    log's 61 executors were never offered. The registry decides case-level vs
    event-level by whether the value is constant, and derives named features
    (`resource::dominant`, `amount::last`) for the ones that are not.

    ``feat`` is accepted for call-site compatibility and no longer needed: the
    registry derives throughput time from the log itself.
    """
    import trace_features

    return trace_features.default_keys(log)


def _bucket_rates(values, kind: str, violation):
    """(bucket_labels, violation_rate_pct, trace_counts) for one attribute, or None."""
    res = _bucket_assign(values, kind)
    if res is None:
        return None
    assign, labels = res
    df = pd.DataFrame({"b": assign, "viol": np.asarray(violation, dtype=float)})
    df = df[df["b"].notna()]
    rates, counts = [], []
    for lab in labels:
        sub = df[df["b"] == lab]
        rates.append(float(sub["viol"].mean() * 100) if len(sub) else 0.0)
        counts.append(int(len(sub)))
    return labels, rates, counts


# ---------------------------------------------------------------------------
# Association measures (one interpretable number per attribute)
# ---------------------------------------------------------------------------

def _point_biserial(values, labels):
    """Point-biserial correlation between a numeric attribute and the binary
    violation label. Returns (r, |r|). r > 0 ⇒ higher value, more violations."""
    x = pd.to_numeric(pd.Series(values), errors="coerce").to_numpy(dtype=float)
    y = np.asarray(labels, dtype=float)
    mask = ~np.isnan(x)
    x, y = x[mask], y[mask]
    if len(x) < 3 or np.std(x) < 1e-12 or len(np.unique(y)) < 2:
        return 0.0, 0.0
    try:
        r, _p = stats.pointbiserialr(y, x)
    except Exception:
        return 0.0, 0.0
    if np.isnan(r):
        return 0.0, 0.0
    return float(r), abs(float(r))


def _cramers_v(values, labels, max_categories: int = MAX_CATEGORIES):
    """Cramér's V between a (bucketed) categorical attribute and the binary
    violation label. Returns (V in [0,1], worst_category) where worst_category is
    the bucket with the highest violation rate (the association's 'direction')."""
    s = pd.Series([None if v is None else str(v) for v in values])
    y = pd.Series(np.asarray(labels, dtype=float))
    mask = s.notna()
    s, y = s[mask], y[mask]
    if s.empty:
        return 0.0, None

    cats = _bucket_categories(s.tolist(), max_categories)
    df = pd.DataFrame({"cat": cats, "viol": y.to_numpy()})
    rates = df.groupby("cat")["viol"].mean()
    worst = rates.idxmax() if not rates.empty else None

    tbl = pd.crosstab(df["cat"], df["viol"])
    if tbl.shape[0] < 2 or tbl.shape[1] < 2:
        return 0.0, worst
    chi2 = stats.chi2_contingency(tbl)[0]
    n = tbl.to_numpy().sum()
    if n == 0:
        return 0.0, worst
    phi2 = chi2 / n
    r, k = tbl.shape
    denom = min(k - 1, r - 1)
    v = float(np.sqrt(phi2 / denom)) if denom > 0 else 0.0
    return min(v, 1.0), worst


def _rank_attributes(evidence_df: pd.DataFrame, attr_meta: list):
    """Compute each attribute's association strength + direction; rank descending."""
    labels = evidence_df["violation"].to_numpy()
    ranking = []
    for m in attr_meta:
        vals = evidence_df[m["col"]].tolist()
        if m["type"] == "numeric":
            r, strength = _point_biserial(vals, labels)
            direction = ("higher → more violations" if r > 0
                         else "higher → fewer violations" if r < 0
                         else "no clear direction")
            measure = "point-biserial r"
        else:
            strength, worst = _cramers_v(vals, labels)
            direction = (f"‘{worst}’ → most violations" if worst is not None
                         else "no clear direction")
            measure = "Cramér's V"
        ranking.append({**m, "strength": strength, "direction": direction, "measure": measure})
    ranking.sort(key=lambda d: d["strength"], reverse=True)
    return ranking


def _evidence_table_data(ranking: list):
    """(cell_text, col_labels) for the ranked attribute-evidence table."""
    col_labels = ["Attribute", "Type", "Assoc.", "Direction"]
    cell_text = [[r["label"], r["type"], f"{r['strength']:.2f}", r["direction"]]
                 for r in ranking]
    return cell_text, col_labels


# ---------------------------------------------------------------------------
# Idiom renderers
# ---------------------------------------------------------------------------

def task13_bar_chart(attr_meta, evidence_df, output_dir):
    """Small multiples: one bar group per candidate attribute, violation rate per bucket."""
    path = os.path.join(output_dir, "task13_bar_chart.svg")
    violation = evidence_df["violation"].to_numpy()
    panels = []
    for m in attr_meta:
        res = _bucket_rates(evidence_df[m["col"]].tolist(), m["type"], violation)
        if res is not None:
            panels.append((m, res))
    if not panels:
        render_empty_state_svg(path, "Violation Rate by Attribute",
                               "No candidate attribute had enough variance to bucket.")
        return

    ncols = len(panels)
    fig, axes = plt.subplots(1, ncols, figsize=(max(5.0, ncols * 4.2), 5.0), squeeze=False)
    for ax, (m, (labels, rates, counts)) in zip(axes[0], panels):
        pos = np.arange(len(labels))
        ax.bar(pos, rates, color=GREY_MED, edgecolor="white")
        for p, rate, c in zip(pos, rates, counts):
            ax.text(p, rate + 1.5, f"{rate:.0f}%\n(n={c})", ha="center", va="bottom",
                    fontsize=FONT_ANNOT - 1, color="#333333")
        ax.set_xticks(pos)
        ax.set_xticklabels(labels, fontsize=FONT_ANNOT - 1)
        ax.set_xlabel(f"{m['label']} ({m['type']})", fontsize=FONT_LABEL)
        ax.set_ylim(0, 100)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.45)
        ax.set_axisbelow(True)
    axes[0][0].set_ylabel("Violation rate (%)", fontsize=FONT_LABEL)
    fig.suptitle("Guideline Violations by Candidate Attribute", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task13_scatter_plot(attr_meta, evidence_df, output_dir):
    """One subplot per candidate attribute, y = #violations per trace.
    Numeric attributes: x = value (scatter). Categorical attributes: x = category
    (jittered strip plot, top categories + 'Other'). Colour = conformant /
    non-conformant. All candidate attributes are shown."""
    path = os.path.join(output_dir, "task13_scatter_plot.svg")
    panels = []
    for m in attr_meta:
        if m["type"] == "numeric":
            v = pd.to_numeric(pd.Series(evidence_df[m["col"]]), errors="coerce")
            if v.notna().sum() >= 2 and v.dropna().nunique() >= 2:
                panels.append((m, v))
        else:
            vals = evidence_df[m["col"]].tolist()
            if any(v is not None for v in vals):
                panels.append((m, vals))
    if not panels:
        render_empty_state_svg(path, "Attribute Value vs. Violations",
                               "No candidate attribute with variance to plot.")
        return

    viol_count = evidence_df["violation_count"].to_numpy(dtype=float)
    nonconf = evidence_df["violation"].to_numpy()
    colors = np.where(nonconf, GREY_DARK, GREY_LIGHTER)

    ncols = len(panels)
    fig, axes = plt.subplots(1, ncols, figsize=(max(5.0, ncols * 4.6), 5.0), squeeze=False)
    rng = np.random.default_rng(0)
    for ax, (m, data) in zip(axes[0], panels):
        if m["type"] == "numeric":
            ax.scatter(data.to_numpy(dtype=float), viol_count, c=colors, s=16, alpha=0.6, linewidths=0)
            ax.set_xlabel(m["label"], fontsize=FONT_LABEL)
        else:
            mask = np.array([v is not None for v in data])
            cats = _bucket_categories([v for v, k in zip(data, mask) if k], MAX_CATEGORIES)
            order = [c for c in dict.fromkeys(cats) if c != "Other"] + (["Other"] if "Other" in cats else [])
            index_of = {c: i for i, c in enumerate(order)}
            x = np.array([index_of[c] for c in cats], dtype=float)
            x = x + rng.uniform(-0.15, 0.15, size=len(x))
            ax.scatter(x, viol_count[mask], c=colors[mask], s=16, alpha=0.6, linewidths=0)
            ax.set_xticks(range(len(order)))
            ax.set_xticklabels(order, rotation=30, ha="right", fontsize=FONT_ANNOT - 1)
            ax.set_xlabel(m["label"], fontsize=FONT_LABEL)
        ax.set_title(f"{m['label']} ({m['type']})", fontsize=FONT_LABEL)
        ax.spines[["top", "right"]].set_visible(False)
        ax.yaxis.grid(True, linestyle="--", alpha=0.4)
        ax.set_axisbelow(True)
    axes[0][0].set_ylabel("# Violations per trace", fontsize=FONT_LABEL)
    fig.legend(
        handles=[mpatches.Patch(color=GREY_LIGHTER, label="Conformant"),
                 mpatches.Patch(color=GREY_DARK, label="Non-conformant")],
        loc="lower center", ncol=2, frameon=False, fontsize=FONT_ANNOT,
    )
    fig.suptitle("Attribute Value vs. Per-trace Violations", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task13_table(ranking, evidence_df, output_dir):
    """Small multiples: one bucket-breakdown table per candidate attribute,
    matching bar_chart's per-attribute panels — Bucket | # Traces | Violation Rate."""
    path = os.path.join(output_dir, "task13_table.svg")
    violation = evidence_df["violation"].to_numpy()
    panels = []
    for r in ranking:
        res = _bucket_rates(evidence_df[r["col"]].tolist(), r["type"], violation)
        if res is not None:
            panels.append((r, res))
    if not panels:
        render_empty_state_svg(path, "Attributes Associated with Guideline Violations",
                               "No candidate attribute had enough variance to bucket.")
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
        ax.set_title(f"{r['label']}\n({r['type']}, assoc.={r['strength']:.2f})",
                     fontsize=FONT_LABEL, pad=8)
    fig.suptitle("Guideline Violations by Candidate Attribute", fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task13_table_and_bar_chart(ranking, output_dir):
    """Attribute-evidence table (left) + adjacent association-strength bars (right)."""
    fig = plt.figure(figsize=(15, max(3.2, 1.6 + len(ranking) * 0.55)))
    gs = gridspec.GridSpec(1, 2, width_ratios=[1.5, 1.0], wspace=0.42)

    cell_text, col_labels = _evidence_table_data(ranking)
    ax_t = fig.add_subplot(gs[0])
    ax_t.axis("off")
    make_table(
        ax_t,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.02, 0.05, 0.96, 0.80],
        col_widths=[0.26, 0.20, 0.16, 0.38],
        font_size=9.5,
        cell_pad=0.08,
    )
    ax_t.set_title("Attribute Evidence (ranked)", fontsize=FONT_TITLE, pad=8)

    ax_b = fig.add_subplot(gs[1])
    labels = [r["label"] for r in ranking][::-1]
    strengths = [r["strength"] for r in ranking][::-1]
    y = np.arange(len(labels))
    ax_b.barh(y, strengths, color=GREY_MED, edgecolor="white")
    ax_b.set_yticks(y)
    ax_b.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax_b.set_xlim(0, 1.0)
    ax_b.set_xlabel("Association strength", fontsize=FONT_LABEL)
    for i, s in enumerate(strengths):
        ax_b.text(min(s + 0.02, 0.98), i, f"{s:.2f}", va="center", fontsize=FONT_ANNOT - 1)
    ax_b.spines[["top", "right"]].set_visible(False)
    ax_b.set_title("Strength", fontsize=FONT_TITLE, pad=8)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task13_table_and_bar_chart.svg"))


def task13_parallel_sets(evidence_df, ranking, output_dir):
    """Small multiples: one parallel-sets diagram per candidate attribute, each
    showing bucket of that attribute × violation present (yes/no). Ribbon width
    = number of traces. All candidate attributes are shown, not just the
    top-ranked one."""
    path = os.path.join(output_dir, "task13_parallel_sets.svg")
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
        render_empty_state_svg(path, "Attribute Bucket vs. Violation",
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
            # No right_title: the bars right below are already individually
            # labelled "Violation" / "No violation", so a column header there
            # is redundant — and with panels this narrow, dropping it is what
            # stops it colliding with the (often long) left_title.
            left_title=wrap_text(r["label"].replace("_", " "), 14), right_title="",
        )
    # Title above the column headers (which draw_parallel_sets places at y=1.08).
    fig.suptitle("Guideline Violations by Candidate Attribute",
                 fontsize=FONT_TITLE, y=0.99)
    fig.subplots_adjust(top=0.78, wspace=0.5)
    save_svg(fig, path)


def task13_flow_chart_and_table(ctx, ranking, output_dir):
    """Basic chevron of a representative violating trace + the attribute-evidence
    table — where the violations sit (flow) and which attributes explain them.
    Stem 'flow_chart_and_table' → canonical slug 'flow_chart_table'."""
    path = os.path.join(output_dir, "task13_flow_chart_and_table.svg")
    if ctx is None:
        render_empty_state_svg(path, "Violation Flow & Attribute Evidence",
                               "No usable alignment to display.")
        return

    nodes = chevron_nodes_from_alignment_rows(ctx["rows"])
    cell_text, col_labels = _evidence_table_data(ranking)

    fig_w = max(13.0, chevron_figure_width(nodes))
    fig_h = max(6.5, 3.2 + len(ranking) * 0.55)
    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(2, 1, height_ratios=[1.0, max(1.2, 0.5 * len(ranking) + 0.8)],
                           hspace=0.30)

    ax_flow = fig.add_subplot(gs[0])
    draw_chevron_strip(ax_flow, nodes, fontsize=10)
    ax_flow.set_title(
        f"Representative Violating Trace ({ctx['trace_label']}, fitness={ctx['fitness']:.3f})",
        fontsize=FONT_TITLE, pad=6)

    ax_tab = fig.add_subplot(gs[1])
    ax_tab.axis("off")
    make_table(
        ax_tab,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.04, 0.05, 0.92, 0.84],
        col_widths=[0.26, 0.20, 0.16, 0.38],
        font_size=9.5,
        cell_pad=0.08,
    )
    ax_tab.set_title("Attributes Explaining the Violations (ranked)", fontsize=FONT_TITLE, pad=6)
    fig.tight_layout(pad=1.2)
    save_svg(fig, path)


def task13_flow_chart_elaborate_bpmn_table(ctx, ranking, model_path, output_dir):
    """Elaborate BPMN with violation locations annotated + the attribute-evidence
    table beneath (reuses shared.compose_bpmn_panels, as task27 does).
    Stem 'flow_chart_elaborate_bpmn_table' → canonical slug 'flow_chart_elaborate_table'."""
    path = os.path.join(output_dir, "task13_flow_chart_elaborate_bpmn_table.svg")
    if ctx is None or not model_path:
        render_empty_state_svg(path, "Violation Locations & Attribute Evidence",
                               "No alignment or model available.")
        return
    try:
        parsed = parse_bpmn_model(model_path)
    except Exception as e:
        logger.warning(f"      task13: BPMN parse failed: {e}")
        render_empty_state_svg(path, "Violation Locations & Attribute Evidence",
                               "BPMN model could not be parsed.")
        return
    if not parsed.get("elements"):
        render_empty_state_svg(path, "Violation Locations & Attribute Evidence",
                               "No BPMN geometry to render.")
        return

    panels = [{
        "parsed": parsed,
        "node_style_fn": alignment_violation_node_style(ctx["rows"]),
        "subtitle": (f"Violation locations on the desired model "
                     f"({ctx['trace_label']}, fitness={ctx['fitness']:.3f})"),
    }]
    table_rows = [[r["label"], r["type"], f"{r['strength']:.2f}", r["direction"]]
                  for r in ranking]
    compose_bpmn_panels(
        panels,
        path,
        title="Where Violations Sit (flow) & Which Attributes Explain Them (table)",
        legend_items=[
            (GREY_MED,    "#444444", 3, "Model move (skipped step)"),
            (GREY_LIGHTER,   "#666666", 2, "Conform (synchronous)"),
            ("white", "#888888", 2, "Not on this trace"),
        ],
        table_rows=table_rows,
        table_cols=["Attribute", "Type", "Assoc.", "Direction"],
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
    """Generate all Task ID 13 SVGs into output_dir.

    Parameters mirror the pipeline calling convention: the central alignment run
    is reused (never recomputed) — task20's feature frame supplies the per-trace
    violation label and the throughput-time reason.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 13 visualizations ---")

    if not log or not alignments:
        logger.warning("      task13: empty log / alignments — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No log or alignment data available.")
        return

    feat = task20_trace_feature_dataframe(log, alignments)
    if feat is None or feat.empty:
        logger.warning("      task13: no trace features — emitting empty-state SVGs.")
        _emit_all_empty(output_dir, "No per-trace features available.")
        return

    if candidate_attributes is None:
        candidate_attributes = discover_candidate_attributes(log, feat)

    evidence_df, attr_meta = _build_evidence_frame(log, feat, candidate_attributes)
    if not attr_meta:
        logger.warning(
            f"      task13: none of the candidate attributes were present. "
            f"Available: {_available_attributes(log)}"
        )
        _emit_all_empty(output_dir, "No candidate attributes found in the log.")
        return

    n_viol = int(evidence_df["violation"].sum())
    if n_viol == 0:
        logger.warning("      task13: all traces conformant — no violations to explain.")
        _emit_all_empty(output_dir, "All traces conformant — no guideline violations to explain.")
        return

    ranking = _rank_attributes(evidence_df, attr_meta)
    logger.info("      task13: ranked reasons — " +
                ", ".join(f"{r['label']}={r['strength']:.2f}" for r in ranking))

    # Statistical idioms
    task13_bar_chart(attr_meta, evidence_df, output_dir)
    # task13_scatter_plot(attr_meta, evidence_df, output_dir)
    task13_table(ranking, evidence_df, output_dir)
    # task13_table_and_bar_chart(ranking, output_dir)
    task13_parallel_sets(evidence_df, ranking, output_dir)

    # Flow combos commented out
    # ctx = build_task28_context(alignments)
    # task13_flow_chart_and_table(ctx, ranking, output_dir)
    # task13_flow_chart_elaborate_bpmn_table(ctx, ranking, model_path, output_dir)
