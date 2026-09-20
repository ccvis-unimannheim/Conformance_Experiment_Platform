"""
tasks/task36.py – Task 36: Present · Present · Process conformance per rule

Question: Which guideline violations are predominant in my process?

**The question lost its addendum, and the task is built on what remains.** It
used to continue "based on concrete guidelines (e.g. LTL-formulas), compute the
average conformance per guideline and present them in conjunction (e.g. as a
coloured declarative process model)". The declarative half had already been
abandoned in the code: `_extract_data` read `violation_profile.profile()` like
its siblings, and the two idioms that needed activity-pair constraints — the
heatmap and the network diagram — rendered a byte-identical empty state on
every run. task36 had one working idiom.

**What now makes this task its own.** task11 (Describe · Summarize), task29
(Explore · Summarize) and task32 (Present · Compare) read the same violation
profile. task32 separates itself with a sub-log axis; without its addendum
task36 has only the word *predominant* — which is not another number but a
threshold on the same ones. So the threshold is the subject: every idiom ranks
the violation groups by their share of all violations, shows where
`prominence_threshold` cuts, and pools everything below it into one "all other
violations" entry. The reader is told which violations are predominant, which
is what Present · Present means.

Idioms:
  bar_chart  — groups ranked by occurrences, with the predominance cut drawn
  table      — the same numbers as text, with the cut stated above them

Neither idiom says which groups qualify. Both state where the cut falls and
leave the reading to the participant, which is the judgement the task is
asking for.

A pie chart was offered and is gone: the cut applies to each slice on its own,
and a circle has nowhere to put it — judging every slice's width against one
reference, spread around the whole circle, is the comparison pie charts are
worst at. It could show the shares but not the question asked about them.

Deliberately absent: matrix, heatmap, stacked bar and parallel sets. task11,
task29 and task32 already draw those over this same profile, and a fourth set
of them would be four tasks showing one payload four ways.

Public API:
    generate(log, alignments, output_dir, grouping_strategy="move_type",
             selection=None, prominence_threshold=None)
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table"]


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
    CIVIDIS_R, GREY_LIGHT, GREY_DARK,
    FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

#: One title over all three.
_TITLE = "Predominant Guideline Violations"

#: What everything not named in its own right is pooled into. One entry rather
#: than a long tail: the question is which violations dominate, and a figure
#: that lists twenty groups at half a percent each answers a different one. It
#: is still shown, because "everything else together is 8%" is part of the
#: answer — and because with it the shares add up to 100, which is what makes
#: the label true.
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
    """``([(label, count, pct, is_predominant)], total)``, largest share first.

    Every group at or above ``threshold`` percent of all violation occurrences
    is named in its own right; everything else is pooled into one `_OTHER`
    entry, which carries the summed count and share and is never predominant.

    **One denominator, and it is the whole log.** The profile is read
    *unselected*, so ``pct_count`` — whose denominator is every violation
    occurrence in the log, by design — is the share of a total the rows
    actually add up to. ``selection`` still decides which groups may be named;
    the ones it excludes go into `_OTHER` instead of vanishing.

    Reading the selected profile instead left the figures with two
    denominators: the shares were of the whole log while the rows covered only
    the selection, so a column of them summed to 62.9% on BPIC-style data, the
    pooled entry claimed to be "all other violations" while a third of them
    were unaccounted for, and the bar chart's cut — drawn at
    ``threshold/100 * sum(shown counts)`` — sat at two thirds of where the
    threshold had actually been applied.
    """
    import violation_profile

    profile = violation_profile.profile(alignments, strategy, n_traces=n_traces)
    if profile.empty:
        return [], 0

    total = int(profile["count"].sum())
    nameable = None
    if selection:
        chosen = violation_profile.profile(alignments, strategy,
                                           selection=selection, n_traces=n_traces)
        nameable = {(r["group"], r["series"]) for _, r in chosen.iterrows()}

    profile = profile.sort_values("pct_count", ascending=False)
    rows, other_count = [], 0
    for _, row in profile.iterrows():
        key = (row["group"], row["series"])
        if float(row["pct_count"]) >= threshold and (nameable is None or key in nameable):
            rows.append((_label(row["group"], row["series"]),
                         int(row["count"]), float(row["pct_count"]), True))
        else:
            other_count += int(row["count"])
    if other_count:
        rows.append((_OTHER, other_count,
                     other_count / total * 100 if total else 0.0, False))
    return rows, total


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
    x = np.arange(len(rows))
    ymax = max(counts)

    fig, ax = plt.subplots(figsize=(max(8.5, 1.4 * len(rows) + 2.4), 6.2))
    ax.set_facecolor("#fafbfc")
    ax.bar(x, counts, 0.62, color=colors, edgecolor="white", linewidth=0.8)
    for xi, (_lbl, count, pct, _pre) in zip(x, rows):
        ax.text(xi, count + ymax * 0.02, _annot(count, pct), ha="center",
                va="bottom", fontsize=FONT_ANNOT, color=GREY_DARK)

    # The cut, in the axis's own unit: a share of all violation occurrences is
    # that share of the total count.
    cut = threshold / 100.0 * total
    if 0 < cut <= ymax * 1.05:
        ax.axhline(cut, color=GREY_DARK, linestyle="--", linewidth=1.2, zorder=3)
        ax.text(len(rows) - 0.4, cut, f" Predominance cut: {threshold:g} %",
                va="bottom", ha="right", fontsize=FONT_ANNOT - 1, color=GREY_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONT_ANNOT, rotation=28, ha="right")
    ax.set_ylabel("Violation occurrences", fontsize=FONT_LABEL)
    ax.set_ylim(0, ymax * 1.16)
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task36_bar_chart.svg"))


def task36_table(rows, threshold, total, output_dir: str):
    """The same numbers as text, with the cut stated above them.

    **The verdict column is gone.** It read "Yes" or "—" per row, which is the
    judgement the task asks the participant to make — the table answered the
    question instead of posing it, while the bar chart beside it only drew the
    line and left the reading to them. The threshold is now a caption in the
    same words the bar chart's line carries, so both idioms state where the cut
    falls and neither applies it.
    """
    if not rows:
        _empty(output_dir, "table", "No violations found.")
        return

    cell_text = [[label, f"{count:,}", f"{pct:.1f} %"]
                 for label, count, pct, _predominant in rows]
    col_labels = ["Violation", "Occurrences", "Share of all violations"]

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
    ax.set_title(_TITLE, fontsize=FONT_TITLE, pad=24)
    ax.text(0.5, 0.955, f"Predominance cut: {threshold:g} % of all violation occurrences",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=FONT_ANNOT, color=GREY_DARK)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task36_table.svg"))


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
    rows, total = _ranking(alignments, len(log) if log is not None else len(alignments),
                           grouping_strategy, selection, threshold)
    if not rows:
        logger.warning("      Skipped Task 36: no violations in the alignments.")
        for key in IDIOMS:
            _empty(output_dir, key, "No violations found.")
        return

    n_pre = sum(1 for r in rows if r[3])
    logger.info(f"      -> {len(rows)} row(s), {n_pre} predominant at "
                f"{threshold:g}% of {total:,} violation occurrences.")

    task36_bar_chart(rows, threshold, total, output_dir)
    task36_table(rows, threshold, total, output_dir)
