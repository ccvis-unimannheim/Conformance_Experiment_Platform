"""
shared.py – Cross-task utilities for the CC Visualization Pipeline.

Contains: color constants, save_svg, wrap_text, table helpers,
draw_decision_tree, tree position layout, and alignment parsing helpers
(_extract_alignment_label, alignment_pairs_to_rows, classify_step,
_task4_format_threshold).

All task modules import from here; this file must NOT import from any task module.
"""

import logging

logger = logging.getLogger(__name__)

import math
import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
from matplotlib.colors import to_hex

import numpy as np

# ---------------------------------------------------------------------------
# Cividis palette  – perceptually uniform, used throughout all visualizations.
# Named by semantic role; cividis runs dark-navy (0.0) → yellow-green (1.0).
# ---------------------------------------------------------------------------
CIVIDIS   = matplotlib.colormaps["cividis"]
CIVIDIS_R = matplotlib.colormaps["cividis_r"]  # reversed: 0=yellow, high=dark
_CIV      = CIVIDIS
GREY_DARK    = to_hex(_CIV(0.15))  # dark navy    (strongest emphasis / Log Move)
GREY_MED     = to_hex(_CIV(0.45))  # olive-grey   (primary category / Model Move)
GREY_LIGHT   = to_hex(_CIV(0.68))  # light olive  (secondary category / Mismatch)
GREY_LIGHTER = to_hex(_CIV(0.90))  # yellow-green (conformant / Synchronous)

# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def contrasting_text_color(hex_color: str) -> str:
    """Return '#ffffff' or '#1a1a1a' depending on the background luminance."""
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    # Perceived luminance (ITU-R BT.709)
    luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#ffffff" if luminance < 140 else "#1a1a1a"


# ---------------------------------------------------------------------------
# Typography constants – used across all task modules
# ---------------------------------------------------------------------------
FONT_TITLE = 13   # chart / section titles
FONT_LABEL = 10   # axis labels
FONT_ANNOT = 9    # data annotations, tick labels, legend text
FONT_TABLE = 9    # table cell content

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def save_svg(fig, path: str):
    fig.savefig(path, format="svg", bbox_inches="tight", pad_inches=0.15)
    plt.close(fig)
    logger.debug(f"      Saved: {path}")

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def wrap_text(text: str, width_chars: int, break_long_words: bool = False) -> str:
    """Wrap text for Matplotlib tables/nodes to prevent overflow."""
    text = "" if text is None else str(text)
    return textwrap.fill(
        text,
        width=width_chars,
        break_long_words=break_long_words,
        break_on_hyphens=False,
    )

# ---------------------------------------------------------------------------
# Table helpers
# ---------------------------------------------------------------------------

def style_table(
    table,
    ncols: int,
    nrows: int,
    header_rows: int = 1,
    header_color: str = GREY_DARK,
    zebra: bool = True,
    odd_color: str = "#FFFFFF",
    even_color: str = "#F0F0F0",
    highlight_last_row: bool = False,
    highlight_color: str = "#E4E4E4",
):
    """Apply consistent styling to Matplotlib tables."""
    for c in range(ncols):
        for r in range(header_rows):
            table[r, c].set_facecolor(header_color)
            table[r, c].set_text_props(color="white")

    start_r = header_rows
    for r in range(start_r, nrows):
        for c in range(ncols):
            if zebra:
                table[r, c].set_facecolor(even_color if r % 2 else odd_color)
            else:
                table[r, c].set_facecolor(even_color)

    if highlight_last_row and nrows > start_r:
        last = nrows - 1
        for c in range(ncols):
            table[last, c].set_facecolor(highlight_color)


def make_table(
    ax,
    cell_text,
    col_labels,
    bbox=None,
    col_widths=None,
    cell_loc: str = "center",
    font_size: float = FONT_TABLE,
    scale_xy=(1.0, 1.7),
    header_rows: int = 1,
    header_color: str = GREY_DARK,
    zebra: bool = True,
    highlight_last_row: bool = False,
    cell_pad: float = None,
):
    """Create a styled Matplotlib table with consistent defaults.

    cell_pad: optional uniform padding (in axes-relative units) applied to every
    cell. Useful when text would otherwise get clipped by the cell border.
    """
    kwargs = dict(cellText=cell_text, colLabels=col_labels, cellLoc=cell_loc)
    if bbox is not None:
        kwargs["bbox"] = bbox
    if col_widths is not None:
        kwargs["colWidths"] = col_widths
    tbl = ax.table(**kwargs)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(font_size)
    tbl.scale(scale_xy[0], scale_xy[1])
    if cell_pad is not None:
        for cell in tbl.get_celld().values():
            cell.PAD = cell_pad
    style_table(
        tbl,
        ncols=len(col_labels),
        nrows=len(cell_text) + header_rows,
        header_rows=header_rows,
        header_color=header_color,
        zebra=zebra,
        highlight_last_row=highlight_last_row,
    )
    return tbl

# ---------------------------------------------------------------------------
# Alignment parsing helpers
#
# Two levels of abstraction:
#   classify_step(obs_raw, exp_raw) -> (activity, type) | (None, None)
#       Low-level primitive.  Returns the activity name + one of:
#       "Move on Model" / "Move on Log" / "Mismatch Move".
#       Used by task09, task11, task12, task34, task35.
#
#   alignment_pairs_to_rows(alignment) -> list[dict]
#       High-level parser producing display rows with step/log_move/model_move/
#       status/moveType fields.  moveType uses the canonical Convention-A names:
#       "Synchronous Move" / "Model Move" / "Log Move" / "Mismatch Move".
#       Used by task05, task19, task20, task22, task23, task27, task28, task29, task30.
# ---------------------------------------------------------------------------

SKIP_ALIGNMENT_TOKENS = {">>", None}


def _extract_alignment_label(value):
    """Pull activity label from PM4Py alignment tuple side."""
    if isinstance(value, (list, tuple)):
        if len(value) >= 2 and not isinstance(value[1], (list, tuple, dict)):
            return None if value[1] is None else str(value[1])
        if len(value) >= 1 and not isinstance(value[-1], dict):
            return None if value[-1] is None else str(value[-1])
        return str(value)
    if value is None:
        return None
    return str(value)


def alignment_pairs_to_rows(alignment):
    """Convert PM4Py alignment list of pairs to table + chevron rows."""
    if not alignment:
        return []
    rows_out = []
    step_num = 0
    for raw_step in alignment:
        if not isinstance(raw_step, (list, tuple)) or len(raw_step) != 2:
            continue
        observed_raw, expected_raw = raw_step
        observed = _extract_alignment_label(observed_raw)
        expected = _extract_alignment_label(expected_raw)
        if observed in SKIP_ALIGNMENT_TOKENS and expected in SKIP_ALIGNMENT_TOKENS:
            continue
        step_num += 1
        if observed not in SKIP_ALIGNMENT_TOKENS and expected not in SKIP_ALIGNMENT_TOKENS and observed == expected:
            rows_out.append({
                "step": step_num, "log_move": observed, "model_move": expected,
                "status": "Conformant", "moveType": "Synchronous Move",
            })
        elif observed not in SKIP_ALIGNMENT_TOKENS and expected not in SKIP_ALIGNMENT_TOKENS:
            rows_out.append({
                "step": step_num, "log_move": observed, "model_move": expected,
                "status": "Deviation", "moveType": "Mismatch Move",
            })
        elif observed in SKIP_ALIGNMENT_TOKENS and expected not in SKIP_ALIGNMENT_TOKENS:
            rows_out.append({
                "step": step_num, "log_move": "(skip)", "model_move": expected,
                "status": "Deviation", "moveType": "Model Move",
            })
        else:
            rows_out.append({
                "step": step_num, "log_move": observed, "model_move": "None",
                "status": "Deviation", "moveType": "Log Move",
            })
    return rows_out


def classify_step(observed_raw, expected_raw):
    """Classify one PM4Py alignment step into (activity, violation_type) or (None, None).

    Naming convention used by task09, task11, task12, task34, task35:
        "Move on Model"  – activity required by the model but absent in the trace
        "Move on Log"    – extra activity present in the trace but not in the model
        "Mismatch Move"  – both present but with different labels
        (None, None)     – Synchronous Move (conformant) or tau/hidden transition
    """
    obs = (str(observed_raw) if observed_raw else "").strip()
    exp = (str(expected_raw) if expected_raw else "").strip()
    obs_skip = obs in (">>", "")
    exp_skip = exp in (">>", "")

    if obs_skip and exp_skip:
        return None, None
    if not obs_skip and not exp_skip:
        if obs == exp:
            return None, None
        return obs, "Mismatch Move"
    if obs_skip:
        return exp, "Move on Model"
    return obs, "Move on Log"


# ---------------------------------------------------------------------------
# Shared number formatter (used by task20 and task31)
# ---------------------------------------------------------------------------

def format_threshold(threshold: float) -> str:
    """Format a split threshold cleanly (integer if round, else 2dp stripped)."""
    if abs(threshold - round(threshold)) < 1e-6:
        return str(int(round(threshold)))
    return f"{threshold:.2f}".rstrip("0").rstrip(".")

# ---------------------------------------------------------------------------
# Decision-tree layout  (called by draw_decision_tree)
# ---------------------------------------------------------------------------

def assign_tree_positions(tree: dict, x_gap: float = 3.15, y_gap: float = 1.85):
    """Assign _x, _y layout coordinates to every node in a binary tree dict."""
    leaves = []
    max_depth = 0

    def collect(node):
        nonlocal max_depth
        max_depth = max(max_depth, node["depth"])
        if node.get("left") is None and node.get("right") is None:
            leaves.append(node)
            return
        collect(node["left"])
        collect(node["right"])

    collect(tree)
    leaf_positions = {node["id"]: idx * x_gap for idx, node in enumerate(leaves)}

    def assign(node):
        if node["id"] in leaf_positions:
            node["_x"] = leaf_positions[node["id"]]
        else:
            assign(node["left"])
            assign(node["right"])
            node["_x"] = (node["left"]["_x"] + node["right"]["_x"]) / 2.0
        node["_y"] = (max_depth - node["depth"]) * y_gap

    assign(tree)
    tree["_leaf_count"] = len(leaves)
    tree["_max_depth"] = max_depth
    tree["_x_gap"] = x_gap
    tree["_y_gap"] = y_gap

# ---------------------------------------------------------------------------
# Shared decision-tree renderer
# ---------------------------------------------------------------------------

