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

IDIOMS = ["bar_chart", "table", "pie_chart"]


def _param_spec():
    """The Violation-profile class's parameters, plus this task's own cut."""
    import violation_profile
    threshold = violation_profile.prominence_threshold_param(
        "Minimum share of all violations for a violation to count as "
        "'predominant' (%)",
        "The same cut task32 calls 'main', on the same number",
    )
    # Required, unlike everywhere else this parameter appears. It is the only
    # thing that separates this task from task11 and task29, and an empty field
    # used to be silently ignored — which produced task11's figures under
    # task36's question.
    threshold["required"] = True
    return [
        violation_profile.GROUPING_STRATEGY_PARAM,
        *violation_profile.SELECTION_PARAMS,
        threshold,
    ]


PARAM_SPEC = _param_spec()

import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

from shared import (
    save_svg, render_empty_state_svg, make_table, auto_col_widths,
    contrasting_text_color, CIVIDIS_R, GREY_LIGHT, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

#: One title over all three.
_TITLE = "Predominant Guideline Violations"

#: What everything under the cut is pooled into. One entry rather than a long
#: tail: the question is which violations dominate, and a figure that lists
#: twenty groups at half a percent each answers a different one. It is still
#: shown, because "everything else together is 8%" is part of the answer.
_OTHER = "All other violations"

#: The default when an admin's threshold does not reach the figures. It cannot
#: happen through the form any more (the parameter is required), only through a
#: direct call.
_DEFAULT_THRESHOLD = 5.0


def _label(group, series) -> str:
    """The row's name.

    Under the "activity" strategy `profile()` puts the activity in ``group``
    and the move type in ``series``, so an activity violated in both ways
    produces two rows with the same ``group``. Reading ``group`` alone would
    label them identically.
    """
    text = str(group)
    return f"{text} ({series})" if series not in (None, "", "None") else text


def _ranking(alignments, n_traces, strategy, selection, threshold):
    """[(label, count, pct, is_predominant)], largest share first.

    Every group at or above ``threshold`` percent of all violation occurrences
    in its own right; everything below pooled into one `_OTHER` entry, which
    carries the summed count and share and is never counted as predominant.
    """
    import violation_profile

    profile = violation_profile.profile(alignments, strategy,
                                        selection=selection, n_traces=n_traces)
    if profile.empty:
        return []

    profile = profile.sort_values("pct_count", ascending=False)
    rows, other_count, other_pct = [], 0, 0.0
    for _, row in profile.iterrows():
        if float(row["pct_count"]) >= threshold:
            rows.append((_label(row["group"], row["series"]),
                         int(row["count"]), float(row["pct_count"]), True))
        else:
            other_count += int(row["count"])
            other_pct += float(row["pct_count"])
    if other_count:
        rows.append((_OTHER, other_count, other_pct, False))
    return rows


def _colors(rows) -> list:
    """Cividis for the predominant groups, neutral for the pooled remainder.

    The remainder is not a violation group but a leftover, and giving it a
    shade from the same ramp would put it in the ranking it stands outside of.
    """
    predominant = [i for i, r in enumerate(rows) if r[3]]
    shades = {}
    for rank, i in enumerate(predominant):
        pos = 0.15 + 0.6 * rank / max(len(predominant) - 1, 1)
        shades[i] = to_hex(CIVIDIS_R(pos))
    return [shades.get(i, GREY_LIGHT) for i in range(len(rows))]


def _annot(count, pct) -> str:
    return f"{count:,} ({pct:.1f} %)"


def _empty(output_dir, idiom_key, message):
    render_empty_state_svg(os.path.join(output_dir, f"task36_{idiom_key}.svg"),
                           _TITLE, message)


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task36_bar_chart(rows, threshold, total, output_dir: str):
    """Groups ranked by occurrences, with the predominance cut drawn across.

    The cut is a line rather than a filter: a group just under it is part of
    the answer to "which are predominant" precisely by being just under it.
    """
    if not rows:
        _empty(output_dir, "bar_chart", "No violations found.")
        return

    labels = [r[0] for r in rows]
    counts = [r[1] for r in rows]
    colors = _colors(rows)
    y = np.arange(len(rows))
    xmax = max(counts)

    fig, ax = plt.subplots(figsize=(max(9.0, 5.0 + 0.085 * max(len(l) for l in labels)),
                                    max(3.4, len(rows) * 0.62 + 2.0)))
    ax.set_facecolor("#fafbfc")
    ax.barh(y, counts, 0.62, color=colors, edgecolor="white", linewidth=0.8)
    for yi, (_lbl, count, pct, _pre) in zip(y, rows):
        ax.text(count + xmax * 0.015, yi, _annot(count, pct), ha="left",
                va="center", fontsize=FONT_ANNOT, color=GREY_DARK)

    # The cut, in the axis's own unit: a share of all violation occurrences is
    # that share of the total count.
    cut = threshold / 100.0 * total
    if 0 < cut <= xmax * 1.05:
        ax.axvline(cut, color=GREY_DARK, linestyle="--", linewidth=1.2, zorder=3)
        ax.text(cut, len(rows) - 0.35, f"  Predominance cut: {threshold:g} %",
                rotation=90, va="top", ha="left", fontsize=FONT_ANNOT - 1,
                color=GREY_DARK)

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Violation occurrences", fontsize=FONT_LABEL)
    ax.set_xlim(0, xmax * 1.28)
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task36_bar_chart.svg"))


def task36_table(rows, threshold, total, output_dir: str):
    """The same numbers as text, with the verdict spelled out.

    The last column is what the bar chart draws as a line and the pie as
    colour: whether this group reaches the cut.
    """
    if not rows:
        _empty(output_dir, "table", "No violations found.")
        return

    cell_text = [[label, f"{count:,}", f"{pct:.1f} %",
                  "Yes" if predominant else "—"]
                 for label, count, pct, predominant in rows]
    col_labels = ["Violation", "Occurrences", "Share of all violations",
                  f"Predominant (≥ {threshold:g} %)"]

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig_w = max(9.0, 5.4 + 0.085 * max(len(r[0]) for r in rows))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.88],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=10.5,
        scale_xy=(1, 1.7),
        zebra=True,
    )
    ax.set_title(_TITLE, fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task36_table.svg"))


def task36_pie_chart(rows, threshold, total, output_dir: str):
    """Each group's share of all violations; the pooled remainder in neutral.

    "Predominant" is a share, and this is the idiom that encodes a share
    directly. Unlike task25, showing it is the point: this task presents the
    answer rather than having it derived.
    """
    if not rows:
        _empty(output_dir, "pie_chart", "No violations found.")
        return

    counts = [r[1] for r in rows]
    colors = _colors(rows)

    fig, ax = plt.subplots(figsize=(9.5, 6.5))
    wedges, _texts, autotexts = ax.pie(
        counts,
        colors=colors,
        startangle=90,
        autopct=lambda pct: f"{pct:.1f} %" if pct >= 4 else "",
        pctdistance=0.68,
        wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops=dict(fontsize=FONT_ANNOT),
    )
    for color, autotext in zip(colors, autotexts):
        autotext.set_color(contrasting_text_color(color))

    for wedge, (label, count, pct, _pre) in zip(wedges, rows):
        mid = np.deg2rad((wedge.theta1 + wedge.theta2) / 2.0)
        text = label if pct >= 4 else f"{label} — {_annot(count, pct)}"
        ax.annotate(text, xy=(np.cos(mid) * 0.85, np.sin(mid) * 0.85),
                    xytext=(np.cos(mid) * 1.18, np.sin(mid) * 1.18),
                    ha="left" if np.cos(mid) >= 0 else "right", va="center",
                    fontsize=FONT_ANNOT,
                    arrowprops=dict(arrowstyle="-", color="#999999", linewidth=0.8))

    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task36_pie_chart.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str, grouping_strategy: str = "move_type",
             selection=None, prominence_threshold: float = None, **kwargs):
    """Generate all Task 36 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 36 visualizations ---")

    if not alignments:
        logger.warning("      Skipped Task 36: no alignments provided.")
        for key in IDIOMS:
            _empty(output_dir, key, "No alignment data available.")
        return

    threshold = float(prominence_threshold) if prominence_threshold else _DEFAULT_THRESHOLD
    rows = _ranking(alignments, len(log) if log is not None else len(alignments),
                    grouping_strategy, selection, threshold)
    if not rows:
        logger.warning("      Skipped Task 36: no violations in the alignments.")
        for key in IDIOMS:
            _empty(output_dir, key, "No violations found.")
        return

    total = sum(count for _l, count, _p, _pre in rows)
    n_pre = sum(1 for r in rows if r[3])
    logger.info(f"      -> {len(rows)} row(s), {n_pre} predominant at "
                f"{threshold:g}% of {total:,} violation occurrences.")

    task36_bar_chart(rows, threshold, total, output_dir)
    task36_table(rows, threshold, total, output_dir)
    task36_pie_chart(rows, threshold, total, output_dir)
