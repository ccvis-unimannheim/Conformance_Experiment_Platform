"""
tasks/task35.py – Task 35: Guideline Violations in Model
Goal: Present · Means: Present · Characteristics: Guideline violations in model

Question: Where does the recorded behavior violate which guidelines?
          Violations (skip / insert) annotated directly on the BPMN process model.

Idioms:
  flow_chart_elaborate       – BPMN shaded by violation count; skip/insert counts per node
  flow_chart_elaborate_table – same BPMN + violation breakdown table below
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["flow_chart_elaborate", "flow_chart_elaborate_table", "petri_net", "flow_chart_elaborate_dfg"]

import os
import html as _html
import io as _io
import base64 as _base64
import re as _re
import xml.etree.ElementTree as _ET
from collections import Counter

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from shared import save_svg, FONT_TITLE, FONT_ANNOT, classify_step as _classify_step

_C_DARK = "#222222"
_C_MED  = "#666666"
_HDR_BG = "#333333"
_TOP_N  = 15


# ── Data extraction ────────────────────────────────────────────────────────────

def _extract_data(alignments):
    activity_type = Counter()
    for aln in alignments:
        for step in aln.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            act, vtype = _classify_step(step[0], step[1])
            if act is None:
                continue
            activity_type[(act, vtype)] += 1
    activity_totals = Counter()
    type_totals = Counter()
    for (act, vtype), cnt in activity_type.items():
        activity_totals[act] += cnt
        type_totals[vtype] += cnt
    return activity_type, activity_totals, type_totals, sum(activity_type.values())


# ── Helpers ────────────────────────────────────────────────────────────────────

def _violation_shade(rate):
    """Light (#eeeeee) → dark (#333333) as rate goes 0 → 1."""
    v = round(238 - max(0.0, min(1.0, rate)) * (238 - 51))
    return f"#{v:02x}{v:02x}{v:02x}"


def _short(label, n=26):
    return label if len(label) <= n else label[: n - 1] + "…"


def _save_empty(output_dir, filename, msg="No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, msg, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


# ── BPMN rendering ─────────────────────────────────────────────────────────────

def _make_bpmn_svg(activity_type, activity_totals, model_path):
    """Return SVG string: BPMN nodes shaded by violation rate; skip/insert annotated."""
    ns = {
        "bpmn":   "http://www.omg.org/spec/BPMN/20100524/MODEL",
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        "dc":     "http://www.omg.org/spec/DD/20100524/DC",
        "di":     "http://www.omg.org/spec/DD/20100524/DI",
    }

    def local(tag): return tag.split("}", 1)[-1] if "}" in tag else tag
    def esc(v):     return _html.escape("" if v is None else str(v), quote=True)

    try:
        tree = _ET.parse(model_path)
    except Exception:
        return None
    root = tree.getroot()

    elements = {}
    for e in root.findall(".//bpmn:*", ns):
        eid  = e.attrib.get("id")
        kind = local(e.tag)
        if eid and kind in {"task", "startEvent", "endEvent",
                            "exclusiveGateway", "parallelGateway"}:
            elements[eid] = {"kind": kind, "name": e.attrib.get("name", "")}

    shapes = {}
    for s in root.findall(".//bpmndi:BPMNShape", ns):
        eid = s.attrib.get("bpmnElement")
        b   = s.find("dc:Bounds", ns)
        if eid and b is not None:
            shapes[eid] = {
                "x": float(b.attrib["x"]), "y": float(b.attrib["y"]),
                "width": float(b.attrib["width"]), "height": float(b.attrib["height"]),
            }

    edges = {}
    for e in root.findall(".//bpmndi:BPMNEdge", ns):
        fid = e.attrib.get("bpmnElement")
        pts = [(float(wp.attrib["x"]), float(wp.attrib["y"]))
               for wp in e.findall("di:waypoint", ns)]
        if fid and pts:
            edges[fid] = pts

    if not shapes:
        return None

    max_v   = max(activity_totals.values()) if activity_totals else 1
    max_act = max(activity_totals, key=activity_totals.get) if activity_totals else ""
    max_cnt = activity_totals.get(max_act, 0)
    name_to_rate = {name: cnt / max_v for name, cnt in activity_totals.items()}

    xs, ys = [], []
    for b in shapes.values():
        xs += [b["x"], b["x"] + b["width"]]
        ys += [b["y"], b["y"] + b["height"]]
    for pts in edges.values():
        for px, py in pts:
            xs.append(px); ys.append(py)

    min_x, min_y = min(xs), min(ys)
    W = max(xs) - min_x + 120
    H = max(ys) - min_y + 210  # extra for title + legend

    def tx(x): return x - min_x + 60
    def ty(y): return y - min_y + 85

    def auto_fit_text(label, box_w, box_h, has_ann):
        import re as _re2
        tokens = _re2.split(r'[ _]+', str(label))
        ann_reserve = 14 if has_ann else 0
        avail_h = box_h - ann_reserve - 8  # 4px pad top+bottom

        for fs in [10, 9, 8, 7, 6.5, 6]:
            gap = fs + 2.5
            mc  = max(4, int((box_w - 10) / (fs * 0.65)))
            lines, cur = [], ""
            for tok in tokens:
                cand = tok if not cur else f"{cur} {tok}"
                if len(cand) <= mc:
                    cur = cand
                else:
                    if cur:
                        lines.append(cur)
                    # hard-clip single token wider than mc
                    cur = tok[:mc]
            if cur:
                lines.append(cur)
            lines = lines[:4]
            if len(lines) * gap <= avail_h:
                return lines, fs, gap

        # Absolute fallback: 1 line, smallest font
        mc = max(4, int((box_w - 10) / (6 * 0.65)))
        return [str(label)[:mc]], 6, 8.5

    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W:.1f}" height="{H:.1f}" '
        f'viewBox="0 0 {W:.1f} {H:.1f}">',
        "<defs><marker id='arr' viewBox='0 0 10 10' refX='9' refY='5' "
        "markerWidth='5' markerHeight='5' orient='auto' markerUnits='userSpaceOnUse'>"
        "<path d='M0,0 L10,5 L0,10 Z' fill='#888'/></marker></defs>",
        "<rect width='100%' height='100%' fill='white'/>",
        f"<text x='{W/2:.1f}' y='28' text-anchor='middle' "
        f"font-family='Arial,sans-serif' font-size='14' font-weight='bold' fill='{_C_DARK}'>"
        "Guideline Violations in Process Model</text>",
        f"<text x='{W/2:.1f}' y='46' text-anchor='middle' "
        f"font-family='Arial,sans-serif' font-size='9' fill='{_C_MED}'>"
        "Darker = more violations  ·  node labels: skip (↑) and insert (↓) counts</text>",
    ]

    # Edges
    for fid, pts in edges.items():
        pstr = " ".join(f"{tx(x):.1f},{ty(y):.1f}" for x, y in pts)
        out.append(f"<polyline points='{pstr}' fill='none' stroke='#999' "
                   f"stroke-width='1.8' marker-end='url(#arr)'/>")

    # Shapes
    for eid, b in shapes.items():
        elem = elements.get(eid, {"kind": "task", "name": ""})
        kind, name = elem["kind"], elem["name"]
        x, y, w, h = tx(b["x"]), ty(b["y"]), b["width"], b["height"]
        rate  = name_to_rate.get(name, 0.0)
        fill  = _violation_shade(rate) if kind == "task" else "#f0f0f0"
        stroke = "#777"
        v_int  = int(fill[1:3], 16)
        tc     = "white" if v_int < 140 else _C_DARK

        if kind == "task":
            mom   = activity_type.get((name, "Move on Model"), 0)
            mol   = activity_type.get((name, "Move on Log"),   0)
            total = activity_totals.get(name, 0)
            clip_id = f"clip_{eid}"
            # clip-path to prevent any text overflow beyond the rect
            out.append(
                f"<clipPath id='{clip_id}'>"
                f"<rect x='{x+1:.1f}' y='{y+1:.1f}' width='{w-2:.1f}' height='{h-2:.1f}' rx='5'/>"
                f"</clipPath>"
            )
            out.append(
                f"<rect x='{x:.1f}' y='{y:.1f}' width='{w:.1f}' height='{h:.1f}' "
                f"rx='6' fill='{fill}' stroke='{stroke}' stroke-width='2'/>"
            )
            has_ann         = total > 0
            lines, fs, gap  = auto_fit_text(name, w, h, has_ann)
            text_block_h    = (len(lines) - 1) * gap
            ann_reserve     = 14 if has_ann else 0
            # Centre the text block in the available vertical space
            sy = y + (h - ann_reserve) / 2 - text_block_h / 2
            for li, line in enumerate(lines):
                out.append(
                    f"<text x='{x+w/2:.1f}' y='{sy+li*gap:.1f}' "
                    f"text-anchor='middle' dominant-baseline='middle' "
                    f"font-family='Arial,sans-serif' font-size='{fs}' fill='{tc}' "
                    f"clip-path='url(#{clip_id})'>"
                    f"{esc(line)}</text>"
                )
            if has_ann:
                ann_tc    = "white" if v_int < 155 else _C_MED
                ann       = f"↑{mom}  ↓{mol}"
                ann_fs    = max(6, fs - 1.5)
                max_ann_w = w - 6
                out.append(
                    f"<text x='{x+w/2:.1f}' y='{y+h-5:.1f}' "
                    f"text-anchor='middle' dominant-baseline='middle' "
                    f"font-family='Arial,sans-serif' font-size='{ann_fs}' fill='{ann_tc}' "
                    f"textLength='{min(max_ann_w, len(ann)*ann_fs*0.6):.1f}' "
                    f"lengthAdjust='spacingAndGlyphs' clip-path='url(#{clip_id})'>"
                    f"{esc(ann)}</text>"
                )

        elif kind in {"exclusiveGateway", "parallelGateway"}:
            cx, cy = x + w / 2, y + h / 2
            out.append(
                f"<polygon points='{cx:.1f},{y:.1f} {x+w:.1f},{cy:.1f} "
                f"{cx:.1f},{y+h:.1f} {x:.1f},{cy:.1f}' "
                f"fill='#f0f0f0' stroke='{stroke}' stroke-width='2'/>"
            )
            mk = "+" if kind == "parallelGateway" else "×"
            fs = max(13.0, min(w, h) * 0.38)
            out.append(
                f"<text x='{cx:.1f}' y='{cy+1:.1f}' text-anchor='middle' "
                f"dominant-baseline='middle' font-family='Arial,sans-serif' "
                f"font-size='{fs:.0f}' fill='{stroke}'>{mk}</text>"
            )

        elif kind in {"startEvent", "endEvent"}:
            cx, cy = x + w / 2, y + h / 2
            r  = min(w, h) / 2
            sw = 3 if kind == "endEvent" else 2
            out.append(
                f"<circle cx='{cx:.1f}' cy='{cy:.1f}' r='{r:.1f}' "
                f"fill='white' stroke='{stroke}' stroke-width='{sw}'/>"
            )
            lbl = "START" if kind == "startEvent" else "END"
            out.append(
                f"<text x='{cx:.1f}' y='{y+h+14:.1f}' text-anchor='middle' "
                f"font-family='Arial,sans-serif' font-size='8' fill='{stroke}'>{lbl}</text>"
            )

    # Greyscale legend
    ly       = H - 58
    STEP     = 58; SW_W = 26; SW_H = 16; LBL_FS = 10
    cnt_lbl  = f"{max_cnt:,}"
    tail_str = f"violations  ·  most: {_short(max_act, 20)}"
    sbar_w   = 4 * STEP + SW_W
    cnt_w    = len(cnt_lbl) * 6.5 + 10
    tail_w   = len(tail_str) * 5.8 + 8
    box_pad  = 14
    box_w    = sbar_w + cnt_w + tail_w + 2 * box_pad
    off      = max(10.0, (W - box_w) / 2)

    out.append(
        f"<rect x='{off - box_pad:.1f}' y='{ly - 10:.1f}' "
        f"width='{box_w:.1f}' height='{SW_H + 22:.1f}' "
        f"rx='5' fill='#fafafa' stroke='#cccccc' stroke-width='1'/>"
    )
    for i, (lvl, lbl) in enumerate([(0.0, "0"), (0.25, ""), (0.5, "50%"), (0.75, ""), (1.0, cnt_lbl)]):
        bx    = off + i * STEP
        shade = _violation_shade(lvl)
        out.append(
            f"<rect x='{bx:.1f}' y='{ly:.1f}' width='{SW_W}' height='{SW_H}' "
            f"fill='{shade}' stroke='#aaa' stroke-width='0.8'/>"
        )
        if lbl:
            out.append(
                f"<text x='{bx + SW_W + 4:.1f}' y='{ly + SW_H - 2:.1f}' "
                f"font-family='Arial,sans-serif' font-size='{LBL_FS}' fill='{_C_MED}'>"
                f"{esc(lbl)}</text>"
            )
    tail_x = off + 4 * STEP + SW_W + cnt_w
    out.append(
        f"<text x='{tail_x:.1f}' y='{ly + SW_H - 2:.1f}' "
        f"font-family='Arial,sans-serif' font-size='{LBL_FS}' fill='{_C_MED}'>"
        f"{esc(tail_str)}</text>"
    )

    out.append("</svg>")
    return "\n".join(out)


