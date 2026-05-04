"""
shared.py – Cross-task utilities for the CC Visualization Pipeline.

Contains: color constants, save_svg, wrap_text, table helpers,
draw_decision_tree, tree position layout, and alignment parsing helpers
(_extract_alignment_label, alignment_pairs_to_rows, _task4_format_threshold).

All task modules import from here; this file must NOT import from any task module.
"""

import os
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch

import numpy as np

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
BLUE   = "#4472C4"
ORANGE = "#ED7D31"
TEAL   = "#2DA8A8"
GREEN  = "#2ECC71"
RED    = "#E74C3C"

# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------

def save_svg(fig, path: str):
    fig.savefig(path, format="svg", bbox_inches="tight")
    plt.close(fig)
    print(f"      Saved: {path}")

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
    header_color: str = "#1F3864",
    zebra: bool = True,
    odd_color: str = "#FFFFFF",
    even_color: str = "#F2F2F2",
    highlight_last_row: bool = False,
    highlight_color: str = "#E8EEF7",
):
    """Apply consistent styling to Matplotlib tables."""
    for c in range(ncols):
        for r in range(header_rows):
            table[r, c].set_facecolor(header_color)
            table[r, c].set_text_props(color="white", fontweight="bold")

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
            table[last, c].set_text_props(fontweight="bold")


def make_table(
    ax,
    cell_text,
    col_labels,
    bbox=None,
    col_widths=None,
    cell_loc: str = "center",
    font_size: float = 10,
    scale_xy=(1.0, 1.7),
    header_rows: int = 1,
    header_color: str = "#1F3864",
    zebra: bool = True,
    highlight_last_row: bool = False,
    cell_pad: float | None = None,
):
    """Create a styled Matplotlib table with consistent defaults."""
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

def assign_tree_positions(tree: dict, x_gap: float = None, y_gap: float = None):
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
    x_gap = 3.15 if x_gap is None else x_gap
    y_gap = 1.85 if y_gap is None else y_gap
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
    edge_label_clearance: float = 0.12,
    edge_label_perp_offset: float = 0.14,
    x_pad_factor: float = 0.70,
    y_pad_base: float = 0.80,
    y_top_pad: float = 0.95,
    x_gap: float = None,
    y_gap: float = None,
):
    """Render a shallow decision tree with adaptive node height and wrapped text."""
    ax.axis("off")
    if title:
        ax.set_title(title, fontsize=title_fontsize, fontweight="bold", loc="left", pad=title_pad)

    if tree is None:
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.text(0.5, 0.5, "No decision tree could be fitted.", ha="center", va="center", fontsize=11)
        return

    def node_text_lines(node):
        a, b = value_pair_fn(node)
        first = first_line_fn(node)
        first = wrap_text(first, width_chars=wrap_width_fn(first))
        raw_lines = [
            f"gini = {node['gini']:.3f}",
            f"samples = {node['samples']}",
            f"value = [{a}, {b}]",
            f"class = {node['class']}",
        ]
        if first:
            raw_lines.insert(0, first)
        lines = []
        for line in raw_lines:
            wrap_width = min(wrap_width_fn(line), 18) if line.startswith(("value =", "class =")) else wrap_width_fn(line)
            lines.extend(wrap_text(line, width_chars=wrap_width).splitlines())
        return lines

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
    effective_box_w = max(box_w, 1.15 + max_line_len * 0.125)

    assign_tree_positions(tree, x_gap=x_gap, y_gap=y_gap)
    current_x_gap = tree.get("_x_gap", 3.15)
    target_x_gap = max(current_x_gap, effective_box_w * 1.18)
    if target_x_gap > current_x_gap:
        scale = target_x_gap / current_x_gap

        def scale_tree_x(node):
            node["_x"] *= scale
            if node.get("left") is not None:
                scale_tree_x(node["left"])
            if node.get("right") is not None:
                scale_tree_x(node["right"])

        scale_tree_x(tree)
        tree["_x_gap"] = target_x_gap

    leaf_count = max(tree.get("_leaf_count", 1), 1)
    x_gap = tree.get("_x_gap", 3.15)
    max_depth = tree.get("_max_depth", 0)
    font_size = max(
        min_font,
        base_font
        - 0.25 * max(0, max_depth - 2)
        - 0.12 * max(0, leaf_count - 6)
        - 0.55 * max(0, max_lines - 6)
        - 0.06 * max(0, max_line_len - 26),
    )

    max_h = max_box_h(tree)
    ax.set_xlim(-effective_box_w * x_pad_factor, (leaf_count - 1) * x_gap + effective_box_w * x_pad_factor)
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
            parent_bottom = node["_y"] - this_h / 2
            child_top = child["_y"] + child_h / 2
            label_x = (node["_x"] + child["_x"]) / 2
            label_y = (node["_y"] + child["_y"]) / 2 + edge_label_offset_y
            dx = child["_x"] - node["_x"]
            dy = child["_y"] - node["_y"]
            norm = max((dx * dx + dy * dy) ** 0.5, 1e-9)
            perp_x = -dy / norm
            perp_y = dx / norm
            if perp_y < 0:
                perp_x *= -1
                perp_y *= -1
            label_x += perp_x * edge_label_perp_offset
            label_y += perp_y * edge_label_perp_offset
            label_min_y = child_top + edge_label_clearance
            label_max_y = parent_bottom - edge_label_clearance
            if label_max_y > label_min_y:
                label_y = min(max(label_y, label_min_y), label_max_y)
            ax.annotate(
                "",
                xy=(child["_x"], child["_y"] + child_h / 2),
                xytext=(node["_x"], node["_y"] - this_h / 2),
                arrowprops=edge_arrowprops,
            )
            ax.text(
                label_x,
                label_y,
                label,
                ha="center", va="center",
                fontsize=edge_label_fontsize, color="#333333",
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.92, pad=0.7),
            )
            draw_edges(child)

    def draw_nodes(node):
        box_h = node_box_h(node)
        patch = FancyBboxPatch(
            (node["_x"] - effective_box_w / 2, node["_y"] - box_h / 2),
            effective_box_w, box_h,
            boxstyle="round,pad=0.04,rounding_size=0.12",
            facecolor=node_facecolor_fn(node),
            edgecolor="#555555",
            linewidth=1.15,
            alpha=0.96,
        )
        ax.add_patch(patch)
        ax.text(
            node["_x"], node["_y"],
            node_text(node),
            ha="center", va="center",
            fontsize=font_size, fontweight="bold", wrap=True,
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
