"""
tasks/task31.py – Task 6: Conformance degree vs. positive process outcome.

Public API:
    generate(log, alignments, output_dir, outcome_activity="")
        outcome_activity  – activity name that constitutes a positive outcome;
                            empty = inferred from the log by
                            shared.infer_terminal_activity
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["table", "bar_chart", "stacked_bar", "matrix", "heatmap"]


PARAM_SPEC = [
    {
        "key": "outcome_activity",
        "label": "Positive-outcome activity (present in trace = Positive group)",
        "hint": "The 'Positive' group is made up of traces that contain this activity",
        "widget": "activity-picker",
        "source": "log.activities",
        "default": "",
        "required": True,
    },
]


def validate_params(log, params) -> list:
    act = params.get("outcome_activity")
    if not act:
        return ["An outcome activity is required."]
    total = len(log)
    present = sum(1 for trace in log if act in {str(e.get("concept:name", "")) for e in trace})
    if present == 0:
        return [f"Outcome activity '{act}' is not present in any trace."]
    if present == total:
        return [f"Outcome activity '{act}' is present in all traces — cannot split into two groups."]
    return []


import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates

from shared import (
    save_svg, make_table,
    format_threshold, PAIR_COLORS, GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT, draw_value_heatmap, render_empty_state_svg,
    infer_terminal_activity,
)
from tasks.task20 import (
    task20_trace_feature_dataframe,
    _task20_feature_label,
)

# Alias so internal references work
_task20_format_threshold = format_threshold


# Task 6 – Conformance degree vs. positive process outcome
# ---------------------------------------------------------------------------

# Task 6 data + labeling helpers
# Module-level outcome activity — overridden by generate() at runtime
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


def task31_outcome_dataframe(log, alignments, outcome_activity=None):
    """Per-trace conformance and whether the trace reached the process goal.

    The goal is reached when the trace *ends* with the chosen activity, not when
    it merely contains it somewhere. Containment made the question softer than
    it reads — a case that reaches approval and is later withdrawn contains the
    approval — and it needed a second list of rejection activities to decide
    which traces had a definite answer at all. Ending on the activity is a
    definite answer for every trace, so that list, and the filter that dropped
    the rest, are both gone.
    """
    import trace_features

    oa = outcome_activity
    df = task20_trace_feature_dataframe(log, alignments)
    if df.empty:
        return df
    last, _ = trace_features.extract(log, trace_features.LAST_ACTIVITY_KEY)
    df["positive_outcome"] = [a == oa for a in last[:len(df)]]
    df["conformance_rate"] = df["fitness"].astype(float)
    df["is_fully_conformant"] = (df["fitness"] >= 1.0).astype(float)
    df["is_not_fully_conformant"] = (df["fitness"] < 1.0).astype(float)
    return df.reset_index(drop=True)


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


# Task 6 tree helpers (data/model)
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


def task31_summary_table_dataframe(df: pd.DataFrame):
    """Positive-outcome rate per conformance band — the bar chart's payload.

    It used to list decision-tree branch conditions ("duration <= 5.1 days …"),
    which are a different cut of the log from the bands every other idiom here
    shows, and it added the case counts behind each rate. Same bands, same
    numbers as the bar chart now.
    """
    cols = ["band", "n", "rate"]
    if df.empty:
        return pd.DataFrame(columns=cols)

    bands = _assign_fitness_band(df["fitness"], include_exact_one=True)
    rows = []
    for label in _FITNESS_BIN_LABELS_EXACT:
        mask = bands == label
        n = int(mask.sum())
        n_pos = int(df.loc[mask, "positive_outcome"].sum()) if n else 0
        rows.append({"band": label, "n": n,
                     "rate": (n_pos / n * 100) if n else float("nan")})
    return pd.DataFrame(rows, columns=cols)


# Task 6 visualizations
def task31_table(df_table: pd.DataFrame, output_dir: str):
    """The bar chart's bands and rates, read as a table."""
    cell_text = [
        [row["band"],
         f"{int(row['n']):,}",
         "—" if pd.isna(row["rate"]) else f"{row['rate']:.1f}"]
        for _, row in df_table.iterrows()
    ]

    fig_h = max(3.3, 1.35 + len(cell_text) * 0.52)
    fig, ax = plt.subplots(figsize=(8.5, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["Conformance Category", "Traces",
                    "Positive Outcome Rate (%)"],
        bbox=[0.04, 0.08, 0.92, 0.70],
        col_widths=[0.40, 0.22, 0.38],
        font_size=10.5,
        scale_xy=(1, 1.85),
        header_color=GREY_DARK,
        zebra=True,
    )
    ax.set_title("Conformance Category vs. Positive Outcome Rate",
                 fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task31_table.svg"))


# ---------------------------------------------------------------------------
# New idiom 1: Bar chart — outcome rate per conformance band
# ---------------------------------------------------------------------------

def task31_bar_chart(df: pd.DataFrame, output_dir: str):
    """Bar chart: positive outcome rate per conformance degree band (6 bands incl. exact 1.0)."""
    out_path = os.path.join(output_dir, "task31_bar_chart.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Conformance Category vs. Positive Outcome Rate")
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

    ax.bar(x, agg["rate"].fillna(0), width=0.58, color=GREY_DARK, zorder=3,
           edgecolor="white")

    # "rate% (n=N)" above each non-empty bar — inside it near the ceiling, where
    # a label above would fall outside the fixed 0-100 axis.
    for i, row in agg.iterrows():
        n = row["n"]
        rate = row["rate"]
        if n == 0 or np.isnan(rate):
            continue
        if rate > 93:
            # Inside the bar, because above it would leave the 0-100 axis.
            # On one line the label is wider than the bar, so its ends would
            # be white on the white background; stacked, it stays on navy.
            ax.text(i, rate - 3.0, f"{rate:.1f}%\n(n={n})",
                    ha="center", va="top", fontsize=FONT_ANNOT - 1,
                    color="#ffffff", linespacing=1.5, zorder=4)
        else:
            ax.text(i, rate + 2.0, f"{rate:.1f}%  (n={n})",
                    ha="center", va="bottom", fontsize=FONT_ANNOT,
                    color="#222222")

    # A rate cannot pass 100, and a headroom factor that lets the axis run to
    # 120 makes the tallest bar look short of a ceiling that does not exist.
    ax.set_ylim(0, 100)
    ax.set_xlim(-0.6, len(_FITNESS_BIN_LABELS_EXACT) - 0.4)
    ax.set_xticks(x)
    ax.set_xticklabels(_FITNESS_BIN_LABELS_EXACT, fontsize=FONT_ANNOT)
    ax.set_xlabel("Conformance Category", fontsize=FONT_LABEL)
    ax.set_ylabel("Positive Outcome Rate (%)", fontsize=FONT_LABEL)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.set_title("Conformance Category vs. Positive Outcome Rate", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 2: Stacked bar — outcome composition per conformance band
# ---------------------------------------------------------------------------

def task31_stacked_bar(df: pd.DataFrame, output_dir: str):
    """100%-stacked bar: positive vs negative outcome share per conformance category.

    Every category keeps its slot, empty ones included — they carry NaN, so no
    bar is drawn and none is annotated. Dropping them would give this idiom a
    different x axis from the other four, which show the same empty categories
    as a blank cell or a "—".
    """
    out_path = os.path.join(output_dir, "task31_stacked_bar.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Outcome Composition by Conformance Category")
        return

    bands = _assign_fitness_band(df["fitness"], include_exact_one=True)
    band_data = []
    for label in _FITNESS_BIN_LABELS_EXACT:
        mask = bands == label
        n = int(mask.sum())
        n_pos = int(df.loc[mask, "positive_outcome"].sum()) if n else 0
        prop_pos = (n_pos / n) if n else float("nan")
        band_data.append({"band": label, "n": n, "prop_pos": prop_pos,
                          "prop_neg": 1.0 - prop_pos})

    if all(d["n"] == 0 for d in band_data):
        render_empty_state_svg(out_path, "Outcome Composition by Conformance Category")
        return

    n_cats = len(band_data)
    fig_w = max(6.5, min(11.0, 1.3 * n_cats + 2.0))
    fig, ax = plt.subplots(figsize=(fig_w, 5.2))
    ax.set_facecolor("#fafbfc")

    x = np.arange(n_cats)
    # Encode n= into x-tick labels (avoids below-axis collision)
    band_labels = [f"{d['band']}\n(n={d['n']})" for d in band_data]
    prop_pos_arr = np.array([d["prop_pos"] for d in band_data])
    prop_neg_arr = np.array([d["prop_neg"] for d in band_data])

    # Bottom segment = positive (darker), top = negative (lighter)
    # PAIR_COLORS is the palette's pair for two unordered groups: dark navy
    # against cividis's bright yellow. GREY_LIGHT (#a99f73) sat in the olive
    # middle and read as a third, muted category.
    _POSITIVE, _NEGATIVE = PAIR_COLORS
    ax.bar(x, prop_pos_arr, color=_POSITIVE, edgecolor="white",
           label="Positive outcome")
    ax.bar(x, prop_neg_arr, bottom=prop_pos_arr, color=_NEGATIVE,
           edgecolor="white", label="Negative outcome")

    # Annotate segments
    for i in range(n_cats):
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
    ax.set_xlabel("Conformance Category", fontsize=FONT_LABEL)
    ax.set_ylabel("Proportion of Cases", fontsize=FONT_LABEL)
    ax.set_xlim(-0.6, n_cats - 0.4)
    ax.set_ylim(0, 1.0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)

    legend_patches = [
        mpatches.Patch(facecolor=_POSITIVE, label="Positive outcome"),
        mpatches.Patch(facecolor=_NEGATIVE, label="Negative outcome"),
    ]
    ax.legend(handles=legend_patches,
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)
    ax.set_title("Outcome Composition by Conformance Category", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# New idiom 3: Scatter plot — trace-level fitness vs outcome + temporal panel
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# New idiom 4: Matrix — P(outcome | fitness band) exact rates
# ---------------------------------------------------------------------------

def _band_outcome_rates(df: pd.DataFrame):
    """(counts, rates) per conformance band x {negative, positive}.

    The matrix and the heatmap draw this same table — one as numbers, one as
    colour — and the bar chart, the table and the stacked bar carry its positive
    column. The bands are the bar chart's, `= 1.0` included: whether a trace is
    perfectly conformant is the cut this task asks about, so a figure that bins
    it away with 0.8-1.0 answers a coarser question than the rest.
    """
    bands = _assign_fitness_band(df["fitness"], include_exact_one=True)
    counts = np.zeros((len(_FITNESS_BIN_LABELS_EXACT), 2), dtype=int)
    for i, label in enumerate(_FITNESS_BIN_LABELS_EXACT):
        mask = bands == label
        n = int(mask.sum())
        n_pos = int(df.loc[mask, "positive_outcome"].sum()) if n > 0 else 0
        counts[i, 0] = n - n_pos   # negative
        counts[i, 1] = n_pos       # positive
    totals = counts.sum(axis=1)
    safe = np.where(totals[:, np.newaxis] == 0, 1, totals[:, np.newaxis])
    # NaN, not 0.0, for a category no trace falls into. A zero would read as
    # "none of these traces had a positive outcome", which is a finding; there
    # are no traces. The matrix prints such a row as "—" and the heatmap leaves
    # its cells blank.
    rates = np.where(totals[:, np.newaxis] > 0, counts / safe * 100, np.nan)
    return counts, rates, totals


def task31_matrix(df: pd.DataFrame, output_dir: str):
    """The band x outcome table as numbers. The heatmap draws it as colour."""
    out_path = os.path.join(output_dir, "task31_matrix.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Outcome Rate by Conformance Category")
        return

    counts_full, rate_matrix, row_totals_full = _band_outcome_rates(df)
    if (row_totals_full > 0).sum() < 2:
        render_empty_state_svg(out_path, "Outcome Rate by Conformance Category")
        return

    fig_h = max(3.8, min(7.0, 1.3 + len(_FITNESS_BIN_LABELS_EXACT) * 0.72))
    fig, ax = plt.subplots(figsize=(6.0, fig_h))

    draw_value_heatmap(
        fig, ax,
        data=np.nan_to_num(rate_matrix, nan=0.0),
        row_labels=_FITNESS_BIN_LABELS_EXACT,
        col_labels=["Negative Outcome", "Positive Outcome"],
        xlabel="Outcome Category",
        annotate=False,   # manual two-line annotations added below
        rotate_xticks=0,
        colorless=True,
    )

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
                ax.text(c, r, f"{rate:.1f}%\n(n={int(count)})",
                        ha="center", va="center", fontsize=FONT_ANNOT - 1,
                        color=GREY_DARK, linespacing=1.4)

    ax.set_ylabel("Conformance Category", fontsize=FONT_LABEL)
    # Matrix convention: keep all four spines (bounding box of the color grid)
    ax.set_title("Outcome Rate by Conformance Category", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Idiom 5: Heatmap — the matrix, encoded as colour
# ---------------------------------------------------------------------------

def task31_heatmap(df: pd.DataFrame, output_dir: str):
    """The same band x outcome table as the matrix, as colour instead of numbers.

    It used to cut the bands by calendar quarter as well. That is a second
    variable no other idiom here carries, and it answers a different question —
    whether the link between conformance and outcome moves over time — so the
    five idioms were not comparable.
    """
    out_path = os.path.join(output_dir, "task31_heatmap.svg")
    if df.empty:
        render_empty_state_svg(out_path, "Outcome Rate by Conformance Category")
        return

    _counts, rate_matrix, row_totals = _band_outcome_rates(df)
    if (row_totals > 0).sum() < 2:
        render_empty_state_svg(out_path, "Outcome Rate by Conformance Category")
        return

    fig_h = max(3.8, min(7.0, 1.3 + len(_FITNESS_BIN_LABELS_EXACT) * 0.72))
    fig, ax = plt.subplots(figsize=(6.4, fig_h))

    draw_value_heatmap(
        fig, ax,
        data=rate_matrix,   # NaN rows stay blank rather than reading as 0%
        row_labels=_FITNESS_BIN_LABELS_EXACT,
        col_labels=["Negative Outcome", "Positive Outcome"],
        xlabel="Outcome Category",
        cbar_label="% of traces in category",
        annotate=False,
        rotate_xticks=0,
        vmax=100,
    )
    ax.set_ylabel("Conformance Category", fontsize=FONT_LABEL)
    ax.set_title("Outcome Rate by Conformance Category", fontsize=FONT_TITLE, pad=10)

    fig.tight_layout(pad=1.2)
    save_svg(fig, out_path)


def generate(log, alignments, output_dir: str, outcome_activity: str = ""):
    """Generate all Task 6 SVGs into output_dir.

    outcome_activity: activity that marks a positive process outcome.
    If empty, inferred automatically from the log.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 31 visualizations ---")

    if not outcome_activity:
        # This task's goal is "the trace ends here", so the fallback has to
        # pick a terminal activity rather than a widely present one.
        outcome_activity = infer_terminal_activity(log)
        logger.info(f"      task31: outcome_activity inferred as '{outcome_activity}'")
    df = task31_outcome_dataframe(log, alignments,
                                  outcome_activity=outcome_activity)
    if df.empty:
        logger.warning("      Skipped Task 31: no trace-level outcome features found.")
        return
    table = task31_summary_table_dataframe(df)
    positive_rate = float(df["positive_outcome"].mean())
    logger.info(f"      -> Ends with '{outcome_activity}': {int(df['positive_outcome'].sum())}/{len(df)} ({positive_rate:.2%})")
    task31_table(table, output_dir)
    task31_bar_chart(df, output_dir)
    task31_stacked_bar(df, output_dir)
    task31_matrix(df, output_dir)
    task31_heatmap(df, output_dir)