# ── Idiom 1: flow_chart_elaborate ─────────────────────────────────────────────

def task35_flow_chart_elaborate_bpmn(activity_type, activity_totals, model_path, output_dir):
    fname = "task35_flow_chart_elaborate_bpmn.svg"
    if model_path is None:
        _save_empty(output_dir, fname, "No process model provided — BPMN file required.")
        return
    if not activity_totals:
        _save_empty(output_dir, fname, "No guideline violations found.")
        return
    svg = _make_bpmn_svg(activity_type, activity_totals, model_path)
    if svg is None:
        _save_empty(output_dir, fname, "Could not parse process model.")
        return
    with open(os.path.join(output_dir, fname), "w", encoding="utf-8") as f:
        f.write(svg)


# ── Idiom 2: flow_chart_elaborate_table ───────────────────────────────────────

def _svg_dims(svg_str):
    m = _re.search(r'<svg[^>]*\bwidth="([^"]+)"[^>]*\bheight="([^"]+)"', svg_str)
    if m:
        w = float(_re.sub(r"[^\d.]", "", m.group(1)))
        h = float(_re.sub(r"[^\d.]", "", m.group(2)))
        return w, h
    return None, None


def task35_flow_chart_elaborate_bpmn_table(activity_type, activity_totals, n_violations,
                                           model_path, output_dir):
    """Composite SVG: BPMN model (top) + per-activity violation table (bottom)."""
    fname = "task35_flow_chart_elaborate_bpmn_table.svg"

    if not activity_totals:
        _save_empty(output_dir, fname, "No guideline violations found.")
        return

    top_acts = [a for a, _ in activity_totals.most_common(_TOP_N)]
    n_rows   = len(top_acts)
    tbl_w_in = 14.0
    tbl_h_in = max(3.5, n_rows * 0.48 + 2.0)

    tbl_fig, tbl_ax = plt.subplots(figsize=(tbl_w_in, tbl_h_in))
    tbl_ax.axis("off")

    col_headers = ["Activity", "Skipped (MoM)", "Inserted (MoL)", "Mismatch", "Total", "% of All"]
    col_widths  = [0.34, 0.14, 0.14, 0.12, 0.10, 0.10]
    t = 0.94; l = 0.02; tw = 0.96
    row_h = (t - 0.06) / (n_rows + 1)

    x = l
    for hdr, cw in zip(col_headers, col_widths):
        tbl_ax.add_patch(plt.Rectangle((x, t - row_h), cw * tw, row_h,
                                       fc=_HDR_BG, ec="white", linewidth=0.5,
                                       transform=tbl_ax.transAxes, clip_on=False))
        tbl_ax.text(x + cw * tw * 0.5, t - row_h * 0.5, hdr,
                    ha="center", va="center", fontsize=FONT_ANNOT,
                    color="white", fontweight="bold", transform=tbl_ax.transAxes)
        x += cw * tw

    for i, act in enumerate(top_acts):
        mom   = activity_type.get((act, "Move on Model"), 0)
        mol   = activity_type.get((act, "Move on Log"),   0)
        mm    = activity_type.get((act, "Mismatch Move"), 0)
        total = mom + mol + mm
        pct   = total / n_violations * 100 if n_violations > 0 else 0
        row_vals = [_short(act, 32), mom, mol, mm, total, f"{pct:.1f}%"]
        y_top = t - (i + 2) * row_h
        x     = l
        bg    = "#f5f5f5" if i % 2 == 0 else "white"
        for j, (val, cw) in enumerate(zip(row_vals, col_widths)):
            tbl_ax.add_patch(plt.Rectangle((x, y_top), cw * tw, row_h,
                                           fc=bg, ec="#eeeeee", linewidth=0.4,
                                           transform=tbl_ax.transAxes, clip_on=False))
            ha = "left" if j == 0 else "center"
            px = x + 0.008 if j == 0 else x + cw * tw * 0.5
            tbl_ax.text(px, y_top + row_h * 0.5, str(val),
                        ha=ha, va="center", fontsize=FONT_ANNOT,
                        color=_C_DARK, transform=tbl_ax.transAxes)
            x += cw * tw

    tbl_ax.set_title(f"Violation Breakdown per Activity  (top {n_rows})",
                     fontsize=FONT_TITLE, pad=14)
    tbl_fig.tight_layout(pad=1.2)
    buf = _io.BytesIO()
    tbl_fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(tbl_fig)
    buf.seek(0)
    tbl_svg_str = buf.read().decode("utf-8")
    tbl_w, tbl_h = _svg_dims(tbl_svg_str)
    if tbl_w is None:
        tbl_w, tbl_h = tbl_w_in * 72, tbl_h_in * 72

    bpmn_svg = None if model_path is None else _make_bpmn_svg(activity_type, activity_totals, model_path)

    if bpmn_svg is None:
        # No model — emit table-only SVG
        path = os.path.join(output_dir, fname)
        with open(path, "w", encoding="utf-8") as f:
            f.write(tbl_svg_str)
        return

    bpmn_w, bpmn_h = _svg_dims(bpmn_svg)
    if bpmn_w is None:
        bpmn_w, bpmn_h = 800.0, 600.0

    tbl_scale = bpmn_w / tbl_w
    tbl_h_scl = tbl_h * tbl_scale
    total_h   = bpmn_h + tbl_h_scl

    b64_bpmn = _base64.b64encode(bpmn_svg.encode()).decode()
    b64_tbl  = _base64.b64encode(tbl_svg_str.encode()).decode()

    composite = "\n".join([
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        f'     width="{bpmn_w:.1f}" height="{total_h:.1f}" viewBox="0 0 {bpmn_w:.1f} {total_h:.1f}">',
        '  <rect width="100%" height="100%" fill="white"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_bpmn}"',
        f'         x="0" y="0" width="{bpmn_w:.1f}" height="{bpmn_h:.1f}"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_tbl}"',
        f'         x="0" y="{bpmn_h:.1f}" width="{bpmn_w:.1f}" height="{tbl_h_scl:.1f}"/>',
        '</svg>',
    ])

    with open(os.path.join(output_dir, fname), "w", encoding="utf-8") as f:
        f.write(composite)


