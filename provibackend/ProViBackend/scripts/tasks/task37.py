"""
tasks/task37.py – Task 37: Present · Summarize · Process conformance

Question: How do fitness values of traces differ when applying two different
techniques to compute them?

**The second half of the question is gone.** It used to continue "What is the
overall trend of trace fitness?", which is a question about time, and the two
idioms that answered it — line graph and horizon chart — are not in IDIOMS.
The wording promised something no idiom offered.

**One payload, drawn four ways.** Every idiom reads the same table: how many
traces each technique puts in each fitness band. Two columns, one per
technique, and the question is read by comparing them.

  bar_chart   – one group per band, two bars in it: one technique each
  heatmap     – the same table as colour, band × technique
  matrix      – the same grid as numbers, no colour
  table       – the same table as numbers
  stacked_bar – one bar per technique, split into bands

Matrix and heatmap are the platform's two readings of one grid: the heatmap
carries the value as continuous colour and prints nothing, the matrix prints
the value and carries no colour (`draw_value_heatmap(annotate=True,
colorless=True)`). The matrix and the table hold the same numbers in the same
shape and differ in being a ruled grid or a row-per-band list, which is the
kind of difference in encoding this experiment exists to measure.

An earlier pass had them draw the *joint* distribution instead — band under
one technique × band under the other. It carries strictly more (which traces
the techniques disagree about), but on real logs the matrix is nearly diagonal,
so a bar chart of it is a field of empty slots with one tall bar, and the
comparison the question asks for is not visible as a comparison. Two bars side
by side is the question.

The four used to carry four different payloads: mean and median plus four
log-level scalars nobody else had; the joint distribution; 200 of the log's
13,087 traces one by one; and the two separate distributions. A participant's
answer depended on which idiom they drew, which is the one thing the
experiment must not vary.

**Colour.** Two techniques and n bands need two channels, so which one colour
carries depends on which the idiom puts on its axis: the bar chart and the
heatmap put the bands on an axis and distinguish the techniques by colour
(`PAIR_COLORS`, the platform's two-group pair — the heatmap by its count, as
a heatmap must); the stacked bar puts the techniques on the axis and the bands
in colour, because a stack is made of bands. The table is colourless. What no
longer happens is one idiom using colour for the technique while the next uses
the same two colours for something else.
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "heatmap", "matrix", "table", "stacked_bar"]

#: The bands the fitness axis is cut into — the heatmap's two axes, the stacked
#: bar's segments and the bucket bar chart. Same parameter as task10's, because
#: it is the same choice about the same number; the presets differ because the
#: two tasks read different parts of the range.
#:
#: **The two techniques are not a parameter.** The task's wording ("two
#: different techniques") suggests one, but only two techniques produce a
#: fitness *per trace*, which is what every idiom here plots: alignments and
#: token-based replay. pm4py's third, footprints, is log-level only
#: (`fitness_footprints` returns perc_fit_traces and log_fitness), and the
#: alignment variants — Dijkstra, A*, less-memory — are algorithms for the same
#: optimum and return the same numbers. A picker over a set with exactly one
#: legal pair decides nothing, so there is none.
PARAM_SPEC = [
    {
        "key": "conformance_bins",
        "label": "Fitness bands the comparison is read in",
        # The bands are printed on the axes → repeating them in the question
        # tells the participant nothing new.
        "hide_hint": True,
        "widget": "select-one",
        "options": [
            {"label": "Quarters (0–25 %, 25–50 %, 50–75 %, 75–100 %)",
             "value": "0.0,0.25,0.5,0.75,1.01"},
            {"label": "Fifths (0–20 %, 20–40 %, 40–60 %, 60–80 %, 80–100 %)",
             "value": "0.0,0.2,0.4,0.6,0.8,1.01"},
            {"label": "High-fitness focus (80–85 %, 85–90 %, 90–95 %, 95–<100 %, 100 %)",
             "value": "0.80,0.85,0.90,0.95,1.0,1.01"},
        ],
        "default": "0.0,0.25,0.5,0.75,1.01",
        "required": False,
    },
]


def _parse_bins(raw) -> list | None:
    """Comma-separated boundaries from the param string, or None."""
    if not raw:
        return None
    if isinstance(raw, (list, tuple)):
        try:
            return [float(x) for x in raw]
        except (TypeError, ValueError):
            return None
    try:
        return [float(x.strip()) for x in str(raw).split(",") if x.strip()]
    except (ValueError, TypeError):
        return None


def validate_params(log, params) -> list:
    raw = (params or {}).get("conformance_bins", "")
    if not raw:
        return []
    bins = _parse_bins(raw)
    if bins is None or len(bins) < 3:
        return ["Fitness bands need at least 3 comma-separated numbers (2 bands)."]
    if bins != sorted(bins) or len(set(bins)) != len(bins):
        return ["Fitness band boundaries must be in strictly ascending order."]
    if bins[0] < 0.0 or bins[-1] > 1.01:
        return ["Fitness band boundaries must lie between 0.0 and 1.01."]
    return []

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker

from matplotlib.colors import to_hex

from shared import (save_svg, draw_value_heatmap, make_table, contrasting_text_color,
                    GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER, CIVIDIS,
                    PAIR_COLORS, FONT_TITLE, FONT_LABEL, FONT_ANNOT)

# ── Cividis palette ───────────────────────────────────────────────────────────
_C_DARK = GREY_DARK
#: There is no per-technique colour. `_C_T1`/`_C_T2` gave the two techniques a
#: dark navy and an olive-grey, which is the same channel the bands use, so a
#: reader moving from the bar chart to the stacked bar met the same two
#: colours meaning two different things.

# Default fitness bands (4), overridden per experiment by `conformance_bins`.
_DEFAULT_EDGES = [0.0, 0.25, 0.5, 0.75, 1.01]
_BUCKETS       = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]
#: Dark → light across however many bands there are, so the ramp reads the same
#: at four bands as at five.
_BUCKET_RAMP   = [GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER]


def _bands_from_edges(edges):
    """(bands, labels, colors) from ascending boundaries.

    The last band is closed — a fitness of exactly 1.0 belongs in the top band
    rather than falling off the end — which is why the presets end at 1.01.
    """
    edges = list(edges or _DEFAULT_EDGES)
    if len(edges) < 3:
        edges = list(_DEFAULT_EDGES)
    bands = list(zip(edges, edges[1:]))
    labels = []
    for i, (lo, hi) in enumerate(bands):
        last = i == len(bands) - 1
        hi_shown = min(hi, 1.0)
        # A full 1.0 keeps its decimal — "[0.75, 1.0]" is how this axis has
        # always been labelled, and %g would print it as "1".
        def _fmt(v):
            return "1.0" if abs(v - 1.0) < 1e-9 else f"{v:g}"
        lo_text, hi_text = _fmt(lo), _fmt(hi_shown)
        # A band holding only perfectly fitting traces is that one value, not an
        # interval from it to itself ("[1.0, 1.0]").
        labels.append(hi_text if lo_text == hi_text
                      else f"[{lo_text}, {hi_text}{']' if last else ')'}")
    n = len(bands)
    if n <= len(_BUCKET_RAMP):
        colors = _BUCKET_RAMP[:n]
    else:
        # Snapping more bands onto four fixed greys gave two adjacent bands the
        # same colour; sampling the ramp's own colormap keeps them distinct.
        colors = [to_hex(CIVIDIS(0.12 + 0.76 * i / (n - 1))) for i in range(n)]
    return bands, labels, colors


def _bucket_idx(v: float, buckets=None) -> int:
    buckets = buckets or _BUCKETS
    for i, (lo, hi) in enumerate(buckets):
        if lo <= v < hi:
            return i
    return len(buckets) - 1


# ── Data extraction ────────────────────────────────────────────────────────

def _compute_tbr_fitness(log, model_path):
    """Token-based replay fitness per trace. Returns list[float] or None on failure."""
    try:
        import pm4py
        bpmn_graph = pm4py.read_bpmn(model_path)
        net, im, fm = pm4py.convert_to_petri_net(bpmn_graph)
        tbr = pm4py.conformance_diagnostics_token_based_replay(log, net, im, fm)
        return [float(r.get("trace_fitness", 0.0)) for r in tbr]
    except Exception as e:
        logger.warning(f"Task37: token-based replay failed ({e}); no comparison possible.")
        return None


def _marginal(t1, t2, buckets):
    """counts[i] = (traces in band i under T1, under T2).

    The one payload. Both techniques score the same traces, so the two columns
    have the same total and are directly comparable band by band.
    """
    nb = len(buckets)
    m = np.zeros((nb, 2), dtype=int)
    for v in t1:
        m[_bucket_idx(v, buckets), 0] += 1
    for v in t2:
        m[_bucket_idx(v, buckets), 1] += 1
    return m


def _extract_data(log, alignments, model_path=None, conformance_bins=None):
    """The band × technique table, or ``matrix=None`` when only one ran.

    The log-level scalars this used to gather — ``fitness_alignments`` and
    ``fitness_token_based_replay``, both cost-weighted — are gone with the box
    the bar chart printed them in. They were four numbers one idiom out of four
    carried, and ``fitness_alignments`` re-ran the whole alignment to get them.
    """
    n = len(alignments)
    buckets, bucket_labels, bucket_colors = _bands_from_edges(_parse_bins(conformance_bins))

    # T1: alignment-based, already computed upstream and cached.
    t1 = [float(aln.get("fitness", 0.0)) for aln in alignments]

    # T2: token-based replay. Needs the model; without it there is no second
    # technique and so no comparison to draw.
    t2 = None
    if model_path:
        t2 = _compute_tbr_fitness(log, model_path)
        if t2 is not None and len(t2) != n:
            logger.warning("Task37: TBR length mismatch — discarding T2.")
            t2 = None

    return {
        "n_traces":      n,
        "matrix":        _marginal(t1, t2, buckets) if t2 is not None else None,
        "buckets":       buckets,
        "bucket_labels": bucket_labels,
        "bucket_colors": bucket_colors,
        "t1_name":       "Alignment-based",
        "t2_name":       "Token-based Replay",
    }


def _save_empty(output_dir, filename, message="No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


def _no_data(output_dir, name, message="No alignment data available."):
    _save_empty(output_dir, f"task37_{name}.svg", message)


#: One title over all four, as the question is one question. Each idiom used to
#: name itself instead — "Fitness Comparison", "Fitness Bucket Agreement",
#: "Per-Trace Fitness Detail", "Fitness Bucket Distribution Comparison" — and
#: three of those named a payload the other three did not have.
_TITLE = "Trace Fitness per Band, by Technique"

#: Only ``matrix`` is ever missing, and always for the same reason.
_NO_T2 = ("Token-based replay needs a process model.\n"
          "Without it there is only one technique to show.")

#: Axis title for the bands, used wherever they sit on an axis.
_BAND_AXIS = "Fitness band"


def _tech_names(data):
    return [data["t1_name"], data["t2_name"]]


def _legend_patches(labels, colors):
    return [mpatches.Patch(color=c, label=l) for c, l in zip(colors, labels)]


# ── Idiom 1: Bar Chart ─────────────────────────────────────────────────────

def task37_bar_chart(data, output_dir):
    """One group per band, two bars in it: one technique each.

    The counts as length, side by side, which is the channel a reader compares
    most accurately — the heatmap's colour and the stacked bar's proportions
    say the same thing less precisely, and that difference in precision is the
    encoding the experiment is there to measure.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "bar_chart", _NO_T2)
        return

    labels = data["bucket_labels"]
    names = _tech_names(data)
    nb = len(labels)
    x = np.arange(nb)
    width = 0.36
    ymax = max(int(m.max()), 1)

    fig, ax = plt.subplots(figsize=(max(9.0, 2.1 * nb + 2.6), 6.0))
    ax.set_facecolor("#fafbfc")
    for k in (0, 1):
        ax.bar(x + (k - 0.5) * width, m[:, k], width * 0.92,
               color=PAIR_COLORS[k], edgecolor="white", linewidth=0.8,
               label=names[k])
        for xi, v in zip(x, m[:, k]):
            ax.text(xi + (k - 0.5) * width, v + ymax * 0.015, f"{int(v):,}",
                    ha="center", va="bottom", fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_xlabel(_BAND_AXIS, fontsize=FONT_LABEL)
    ax.set_ylabel("Traces", fontsize=FONT_LABEL)
    ax.set_ylim(0, ymax * 1.16)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(loc="upper right", fontsize=FONT_ANNOT, frameon=True, framealpha=0.9)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_bar_chart.svg"))


# ── Idiom 2: Heatmap ───────────────────────────────────────────────────────

def task37_heatmap(data, output_dir):
    """The same table as continuous colour, one column per technique.

    Drawn by shared.draw_value_heatmap, which is where the platform's heatmap
    rules live: the reversed ramp, so the busiest cell is the darkest one, and
    no per-cell numbers — a heatmap is the colour reading of a table and a
    matrix is the number reading of it. The colourbar carries the scale.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "heatmap", _NO_T2)
        return

    labels = data["bucket_labels"]
    names = _tech_names(data)

    fig, ax = plt.subplots(figsize=(7.6, max(4.4, 0.8 * len(labels) + 3.0)))
    draw_value_heatmap(
        fig, ax, m,
        row_labels=labels, col_labels=names,
        cbar_label="Traces",
        annotate=False,
        vmax=max(int(m.max()), 1),
    )
    ax.set_ylabel(_BAND_AXIS, fontsize=FONT_LABEL)
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_heatmap.svg"))


# ── Idiom 3: Matrix ────────────────────────────────────────────────────────

def task37_matrix(data, output_dir):
    """The same grid as numbers, with no colour.

    The platform's Matrix/Heatmap pair: same call, same grid, opposite
    channels. Without ``colorless`` a matrix is a heatmap that also prints its
    numbers, which encodes one variable twice and leaves the two idioms
    differing only in annotation.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "matrix", _NO_T2)
        return

    labels = data["bucket_labels"]
    names = _tech_names(data)

    fig, ax = plt.subplots(figsize=(7.2, max(3.6, 0.72 * len(labels) + 2.4)))
    draw_value_heatmap(
        fig, ax, m,
        row_labels=labels, col_labels=names,
        cell_fmt="{:,.0f}",
        annotate=True,
        colorless=True,
    )
    ax.set_ylabel(_BAND_AXIS, fontsize=FONT_LABEL)
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_matrix.svg"))


