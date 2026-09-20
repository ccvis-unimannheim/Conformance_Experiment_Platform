"""
tasks/task08.py – Task 8: Violation co-occurrence patterns.

Which guideline violations frequently co-occur in a trace?

Visualizations:
    heatmap, matrix, network_diagram, table

Skipped (require BPMN rendering infrastructure):
    flow_table, flow_plus, flow_plus_table

Public API:
    generate(log, alignments, output_dir)
        log        – PM4Py EventLog (for total trace count)
        alignments – list[dict] from pm4py.conformance_diagnostics_alignments
        output_dir – directory where SVGs are written

Co-occurrence is shown neutrally: no pair is flagged high or low, so the
analyst decides which correlations are noteworthy.
"""

import logging
logger = logging.getLogger(__name__)

import violation_profile

#: Which violations the axes are built from. The same parameter the
#: Violation-profile tasks declare, so "violation pattern" means one thing
#: across the platform; empty keeps the task's own top-N by trace coverage.
#:
#: There is no co-occurrence threshold. One was plumbed through every renderer
#: and then passed as None — "no pair is flagged high or low, so the analyst
#: decides which correlations are noteworthy" — and naming the pairs worth
#: looking at is what choosing the patterns does, without pre-judging them.
PARAM_SPEC = [violation_profile.selection_param_for("pattern")]


def validate_params(log, params) -> list:
    """A co-occurrence needs two things to co-occur."""
    selected = (params or {}).get("violation_patterns") or []
    if len(selected) == 1:
        return ["Select at least two violation patterns — a co-occurrence "
                "between one pattern and itself is not a finding."]
    return []

IDIOMS = [
    "heatmap",
    "matrix",
    "network_diagram",
    "table",
]

import os
from collections import Counter
from itertools import combinations

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

from matplotlib.colors import ListedColormap
from shared import most_common_stable, save_svg, make_table, draw_cell_grid, GREY_DARK, GREY_MED, CIVIDIS, CIVIDIS_R, FONT_TITLE, FONT_ANNOT
from shared import MOVE_LOG, MOVE_MODEL

# ── Cividis palette ──────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK      # dark navy   (highest emphasis)
_C_MED    = GREY_MED       # neutral grey — caption text only, never data
_CMAP_SEQ = CIVIDIS_R      # sequential: yellow-green → dark navy (high = dark)

# ── Chrome ───────────────────────────────────────────────────────────────────
# Greys for what carries no data — the network panel and the boxes behind its
# labels. shared.py sanctions plain grey here ("Grey stays fine for what encodes
# no data: axes, gridlines, borders, text …") but names no constant for it, so
# the values are named once here rather than repeated as near-identical literals
# (#dddddd / #cccccc / #e0e0e0) that differed for no reason.
_CHROME_PANEL  = "#fafbfc"   # axes background behind the network diagram
_CHROME_BORDER = "#dddddd"   # outline of the white label boxes
_CHROME_FILL   = "white"     # fill of those label boxes

# How many of the most-frequent violation types the figures are built from: the
# matrix and heatmap axis, and the ring of the network diagram. One number for
# all three, because they are compared against each other — the network drew 12
# against their 10, so it carried a co-occurrence they had no row for. An admin
# who names the patterns overrides this; see generate().
_TOP_N = 10
# Min co-occurrence count for network edges / scatter points
_MIN_COOCCUR = 1
# Network diagram: the ring has radius 1, labels start outside the widest node
# and read outwards, and the axis is squared off wide enough to hold the longest
# of them without leaving the ring adrift in white space.
_LABEL_RADIUS = 1.18
_NETWORK_LIMIT = 1.85

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
        Model Move        – model fires a transition the trace skipped
        Log Move          – trace has an event the model doesn't expect
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
        # Both sides carry a label and they differ: pm4py's alignments do not
        # produce this, and the step contains a log move on `obs` (the model
        # move on `exp` is counted when the step is parsed as rows elsewhere).
        return f"Log Move: {obs}"
    if obs_skip:
        return f"Model Move: {exp}"        # model expected exp, trace skipped it
    return f"Log Move: {obs}"              # trace has obs, model didn't expect it


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
    return [v for v, _ in most_common_stable(violation_freq, n)]


def _selected_labels(violation_patterns) -> set:
    """`log.violations` values ("Ship Order|Model Move") as this task's labels.

    The picker speaks the platform's activity|move-type vocabulary; this module
    labels a violation "Model Move: Ship Order". Translating at the boundary
    keeps both intact.
    """
    labels = set()
    for raw in violation_patterns or []:
        activity, _, move_type = str(raw).partition("|")
        labels.add(f"{move_type}: {activity}" if move_type else str(raw))
    return labels