def draw_decision_tree(
    ax,
    tree: dict,
    *,
    title: str,
    title_fontsize: float,
    title_pad: float,
    box_w: float,
    base_font: float,
    min_font: float,
    line_height: float,
    box_padding_h: float,
    wrap_width_fn,
    first_line_fn,
    value_pair_fn,
    node_facecolor_fn,
    legend_items=None,
    legend_kwargs=None,
    edge_arrowprops=None,
    edge_label_fontsize: float = 9,
    edge_label_offset_y: float = 0.16,
    edge_label_clearance: float = 0.0,
    edge_label_perp_offset: float = 0.0,
    x_pad_factor: float = 0.70,
    y_pad_base: float = 0.80,
    y_top_pad: float = 0.95,
    x_gap: float = 3.15,
    y_gap: float = 1.85,
):
    """Render a shallow decision tree with adaptive node height and wrapped text.

    edge_label_clearance:
        If > 0, push True/False edge labels at least this far away from any
        sibling edge endpoint to prevent overlapping labels in dense trees.
    edge_label_perp_offset:
        If > 0, shift each edge label perpendicular to its arrow by this amount,
        so the label sits beside (not on top of) the arrow line.
    x_gap, y_gap:
        Override the default leaf-spacing / level-spacing of the tree layout.
    """
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=title_fontsize, loc="left", pad=title_pad)

    if tree is None:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.text(0.5, 0.5, "No decision tree could be fitted.", ha="center", va="center", fontsize=11)
        return

    assign_tree_positions(tree, x_gap=x_gap, y_gap=y_gap)
    leaf_count = max(tree.get("_leaf_count", 1), 1)
    x_gap = tree.get("_x_gap", x_gap)
    max_depth = tree.get("_max_depth", 0)

    def node_text_lines(node):
        a, b = value_pair_fn(node)
        first = first_line_fn(node)
        first = wrap_text(first, width_chars=wrap_width_fn(first))
        return [
            first,
            f"gini = {node['gini']:.3f}",
            f"samples = {node['samples']}",
            f"value = [{a}, {b}]",
            f"class = {node['class']}",
        ]

    def node_text(node):
        return "\n".join(node_text_lines(node))

    def node_box_h(node) -> float:
        return box_padding_h + len(node_text_lines(node)) * line_height

    def max_text_complexity(node):
        lines = node_text_lines(node)
        max_lines = len(lines)
        max_len = max(len(part) for line in lines for part in line.splitlines())
        if node.get("left") is not None:
            l1, l2 = max_text_complexity(node["left"])
            max_lines = max(max_lines, l1)
            max_len = max(max_len, l2)
        if node.get("right") is not None:
            r1, r2 = max_text_complexity(node["right"])
            max_lines = max(max_lines, r1)
            max_len = max(max_len, r2)
        return max_lines, max_len

    def max_box_h(node) -> float:
        h = node_box_h(node)
        if node.get("left") is not None:
            h = max(h, max_box_h(node["left"]))
        if node.get("right") is not None:
            h = max(h, max_box_h(node["right"]))
        return h

    max_lines, max_line_len = max_text_complexity(tree)
    font_size = max(
        min_font,
        base_font
        - 0.25 * max(0, max_depth - 2)
        - 0.12 * max(0, leaf_count - 6)
        - 0.55 * max(0, max_lines - 6)
        - 0.06 * max(0, max_line_len - 26),
    )

    max_h = max_box_h(tree)
    ax.set_xlim(-box_w * x_pad_factor, (leaf_count - 1) * x_gap + box_w * x_pad_factor)
    ax.set_ylim(-y_pad_base - max_h * 0.15, max_depth * tree.get("_y_gap", 1.85) + y_top_pad + max_h * 0.20)

    if edge_arrowprops is None:
        edge_arrowprops = dict(arrowstyle="-|>", color="#555555", linewidth=1.35, shrinkA=5, shrinkB=5)

    def draw_edges(node):
        this_h = node_box_h(node)
        for side, label in [("left", "True"), ("right", "False")]:
            child = node.get(side)
            if child is None:
                continue
            child_h = node_box_h(child)
            arrow_start = (node["_x"], node["_y"] - this_h / 2)
            arrow_end   = (child["_x"], child["_y"] + child_h / 2)
            ax.annotate(
                "",
                xy=arrow_end,
                xytext=arrow_start,
                arrowprops=edge_arrowprops,
            )
            # Midpoint with optional vertical and clearance offsets
            mid_x = (arrow_start[0] + arrow_end[0]) / 2
            mid_y = (arrow_start[1] + arrow_end[1]) / 2 + edge_label_offset_y
            if edge_label_clearance > 0:
                # Push label vertically toward the parent so it sits well clear
                # of the child's box (helps in dense trees where labels collide)
                mid_y = mid_y + edge_label_clearance
            if edge_label_perp_offset > 0:
                # Shift label perpendicular to the edge: left edges shift left,
                # right edges shift right, keeping labels off the arrow line
                mid_x = mid_x + (-edge_label_perp_offset if side == "left" else edge_label_perp_offset)
            ax.text(
                mid_x, mid_y, label,
                ha="center", va="center",
                fontsize=edge_label_fontsize, color="#333333",
            )
            draw_edges(child)

    def draw_nodes(node):
        box_h = node_box_h(node)
        facecolor = node_facecolor_fn(node)
        patch = FancyBboxPatch(
            (node["_x"] - box_w / 2, node["_y"] - box_h / 2),
            box_w, box_h,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=facecolor,
            edgecolor="#555555",
            linewidth=1.15,
            alpha=0.96,
        )
        ax.add_patch(patch)
        ax.text(
            node["_x"], node["_y"],
            node_text(node),
            ha="center", va="center",
            fontsize=font_size, wrap=True,
            color=contrasting_text_color(facecolor),
        )
        if node.get("left") is not None:
            draw_nodes(node["left"])
        if node.get("right") is not None:
            draw_nodes(node["right"])

    draw_edges(tree)
    draw_nodes(tree)

    if legend_items:
        if legend_kwargs is None:
            legend_kwargs = {}
        ax.legend(handles=legend_items, **legend_kwargs)

# ---------------------------------------------------------------------------
# Shared Tile Metric renderer  (used by task02, task06 and task25)
# ---------------------------------------------------------------------------

def _draw_tile_box(ax):
    """Draw the rounded tile frame shared by all tile-metric variants."""
    ax.axis("off")
    ax.add_patch(FancyBboxPatch(
        (0.05, 0.05), 0.9, 0.9,
        boxstyle="round,pad=0.02", linewidth=2,
        edgecolor="black", facecolor="white",
        transform=ax.transAxes, clip_on=False,
    ))


def render_fitness_tile_metric(avg_fitness_pct: float, out_path: str,
                               threshold_pct: float = None, *,
                               metric_label: str = "Conformance Rate",
                               threshold_label: str = "Predominant threshold",
                               as_fraction: bool = False):
    """Render a single-value tile showing overall conformance rate and save to out_path.

    When ``threshold_pct`` is given, it is shown neutrally as a reference subline
    — no pass/fail verdict, so the reader judges for themselves. When omitted the
    tile keeps its original threshold-free appearance (task06). Colours stay
    greyscale.

    ``metric_label`` / ``threshold_label`` let a caller align the tile's wording
    with its other idioms (e.g. task02 uses "Mean Fitness" / "Fitness Threshold").
    ``as_fraction``: when True the value and threshold are treated as 0–1 fractions
    and rendered as e.g. "0.84" / "0.80"; otherwise they are percentages ("84%").
    """
    fig, ax = plt.subplots(figsize=(4, 3))
    _draw_tile_box(ax)
    ax.text(0.5, 0.72 if threshold_pct is not None else 0.68, metric_label,
            transform=ax.transAxes, ha="center", va="center",
            fontsize=FONT_TITLE, color="#555555")

    value_y = 0.45 if threshold_pct is not None else 0.38
    value_str = f"{avg_fitness_pct:.3f}" if as_fraction else f"{avg_fitness_pct:.2f}%"
    ax.text(0.5, value_y, value_str,
            transform=ax.transAxes, ha="center", va="center",
            fontsize=32, color="#333333")

    if threshold_pct is not None:
        thr_str = f"{threshold_pct:.2f}" if as_fraction else f"{threshold_pct:.0f}%"
        ax.text(0.5, 0.20,
                f"{threshold_label}: {thr_str}",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=FONT_LABEL, color="#555555")
    fig.tight_layout()
    save_svg(fig, out_path)


def render_counts_tile_metric(conform: int, non_conform: int, out_path: str,
                              title: str = "Trace Counts"):
    """Counts-only tile variant: raw conformant / non-conformant / total counts.

    Deliberately shows NO ratio or percentage (degree-discovery tasks must not
    hand the analyst the aggregated number).
    """
    total = conform + non_conform
    fig, ax = plt.subplots(figsize=(4, 3))
    _draw_tile_box(ax)
    ax.text(0.5, 0.80, title,
            transform=ax.transAxes, ha="center", va="center",
            fontsize=FONT_TITLE, color="#555555")
    rows = [
        ("Conformant traces", f"{conform}"),
        ("Non-conformant traces", f"{non_conform}"),
        ("Total traces", f"{total}"),
    ]
    for i, (label, value) in enumerate(rows):
        y = 0.58 - i * 0.17
        ax.text(0.13, y, label, transform=ax.transAxes,
                ha="left", va="center", fontsize=FONT_LABEL, color="#555555")
        ax.text(0.87, y, value, transform=ax.transAxes,
                ha="right", va="center", fontsize=FONT_TITLE + 2, color="#333333")
    fig.tight_layout()
    save_svg(fig, out_path)


def render_distribution_tile_metric(rows, out_path: str, title: str = "Distribution",
                                    caption: str = None):
    """Tile variant showing labelled rows (one (label, value) pair each).

    ``rows`` is a list of (label, value) pairs; row spacing adapts to their count
    so 2–7 rows all fit. ``caption`` adds a small line at the bottom (e.g. a
    derivation hint). The tile shows raw quantities only — NO single aggregate
    ratio/percentage — so a degree-discovery task can present the ingredients of
    the conformance rate (e.g. trace count + summed fitness) without handing the
    analyst the aggregated number; the analyst derives it themselves.
    """
    fig, ax = plt.subplots(figsize=(4, 3.2))
    _draw_tile_box(ax)
    ax.text(0.5, 0.88, title,
            transform=ax.transAxes, ha="center", va="center",
            fontsize=FONT_TITLE, color="#555555")
    n = max(len(rows), 1)
    top = 0.66
    bottom = 0.30 if caption else 0.12
    step = (top - bottom) / max(n - 1, 1) if n > 1 else 0.0
    for i, (label, value) in enumerate(rows):
        y = top - i * step
        ax.text(0.13, y, label, transform=ax.transAxes,
                ha="left", va="center", fontsize=FONT_LABEL, color="#555555")
        ax.text(0.87, y, value, transform=ax.transAxes,
                ha="right", va="center", fontsize=FONT_TITLE + 1, color="#333333")
    if caption:
        ax.text(0.5, 0.15, caption, transform=ax.transAxes,
                ha="center", va="center", fontsize=FONT_ANNOT, color="#777777",
                style="italic")
    fig.tight_layout()
    save_svg(fig, out_path)

# ---------------------------------------------------------------------------
# Shared zero-state renderer  (used by task23-style empty outputs)
# ---------------------------------------------------------------------------

