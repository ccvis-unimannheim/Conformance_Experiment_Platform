"""
tasks/task36.py – Task 36: Present · Present · Process conformance per rule

Question: Which concrete violations of guidelines are predominant in my process?
  Based on declarative guidelines (Declare model), compute per-rule conformance
  and present as a colored process network.

Visualizations:
  bar_chart       – rules ranked by conformance rate (horizontal bars)

The heatmap and the network diagram are gone. Both drew activity-pair
constraints, and an alignment violation is not a pair, so both could only
render a line of text saying they await a redesign — on every log, by
construction, while still being offered to an admin as something to pick.
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart"]


def _param_spec():
    """The Violation-profile class's parameters, plus this task's own cut."""
    import violation_profile
    return [
        violation_profile.GROUPING_STRATEGY_PARAM,
        *violation_profile.SELECTION_PARAMS,
        violation_profile.prominence_threshold_param(
            "Minimum share of all violations for a violation to count as "
            "'predominant' (%)",
            "The same cut task32 calls 'main', on the same number",
        ),
    ]


PARAM_SPEC = _param_spec()

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings
warnings.filterwarnings("ignore")

from shared import (save_svg, render_empty_state_svg, FONT_TITLE, FONT_LABEL,
                    FONT_ANNOT, GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER)
from matplotlib.colors import to_hex

# ── Palette ──────────────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK
_C_MED    = GREY_MED
_C_LIGHT  = GREY_LIGHT
_C_XLIGHT = GREY_LIGHTER
_HDR_BG   = GREY_DARK

_TEMPLATE_PRIORITY = {
    "succession": 0, "chainsuccession": 1,
    "coexistence": 2, "response": 3, "altresponse": 4,
    "responded_existence": 5, "precedence": 6, "altprecedence": 7,
    "absence": 0, "exactly_one": 1, "init": 2, "existence": 3,
}

_TEMPLATE_LABELS = {
    "init":                "Init",
    "existence":           "Existence",
    "exactly_one":         "Exactly One",
    "absence":             "Absence",
    "responded_existence": "Resp. Existence",
    "response":            "Response",
    "altresponse":         "Alt. Response",
    "precedence":          "Precedence",
    "altprecedence":       "Alt. Precedence",
    "coexistence":         "Co-existence",
    "succession":          "Succession",
    "chainsuccession":     "Chain Succession",
}

_ALLOWED_TEMPLATES = {
    "init", "exactly_one", "absence",
    "response", "precedence", "coexistence", "succession",
}


def _conf_gray(rate: float) -> str:
    """Low conformance → dark, high → light (greyscale)."""
    v = int(0x2a + (0xe0 - 0x2a) * max(0.0, min(1.0, rate)))
    return f"#{v:02x}{v:02x}{v:02x}"


# ── Data extraction ───────────────────────────────────────────────────────────

def _extract_data(log, alignments=None, grouping_strategy: str = "pattern",
                  selection=None, prominence_threshold: float = None) -> dict:
    """Per-violation conformance rates, from the alignment.

    **This is a redefinition.** The task used to discover a Declare model and
    compute per-constraint conformance with pm4py — it took `alignments` and
    never read them. "Conformance per rule" was therefore a different kind of
    conformance from the one every other task in this study reports, and the
    two could disagree about the same log without either being wrong.

    A "rule" is now a violation group from the shared kernel, and its
    conformance rate is the share of traces that do **not** carry it. The
    predominant violations are the ones a `prominence_threshold` keeps — the
    same cut task32 calls "main", on the same number.

    The activity-pair data this used to carry alongside is gone with the two
    idioms that read it: an alignment violation is not a pair, so the heatmap
    and the network diagram could only ever say they awaited a redesign.
    """
    import violation_profile

    n_traces = len(log)
    empty = {"constraints": [], "n_traces": n_traces}
    if not alignments:
        logger.warning("Task36: no alignments provided.")
        return empty

    profile = violation_profile.profile(alignments, grouping_strategy,
                                        selection=selection, n_traces=n_traces)
    if profile.empty:
        return empty

    if prominence_threshold:
        kept = violation_profile.prominent(profile, prominence_threshold)
        if kept.empty:
            logger.warning(
                "Task36: no violation reaches %g%% of all occurrences — the "
                "predominance cut is ignored so the figures are not empty.",
                prominence_threshold)
        else:
            dropped = len(profile) - len(kept)
            profile = kept
            logger.info("Task36: %d below the %g%% predominance cut, %d kept.",
                        dropped, prominence_threshold, len(profile))

    constraints = []
    for _, row in profile.iterrows():
        label = str(row["group"])
        if row["series"]:
            label = f'{label} ({row["series"]})'
        conf_rate = 1.0 - (row["traces"] / n_traces if n_traces else 0.0)
        constraints.append({
            "label": label,
            "conf_rate": conf_rate,
            "violations": int(row["traces"]),
            "color": _conf_gray(conf_rate),
        })
    # Least conformant first: the question asks which violations are
    # predominant, so the worst rule leads.
    constraints.sort(key=lambda c: (c["conf_rate"], c["label"]))

    logger.info("Task36: %d violation group(s) over %d traces.",
                len(constraints), n_traces)
    return {"constraints": constraints, "n_traces": n_traces}


def task36_bar_chart(data: dict, output_dir: str):
    constraints = data["constraints"]
    if not constraints:
        logger.warning("Task36 bar_chart: no violations to rank.")
        render_empty_state_svg(
            os.path.join(output_dir, "task36_bar_chart.svg"),
            "Conformance per Rule", "No violations found in this log.")
        return

    items = constraints[:20]
    n = len(items)
    fig_h = max(6, n * 0.52 + 2.5)
    fig, ax = plt.subplots(figsize=(11, fig_h))

    labels = [c["label"] for c in items]
    rates  = [c["conf_rate"] for c in items]
    colors = [c["color"] for c in items]
    viols  = [c["violations"] for c in items]
    n_tr   = data["n_traces"]

    y_pos = np.arange(n)
    bars = ax.barh(y_pos, rates, color=colors, edgecolor="white",
                   linewidth=0.5, height=0.72)

    for i, (rate, bar, viol) in enumerate(zip(rates, bars, viols)):
        pct_txt = f"{rate:.1%}"
        x_text = min(rate + 0.012, 1.06)
        ax.text(x_text, bar.get_y() + bar.get_height() / 2,
                f"{pct_txt}  ({viol:,} violations)",
                va="center", ha="left", fontsize=7.5, color=_C_DARK)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, 1.38)
    ax.set_xlabel("Conformance Rate (fraction of traces satisfying rule)",
                  fontsize=FONT_LABEL)
    ax.set_title(
        "Per-Rule Conformance Rate  ·  Task 36\n"
        f"Declare model constraints, sorted by violation severity  (n = {n_tr:,} traces)",
        fontsize=FONT_TITLE, pad=10, loc="left",
    )

    # Reference lines
    ax.axvline(0.8, color=_C_LIGHT, linestyle="--", linewidth=0.9)
    ax.axvline(0.5, color=_C_LIGHT, linestyle=":",  linewidth=0.9)

    # Conformance bands legend
    legend_items = [
        mpatches.Patch(color=_conf_gray(0.95), label="High  ≥ 80%",      ec="#888"),
        mpatches.Patch(color=_conf_gray(0.65), label="Medium  50–80%",   ec="#888"),
        mpatches.Patch(color=_conf_gray(0.40), label="Low  30–50%",       ec="#888"),
        mpatches.Patch(color=_conf_gray(0.15), label="Very Low  < 30%",   ec="#888"),
    ]
    ax.legend(handles=legend_items,
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=4, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=1.2)

    path = os.path.join(output_dir, "task36_bar_chart.svg")
    save_svg(fig, path)
    logger.info(f"Task36: bar_chart saved → {path}")


# ── Idiom 2: Heatmap ──────────────────────────────────────────────────────────

def generate(log, alignments, output_dir: str, model_path: str = None,
             grouping_strategy: str = "pattern", selection=None,
             prominence_threshold: float = None):
    logger.info("\n--- Generating Task 36 visualizations (Declare constraint conformance) ---")
    logger.info("      Extracting Declare conformance data…")
    data = _extract_data(log, alignments, grouping_strategy, selection,
                         prominence_threshold)

    if not data["constraints"]:
        logger.warning("Task36: no violations found — emitting empty states.")
        for name in IDIOMS:
            render_empty_state_svg(
                os.path.join(output_dir, f"task36_{name}.svg"),
                "Conformance per Rule", "No violations found in this log.")
        return

    n = data["n_traces"]
    logger.info(f"Task36: {len(data['constraints'])} constraints, {n} traces")

    try:
        task36_bar_chart(data, output_dir)
    except Exception as e:
        logger.warning(f"Task36: bar_chart failed: {e}", exc_info=True)
