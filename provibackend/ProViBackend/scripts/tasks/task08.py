"""
tasks/task08.py – Task 8: Violation co-occurrence patterns.

Which guideline violations frequently co-occur in a trace?

Visualizations:
    bar_chart, heatmap, matrix, network_diagram, scatter_plot,
    table, table_bar_chart, tree

Skipped (require BPMN rendering infrastructure):
    flow_table, flow_plus, flow_plus_table

Public API:
    generate(log, alignments, output_dir)
        log        – PM4Py EventLog (for total trace count)
        alignments – list[dict] from pm4py.conformance_diagnostics_alignments
        output_dir – directory where SVGs are written
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart",
    "heatmap",
    "matrix",
    "network_diagram",
    "scatter_plot",
    "table",
    "table_bar_chart",
]

import os
from collections import Counter
from itertools import combinations

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
import matplotlib.colors as mcolors
import matplotlib.cm as cm

from shared import save_svg, FONT_TITLE, FONT_LABEL, FONT_ANNOT

# ── Greyscale palette (consistent with platform style) ──────────────────────
_C_DARK   = "#222222"   # highest emphasis (= black bars, dark nodes)
_C_MED    = "#666666"   # secondary
_C_LIGHT  = "#aaaaaa"   # tertiary / background nodes
_C_BG     = "#f5f5f5"   # panel / cell backgrounds
_HDR_BG   = "#333333"   # table header background
_HDR_FG   = "white"     # table header text
_CMAP_SEQ = "Greys"     # sequential: white → black

# Max violations shown in most idioms (keeps charts readable)
_TOP_N = 12
# Min co-occurrence count for network edges / scatter points
_MIN_COOCCUR = 1

SKIP_TOKENS = {">>", None}


# ---------------------------------------------------------------------------
# Core: extract per-trace violation sets from alignment results
# ---------------------------------------------------------------------------

def _extract_label(raw):
    """Extract activity string from a PM4Py alignment side (str or tuple)."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple)):
        for v in raw:
            if v is not None and v != ">>":
                return str(v)
        return ">>"
    return str(raw)


def _classify_step(observed_raw, expected_raw):
    """Return (violation_label | None) for one alignment step.

    Standard PM4Py alignment terminology:
        Synchronous Move  – both log and model agree (fit, ignored)
        Move on Model     – model fires a transition the trace skipped
        Move on Log       – trace has an event the model doesn't expect
        Mismatch Move     – both present but different labels (rare)
    """
    obs = _extract_label(observed_raw)
    exp = _extract_label(expected_raw)
    obs_skip = obs in SKIP_TOKENS or obs is None
    exp_skip = exp in SKIP_TOKENS or exp is None

    if obs_skip and exp_skip:
        return None                        # hidden / tau transition, ignore
    if not obs_skip and not exp_skip:
        if obs == exp:
            return None                    # Synchronous Move (fit)
        return f"Mismatch Move: {obs}"     # rare in proper alignments
    if obs_skip:
        return f"Move on Model: {exp}"     # model expected exp, trace skipped it
    return f"Move on Log: {obs}"           # trace has obs, model didn't expect it


def _extract_violation_data(alignments):
    """Build violation sets and frequency counts from raw alignment results.

    Returns
    -------
    violation_sets : list[frozenset]   one per trace (empty = fully conformant)
    violation_freq : Counter           violation_label → n_traces containing it
    cooccurrence   : Counter           (viol_A, viol_B) sorted pair → n_traces
    """
    violation_sets = []
    for result in alignments:
        seen = set()
        for step in result.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) != 2:
                continue
            label = _classify_step(step[0], step[1])
            if label:
                seen.add(label)
        violation_sets.append(frozenset(seen))

    violation_freq = Counter()
    for vset in violation_sets:
        violation_freq.update(vset)

    cooccurrence = Counter()
    for vset in violation_sets:
        if len(vset) >= 2:
            for pair in combinations(sorted(vset), 2):
                cooccurrence[pair] += 1

    return violation_sets, violation_freq, cooccurrence


def _top_violations(violation_freq, n=_TOP_N):
    return [v for v, _ in violation_freq.most_common(n)]


def _short_label(label: str, max_len: int = 28) -> str:
    """Truncate long violation labels for display."""
    return label if len(label) <= max_len else label[: max_len - 1] + "…"