def render_empty_state_svg(out_path: str, title: str, message: str = "No data available."):
    """Render a minimal placeholder SVG used when a task has no data to show."""
    fig, ax = plt.subplots(figsize=(7, 3.5))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=12, color="#888888", transform=ax.transAxes)
    ax.set_title(title, fontsize=FONT_TITLE)
    save_svg(fig, out_path)


def place_scatter_labels(ax, points, *, x_margin: float = 0.16, y_margin: float = 0.14,
                         cluster_x_frac: float = 0.08, gap_y_frac: float = 0.06,
                         dx_frac: float = 0.025, fontsize: float = None):
    """Annotate scatter points with non-overlapping, non-crossing callout labels.

    points: iterable of (x, y, text). Nearby points are grouped into clusters (by
    x proximity); within a cluster the labels are spread monotonically into the
    emptier vertical direction so the leader lines never cross and never swap a
    label onto the wrong dot. Labels for points in the right half are placed to the
    left (and vice versa) so they don't run off the canvas. Used by task18/task19's
    scatter idioms.
    """
    pts = [p for p in points if p is not None]
    if not pts:
        return
    if fontsize is None:
        fontsize = FONT_ANNOT - 1

    ax.margins(x=x_margin, y=y_margin)
    x0, x1 = ax.get_xlim()
    y0, y1 = ax.get_ylim()
    xr = (x1 - x0) or 1.0
    yr = (y1 - y0) or 1.0
    xmid = (x0 + x1) / 2.0
    ymid = (y0 + y1) / 2.0
    gap = yr * gap_y_frac
    dx = xr * dx_frac

    # Cluster by x proximity.
    ordered = sorted(pts, key=lambda p: p[0])
    clusters = []
    for p in ordered:
        if clusters and (p[0] - clusters[-1][-1][0]) <= xr * cluster_x_frac:
            clusters[-1].append(p)
        else:
            clusters.append([p])

    for cluster in clusters:
        cx = sum(p[0] for p in cluster) / len(cluster)
        cy = sum(p[1] for p in cluster) / len(cluster)
        to_right = cx < xmid
        placed = []
        if cy > ymid:
            # Cluster sits high — spread labels downward into the emptier space.
            prev = None
            for p in sorted(cluster, key=lambda p: p[1], reverse=True):
                ty = p[1] if prev is None else min(p[1], prev - gap)
                prev = ty
                placed.append((p, ty))
        else:
            prev = None
            for p in sorted(cluster, key=lambda p: p[1]):
                ty = p[1] if prev is None else max(p[1], prev + gap)
                prev = ty
                placed.append((p, ty))
        for (x, y, text), ty in placed:
            ax.annotate(
                text, (x, y),
                xytext=(x + (dx if to_right else -dx), ty), textcoords="data",
                ha="left" if to_right else "right", va="center",
                fontsize=fontsize, annotation_clip=False,
                bbox=dict(boxstyle="round,pad=0.18", fc="white", ec="#dddddd", lw=0.5, alpha=0.85),
                arrowprops=dict(arrowstyle="-", color="#aaaaaa", lw=0.6),
            )

# ---------------------------------------------------------------------------
# Shared variant aggregation  (used by task04, task25 and task27)
# ---------------------------------------------------------------------------

def build_variant_df(log, fitness_df, warn_prefix: str = "shared"):
    """Group traces by activity sequence; compute count, coverage, fitness per variant.

    Returns a DataFrame with columns:
        rank, variant, count, coverage, fitness, length, label, rep_trace_index
    sorted by count descending. rep_trace_index is the first trace index of the
    variant (usable to look up the variant's alignment).
    """
    import pandas as pd

    records = []
    for i, trace in enumerate(log):
        if i >= len(fitness_df):
            break
        seq = tuple(str(e.get("concept:name", "")) for e in trace)
        records.append({
            "trace_index": i,
            "variant":     seq,
            "length":      len(seq),
            "fitness":     float(fitness_df.iloc[i]["fitness"]),
        })

    columns = ["rank", "variant", "count", "coverage", "fitness",
               "length", "label", "rep_trace_index"]
    if not records:
        return pd.DataFrame(columns=columns)

    df = pd.DataFrame(records)
    total = len(df)

    groups = []
    for variant, sub in df.groupby("variant", sort=False):
        fits = sub["fitness"].values
        mean_fit = float(fits.mean())
        if fits.max() - fits.min() > 1e-6:
            logger.warning(
                f"{warn_prefix}: fitness not constant within variant "
                f"(len={len(variant)}, n={len(sub)}); using mean {mean_fit:.4f}"
            )
        groups.append({
            "variant":         variant,
            "count":           len(sub),
            "fitness":         mean_fit,
            "length":          int(sub["length"].iloc[0]),
            "rep_trace_index": int(sub["trace_index"].iloc[0]),
        })

    vdf = pd.DataFrame(groups).sort_values("count", ascending=False).reset_index(drop=True)
    vdf["rank"]     = vdf.index + 1
    vdf["coverage"] = vdf["count"] / total * 100
    vdf["label"]    = vdf["rank"].apply(lambda r: f"V{r}")
    return vdf


def variant_table_data(vdf, top_n: int, include_length: bool = False,
                       include_coverage: bool = True,
                       include_status: bool = False, rank_header: str = "Variant"):
    """Build (cell_text, col_labels, col_widths) for the shared variant table.

    Base columns: <rank_header> | #Traces | [Coverage (%)] | Fitness.
    include_coverage (default True) keeps the Coverage (%) column.
    include_length adds a Length column, include_status a Conformant/
    Non-conformant status column (✓ / ✗).
    """
    top = vdf.head(top_n)
    cell_text, col_labels = [], [rank_header, "#Traces"]
    col_widths = [0.16, 0.20]
    if include_coverage:
        col_labels.append("Coverage (%)")
        col_widths.append(0.22)
    col_labels.append("Fitness")
    col_widths.append(0.26)
    if include_length:
        col_labels.append("Length (#act.)")
        col_widths.append(0.22)
    if include_status:
        col_labels.append("Status")
        col_widths.append(0.28)
    # normalize widths
    s = sum(col_widths)
    col_widths = [w / s for w in col_widths]

    for _, row in top.iterrows():
        cells = [row["label"], str(int(row["count"]))]
        if include_coverage:
            cells.append(f"{row['coverage']:.1f}%")
        cells.append(f"{row['fitness']:.4f}")
        if include_length:
            cells.append(str(int(row["length"])))
        if include_status:
            conform = row["fitness"] >= 1.0
            cells.append("Conformant ✓" if conform else "Non-conformant ✗")
        cell_text.append(cells)
    return cell_text, col_labels, col_widths

# ---------------------------------------------------------------------------
# Shared violation pattern aggregation  (used by task23 and task26)
# ---------------------------------------------------------------------------

def build_violation_pattern_df(alignments):
    """Build per-pattern violation DataFrame from alignment results.

    Pattern = (activity, move_type), label "activity (move_type)" — the same
    classification task29/task05 use. Columns: pattern, activity, move_type,
    count, n_traces, pct; sorted by count descending.
    """
    import pandas as pd

    rows = []
    for trace_idx, result in enumerate(alignments):
        for step in alignment_pairs_to_rows(result.get("alignment", [])):
            if step["moveType"] == "Synchronous Move":
                continue
            activity = (step["model_move"] if step["moveType"] == "Model Move"
                        else step["log_move"])
            if not activity or activity in {"-", "None", "(skip)"}:
                continue
            rows.append({
                "trace_index": trace_idx,
                "move_type":   step["moveType"],
                "activity":    str(activity),
            })

    if not rows:
        return pd.DataFrame(columns=["pattern", "activity", "move_type",
                                     "count", "n_traces", "pct"])

    df = pd.DataFrame(rows)
    df["pattern"] = df["activity"] + " (" + df["move_type"] + ")"

    agg = (
        df.groupby(["pattern", "activity", "move_type"])
        .agg(count=("trace_index", "size"), n_traces=("trace_index", "nunique"))
        .reset_index()
        .sort_values("count", ascending=False)
        .reset_index(drop=True)
    )
    total = int(agg["count"].sum())
    agg["pct"] = agg["count"] / total * 100 if total else 0.0
    return agg

# ---------------------------------------------------------------------------
# Shared group-comparison renderers  (factored out of task05; also used by task30)
# ---------------------------------------------------------------------------

# Cividis shades used for pattern segments in composition stacked bars
COMPOSITION_GREYS = [to_hex(_CIV(0.10 + 0.80 * i / 9)) for i in range(10)]


def draw_grouped_rate_bars(ax, n_cats, group_labels, rates, group_colors,
                           horizontal: bool = False, width_total: float = 0.76):
    """Draw grouped bars: one bar group per category, one bar per group.

    rates: array-like of shape (n_cats, n_groups).
    Returns the category positions (for tick placement by the caller).
    """
    rates = np.asarray(rates, dtype=float)
    n_groups = len(group_labels)
    pos = np.arange(n_cats)
    bw = width_total / max(n_groups, 1)
    offsets = (np.arange(n_groups) - (n_groups - 1) / 2.0) * bw
    for gi, (label, color) in enumerate(zip(group_labels, group_colors)):
        vals = rates[:, gi]
        if horizontal:
            ax.barh(pos + offsets[gi], vals, bw, color=color, label=label,
                    edgecolor="white")
        else:
            ax.bar(pos + offsets[gi], vals, bw, color=color, label=label,
                   edgecolor="white")
    return pos


def draw_composition_stacked_bars(ax, group_labels, pattern_labels, rates,
                                  segment_colors=None):
    """One stacked bar per group; segments = patterns (legend entry once per pattern).

    rates: array-like of shape (n_patterns, n_groups).
    """
    rates = np.asarray(rates, dtype=float)
    if segment_colors is None:
        segment_colors = COMPOSITION_GREYS
    bottoms = {g: 0.0 for g in group_labels}
    for pi, pat in enumerate(pattern_labels):
        labeled = False
        for gi, g in enumerate(group_labels):
            h = float(rates[pi, gi])
            if h > 0:
                ax.bar(g, h, bottom=bottoms[g],
                       color=segment_colors[pi % len(segment_colors)],
                       edgecolor="white", linewidth=0.5,
                       label=pat if not labeled else "_nolegend_")
                labeled = True
            bottoms[g] += h


