"""
tasks/task37.py – Task 37: Present · Summarize · Process conformance

Question: How do fitness values of traces differ when applying two different
techniques to compute them? What is the overall trend of trace fitness?

Visualizations (all SVG, cividis palette from shared.py):
  bar_chart   – mean/median comparison: T1 vs T2
  heatmap     – 2D density: T1 bucket × T2 bucket
  table       – per-trace detail: T1, T2, delta, classification
  stacked_bar – fitness bucket distribution: T1 row and T2 row
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

from shared import (save_svg, draw_value_heatmap, make_table, GREY_DARK, GREY_MED, GREY_LIGHT,
                    GREY_LIGHTER, CIVIDIS, FONT_TITLE, FONT_LABEL, FONT_ANNOT)

# ── Cividis palette ───────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK
_C_MED    = GREY_MED
_C_LIGHT  = GREY_LIGHT
_C_XLIGHT = GREY_LIGHTER
_C_T1     = GREY_DARK    # Alignment-based (dark navy)
_C_T2     = GREY_MED     # Token-based Replay (olive-grey)

# Default fitness bands (4), overridden per experiment by `conformance_bins`.
_DEFAULT_EDGES = [0.0, 0.25, 0.5, 0.75, 1.01]
_BUCKETS       = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]
_BUCKET_LABELS = ["[0, 0.25)", "[0.25, 0.5)", "[0.5, 0.75)", "[0.75, 1.0]"]
#: Dark → light across however many bands there are, so the ramp reads the same
#: at four bands as at five.
_BUCKET_RAMP   = [GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER]
_BUCKET_COLORS = list(_BUCKET_RAMP)


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


def _fitness_stats(vals, buckets_def=None):
    a = np.array(vals, dtype=float)
    buckets = [int(np.sum((a >= lo) & (a < hi))) for lo, hi in (buckets_def or _BUCKETS)]
    return {
        "mean":    float(np.mean(a)),
        "median":  float(np.median(a)),
        "std":     float(np.std(a)),
        "min":     float(np.min(a)),
        "max":     float(np.max(a)),
        "buckets": buckets,
    }


# ── Data extraction ───────────────────────────────────────────────────────────

def _compute_tbr_fitness(log, model_path):
    """Token-based replay fitness per trace. Returns list[float] or None on failure."""
    try:
        import pm4py
        bpmn_graph = pm4py.read_bpmn(model_path)
        net, im, fm = pm4py.convert_to_petri_net(bpmn_graph)
        tbr = pm4py.conformance_diagnostics_token_based_replay(log, net, im, fm)
        return [float(r.get("trace_fitness", 0.0)) for r in tbr]
    except Exception as e:
        logger.warning(f"Task37: token-based replay failed ({e}); single-technique mode.")
        return None


def _compute_log_fitness_tbr(log, model_path):
    """TBR log-level fitness via pm4py.fitness_token_based_replay(). Returns dict or None."""
    try:
        import pm4py
        bpmn_graph = pm4py.read_bpmn(model_path)
        net, im, fm = pm4py.convert_to_petri_net(bpmn_graph)
        return pm4py.fitness_token_based_replay(log, net, im, fm)
    except Exception as e:
        logger.warning(f"Task37: TBR log-fitness failed ({e}).")
        return None


def _compute_log_fitness_aln(log, model_path):
    """Alignment log-level fitness via pm4py.fitness_alignments(). Returns dict or None.

    pm4py.fitness_alignments() re-runs the alignment algorithm internally to
    compute the cost-weighted aggregate:
        log_fitness = 1 - sum(move_costs) / sum(worst_case_costs)
    This is different from mean(trace_fitness) because it weights by trace length.
    """
    try:
        import pm4py
        bpmn_graph = pm4py.read_bpmn(model_path)
        net, im, fm = pm4py.convert_to_petri_net(bpmn_graph)
        return pm4py.fitness_alignments(log, net, im, fm)
    except Exception as e:
        logger.warning(f"Task37: ALN log-fitness failed ({e}).")
        return None


def _extract_data(log, alignments, model_path=None, conformance_bins=None):
    n = len(alignments)
    buckets, bucket_labels, bucket_colors = _bands_from_edges(_parse_bins(conformance_bins))

    # T1: alignment-based (trace-level)
    t1 = [float(aln.get("fitness", 0.0)) for aln in alignments]

    # T2: token-based replay (trace-level, optional)
    t2 = None
    tbr_log = None
    aln_log = None
    if model_path:
        t2 = _compute_tbr_fitness(log, model_path)
        if t2 is not None and len(t2) != n:
            logger.warning("Task37: TBR length mismatch — discarding T2.")
            t2 = None
        if t2 is not None:
            tbr_log = _compute_log_fitness_tbr(log, model_path)
        # T1 log-level: pm4py.fitness_alignments() (cost-weighted, re-runs alignment)
        aln_log = _compute_log_fitness_aln(log, model_path)

    delta = [t1[i] - t2[i] for i in range(n)] if t2 is not None else None

    t1_perc_fit = sum(1 for f in t1 if f >= 1.0) / n * 100 if n > 0 else 0.0
    t2_perc_fit = (sum(1 for f in t2 if f >= 1.0) / n * 100
                   if t2 is not None and n > 0 else None)

    t1_log_fitness = aln_log.get("log_fitness") if aln_log else None
    t2_log_fitness = tbr_log.get("log_fitness") if tbr_log else None

    return {
        "n_traces":       n,
        "t1":             t1,
        "t2":             t2,
        "delta":          delta,
        "t1_stats":       _fitness_stats(t1, buckets),
        "t2_stats":       _fitness_stats(t2, buckets) if t2 is not None else None,
        "buckets":        buckets,
        "bucket_labels":  bucket_labels,
        "bucket_colors":  bucket_colors,
        "t1_name":        "Alignment-based",
        "t2_name":        "Token-based Replay",
        "t1_perc_fit":    t1_perc_fit,
        "t2_perc_fit":    t2_perc_fit,
        "t1_log_fitness": t1_log_fitness,   # ALN cost-weighted log fitness
        "t2_log_fitness": t2_log_fitness,   # TBR cost-weighted log fitness
    }


def _save_empty(output_dir, filename, message="No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


def _no_data(output_dir, name):
    _save_empty(output_dir, f"task37_{name}.svg", "No alignment data available.")


# ── Idiom 1: Bar Chart ────────────────────────────────────────────────────────

def task37_bar_chart(data, output_dir):
    """Trace-level and log-level fitness comparison: T1 vs T2.

    Three metric groups:
      Avg. Trace Fitness  – mean of individual trace fitness values (trace-level aggregate)
      Median Trace Fitness – median of individual trace fitness values
      % Fitting Traces    – proportion of traces with fitness = 1.0 (log-level, right y-axis)

    The distinction between trace-level (per-case) and log-level (whole-log)
    is central to conformance checking: a log can have a high average trace
    fitness while most traces have non-zero violations, or vice versa.
    """
    if data["n_traces"] == 0:
        _no_data(output_dir, "bar_chart"); return

    has_t2  = data["t2"] is not None
    t1_s    = data["t1_stats"]
    t2_s    = data["t2_stats"]

    # ── Left axis: trace-level metrics ───────────────────────────────────────
    metrics_left  = ["Avg. Trace\nFitness", "Median Trace\nFitness"]
    t1_left  = [t1_s["mean"], t1_s["median"]]
    t2_left  = [t2_s["mean"], t2_s["median"]] if has_t2 else None

    # ── Right axis: log-level % fitting traces ────────────────────────────────
    t1_pf = data.get("t1_perc_fit", 0.0)
    t2_pf = data.get("t2_perc_fit")

    x   = np.arange(len(metrics_left))
    w   = 0.35 if has_t2 else 0.5

    fig, ax = plt.subplots(figsize=(11, 5))
    ax.set_facecolor("#fafbfc")

    # Trace-level bars
    bars1 = ax.bar(x - w / 2 if has_t2 else x, t1_left, width=w,
                   color=_C_T1, edgecolor="white", label=data["t1_name"])
    for b, v in zip(bars1, t1_left):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.012,
                f"{v:.3f}", ha="center", va="bottom",
                fontsize=FONT_ANNOT, color=_C_DARK)

    if has_t2:
        bars2 = ax.bar(x + w / 2, t2_left, width=w,
                       color=_C_T2, edgecolor="white", label=data["t2_name"])
        for b, v in zip(bars2, t2_left):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.012,
                    f"{v:.3f}", ha="center", va="bottom",
                    fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels(metrics_left, fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness (trace-level)", fontsize=FONT_LABEL)
    ax.set_ylim(0, 1.18)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)

    # Log-level annotation box
    t1_logf = data.get("t1_log_fitness")
    t2_logf = data.get("t2_log_fitness")
    pf_lines = ["Log-level metrics"]
    pf_lines.append(f"  % Fitting  {data['t1_name']}: {t1_pf:.1f}%")
    if has_t2 and t2_pf is not None:
        pf_lines.append(f"  % Fitting  {data['t2_name']}: {t2_pf:.1f}%")
    if t1_logf is not None:
        pf_lines.append(f"  Log fitness (ALN, cost-wtd): {t1_logf:.4f}")
    if has_t2 and t2_logf is not None:
        pf_lines.append(f"  Log fitness (TBR, cost-wtd): {t2_logf:.4f}")
    ax.set_title(
        f"Fitness Comparison  ·  {data['n_traces']:,} traces  "
        f"(bars = trace-level · box = log-level)",
        fontsize=FONT_TITLE,
    )
    if has_t2:
        ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.25),
                  ncol=2, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)

    # Log-level annotation placed below the x-axis to avoid overlapping bars
    fig.tight_layout(pad=1.2)
    fig.subplots_adjust(bottom=0.22)
    fig.text(0.5, 0.01, "   ".join(pf_lines),
             ha="center", va="bottom",
             fontsize=FONT_ANNOT, color=_C_DARK,
             bbox=dict(boxstyle="round,pad=0.5", fc="#f0f0f0", ec="#cccccc", lw=0.8))

    save_svg(fig, os.path.join(output_dir, "task37_bar_chart.svg"))


# ── Idiom 2: Box Plot ─────────────────────────────────────────────────────────

def task37_heatmap(data, output_dir):
    """2D heatmap: T1 fitness bucket (rows) × T2 fitness bucket (cols).
    Diagonal cells = techniques agree on the bucket."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "heatmap"); return
    if data["t2"] is None:
        _save_empty(output_dir, "task37_heatmap.svg",
                    "Heatmap requires two techniques.\n"
                    "Token-based replay not available (no model path).")
        return

    t1 = data["t1"]
    t2 = data["t2"]
    n  = data["n_traces"]
    nb = len(data.get("buckets") or _BUCKETS)

    mat = np.zeros((nb, nb), dtype=int)
    for v1, v2 in zip(t1, t2):
        mat[_bucket_idx(v1, data.get("buckets")), _bucket_idx(v2, data.get("buckets"))] += 1

    labels = data.get("bucket_labels") or _BUCKET_LABELS
    fig, ax = plt.subplots(figsize=(9, 7.5))
    # shared.draw_value_heatmap, which is where the platform's heatmap rules
    # live: the reversed ramp, so the busiest cell is the darkest one rather
    # than the one yellow square in a navy field this drew before; and no
    # per-cell numbers, because a heatmap is the colour reading of a table and
    # a matrix is the number reading of it. The colourbar carries the scale.
    draw_value_heatmap(
        fig, ax, mat,
        row_labels=labels, col_labels=labels,
        xlabel=f"{data['t1_name']} fitness bucket",
        cbar_label="Traces",
        annotate=False,
        vmax=max(int(mat.max()), 1),
    )

    # Highlight diagonal (agreement)
    for k in range(nb):
        ax.add_patch(plt.Rectangle(
            (k - 0.5, k - 0.5), 1, 1,
            fill=False, edgecolor=_C_MED, linewidth=2.0,
        ))

    ax.set_ylabel(f"{data['t2_name']} fitness bucket", fontsize=FONT_LABEL)
    ax.set_title(
        f"Fitness Bucket Agreement  ·  {n:,} traces\n"
        f"Boxed diagonal = techniques agree on bucket",
        fontsize=FONT_TITLE,
    )

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_heatmap.svg"))