def _save_empty(output_dir: str, filename: str, message: str = "No violation data"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


def _no_violations(output_dir, name):
    _save_empty(output_dir, f"task08_{name}.svg",
                "No guideline violations detected in this log")


# ---------------------------------------------------------------------------
# Idiom 1: Bar Chart — individual violation frequencies
# ---------------------------------------------------------------------------

def task08_bar_chart(violation_freq, n_traces, output_dir):
    if not violation_freq:
        _no_violations(output_dir, "bar_chart")
        return

    top = _top_violations(violation_freq, _TOP_N)
    labels = [_short_label(v) for v in top]
    counts = [violation_freq[v] for v in top]
    pcts   = [c / n_traces * 100 for c in counts]

    fig, ax = plt.subplots(figsize=(12, 5))
    bars = ax.barh(range(len(top)), counts, color=_C_DARK, alpha=0.85, height=0.65)
    ax.invert_yaxis()

    # Annotate with % of traces
    for i, (c, p) in enumerate(zip(counts, pcts)):
        ax.text(c + max(counts) * 0.01, i, f"{p:.1f}%",
                va="center", fontsize=FONT_ANNOT, color=_C_MED)

    ax.set_yticks(range(len(top)))
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.set_xlabel("Number of Traces", fontsize=FONT_LABEL)
    ax.set_title("Most Frequent Guideline Violations", fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_bar_chart.svg"))


# ---------------------------------------------------------------------------
# Idiom 2: Heatmap — violation × violation co-occurrence (colour only)
# ---------------------------------------------------------------------------

def _build_cooccur_matrix(top_viols, violation_freq, cooccurrence):
    n = len(top_viols)
    mat = np.zeros((n, n))
    idx = {v: i for i, v in enumerate(top_viols)}
    for (a, b), cnt in cooccurrence.items():
        if a in idx and b in idx:
            mat[idx[a], idx[b]] = cnt
            mat[idx[b], idx[a]] = cnt
    # Diagonal = individual frequency
    for v, i in idx.items():
        mat[i, i] = violation_freq[v]
    return mat


def task08_heatmap(violation_freq, cooccurrence, output_dir):
    if not violation_freq:
        _no_violations(output_dir, "heatmap")
        return

    top = _top_violations(violation_freq, _TOP_N)
    if len(top) < 2:
        _save_empty(output_dir, "task08_heatmap.svg",
                    "Too few distinct violations for co-occurrence heatmap")
        return

    mat  = _build_cooccur_matrix(top, violation_freq, cooccurrence)
    labs = [_short_label(v) for v in top]
    n    = len(top)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.75), max(6, n * 0.65)))
    im = ax.imshow(mat, cmap=_CMAP_SEQ, aspect="auto", vmin=0)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labs, rotation=40, ha="right", fontsize=FONT_ANNOT)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labs, fontsize=FONT_ANNOT)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Co-occurrence count", fontsize=FONT_ANNOT)
    cbar.outline.set_visible(False)

    ax.set_title("Violation Co-occurrence Heatmap\n(diagonal = individual frequency)",
                 fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_heatmap.svg"))


# ---------------------------------------------------------------------------
# Idiom 3: Matrix — same as heatmap but with numbers in each cell
# ---------------------------------------------------------------------------

def task08_matrix(violation_freq, cooccurrence, output_dir):
    if not violation_freq:
        _no_violations(output_dir, "matrix")
        return

    top = _top_violations(violation_freq, min(_TOP_N, 10))  # tighter for readability
    if len(top) < 2:
        _save_empty(output_dir, "task08_matrix.svg",
                    "Too few distinct violations for co-occurrence matrix")
        return

    mat  = _build_cooccur_matrix(top, violation_freq, cooccurrence)
    labs = [_short_label(v) for v in top]
    n    = len(top)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.9), max(6, n * 0.8)))
    im = ax.imshow(mat, cmap=_CMAP_SEQ, aspect="auto", vmin=0)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labs, rotation=40, ha="right", fontsize=FONT_ANNOT)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labs, fontsize=FONT_ANNOT)

    # Annotate each cell with the count
    thresh = mat.max() / 2
    for i in range(n):
        for j in range(n):
            val = int(mat[i, j])
            color = "white" if mat[i, j] > thresh else _C_DARK
            ax.text(j, i, str(val), ha="center", va="center",
                    fontsize=max(FONT_ANNOT - 1, 6), color=color, fontweight="bold")

    ax.set_title("Violation Co-occurrence Matrix\n(diagonal = individual frequency)",
                 fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_matrix.svg"))


# ---------------------------------------------------------------------------
# Idiom 4: Network Diagram — violations as nodes, co-occurrence as edges
# ---------------------------------------------------------------------------

def task08_network_diagram(violation_freq, cooccurrence, output_dir):
    try:
        import networkx as nx
    except ImportError:
        _save_empty(output_dir, "task08_network_diagram.svg",
                    "networkx not installed — pip install networkx")
        return

    if not violation_freq:
        _no_violations(output_dir, "network_diagram")
        return

    top   = set(_top_violations(violation_freq, _TOP_N))
    pairs = [(a, b, cnt) for (a, b), cnt in cooccurrence.items()
             if a in top and b in top and cnt >= _MIN_COOCCUR]

    if not pairs:
        _save_empty(output_dir, "task08_network_diagram.svg",
                    "No co-occurring violations to display")
        return

    G = nx.Graph()
    for v in top:
        G.add_node(v, freq=violation_freq[v])
    for a, b, cnt in pairs:
        G.add_edge(a, b, weight=cnt)

    # Circular layout for ≤8 nodes (avoids spring clustering); spring for more
    n_nodes = G.number_of_nodes()
    if n_nodes <= 8:
        pos = nx.circular_layout(G, scale=2.0)
    else:
        pos = nx.spring_layout(G, seed=42, k=3.0)

    # Node sizes proportional to frequency
    nodes_ordered = list(G.nodes)
    freqs   = np.array([G.nodes[n]["freq"] for n in nodes_ordered])
    node_sz = (freqs / freqs.max() * 1600 + 400).tolist()

    # Edge widths and grey shades proportional to co-occurrence
    edges   = list(G.edges())
    weights = [G[u][v]["weight"] for u, v in edges]
    max_w   = max(weights) if weights else 1
    edge_w  = [1.5 + (w / max_w) * 5 for w in weights]
    edge_col= [plt.cm.Greys(0.25 + 0.55 * w / max_w) for w in weights]

    # Node shades by violation type (updated for new terminology)
    def node_color(label):
        if "Move on Model" in label: return _C_LIGHT   # light grey
        if "Move on Log"   in label: return _C_MED     # mid grey
        return _C_DARK                                  # dark (Mismatch)

    colors = [node_color(n) for n in nodes_ordered]

    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_facecolor("#fafbfc")

    nx.draw_networkx_edges(G, pos, ax=ax, width=edge_w,
                           edge_color=edge_col, alpha=0.85, edgelist=edges)
    nx.draw_networkx_nodes(G, pos, nodelist=nodes_ordered, ax=ax,
                           node_size=node_sz, node_color=colors,
                           alpha=0.92, linewidths=0.8, edgecolors="white")

    # Node labels: placed below each node, with white bbox
    for node, (x, y) in pos.items():
        ax.annotate(
            _short_label(node, 26), xy=(x, y),
            xytext=(0, -22), textcoords="offset points",
            ha="center", va="top",
            fontsize=max(FONT_ANNOT - 1, 6), color=_C_DARK,
            bbox=dict(boxstyle="round,pad=0.25", fc="white",
                      ec="#dddddd", alpha=0.92, linewidth=0.4),
        )

    # Edge weight labels: drawn manually at midpoint, pushed perpendicular
    # to avoid overlapping the edge line or nearby nodes
    top_edges = sorted(zip(edges, weights), key=lambda x: -x[1])[:8]
    for (u, v), w in top_edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        # Perpendicular unit offset so label sits beside the line, not on it
        dx, dy = x1 - x0, y1 - y0
        length = max(np.hypot(dx, dy), 1e-6)
        perp_x, perp_y = -dy / length * 0.12, dx / length * 0.12
        ax.text(mx + perp_x, my + perp_y, str(w),
                ha="center", va="center",
                fontsize=max(FONT_ANNOT - 1, 7), color=_C_DARK, fontweight="bold",
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec="#cccccc", alpha=0.95, linewidth=0.4))

    # Legend with updated terminology
    legend_handles = [
        mpatches.Patch(color=_C_LIGHT, label="Move on Model (skipped activity)"),
        mpatches.Patch(color=_C_MED,   label="Move on Log (extra activity)"),
        mpatches.Patch(color=_C_DARK,  label="Mismatch Move"),
    ]
    ax.legend(handles=legend_handles, loc="lower right",
              fontsize=FONT_ANNOT, frameon=True, framealpha=0.95)

    ax.set_title("Violation Co-occurrence Network\n"
                 "(node size = frequency · edge width & shade = co-occurrence count)",
                 fontsize=FONT_TITLE)
    ax.axis("off")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_network_diagram.svg"))