def draw_value_heatmap(fig, ax, data, row_labels, col_labels,
                       xlabel: str = "", cbar_label: str = "Rate (%)",
                       cell_fmt: str = "{:.1f}%", annotate: bool = True,
                       cmap=None, rotate_xticks: int = 0):
    """Colour-encoded matrix/heatmap with optional per-cell value labels + colorbar.

    Convention used across the platform: Matrix = annotated grid (annotate=True);
    Heatmap = continuous colour intensity (annotate=False).

    data: array-like of shape (len(row_labels), len(col_labels)).
    """
    import matplotlib as _mpl
    from matplotlib.colors import to_hex as _to_hex, Normalize as _Norm

    data = np.asarray(data, dtype=float)
    if cmap is None:
        cmap = CIVIDIS_R
    vmax = max(data.max(), 1.0) if data.size else 1.0
    im = ax.imshow(data, cmap=cmap, vmin=0, vmax=vmax, aspect="auto")

    ax.set_xticks(range(len(col_labels)))
    ax.set_xticklabels(col_labels, fontsize=FONT_ANNOT,
                       rotation=rotate_xticks, ha="right" if rotate_xticks else "center")
    ax.set_yticks(range(len(row_labels)))
    ax.set_yticklabels(row_labels, fontsize=FONT_ANNOT - 1)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=FONT_LABEL)

    if annotate:
        _cmap_obj = _mpl.colormaps[cmap] if isinstance(cmap, str) else cmap
        _norm = _Norm(vmin=0, vmax=vmax)
        for ri in range(len(row_labels)):
            for ci in range(len(col_labels)):
                val = data[ri, ci]
                cell_hex = _to_hex(_cmap_obj(_norm(val)))
                ax.text(ci, ri, cell_fmt.format(val),
                        ha="center", va="center", fontsize=FONT_ANNOT,
                        color=contrasting_text_color(cell_hex))

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.02)
    cbar.set_label(cbar_label, fontsize=FONT_ANNOT)
    return im


def draw_rate_matrix(fig, ax, data, row_labels, col_labels,
                     xlabel: str = "", cbar_label: str = "Rate (%)",
                     cell_fmt: str = "{:.1f}%"):
    """Annotated rate matrix — thin wrapper over draw_value_heatmap(annotate=True)."""
    return draw_value_heatmap(fig, ax, data, row_labels, col_labels,
                              xlabel=xlabel, cbar_label=cbar_label,
                              cell_fmt=cell_fmt, annotate=True)


def draw_grouped_box_plot(ax, data, labels, colors, *, ylabel: str = "",
                          ylim=(-0.05, 1.1), widths: float = 0.45):
    """Styled vertical box plot, one box per group, coloured per the group palette.

    data: list of 1-D arrays (one per group); empty arrays are tolerated.
    """
    boxes = ax.boxplot(
        data, vert=True, patch_artist=True, widths=widths,
        medianprops=dict(color="white", linewidth=2),
        flierprops=dict(marker="D", markersize=4, linestyle="none"),
    )
    for patch, whisker_pair, cap_pair, flier, color in zip(
            boxes["boxes"],
            zip(boxes["whiskers"][0::2], boxes["whiskers"][1::2]),
            zip(boxes["caps"][0::2], boxes["caps"][1::2]),
            boxes["fliers"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.85)
        # Dark outline so the box stays visible even when the distribution is
        # near-constant and the IQR collapses to ~zero height (otherwise the box
        # vanishes and only the white median line floats on the background).
        patch.set_edgecolor("#333333")
        patch.set_linewidth(1.2)
        for w in whisker_pair:
            w.set_color(color); w.set_linewidth(1.5)
        for c in cap_pair:
            c.set_color(color); c.set_linewidth(1.5)
        flier.set_markerfacecolor(color)
        flier.set_markeredgecolor(color)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=FONT_ANNOT)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=FONT_LABEL)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.5)
    ax.set_axisbelow(True)
    return boxes

# ---------------------------------------------------------------------------
# Shared time-series builder  (factored out of task07; also used by task01/04)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Conformance category buckets — single source of truth.
# Extracted from task10 so task01 / task25 / task27 / task33 (and task10's own
# idioms) share one definition of the conformance ranges.
# ---------------------------------------------------------------------------

# 1.01 upper edge so fitness == 1.0 lands in the last (left-closed) bucket.
CONFORMANCE_BINS = [0.0, 0.2, 0.4, 0.6, 0.8, 1.01]
CONFORMANCE_LABELS = ["0.0 – 0.2", "0.2 – 0.4", "0.4 – 0.6", "0.6 – 0.8", "0.8 – 1.0"]
CONFORMANCE_CATEGORY_NAMES = ["Very Low", "Low", "Medium", "High", "Very High"]


def make_conformance_labels(bins) -> list:
    """Human-readable "lo – hi" range labels for a list of conformance bin edges.

    The final upper edge is clamped to 1.0 for display (the canonical bins use a
    1.01 upper edge so fitness == 1.0 lands in the last left-closed bucket).
    """
    labels = []
    for lo, hi in zip(bins[:-1], bins[1:]):
        labels.append(f"{lo:.1f} – {min(float(hi), 1.0):.1f}")
    return labels


def conformance_category_index(fitness_value, bins=None) -> int:
    """Index of the conformance category for one fitness value.

    bins defaults to the canonical CONFORMANCE_BINS; pass a custom edge list to
    categorize against configurable buckets (n categories == len(bins) - 1).
    """
    b = bins if bins is not None else CONFORMANCE_BINS
    f = float(fitness_value)
    for i in range(len(b) - 1):
        if b[i] <= f < b[i + 1]:
            return i
    return len(b) - 2


def conformance_category_series(fitness, bins=None):
    """Per-value category index over the conformance buckets (canonical or custom)."""
    import pandas as pd
    return pd.Series([conformance_category_index(x, bins) for x in fitness], dtype=int)


def conformance_category_counts(fitness):
    """DataFrame [category, range, count, percentage] over the FIXED buckets."""
    import pandas as pd
    idx = conformance_category_series(fitness)
    total = len(idx)
    rows = []
    for i, (name, rng) in enumerate(zip(CONFORMANCE_CATEGORY_NAMES, CONFORMANCE_LABELS)):
        c = int((idx == i).sum())
        rows.append({"category": name, "range": rng, "count": c,
                     "percentage": (c / total * 100 if total else 0.0)})
    return pd.DataFrame(rows)


def build_fitness_time_series(log, fitness_df):
    """Merge per-trace fitness with trace start/end timestamps from the log.

    Returns a DataFrame with columns trace_index, fitness, is_fit, start_time,
    end_time; rows without a start timestamp are dropped, sorted by start_time.
    """
    import pandas as pd

    rows = []
    for _, row in fitness_df.iterrows():
        idx = int(row["trace_index"])
        try:
            trace = log[idx]
        except (IndexError, Exception):
            continue
        ts_start = trace[0].get("time:timestamp") if trace else None
        ts_end   = trace[-1].get("time:timestamp") if trace else None
        rows.append({
            "trace_index": idx,
            "fitness":     float(row["fitness"]),
            "is_fit":      bool(row["is_fit"]),
            "start_time":  pd.Timestamp(ts_start) if ts_start is not None else pd.NaT,
            "end_time":    pd.Timestamp(ts_end)   if ts_end   is not None else pd.NaT,
        })
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    return df.dropna(subset=["start_time"]).sort_values("start_time").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Shared conformance-over-time renderers (used by task07 and task10)
# ---------------------------------------------------------------------------

# Time-bin granularity -> pandas period frequency. All three share one code path
# (bin_fitness_time_series); only the date truncation differs.
TIME_GRANULARITY_FREQ = {"year": "Y", "month": "M", "day": "D"}
DEFAULT_TIME_GRANULARITY = "month"

# Per-granularity x-axis tick formatting for the conformance-over-time charts.
TIME_GRANULARITY_LABEL = {"year": "year", "month": "month", "day": "day"}


def apply_time_axis(ax, time_granularity: str = DEFAULT_TIME_GRANULARITY):
    """Set a date locator + formatter on ax.xaxis that matches the chosen bin
    granularity, so day/month/year bins are actually labelled as such instead of
    matplotlib's auto (always month-ish) ticks. Returns the normalised granularity."""
    import matplotlib.dates as mdates
    g = str(time_granularity).lower()
    if g == "day":
        loc, fmt = mdates.AutoDateLocator(), mdates.DateFormatter("%Y-%m-%d")
    elif g == "year":
        loc, fmt = mdates.YearLocator(), mdates.DateFormatter("%Y")
    else:  # month (default / fallback)
        g = "month"
        loc, fmt = mdates.MonthLocator(), mdates.DateFormatter("%b '%y")
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(fmt)
    return g


def bin_fitness_time_series(df, time_granularity: str = DEFAULT_TIME_GRANULARITY):
    """Aggregate per-trace fitness into fixed-granularity time bins.

    df: DataFrame with start_time + fitness columns (from build_fitness_time_series).
    time_granularity: "year" | "month" | "day" (falls back to month if unknown).
    Returns a DataFrame [time_bin, avg_fitness, n_traces].
    """
    freq = TIME_GRANULARITY_FREQ.get(str(time_granularity).lower(),
                                     TIME_GRANULARITY_FREQ[DEFAULT_TIME_GRANULARITY])
    df2 = df.copy()
    df2["time_bin"] = df2["start_time"].dt.to_period(freq).dt.to_timestamp()
    binned = (
        df2.groupby("time_bin")["fitness"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "avg_fitness", "count": "n_traces"})
        .reset_index()
    )
    return binned


def render_conformance_line_graph(df, out_path, *,
                                  time_granularity: str = DEFAULT_TIME_GRANULARITY,
                                  title: str = "Process Conformance Over Time",
                                  value_labels: bool = False):
    """Line graph of mean conformance per time bin (granularity-aware).

    value_labels: when True, annotate each marker with its mean-fitness percentage
    (opt-in so callers that prefer an uncluttered trend line are unaffected).
    """
    import matplotlib.ticker as _mticker

    if df is None or df.empty:
        render_empty_state_svg(out_path, title, "No timestamp data available")
        return

    binned = bin_fitness_time_series(df, time_granularity)
    if len(binned) < 2:
        render_empty_state_svg(out_path, title,
                               "Insufficient time range for trend line "
                               "(fewer than 2 time bins)")
        return

    fig, ax = plt.subplots(figsize=(12, 5))
    x = binned["time_bin"]
    y = binned["avg_fitness"]

    ax.fill_between(x, y, alpha=0.18, color=GREY_MED)
    ax.plot(x, y, color=GREY_MED, linewidth=1.8, marker="o", markersize=4)

    if value_labels:
        for xi, yi in zip(x, y):
            ax.annotate(f"{yi * 100:.1f}%", (xi, yi),
                        textcoords="offset points", xytext=(0, 7),
                        ha="center", va="bottom", fontsize=FONT_ANNOT - 1,
                        color=GREY_DARK)

    overall_mean = df["fitness"].mean()
    ax.axhline(overall_mean, color=GREY_LIGHT, linewidth=1.2,
               linestyle="--", label=f"Overall mean: {overall_mean:.2f}")

    g = apply_time_axis(ax, time_granularity)
    ax.set_ylim(-0.05, 1.1)
    ax.set_ylabel("Average Conformance Rate", fontsize=FONT_LABEL)
    ax.set_xlabel(f"Time (binned by {g})", fontsize=FONT_LABEL)
    ax.set_title(title, fontsize=FONT_TITLE)
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)
    ax.yaxis.set_major_formatter(_mticker.PercentFormatter(xmax=1.0))
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=FONT_ANNOT)

    fig.tight_layout()
    save_svg(fig, out_path)


