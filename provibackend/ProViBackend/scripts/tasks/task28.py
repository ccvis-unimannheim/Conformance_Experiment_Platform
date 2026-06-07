"""
tasks/task28.py – Task 2: Location/alignment visualizations for a representative trace.

Public API:
    generate(alignments, model_path, output_dir)
"""

import logging

logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_basic", "flow_chart_table", "flow_chart_elaborate", "table"]

import html
import math
import os
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Polygon
from matplotlib import gridspec

from shared import (
    save_svg, BLUE, ORANGE, GREEN, RED, FONT_TITLE, FONT_LABEL, FONT_ANNOT,
    contrasting_text_color,
)


# Task 2 – Location / alignment visualizations (representative trace)
# ---------------------------------------------------------------------------

# Task 2 helpers
SKIP_ALIGNMENT_TOKENS = {">>", None}
TASK28_HEADER_COLOR = "#555555"
TASK28_SYNC_ROW_COLOR = "#F2F2F2"
TASK28_MODEL_ROW_COLOR = "#E0E0E0"
TASK28_LOG_ROW_COLOR = "#C8C8C8"
TASK28_MISMATCH_ROW_COLOR = "#D8D8D8"
TASK28_TABLE_EDGE_COLOR = "#FFFFFF"
TASK28_TABLE_COL_LABELS = ["Step", "Log Move", "Model Move", "Status"]
TASK28_TABLE_COL_WIDTHS = [0.065, 0.375, 0.375, 0.185]
TASK28_CHEVRON_HEIGHT = 1.65
TASK28_CHEVRON_DEPTH = 0.92
TASK28_CHEVRON_GAP = 0.82
TASK28_CHEVRON_MIN_WIDTH = 6.15
TASK28_CHEVRON_CHAR_WIDTH = 0.42


def _extract_alignment_label(value):
    """Pull activity label from PM4Py alignment tuple side (supports ('name', 'act') etc.)."""
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
    """Convert PM4Py alignment pairs to display rows, skipping empty internal moves."""
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
                "step": step_num,
                "log_move": observed,
                "model_move": expected,
                "status": "Synchronous",
                "moveType": "Synchronous Move",
            })
        elif observed not in SKIP_ALIGNMENT_TOKENS and expected not in SKIP_ALIGNMENT_TOKENS:
            rows_out.append({
                "step": step_num,
                "log_move": observed,
                "model_move": expected,
                "status": "Mismatch Move",
                "moveType": "Mismatch Move",
            })
        elif observed in SKIP_ALIGNMENT_TOKENS and expected not in SKIP_ALIGNMENT_TOKENS:
            rows_out.append({
                "step": step_num,
                "log_move": "-",
                "model_move": expected,
                "status": "Model Move",
                "moveType": "Model Move",
            })
        elif observed not in SKIP_ALIGNMENT_TOKENS and expected in SKIP_ALIGNMENT_TOKENS:
            rows_out.append({
                "step": step_num,
                "log_move": observed,
                "model_move": "-",
                "status": "Log Move",
                "moveType": "Log Move",
            })
    return rows_out


def pick_representative_trace_index(alignments):
    """First trace with fitness < 1, else 0."""
    for i, result in enumerate(alignments):
        if float(result.get("fitness", 1.0)) < 1.0 - 1e-9:
            return i
    return 0


def build_task28_context(alignments):
    """Pick representative trace and build row list; returns None if no usable alignment."""
    if not alignments:
        return None
    idx = pick_representative_trace_index(alignments)
    result = alignments[idx]
    alignment = result.get("alignment")
    if not alignment:
        return None
    rows = alignment_pairs_to_rows(alignment)
    if not rows:
        return None
    return {
        "trace_index": idx,
        "trace_label": f"Trace {idx + 1}",
        "fitness": float(result.get("fitness", 0.0)),
        "cost": result.get("cost"),
        "rows": rows,
    }


def _task28_format_cost(cost):
    """Format PM4Py alignment cost for the table subtitle."""
    if cost is None:
        return None
    try:
        cost_num = float(cost)
    except (TypeError, ValueError):
        return str(cost)
    if abs(cost_num - round(cost_num)) < 1e-9:
        return str(int(round(cost_num)))
    return f"{cost_num:.4f}".rstrip("0").rstrip(".")


def _task28_status_color(move_type: str) -> str:
    """Map alignment move type to the reference table row color."""
    if move_type == "Model Move":
        return TASK28_MODEL_ROW_COLOR
    if move_type == "Log Move":
        return TASK28_LOG_ROW_COLOR
    if move_type == "Mismatch Move":
        return TASK28_MISMATCH_ROW_COLOR
    return TASK28_SYNC_ROW_COLOR