# ---------------------------------------------------------------------------
# Idiom 5: Scatter Plot — each point = a violation pair
# ---------------------------------------------------------------------------

def task08_scatter_plot(violation_freq, cooccurrence, n_traces, output_dir):
    """Scatter: X = freq(A), Y = freq(B), bubble size = co-occurrence count.

    Only top 12 pairs shown (by co-occurrence). Small jitter separates points
    that share the same violation frequency. Labels on top 6 only.
    """
    if not violation_freq or not cooccurrence:
        _no_violations(output_dir, "scatter_plot")
        return

    top_set = set(_top_violations(violation_freq, _TOP_N))
    rows = []
    for (a, b), cnt in cooccurrence.items():
        if a not in top_set or b not in top_set:
            continue
        fa, fb = violation_freq[a], violation_freq[b]
        # Always put the more frequent violation on X-axis
        if fa < fb:
            a, b, fa, fb = b, a, fb, fa
        rows.append({"a": a, "b": b, "freq_a": fa, "freq_b": fb, "cooccur": cnt})

    if not rows:
        _save_empty(output_dir, "task08_scatter_plot.svg",
                    "No co-occurring violation pairs to display")
        return

    df = pd.DataFrame(rows).sort_values("cooccur", ascending=False).head(12)

    rng = np.random.default_rng(42)
    jitter_scale = max(df["freq_a"].max() - df["freq_a"].min(), 1) * 0.02
    x = df["freq_a"].values + rng.uniform(-jitter_scale, jitter_scale, len(df))
    y = df["freq_b"].values + rng.uniform(-jitter_scale, jitter_scale, len(df))

    fig, ax = plt.subplots(figsize=(11, 8))
    ax.set_facecolor("#fafbfc")

    # Normalise bubble area to a bounded range so high co-occurrence counts
    # don't blow up into canvas-filling circles.
    cc = df["cooccur"].values.astype(float)
    cc_max = max(cc.max(), 1.0)
    sizes = (cc / cc_max) * 1800.0 + 140.0

    sc = ax.scatter(
        x, y,
        s=sizes,
        c=cc, cmap=_CMAP_SEQ,
        alpha=0.85, edgecolors=_C_MED, linewidths=0.6, vmin=0,
    )

    # Label top 6 only, with white backing; show the full violation names.
    for i, (_, row) in enumerate(df.head(6).iterrows()):
        label = f"{_short_label(row['a'], 40)}\n× {_short_label(row['b'], 40)}"
        ax.annotate(
            label,
            xy=(x[i], y[i]),
            xytext=(12, 8), textcoords="offset points",
            fontsize=max(FONT_ANNOT - 1, 6), color=_C_DARK,
            bbox=dict(boxstyle="round,pad=0.25", fc="white", ec="#dddddd",
                      alpha=0.92, linewidth=0.5),
        )

    # Extra margins so the largest bubbles are not clipped at the axes' edges.
    ax.margins(0.18)

    cbar = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Co-occurrence count", fontsize=FONT_ANNOT)
    cbar.outline.set_visible(False)

    ax.set_xlabel("Frequency of Violation A  (traces)", fontsize=FONT_LABEL)
    ax.set_ylabel("Frequency of Violation B  (traces)", fontsize=FONT_LABEL)
    ax.set_title("Top Violation Pair Co-occurrences\n(bubble size & shade = co-occurrence count · top 6 labelled)",
                 fontsize=FONT_TITLE)
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_scatter_plot.svg"))