def render_conformance_horizon_chart(df, out_path, *,
                                     time_granularity: str = DEFAULT_TIME_GRANULARITY,
                                     title: str = "Process Conformance Over Time",
                                     value_labels: bool = False):
    """Horizon chart: filled area above/below the overall mean (granularity-aware).

    Area above mean -> dark grey (higher conformance); below -> light grey.

    value_labels: when True, annotate each time bin with its mean-fitness
    percentage (same opt-in semantics as render_conformance_line_graph), so the
    horizon chart lets participants read off exact values like the line graph.
    """
    import matplotlib.ticker as _mticker

    if df is None or df.empty:
        render_empty_state_svg(out_path, title, "No timestamp data available")
        return

    binned = bin_fitness_time_series(df, time_granularity)
    if len(binned) < 2:
        render_empty_state_svg(out_path, title,
                               "Insufficient time range for horizon chart "
                               "(fewer than 2 time bins)")
        return

    mean_val = df["fitness"].mean()
    x = binned["time_bin"]
    y = binned["avg_fitness"]

    fig, ax = plt.subplots(figsize=(14, 5))

    ax.fill_between(x, mean_val, y, where=(y >= mean_val), interpolate=True,
                    color=GREY_DARK, alpha=0.75, label="Above mean (higher conformance)")
    ax.fill_between(x, mean_val, y, where=(y <= mean_val), interpolate=True,
                    color=GREY_LIGHTER, alpha=0.75, label="Below mean (lower conformance)")
    ax.plot(x, y, color="#444444", linewidth=0.9, alpha=0.5,
            marker="o", markersize=3)
    ax.axhline(mean_val, color="#555555", linewidth=1.2, linestyle="--")

    if value_labels:
        # Offset each label away from the mean line (up for above-mean bins,
        # down for below-mean) so it sits in the open area, not over the fill.
        for xi, yi in zip(x, y):
            above = yi >= mean_val
            ax.annotate(f"{yi * 100:.1f}%", (xi, yi),
                        textcoords="offset points",
                        xytext=(0, 7 if above else -7),
                        ha="center", va="bottom" if above else "top",
                        fontsize=FONT_ANNOT - 1, color=GREY_DARK)
    ax.annotate(f"Mean: {mean_val:.0%}", xy=(1.01, mean_val),
                xycoords=("axes fraction", "data"),
                fontsize=FONT_ANNOT, color="#555555", va="center")

    y_pad = max((y.max() - y.min()) * (0.28 if value_labels else 0.15), 0.02)
    ax.set_ylim(max(0.0, y.min() - y_pad), min(1.0, y.max() + y_pad))
    ax.yaxis.set_major_formatter(_mticker.PercentFormatter(xmax=1.0))

    g = apply_time_axis(ax, time_granularity)
    ax.set_ylabel("Conformance Rate", fontsize=FONT_LABEL)
    ax.set_xlabel(f"Time (binned by {g})", fontsize=FONT_LABEL)
    ax.set_title(title, fontsize=FONT_TITLE)
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT)
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=FONT_ANNOT, loc="lower left")

    fig.tight_layout()
    save_svg(fig, out_path)


# ---------------------------------------------------------------------------
# Shared calendar heatmap  (GitHub-style weekday × week grid of a daily metric)
# ---------------------------------------------------------------------------

