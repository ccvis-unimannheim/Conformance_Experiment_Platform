"""
tasks/task37.py – Task 37: Present · Summarize · Process conformance

Question: How do fitness values of traces differ when applying two different
techniques to compute them?

**The second half of the question is gone.** It used to continue "What is the
overall trend of trace fitness?", which is a question about time, and the two
idioms that answered it — line graph and horizon chart — are not in IDIOMS.
The wording promised something no idiom offered.

**One payload, drawn four ways.** Every idiom reads the same table: how many
traces the alignment technique puts in band X while token-based replay puts
them in band Y. That joint distribution is the answer to "how do the values
differ" — it says not just that the two techniques spread the log
differently but which traces they disagree about, and each technique's own
distribution is the row or column sum, so nothing is lost by it.

  bar_chart   – grouped bars: one group per alignment band, one bar per replay band
  heatmap     – the same table as colour, alignment band × replay band
  table       – the same table as numbers
  stacked_bar – one row per alignment band, segments by replay band

The four used to carry four different payloads: mean and median plus four
log-level scalars nobody else had; the joint distribution; 200 of the log's
13,087 traces one by one; and the two separate distributions. A participant's
answer depended on which idiom they drew, which is the one thing the
experiment must not vary.

**Colour means the replay band, everywhere it means anything.** It used to
mean the technique in the bar chart, the band in the stacked bar, a count in
the heatmap and the sign of a delta in the table. The technique is now carried
by position alone — an axis or a row — in every idiom. The heatmap is the
documented exception: a heatmap encodes its value as continuous colour, which
is what makes it a heatmap rather than a matrix.
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "heatmap", "table", "stacked_bar"]

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
                    FONT_TITLE, FONT_LABEL, FONT_ANNOT)

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


def _joint(t1, t2, buckets):
    """counts[i][j] = traces in alignment band i and replay band j.

    The one payload. Its row sums are the alignment technique's own
    distribution and its column sums are the replay technique's, so an idiom
    drawing this draws both.
    """
    nb = len(buckets)
    m = np.zeros((nb, nb), dtype=int)
    for v1, v2 in zip(t1, t2):
        m[_bucket_idx(v1, buckets), _bucket_idx(v2, buckets)] += 1
    return m


def _extract_data(log, alignments, model_path=None, conformance_bins=None):
    """The joint band table, or ``matrix=None`` when only one technique ran.

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
        "matrix":        _joint(t1, t2, buckets) if t2 is not None else None,
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
_TITLE = "Trace Fitness Band by Technique"

#: Only ``matrix`` is ever missing, and always for the same reason.
_NO_T2 = ("Token-based replay needs a process model.\n"
          "Without it there is only one technique to show.")


def _axis_labels(data):
    return (f"{data['t1_name']} fitness band",
            f"{data['t2_name']} fitness band")


def _legend_patches(labels, colors):
    return [mpatches.Patch(color=c, label=l) for c, l in zip(colors, labels)]


# ── Idiom 1: Bar Chart ─────────────────────────────────────────────────────

def task37_bar_chart(data, output_dir):
    """One group per alignment band, one bar per replay band.

    The counts as length, which is the channel a reader compares most
    accurately — the heatmap's colour and the stacked bar's proportions say
    the same thing less precisely, and that difference in precision is the
    encoding the experiment is there to measure.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "bar_chart", _NO_T2)
        return

    labels = data["bucket_labels"]
    colors = data["bucket_colors"]
    nb = len(labels)
    x = np.arange(nb)
    width = 0.8 / nb
    ymax = max(int(m.max()), 1)

    fig, ax = plt.subplots(figsize=(max(9.0, 1.9 * nb + 2.6), 6.0))
    ax.set_facecolor("#fafbfc")
    for j in range(nb):
        vals = m[:, j]
        ax.bar(x + (j - (nb - 1) / 2) * width, vals, width * 0.92,
               color=colors[j], edgecolor="white", linewidth=0.8,
               label=labels[j])
        for xi, v in zip(x, vals):
            if v:
                ax.text(xi + (j - (nb - 1) / 2) * width, v + ymax * 0.015,
                        f"{int(v):,}", ha="center", va="bottom",
                        fontsize=FONT_ANNOT - 1, color=_C_DARK, rotation=90)

    xlabel, ylabel = _axis_labels(data)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_xlabel(xlabel, fontsize=FONT_LABEL)
    ax.set_ylabel("Traces", fontsize=FONT_LABEL)
    ax.set_ylim(0, ymax * 1.18)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{int(v):,}"))
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(title=ylabel, loc="upper right", fontsize=FONT_ANNOT,
              title_fontsize=FONT_ANNOT, frameon=True, framealpha=0.9)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_bar_chart.svg"))


# ── Idiom 2: Heatmap ───────────────────────────────────────────────────────

def task37_heatmap(data, output_dir):
    """The same table as continuous colour.

    Drawn by shared.draw_value_heatmap, which is where the platform's heatmap
    rules live: the reversed ramp, so the busiest cell is the darkest one, and
    no per-cell numbers — a heatmap is the colour reading of a table and a
    matrix is the number reading of it. The colourbar carries the scale.

    The boxed diagonal is gone. It marked the cells where the techniques agree,
    which is a reading of the table no other idiom was given, and the whole
    point of the row and column labels is that a participant can find those
    cells themselves.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "heatmap", _NO_T2)
        return

    labels = data["bucket_labels"]
    xlabel, ylabel = _axis_labels(data)

    fig, ax = plt.subplots(figsize=(max(8.0, 1.6 * len(labels) + 4.0), 7.0))
    draw_value_heatmap(
        fig, ax, m.T,
        row_labels=labels, col_labels=labels,
        xlabel=xlabel,
        cbar_label="Traces",
        annotate=False,
        vmax=max(int(m.max()), 1),
    )
    ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_heatmap.svg"))


