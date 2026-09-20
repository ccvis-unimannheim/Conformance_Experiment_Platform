"""
tasks/task25.py – Task ID 25: Explore / Discover / Process conformance.

The analyst works out the overall degree of conformance themself. Three
principles, in the order they constrain the design:

  * **Discovery, not description.** No aggregated conformance value is handed
    over — no mean fitness, no conformance rate, no summary row, no tile. The
    task's whole difference from task06 (which states the number) is that here
    it has to be derived.
  * **Per trace.** Fitness is defined per trace and the overall degree is the
    mean over traces, so a decomposition that adds back up to it has to be a
    decomposition by trace. Every idiom shows the distribution of per-trace
    fitness: which values occur in the log, and how many traces have each.
  * **Recoverable, not binned.** The values are the ones the alignments
    actually produced, never ranges or bands, so the mean can be reconstructed
    exactly from any of the four figures. On BPIC12-A the whole log takes five
    distinct fitness values, so this costs nothing in table length.

**This replaced a per-activity payload, and that mattered.** The task used to
annotate the guideline BPMN with per-activity replay counts. Pooling those
gives the share of replayed steps that were synchronous — an *event*-weighted
rate — while task06 states the mean of the per-trace fitness. On the
order-to-cash log the two were 93.7% and 95.3%: two tasks asking verbatim the
same question with two different right answers. Reading the same per-trace
fitness task06 reads removes that by construction, and
`io_helpers.fitness_summary_dataframe` builds its column from exactly the
`result["fitness"]` this module reads, so the two cannot drift apart.

**Why these two idioms.** Both hand the reader the counts to pool: the bar
chart as length from a common baseline, the table as text.

Deliberately absent: a heatmap (colour cannot be pooled back into a mean), a
box plot (median and quartiles are already aggregates, and the mean is not
derivable from them), a tile metric or gauge (they *are* the answer), a
scatter plot (one dot per trace shows the distribution's shape but no exact
count), and the annotated BPMN (a model's topology says where behaviour
deviates, not how much of it does).

A pie chart and a stacked bar were built and then taken out again. Both encode
the share of the whole, which is the quantity being asked for, and both read it
off an angle or a length rather than off a number — which is a reasonable
thing to measure, but not in a task whose premise is that the degree has to be
*derived* rather than seen.

Reuses the centrally computed alignments; nothing is re-run here.

Public API:
    generate(log, alignments, output_dir)
        log        – PM4Py EventLog (unused; kept for the calling convention)
        alignments – raw alignment results from io_helpers.run_alignments
        output_dir – directory where SVGs are written
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "table"]


PARAM_SPEC = []


import os

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import to_hex

from shared import (
    save_svg, make_table, auto_col_widths, render_empty_state_svg,
    CIVIDIS_R,
    GREY_DARK, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
)

#: One title over all four. It names what the figures show — the traces and how
#: they scored — and not what the reader is to conclude from them.
_TITLE = "How the Log's Traces Scored Against the Guideline"

#: Fitness printed to three decimals. Display only: the alignments produce
#: values like 9/11, and three decimals keep the mean recoverable to better
#: than a thousandth, which no reader of these figures needs to beat.
_VALUE_FMT = "{:.3f}"

def _fitness_distribution(alignments) -> list:
    """[(fitness, trace count)], best fitness first.

    The exact values the alignments produced, not bins. ``result["fitness"]``
    is the same field `io_helpers.fitness_summary_dataframe` puts in the
    `fitness` column, so this is task06's number taken apart rather than a
    second measurement of the same thing.
    """
    counts: dict = {}
    for result in alignments or []:
        value = result.get("fitness")
        if value is None:
            continue
        key = round(float(value), 6)
        counts[key] = counts.get(key, 0) + 1
    return sorted(counts.items(), key=lambda pair: -pair[0])


def _labels(distribution) -> list:
    return [_VALUE_FMT.format(value) for value, _count in distribution]


def _colors(distribution) -> list:
    """One cividis shade per fitness value, the best fitness lightest.

    Ordered, because the categories are: these are points on a scale, and a
    palette that ran through unrelated hues would deny that.
    """
    n = max(len(distribution), 1)
    return [to_hex(CIVIDIS_R(0.12 + 0.72 * i / max(n - 1, 1))) for i in range(n)]


def _empty(output_dir, idiom_key):
    render_empty_state_svg(os.path.join(output_dir, f"task25_{idiom_key}.svg"),
                           _TITLE, "No alignment data available.")


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------

def task25_bar_chart(distribution, output_dir: str):
    """One bar per fitness value, height = how many traces reached it."""
    if not distribution:
        _empty(output_dir, "bar_chart")
        return

    labels = _labels(distribution)
    counts = [count for _value, count in distribution]
    colors = _colors(distribution)
    x = np.arange(len(labels))
    ymax = max(counts)

    fig, ax = plt.subplots(figsize=(max(7.0, len(labels) * 1.3 + 3.0), 5.4))
    ax.set_facecolor("#fafbfc")
    ax.bar(x, counts, 0.62, color=colors, edgecolor="white", linewidth=0.8)
    for xi, count in zip(x, counts):
        ax.text(xi, count + ymax * 0.015, f"{count:,}", ha="center", va="bottom",
                fontsize=FONT_ANNOT, color=GREY_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_xlabel("Trace fitness", fontsize=FONT_LABEL)
    ax.set_ylabel("Traces", fontsize=FONT_LABEL)
    ax.set_ylim(0, ymax * 1.14)
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_bar_chart.svg"))


def task25_table(distribution, output_dir: str):
    """The same two numbers per row, as text.

    No total row and no share column. A total invites subtraction towards the
    answer and a share is one division away from it; the counts are what the
    bar chart beside it carries, and the table carries what it carries.
    """
    if not distribution:
        _empty(output_dir, "table")
        return

    cell_text = [[_VALUE_FMT.format(value), f"{count:,}"]
                 for value, count in distribution]
    col_labels = ["Trace fitness", "Traces"]

    fig_h = max(3.0, 1.2 + len(cell_text) * 0.46)
    fig, ax = plt.subplots(figsize=(7.0, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.06, 0.05, 0.88, 0.88],
        col_widths=auto_col_widths(col_labels, cell_text),
        font_size=10.5,
        scale_xy=(1, 1.7),
        zebra=True,
    )
    ax.set_title(_TITLE, fontsize=FONT_TITLE, pad=12)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task25_table.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str):
    """Generate all Task 25 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 25 visualizations ---")

    distribution = _fitness_distribution(alignments)
    if not distribution:
        logger.warning("      Skipped Task 25: no alignment data.")
    else:
        traces = sum(count for _value, count in distribution)
        mean = sum(value * count for value, count in distribution) / traces
        # The mean is logged for whoever sets the answer key, and appears on no
        # figure: stating it is what task06 does and what this task must not.
        logger.info(f"      -> {traces:,} traces over {len(distribution)} distinct "
                    f"fitness value(s); derivable mean {mean:.4f}.")

    task25_bar_chart(distribution, output_dir)
    task25_table(distribution, output_dir)