def _restrict_to_selection(violation_freq, cooccurrence, labels):
    """Keep only the chosen patterns, and only pairs between two of them."""
    if not labels:
        return violation_freq, cooccurrence
    freq = Counter({v: n for v, n in violation_freq.items() if v in labels})
    pairs = Counter({pair: n for pair, n in cooccurrence.items()
                     if pair[0] in labels and pair[1] in labels})
    return freq, pairs


def _viol_label(v) -> str:
    """Return a violation's display label in 'type: activity' form.

    Violation identifiers are strings produced by _classify_step (e.g.
    "Model Move: A_ACCEPTED"), which are already in that form, so they pass
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
            fontsize=11, color=_C_MED, transform=ax.transAxes)
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


def task08_heatmap(violation_freq, cooccurrence, output_dir, top_n=_TOP_N):
    if not violation_freq:
        _no_violations(output_dir, "heatmap")
        return

    top = _top_violations(violation_freq, top_n)  # same axis as the matrix idiom
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

    ax.set_title("Violation Co-occurrence Heatmap\n(diagonal = individual frequency)",
                 fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_heatmap.svg"))


# ---------------------------------------------------------------------------
# Idiom: Matrix — the same grid as the heatmap, read as numbers instead of colour
# ---------------------------------------------------------------------------

def task08_matrix(violation_freq, cooccurrence, output_dir, top_n=_TOP_N):
    if not violation_freq:
        _no_violations(output_dir, "matrix")
        return

    top = _top_violations(violation_freq, top_n)  # same axis as the heatmap idiom
    if len(top) < 2:
        _save_empty(output_dir, "task08_matrix.svg",
                    "Too few distinct violations for co-occurrence matrix")
        return

    mat  = _build_cooccur_matrix(top, violation_freq, cooccurrence)
    labs = [_short_label(_viol_label(v)) for v in top]
    n    = len(top)

    fig, ax = plt.subplots(figsize=(max(8, n * 0.9), max(6, n * 0.9)))
    # A matrix in the strict sense: empty cells ruled into a grid, the count
    # carried by the printed number alone, and no colour scale. Shading the
    # cells as well would make this the heatmap with digits on top — one
    # variable encoded twice, and two idioms differing only in annotation.
    # Same contract as shared.draw_value_heatmap(colorless=True), kept inline
    # here because a co-occurrence matrix is symmetric and wants square cells
    # (aspect="equal"), which that helper fixes to "auto".
    ax.imshow(np.zeros_like(mat), cmap=ListedColormap(["white"]),
              vmin=0, vmax=1, aspect="equal")
    draw_cell_grid(ax, n, n)

    ax.set_xticks(range(n))
    ax.set_xticklabels(labs, rotation=40, ha="right", fontsize=FONT_ANNOT)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labs, fontsize=FONT_ANNOT)

    # No pair is flagged high or low — the reader decides which correlations
    # are noteworthy.
    for i in range(n):
        for j in range(n):
            ax.text(j, i, str(int(mat[i, j])), ha="center", va="center",
                    fontsize=max(FONT_ANNOT - 1, 6), color=_C_DARK)

    ax.set_title("Violation Co-occurrence Matrix\n(diagonal = individual frequency)",
                 fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_matrix.svg"))


# ---------------------------------------------------------------------------
# Idiom 4: Network Diagram — violations as nodes, co-occurrence as edges
# ---------------------------------------------------------------------------

def task08_network_diagram(violation_freq, cooccurrence, output_dir,
                           top_n=_TOP_N):
    try:
        import networkx as nx
    except ImportError:
        _save_empty(output_dir, "task08_network_diagram.svg",
                    "networkx not installed — pip install networkx")
        return

    if not violation_freq:
        _no_violations(output_dir, "network_diagram")
        return

    # The same violations the heatmap and the matrix put on their axis, so the
    # three idioms of one task show one set of violations and a participant
    # comparing them is comparing the encoding, not the data behind it. A list,
    # not a set: the ranking decides which group of nodes is seated first, and a
    # set would reorder it differently on every run.
    #
    # The ranking is by how many traces contain a violation, not by how much it
    # co-occurs, so a node whose only partner ranks below the cut is drawn with
    # no edge. That is the same gap the matrix shows as a row of zeros — the
    # figures agree — but neither says the pair exists; only the table does.
    top = _top_violations(violation_freq, top_n)
    top_set = set(top)
    pairs = [(a, b, cnt) for (a, b), cnt in cooccurrence.items()
             if a in top_set and b in top_set and cnt >= _MIN_COOCCUR]

    if not pairs:
        _save_empty(output_dir, "task08_network_diagram.svg",
                    "No co-occurring violations to display")
        return

    # Seat each group of violations that co-occur together in one unbroken run
    # of the ring. Ranked order scattered them around it, so every edge became a
    # chord across the middle and the crossings were most of what the figure
    # showed. Seating a whole connected group at once makes every edge a short
    # arc inside its own block; the ranking still decides which block comes
    # first, and the walk is ordered throughout, so the seating does not move
    # between runs.
    partners = {}
    for a, b, _cnt in sorted(pairs, key=lambda e: (-e[2], str(e[0]), str(e[1]))):
        partners.setdefault(a, []).append(b)
        partners.setdefault(b, []).append(a)

    ring, seated = [], set()
    for v in top:
        if v in seated:
            continue
        queue = [v]
        while queue:
            cur = queue.pop(0)
            if cur in seated:
                continue
            ring.append(cur)
            seated.add(cur)
            queue.extend(p for p in partners.get(cur, []) if p not in seated)

    G = nx.Graph()
    for v in ring:
        G.add_node(v, freq=violation_freq[v])
    for a, b, cnt in pairs:
        G.add_edge(a, b, weight=cnt)

    # A ring at every size. Spring layout pulled the connected pairs into tight
    # clusters and scattered the rest, so labels sitting under their node ran
    # straight into the neighbouring one. On a ring the nodes are evenly spaced
    # and every label can point away from the centre, where the only thing it
    # could meet is the label of a node far away in angle.
    n_nodes = G.number_of_nodes()
    pos = nx.circular_layout(G, scale=1.0)

    # Node sizes proportional to frequency
    nodes_ordered = list(G.nodes)
    freqs   = np.array([G.nodes[n]["freq"] for n in nodes_ordered])
    # Capped so the widest node still clears _LABEL_RADIUS and two neighbours on
    # a full ring do not touch.
    node_sz = (freqs / freqs.max() * 1100 + 250).tolist()

    # Edge widths and shades proportional to co-occurrence: the blue end of
    # cividis, slate for the weakest pair to navy for the strongest.
    edges   = list(G.edges())
    weights = [G[u][v]["weight"] for u, v in edges]
    max_w   = max(weights) if weights else 1
    edge_w  = [1.5 + (w / max_w) * 5 for w in weights]
    edge_col= [CIVIDIS(0.30 - 0.25 * w / max_w) for w in weights]

    # Node colours by move type, as on every other task.
    def node_color(label):
        return MOVE_MODEL if "Model Move" in label else MOVE_LOG

    colors = [node_color(n) for n in nodes_ordered]

    # Square, because the ring is: the labels need as much room above and below
    # as they do left and right. It grows with the node count so the ring never
    # gets so crowded that two spokes touch.
    side = max(10.0, min(15.0, 7.0 + n_nodes * 0.45))
    fig, ax = plt.subplots(figsize=(side, side))
    ax.set_facecolor(_CHROME_PANEL)

    nx.draw_networkx_edges(G, pos, ax=ax, width=edge_w,
                           edge_color=edge_col, alpha=0.85, edgelist=edges)
    nx.draw_networkx_nodes(G, pos, nodelist=nodes_ordered, ax=ax,
                           node_size=node_sz, node_color=colors,
                           alpha=0.92, linewidths=0.8, edgecolors=_CHROME_FILL)

    # Node labels: one spoke per node, starting just outside the ring and
    # reading outwards. Parallel rays cannot collide the way a row of boxes
    # under the nodes did; the left half is flipped so nothing reads upside
    # down. No box behind them — outside the ring there is nothing to cover.
    for node, (x, y) in pos.items():
        angle = np.degrees(np.arctan2(y, x))
        lx, ly = x * _LABEL_RADIUS, y * _LABEL_RADIUS
        rotation, ha = (angle + 180, "right") if x < 0 else (angle, "left")
        ax.annotate(
            _short_label(_viol_label(node), 26), xy=(lx, ly),
            rotation=rotation, rotation_mode="anchor",
            ha=ha, va="center",
            fontsize=max(FONT_ANNOT - 1, 6), color=_C_DARK,
        )

    # Edge weight labels: drawn manually at midpoint, pushed perpendicular
    # to avoid overlapping the edge line or nearby nodes
    top_edges = sorted(zip(edges, weights), key=lambda x: (-x[1], str(x[0])))[:8]
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
                bbox=dict(boxstyle="round,pad=0.2", fc=_CHROME_FILL,
                          ec=_CHROME_BORDER, alpha=0.95, linewidth=0.4))

    # Legend with updated terminology
    legend_handles = [
        mpatches.Patch(color=MOVE_MODEL,    label="Model Move (skipped activity)"),
        mpatches.Patch(color=MOVE_LOG,      label="Log Move (extra activity)"),
    ]
    # Under the axis: the corners the legend used to sit in are now where the
    # diagonal spokes reach.
    ax.legend(handles=legend_handles, loc="upper center",
              bbox_to_anchor=(0.5, -0.01), ncol=2,
              fontsize=FONT_ANNOT, frameon=False)

    ax.set_title("Violation Co-occurrence Network\n"
                 "(node size = frequency · edge width & shade = co-occurrence count)",
                 fontsize=FONT_TITLE)

    # Square limits around the ring, set explicitly: the spokes are annotations,
    # which the auto-scaler does not measure, and ax.axis("off") confuses it
    # further. The margin is what holds the longest label.
    ax.set_xlim(-_NETWORK_LIMIT, _NETWORK_LIMIT)
    ax.set_ylim(-_NETWORK_LIMIT, _NETWORK_LIMIT)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_network_diagram.svg"))


# ---------------------------------------------------------------------------
# Idiom: Table — ranked co-occurrence pairs
# ---------------------------------------------------------------------------

_TABLE_COLS       = ["Violation A", "Violation B", "Co-occ. Count", "% of Traces"]
_TABLE_COL_WIDTHS = [0.34, 0.34, 0.16, 0.16]


def task08_table(violation_freq, cooccurrence, n_traces, output_dir):
    if not cooccurrence:
        _no_violations(output_dir, "table")
        return

    rows = [
        [_short_label(_viol_label(a), 30),
         _short_label(_viol_label(b), 30),
         cnt,
         f"{cnt / n_traces * 100:.1f}%"]
        for (a, b), cnt in most_common_stable(cooccurrence, 20)
    ]

    fig_h = max(4, 0.38 * len(rows) + 1.5)
    fig   = plt.figure(figsize=(14, fig_h))
    ax    = fig.add_subplot(111)
    ax.axis("off")

    # shared.make_table, as every other task's table idiom draws one: the same
    # header colour, zebra shading and row height, so a participant comparing
    # table idioms across tasks is not also comparing two table designs.
    make_table(ax, cell_text=rows, col_labels=_TABLE_COLS,
               bbox=[0.02, 0.02, 0.96, 0.88], col_widths=_TABLE_COL_WIDTHS,
               cell_loc="left", cell_pad=0.08)

    # Centred, and named and captioned like the other three: the four are read
    # against each other, so the heading is not where they should differ.
    ax.set_title("Violation Co-occurrence Table\n"
                 "(count = traces containing both violations)",
                 fontsize=FONT_TITLE)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task08_table.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, alignments, output_dir: str, violation_patterns=None):
    """Generate all Task 8 SVGs into output_dir.

    ``violation_patterns`` — `log.violations` values — restricts the axes to
    those violations, and the pairs to those between two of them. Empty keeps
    the task's own top-N by trace coverage. A selection is never truncated: the
    axis grows to hold every pattern the admin named, since a cap silently
    dropping three of fifteen chosen patterns would answer a question nobody
    asked.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 8 visualizations (Violation co-occurrence patterns) ---")

    n_traces = len(log)
    violation_sets, violation_freq, cooccurrence = _extract_violation_data(alignments)

    selected = _selected_labels(violation_patterns)
    if selected:
        missing = selected - set(violation_freq)
        if missing:
            logger.warning(f"      task08: {len(missing)} selected pattern(s) do not "
                           f"occur in this log: {', '.join(sorted(missing))}")
        violation_freq, cooccurrence = _restrict_to_selection(
            violation_freq, cooccurrence, selected)
        logger.info(f"      -> restricted to {len(violation_freq)} selected pattern(s).")
    axis_n = len(selected) if selected else None

    n_with_viols = sum(1 for vs in violation_sets if vs)
    logger.info(f"      -> {n_with_viols} / {n_traces} traces have violations; "
                f"{len(violation_freq)} distinct violation types.")

    if not violation_freq:
        logger.warning("      Skipped Task 8: no violations found in any trace.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task08_{name}.svg",
                        "No guideline violations detected in this log")
        return

    # No co-occurrence threshold is drawn anywhere: no pair is flagged high or
    # low, so the analyst decides which correlations are noteworthy. Naming the
    # pairs worth looking at is what choosing the patterns does.
    task08_heatmap(violation_freq, cooccurrence, output_dir,
                   top_n=axis_n or _TOP_N)
    task08_matrix(violation_freq, cooccurrence, output_dir,
                  top_n=axis_n or _TOP_N)
    task08_network_diagram(violation_freq, cooccurrence, output_dir,
                           top_n=axis_n or _TOP_N)
    task08_table(violation_freq, cooccurrence, n_traces, output_dir)