# ── Idiom 3: Table ─────────────────────────────────────────────────────────

def task37_table(data, output_dir):
    """The same table as numbers, one row per alignment band.

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
    xlabel, ylabel = _axis_labels(data)
    nb = len(labels)

    col_labels = [xlabel] + labels
    cell_text = [[labels[i]] + [f"{int(m[i, j]):,}" for j in range(nb)]
                 for i in range(nb)]

    fig_w = max(9.0, 2.0 + 1.5 * (nb + 1))
    fig_h = max(3.4, 1.6 + nb * 0.52)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=cell_text,
        col_labels=col_labels,
        bbox=[0.03, 0.05, 0.94, 0.84],
        cell_loc="center",
        font_size=FONT_ANNOT,
        scale_xy=(1, 1.6),
        zebra=True,
    )
    ax.set_title(_TITLE, fontsize=FONT_TITLE, pad=24)
    ax.text(0.5, 0.95, f"Columns: {ylabel}", transform=ax.transAxes,
            ha="center", va="bottom", fontsize=FONT_ANNOT, color=_C_DARK)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_table.svg"))


# ── Idiom 4: Stacked Bar ───────────────────────────────────────────────────

def task37_stacked_bar(data, output_dir):
    """One row per alignment band, split into replay bands.

    Proportions within each row, which is the reading a stacked bar gives: of
    the traces the alignment technique put in this band, where did replay put
    them. The row's own size is printed beside it, because a proportion of an
    unknown total is not the payload the other three carry.
    """
    m = data.get("matrix")
    if m is None:
        _no_data(output_dir, "stacked_bar", _NO_T2)
        return

    labels = data["bucket_labels"]
    colors = data["bucket_colors"]
    xlabel, ylabel = _axis_labels(data)
    nb = len(labels)

    fig, ax = plt.subplots(figsize=(max(9.5, 1.4 * nb + 6.0), max(3.6, nb * 0.9 + 2.2)))
    ax.set_facecolor("#fafbfc")

    for i in range(nb):
        row_total = int(m[i].sum())
        left = 0.0
        for j in range(nb):
            if not row_total:
                continue
            frac = m[i, j] / row_total * 100
            if frac <= 0:
                continue
            ax.barh(i, frac, left=left, color=colors[j], edgecolor="white",
                    linewidth=1.0, height=0.55)
            if frac >= 7:
                ax.text(left + frac / 2, i, f"{frac:.0f} %", ha="center",
                        va="center", fontsize=FONT_ANNOT,
                        color=contrasting_text_color(colors[j]))
            left += frac
        ax.text(101, i, f"{row_total:,} traces", ha="left", va="center",
                fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, nb - 0.4)
    ax.invert_yaxis()
    ax.set_yticks(range(nb))
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_ylabel(xlabel, fontsize=FONT_LABEL)
    ax.set_xlabel("Share of the band's traces (%)", fontsize=FONT_LABEL)
    ax.set_title(_TITLE, fontsize=FONT_TITLE)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(handles=_legend_patches(labels, colors), title=ylabel,
              loc="lower center", bbox_to_anchor=(0.5, -0.32), ncol=min(nb, 5),
              fontsize=FONT_ANNOT, title_fontsize=FONT_ANNOT,
              frameon=True, framealpha=0.9)
    fig.tight_layout(pad=1.2)
    fig.subplots_adjust(right=0.86)
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
    if data["matrix"] is None:
        logger.warning("      Task 37: no second technique — nothing to compare.")
    else:
        agree = int(np.trace(data["matrix"]))
        logger.info(f"      -> {agree:,} of {data['n_traces']:,} traces in the same band "
                    f"under both techniques.")

    task37_bar_chart(data, output_dir)
    task37_heatmap(data, output_dir)
    task37_table(data, output_dir)
    task37_stacked_bar(data, output_dir)