# ── Idiom 4: Table ─────────────────────────────────────────────────────────

def task37_table(data, output_dir):
    """The same table as numbers, one row per band.

    It used to list traces one by one — 200 of the log's 13,087, stratified
    by fitness level. That is both more than its siblings (which trace, by
    name) and less (a sample, where they describe the whole log), and the
    question is about the log.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "table", _NO_T2)
        return

    labels = data["bucket_labels"]
    names = _tech_names(data)

    # Counts alone. The share is the count over a total that is the same for
    # both columns and every band, so it ranked nothing the counts did not
    # already rank, and no other idiom printed it.
    col_labels = [_BAND_AXIS] + names
    cell_text = [[labels[i]] + [f"{int(m[i, k]):,}" for k in (0, 1)]
                 for i in range(len(labels))]

    fig_h = max(3.2, 1.5 + len(labels) * 0.52)
    fig, ax = plt.subplots(figsize=(10.0, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.04, 0.06, 0.92, 0.84],
        col_widths=[0.28, 0.36, 0.36],
        cell_loc="center",
        font_size=FONT_ANNOT,
        scale_xy=(1, 1.6),
        zebra=True,
    )
    ax.set_title(_TITLE, fontsize=FONT_TITLE, pad=20)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_table.svg"))


# ── Idiom 5: Stacked Bar ───────────────────────────────────────────────────

def task37_stacked_bar(data, output_dir):
    """One bar per technique, split into bands.

    Vertical, with the techniques on the x axis and the counts running up, so
    it reads the same way round as the bar chart beside it. It used to lie on
    its side with a row per band, which put the bands on the axis the bar chart
    uses for the same thing and the techniques nowhere.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "stacked_bar", _NO_T2)
        return

    labels = data["bucket_labels"]
    colors = data["bucket_colors"]
    names = _tech_names(data)
    x = np.arange(2)

    fig, ax = plt.subplots(figsize=(9.0, 6.4))
    ax.set_facecolor("#fafbfc")
    tallest = max(int(m.sum(axis=0).max()), 1)

    # A segment shorter than this cannot hold its own number.
    inside_min = tallest * 0.045

    bottom = np.zeros(2, dtype=float)
    outside = {0: [], 1: []}       # (mid, text) per bar, for the thin ones
    for i, (lbl, clr) in enumerate(zip(labels, colors)):
        vals = m[i].astype(float)
        ax.bar(x, vals, 0.46, bottom=bottom, color=clr, edgecolor="white",
               linewidth=1.0, label=lbl)
        for xi, (v, b) in enumerate(zip(vals, bottom)):
            if not v:
                continue
            if v >= inside_min:
                ax.text(xi, b + v / 2, f"{int(v):,}", ha="center", va="center",
                        fontsize=FONT_ANNOT, color=contrasting_text_color(clr))
            else:
                outside[xi].append((b + v / 2, f"{int(v):,}"))
        bottom += vals

    # The thin ones, written beside the bar with a leader. Their true mid-heights
    # can be closer together than the text is tall, so they are pushed apart
    # first — a number that has been nudged still points at its own segment.
    gap = tallest * 0.042
    for xi, items in outside.items():
        if not items:
            continue
        items.sort()
        placed = []
        for mid, text in items:
            y = mid if not placed else max(mid, placed[-1] + gap)
            placed.append(y)
        for (mid, text), y in zip(items, placed):
            ax.annotate(
                text, xy=(xi + 0.24, mid), xytext=(xi + 0.40, y),
                ha="left", va="center", fontsize=FONT_ANNOT, color=_C_DARK,
                arrowprops=dict(arrowstyle="-", color="#999999", linewidth=0.8,
                                shrinkA=0, shrinkB=2),
            )

    ax.set_xticks(x)
    ax.set_xticklabels(names, fontsize=FONT_ANNOT)
    ax.set_ylabel("Traces", fontsize=FONT_LABEL)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(handles=_legend_patches(labels, colors), title=_BAND_AXIS,
              loc="center left", bbox_to_anchor=(1.02, 0.5),
              fontsize=FONT_ANNOT, title_fontsize=FONT_ANNOT,
              frameon=True, framealpha=0.9)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_stacked_bar.svg"))


# ── Public entry point ─────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None, conformance_bins=None,
             **kwargs):
    """Generate all Task 37 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 37 visualizations (Present fitness technique comparison) ---")

    if not alignments:
        logger.warning("      Skipped Task 37: no alignments provided.")
        for name in IDIOMS:
            _no_data(output_dir, name)
        return

    data = _extract_data(log, alignments, model_path, conformance_bins)
    logger.info(f"      -> Fitness bands: {', '.join(data['bucket_labels'])}")
    m = data["matrix"]
    if m is None:
        logger.warning("      Task 37: no second technique — nothing to compare.")
    else:
        moved = int(np.abs(m[:, 0] - m[:, 1]).sum() // 2)
        logger.info(f"      -> {moved:,} of {data['n_traces']:,} traces sit in a "
                    f"different band under the two techniques.")

    task37_bar_chart(data, output_dir)
    task37_heatmap(data, output_dir)
    task37_matrix(data, output_dir)
    task37_table(data, output_dir)
    task37_stacked_bar(data, output_dir)
