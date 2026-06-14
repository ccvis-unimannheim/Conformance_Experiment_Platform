"""
tasks/task25.py – Task ID 25: Explore / Discover / Process conformance.

The analyst discovers the overall conformance degree themself from raw /
per-entity data. Core principle: NO aggregated conformance number appears in
any of this task's figures — no overall fitness, no percentage, no mean line,
no summary row. Reuses the centrally computed per-trace fitness.

Public API:
    generate(log, fitness_df, output_dir)
        log        – PM4Py EventLog
        fitness_df – per-trace fitness DataFrame from io_helpers.fitness_summary_dataframe
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["tile_metric", "bar_chart", "scatter_plot", "table",
          "flow_chart_elaborate", "flow_chart_table"]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 25 (AUTO): no hyperparameters — the analyst discovers the overall
# conformance degree from the visualisation. GT is the same scalar fitness
# as task06 (mean per-trace fitness × 100, rounded). count-set format
# additionally exposes the raw conformant / non-conformant trace counts.
# ---------------------------------------------------------------------------
GT_TIER = "AUTO"

PARAM_SPEC = []

ANSWER_FORMATS = [
    {"key": "pct",   "gt_shape": "scalar", "decisive_default": True},
    {"key": "count", "gt_shape": "scalar", "decisive_default": True},
]


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Overall log fitness (mean per-trace fitness × 100, rounded) for pct format;
    conformant trace count as a scalar for count format."""
    mean_fit = float(fitness_df["fitness"].mean()) if len(fitness_df) > 0 else 0.0
    pct = round(mean_fit * 100)

    if answer_format == "count":
        conform = int(fitness_df["is_fit"].sum())
        return {"value": str(conform)}

    # pct (default)
    return {"value": f"{pct}%"}


