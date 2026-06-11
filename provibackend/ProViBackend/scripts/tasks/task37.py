"""
tasks/task37.py – Task 37: Present · Summarize · Process conformance

Question: How do fitness values of traces differ when applying two different
techniques to compute them? What is the overall trend of trace fitness?

Visualizations (all SVG, white-grey-black palette):
  bar_chart       – mean/median comparison: T1 vs T2
  boxplot         – distribution: T1 vs T2 side by side
  scatter_plot    – per-trace T1 vs T2 (technique agreement)
  line_graph      – fitness trend per trace index: T1 and T2 overlaid
  horizon_chart   – delta (T1 – T2) horizon chart, or T1 deviation from mean
  heatmap         – 2D density: T1 bucket × T2 bucket
  table           – per-trace detail: T1, T2, delta, classification
  table_bar_chart – summary statistics table + fitness bucket bar chart
  stacked_bar     – fitness bucket distribution: T1 row and T2 row
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart", "boxplot", "scatter_plot",
    "heatmap", "table", "table_bar_chart", "stacked_bar",
]

import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.ticker as mticker

from shared import save_svg, FONT_TITLE, FONT_LABEL, FONT_ANNOT

# ── Palette ───────────────────────────────────────────────────────────────────
_C_DARK   = "#222222"
_C_MED    = "#666666"
_C_LIGHT  = "#aaaaaa"
_C_XLIGHT = "#dddddd"
_HDR_BG   = "#333333"
_C_T1     = "#333333"   # Alignment-based (dark)
_C_T2     = "#999999"   # Token-based Replay (light)

# Fitness bucket definitions (4 bands)
_BUCKETS       = [(0.0, 0.25), (0.25, 0.5), (0.5, 0.75), (0.75, 1.01)]
_BUCKET_LABELS = ["[0, 0.25)", "[0.25, 0.5)", "[0.5, 0.75)", "[0.75, 1.0]"]
_BUCKET_COLORS = ["#222222", "#555555", "#888888", "#cccccc"]


def _bucket_idx(v: float) -> int:
    for i, (lo, hi) in enumerate(_BUCKETS):
        if lo <= v < hi:
            return i
    return len(_BUCKETS) - 1


def _fitness_stats(vals):
    a = np.array(vals, dtype=float)
    buckets = [int(np.sum((a >= lo) & (a < hi))) for lo, hi in _BUCKETS]
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


def _extract_data(log, alignments, model_path=None):
    n = len(alignments)

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
        "t1_stats":       _fitness_stats(t1),
        "t2_stats":       _fitness_stats(t2) if t2 is not None else None,
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
                   color=_C_T1, label=data["t1_name"])
    for b, v in zip(bars1, t1_left):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.012,
                f"{v:.3f}", ha="center", va="bottom",
                fontsize=FONT_ANNOT, color=_C_DARK)

    if has_t2:
        bars2 = ax.bar(x + w / 2, t2_left, width=w,
                       color=_C_T2, label=data["t2_name"])
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
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
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
        ax.legend(fontsize=FONT_ANNOT, frameon=False, loc="upper left")

    # Log-level annotation placed below the x-axis to avoid overlapping bars
    fig.tight_layout()
    fig.subplots_adjust(bottom=0.22)
    fig.text(0.5, 0.01, "   ".join(pf_lines),
             ha="center", va="bottom",
             fontsize=FONT_ANNOT, color=_C_DARK,
             bbox=dict(boxstyle="round,pad=0.5", fc="#f0f0f0", ec="#cccccc", lw=0.8))

    save_svg(fig, os.path.join(output_dir, "task37_bar_chart.svg"))


# ── Idiom 2: Box Plot ─────────────────────────────────────────────────────────

def task37_boxplot(data, output_dir):
    """Side-by-side box plots: T1 vs T2 fitness distributions."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "boxplot"); return

    has_t2     = data["t2"] is not None
    plot_data  = [data["t1"]] + ([data["t2"]] if has_t2 else [])
    labels     = [data["t1_name"]] + ([data["t2_name"]] if has_t2 else [])
    box_colors = [_C_T1] + ([_C_T2] if has_t2 else [])

    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.set_facecolor("#fafbfc")

    bp = ax.boxplot(
        plot_data, labels=labels, patch_artist=True,
        medianprops=dict(color=_C_DARK, linewidth=2),
        whiskerprops=dict(color=_C_MED, linewidth=1.2),
        capprops=dict(color=_C_MED, linewidth=1.2),
        flierprops=dict(marker="o", markerfacecolor=_C_LIGHT,
                        markersize=3, linestyle="none", markeredgewidth=0),
    )
    for patch, clr in zip(bp["boxes"], box_colors):
        patch.set_facecolor(clr)

    # Annotate median values
    for i, vals in enumerate(plot_data):
        med = float(np.median(vals))
        txt_clr = "white" if box_colors[i] == _C_T1 else _C_DARK
        ax.text(i + 1, med + 0.025, f"{med:.3f}",
                ha="center", va="bottom",
                fontsize=FONT_ANNOT, color=txt_clr)

    ax.set_ylabel("Fitness (0 – 1)", fontsize=FONT_LABEL)
    ax.set_ylim(-0.05, 1.12)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_title(
        f"Fitness Distribution Comparison  ·  {data['n_traces']:,} traces",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task37_boxplot.svg"))


# ── Idiom 3: Scatter Plot ─────────────────────────────────────────────────────

def task37_scatter_plot(data, output_dir):
    """Per-trace scatter: T1 fitness (x) vs T2 fitness (y).
    Points on the y=x diagonal indicate full agreement between techniques."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "scatter_plot"); return
    if data["t2"] is None:
        _save_empty(output_dir, "task37_scatter_plot.svg",
                    "Scatter plot requires two techniques.\n"
                    "Token-based replay not available (no model path).")
        return

    t1     = np.array(data["t1"])
    t2     = np.array(data["t2"])
    abs_d  = np.abs(t1 - t2)
    # Map delta to greyscale: 0 → light, max → dark
    vmax   = max(float(abs_d.max()), 0.01)
    greys  = (abs_d / vmax) * 0.8 + 0.1   # range [0.1, 0.9]
    colors = [(g, g, g) for g in greys]

    fig, ax = plt.subplots(figsize=(7, 7))
    ax.set_facecolor("#fafbfc")

    ax.scatter(t1, t2, c=colors, s=20, alpha=0.75, edgecolors="none", zorder=3)
    ax.plot([0, 1], [0, 1], linestyle="--", color=_C_LIGHT, linewidth=1.2,
            zorder=2, label="Perfect agreement  (y = x)")

    ax.set_xlim(-0.02, 1.05)
    ax.set_ylim(-0.02, 1.05)
    ax.set_xlabel(f"{data['t1_name']} fitness", fontsize=FONT_LABEL)
    ax.set_ylabel(f"{data['t2_name']} fitness", fontsize=FONT_LABEL)
    ax.xaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_title(
        f"Technique Fitness Agreement  ·  {data['n_traces']:,} traces",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(True, linestyle="--", alpha=0.2)
    ax.set_axisbelow(True)
    ax.legend(fontsize=FONT_ANNOT, frameon=False)

    ax.text(0.03, 0.97, f"Mean |Δ| = {abs_d.mean():.3f}",
            transform=ax.transAxes, fontsize=FONT_ANNOT,
            va="top", color=_C_MED)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task37_scatter_plot.svg"))


# ── Idiom 4: Line Graph ───────────────────────────────────────────────────────

# ── Idiom 4: Heatmap ──────────────────────────────────────────────────────────

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
    nb = len(_BUCKETS)

    mat = np.zeros((nb, nb), dtype=int)
    for v1, v2 in zip(t1, t2):
        mat[_bucket_idx(v1), _bucket_idx(v2)] += 1

    fig, ax = plt.subplots(figsize=(9, 7.5))
    ax.imshow(mat, cmap="Greys", aspect="auto", vmin=0, vmax=max(int(mat.max()), 1))

    for i in range(nb):
        for j in range(nb):
            cnt = int(mat[i, j])
            pct = cnt / n * 100 if n > 0 else 0.0
            txt_clr = "white" if cnt > mat.max() * 0.5 else _C_DARK
            ax.text(j, i, f"{cnt}\n({pct:.1f}%)",
                    ha="center", va="center",
                    fontsize=FONT_ANNOT, color=txt_clr, linespacing=1.4)

    # Highlight diagonal (agreement)
    for k in range(nb):
        ax.add_patch(plt.Rectangle(
            (k - 0.5, k - 0.5), 1, 1,
            fill=False, edgecolor=_C_MED, linewidth=2.0,
        ))

    ax.set_xticks(range(nb)); ax.set_xticklabels(_BUCKET_LABELS, fontsize=FONT_ANNOT)
    ax.set_yticks(range(nb)); ax.set_yticklabels(_BUCKET_LABELS, fontsize=FONT_ANNOT)
    ax.set_xlabel(f"{data['t1_name']} fitness bucket", fontsize=FONT_LABEL)
    ax.set_ylabel(f"{data['t2_name']} fitness bucket", fontsize=FONT_LABEL)
    ax.set_title(
        f"Fitness Bucket Agreement  ·  {n:,} traces\n"
        f"Boxed diagonal = techniques agree on bucket",
        fontsize=FONT_TITLE,
    )

    fig.tight_layout()
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

    t_ = 0.94; b_ = 0.04; tw = 0.97; l_ = 0.015
    row_h = (t_ - b_) / (n_rows + 1)

    x = l_
    for hdr, cw in zip(col_headers, col_widths):
        ax.add_patch(plt.Rectangle((x, t_ - row_h), cw * tw, row_h,
                                   fc=_HDR_BG, ec="white", linewidth=0.5,
                                   transform=ax.transAxes, clip_on=False))
        ax.text(x + cw * tw * 0.5, t_ - row_h * 0.5, hdr,
                ha="center", va="center", fontsize=FONT_ANNOT,
                color="white", transform=ax.transAxes)
        x += cw * tw

    for i, row in enumerate(rows):
        y_top = t_ - (i + 2) * row_h
        x = l_
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(zip(row, col_widths)):
            ax.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                       fc=bg, ec="#eeeeee", linewidth=0.4,
                                       transform=ax.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            # Colour Δ column: dark = T1 higher, grey = T2 higher
            clr = _C_DARK
            if has_t2 and j == 3:
                try:
                    clr = _C_DARK if float(val) >= 0 else _C_MED
                except ValueError:
                    pass
            ax.text(px, y_top + row_h * 0.5, str(val),
                    ha=ha, va="center", fontsize=FONT_ANNOT,
                    color=clr, transform=ax.transAxes)
            x += cw * tw

    sort_note = f"stratified by fitness level  ·  {n_groups} unique value groups"
    title = f"Per-Trace Fitness Detail  ·  {n:,} traces  ·  {sort_note}"
    if n > MAX:
        title += f"  ({MAX} shown)"
    ax.set_title(title, fontsize=FONT_TITLE, pad=14)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task37_table.svg"))


# ── Idiom 8: Table & Bar Chart ────────────────────────────────────────────────

def task37_table_bar_chart(data, output_dir):
    """Left: statistics summary table. Right: fitness bucket grouped bar chart."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "table_bar_chart"); return

    has_t2  = data["t2"] is not None
    t1_s    = data["t1_stats"]
    t2_s    = data["t2_stats"]
    n       = data["n_traces"]
    stat_names  = ["Mean", "Median", "Std", "Min", "Max"]
    t1_stat_v   = [t1_s["mean"], t1_s["median"], t1_s["std"], t1_s["min"], t1_s["max"]]
    t2_stat_v   = [t2_s["mean"], t2_s["median"], t2_s["std"], t2_s["min"], t2_s["max"]] if has_t2 else None

    fig, (ax_tbl, ax_bar) = plt.subplots(
        1, 2, figsize=(16, 5.2),
        gridspec_kw={"width_ratios": [2, 3]},
    )

    # ── Left: stats table ────────────────────────────────────────────────────
    ax_tbl.axis("off")
    col_headers = ["Statistic", data["t1_name"]] + ([data["t2_name"]] if has_t2 else [])
    col_widths  = [0.36, 0.32] + ([0.32] if has_t2 else [])
    t_ = 0.94; tw = 0.98; row_h = (t_ - 0.04) / (len(stat_names) + 1)
    x = 0.01

    for hdr, cw in zip(col_headers, col_widths):
        ax_tbl.add_patch(plt.Rectangle((x, t_ - row_h), cw * tw, row_h,
                                       fc=_HDR_BG, ec="white", linewidth=0.5,
                                       transform=ax_tbl.transAxes, clip_on=False))
        ax_tbl.text(x + cw * tw * 0.5, t_ - row_h * 0.5, hdr,
                    ha="center", va="center", fontsize=FONT_ANNOT,
                    color="white", transform=ax_tbl.transAxes)
        x += cw * tw

    for i, (name, v1) in enumerate(zip(stat_names, t1_stat_v)):
        y_top = t_ - (i + 2) * row_h
        x = 0.01
        bg = "#f5f5f5" if i % 2 == 0 else "white"
        row_v = [name, f"{v1:.3f}"] + ([f"{t2_stat_v[i]:.3f}"] if has_t2 else [])
        for j, (val, cw) in enumerate(zip(row_v, col_widths)):
            ax_tbl.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg, ec="#eeeeee", linewidth=0.4,
                                           transform=ax_tbl.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            ax_tbl.text(px, y_top + row_h * 0.5, val,
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, transform=ax_tbl.transAxes)
            x += cw * tw

    # ── Right: fitness bucket grouped bar ────────────────────────────────────
    ax_bar.set_facecolor("#fafbfc")
    nb = len(_BUCKETS)
    xb = np.arange(nb)
    w  = 0.35 if has_t2 else 0.5

    t1_b = [t1_s["buckets"][i] / n * 100 for i in range(nb)]
    bars1 = ax_bar.bar(xb - w / 2 if has_t2 else xb, t1_b, width=w,
                       color=_C_T1, label=data["t1_name"])
    for b, v in zip(bars1, t1_b):
        if v > 0:
            ax_bar.text(b.get_x() + b.get_width() / 2, v + 0.5,
                        f"{v:.1f}%", ha="center", va="bottom",
                        fontsize=FONT_ANNOT - 1, color=_C_DARK)

    if has_t2:
        t2_b = [t2_s["buckets"][i] / n * 100 for i in range(nb)]
        bars2 = ax_bar.bar(xb + w / 2, t2_b, width=w,
                           color=_C_T2, label=data["t2_name"])
        for b, v in zip(bars2, t2_b):
            if v > 0:
                ax_bar.text(b.get_x() + b.get_width() / 2, v + 0.5,
                            f"{v:.1f}%", ha="center", va="bottom",
                            fontsize=FONT_ANNOT - 1, color=_C_DARK)

    ax_bar.set_xticks(xb)
    ax_bar.set_xticklabels(_BUCKET_LABELS, fontsize=FONT_ANNOT)
    ax_bar.set_ylabel("% of traces", fontsize=FONT_LABEL)
    ax_bar.set_title("Fitness Bucket Distribution", fontsize=FONT_TITLE)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax_bar.set_axisbelow(True)
    if has_t2:
        ax_bar.legend(fontsize=FONT_ANNOT, frameon=False)

    fig.suptitle(
        f"Fitness Summary  ·  {n:,} total traces",
        fontsize=FONT_TITLE + 1, y=1.01,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task37_table_bar_chart.svg"))


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

    nb = len(_BUCKETS)

    fig, ax = plt.subplots(figsize=(13, 2.8 + 1.2 * len(rows)))
    ax.set_facecolor("#fafbfc")

    patches = [mpatches.Patch(color=c, label=l)
               for c, l in zip(_BUCKET_COLORS, _BUCKET_LABELS)]

    for y_pos, (label, stats) in enumerate(rows):
        left = 0.0
        for bi in range(nb):
            frac = stats["buckets"][bi] / n * 100
            cnt  = stats["buckets"][bi]
            clr  = _BUCKET_COLORS[bi]
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
    ax.xaxis.grid(True, linestyle="--", alpha=0.25)
    ax.set_axisbelow(True)
    ax.legend(handles=patches, loc="upper center",
              bbox_to_anchor=(0.5, -0.22), ncol=4,
              fontsize=FONT_ANNOT, frameon=True, framealpha=0.9)

    fig.tight_layout(rect=[0, 0.10, 1, 1])
    save_svg(fig, os.path.join(output_dir, "task37_stacked_bar.svg"))


# ── Public entry point ────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None, **kwargs):
    """Generate all Task 37 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 37 visualizations (Present fitness technique comparison) ---")

    if not alignments:
        logger.warning("      Skipped Task 37: no alignments provided.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task37_{name}.svg", "No alignment data available.")
        return

    data = _extract_data(log, alignments, model_path)

    task37_bar_chart(data, output_dir)
    task37_boxplot(data, output_dir)
    task37_scatter_plot(data, output_dir)
    task37_heatmap(data, output_dir)
    task37_table(data, output_dir)
    task37_table_bar_chart(data, output_dir)
    task37_stacked_bar(data, output_dir)