# ── Idiom 5: Table (per-trace detail) ────────────────────────────────────────

def task37_table(data, output_dir):
    """Per-trace detail table: Trace # | T1 | T2 | Δ | Classification.

    Directly supports "inspect differences in the trace fitness values":
    each row = one trace, showing T1 and T2 fitness side-by-side so the
    reader can identify individual traces where the two techniques disagree.
    Sorted by |Δ| descending so the largest disagreements appear first.
    Capped at 50 rows for readability.
    """
    if data["n_traces"] == 0:
        _no_data(output_dir, "table"); return

    t1     = data["t1"]
    t2     = data["t2"]
    has_t2 = t2 is not None
    n      = data["n_traces"]
    MAX    = 50

    def classify(v):
        if v >= 0.75: return "High"
        if v >= 0.5:  return "Medium"
        if v >= 0.25: return "Low"
        return "Very Low"

    # Stratified sampling: group traces by unique (T1_rounded, T2_rounded) pair,
    # then round-robin across groups so all fitness levels are represented.
    # Within each group, sort by |Δ| desc to surface the most interesting traces.
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for i in range(n):
        key = (round(t1[i], 3), round(t2[i], 3) if has_t2 else None)
        groups[key].append(i)

    # Sort groups: most disagreement first, then by T1 ascending
    def _group_sort_key(k):
        delta = abs(k[0] - k[1]) if k[1] is not None else 0.0
        return (-delta, k[0])

    group_keys = sorted(groups.keys(), key=_group_sort_key)
    n_groups   = len(group_keys)
    per_group  = max(1, MAX // n_groups)

    # Round-robin: take `per_group` traces from each group
    order = []
    for key in group_keys:
        members = sorted(groups[key],
                         key=lambda i: abs(t1[i] - (t2[i] if has_t2 else t1[i])),
                         reverse=True)
        order.extend(members[:per_group])

    # Fill remaining slots in |Δ| desc order (no duplicates)
    if len(order) < MAX:
        shown = set(order)
        remaining = sorted(
            (i for i in range(n) if i not in shown),
            key=lambda i: abs(t1[i] - (t2[i] if has_t2 else t1[i])),
            reverse=True,
        )
        order.extend(remaining[: MAX - len(order)])

    order = order[:MAX]

    rows = []
    for i in order:
        row = [str(i + 1), f"{t1[i]:.3f}"]
        if has_t2:
            delta = t1[i] - t2[i]
            row += [f"{t2[i]:.3f}", f"{delta:+.3f}"]
        row.append(classify(t1[i]))
        rows.append(row)

    if has_t2:
        col_headers = ["Trace #", data["t1_name"], data["t2_name"], "Δ (T1−T2)", "Fitness Level (T1)"]
        col_widths  = [0.10, 0.19, 0.19, 0.16, 0.36]
    else:
        col_headers = ["Trace #", data["t1_name"], "Fitness Level"]
        col_widths  = [0.12, 0.28, 0.60]

    n_rows = len(rows)
    fig_h  = max(4.0, n_rows * 0.42 + 1.8)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")
    # shared.make_table, as every other table in the platform. Drawn by hand
    # this had its own zebra stripe (#f5f5f5 against the shared #F0F0F0), its
    # own cell borders and its own row height, so the one idiom a participant
    # is meant to recognise across tasks looked slightly different here.
    tbl = make_table(ax, cell_text=rows, col_labels=col_headers,
                     bbox=[0.015, 0.04, 0.97, 0.90], col_widths=col_widths,
                     cell_loc="center", font_size=FONT_ANNOT, cell_pad=0.06)

    # The delta column keeps the reading it had: dark where the first technique
    # scores higher, grey where the second does.
    if has_t2:
        for r, row in enumerate(rows, start=1):
            try:
                tbl[r, 3].set_text_props(
                    color=_C_DARK if float(row[3]) >= 0 else _C_MED)
            except (ValueError, KeyError):
                pass

    sort_note = f"stratified by fitness level  ·  {n_groups} unique value groups"
    title = f"Per-Trace Fitness Detail  ·  {n:,} traces  ·  {sort_note}"
    if n > MAX:
        title += f"  ({MAX} shown)"
    ax.set_title(title, fontsize=FONT_TITLE, pad=14)
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_table.svg"))


# ── Idiom 9: Stacked Bar ──────────────────────────────────────────────────────

def task37_stacked_bar(data, output_dir):
    """100% stacked bars: one row per technique, 4 fitness buckets each."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "stacked_bar"); return

    has_t2 = data["t2"] is not None
    n      = data["n_traces"]
    rows   = [(data["t1_name"], data["t1_stats"])]
    if has_t2:
        rows.append((data["t2_name"], data["t2_stats"]))

    nb = len(data.get("buckets") or _BUCKETS)

    fig, ax = plt.subplots(figsize=(13, 2.8 + 1.2 * len(rows)))
    ax.set_facecolor("#fafbfc")

    patches = [mpatches.Patch(color=c, label=l)
               for c, l in zip(data.get("bucket_colors") or _BUCKET_COLORS,
                               data.get("bucket_labels") or _BUCKET_LABELS)]

    for y_pos, (label, stats) in enumerate(rows):
        left = 0.0
        for bi in range(nb):
            frac = stats["buckets"][bi] / n * 100
            cnt  = stats["buckets"][bi]
            clr  = (data.get("bucket_colors") or _BUCKET_COLORS)[bi]
            ax.barh(y_pos, frac, left=left, color=clr,
                    edgecolor="white", linewidth=1.0, height=0.5)
            if frac > 5:
                txt_clr = "white" if int(clr[1:3], 16) < 150 else _C_DARK
                ax.text(left + frac / 2, y_pos,
                        f"{frac:.1f}%\n({cnt:,})",
                        ha="center", va="center",
                        fontsize=FONT_ANNOT, color=txt_clr, linespacing=1.4)
            left += frac

    ax.set_xlim(0, 100)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows], fontsize=FONT_LABEL)
    ax.set_xlabel("Proportion of traces (%)", fontsize=FONT_LABEL)
    ax.set_title(
        f"Fitness Bucket Distribution Comparison  ·  {n:,} total traces",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.legend(handles=patches, loc="lower center",
              bbox_to_anchor=(0.5, -0.25), ncol=4,
              fontsize=FONT_ANNOT, frameon=True, framealpha=0.9)

    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task37_stacked_bar.svg"))


# ── Public entry point ────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None, conformance_bins=None,
             **kwargs):
    """Generate all Task 37 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 37 visualizations (Present fitness technique comparison) ---")

    if not alignments:
        logger.warning("      Skipped Task 37: no alignments provided.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task37_{name}.svg", "No alignment data available.")
        return

    data = _extract_data(log, alignments, model_path, conformance_bins)
    logger.info(f"      -> Fitness bands: {', '.join(data['bucket_labels'])}")

    task37_bar_chart(data, output_dir)
    task37_heatmap(data, output_dir)
    task37_table(data, output_dir)
    task37_stacked_bar(data, output_dir)