def draw_calendar_heatmap(ax, daily, *, cmap=None, vmin=0.0, vmax=None,
                          empty_color="#F4F4F4"):
    """Draw a weekday(row) × week(col) calendar heatmap of a daily metric onto ax.

    daily: mapping/Series of (date-like -> value). Missing days render as empty.
    Returns the imshow handle (or None when there is no data).
    """
    import pandas as pd

    items = list(daily.items()) if hasattr(daily, "items") else list(daily)
    points = []
    for d, v in items:
        ts = pd.Timestamp(d).normalize()
        points.append((ts, float(v)))
    if not points:
        ax.axis("off")
        ax.text(0.5, 0.5, "No dated data.", ha="center", va="center",
                fontsize=FONT_ANNOT, color="#888888", transform=ax.transAxes)
        return None

    points.sort(key=lambda p: p[0])
    start = points[0][0] - pd.Timedelta(days=int(points[0][0].weekday()))
    n_weeks = int((points[-1][0] - start).days // 7) + 1

    grid = np.full((7, n_weeks), np.nan)
    for ts, val in points:
        week = int((ts - start).days // 7)
        grid[int(ts.weekday()), week] = val

    if vmax is None:
        finite = grid[np.isfinite(grid)]
        vmax = float(finite.max()) if finite.size else 1.0
    vmax = max(vmax, vmin + 1e-9)

    from matplotlib.colors import LinearSegmentedColormap as _LSC
    if cmap is None:
        cmap = _LSC.from_list("shared_calendar", ["#F0F0F0", "#333333"])
    cmap = cmap.copy() if hasattr(cmap, "copy") else cmap
    masked = np.ma.masked_invalid(grid)
    try:
        cmap.set_bad(empty_color)
    except Exception:
        pass
    im = ax.imshow(masked, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")

    ax.set_yticks(range(7))
    ax.set_yticklabels(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                       fontsize=FONT_ANNOT - 2)
    # Month label at the first week whose Monday starts a new month
    month_ticks, month_labels = [], []
    last_month = None
    for w in range(n_weeks):
        monday = start + pd.Timedelta(weeks=w)
        if monday.month != last_month:
            month_ticks.append(w)
            month_labels.append(monday.strftime("%b '%y"))
            last_month = monday.month
    ax.set_xticks(month_ticks)
    ax.set_xticklabels(month_labels, fontsize=FONT_ANNOT - 2, rotation=30, ha="right")
    ax.tick_params(length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    return im


def calendar_heatmap(daily, out_path, *, title, cbar_label, cmap=None,
                     vmin=0.0, vmax=None):
    """Single-calendar figure wrapper around draw_calendar_heatmap."""
    fig, ax = plt.subplots(figsize=(12, 2.6))
    im = draw_calendar_heatmap(ax, daily, cmap=cmap, vmin=vmin, vmax=vmax)
    ax.set_title(title, fontsize=FONT_TITLE, pad=8)
    if im is not None:
        cbar = fig.colorbar(im, ax=ax, fraction=0.025, pad=0.02)
        cbar.set_label(cbar_label, fontsize=FONT_ANNOT)
    fig.tight_layout()
    save_svg(fig, out_path)


def calendar_small_multiples(group_to_daily, out_path, *, title, cbar_label,
                             cmap=None, vmin=0.0, vmax=None):
    """Stacked small-multiple calendars (one row per group) sharing a colour scale."""
    import pandas as pd

    groups = list(group_to_daily.keys())
    if not groups:
        render_empty_state_svg(out_path, title, "No dated data.")
        return
    if vmax is None:
        all_vals = [float(v) for s in group_to_daily.values()
                    for v in (s.values() if hasattr(s, "values") else dict(s).values())]
        vmax = max(all_vals) if all_vals else 1.0
    fig, axes = plt.subplots(len(groups), 1,
                             figsize=(12, max(2.8, 2.4 * len(groups))), squeeze=False)
    last_im = None
    for ax, g in zip(axes[:, 0], groups):
        im = draw_calendar_heatmap(ax, group_to_daily[g], cmap=cmap, vmin=vmin, vmax=vmax)
        ax.set_title(str(g), fontsize=FONT_ANNOT + 1, loc="left", pad=12)
        last_im = im if im is not None else last_im
    fig.suptitle(title, fontsize=FONT_TITLE, y=0.99)
    if last_im is not None:
        cbar = fig.colorbar(last_im, ax=axes[:, 0].tolist(), fraction=0.02, pad=0.02)
        cbar.set_label(cbar_label, fontsize=FONT_ANNOT)
    save_svg(fig, out_path)

# ---------------------------------------------------------------------------
# Shared Gantt strips  (small-multiple horizontal event-span strips)
# ---------------------------------------------------------------------------

def draw_gantt_strips(ax, rows, *, min_frac: float = 0.012):
    """Draw event-span strips: one row per trace; a bar spans each consecutive
    event-timestamp pair (event -> next event).

    rows: list of {"label": str, "color": color, "times": [Timestamp, ...]}.
    Rows with fewer than 2 timestamps still get a thin marker bar.
    """
    import matplotlib.dates as mdates
    import pandas as pd

    valid = [r for r in rows if r.get("times")]
    if not valid:
        ax.axis("off")
        ax.text(0.5, 0.5, "No timestamped traces.", ha="center", va="center",
                fontsize=FONT_ANNOT, color="#888888", transform=ax.transAxes)
        return

    all_nums = []
    for r in valid:
        nums = [mdates.date2num(pd.Timestamp(t)) for t in r["times"]]
        r["_nums"] = nums
        all_nums.extend(nums)
    span = max(max(all_nums) - min(all_nums), 1e-6)
    min_w = span * min_frac

    for i, r in enumerate(valid):
        nums = r["_nums"]
        color = r["color"]
        if len(nums) >= 2:
            for a, b in zip(nums, nums[1:]):
                w = max(b - a, min_w)
                ax.barh(i, w, left=a, height=0.6, color=color,
                        edgecolor="white", linewidth=0.6, alpha=0.9)
        else:
            ax.barh(i, min_w, left=nums[0], height=0.6, color=color,
                    edgecolor="white", linewidth=0.6, alpha=0.9)

    ax.set_yticks(range(len(valid)))
    ax.set_yticklabels([r["label"] for r in valid], fontsize=FONT_ANNOT - 1)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)
    ax.xaxis_date()
    ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
    ax.tick_params(axis="x", labelrotation=30, labelsize=FONT_ANNOT - 1)
    ax.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)

# ---------------------------------------------------------------------------
# Shared BPMN parse + annotated renderer  (factored out of task24; used by task25/26)
# ---------------------------------------------------------------------------

_BPMN_NS = {
    "bpmn":   "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc":     "http://www.omg.org/spec/DD/20100524/DC",
    "di":     "http://www.omg.org/spec/DD/20100524/DI",
}


def parse_bpmn_model(model_path: str) -> dict:
    """Parse a BPMN file into geometry usable by the annotated renderer.

    Returns dict with: elements, sequence_flows, shapes, edge_pts, name_to_ids.
    Applies the same coordinate normalisation task24/task28 use (box expansion,
    gateway resize, edge orthogonalisation, endpoint inset).
    """
    import math
    import xml.etree.ElementTree as ET

    def _nc(b):
        return b["x"] + b["width"] / 2.0, b["y"] + b["height"] / 2.0

    def _adj_ep(pt, nxt, eid, sh):
        if eid not in sh:
            return pt
        b = sh[eid]; cx, cy = _nc(b)
        dx, dy = nxt[0] - pt[0], nxt[1] - pt[1]
        if abs(dx) >= abs(dy):
            return (b["x"] + (b["width"] if dx > 0 else 0), cy)
        return (cx, b["y"] + (b["height"] if dy > 0 else 0))

    def _ortho(pts):
        if len(pts) < 2:
            return list(pts)
        out = [pts[0]]; tol = 1e-6
        for i in range(1, len(pts)):
            ax, ay = out[-1]; bx, by = pts[i]
            if abs(ax - bx) < tol and abs(ay - by) < tol:
                continue
            if abs(ax - bx) < tol or abs(ay - by) < tol:
                if abs(bx - out[-1][0]) > tol or abs(by - out[-1][1]) > tol:
                    out.append((bx, by))
                continue
            mid = (bx, ay) if abs(bx - ax) >= abs(by - ay) else (ax, by)
            if abs(mid[0] - out[-1][0]) > tol or abs(mid[1] - out[-1][1]) > tol:
                out.append(mid)
            if (abs(mid[0] - bx) > tol or abs(mid[1] - by) > tol) and \
               (abs(bx - out[-1][0]) > tol or abs(by - out[-1][1]) > tol):
                out.append((bx, by))
        if len(out) < 3:
            return out
        simp = [out[0]]
        for j in range(1, len(out) - 1):
            ax, ay = simp[-1]; bx, by = out[j]; cx, cy = out[j + 1]
            if abs((bx - ax) * (cy - ay) - (by - ay) * (cx - ax)) > 1e-3:
                simp.append(out[j])
        simp.append(out[-1])
        return simp

    def _inset(tgt_id, pts, elems, sh):
        if len(pts) < 2 or tgt_id not in sh:
            return pts
        elem = elems.get(tgt_id)
        if not elem or elem["kind"] != "endEvent":
            return pts
        px, py = pts[-2]; bx, by = pts[-1]
        dlen = math.hypot(bx - px, by - py)
        if dlen < 1e-9:
            return pts
        t = min(16.0, dlen * 0.92)
        ux, uy = (bx - px) / dlen, (by - py) / dlen
        return pts[:-1] + [(bx - ux * t, by - uy * t)]

    def _dedup(pts, tol=0.05):
        if not pts:
            return pts
        out = [pts[0]]
        for p in pts[1:]:
            if abs(p[0] - out[-1][0]) > tol or abs(p[1] - out[-1][1]) > tol:
                out.append(p)
        return out

    root = ET.parse(model_path).getroot()
    elements = {}; sequence_flows = {}

    for elem in root.findall(".//bpmn:*", _BPMN_NS):
        eid = elem.attrib.get("id")
        if not eid:
            continue
        kind = elem.tag.split("}", 1)[-1] if "}" in elem.tag else elem.tag
        if kind in {"task", "startEvent", "endEvent", "exclusiveGateway", "parallelGateway"}:
            elements[eid] = {"id": eid, "kind": kind,
                             "name": elem.attrib.get("name", ""),
                             "direction": elem.attrib.get("gatewayDirection", "")}
        elif kind == "sequenceFlow":
            sequence_flows[eid] = {"id": eid,
                                   "source": elem.attrib.get("sourceRef"),
                                   "target": elem.attrib.get("targetRef")}

    shapes = {}
    for shape in root.findall(".//bpmndi:BPMNShape", _BPMN_NS):
        eid = shape.attrib.get("bpmnElement")
        b = shape.find("dc:Bounds", _BPMN_NS)
        if eid and b is not None:
            shapes[eid] = {k: float(b.attrib[k]) for k in ("x", "y", "width", "height")}

    for eid, b in list(shapes.items()):
        elem = elements.get(eid)
        if not elem or elem["kind"] != "task":
            continue
        name = elem["name"]
        mw = min(max(b["width"], 90.0, 28.0 + len(name) * 4.6), 138.0)
        mh = max(b["height"], 46.0)
        if mw > b["width"]:
            cx, _ = _nc(b); b["x"] = cx - mw / 2.0; b["width"] = mw
        if mh > b["height"]:
            _, cy = _nc(b); b["y"] = cy - mh / 2.0; b["height"] = mh

    for eid, b in list(shapes.items()):
        elem = elements.get(eid)
        if not elem or elem["kind"] not in {"exclusiveGateway", "parallelGateway"}:
            continue
        nw, nh = max(b["width"], 36.0), max(b["height"], 36.0)
        if abs(nw - b["width"]) > 0.5 or abs(nh - b["height"]) > 0.5:
            cx, cy = _nc(b)
            b.update({"width": nw, "height": nh, "x": cx - nw / 2.0, "y": cy - nh / 2.0})

    edge_pts = {}
    for edge in root.findall(".//bpmndi:BPMNEdge", _BPMN_NS):
        fid = edge.attrib.get("bpmnElement")
        pts = [(float(wp.attrib["x"]), float(wp.attrib["y"]))
               for wp in edge.findall("di:waypoint", _BPMN_NS)]
        if fid and pts:
            edge_pts[fid] = pts

    for fid, pts in list(edge_pts.items()):
        flow = sequence_flows.get(fid)
        if not flow or len(pts) < 2:
            continue
        pts = list(pts)
        pts[0]  = _adj_ep(pts[0],  pts[1],  flow["source"], shapes)
        pts[-1] = _adj_ep(pts[-1], pts[-2], flow["target"], shapes)
        pts = _ortho(pts)
        pts = _inset(flow["target"], pts, elements, shapes)
        pts = _dedup(pts)
        edge_pts[fid] = pts

    name_to_ids = {}
    for eid, elem in elements.items():
        if elem["name"]:
            name_to_ids.setdefault(elem["name"], []).append(eid)

    return {"elements": elements, "sequence_flows": sequence_flows,
            "shapes": shapes, "edge_pts": edge_pts, "name_to_ids": name_to_ids}


def _bpmn_label_lines(label, box_width, font_size=9) -> list:
    """Wrap an activity label into up to 3 lines that fit a box width."""
    import html as _html  # noqa: F401 (kept for parity; escaping done by caller)

    def _wrap(text, max_chars):
        words = str(text).replace("_", "_ ").split()
        lines, cur = [], ""
        for w in words:
            cand = w if not cur else f"{cur} {w}"
            if len(cand) <= max_chars:
                cur = cand
            else:
                if cur:
                    lines.append(cur.replace("_ ", "_"))
                cur = w
        if cur:
            lines.append(cur.replace("_ ", "_"))
        return lines or [str(text)]
    mc = max(7, int((box_width - 14) / (font_size * 0.58)))
    lines = _wrap(label, mc)
    if len(lines) > 3:
        mc2 = max(9, int((box_width - 12) / (font_size * 0.50)))
        s = str(label)
        lines = [s[i:i + mc2] for i in range(0, len(s), mc2)]
    return lines[:3]


def _bpmn_esc(v):
    import html
    return html.escape("" if v is None else str(v), quote=True)


_BPMN_MARKER_DEFS = (
    "<defs>"
    '<marker id="arrow-grey" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="10" '
    'markerHeight="10" orient="auto" markerUnits="userSpaceOnUse">'
    '<path d="M0,1 L10,5 L0,9 Z" fill="#444444"/></marker>'
    '<marker id="arrow-faded" viewBox="0 0 10 10" refX="10" refY="5" markerWidth="8" '
    'markerHeight="8" orient="auto" markerUnits="userSpaceOnUse">'
    '<path d="M0,1 L10,5 L0,9 Z" fill="#AAAAAA"/></marker>'
    "</defs>"
)


def bpmn_diagram_body(parsed, node_style_fn, faded_flow_fn=None, *, ox=0.0, oy=0.0,
                      top_pad=88.0):
    """Return (svg_lines, width, height) for one BPMN diagram translated by (ox, oy).

    The body excludes the outer <svg>, marker <defs> and legend so it can be
    composed into single- or multi-panel figures.
    """
    elements = parsed["elements"]; shapes = parsed["shapes"]; edge_pts = parsed["edge_pts"]
    if not shapes:
        return [], 0.0, 0.0
    xs, ys = [], []
    for b in shapes.values():
        xs += [b["x"], b["x"] + b["width"]]; ys += [b["y"], b["y"] + b["height"]]
    for eid, b in shapes.items():
        if elements.get(eid, {}).get("kind") == "endEvent":
            xs.append(b["x"] + b["width"] / 2.0 + min(b["width"], b["height"]) / 2.0 + 88.0)
    for pts in edge_pts.values():
        for px, py in pts:
            xs.append(px); ys.append(py)
    if not xs or not ys:
        return [], 0.0, 0.0

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    lp, rp, bp = 80.0, 80.0, 68.0
    W = max_x - min_x + lp + rp
    H = max_y - min_y + top_pad + bp

    def tx(x): return x - min_x + lp + ox
    def ty(y): return y - min_y + top_pad + oy

    def _clean_pts(pts, min_seg=10.0):
        """Drop penultimate points that create a tiny final segment.
        A tiny final segment (< min_seg units) makes orient=auto point the
        arrowhead in the wrong direction instead of the main travel direction."""
        clean = list(pts)
        while len(clean) >= 3:
            x1, y1 = clean[-2]
            x2, y2 = clean[-1]
            if math.hypot(x2 - x1, y2 - y1) < min_seg:
                clean.pop(-2)
            else:
                break
        return clean

    out = []
    for fid, pts in edge_pts.items():
        pts = _clean_pts(pts)
        pts_str = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in pts)
        if faded_flow_fn is not None and faded_flow_fn(fid):
            out.append(
                f'<polyline points="{pts_str}" fill="none" stroke="#AAAAAA" stroke-width="1.5" '
                f'stroke-dasharray="5 4" stroke-linejoin="miter" marker-end="url(#arrow-faded)"/>'
            )
        else:
            out.append(
                f'<polyline points="{pts_str}" fill="none" stroke="#444444" stroke-width="1.5" '
                f'stroke-linejoin="miter" stroke-linecap="butt" marker-end="url(#arrow-grey)"/>'
            )

    for eid, b in shapes.items():
        elem = elements.get(eid, {"kind": "task", "name": ""})
        kind = elem["kind"]; name = elem.get("name", "")
        x, y, w, h = tx(b["x"]), ty(b["y"]), b["width"], b["height"]
        # node_style_fn may return a 4-tuple (fill, stroke, stroke_width,
        # text_color) or, optionally, a 5-tuple whose last element is an SVG
        # stroke-dasharray string (e.g. "6 4") used to draw a dashed node
        # outline. None/"" keeps the outline solid (backward compatible).
        style = node_style_fn(eid, elem)
        fill, stroke, sw, tc = style[0], style[1], style[2], style[3]
        dash = style[4] if len(style) > 4 else None
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""

        if kind == "task":
            out.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'rx="7" ry="7" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash_attr}/>'
            )
            lines = _bpmn_label_lines(name, w)
            gap = 10.5; sy = y + h / 2.0 - (len(lines) - 1) * gap / 2.0
            for i, line in enumerate(lines):
                out.append(
                    f'<text x="{x + w / 2.0:.1f}" y="{sy + i * gap:.1f}" text-anchor="middle" '
                    f'dominant-baseline="middle" font-family="Arial, sans-serif" font-size="9" '
                    f'fill="{tc}">{_bpmn_esc(line)}</text>'
                )
        elif kind in {"exclusiveGateway", "parallelGateway"}:
            cx, cy = x + w / 2.0, y + h / 2.0
            pts_str = f"{cx:.1f},{y:.1f} {x+w:.1f},{cy:.1f} {cx:.1f},{y+h:.1f} {x:.1f},{cy:.1f}"
            out.append(f'<polygon points="{pts_str}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{dash_attr}/>')
            marker = "+" if kind == "parallelGateway" else "X"
            g_fs = max(13.0, min(w, h) * 0.34)
            out.append(
                f'<text x="{cx:.1f}" y="{cy + 0.5:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle" font-family="Arial, sans-serif" '
                f'font-size="{g_fs:.1f}" fill="{stroke}">{marker}</text>'
            )
        elif kind in {"startEvent", "endEvent"}:
            cx, cy = x + w / 2.0, y + h / 2.0; r = min(w, h) / 2.0
            sw2 = 3 if kind == "endEvent" else 2
            out.append(
                f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" '
                f'stroke="{stroke}" stroke-width="{sw2}"{dash_attr}/>'
            )
            if kind == "startEvent":
                out.append(
                    f'<text x="{cx:.1f}" y="{cy + h / 2.0 + 18.0:.1f}" text-anchor="middle" '
                    f'font-family="Arial, sans-serif" font-size="9" fill="{stroke}">START</text>'
                )
            else:
                out.append(
                    f'<text x="{cx + r + 10.0:.1f}" y="{cy:.1f}" text-anchor="start" '
                    f'dominant-baseline="middle" font-family="Arial, sans-serif" '
                    f'font-size="9" fill="{stroke}">END EVENT</text>'
                )
    return out, W, H


