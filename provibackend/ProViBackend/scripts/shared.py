"""
shared.py – Cross-task utilities for the CC Visualization Pipeline.

Contains: color constants, save_svg, wrap_text, table helpers,
draw_decision_tree, tree position layout, and alignment parsing helpers
(_extract_alignment_label, alignment_pairs_to_rows, _task4_format_threshold).

All task modules import from here; this file must NOT import from any task module.
"""

import logging

logger = logging.getLogger(__name__)

import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

import numpy as np

# ---------------------------------------------------------------------------
# Color palette  – greyscale throughout all visualizations
# ---------------------------------------------------------------------------
BLUE   = "#666666"   # medium-dark grey  (model moves, primary category)
ORANGE = "#999999"   # medium grey       (mismatch / secondary category)
TEAL   = "#666666"   # same as BLUE      (single-category neutral)
GREEN  = "#CCCCCC"   # light grey        (synchronous / conformant)
RED    = "#333333"   # dark grey         (log moves / strongest deviation)

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
    header_color: str = "#555555",
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
    header_color: str = "#555555",
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
# Alignment parsing helpers  (used by task2, task3, task4)
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

# ---------------------------------------------------------------------------
# Shared number formatter (used by task4 and task6)
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
