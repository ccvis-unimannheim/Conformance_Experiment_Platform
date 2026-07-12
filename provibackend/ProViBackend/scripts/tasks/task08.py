"""
tasks/task08.py – Task 8: Violation co-occurrence patterns.

Which guideline violations frequently co-occur in a trace?

Visualizations:
    heatmap, matrix, network_diagram, table

Skipped (require BPMN rendering infrastructure):
    flow_table, flow_plus, flow_plus_table

Public API:
    generate(log, alignments, output_dir, high_cooccurrence_threshold=0.1)
        log        – PM4Py EventLog (for total trace count)
        alignments – list[dict] from pm4py.conformance_diagnostics_alignments
        output_dir – directory where SVGs are written
        high_cooccurrence_threshold – share of traces (0–1) at/above which a
                       violation pair's co-occurrence is regarded as "high".
                       Drawn neutrally as a reference value on the co-occurrence
                       idioms; no pair is flagged pass/fail, so the analyst
                       decides which correlations are noteworthy.
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "heatmap",
    "matrix",
    "network_diagram",
    "table",
]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8)
#
# Task 8 (SEMI): admin specifies the share-of-traces threshold above which a
# violation pair counts as "highly co-occurring"; GT = off-diagonal cells of
# the top-N co-occurrence matrix flagged correct when count ≥ threshold×n_traces.
# ---------------------------------------------------------------------------
DEFAULT_HIGH_COOCCURRENCE_THRESHOLD = 0.1

GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "high_cooccurrence_threshold",
        "label": "High co-occurrence threshold (share of traces 0–1 at/above which a violation pair counts as highly co-occurring)",
        "hint": "Two violations count as frequently co-occurring when they appear together in at least this share of traces",
        "widget": "threshold",
        "default": DEFAULT_HIGH_COOCCURRENCE_THRESHOLD,
        "required": False,
        "optional_hint": f"(optional — leave empty to use the default threshold of {DEFAULT_HIGH_COOCCURRENCE_THRESHOLD})",
        "min": 0.01,
        "max": 1.0,
        "step": 0.01,
    },
]

ANSWER_FORMATS = [
    {"key": "matrix", "gt_shape": "matrix", "decisive_default": True},
]


def validate_params(log, params) -> list:
    """Reject an out-of-range threshold; param is optional (defaults to 0.1)."""
    raw = params.get("high_cooccurrence_threshold")
    if raw is None or raw == "":
        return []
    try:
        thr = float(raw)
    except (TypeError, ValueError):
        return [f"High co-occurrence threshold '{raw}' is not a number."]
    if not (0.0 < thr <= 1.0):
        return ["High co-occurrence threshold must be between 0 and 1."]
    return []


import os
from collections import Counter
from itertools import combinations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from shared import save_svg, GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER, CIVIDIS, CIVIDIS_R, FONT_TITLE, FONT_ANNOT

# ── Cividis palette ──────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK      # dark navy   (highest emphasis)
_C_MED    = GREY_MED       # olive-grey  (secondary)
_C_LIGHT  = GREY_LIGHT     # light olive (tertiary)
_C_BG     = "#f5f5f5"      # panel / cell backgrounds
_HDR_BG   = GREY_DARK      # table header background
_HDR_FG   = "white"        # table header text
_CMAP_SEQ = CIVIDIS_R      # sequential: yellow-green → dark navy (high = dark)

# Max violations shown in most idioms (keeps charts readable)
_TOP_N = 12
# Number of most-frequent violation types forming the (symmetric) co-occurrence
# axis shared by the matrix/heatmap SVGs and the matrix ground truth.
_MATRIX_TOP_N = 10
# Min co-occurrence count for network edges / scatter points
_MIN_COOCCUR = 1

SKIP_TOKENS = {">>", None}


def _cooccur_threshold_caption(thr_count: float, thr_frac: float) -> str:
    """Neutral one-line label describing the high-co-occurrence reference value."""
    return (f"High co-occurrence threshold: ≥ {thr_count:.0f} traces "
            f"({thr_frac * 100:.0f}% of all traces)")


def _add_threshold_footer(fig, thr_count, thr_frac):
    """Lay out the figure with a reserved bottom band and place the high
    co-occurrence reference there as a centered footer.

    Using a figure-level footer (in the reserved band) keeps the caption clear
    of axes content, rotated tick labels and legends, which is where the older
    in-axes caption used to collide.
    """
    fig.tight_layout(rect=(0, 0.06, 1, 1))
    fig.text(0.5, 0.02, _cooccur_threshold_caption(thr_count, thr_frac),
             ha="center", va="bottom", fontsize=FONT_ANNOT, color=_C_MED)


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


def _viol_label(v) -> str:
    """Return a violation's display label in 'type: activity' form.

    Violation identifiers are strings produced by _classify_step (e.g.
    "Move on Model: A_ACCEPTED"), which are already in that form, so they pass
    through unchanged. A legacy (activity, violation_type) tuple is still
    accepted and reformatted for safety.
    """
    if isinstance(v, tuple):
        act, vtype = v
        return f"{vtype}: {act}"
    return str(v)


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
# Idiom: Heatmap — violation × violation co-occurrence (colour only)
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


def task08_heatmap(violation_freq, cooccurrence, output_dir, thr_count, thr_frac):
    if not violation_freq:
        _no_violations(output_dir, "heatmap")
        return

    top = _top_violations(violation_freq, _MATRIX_TOP_N)  # same axis as the matrix GT
    if len(top) < 2:
        _save_empty(output_dir, "task08_heatmap.svg",
                    "Too few distinct violations for co-occurrence heatmap")
        return

    mat  = _build_cooccur_matrix(top, violation_freq, cooccurrence)
    labs = [_short_label(_viol_label(v)) for v in top]
    n    = len(top)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.85), max(6, n * 0.85)))
    im = ax.imshow(mat, cmap=_CMAP_SEQ, aspect="equal", vmin=0)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labs, rotation=40, ha="right", fontsize=FONT_ANNOT)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labs, fontsize=FONT_ANNOT)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Co-occurrence count", fontsize=FONT_ANNOT)
    cbar.outline.set_visible(False)
    # Neutral reference line marking the "high co-occurrence" threshold on the
    # colour scale (no cell is highlighted — the reader decides what is high).
    if thr_count is not None and 0 < thr_count <= mat.max():
        cbar.ax.axhline(thr_count, color=_C_DARK, linewidth=1.2, linestyle="--")

    ax.set_title("Violation Co-occurrence Heatmap\n(diagonal = individual frequency)",
                 fontsize=FONT_TITLE)
    if thr_count is not None:
        _add_threshold_footer(fig, thr_count, thr_frac)
    else:
        fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_heatmap.svg"))


# ---------------------------------------------------------------------------
# Idiom 3: Matrix — same as heatmap but with numbers in each cell
# ---------------------------------------------------------------------------

def task08_matrix(violation_freq, cooccurrence, output_dir, thr_count, thr_frac):
    if not violation_freq:
        _no_violations(output_dir, "matrix")
        return

    top = _top_violations(violation_freq, _MATRIX_TOP_N)  # same axis as the matrix GT
    if len(top) < 2:
        _save_empty(output_dir, "task08_matrix.svg",
                    "Too few distinct violations for co-occurrence matrix")
        return

    mat  = _build_cooccur_matrix(top, violation_freq, cooccurrence)
    labs = [_short_label(_viol_label(v)) for v in top]
    n    = len(top)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.9), max(6, n * 0.9)))
    im = ax.imshow(mat, cmap=_CMAP_SEQ, aspect="equal", vmin=0)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labs, rotation=40, ha="right", fontsize=FONT_ANNOT)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labs, fontsize=FONT_ANNOT)

    # Annotate each cell with the count; outline high-co-occurrence off-diagonal
    # cells (count >= threshold) so "frequently co-occurring" pairs stand out.
    thresh = mat.max() / 2
    for i in range(n):
        for j in range(n):
            val = int(mat[i, j])
            color = "white" if mat[i, j] > thresh else _C_DARK
            ax.text(j, i, str(val), ha="center", va="center",
                    fontsize=max(FONT_ANNOT - 1, 6), color=color, fontweight="bold")
            if thr_count is not None and i != j and thr_count > 0 and mat[i, j] >= thr_count:
                ax.add_patch(mpatches.Rectangle(
                    (j - 0.5, i - 0.5), 1, 1, fill=False,
                    edgecolor=_C_DARK, linewidth=2.2))

    title_note = "diagonal = individual frequency · outlined = high co-occurrence" \
        if thr_count is not None else "diagonal = individual frequency"
    ax.set_title(f"Violation Co-occurrence Matrix\n({title_note})", fontsize=FONT_TITLE)
    if thr_count is not None:
        _add_threshold_footer(fig, thr_count, thr_frac)
    else:
        fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_matrix.svg"))


# ---------------------------------------------------------------------------
# Idiom 4: Network Diagram — violations as nodes, co-occurrence as edges
# ---------------------------------------------------------------------------

def task08_network_diagram(violation_freq, cooccurrence, output_dir, thr_count, thr_frac):
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

    fig_w = max(8, min(14, n_nodes * 2.5))
    fig_h = max(6, min(9, n_nodes * 1.8))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.set_facecolor("#fafbfc")

    nx.draw_networkx_edges(G, pos, ax=ax, width=edge_w,
                           edge_color=edge_col, alpha=0.85, edgelist=edges)
    nx.draw_networkx_nodes(G, pos, nodelist=nodes_ordered, ax=ax,
                           node_size=node_sz, node_color=colors,
                           alpha=0.92, linewidths=0.8, edgecolors="white")

    # Node labels: placed below each node, with white bbox
    for node, (x, y) in pos.items():
        ax.annotate(
            _short_label(_viol_label(node), 26), xy=(x, y),
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

    # Explicitly set axis limits so tight_layout / bbox_inches captures the
    # networkx content correctly — ax.axis("off") can confuse the auto-scaler.
    all_x = [p[0] for p in pos.values()]
    all_y = [p[1] for p in pos.values()]
    pad = max(1.0, (max(all_x) - min(all_x)) * 0.25, (max(all_y) - min(all_y)) * 0.25)
    ax.set_xlim(min(all_x) - pad, max(all_x) + pad)
    ax.set_ylim(min(all_y) - pad - 0.5, max(all_y) + pad)  # extra bottom room for labels
    ax.axis("off")

    if thr_count is not None:
        _add_threshold_footer(fig, thr_count, thr_frac)
    else:
        fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_network_diagram.svg"))


# ---------------------------------------------------------------------------
# Idiom: Table — ranked co-occurrence pairs
# ---------------------------------------------------------------------------

def task08_table(violation_freq, cooccurrence, n_traces, output_dir,
                 thr_count, thr_frac):
    if not cooccurrence:
        _no_violations(output_dir, "table")
        return

    top_pairs = cooccurrence.most_common(20)
    rows = []
    for (a, b), cnt in top_pairs:
        rows.append([
            _short_label(_viol_label(a), 30),
            _short_label(_viol_label(b), 30),
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
    if thr_count is not None:
        _add_threshold_footer(fig, thr_count, thr_frac)
    else:
        fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_table.svg"))


# ---------------------------------------------------------------------------
# Ground-truth computation (SEMI tier)
# ---------------------------------------------------------------------------

def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Violation-pair co-occurrence grid over the symmetric top-N violation axis.

    Both matrix axes are the same ordered set of the top-N most frequent
    violation types. Each option is one upper-triangle cell (no diagonal, no
    duplicate (i,j)/(j,i)); `label` and `value` share the same axis order so the
    admin editor, the participant grid and the submit token stay consistent. A
    pair is flagged correct when it co-occurs in >= threshold x n_traces traces
    (design doc §2 row 8, SEMI tier).
    """
    if answer_format != "matrix":
        return {"options": []}
    raw = params.get("high_cooccurrence_threshold")
    if raw is None or raw == "":
        return {"options": []}
    threshold = float(raw)
    n_traces  = len(log) if log is not None else 0
    thr_count = threshold * n_traces
    _, violation_freq, cooccurrence = _extract_violation_data(alignments)
    top = _top_violations(violation_freq, _MATRIX_TOP_N)
    options = []
    for a, b in combinations(top, 2):           # upper triangle, no diagonal
        cnt = cooccurrence.get(tuple(sorted((a, b))), 0)
        la, lb = _viol_label(a), _viol_label(b)
        options.append({
            "label":   f"{la} × {lb}",
            "value":   f"{la}__{lb}",           # same order as label (axis-consistent)
            "correct": cnt > 0 and cnt >= thr_count,
        })
    return {"options": options}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str,
             high_cooccurrence_threshold=DEFAULT_HIGH_COOCCURRENCE_THRESHOLD):
    """Generate all Task 8 SVGs into output_dir.

    high_cooccurrence_threshold : float or None
        Share of traces (0–1) at/above which a violation pair's co-occurrence is
        regarded as "high". When None (left empty by admin), threshold annotations
        are omitted from all idioms and no cells are outlined in the matrix.
    """
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

    # High co-occurrence hints are intentionally NOT drawn on the visualizations
    # (passing thr_count/thr_frac = None disables the footer caption, the heatmap
    # reference line and the matrix cell outlines). They are being moved to the
    # participant view instead. The high_cooccurrence_threshold still drives the
    # ground truth via compute_ground_truth (which reads it from params directly).
    task08_heatmap(violation_freq, cooccurrence, output_dir, None, None)
    task08_matrix(violation_freq, cooccurrence, output_dir, None, None)
    task08_network_diagram(violation_freq, cooccurrence, output_dir, None, None)
    task08_table(violation_freq, cooccurrence, n_traces, output_dir, None, None)