# ---------------------------------------------------------------------------
# Idiom 6: Table — ranked co-occurrence pairs
# ---------------------------------------------------------------------------

def task08_table(violation_freq, cooccurrence, n_traces, output_dir):
    if not cooccurrence:
        _no_violations(output_dir, "table")
        return

    top_pairs = cooccurrence.most_common(20)
    rows = []
    for (a, b), cnt in top_pairs:
        rows.append([
            _short_label(a, 30),
            _short_label(b, 30),
            cnt,
            f"{cnt / n_traces * 100:.1f}%",
        ])

    col_headers = ["Violation A", "Violation B", "Co-occ. Count", "% of Traces"]
    col_widths   = [0.34, 0.34, 0.16, 0.16]

    n_rows  = len(rows)
    fig_h   = max(4, 0.38 * n_rows + 1.5)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis("off")

    tbl = ax.table(
        cellText=rows,
        colLabels=col_headers,
        colWidths=col_widths,
        loc="center", cellLoc="left",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(FONT_ANNOT)
    tbl.scale(1, 1.5)

    # Header styling
    for j in range(len(col_headers)):
        cell = tbl[0, j]
        cell.set_facecolor(_HDR_BG)
        cell.set_text_props(color=_HDR_FG, fontweight="bold")

    # Alternating row colours
    for i in range(1, n_rows + 1):
        bg = _C_BG if i % 2 == 0 else "white"
        for j in range(len(col_headers)):
            tbl[i, j].set_facecolor(bg)
            tbl[i, j].set_edgecolor("#e0e0e0")

    ax.set_title("Top Violation Co-occurrences", fontsize=FONT_TITLE,
                 pad=12, loc="left")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_table.svg"))


# ---------------------------------------------------------------------------
# Idiom 7: Table & Bar Chart — left bar chart + right table
# ---------------------------------------------------------------------------

def task08_table_bar_chart(violation_freq, cooccurrence, n_traces, output_dir):
    if not violation_freq:
        _no_violations(output_dir, "table_bar_chart")
        return

    top   = _top_violations(violation_freq, 10)
    labs  = [_short_label(v, 26) for v in top]
    cnts  = [violation_freq[v] for v in top]
    pcts  = [f"{c / n_traces * 100:.1f}%" for c in cnts]

    fig, (ax_bar, ax_tbl) = plt.subplots(1, 2, figsize=(16, 6),
                                          gridspec_kw={"width_ratios": [1.4, 1]})

    # Left: horizontal bar chart
    ax_bar.barh(range(len(top)), cnts, color=_C_DARK, alpha=0.85, height=0.65)
    ax_bar.invert_yaxis()
    ax_bar.set_yticks(range(len(top)))
    ax_bar.set_yticklabels(labs, fontsize=FONT_ANNOT)
    ax_bar.set_xlabel("Traces", fontsize=FONT_LABEL)
    ax_bar.set_title("Violation Frequency", fontsize=FONT_TITLE)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.35)
    ax_bar.set_axisbelow(True)
    ax_bar.tick_params(axis="y", length=0)

    # Right: table showing top co-occurring pairs
    ax_tbl.axis("off")
    top_pairs = cooccurrence.most_common(10)
    tbl_rows = [[_short_label(a, 22), _short_label(b, 22), str(cnt)]
                for (a, b), cnt in top_pairs]
    if tbl_rows:
        tbl = ax_tbl.table(
            cellText=tbl_rows,
            colLabels=["Violation A", "Violation B", "Count"],
            colWidths=[0.38, 0.38, 0.24],
            loc="center", cellLoc="left",
        )
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(FONT_ANNOT)
        tbl.scale(1, 1.6)
        for j in range(3):
            tbl[0, j].set_facecolor(_HDR_BG)
            tbl[0, j].set_text_props(color=_HDR_FG, fontweight="bold")
        for i in range(1, len(tbl_rows) + 1):
            for j in range(3):
                tbl[i, j].set_facecolor(_C_BG if i % 2 == 0 else "white")
                tbl[i, j].set_edgecolor("#e0e0e0")
        ax_tbl.set_title("Top Co-occurring Pairs", fontsize=FONT_TITLE,
                         pad=12, loc="left")

    fig.suptitle("Violation Frequency & Top Co-occurrences", fontsize=FONT_TITLE,
                 y=1.01, fontweight="bold")
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_table_bar_chart.svg"))




# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str):
    """Generate all Task 8 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 8 visualizations (Violation co-occurrence patterns) ---")

    n_traces = len(log)
    violation_sets, violation_freq, cooccurrence = _extract_violation_data(alignments)

    n_with_viols = sum(1 for vs in violation_sets if vs)
    logger.info(f"      -> {n_with_viols} / {n_traces} traces have violations; "
                f"{len(violation_freq)} distinct violation types.")

    if not violation_freq:
        logger.warning("      Skipped Task 8: no violations found in any trace.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task08_{name}.svg",
                        "No guideline violations detected in this log")
        return

    task08_bar_chart(violation_freq, n_traces, output_dir)
    task08_heatmap(violation_freq, cooccurrence, output_dir)
    task08_matrix(violation_freq, cooccurrence, output_dir)
    task08_network_diagram(violation_freq, cooccurrence, output_dir)
    task08_scatter_plot(violation_freq, cooccurrence, n_traces, output_dir)
    task08_table(violation_freq, cooccurrence, n_traces, output_dir)
    task08_table_bar_chart(violation_freq, cooccurrence, n_traces, output_dir)