def _bpmn_legend_lines(legend_items, y, x0=24.0):
    out = []
    for i, item in enumerate(legend_items):
        # Legend item is (fill, stroke, stroke_width, label) or, optionally, a
        # 5-tuple whose last element is an SVG stroke-dasharray for a dashed
        # swatch outline (mirrors node_style_fn's optional 5th element).
        lf, ls, lsw, lbl = item[0], item[1], item[2], item[3]
        ldash = item[4] if len(item) > 4 else None
        ldash_attr = f' stroke-dasharray="{ldash}"' if ldash else ""
        lx = x0 + i * 265
        out.append(
            f'<rect x="{lx:.1f}" y="{y - 11:.1f}" width="22" height="12" '
            f'fill="{lf}" stroke="{ls}" stroke-width="{lsw}"{ldash_attr}/>'
        )
        out.append(
            f'<text x="{lx + 30:.1f}" y="{y:.1f}" font-family="Arial, sans-serif" '
            f'font-size="9" fill="#222">{_bpmn_esc(lbl)}</text>'
        )
    return out


def render_bpmn_annotated(parsed, out_path, *, title, summary,
                          node_style_fn, legend_items, faded_flow_fn=None,
                          legend_center=True):
    """Render a BPMN model to a standalone SVG with per-node annotation styling.

    node_style_fn(eid, elem) -> (fill, stroke, stroke_width, text_color)
    faded_flow_fn(flow_id) -> bool   (optional; draw the flow faded/dashed)
    legend_center: horizontally centre the legend strip on the canvas (default).
    """
    body, W, H = bpmn_diagram_body(parsed, node_style_fn, faded_flow_fn, top_pad=88.0)
    if not body:
        render_empty_state_svg(out_path, title, "No BPMN geometry to render.")
        return
    H_total = H + 22  # room for the legend strip
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H_total:.1f}" '
        f'viewBox="0 0 {W:.1f} {H_total:.1f}">',
        _BPMN_MARKER_DEFS,
        '<rect x="0" y="0" width="100%" height="100%" fill="white"/>',
        f'<text x="24" y="44" font-family="Arial, sans-serif" font-size="13" '
        f'fill="black">{_bpmn_esc(title)}</text>',
        f'<text x="24" y="67" font-family="Arial, sans-serif" font-size="10" '
        f'fill="#555">{_bpmn_esc(summary)}</text>',
    ]
    out += body
    span = 265.0 * (len(legend_items) - 1) + 140.0
    lx0 = max(24.0, (W - span) / 2.0) if legend_center else 24.0
    out += _bpmn_legend_lines(legend_items, H_total - 16, x0=lx0)
    out.append("</svg>")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    logger.debug(f"      Saved: {out_path}")


def compose_bpmn_panels(panels, out_path, *, title, legend_items,
                        table_rows=None, table_cols=None,
                        legend_below_panels=True, legend_center=True,
                        table_stretch: bool = False,
                        table_header_bg: str = GREY_DARK):
    """Compose several BPMN panels (stacked vertically) + an optional table into one SVG.

    panels: list of {"parsed", "node_style_fn", "faded_flow_fn"(opt), "subtitle"}.
    table_rows/table_cols: optional comparison table rendered beneath the panels.
    legend_below_panels: place the legend strip between the diagram and the table
        (default) rather than at the very bottom of the canvas.
    legend_center: horizontally centre the legend strip on the canvas (default).
    """
    panel_gap = 26.0
    y_cursor = 64.0  # below the main title
    bodies, max_w = [], 0.0
    for p in panels:
        sub = p.get("subtitle", "")
        bodies.append(
            f'<text x="24" y="{y_cursor + 16:.1f}" font-family="Arial, sans-serif" '
            f'font-size="11" fill="#333">{_bpmn_esc(sub)}</text>'
        )
        body, w, h = bpmn_diagram_body(
            p["parsed"], p["node_style_fn"], p.get("faded_flow_fn"),
            oy=y_cursor + 24.0, top_pad=8.0,
        )
        bodies += body
        max_w = max(max_w, w)
        y_cursor += 24.0 + h + panel_gap

    # Optionally reserve a legend strip directly below the diagram (above table).
    legend_below_y = None
    if legend_below_panels:
        legend_below_y = y_cursor + 8.0
        y_cursor += 30.0

    table_lines = []
    if table_rows and table_cols:
        col_w = max(200.0, max_w / len(table_cols)) if table_stretch else 200.0
        row_h = 22.0
        table_total_w = col_w * len(table_cols)
        # Pre-compute canvas width so we can center the table horizontally
        legend_min_w = 24.0 + 265.0 * len(legend_items)
        canvas_w = max(max_w, legend_min_w)
        tx0 = max(24.0, (canvas_w - table_total_w) / 2.0)
        ty0 = y_cursor + 6.0
        table_lines.append(
            f'<rect x="{tx0:.1f}" y="{ty0:.1f}" '
            f'width="{table_total_w:.1f}" height="{row_h:.1f}" fill="{table_header_bg}"/>'
        )
        for ci, col in enumerate(table_cols):
            table_lines.append(
                f'<text x="{tx0 + ci * col_w + 8:.1f}" y="{ty0 + 15:.1f}" '
                f'font-family="Arial, sans-serif" font-size="10" fill="white">{_bpmn_esc(col)}</text>'
            )
        for ri, row in enumerate(table_rows):
            ry = ty0 + (ri + 1) * row_h
            bg = "#F0F0F0" if ri % 2 else "#FFFFFF"
            table_lines.append(
                f'<rect x="{tx0:.1f}" y="{ry:.1f}" '
                f'width="{table_total_w:.1f}" height="{row_h:.1f}" '
                f'fill="{bg}" stroke="#E0E0E0" stroke-width="0.5"/>'
            )
            for ci, cell in enumerate(row):
                table_lines.append(
                    f'<text x="{tx0 + ci * col_w + 8:.1f}" y="{ry + 15:.1f}" '
                    f'font-family="Arial, sans-serif" font-size="9.5" '
                    f'fill="#222">{_bpmn_esc(cell)}</text>'
                )
        y_cursor = ty0 + (len(table_rows) + 1) * row_h
        max_w = max(max_w, tx0 + table_total_w)

    H_total = y_cursor + 34.0
    W = max(max_w, 24.0 + 265.0 * len(legend_items))
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H_total:.1f}" '
        f'viewBox="0 0 {W:.1f} {H_total:.1f}">',
        _BPMN_MARKER_DEFS,
        '<rect x="0" y="0" width="100%" height="100%" fill="white"/>',
        f'<text x="24" y="40" font-family="Arial, sans-serif" font-size="13" '
        f'fill="black">{_bpmn_esc(title)}</text>',
    ]
    def _legend_x0():
        if not legend_center:
            return 24.0
        # Legend items are laid out on a fixed 265px stride; estimate the strip
        # span and centre it on the canvas.
        span = 265.0 * (len(legend_items) - 1) + 140.0
        return max(24.0, (W - span) / 2.0)

    out += bodies
    out += table_lines
    legend_y = legend_below_y if legend_below_y is not None else (H_total - 14)
    out += _bpmn_legend_lines(legend_items, legend_y, x0=_legend_x0())
    out.append("</svg>")
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    logger.debug(f"      Saved: {out_path}")

# ---------------------------------------------------------------------------
# Shared chevron strip primitives  (factored out of task28; also used by task27)
# ---------------------------------------------------------------------------

CHEVRON_HEIGHT     = 1.65
CHEVRON_DEPTH      = 0.92
CHEVRON_GAP        = 0.82
CHEVRON_MIN_WIDTH  = 6.15
CHEVRON_CHAR_WIDTH = 0.42


def chevron_layout(nodes, uniform_width=False):
    """Return chevron x positions/widths sized from label content, plus total span.

    uniform_width=True forces every chevron to the width of the widest label.
    """
    widths = []
    for node in nodes:
        longest = max(len(line) for line in str(node["label"]).splitlines())
        content_w = CHEVRON_DEPTH * 2.0 + 2.65 + longest * CHEVRON_CHAR_WIDTH
        widths.append(max(CHEVRON_MIN_WIDTH, content_w))
    if uniform_width and widths:
        widths = [max(widths)] * len(widths)
    x_cursor = 0.0
    layout = []
    for width in widths:
        layout.append({"x": x_cursor, "width": width})
        x_cursor += width + CHEVRON_GAP
    span = max(0.0, x_cursor - CHEVRON_GAP)
    return layout, span


def chevron_figure_width(nodes, min_w: float = 13.0, max_w: float = 34.0):
    """Choose a figure width that keeps chevron text from being compressed."""
    _layout, span = chevron_layout(nodes)
    return min(max(min_w, span * 0.29 + 1.6), max_w)


def _chevron_font_size(label, width, base_fontsize):
    """Shrink only when a very long label would otherwise touch chevron edges."""
    longest = max(len(line) for line in str(label).splitlines())
    available = max(width - CHEVRON_DEPTH * 2.0 - 1.2, 1.0)
    estimated = longest * 0.34
    if estimated <= available:
        return base_fontsize
    return max(8.5, base_fontsize * available / estimated)