# ── Idiom 3: Petri net (graphviz, greyscale) ──────────────────────────────────

def task35_petri_net(activity_type, activity_totals, model_path, output_dir):
    fname = "task35_petri_net.svg"
    if model_path is None:
        _save_empty(output_dir, fname, "No process model provided.")
        return
    if not activity_totals:
        _save_empty(output_dir, fname, "No guideline violations found.")
        return
    try:
        import graphviz as _gv
        import sys as _sys
        # Load Petri net from BPMN
        _scripts = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if _scripts not in _sys.path:
            _sys.path.insert(0, _scripts)
        from io_helpers import load_model
        net, im, fm = load_model(model_path)

        max_v = max(activity_totals.values()) if activity_totals else 1

        dot = _gv.Digraph(format="svg")
        dot.attr(bgcolor="white", rankdir="LR", fontname="Arial")
        dot.attr("node", fontname="Arial")
        dot.attr("edge", color="#888888")

        # ── Places ─────────────────────────────────────────────────────────
        for place in net.places:
            is_init  = place in im
            is_final = place in fm
            if is_init:
                dot.node(str(id(place)), label="●", shape="circle",
                         width="0.35", fixedsize="true",
                         style="filled", fillcolor="#333333", fontcolor="white",
                         color="#333333", fontsize="10")
            elif is_final:
                dot.node(str(id(place)), label="", shape="doublecircle",
                         width="0.3", fixedsize="true",
                         style="filled", fillcolor="white", color="#555555",
                         penwidth="2")
            else:
                dot.node(str(id(place)), label="", shape="circle",
                         width="0.28", fixedsize="true",
                         style="filled", fillcolor="white", color="#888888")

        # ── Transitions ────────────────────────────────────────────────────
        for trans in net.transitions:
            if trans.label is None:  # silent / tau
                dot.node(str(id(trans)), label="τ", shape="rectangle",
                         width="0.25", height="0.55", fixedsize="true",
                         style="filled", fillcolor="#555555", fontcolor="white",
                         color="#333333", fontsize="8")
            else:
                name  = trans.label
                skip  = activity_type.get((name, "Move on Model"), 0)
                ins   = activity_type.get((name, "Move on Log"),   0)
                total = activity_totals.get(name, 0)
                rate  = total / max_v
                fill  = _violation_shade(rate)
                v_int = int(fill[1:3], 16)
                fc    = "white" if v_int < 140 else _C_DARK
                # Wrap long names at underscore
                disp  = name.replace("_", "\\n")
                ann   = f"\\n↑{skip} ↓{ins}" if total > 0 else ""
                dot.node(str(id(trans)), label=disp + ann,
                         shape="rectangle",
                         style="filled", fillcolor=fill, fontcolor=fc,
                         color="#777777", fontsize="9",
                         margin="0.08,0.04")

        # ── Arcs ───────────────────────────────────────────────────────────
        for arc in net.arcs:
            dot.edge(str(id(arc.source)), str(id(arc.target)),
                     arrowsize="0.7")

        # ── Legend group ───────────────────────────────────────────────────
        with dot.subgraph(name="cluster_legend") as leg:
            leg.attr(label="violation rate →", style="rounded",
                     color="#cccccc", bgcolor="#fafafa",
                     fontsize="9", fontcolor=_C_MED)
            prev = None
            for lvl, lbl in [(0.0, "0%"), (0.33, "33%"), (0.66, "66%"), (1.0, "100%")]:
                nid  = f"_leg_{int(lvl*100)}"
                fill = _violation_shade(lvl)
                v    = int(fill[1:3], 16)
                fc   = "white" if v < 140 else _C_DARK
                leg.node(nid, label=lbl, shape="rectangle",
                         style="filled", fillcolor=fill, fontcolor=fc,
                         fontsize="8", width="0.7", height="0.35",
                         fixedsize="true", color="#aaaaaa")
                if prev:
                    leg.edge(prev, nid, style="invis")
                prev = nid

        # ── Render ─────────────────────────────────────────────────────────
        tmp_base = os.path.join(output_dir, "_task35_petri_net_tmp")
        dot.render(tmp_base, cleanup=True)
        rendered = tmp_base + ".svg"
        if os.path.exists(rendered):
            os.rename(rendered, os.path.join(output_dir, fname))
        else:
            _save_empty(output_dir, fname, "Graphviz render produced no output.")

    except Exception as e:
        logger.warning(f"task35_petri_net failed: {e}")
        _save_empty(output_dir, fname, f"Petri net rendering failed: {e}")