def _task28_table_cell_text(rows):
    """Return table cells in the reference Step | Log | Model | Status order."""
    return [
        [str(row["step"]), str(row["log_move"]), str(row["model_move"]), str(row["status"])]
        for row in rows
    ]


def _task28_alignment_table_height(row_count: int, *, compact: bool = False) -> float:
    """Figure height that keeps table rows close to the reference density."""
    base = 3.8 if compact else 4.7
    row_h = 0.27 if compact else 0.31
    return max(base, base + row_count * row_h)


def _draw_task28_alignment_table(ax, rows, *, bbox, font_size=10.5):
    """Draw the shared Task 2 table style used by standalone and composite views."""
    table = ax.table(
        cellText=_task28_table_cell_text(rows),
        colLabels=TASK28_TABLE_COL_LABELS,
        colWidths=TASK28_TABLE_COL_WIDTHS,
        cellLoc="center",
        bbox=bbox,
    )
    table.auto_set_font_size(False)
    table.set_fontsize(font_size)

    for (r_idx, c_idx), cell in table.get_celld().items():
        cell.set_edgecolor(TASK28_TABLE_EDGE_COLOR)
        cell.set_linewidth(1.0)
        if r_idx == 0:
            cell.set_facecolor(TASK28_HEADER_COLOR)
            cell.set_text_props(color="white")
            continue

        row = rows[r_idx - 1]
        cell.set_facecolor(_task28_status_color(row["moveType"]))
        cell.set_text_props(color="#2B2B2B")
    return table


def _add_task28_table_heading(fig, ctx, *, x=0.055, y=0.86, compact=False):
    """Add the trace title and alignment summary above the table."""
    fig.text(
        x,
        y,
        ctx["trace_label"],
        ha="left",
        va="top",
        fontsize=FONT_TITLE,
        color="#111111",
    )

    cost_text = _task28_format_cost(ctx.get("cost"))
    meta_parts = [f"Fitness: {ctx['fitness']:.4f}"]
    if cost_text is not None:
        meta_parts.append(f"Cost: {cost_text}")
    fig.text(
        x,
        y - (0.055 if compact else 0.065),
        "   |   ".join(meta_parts),
        ha="left",
        va="top",
        fontsize=FONT_ANNOT,
        color="#6C6C6C",
    )


def _task28_nodes_from_rows(rows):
    """Shared Task 2 move-to-chevron mapping."""
    nodes = []
    for row in rows:
        if row["moveType"] == "Synchronous Move":
            label = row["log_move"] if row["log_move"] != "-" else row["model_move"]
            nodes.append({"label": str(label), "color": GREEN})
        elif row["moveType"] == "Model Move":
            nodes.append({"label": str(row["model_move"]), "color": BLUE})
        elif row["moveType"] == "Mismatch Move":
            nodes.append({"label": f"{row['log_move']} / {row['model_move']}", "color": ORANGE})
        else:
            nodes.append({"label": str(row["log_move"]), "color": RED})
    return nodes


def _task28_chevron_layout(nodes):
    """Return chevron x positions and widths sized from label content."""
    widths = []
    for node in nodes:
        label = node["label"]
        longest = max(len(line) for line in str(label).splitlines())
        content_w = TASK28_CHEVRON_DEPTH * 2.0 + 2.65 + longest * TASK28_CHEVRON_CHAR_WIDTH
        widths.append(max(TASK28_CHEVRON_MIN_WIDTH, content_w))

    x_cursor = 0.0
    layout = []
    for width in widths:
        layout.append({"x": x_cursor, "width": width})
        x_cursor += width + TASK28_CHEVRON_GAP
    span = max(0.0, x_cursor - TASK28_CHEVRON_GAP)
    return layout, span


def _task28_chevron_figure_width(nodes):
    """Choose a figure width that keeps chevron text from being compressed."""
    _layout, span = _task28_chevron_layout(nodes)
    return min(max(13.0, span * 0.29 + 1.6), 34.0)


def _task28_chevron_font_size(label, width, base_fontsize):
    """Shrink only when a very long label would otherwise touch chevron edges."""
    longest = max(len(line) for line in str(label).splitlines())
    available = max(width - TASK28_CHEVRON_DEPTH * 2.0 - 1.2, 1.0)
    estimated = longest * 0.34
    if estimated <= available:
        return base_fontsize
    return max(8.5, base_fontsize * available / estimated)


