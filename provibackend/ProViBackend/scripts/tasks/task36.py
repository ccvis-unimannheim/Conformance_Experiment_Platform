"""
tasks/task36.py – Task 36: Present · Present · Process conformance per rule

Question: Which concrete violations of guidelines are predominant in my process?
  Based on declarative guidelines (Declare model), compute per-rule conformance
  and present as a colored process network.

Visualizations:
  bar_chart       – rules ranked by conformance rate (horizontal bars)
  heatmap         – activity-pair constraint conformance matrix
  network_diagram – Process Network Graph: edge color=conformance, width=support
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = ["bar_chart", "heatmap", "network_diagram"]

import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import warnings
warnings.filterwarnings("ignore")

from shared import save_svg, FONT_TITLE, FONT_LABEL, FONT_ANNOT, make_table, GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER, CIVIDIS
from matplotlib.colors import to_hex

# ── Palette ──────────────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK
_C_MED    = GREY_MED
_C_LIGHT  = GREY_LIGHT
_C_XLIGHT = GREY_LIGHTER
_HDR_BG   = GREY_DARK

_TEMPLATE_PRIORITY = {
    "succession": 0, "chainsuccession": 1,
    "coexistence": 2, "response": 3, "altresponse": 4,
    "responded_existence": 5, "precedence": 6, "altprecedence": 7,
    "absence": 0, "exactly_one": 1, "init": 2, "existence": 3,
}

_TEMPLATE_LABELS = {
    "init":                "Init",
    "existence":           "Existence",
    "exactly_one":         "Exactly One",
    "absence":             "Absence",
    "responded_existence": "Resp. Existence",
    "response":            "Response",
    "altresponse":         "Alt. Response",
    "precedence":          "Precedence",
    "altprecedence":       "Alt. Precedence",
    "coexistence":         "Co-existence",
    "succession":          "Succession",
    "chainsuccession":     "Chain Succession",
}

_ALLOWED_TEMPLATES = {
    "init", "exactly_one", "absence",
    "response", "precedence", "coexistence", "succession",
}


def _short(name: str) -> str:
    return name.replace("A_", "")


def _conf_gray(rate: float) -> str:
    """Low conformance → dark, high → light (greyscale)."""
    v = int(0x2a + (0xe0 - 0x2a) * max(0.0, min(1.0, rate)))
    return f"#{v:02x}{v:02x}{v:02x}"


def _text_color(bg_hex: str) -> str:
    h = bg_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#ffffff" if lum < 140 else "#111111"


# ── Data extraction ───────────────────────────────────────────────────────────

def _extract_data(log) -> dict:
    """Discover Declare model and compute per-constraint conformance rates."""
    import pm4py
    from collections import defaultdict

    n_traces = len(log)

    try:
        dm = pm4py.discover_declare(
            log,
            allowed_templates=_ALLOWED_TEMPLATES,
            min_support_ratio=0.3,
            min_confidence_ratio=0.3,
        )
    except Exception as e:
        logger.warning(f"Task36: discover_declare failed: {e}")
        return {"constraints": [], "binary": [], "n_traces": n_traces, "activities": []}

    if not dm:
        return {"constraints": [], "binary": [], "n_traces": n_traces, "activities": []}

    try:
        results = pm4py.conformance_declare(log, dm)
    except Exception as e:
        logger.warning(f"Task36: conformance_declare failed: {e}")
        results = []

    # Count violations per (template, activities)
    violation_count = defaultdict(int)
    for r in results:
        for dev in r.get("deviations", []):
            violation_count[(dev[0], dev[1])] += 1

    # Build raw constraint list
    raw = []
    all_activities = set()
    for tmpl, pairs in dm.items():
        if tmpl not in _ALLOWED_TEMPLATES:
            continue
        for activities, stats in pairs.items():
            viols = violation_count.get((tmpl, activities), 0)
            conf_rate = 1.0 - viols / n_traces
            is_binary = isinstance(activities, tuple)
            if is_binary:
                all_activities.update(activities)
            else:
                all_activities.add(activities)
            raw.append({
                "template": tmpl,
                "activities": activities,
                "is_binary": is_binary,
                "conf_rate": conf_rate,
                "violations": viols,
                "support": stats.get("support", n_traces),
            })

    # Deduplicate: keep one per (activities key), lowest priority = most specific template
    best = {}
    for c in raw:
        key = c["activities"]
        prio = _TEMPLATE_PRIORITY.get(c["template"], 99)
        if key not in best or prio < _TEMPLATE_PRIORITY.get(best[key]["template"], 99):
            best[key] = c

    constraints = []
    for key, c in best.items():
        tmpl = c["template"]
        acts = c["activities"]
        conf_rate = c["conf_rate"]
        is_binary = c["is_binary"]

        if is_binary:
            a, b = acts
            act_label = f"{_short(a)} → {_short(b)}"
        else:
            act_label = _short(acts) if isinstance(acts, str) else _short(str(acts))

        tmpl_label = _TEMPLATE_LABELS.get(tmpl, tmpl)
        full_label = f"{tmpl_label}: {act_label}"

        constraints.append({
            "template": tmpl,
            "template_label": tmpl_label,
            "activities": acts,
            "act_label": act_label,
            "label": full_label,
            "is_binary": is_binary,
            "conf_rate": conf_rate,
            "violations": c["violations"],
            "support": c.get("support", n_traces),
            "n_traces": n_traces,
            "color": _conf_gray(conf_rate),
        })

    constraints.sort(key=lambda x: x["conf_rate"])

    # Binary only (for heatmap + flow)
    binary = [c for c in constraints if c["is_binary"]]
    # Limit binary to most interesting (exclude perfect 100% if too many)
    if len(binary) > 20:
        non_perfect = [c for c in binary if c["conf_rate"] < 0.999]
        perfect = [c for c in binary if c["conf_rate"] >= 0.999]
        binary = non_perfect[:15] + perfect[:5]

    return {
        "constraints": constraints[:25],
        "binary": binary,
        "n_traces": n_traces,
        "activities": sorted(all_activities),
    }


# ── Idiom 1: Bar Chart ────────────────────────────────────────────────────────

def task36_bar_chart(data: dict, output_dir: str):
    constraints = data["constraints"]
    if not constraints:
        logger.warning("Task36 bar_chart: no constraints.")
        return

    items = constraints[:20]
    n = len(items)
    fig_h = max(6, n * 0.52 + 2.5)
    fig, ax = plt.subplots(figsize=(11, fig_h))

    labels = [c["label"] for c in items]
    rates  = [c["conf_rate"] for c in items]
    colors = [c["color"] for c in items]
    viols  = [c["violations"] for c in items]
    n_tr   = data["n_traces"]

    y_pos = np.arange(n)
    bars = ax.barh(y_pos, rates, color=colors, edgecolor="white",
                   linewidth=0.5, height=0.72)

    for i, (rate, bar, viol) in enumerate(zip(rates, bars, viols)):
        pct_txt = f"{rate:.1%}"
        x_text = min(rate + 0.012, 1.06)
        ax.text(x_text, bar.get_y() + bar.get_height() / 2,
                f"{pct_txt}  ({viol:,} violations)",
                va="center", ha="left", fontsize=7.5, color=_C_DARK)

    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=8)
    ax.set_xlim(0, 1.38)
    ax.set_xlabel("Conformance Rate (fraction of traces satisfying rule)",
                  fontsize=FONT_LABEL)
    ax.set_title(
        "Per-Rule Conformance Rate  ·  Task 36\n"
        f"Declare model constraints, sorted by violation severity  (n = {n_tr:,} traces)",
        fontsize=FONT_TITLE, pad=10, loc="left",
    )

    # Reference lines
    ax.axvline(0.8, color=_C_LIGHT, linestyle="--", linewidth=0.9)
    ax.axvline(0.5, color=_C_LIGHT, linestyle=":",  linewidth=0.9)

    # Conformance bands legend
    legend_items = [
        mpatches.Patch(color=_conf_gray(0.95), label="High  ≥ 80%",      ec="#888"),
        mpatches.Patch(color=_conf_gray(0.65), label="Medium  50–80%",   ec="#888"),
        mpatches.Patch(color=_conf_gray(0.40), label="Low  30–50%",       ec="#888"),
        mpatches.Patch(color=_conf_gray(0.15), label="Very Low  < 30%",   ec="#888"),
    ]
    ax.legend(handles=legend_items,
              loc="lower center", bbox_to_anchor=(0.5, -0.25),
              ncol=4, frameon=True, framealpha=0.9, fontsize=FONT_ANNOT)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout(pad=1.2)

    path = os.path.join(output_dir, "task36_bar_chart.svg")
    save_svg(fig, path)
    logger.info(f"Task36: bar_chart saved → {path}")


# ── Idiom 2: Heatmap ──────────────────────────────────────────────────────────

def task36_heatmap(data: dict, output_dir: str):
    binary = data["binary"]
    activities = data["activities"]

    if not binary or not activities:
        logger.warning("Task36 heatmap: no binary constraints.")
        return

    acts = sorted(activities)
    n = len(acts)
    act_idx = {a: i for i, a in enumerate(acts)}

    # Build matrix: lowest conformance wins for a cell
    matrix = np.full((n, n), np.nan)
    cell_label = {}

    for c in binary:
        a, b = c["activities"]
        if a in act_idx and b in act_idx:
            i, j = act_idx[a], act_idx[b]
            if np.isnan(matrix[i, j]) or c["conf_rate"] < matrix[i, j]:
                matrix[i, j] = c["conf_rate"]
                cell_label[(i, j)] = c["template_label"]

    short_acts = [_short(a) for a in acts]
    cell_size = max(1.0, 8.0 / n)
    fig, ax = plt.subplots(figsize=(max(8, n * cell_size + 3),
                                     max(6, n * cell_size + 2.5)))

    # invert: higher violation → darker cell → higher imshow value in Greys
    masked = np.ma.masked_where(np.isnan(matrix), matrix)
    im = ax.imshow(1 - masked, cmap=CIVIDIS, vmin=0, vmax=1, aspect="auto")

    for i in range(n):
        for j in range(n):
            if not np.isnan(matrix[i, j]):
                rate = matrix[i, j]
                bg = _conf_gray(rate)
                tc = _text_color(bg)
                ax.text(j, i - 0.10, f"{rate:.0%}",
                        ha="center", va="center", fontsize=7.5, color=tc,
                        fontweight="bold")
                lbl = cell_label.get((i, j), "")
                ax.text(j, i + 0.22, lbl,
                        ha="center", va="center", fontsize=5.5, color=tc)

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(short_acts, fontsize=FONT_ANNOT, rotation=40, ha="right")
    ax.set_yticklabels(short_acts, fontsize=FONT_ANNOT)
    ax.set_xlabel("Target Activity", fontsize=FONT_LABEL)
    ax.set_ylabel("Source Activity", fontsize=FONT_LABEL)
    ax.set_title(
        "Constraint Conformance by Activity Pair  ·  Task 36\n"
        "Cells show worst-case conformance rate  (darker = more violations)",
        fontsize=FONT_TITLE, pad=10, loc="left",
    )

    cbar = fig.colorbar(im, ax=ax, fraction=0.04, pad=0.04, shrink=0.7)
    cbar.set_label("Violation Rate →", fontsize=FONT_ANNOT)
    cbar.set_ticks([0, 0.25, 0.5, 0.75, 1.0])
    cbar.set_ticklabels(["0%", "25%", "50%", "75%", "100%"], fontsize=7)

    fig.tight_layout(pad=1.2)
    path = os.path.join(output_dir, "task36_heatmap.svg")
    save_svg(fig, path)
    logger.info(f"Task36: heatmap saved → {path}")



# ── Idiom 4: Process Network Graph ───────────────────────────────────────────

def task36_network_diagram(data: dict, output_dir: str):
    """
    Process Network Graph: activities as nodes, binary constraints as edges.
    Edge color : white (#e0e0e0 at 0%) → black (#111111 at 100%) conformance.
    Edge width : thin (low support) → thick (high support / trigger freq).
    """
    import networkx as nx

    binary   = data["binary"]
    n_traces = data["n_traces"]

    if not binary:
        logger.warning("Task36 network_diagram: no binary constraints.")
        return

    # ── Build directed graph (one edge per pair – worst conformance) ──────────
    G = nx.DiGraph()
    edge_best = {}
    for c in binary:
        a, b = c["activities"]
        G.add_node(a)
        G.add_node(b)
        key = (a, b)
        if key not in edge_best or c["conf_rate"] < edge_best[key]["conf_rate"]:
            edge_best[key] = c

    for (a, b), c in edge_best.items():
        G.add_edge(a, b,
                   conf_rate=c["conf_rate"],
                   support=c.get("support", n_traces),
                   template=c["template_label"])

    # Worst conformance per node (for optional future use)
    for node in G.nodes():
        worst = min((c["conf_rate"] for c in binary if node in c["activities"]),
                    default=1.0)
        G.nodes[node]["worst_conf"] = worst

    # ── Layout: spring, normalized to [-0.82, 0.82] ───────────────────────────
    pos_raw = nx.spring_layout(G, k=3.2, seed=7, iterations=120)
    xs = np.array([p[0] for p in pos_raw.values()])
    ys = np.array([p[1] for p in pos_raw.values()])
    xr = max(xs.max() - xs.min(), 1e-9)
    yr = max(ys.max() - ys.min(), 1e-9)
    PAD = 0.82
    pos = {n: (PAD * (2*(p[0]-xs.min())/xr - 1),
               PAD * (2*(p[1]-ys.min())/yr - 1))
           for n, p in pos_raw.items()}

    # ── Edge visual mappings ──────────────────────────────────────────────────
    supports = [d["support"] for _, _, d in G.edges(data=True)]
    min_sup  = min(supports)
    max_sup  = max(supports)
    sup_rng  = max(max_sup - min_sup, 1)

    def _edge_color(conf: float) -> str:
        return to_hex(CIVIDIS(max(0.0, min(1.0, conf))))

    def _edge_width(sup: int) -> float:
        return 0.9 + 4.1 * (sup - min_sup) / sup_rng

    # ── Figure: single subplot, task08 style ─────────────────────────────────
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(figsize=(14, 9))
    ax.set_facecolor("#fafbfc")
    ax.axis("off")

    # ── Draw edges ────────────────────────────────────────────────────────────
    edges_list = list(G.edges())
    edge_colors = [_edge_color(G[u][v]["conf_rate"]) for u, v in edges_list]
    edge_widths = [_edge_width(G[u][v]["support"])   for u, v in edges_list]

    nx.draw_networkx_edges(
        G, pos, ax=ax,
        edgelist=edges_list,
        edge_color=edge_colors,
        width=edge_widths,
        alpha=0.90,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=14,
        connectionstyle="arc3,rad=0.14",
        min_source_margin=22,
        min_target_margin=22,
    )

    # ── Edge labels: template + % at arc midpoint (task08 perpendicular style)─
    rad = 0.14
    for u, v, edata in G.edges(data=True):
        conf   = edata["conf_rate"]
        tmpl   = edata["template"]
        xu, yu = pos[u]
        xv, yv = pos[v]
        dx, dy = xv - xu, yv - yu
        length = max(np.hypot(dx, dy), 1e-9)
        px, py = -dy / length, dx / length          # perpendicular left-turn
        xm = (xu + xv) / 2 + rad * (length / 2) * px
        ym = (yu + yv) / 2 + rad * (length / 2) * py
        ax.text(xm, ym, f"{tmpl}\n{conf:.0%}",
                ha="center", va="center", fontsize=FONT_ANNOT - 2,
                color=_C_DARK,
                bbox=dict(boxstyle="round,pad=0.2", fc="white",
                          ec=_C_XLIGHT, alpha=0.95, linewidth=0.4),
                zorder=3)

    # ── Draw nodes (invisible fill, dark border) ──────────────────────────────
    nx.draw_networkx_nodes(
        G, pos, ax=ax,
        node_color="#ffffff",
        node_size=800,
        edgecolors="#333333",
        linewidths=1.2,
        alpha=1.0,
    )

    # ── Node labels: below each node, white bbox (task08 annotate style) ──────
    for node, (x, y) in pos.items():
        label = _short(node)
        if len(label) > 9:
            mid   = len(label) // 2
            label = label[:mid] + "\n" + label[mid:]
        ax.annotate(
            label, xy=(x, y),
            xytext=(0, -24), textcoords="offset points",
            ha="center", va="top",
            fontsize=max(FONT_ANNOT - 1, 6), color=_C_DARK, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.25", fc="white",
                      ec=_C_XLIGHT, alpha=0.92, linewidth=0.4),
        )

    # ── Legend: edge color (conformance) + edge width (support) ──────────────
    legend_color = [
        Line2D([0], [0], color=_edge_color(r), lw=2.5,
               label=f"{r:.0%}  conformance")
        for r in [0.38, 0.60, 0.78, 1.00]
    ]
    legend_width = [
        Line2D([0], [0], color=_C_MED, lw=_edge_width(s),
               label=f"{s:,}  traces")
        for s in [min_sup, int(min_sup + sup_rng * 0.5), max_sup]
    ]

    leg1 = ax.legend(handles=legend_color, loc="lower left",
                     title="Edge color → Conformance", title_fontsize=FONT_ANNOT - 1,
                     fontsize=FONT_ANNOT - 1, frameon=True, framealpha=0.95,
                     edgecolor=_C_XLIGHT)
    ax.add_artist(leg1)
    ax.legend(handles=legend_width, loc="lower right",
              title="Edge width → Support", title_fontsize=FONT_ANNOT - 1,
              fontsize=FONT_ANNOT - 1, frameon=True, framealpha=0.95,
              edgecolor=_C_XLIGHT)

    fig.tight_layout(pad=1.2)

    path = os.path.join(output_dir, "task36_network_diagram.svg")
    save_svg(fig, path)
    logger.info(f"Task36: network_diagram saved → {path}")


# ── Entry point ──────────────────────────────────────────────────────────────

def generate(log, alignments, output_dir: str, model_path: str = None):
    logger.info("\n--- Generating Task 36 visualizations (Declare constraint conformance) ---")
    logger.info("      Extracting Declare conformance data…")
    data = _extract_data(log)

    if not data["constraints"]:
        logger.warning("Task36: no constraints discovered — skipping all idioms.")
        return

    n = data["n_traces"]
    logger.info(f"Task36: {len(data['constraints'])} constraints, {n} traces")

    fns = {
        "bar_chart":       lambda d: task36_bar_chart(d, output_dir),
        "heatmap":         lambda d: task36_heatmap(d, output_dir),
        "network_diagram": lambda d: task36_network_diagram(d, output_dir),
    }

    for idiom in IDIOMS:
        try:
            fns[idiom](data)
        except Exception as e:
            logger.warning(f"Task36: {idiom} failed: {e}", exc_info=True)