# ── Idiom 4: DFG (Directly-Follows Graph) ─────────────────────────────────────

def task35_flow_chart_elaborate_dfg(activity_type, activity_totals, log, output_dir):
    fname = "task35_flow_chart_elaborate_dfg.svg"
    if log is None:
        _save_empty(output_dir, fname, "No event log provided.")
        return
    if not activity_totals:
        _save_empty(output_dir, fname, "No guideline violations found.")
        return
    try:
        import math as _math
        import graphviz as _gv
        import pm4py as _pm4py

        dfg, start_acts, end_acts = _pm4py.discover_dfg(log)
        if not dfg:
            _save_empty(output_dir, fname, "DFG discovery returned no edges.")
            return

        all_acts = set()
        for s, t in dfg:
            all_acts.add(s); all_acts.add(t)

        max_v    = max(activity_totals.values()) if activity_totals else 1
        max_edge = max(dfg.values())

        dot = _gv.Digraph(format="svg")
        dot.attr(bgcolor="white", rankdir="LR", fontname="Arial",
                 pad="0.4", nodesep="0.5", ranksep="0.7")
        dot.attr("node", fontname="Arial", fontsize="9", margin="0.1,0.06")
        dot.attr("edge", fontname="Arial", fontsize="8", fontcolor=_C_MED)

        # ── Nodes ──────────────────────────────────────────────────────────
        for act in sorted(all_acts):
            skip  = activity_type.get((act, "Move on Model"), 0)
            ins   = activity_type.get((act, "Move on Log"),   0)
            total = activity_totals.get(act, 0)
            rate  = total / max_v
            fill  = _violation_shade(rate)
            v_int = int(fill[1:3], 16)
            fc    = "white" if v_int < 140 else _C_DARK

            ann  = f"\\n↑{skip} ↓{ins}" if total > 0 else ""
            disp = act.replace("_", "\\n")

            is_start = act in start_acts
            is_end   = act in end_acts
            pw       = "3" if is_start else ("2.5" if is_end else "1.2")
            shape    = "rectangle"

            dot.node(act, label=disp + ann,
                     shape=shape, style="filled",
                     fillcolor=fill, fontcolor=fc,
                     color="#666666", penwidth=pw)

        # ── Edges ──────────────────────────────────────────────────────────
        for (s, t), count in dfg.items():
            # Log-normalised width: thin=rare, thick=frequent
            w = 0.5 + 3.5 * _math.log(count + 1) / _math.log(max_edge + 1)
            dot.edge(s, t,
                     label=str(count),
                     penwidth=f"{w:.2f}",
                     color="#aaaaaa",
                     arrowsize="0.7")

        # ── Start / end markers ────────────────────────────────────────────
        dot.node("__START__", label="●", shape="circle",
                 width="0.3", fixedsize="true",
                 style="filled", fillcolor="#333333", fontcolor="white",
                 color="#333333", fontsize="11")
        dot.node("__END__", label="", shape="doublecircle",
                 width="0.28", fixedsize="true",
                 style="filled", fillcolor="white", color="#555555",
                 penwidth="2.5")
        for act in start_acts:
            if act in all_acts:
                dot.edge("__START__", act, color="#888888",
                         arrowsize="0.7", penwidth="1.2")
        for act in end_acts:
            if act in all_acts:
                dot.edge(act, "__END__", color="#888888",
                         arrowsize="0.7", penwidth="1.2")

        # ── Legend ─────────────────────────────────────────────────────────
        with dot.subgraph(name="cluster_legend") as leg:
            leg.attr(label="violation rate →", style="rounded",
                     color="#cccccc", bgcolor="#fafafa",
                     fontsize="9", fontcolor=_C_MED)
            prev = None
            for lvl, lbl in [(0.0, "0%"), (0.33, "33%"), (0.66, "66%"), (1.0, "100%")]:
                nid  = f"_dleg_{int(lvl*100)}"
                fill = _violation_shade(lvl)
                v    = int(fill[1:3], 16)
                fc   = "white" if v < 140 else _C_DARK
                leg.node(nid, label=lbl, shape="rectangle",
                         style="filled", fillcolor=fill, fontcolor=fc,
                         fontsize="8", width="0.7", height="0.3",
                         fixedsize="true", color="#aaaaaa")
                if prev:
                    leg.edge(prev, nid, style="invis")
                prev = nid

        # ── Render ─────────────────────────────────────────────────────────
        tmp_base = os.path.join(output_dir, "_task35_dfg_tmp")
        dot.render(tmp_base, cleanup=True)
        rendered = tmp_base + ".svg"
        if os.path.exists(rendered):
            os.rename(rendered, os.path.join(output_dir, fname))
        else:
            _save_empty(output_dir, fname, "Graphviz render produced no output.")

    except Exception as e:
        logger.warning(f"task35_flow_chart_elaborate_dfg failed: {e}")
        _save_empty(output_dir, fname, f"DFG rendering failed: {e}")


# ── Public entry point ─────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None):
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 35 visualizations (Guideline violations in model) ---")

    activity_type, activity_totals, type_totals, n_violations = _extract_data(alignments)

    if not activity_totals:
        logger.warning("Skipped Task 35: no violations found in alignments.")
        for stem in ["flow_chart_elaborate_bpmn", "flow_chart_elaborate_bpmn_table",
                     "petri_net", "flow_chart_elaborate_dfg"]:
            _save_empty(output_dir, f"task35_{stem}.svg", "No guideline violations found.")
        return

    task35_flow_chart_elaborate_bpmn(activity_type, activity_totals, model_path, output_dir)
    task35_flow_chart_elaborate_bpmn_table(activity_type, activity_totals, n_violations,
                                           model_path, output_dir)
    task35_petri_net(activity_type, activity_totals, model_path, output_dir)
    task35_flow_chart_elaborate_dfg(activity_type, activity_totals, log, output_dir)
