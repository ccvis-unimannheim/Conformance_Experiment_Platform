"""
tasks/task24.py – Task ID 24: Explore / Discover / Guideline violations in model.

Discovers the directly-follows graph (DFG) from the event log and compares it to the
reference BPMN to reveal where observed behaviour deviates from the desired model.

Public API:
    generate(log, model_path, output_dir)
        log        – PM4Py EventLog
        model_path – path to the reference BPMN file
        output_dir – directory where SVGs are written

Two idioms (renamed by pipeline to canonical slugs):
    task24_flow_chart_elaborate_bpmn  →  flow_chart_elaborate.svg
    task24_flow_chart_and_table       →  flow_chart_table.svg
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_elaborate_bpmn", "flow_chart_and_table"]

import html
import math
import os
import xml.etree.ElementTree as ET
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import save_svg, make_table, FONT_TITLE, FONT_ANNOT

# Minimum DFG edge frequency to count as real observed behaviour (raise to de-clutter)
NOISE_THRESHOLD = 1

_BPMN_NS = {
    "bpmn":   "http://www.omg.org/spec/BPMN/20100524/MODEL",
    "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
    "dc":     "http://www.omg.org/spec/DD/20100524/DC",
    "di":     "http://www.omg.org/spec/DD/20100524/DI",
}


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _discover_dfg(log, noise_threshold: int) -> dict:
    """Return {(a, b): count} directly-follows pairs with count >= noise_threshold."""
    dfg: Counter = Counter()
    for trace in log:
        acts = [str(e.get("concept:name", "")) for e in trace if e.get("concept:name")]
        for a, b in zip(acts, acts[1:]):
            dfg[(a, b)] += 1
    return {pair: cnt for pair, cnt in dfg.items() if cnt >= noise_threshold}


def _parse_bpmn(model_path: str):
    """Parse BPMN; return (elements, sequence_flows, shapes, edge_pts, name_to_ids).

    Applies the same coordinate normalisation as task28 so layouts are consistent:
    box expansion, gateway resize, orthogonalisation, endpoint inset.
    """
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

    return elements, sequence_flows, shapes, edge_pts, name_to_ids


def _model_task_edges(elements: dict, sequence_flows: dict) -> set:
    """Set of (src_name, tgt_name) for task-to-task reachability; gateways collapsed."""
    adj = {}
    for sf in sequence_flows.values():
        adj.setdefault(sf["source"], []).append(sf["target"])

    task_ids = {eid for eid, e in elements.items() if e["kind"] == "task" and e.get("name")}
    model_edges = set()
    for src_id in task_ids:
        src_name = elements[src_id]["name"]
        queue, visited = list(adj.get(src_id, [])), set()
        while queue:
            cur = queue.pop(0)
            if cur in visited:
                continue
            visited.add(cur)
            elem = elements.get(cur)
            if elem and elem["kind"] == "task" and elem.get("name"):
                model_edges.add((src_name, elem["name"]))
            else:
                queue.extend(adj.get(cur, []))
    return model_edges


def _compute_diff(log, model_path: str, noise_threshold: int = NOISE_THRESHOLD) -> dict:
    """Diff observed DFG against reference BPMN model edges."""
    dfg_counts     = _discover_dfg(log, noise_threshold)
    observed_edges = set(dfg_counts.keys())
    observed_acts  = {a for pair in observed_edges for a in pair}

    elements, sequence_flows, shapes, edge_pts, name_to_ids = _parse_bpmn(model_path)
    model_task_names = {e["name"] for e in elements.values() if e["kind"] == "task" and e["name"]}
    model_edges      = _model_task_edges(elements, sequence_flows)

    conform_edges         = observed_edges & model_edges
    in_model_not_observed = model_edges    - observed_edges
    observed_not_in_model = observed_edges - model_edges
    extra_activities      = observed_acts  - model_task_names
    missing_activities    = model_task_names - observed_acts

    logger.info(f"      -> DFG edges (≥{noise_threshold}): {len(observed_edges)}"
                f"  |  Model edges: {len(model_edges)}")
    logger.info(f"      -> Conform: {len(conform_edges)}"
                f"  |  In-model-not-observed: {len(in_model_not_observed)}"
                f"  |  Observed-not-in-model: {len(observed_not_in_model)}")

    return {
        "model_task_names": model_task_names, "observed_activities": observed_acts,
        "model_edges": model_edges, "observed_edges": observed_edges,
        "conform_edges": conform_edges,
        "in_model_not_observed": in_model_not_observed,
        "observed_not_in_model": observed_not_in_model,
        "extra_activities": extra_activities,
        "missing_activities": missing_activities,
        "dfg_counts": dfg_counts,
        "elements": elements, "sequence_flows": sequence_flows,
        "shapes": shapes, "edge_pts": edge_pts, "name_to_ids": name_to_ids,
    }


# ---------------------------------------------------------------------------
# SVG helpers
# ---------------------------------------------------------------------------

def _esc(v) -> str:
    return html.escape("" if v is None else str(v), quote=True)


def _label_lines(label, box_width, font_size=9) -> list:
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


# ---------------------------------------------------------------------------
# Idiom 1 – Process graph with aggregate diff coloring
# ---------------------------------------------------------------------------

def task24_flow_chart_elaborate_bpmn(diff: dict, output_dir: str):
    """BPMN model graph decorated with discovery-diff coloring.

    Always uses node-highlight fallback (no extra arrow routing):
      missing task nodes         → faded fill + light stroke
      violation endpoint nodes   → dark border (endpoint of observed-not-in-model edge)
      flows from/to missing task → faded dashed line
    """
    logger.info("      -> Fallback mode: observed-not-in-model edges shown via node highlighting.")

    elements  = diff["elements"];  shapes   = diff["shapes"]
    edge_pts  = diff["edge_pts"];  seq_flows = diff["sequence_flows"]
    name_to_ids = diff["name_to_ids"]
    missing_activities    = diff["missing_activities"]
    observed_not_in_model = diff["observed_not_in_model"]

    missing_ids   = {eid for n in missing_activities                                for eid in name_to_ids.get(n, [])}
    violation_eps = {a for (a, b) in observed_not_in_model} | {b for (a, b) in observed_not_in_model}
    violation_ids = {eid for n in violation_eps                                     for eid in name_to_ids.get(n, [])}

    def _flow_faded(flow_id):
        sf = seq_flows.get(flow_id)
        if not sf:
            return False
        for role in ("source", "target"):
            e = elements.get(sf[role], {})
            if e.get("kind") == "task" and e.get("name", "") in missing_activities:
                return True
        return False

    # Bounding box
    xs, ys = [], []
    for b in shapes.values():
        xs += [b["x"], b["x"] + b["width"]];  ys += [b["y"], b["y"] + b["height"]]
    for eid, b in shapes.items():
        if elements.get(eid, {}).get("kind") == "endEvent":
            xs.append(b["x"] + b["width"] / 2.0 + min(b["width"], b["height"]) / 2.0 + 88.0)
    for pts in edge_pts.values():
        for px, py in pts:
            xs.append(px); ys.append(py)

    if not xs or not ys:
        logger.warning("      task24: no BPMN shapes — skipping elaborate render.")
        return

    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    lp, rp, tp, bp = 80.0, 80.0, 88.0, 68.0
    W = max_x - min_x + lp + rp
    H = max_y - min_y + tp + bp

    def tx(x): return x - min_x + lp
    def ty(y): return y - min_y + tp

    has_viol  = bool(observed_not_in_model)
    has_miss  = bool(missing_activities)
    has_imno  = bool(diff["in_model_not_observed"])
    no_diff   = not has_viol and not has_miss and not has_imno

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H:.1f}" '
        f'viewBox="0 0 {W:.1f} {H:.1f}">',
        "<defs>",
    ]
    for mid, col in [("arrow-grey", "#888888"), ("arrow-faded", "#CCCCCC")]:
        out.append(
            f'<marker id="{mid}" viewBox="0 0 10 10" refX="9" refY="5" '
            f'markerWidth="5" markerHeight="5" orient="auto" markerUnits="userSpaceOnUse">'
            f'<path d="M0,0 L10,5 L0,10 Z" fill="{col}"/></marker>'
        )
    out += [
        "</defs>",
        '<rect x="0" y="0" width="100%" height="100%" fill="white"/>',
        '<text x="24" y="44" font-family="Arial, sans-serif" font-size="13" fill="black">'
        'Discovered vs. Desired Model &#8212; Differences</text>',
    ]

    if no_diff:
        summary = "No structural differences detected between log behaviour and model."
    else:
        parts = []
        if has_viol: parts.append(f"{len(observed_not_in_model)} observed-not-in-model transition(s)")
        if has_miss: parts.append(f"{len(missing_activities)} task(s) never observed")
        if has_imno: parts.append(f"{len(diff['in_model_not_observed'])} model edge(s) not observed")
        summary = "; ".join(parts)
    out.append(
        f'<text x="24" y="67" font-family="Arial, sans-serif" font-size="10" fill="#555">'
        f'{_esc(summary)}</text>'
    )

    # Edges
    for fid, pts in edge_pts.items():
        pts_str = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in pts)
        if _flow_faded(fid):
            out.append(
                f'<polyline points="{pts_str}" fill="none" stroke="#CCCCCC" stroke-width="1.5" '
                f'stroke-dasharray="5 4" stroke-linejoin="miter" marker-end="url(#arrow-faded)"/>'
            )
        else:
            out.append(
                f'<polyline points="{pts_str}" fill="none" stroke="#888888" stroke-width="2" '
                f'stroke-linejoin="miter" stroke-linecap="butt" marker-end="url(#arrow-grey)"/>'
            )

    # Nodes
    for eid, b in shapes.items():
        elem = elements.get(eid, {"kind": "task", "name": ""})
        kind = elem["kind"]; name = elem.get("name", "")
        x, y, w, h = tx(b["x"]), ty(b["y"]), b["width"], b["height"]

        fill, stroke, sw, tc = "white", "#888888", 2, "#333333"
        if eid in missing_ids:
            fill, stroke, sw, tc = "#EBEBEB", "#BBBBBB", 2, "#AAAAAA"
        elif eid in violation_ids:
            stroke, sw = "#444444", 3

        if kind == "task":
            out.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'rx="7" ry="7" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>'
            )
            lines = _label_lines(name, w)
            gap = 10.5; sy = y + h / 2.0 - (len(lines) - 1) * gap / 2.0
            for i, line in enumerate(lines):
                out.append(
                    f'<text x="{x + w / 2.0:.1f}" y="{sy + i * gap:.1f}" text-anchor="middle" '
                    f'dominant-baseline="middle" font-family="Arial, sans-serif" font-size="9" '
                    f'fill="{tc}">{_esc(line)}</text>'
                )
        elif kind in {"exclusiveGateway", "parallelGateway"}:
            cx, cy = x + w / 2.0, y + h / 2.0
            pts_str = f"{cx:.1f},{y:.1f} {x+w:.1f},{cy:.1f} {cx:.1f},{y+h:.1f} {x:.1f},{cy:.1f}"
            out.append(f'<polygon points="{pts_str}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"/>')
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
                f'stroke="{stroke}" stroke-width="{sw2}"/>'
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

    # Legend
    ley = H - 28; lex = 24.0
    legend_items = [
        ("white",   "#888888", 2, "Conform (in model and observed)"),
        ("#EBEBEB", "#BBBBBB", 2, "In model, not observed"),
        ("white",   "#444444", 3, "Endpoint of observed-not-in-model transition"),
    ]
    for i, (lf, ls, lsw, lbl) in enumerate(legend_items):
        lx = lex + i * 265
        out.append(
            f'<rect x="{lx:.1f}" y="{ley - 11:.1f}" width="22" height="12" '
            f'fill="{lf}" stroke="{ls}" stroke-width="{lsw}"/>'
        )
        out.append(
            f'<text x="{lx + 30:.1f}" y="{ley:.1f}" font-family="Arial, sans-serif" '
            f'font-size="9" fill="#222">{_esc(lbl)}</text>'
        )

    out.append("</svg>")
    path = os.path.join(output_dir, "task24_flow_chart_elaborate_bpmn.svg")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(out))
    logger.debug(f"      Saved: {path}")


# ---------------------------------------------------------------------------
# Idiom 2 – Difference table
# ---------------------------------------------------------------------------

def task24_flow_chart_and_table(diff: dict, output_dir: str):
    """Difference table: Type | From / Activity | To | Observed Frequency."""
    dfg_counts            = diff["dfg_counts"]
    observed_not_in_model = diff["observed_not_in_model"]
    in_model_not_observed = diff["in_model_not_observed"]
    extra_activities      = diff["extra_activities"]
    missing_activities    = diff["missing_activities"]

    rows = []
    for (a, b) in sorted(observed_not_in_model, key=lambda e: -dfg_counts.get(e, 0)):
        rows.append(["Observed not in model", a, b, str(dfg_counts.get((a, b), 0))])
    for (a, b) in sorted(in_model_not_observed):
        rows.append(["In model, not observed", a, b, "—"])
    for act in sorted(extra_activities):
        rows.append(["Extra activity (log only)", act, "—", "—"])
    for act in sorted(missing_activities):
        rows.append(["Missing activity (model only)", act, "—", "—"])

    if not rows:
        rows = [["(No structural differences detected)", "—", "—", "—"]]

    fig_h = max(3.5, 1.4 + len(rows) * 0.42)
    fig, ax = plt.subplots(figsize=(14, fig_h))
    ax.axis("off")
    make_table(
        ax,
        cell_text=rows,
        col_labels=["Type", "From / Activity", "To", "Observed Frequency"],
        bbox=[0.02, 0.05, 0.96, 0.88],
        col_widths=[0.36, 0.26, 0.22, 0.16],
        font_size=10,
        scale_xy=(1, 1.7),
        cell_pad=0.10,
    )
    ax.set_title("Guideline Violations — Discovery Diff", fontsize=FONT_TITLE, pad=4)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task24_flow_chart_and_table.svg"))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def generate(log, model_path: str, output_dir: str):
    """Generate all Task ID 24 SVGs into output_dir."""
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task ID 24 visualizations ---")

    if not log:
        logger.warning("      task24: empty log — skipping.")
        return

    try:
        diff = _compute_diff(log, model_path, noise_threshold=NOISE_THRESHOLD)
    except Exception as e:
        logger.warning(f"      task24: computation failed: {e}")
        return

    if not diff["elements"]:
        logger.warning("      task24: no elements found in BPMN — skipping.")
        return

    task24_flow_chart_elaborate_bpmn(diff, output_dir)
    task24_flow_chart_and_table(diff, output_dir)