def _draw_task28_basic_chevrons(ax, nodes, fontsize=10):
    """Draw the shared chevron style with boxes sized to their labels."""
    ax.set_aspect("auto")
    ax.axis("off")

    h = TASK28_CHEVRON_HEIGHT
    notch_x = TASK28_CHEVRON_DEPTH
    shoulder = TASK28_CHEVRON_DEPTH
    layout, span = _task28_chevron_layout(nodes)

    for i, node in enumerate(nodes):
        base_x = layout[i]["x"]
        width = layout[i]["width"]
        mid_y = h / 2.0
        verts = [
            (base_x, 0.0),
            (base_x + notch_x, mid_y),
            (base_x, h),
            (base_x + width - shoulder, h),
            (base_x + width, mid_y),
            (base_x + width - shoulder, 0.0),
        ]
        ax.add_patch(Polygon(
            verts,
            closed=True,
            facecolor=node["color"],
            edgecolor="#4a4a4a",
            linewidth=1.25,
            joinstyle="miter",
        ))
        ax.text(
            base_x + width / 2.0,
            mid_y,
            node["label"],
            ha="center",
            va="center",
            fontsize=_task28_chevron_font_size(node["label"], width, fontsize),
            color=contrasting_text_color(node["color"]),
            clip_on=False,
        )

    ax.set_xlim(-0.45, span + 0.45)
    ax.set_ylim(-0.18, h + 0.18)
    return span


def _task28_move_legend_elements():
    return [
        mpatches.Patch(facecolor=GREEN, edgecolor="black", linewidth=0.75, label="Synchronous move (Conform)"),
        mpatches.Patch(facecolor=BLUE, edgecolor="black", linewidth=0.75, label="Model move only"),
        mpatches.Patch(facecolor=RED, edgecolor="black", linewidth=0.75, label="Log move only"),
    ]


# Task 2 visualizations
def task28_alignment_table(ctx: dict, output_dir: str):
    """Alignment detail table for representative trace."""
    rows = ctx["rows"]

    fig_h = _task28_alignment_table_height(len(rows))
    fig, ax = plt.subplots(figsize=(15.8, fig_h))
    ax.axis("off")
    _add_task28_table_heading(fig, ctx, x=0.06, y=0.86)
    _draw_task28_alignment_table(
        ax,
        rows,
        bbox=[0.045, 0.08, 0.91, 0.58],
        font_size=10.5,
    )
    fig.subplots_adjust(left=0.025, right=0.985, top=0.94, bottom=0.05)
    save_svg(fig, os.path.join(output_dir, "task28_table.svg"))


def task28_flow_chart_basic(ctx: dict, output_dir: str):
    """Chevron diagram (reference layout): titled flow strip + bottom move-type legend."""
    nodes = _task28_nodes_from_rows(ctx["rows"])

    fig_w = _task28_chevron_figure_width(nodes)
    fig_h = 4.15
    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    _draw_task28_basic_chevrons(ax, nodes, fontsize=10)
    fig.subplots_adjust(left=0.045, right=0.985, top=0.55, bottom=0.28)
    fig.text(
        0.045,
        0.90,
        "Trace Alignment",
        ha="left",
        va="top",
        fontsize=FONT_TITLE,
        color="black",
    )
    fig.text(
        0.045,
        0.58,
        ctx["trace_label"],
        ha="left",
        va="center",
        fontsize=FONT_TITLE,
        color="#222222",
    )
    fig.legend(
        handles=_task28_move_legend_elements(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.075),
        ncol=3,
        fontsize=FONT_ANNOT,
        frameon=True,
        fancybox=False,
        edgecolor="#cccccc",
    )
    save_svg(fig, os.path.join(output_dir, "task28_flow_chart_basic.svg"))


def task28_flow_chart_and_table(ctx: dict, output_dir: str):
    """Composite: table above, chevron row below."""
    rows = ctx["rows"]
    nodes = _task28_nodes_from_rows(rows)

    fig_w = max(16.0, _task28_chevron_figure_width(nodes))
    fig_h = max(7.0, 4.0 + len(rows) * 0.22 + 2.0)

    fig = plt.figure(figsize=(fig_w, fig_h))
    gs = gridspec.GridSpec(
        2,
        1,
        height_ratios=[max(2.0, 0.22 * len(rows) + 1.65), 1.0],
        hspace=0.16,
    )
    ax_top = fig.add_subplot(gs[0])
    ax_bot = fig.add_subplot(gs[1])

    ax_top.axis("off")
    _add_task28_table_heading(fig, ctx, x=0.055, y=0.92, compact=True)
    _draw_task28_alignment_table(
        ax_top,
        rows,
        bbox=[0.055, 0.04, 0.89, 0.66],
        font_size=9.4,
    )

    _draw_task28_basic_chevrons(ax_bot, nodes, fontsize=11)
    ax_bot.set_title("Trace Alignment", fontsize=FONT_TITLE, pad=7)

    fig.tight_layout(rect=[0, 0.105, 1, 0.98])
    fig.legend(
        handles=_task28_move_legend_elements(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.025),
        ncol=3,
        fontsize=FONT_ANNOT,
        frameon=True,
        fancybox=False,
        edgecolor="#cccccc",
    )
    save_svg(fig, os.path.join(output_dir, "task28_flow_chart_and_table.svg"))


