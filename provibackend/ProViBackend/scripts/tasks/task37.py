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
    "line_graph", "horizon_chart", "heatmap",
    "table", "table_bar_chart", "stacked_bar",
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


def _extract_data(log, alignments, model_path=None):
    n = len(alignments)

    # T1: alignment-based
    t1 = [float(aln.get("fitness", 0.0)) for aln in alignments]

    # T2: token-based replay (optional)
    t2 = None
    if model_path:
        t2 = _compute_tbr_fitness(log, model_path)
        if t2 is not None and len(t2) != n:
            logger.warning("Task37: TBR length mismatch — discarding T2.")
            t2 = None

    delta = [t1[i] - t2[i] for i in range(n)] if t2 is not None else None

    return {
        "n_traces": n,
        "t1":       t1,
        "t2":       t2,
        "delta":    delta,
        "t1_stats": _fitness_stats(t1),
        "t2_stats": _fitness_stats(t2) if t2 is not None else None,
        "t1_name":  "Alignment-based",
        "t2_name":  "Token-based Replay",
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
    """Mean + median fitness comparison: T1 vs T2."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "bar_chart"); return

    has_t2  = data["t2"] is not None
    t1_s    = data["t1_stats"]
    t2_s    = data["t2_stats"]
    metrics = ["Mean", "Median"]
    t1_vals = [t1_s["mean"], t1_s["median"]]
    t2_vals = [t2_s["mean"], t2_s["median"]] if has_t2 else None

    x = np.arange(len(metrics))
    w = 0.35 if has_t2 else 0.5

    fig, ax = plt.subplots(figsize=(9, 5))
    ax.set_facecolor("#fafbfc")

    bars1 = ax.bar(x - w / 2 if has_t2 else x, t1_vals, width=w,
                   color=_C_T1, label=data["t1_name"])
    for b, v in zip(bars1, t1_vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.012,
                f"{v:.3f}", ha="center", va="bottom",
                fontsize=FONT_ANNOT, color=_C_DARK)

    if has_t2:
        bars2 = ax.bar(x + w / 2, t2_vals, width=w,
                       color=_C_T2, label=data["t2_name"])
        for b, v in zip(bars2, t2_vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 0.012,
                    f"{v:.3f}", ha="center", va="bottom",
                    fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_xticks(x)
    ax.set_xticklabels(metrics, fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness", fontsize=FONT_LABEL)
    ax.set_ylim(0, 1.15)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_title(
        f"Fitness Statistics Comparison  ·  {data['n_traces']:,} traces",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    if has_t2:
        ax.legend(fontsize=FONT_ANNOT, frameon=False)

    fig.tight_layout()
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

def task37_line_graph(data, output_dir):
    """Fitness per trace index: T1 and T2 overlaid. Rolling average when N > 100."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "line_graph"); return

    t1     = np.array(data["t1"])
    has_t2 = data["t2"] is not None
    t2     = np.array(data["t2"]) if has_t2 else None
    n      = len(t1)
    x      = np.arange(1, n + 1)
    smooth = n > 100

    def _roll(arr, w=10):
        kernel = np.ones(w) / w
        return np.convolve(arr, kernel, mode="same")

    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.set_facecolor("#fafbfc")

    t1_plot = _roll(t1) if smooth else t1
    lbl1 = f"{data['t1_name']}" + (" (rolling avg)" if smooth else "")
    ax.plot(x, t1_plot, color=_C_T1, linewidth=1.4, label=lbl1)

    if has_t2:
        t2_plot = _roll(t2) if smooth else t2
        lbl2 = f"{data['t2_name']}" + (" (rolling avg)" if smooth else "")
        ax.plot(x, t2_plot, color=_C_T2, linewidth=1.4,
                linestyle="--", label=lbl2)

    ax.set_xlim(1, n)
    ax.set_ylim(-0.02, 1.05)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_xlabel("Trace Index", fontsize=FONT_LABEL)
    ax.set_ylabel("Fitness", fontsize=FONT_LABEL)
    ax.set_title(
        f"Fitness Trend per Trace  ·  {n:,} traces",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(fontsize=FONT_ANNOT, frameon=False, loc="lower left")

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task37_line_graph.svg"))


# ── Idiom 5: Horizon Chart ────────────────────────────────────────────────────

def task37_horizon_chart(data, output_dir):
    """If T2 available: horizon chart of delta (T1 – T2) per trace.
    Otherwise: T1 deviation from its mean."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "horizon_chart"); return

    n      = data["n_traces"]
    x      = np.arange(1, n + 1)
    has_t2 = data["t2"] is not None

    if has_t2:
        y         = np.array(data["delta"])
        baseline  = 0.0
        ylabel    = "Δ Fitness  (T1 – T2)"
        title     = f"Fitness Technique Difference  (T1 – T2)  ·  {n:,} traces"
        lbl_above = f"{data['t1_name']} higher"
        lbl_below = f"{data['t2_name']} higher"
    else:
        t1        = np.array(data["t1"])
        baseline  = float(t1.mean())
        y         = t1 - baseline
        ylabel    = f"Fitness deviation from mean"
        title     = f"Fitness Deviation from Mean  ·  {n:,} traces"
        lbl_above = "Above mean"
        lbl_below = "Below mean"

    fig, ax = plt.subplots(figsize=(13, 4.5))
    ax.set_facecolor("#fafbfc")

    ax.fill_between(x, baseline, y + baseline, where=(y >= 0),
                    interpolate=True, color=_C_T1, alpha=0.75, label=lbl_above)
    ax.fill_between(x, baseline, y + baseline, where=(y < 0),
                    interpolate=True, color=_C_T2, alpha=0.75, label=lbl_below)
    ax.plot(x, y + baseline, color="#555555", linewidth=0.6, alpha=0.5)
    ax.axhline(baseline, color=_C_MED, linewidth=1.0, linestyle="--")

    ax.annotate(
        f"{'baseline = 0' if has_t2 else f'mean = {baseline:.3f}'}",
        xy=(1.01, baseline), xycoords=("axes fraction", "data"),
        fontsize=FONT_ANNOT, color=_C_MED, va="center",
    )

    ax.set_xlim(1, n)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter("%.2f"))
    ax.set_xlabel("Trace Index", fontsize=FONT_LABEL)
    ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    ax.set_title(title, fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(fontsize=FONT_ANNOT, frameon=False, loc="lower left")

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task37_horizon_chart.svg"))


# ── Idiom 6: Heatmap ──────────────────────────────────────────────────────────

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


# ── Idiom 7: Table ────────────────────────────────────────────────────────────

def task37_table(data, output_dir):
    """Per-trace detail table: Trace # | T1 | T2 | Δ | Classification."""
    if data["n_traces"] == 0:
        _no_data(output_dir, "table"); return

    t1     = data["t1"]
    t2     = data["t2"]
    has_t2 = t2 is not None
    n      = data["n_traces"]
    MAX    = 50

    def classify(v):
        if v >= 0.8: return "Conformant"
        if v >= 0.5: return "Partial"
        return "Deviating"

    rows = []
    for i in range(min(n, MAX)):
        row = [str(i + 1), f"{t1[i]:.3f}"]
        if has_t2:
            row += [f"{t2[i]:.3f}", f"{t1[i] - t2[i]:+.3f}"]
        row.append(classify(t1[i]))
        rows.append(row)

    if has_t2:
        col_headers = ["Trace #", data["t1_name"], data["t2_name"], "Δ (T1−T2)", "Class. (T1)"]
        col_widths  = [0.10, 0.20, 0.20, 0.18, 0.32]
    else:
        col_headers = ["Trace #", data["t1_name"], "Classification"]
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
            ax.text(px, y_top + row_h * 0.5, str(val),
                    ha=ha, va="center", fontsize=FONT_ANNOT,
                    color=_C_DARK, transform=ax.transAxes)
            x += cw * tw

    title = f"Per-Trace Fitness Detail  ·  {n:,} traces"
    if n > MAX:
        title += f"  (first {MAX} shown)"
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
    task37_line_graph(data, output_dir)
    task37_horizon_chart(data, output_dir)
    task37_heatmap(data, output_dir)
    task37_table(data, output_dir)
    task37_table_bar_chart(data, output_dir)
    task37_stacked_bar(data, output_dir)