import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import (
    save_svg, make_table, render_counts_tile_metric,
    build_variant_df, variant_table_data, render_bpmn_annotated, render_empty_state_svg,
    GREY_MED, GREY_LIGHT, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

# Discovery-diff machinery is reused from task24.
try:
    from tasks.task24 import _compute_diff as _task24_compute_diff
except ImportError:  # when imported from inside the scripts/ dir
    from task24 import _compute_diff as _task24_compute_diff

TOP_N = 15


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task25_tile_metric(df, output_dir: str):
    """Tile Metric (discovery variant): raw counts only — no ratio, no percentage."""
    conform = int(df["is_fit"].sum())
    non_conform = len(df) - conform
    render_counts_tile_metric(
        conform, non_conform,
        os.path.join(output_dir, "task25_tile_metric.svg"),
    )


def task25_bar_chart(df, output_dir: str):
    """Exactly two bars: conformant vs non-conformant trace counts, counts as labels."""
    conform = int(df["is_fit"].sum())
    non_conform = len(df) - conform
    ymax = max(conform, non_conform, 1)

    fig, ax = plt.subplots(figsize=(6, 5))
    bars = ax.bar(
        ["Conformant Traces", "Non-conformant Traces"],
        [conform, non_conform],
        color=[GREY_MED, GREY_LIGHT], edgecolor="white", width=0.5,
    )
    for bar, val in zip(bars, [conform, non_conform]):
        ax.text(
            bar.get_x() + bar.get_width() / 2,
            bar.get_height() + ymax * 0.015,
            str(val), ha="center", va="bottom", fontsize=FONT_ANNOT,
        )
    ax.set_ylabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Conformant vs. Non-conformant Traces", fontsize=FONT_TITLE)
    ax.set_ylim(0, ymax * 1.15)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_bar_chart.svg"))


def task25_scatter_plot(df, output_dir: str):
    """One neutral-coloured dot per trace; x = chronological index, y = fitness.

    No mean/aggregate annotation (task06's scatter scaffolding minus its
    aggregate decorations and conformance colouring).
    """
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.scatter(df["trace_index"], df["fitness"], c=GREY_MED, s=15, alpha=0.6, linewidths=0)
    ax.set_xlabel("Traces in Log ordered by time", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (0–1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.1)
    ax.set_title("Fitness per Trace", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_scatter_plot.svg"))


def task25_table(vdf, output_dir: str):
    """Per-variant table: Rank | #Traces | Coverage % | Fitness — no summary row."""
    cell_text, col_labels, col_widths = variant_table_data(
        vdf, TOP_N, rank_header="Rank",
    )
    fig_h = max(3.5, 1.3 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(9, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.92],
        col_widths=col_widths,
        font_size=10.5,
        scale_xy=(1, 1.75),
        cell_pad=0.11,
    )
    ax.set_title(
        f"Top-{len(cell_text)} Process Variants by Frequency (of {len(vdf)} total)",
        fontsize=FONT_TITLE, pad=3,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_table.svg"))


# ---------------------------------------------------------------------------
# Flow-chart idioms (model annotated with aggregated deviations; NO fitness number)
# Reuses task24's discovery diff + shared.render_bpmn_annotated.
# ---------------------------------------------------------------------------

def _task25_diff_styles(diff):
    """Return (node_style_fn, faded_flow_fn) marking discovery deviations."""
    elements    = diff["elements"];   name_to_ids = diff["name_to_ids"]
    seq_flows   = diff["sequence_flows"]
    missing     = diff["missing_activities"]
    obs_not     = diff["observed_not_in_model"]

    missing_ids = {eid for n in missing for eid in name_to_ids.get(n, [])}
    viol_eps    = {a for (a, b) in obs_not} | {b for (a, b) in obs_not}
    viol_ids    = {eid for n in viol_eps for eid in name_to_ids.get(n, [])}

    def _node_style(eid, elem):
        if eid in missing_ids:
            return ("#EBEBEB", "#BBBBBB", 2, "#AAAAAA")
        if eid in viol_ids:
            return ("white", "#444444", 3, "#333333")
        return ("white", "#888888", 2, "#333333")

    def _faded(flow_id):
        sf = seq_flows.get(flow_id)
        if not sf:
            return False
        for role in ("source", "target"):
            e = elements.get(sf[role], {})
            if e.get("kind") == "task" and e.get("name", "") in missing:
                return True
        return False

    return _node_style, _faded


def task25_flow_chart_elaborate(diff, output_dir):
    """Desired model annotated with aggregated deviation marks — no fitness number."""
    node_style, faded = _task25_diff_styles(diff)
    render_bpmn_annotated(
        diff,
        os.path.join(output_dir, "task25_flow_chart_elaborate.svg"),
        title="Process Model — Observed Deviations",
        summary="Faded = model activity never observed; dark border = endpoint of a "
                "transition observed but not in the model.",
        node_style_fn=node_style,
        faded_flow_fn=faded,
        legend_items=[
            ("white",   "#888888", 2, "Conform (in model and observed)"),
            ("#EBEBEB", "#BBBBBB", 2, "In model, not observed"),
            ("white",   "#444444", 3, "Endpoint of observed-not-in-model transition"),
        ],
    )


def task25_flow_chart_table(diff, output_dir):
    """Per-activity deviation table (raw counts; NO total/percentage row)."""
    dfg = diff["dfg_counts"]
    extra   = diff["extra_activities"]
    missing = diff["missing_activities"]
    obs_not = diff["observed_not_in_model"]

    acc = {}  # activity -> {"types": set, "freq": int, "has_freq": bool}
    def _bump(act, kind, freq=None):
        cell = acc.setdefault(act, {"types": set(), "freq": 0, "has_freq": False})
        cell["types"].add(kind)
        if freq is not None:
            cell["freq"] += freq
            cell["has_freq"] = True

    for act in extra:
        f = sum(c for (a, b), c in dfg.items() if act in (a, b))
        _bump(act, "Extra (log only)", f)
    for act in missing:
        _bump(act, "Missing (model only)")
    for (a, b) in obs_not:
        c = dfg.get((a, b), 0)
        _bump(a, "Unexpected transition", c)
        _bump(b, "Unexpected transition", c)

    rows = [[act, ", ".join(sorted(cell["types"])),
             str(cell["freq"]) if cell["has_freq"] else "—"]
            for act, cell in sorted(acc.items())]
    if not rows:
        rows = [["(No structural deviations detected)", "—", "—"]]

    fig_h = max(3.0, 1.3 + len(rows) * 0.42)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=rows,
        col_labels=["Activity", "Deviation type", "Observed frequency"],
        bbox=[0.02, 0.05, 0.96, 0.86],
        col_widths=[0.40, 0.40, 0.20],
        font_size=10,
        scale_xy=(1, 1.7),
        cell_pad=0.10,
    )
    # Deliberately NO total/percentage row — the overall degree must stay
    # underivable-at-a-glance (discovery principle).
    ax.set_title("Per-Activity Deviations from the Desired Model", fontsize=FONT_TITLE, pad=4)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_flow_chart_table.svg"))


# ---------------------------------------------------------------------------
# Self-check: no aggregate conformance number may appear in any figure
# ---------------------------------------------------------------------------

def _task25_self_check(df, output_dir: str):
    """Assert none of the rendered SVGs contains an overall fitness annotation."""
    mean_fitness = float(df["fitness"].mean())
    forbidden = {
        f"{mean_fitness * 100:.2f}%",   # tile / table style aggregate
        f"{mean_fitness:.2%}",          # heatmap style aggregate
        "Average", "Overall", "Mean fitness", "Conformance Rate",
    }
    for fname in [f"task25_{idiom}.svg" for idiom in IDIOMS]:
        path = os.path.join(output_dir, fname)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as f:
            content = f.read()
        for token in forbidden:
            assert token not in content, (
                f"task25 self-check failed: aggregate annotation {token!r} found in {fname}"
            )
    logger.info("      task25 self-check passed: no aggregate annotation in any SVG.")


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, fitness_df, output_dir: str, model_path: str = None):
    """Generate all Task ID 25 SVGs into output_dir.

    model_path is required for the flow-chart idioms (model annotated with
    aggregated deviations); when absent those two idioms are skipped.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 25 visualizations ---")

    if fitness_df is None or fitness_df.empty:
        logger.warning("      Skipped Task 25: empty fitness DataFrame.")
        return

    conform = int(fitness_df["is_fit"].sum())
    non_conform = len(fitness_df) - conform
    if conform == 0:
        logger.warning("      task25: no conformant traces in the log.")
    if non_conform == 0:
        logger.warning("      task25: all traces are conformant.")

    vdf = build_variant_df(log, fitness_df, warn_prefix="task25")

    task25_tile_metric(fitness_df, output_dir)
    task25_bar_chart(fitness_df, output_dir)
    task25_scatter_plot(fitness_df, output_dir)
    if vdf.empty:
        logger.warning("      task25: no variant data — table skipped.")
    else:
        task25_table(vdf, output_dir)

    if model_path:
        try:
            # Compute the discovery diff once (silently — task24 logs its own
            # summary under its own section) and reuse it for both idioms.
            diff = _task24_compute_diff(log, model_path, log_summary=False)
            task25_flow_chart_elaborate(diff, output_dir)
            task25_flow_chart_table(diff, output_dir)
        except Exception as e:
            logger.warning(f"      task25: flow-chart idioms skipped ({e}).")
    else:
        logger.warning("      task25: no model_path — flow-chart idioms skipped.")

    _task25_self_check(fitness_df, output_dir)