def task28_flow_chart_elaborate_bpmn(ctx: dict, model_path: str, output_dir: str):
    """Render native BPMN DI geometry as SVG and overlay alignment deviations."""
    ns = {
        "bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        "dc": "http://www.omg.org/spec/DD/20100524/DC",
        "di": "http://www.omg.org/spec/DD/20100524/DI",
    }

    def local_name(tag):
        return tag.split("}", 1)[-1] if "}" in tag else tag

    def esc(value):
        return html.escape("" if value is None else str(value), quote=True)

    def tx(x):
        return x - min_x + left_pad

    def ty(y):
        return y - min_y + top_pad

    def node_center(bounds):
        return bounds["x"] + bounds["width"] / 2.0, bounds["y"] + bounds["height"] / 2.0

    def wrap_label(label, max_chars=12):
        words = str(label).replace("_", "_ ").split()
        lines = []
        current = ""
        for word in words:
            candidate = word if not current else f"{current} {word}"
            if len(candidate) <= max_chars:
                current = candidate
            else:
                if current:
                    lines.append(current.replace("_ ", "_"))
                current = word
        if current:
            lines.append(current.replace("_ ", "_"))
        return lines or [str(label)]

    def label_lines_for_box(label, box_width, font_size=9):
        max_chars = max(7, int((box_width - 14) / (font_size * 0.58)))
        lines = wrap_label(label, max_chars=max_chars)
        if len(lines) > 3:
            compact = str(label)
            max_chars = max(9, int((box_width - 12) / (font_size * 0.50)))
            lines = [compact[i:i + max_chars] for i in range(0, len(compact), max_chars)]
        return lines[:3]

    def adjust_endpoint_to_shape(point, next_point, elem_id):
        if elem_id not in shapes:
            return point
        b = shapes[elem_id]
        cx, cy = node_center(b)
        dx = next_point[0] - point[0]
        dy = next_point[1] - point[1]
        if abs(dx) >= abs(dy):
            x = b["x"] + (b["width"] if dx > 0 else 0)
            return (x, cy)
        y = b["y"] + (b["height"] if dy > 0 else 0)
        return (cx, y)

    def expanded_rect(bounds, pad=10.0):
        return {
            "x": bounds["x"] - pad,
            "y": bounds["y"] - pad,
            "width": bounds["width"] + pad * 2,
            "height": bounds["height"] + pad * 2,
        }

    def segment_intersects_rect(p1, p2, rect):
        x1, y1 = p1
        x2, y2 = p2
        rx1, ry1 = rect["x"], rect["y"]
        rx2, ry2 = rect["x"] + rect["width"], rect["y"] + rect["height"]
        if abs(x1 - x2) < 1e-9:
            x = x1
            return rx1 <= x <= rx2 and max(min(y1, y2), ry1) <= min(max(y1, y2), ry2)
        if abs(y1 - y2) < 1e-9:
            y = y1
            return ry1 <= y <= ry2 and max(min(x1, x2), rx1) <= min(max(x1, x2), rx2)
        # Conservative fallback: bounding-box overlap for rare diagonal segments.
        return max(min(x1, x2), rx1) <= min(max(x1, x2), rx2) and max(min(y1, y2), ry1) <= min(max(y1, y2), ry2)

    def route_intersection_count(points, obstacle_rects):
        count = 0
        for p1, p2 in zip(points, points[1:]):
            for rect in obstacle_rects:
                if segment_intersects_rect(p1, p2, rect):
                    count += 1
        return count

    def log_move_route_candidates(rb, callout_x, callout_y):
        """Generate red dashed routes that can leave a task from multiple sides."""
        _, center_y = node_center(rb)
        callout_cx = callout_x + callout_w / 2.0
        bend_y = callout_y - 26.0
        side_pad = 34.0
        right_x = rb["x"] + rb["width"] + side_pad
        left_x = rb["x"] - side_pad
        return [
            [(rb["x"] + rb["width"], center_y), (right_x, center_y), (right_x, bend_y), (callout_cx, bend_y), (callout_cx, callout_y)],
            [(rb["x"], center_y), (left_x, center_y), (left_x, bend_y), (callout_cx, bend_y), (callout_cx, callout_y)],
        ]

    tree = ET.parse(model_path)
    root = tree.getroot()

    elements = {}
    sequence_flows = {}
    for elem in root.findall(".//bpmn:*", ns):
        elem_id = elem.attrib.get("id")
        if not elem_id:
            continue
        kind = local_name(elem.tag)
        if kind in {"task", "startEvent", "endEvent", "exclusiveGateway", "parallelGateway"}:
            elements[elem_id] = {
                "id": elem_id,
                "kind": kind,
                "name": elem.attrib.get("name", ""),
                "direction": elem.attrib.get("gatewayDirection", ""),
            }
        elif kind == "sequenceFlow":
            sequence_flows[elem_id] = {
                "id": elem_id,
                "source": elem.attrib.get("sourceRef"),
                "target": elem.attrib.get("targetRef"),
            }

    shapes = {}
    for shape in root.findall(".//bpmndi:BPMNShape", ns):
        elem_id = shape.attrib.get("bpmnElement")
        bounds = shape.find("dc:Bounds", ns)
        if elem_id and bounds is not None:
            shapes[elem_id] = {
                "x": float(bounds.attrib["x"]),
                "y": float(bounds.attrib["y"]),
                "width": float(bounds.attrib["width"]),
                "height": float(bounds.attrib["height"]),
            }

    for elem_id, bounds in list(shapes.items()):
        elem = elements.get(elem_id)
        if not elem or elem["kind"] != "task":
            continue
        name = elem["name"]
        min_width = max(bounds["width"], 90.0, 28.0 + len(name) * 4.6)
        min_width = min(min_width, 138.0)
        min_height = max(bounds["height"], 46.0)
        if min_width > bounds["width"]:
            cx, _ = node_center(bounds)
            bounds["x"] = cx - min_width / 2.0
            bounds["width"] = min_width
        if min_height > bounds["height"]:
            _, cy = node_center(bounds)
            bounds["y"] = cy - min_height / 2.0
            bounds["height"] = min_height

    # Enlarge XOR/AND gateways so they match task box scale better
    _gw_min = 36.0
    _gw_scale = 1.0
    for elem_id, bounds in list(shapes.items()):
        elem = elements.get(elem_id)
        if not elem or elem["kind"] not in {"exclusiveGateway", "parallelGateway"}:
            continue
        nw = max(bounds["width"] * _gw_scale, _gw_min)
        nh = max(bounds["height"] * _gw_scale, _gw_min)
        if abs(nw - bounds["width"]) > 0.5 or abs(nh - bounds["height"]) > 0.5:
            cx, cy = node_center(bounds)
            bounds["width"] = nw
            bounds["height"] = nh
            bounds["x"] = cx - nw / 2.0
            bounds["y"] = cy - nh / 2.0

    def orthogonalize_polyline(points):
        """Replace every diagonal segment with a single right-angle bend (Manhattan)."""
        if len(points) < 2:
            return list(points)
        out = [points[0]]
        tol = 1e-6
        for i in range(1, len(points)):
            ax, ay = out[-1]
            bx, by = points[i]
            if abs(ax - bx) < tol and abs(ay - by) < tol:
                continue
            if abs(ax - bx) < tol or abs(ay - by) < tol:
                if abs(bx - out[-1][0]) > tol or abs(by - out[-1][1]) > tol:
                    out.append((bx, by))
                continue
            if abs(bx - ax) >= abs(by - ay):
                mid = (bx, ay)
            else:
                mid = (ax, by)
            if abs(mid[0] - out[-1][0]) > tol or abs(mid[1] - out[-1][1]) > tol:
                out.append(mid)
            if (abs(mid[0] - bx) > tol or abs(mid[1] - by) > tol) and (
                abs(bx - out[-1][0]) > tol or abs(by - out[-1][1]) > tol
            ):
                out.append((bx, by))
        # Drop collinear middle vertices from stair-steps
        if len(out) < 3:
            return out
        simp = [out[0]]
        for j in range(1, len(out) - 1):
            ax, ay = simp[-1]
            bx, by = out[j]
            cx, cy = out[j + 1]
            cross = (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)
            if abs(cross) < 1e-3:
                continue
            simp.append(out[j])
        simp.append(out[-1])
        return simp

    def inset_edge_endpoint_toward_prev(flow_target_id, points):
        """Shorten last segment into end shapes so small arrowheads do not cover the node."""
        if len(points) < 2 or flow_target_id not in shapes:
            return points
        elem = elements.get(flow_target_id)
        if not elem or elem["kind"] != "endEvent":
            return points
        px, py = points[-2]
        bx, by = points[-1]
        dx, dy = bx - px, by - py
        dlen = math.hypot(dx, dy)
        if dlen < 1e-9:
            return points
        inset = 16.0
        t = min(inset, dlen * 0.92)
        ux, uy = dx / dlen, dy / dlen
        pts = list(points)
        pts[-1] = (bx - ux * t, by - uy * t)
        return pts

    def dedupe_consecutive(points, tol=0.05):
        if not points:
            return points
        out = [points[0]]
        for p in points[1:]:
            if abs(p[0] - out[-1][0]) > tol or abs(p[1] - out[-1][1]) > tol:
                out.append(p)
        return out

    edges = {}
    for edge in root.findall(".//bpmndi:BPMNEdge", ns):
        flow_id = edge.attrib.get("bpmnElement")
        points = []
        for wp in edge.findall("di:waypoint", ns):
            points.append((float(wp.attrib["x"]), float(wp.attrib["y"])))
        if flow_id and points:
            edges[flow_id] = points

    for flow_id, points in list(edges.items()):
        flow = sequence_flows.get(flow_id)
        if not flow or len(points) < 2:
            continue
        points = list(points)
        points[0] = adjust_endpoint_to_shape(points[0], points[1], flow["source"])
        points[-1] = adjust_endpoint_to_shape(points[-1], points[-2], flow["target"])
        points = orthogonalize_polyline(points)
        points = inset_edge_endpoint_toward_prev(flow["target"], points)
        points = dedupe_consecutive(points)
        edges[flow_id] = points

    name_to_ids = {}
    for elem_id, elem in elements.items():
        if elem["name"]:
            name_to_ids.setdefault(elem["name"], []).append(elem_id)

    sync_names = set()
    model_names = set()
    mismatch_names = set()
    log_moves = []
    for row in ctx["rows"]:
        move_type = row["moveType"]
        if move_type == "Synchronous Move":
            sync_names.add(row["model_move"])
        elif move_type == "Model Move":
            model_names.add(row["model_move"])
        elif move_type == "Log Move":
            log_moves.append(row)
        elif move_type == "Mismatch Move":
            mismatch_names.add(row["model_move"])
            log_moves.append(row)

    sync_ids = {elem_id for name in sync_names for elem_id in name_to_ids.get(name, [])}
    model_ids = {elem_id for name in model_names for elem_id in name_to_ids.get(name, [])}
    mismatch_ids = {elem_id for name in mismatch_names for elem_id in name_to_ids.get(name, [])}

    xs, ys = [], []
    for b in shapes.values():
        xs.extend([b["x"], b["x"] + b["width"]])
        ys.extend([b["y"], b["y"] + b["height"]])
    for elem_id, b in shapes.items():
        elem = elements.get(elem_id)
        if elem and elem["kind"] == "endEvent":
            ecx = b["x"] + b["width"] / 2.0
            er = min(b["width"], b["height"]) / 2.0
            xs.append(ecx + er + 88.0)
    for pts in edges.values():
        for x, y in pts:
            xs.append(x)
            ys.append(y)

    callouts = []
    callout_w, callout_h = 116.0, 48.0
    base_callout_y = max([b["y"] + b["height"] for b in shapes.values()]) + 72.0
    obstacle_rects_by_id = {elem_id: expanded_rect(b, pad=28.0) for elem_id, b in shapes.items()}
    for idx, row in enumerate(log_moves):
        label = row["log_move"]
        ref_id = None
        if label in name_to_ids:
            ref_id = name_to_ids[label][0]
        else:
            for prior in reversed(ctx["rows"][: max(row["step"] - 1, 0)]):
                candidate = prior["model_move"] if prior["model_move"] != "None" else prior["log_move"]
                if candidate in name_to_ids:
                    ref_id = name_to_ids[candidate][0]
                    break
        if ref_id in shapes:
            rb = shapes[ref_id]
            cx, _ = node_center(rb)
            cy = rb["y"] + rb["height"]
            y = max(base_callout_y, rb["y"] + rb["height"] + 92.0) + idx * 18.0
            bend_y = y - 26.0
            candidates = [
                rb["x"] + rb["width"] + 110.0 + idx * 14.0,
                rb["x"] - callout_w - 110.0 - idx * 14.0,
                max(shapes.values(), key=lambda b: b["x"] + b["width"])["x"] + 72.0,
                min(shapes.values(), key=lambda b: b["x"])["x"] - callout_w - 72.0,
                cx - callout_w / 2.0 + idx * 16.0,
            ]
            route_obstacles = [rect for elem_id, rect in obstacle_rects_by_id.items() if elem_id != ref_id]
            best = None
            for candidate_x in candidates:
                callout_rect = {"x": candidate_x, "y": y, "width": callout_w, "height": callout_h}
                overlap = sum(1 for rect in route_obstacles if not (
                    callout_rect["x"] + callout_rect["width"] < rect["x"]
                    or rect["x"] + rect["width"] < callout_rect["x"]
                    or callout_rect["y"] + callout_rect["height"] < rect["y"]
                    or rect["y"] + rect["height"] < callout_rect["y"]
                ))
                for route in log_move_route_candidates(rb, candidate_x, y):
                    route_hits = route_intersection_count(route, route_obstacles)
                    callout_cx = candidate_x + callout_w / 2.0
                    vertical_on_activity = 250 if abs(callout_cx - cx) < callout_w * 0.75 else 0
                    segment_count = max(len(route) - 1, 1)
                    route_length = sum(
                        abs(p2[0] - p1[0]) + abs(p2[1] - p1[1])
                        for p1, p2 in zip(route, route[1:])
                    )
                    score = (
                        route_hits * 2000
                        + overlap * 500
                        + vertical_on_activity
                        + segment_count * 12
                        + route_length * 0.035
                        + abs(candidate_x - (cx - callout_w / 2.0)) * 0.12
                    )
                    if best is None or score < best[0]:
                        best = (score, candidate_x, route)
            x = best[1]
            route = best[2]
        else:
            x = max(xs) - callout_w
            y = base_callout_y + idx * 18.0
            cx, cy = x + callout_w / 2.0, y - 24.0
            route = [(cx, cy), (cx, y)]
        callout = {"label": label, "x": x, "y": y, "route": route}
        callouts.append(callout)
        xs.extend([x, x + callout_w])
        ys.extend([y, y + callout_h])

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    left_pad, right_pad = 80.0, 80.0
    top_pad, bottom_pad = 82.0, 80.0
    width = max_x - min_x + left_pad + right_pad
    height = max_y - min_y + top_pad + bottom_pad

    out = []
    out.append('<?xml version="1.0" encoding="UTF-8"?>')
    out.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.1f}" height="{height:.1f}" '
        f'viewBox="0 0 {width:.1f} {height:.1f}">'
    )
    out.append("<defs>")
    _amw, _amh = 5.0, 5.0
    _tri = '<path d="M0,0 L10,5 L0,10 Z" fill="#888888"/>'
    _tri_r = '<path d="M0,0 L10,5 L0,10 Z" fill="#444444"/>'
    out.append(
        f'<marker id="arrow-grey" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="{_amw}" markerHeight="{_amh}" orient="auto" markerUnits="userSpaceOnUse">{_tri}</marker>'
    )
    out.append(
        f'<marker id="arrow-red" viewBox="0 0 10 10" refX="9" refY="5" '
        f'markerWidth="{_amw}" markerHeight="{_amh}" orient="auto" markerUnits="userSpaceOnUse">{_tri_r}</marker>'
    )
    out.append("</defs>")
    out.append('<rect x="0" y="0" width="100%" height="100%" fill="white"/>')
    out.append('<text x="24" y="44" font-family="Arial, sans-serif" font-size="13" fill="black">Process Model Alignment</text>')
    out.append(f'<text x="24" y="67" font-family="Arial, sans-serif" font-size="10" fill="#555">{esc(ctx["trace_label"])}</text>')

    for flow_id, pts in edges.items():
        points = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in pts)
        out.append(
            f'<polyline points="{points}" fill="none" stroke="#888888" stroke-width="2" '
            f'stroke-linejoin="miter" stroke-linecap="butt" marker-end="url(#arrow-grey)"/>'
        )

    for elem_id, b in shapes.items():
        elem = elements.get(elem_id, {"kind": "task", "name": ""})
        kind = elem["kind"]
        x, y, w, h = tx(b["x"]), ty(b["y"]), b["width"], b["height"]
        name = elem["name"]
        fill = "white"
        stroke = "#888888"
        stroke_width = 2
        text_color = "#333333"
        if elem_id in sync_ids:
            fill = "#F2F2F2"
            stroke = "#AAAAAA"
            stroke_width = 3
            text_color = "#444444"
        if elem_id in model_ids:
            fill = "#E0E0E0"
            stroke = "#555555"
            stroke_width = 4
            text_color = "#222222"
        if elem_id in mismatch_ids:
            fill = "#E8E8E8"
            stroke = "#777777"
            stroke_width = 4
            text_color = "#333333"

        if kind == "task":
            out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="7" ry="7" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>')
            lines = label_lines_for_box(name, w, font_size=9)
            line_gap = 10.5
            start_y = y + h / 2.0 - (len(lines) - 1) * line_gap / 2.0
            for line_idx, line in enumerate(lines):
                out.append(f'<text x="{x + w / 2.0:.1f}" y="{start_y + line_idx * line_gap:.1f}" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="9" fill="{text_color}">{esc(line)}</text>')
        elif kind in {"exclusiveGateway", "parallelGateway"}:
            cx, cy = x + w / 2.0, y + h / 2.0
            points = f"{cx:.1f},{y:.1f} {x + w:.1f},{cy:.1f} {cx:.1f},{y + h:.1f} {x:.1f},{cy:.1f}"
            out.append(f'<polygon points="{points}" fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>')
            marker = "+" if kind == "parallelGateway" else "X"
            g_fs = max(13.0, min(w, h) * 0.34)
            out.append(f'<text x="{cx:.1f}" y="{cy + 0.5:.1f}" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="{g_fs:.1f}" fill="{stroke}">{marker}</text>')
        elif kind in {"startEvent", "endEvent"}:
            cx, cy = x + w / 2.0, y + h / 2.0
            r = min(w, h) / 2.0
            sw = 3 if kind == "endEvent" else 2
            out.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
            if kind == "startEvent":
                out.append(
                    f'<text x="{cx:.1f}" y="{cy + h / 2.0 + 18.0:.1f}" text-anchor="middle" '
                    f'font-family="Arial, sans-serif" font-size="9" fill="{stroke}">START</text>'
                )
            else:
                lbl_x = cx + r + 10.0
                out.append(
                    f'<text x="{lbl_x:.1f}" y="{cy:.1f}" text-anchor="start" dominant-baseline="middle" '
                    f'font-family="Arial, sans-serif" font-size="9" fill="{stroke}">END EVENT</text>'
                )

    for callout in callouts:
        x, y = tx(callout["x"]), ty(callout["y"])
        cx = x + callout_w / 2.0
        route_points = " ".join(f"{tx(px):.1f},{ty(py):.1f}" for px, py in callout["route"])
        out.append(
            f'<polyline points="{route_points}" fill="none" stroke="#444444" stroke-width="2.5" '
            f'stroke-dasharray="7 5" stroke-linejoin="miter" stroke-linecap="butt" marker-end="url(#arrow-red)"/>'
        )
        out.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{callout_w:.1f}" height="{callout_h:.1f}" rx="7" ry="7" fill="#D8D8D8" stroke="#444444" stroke-width="3" stroke-dasharray="8 5"/>')
        lines = label_lines_for_box(callout["label"], callout_w, font_size=10)
        start_y = y + callout_h / 2.0 - (len(lines) - 1) * 6.0
        for line_idx, line in enumerate(lines):
            out.append(f'<text x="{cx:.1f}" y="{start_y + line_idx * 12:.1f}" text-anchor="middle" dominant-baseline="middle" font-family="Arial, sans-serif" font-size="9" fill="#222222">{esc(line)}</text>')

    legend_y = height - 32
    legend_x = width / 2.0 - 280
    legend_items = [(GREEN, "Synchronous move (Conform)"), (BLUE, "Model move only"), ("#444444", "Log move only")]
    for i, (color, label) in enumerate(legend_items):
        x = legend_x + i * 205
        out.append(f'<rect x="{x:.1f}" y="{legend_y - 11:.1f}" width="22" height="12" fill="{color}" stroke="#888888" stroke-width="0.8"/>')
        out.append(f'<text x="{x + 32:.1f}" y="{legend_y:.1f}" font-family="Arial, sans-serif" font-size="9" fill="#222">{esc(label)}</text>')
    out.append("</svg>")

    path = os.path.join(output_dir, "task28_flow_chart_elaborate_bpmn.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))
    logger.debug(f"      Saved: {path}")




# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(alignments, model_path: str, output_dir: str):
    """Generate all Task 2 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 2 visualizations ---")
    ctx = build_task28_context(alignments)
    if ctx is None:
        logger.warning("      Skipped Task 2: no alignment steps in representative trace.")
        return
    logger.info(f"      Using {ctx['trace_label']} (log index {ctx['trace_index']}, fitness={ctx['fitness']:.4f})")
    task28_alignment_table(ctx, output_dir)
    task28_flow_chart_basic(ctx, output_dir)
    task28_flow_chart_and_table(ctx, output_dir)
    task28_flow_chart_elaborate_bpmn(ctx, model_path, output_dir)