def draw_chevron_strip(ax, nodes, fontsize=10, y_pad: float = 0.18,
                       uniform_width: bool = False):
    """Draw one chevron strip (list of {label, color} nodes) onto *ax*.

    uniform_width=True makes every chevron the same width (widest label wins).
    Returns the horizontal span so callers can align multiple strips.
    """
    from matplotlib.patches import Polygon as _Polygon

    ax.set_aspect("auto")
    ax.axis("off")
    h = CHEVRON_HEIGHT
    layout, span = chevron_layout(nodes, uniform_width=uniform_width)
    for i, node in enumerate(nodes):
        base_x = layout[i]["x"]
        width  = layout[i]["width"]
        mid_y  = h / 2.0
        verts = [
            (base_x,                          0.0),
            (base_x + CHEVRON_DEPTH,          mid_y),
            (base_x,                          h),
            (base_x + width - CHEVRON_DEPTH,  h),
            (base_x + width,                  mid_y),
            (base_x + width - CHEVRON_DEPTH,  0.0),
        ]
        ax.add_patch(_Polygon(
            verts, closed=True,
            facecolor=node["color"], edgecolor="#4a4a4a",
            linewidth=1.25, joinstyle="miter",
        ))
        ax.text(
            base_x + width / 2.0, mid_y,
            node["label"],
            ha="center", va="center",
            fontsize=_chevron_font_size(node["label"], width, fontsize),
            color=contrasting_text_color(node["color"]), clip_on=False,
        )
    ax.set_xlim(-0.45, span + 0.45)
    ax.set_ylim(-y_pad, h + y_pad)
    return span


_CHEVRON_MISSING_TOKENS = {"-", "None", "(skip)", ""}


def chevron_nodes_from_alignment_rows(rows):
    """Map alignment rows (alignment_pairs_to_rows output) to chevron nodes.

    Colors follow the established move-type palette:
    sync = GREY_LIGHTER, model move = GREY_MED, mismatch = GREY_LIGHT, log move = GREY_DARK.
    """
    nodes = []
    for row in rows:
        if row["moveType"] == "Synchronous Move":
            label = row["log_move"] if str(row["log_move"]) not in _CHEVRON_MISSING_TOKENS else row["model_move"]
            nodes.append({"label": str(label), "color": GREY_LIGHTER})
        elif row["moveType"] == "Model Move":
            nodes.append({"label": str(row["model_move"]), "color": GREY_MED})
        elif row["moveType"] == "Mismatch Move":
            nodes.append({"label": f"{row['log_move']} / {row['model_move']}", "color": GREY_LIGHT})
        else:
            nodes.append({"label": str(row["log_move"]), "color": GREY_DARK})
    return nodes


def alignment_violation_node_style(rep_rows):
    """Return a BPMN node_style_fn marking a trace's deviating / conform tasks.

    Maps the alignment rows (alignment_pairs_to_rows output) of one representative
    trace onto the desired model: model moves -> GREY_MED (skipped step), mismatch
    moves -> GREY_LIGHT, synchronous moves -> GREY_LIGHTER, everything else -> white. Shared
    by the "Reasons" family (task13/task18/task21) so the elaborate flow idiom
    annotates violations identically. node_style_fn(eid, elem) ->
    (fill, stroke, stroke_width, text_color)."""
    skipped, mismatch, conform = set(), set(), set()
    for row in rep_rows:
        mt = row["moveType"]
        if mt == "Synchronous Move":
            lbl = str(row["log_move"]) if str(row["log_move"]) not in {"-", "None"} \
                else str(row["model_move"])
            conform.add(lbl)
        elif mt == "Model Move":
            skipped.add(str(row["model_move"]))
        elif mt == "Mismatch Move":
            mismatch.add(str(row["model_move"]))

    def _style(eid, elem):
        name = elem.get("name", "")
        if elem.get("kind") == "task":
            if name in skipped:
                return (GREY_MED, "#444444", 3, contrasting_text_color(GREY_MED))
            if name in mismatch:
                return (GREY_LIGHT, "#444444", 3, contrasting_text_color(GREY_LIGHT))
            if name in conform:
                return (GREY_LIGHTER, "#666666", 2, contrasting_text_color(GREY_LIGHTER))
        return ("white", "#888888", 2, "#333333")
    return _style

# ---------------------------------------------------------------------------
# Shared Parallel Sets renderer  (used by task01, task03, task05, …)
# ---------------------------------------------------------------------------

def draw_parallel_sets(
    ax,
    left_labels,
    right_labels,
    matrix,
    left_colors,
    right_colors=None,
    left_title: str = "",
    right_title: str = "",
    bar_w: float = 0.10,
    x_left: float = 0.12,
    x_right: float = 0.88,
):
    """Draw a two-dimension Parallel Sets chart onto *ax*.

    Parameters
    ----------
    left_labels   : sequence of str — categories on the left axis
    right_labels  : sequence of str — categories on the right axis
    matrix        : 2-D array-like, shape (len(left_labels), len(right_labels)) — counts
    left_colors   : sequence of colour strings, one per left category
    right_colors  : sequence of colour strings, one per right category; defaults to greyscale
    left_title    : column header above left axis
    right_title   : column header above right axis
    bar_w         : width of the bar rectangles (axes units)
    x_left/right  : x position of the left/right bar centres (axes units)
    """
    import numpy as _np
    from matplotlib.patches import PathPatch as _PP
    from matplotlib.path import Path as _Path

    matrix = _np.asarray(matrix, dtype=float)
    total  = float(matrix.sum())
    if total == 0:
        ax.text(0.5, 0.5, "No data.", ha="center", va="center", fontsize=11)
        return

    if right_colors is None:
        n = len(right_labels)
        right_colors = [to_hex(_CIV(0.15 + 0.70 * i / max(n - 1, 1))) for i in range(n)]

    ctrl_x  = (x_left + x_right) / 2.0
    g_hts   = matrix.sum(axis=1) / total
    c_hts   = matrix.sum(axis=0) / total
    g_bots  = _np.concatenate([[0.0], _np.cumsum(g_hts[:-1])])
    c_bots  = _np.concatenate([[0.0], _np.cumsum(c_hts[:-1])])

    # Left bars
    for label, color, h, bot in zip(left_labels, left_colors, g_hts, g_bots):
        ax.add_patch(plt.Rectangle(
            (x_left - bar_w / 2, bot), bar_w, h,
            facecolor=color, edgecolor="white", linewidth=0.8, zorder=3,
        ))
        if h > 0.03:
            ax.text(x_left - bar_w / 2 - 0.015, bot + h / 2, label,
                    ha="right", va="center", fontsize=FONT_ANNOT, color="#333333")

    # Right bars
    for label, color, h, bot in zip(right_labels, right_colors, c_hts, c_bots):
        ax.add_patch(plt.Rectangle(
            (x_right - bar_w / 2, bot), bar_w, h,
            facecolor=color, edgecolor="white", linewidth=0.8, zorder=3,
        ))
        if h > 0.03:
            ax.text(x_right + bar_w / 2 + 0.015, bot + h / 2, label,
                    ha="left", va="center", fontsize=FONT_ANNOT - 1, color="#333333")

    # Bezier ribbons
    g_fill = g_bots.copy()
    c_fill = c_bots.copy()
    for gi, color in enumerate(left_colors):
        for ci in range(len(right_labels)):
            count = matrix[gi, ci]
            if count == 0:
                continue
            rh   = count / total
            ylb  = g_fill[gi];  ylt = ylb + rh
            yrb  = c_fill[ci];  yrt = yrb + rh
            g_fill[gi] += rh
            c_fill[ci] += rh
            verts = [
                (x_left,  ylb),
                (ctrl_x,  ylb), (ctrl_x, yrb), (x_right, yrb),
                (x_right, yrt),
                (ctrl_x,  yrt), (ctrl_x, ylt), (x_left,  ylt),
                (x_left,  ylb),
            ]
            codes = [
                _Path.MOVETO,
                _Path.CURVE4, _Path.CURVE4, _Path.CURVE4,
                _Path.LINETO,
                _Path.CURVE4, _Path.CURVE4, _Path.CURVE4,
                _Path.CLOSEPOLY,
            ]
            ax.add_patch(_PP(
                _Path(verts, codes),
                facecolor=color, edgecolor="none", alpha=0.35, zorder=2,
            ))

    # Column titles
    if left_title:
        ax.text(x_left,  1.08, left_title,  ha="center", va="bottom",
                fontsize=FONT_LABEL, fontweight="bold")
    if right_title:
        ax.text(x_right, 1.08, right_title, ha="center", va="bottom",
                fontsize=FONT_LABEL, fontweight="bold")


# ---------------------------------------------------------------------------
# Dataset-agnostic outcome-activity inference
# ---------------------------------------------------------------------------

def infer_outcome_activity(log) -> str:
    """Infer a positive-outcome activity from the log without any hardcoded names.

    Heuristic: among activities present in 25–55 % of traces (good split range),
    pick the one with the highest overall presence, breaking ties by frequency
    as the last event.  If no activity falls in that window, the constraint is
    relaxed progressively (15–65 %, then 5–85 %, then 0–100 %).

    This is a best-effort fallback; admins should always set outcome_activity
    explicitly via PARAM_SPEC when configuring an experiment.
    """
    n = len(log)
    if n == 0:
        return ""

    presence: dict[str, int] = {}
    as_last:  dict[str, int] = {}

    for trace in log:
        seen: set[str] = set()
        for event in trace:
            a = str(event.get("concept:name", ""))
            if a:
                seen.add(a)
        for a in seen:
            presence[a] = presence.get(a, 0) + 1
        if trace:
            last = str(trace[-1].get("concept:name", ""))
            if last:
                as_last[last] = as_last.get(last, 0) + 1

    import logging as _logging
    _logging.getLogger(__name__).warning(
        "infer_outcome_activity: no outcome_activity configured — "
        "falling back to heuristic. Set outcome_activity explicitly via PARAM_SPEC."
    )
    # Pick the activity present in 25-55 % of traces (best split range).
    # Use total trace-count as the primary key, as_last as tiebreaker.
    for lo, hi in [(0.25, 0.55), (0.15, 0.65), (0.05, 0.85), (0.0, 1.0)]:
        candidates = {a for a, c in presence.items() if lo * n <= c <= hi * n}
        if candidates:
            return max(candidates, key=lambda a: (presence[a], as_last.get(a, 0)))


def infer_rejected_activities(log, outcome_activity: str, min_pct: float = 0.03) -> set:
    """Infer rejection/cancellation activities from the log.

    Returns activities that appear as the *last* event in traces that do NOT
    contain the positive-outcome activity, with presence above min_pct of the
    negative-outcome trace count (default 3 %).
    """
    n = len(log)
    if n == 0:
        return set()
    counts: dict[str, int] = {}
    n_neg = 0
    for trace in log:
        if not trace:
            continue
        acts = {str(e.get("concept:name", "")) for e in trace}
        if outcome_activity in acts:
            continue
        n_neg += 1
        last = str(trace[-1].get("concept:name", ""))
        if last:
            counts[last] = counts.get(last, 0) + 1
    if n_neg == 0:
        return set()
    threshold = max(1, int(n_neg * min_pct))
    return {a for a, c in counts.items() if c >= threshold}
