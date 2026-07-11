"""
tasks/task11.py – Task 11: Predefined Guideline Violation(s)
Goal: Describe · Means: Summarize · Characteristics: Guideline violations

Question: How often did predefined guideline violation(s) occur?

Visualizations (all SVG, white-grey-black palette):
  bar_chart                     – trace count per predefined violation
  heatmap                       – activity × type grid for selected violations
  table                         – violations ranked by trace frequency
  table_bar_chart               – table + gradient bar chart
  flow_chart_elaborate_bpmn_table – BPMN heatmap + violation frequency table
"""

import logging
logger = logging.getLogger(__name__)

IDIOMS = [
    "bar_chart", "heatmap",
    "table", "table_bar_chart",
    "flow_chart_elaborate_bpmn_table",
]

# ---------------------------------------------------------------------------
# Per-task contract (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4, §6, §8;
# design doc §2 row 11)
#
# Task 11 (SEMI): trace-level frequency of a set of predefined violations.
# The admin picks one or more (activity, move_type) pairs from the log;
# every idiom shows how many traces each one appears in (% of all traces).
# ---------------------------------------------------------------------------
GT_TIER = "SEMI"

PARAM_SPEC = [
    {
        "key": "target_violations",
        "label": "Predefined violation(s) to summarize",
        "hint": "The chart summarises these guideline violations.",
        "widget": "select-many",
        "source": "log.violations",
        "required": True,
    },
]

ANSWER_FORMATS = [
    {"key": "pct-set",   "gt_shape": "labelled-set", "decisive_default": True},
    {"key": "free-text", "gt_shape": "reference",     "decisive_default": False},
]

RUBRIC = (
    "A strong answer states the trace-level frequency of each predefined violation — "
    "i.e. the percentage of all traces in which that violation appears at least once — "
    "for every violation in the specified set. "
    "Full credit requires a correct percentage for each violation, rounded to the nearest "
    "whole number. Partial credit for values within ±5 percentage points of the true value, "
    "or for correctly ranking violations by trace frequency. No credit for raw occurrence "
    "counts rather than trace-level percentages, or for percentages relative to a subset "
    "of traces rather than the full log."
)


def validate_params(log, params) -> list:
    violations = params.get("target_violations")
    if not violations or (isinstance(violations, list) and len(violations) == 0):
        return ["At least one guideline violation must be selected."]
    return []


def compute_ground_truth(log, alignments, fitness_df, model_path, params, answer_format) -> dict:
    """Trace-level frequency per selected violation, shaped for the chosen answer format.

    pct-set: one labelled row per violation, value = % of all traces (rounded), correct=True.
    free-text: falls through to the static RUBRIC; no value is computed.
    """
    if answer_format == "free-text":
        return {}
    trace_coverage, n_traces = _extract_trace_coverage(alignments)
    violations = params.get("target_violations") or []
    selected = _resolve_violations(violations, trace_coverage)
    if not selected:
        return {"value": None, "options": []}
    options = []
    for act, vt in selected:
        count = trace_coverage.get((act, vt), 0)
        pct = count / n_traces * 100 if n_traces > 0 else 0
        options.append({
            "label": f"{act} · {vt}",
            "value": f"{round(pct)}%",
            "correct": True,
        })
    return {"value": None, "options": options}


import os
import io as _io
import base64 as _base64
import re as _re
import xml.etree.ElementTree as _ET
from collections import Counter

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from shared import save_svg, make_table, GREY_DARK, GREY_MED, GREY_LIGHT, GREY_LIGHTER, CIVIDIS_R, FONT_TITLE, FONT_LABEL, FONT_ANNOT, classify_step as _classify_step

# ── Cividis palette ───────────────────────────────────────────────────────────
_C_DARK   = GREY_DARK
_C_MED    = GREY_MED
_C_LIGHT  = GREY_LIGHT
_C_XLIGHT = GREY_LIGHTER
_HDR_BG   = GREY_DARK
_CMAP_SEQ = CIVIDIS_R  # dark = many violations, yellow = 0

_VTYPES = ["Move on Model", "Move on Log", "Mismatch Move"]
_VTYPE_SHORT = {
    "Move on Model": "MoM",
    "Move on Log":   "MoL",
    "Mismatch Move": "MM",
}

# Accepts full names or short codes when parsing a violation spec.
_VTYPE_FROM_TOKEN = {
    "mom": "Move on Model", "move on model": "Move on Model",
    "mol": "Move on Log",   "move on log":   "Move on Log",
    "mm":  "Mismatch Move", "mismatch move": "Mismatch Move",
}


# ── Data extraction ───────────────────────────────────────────────────────────

def _extract_trace_coverage(alignments):
    """Returns (trace_coverage Counter, n_traces int).

    trace_coverage maps (activity, vtype) → number of distinct traces in which
    that violation appears at least once.
    """
    trace_coverage = Counter()
    n_traces = len(alignments)
    for aln in alignments:
        seen = set()
        for step in aln.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            act, vtype = _classify_step(step[0], step[1])
            if act is None:
                continue
            seen.add((act, vtype))
        for pair in seen:
            trace_coverage[pair] += 1
    return trace_coverage, n_traces


def _resolve_target(spec, trace_coverage):
    """Parse one 'activity|move_type' string to an (act, vt) key present in trace_coverage."""
    if spec is None:
        return None
    if isinstance(spec, (tuple, list)) and len(spec) == 2:
        act, vt = str(spec[0]).strip(), str(spec[1]).strip()
    else:
        s = str(spec).strip()
        if "|" in s:
            act, vt = s.rsplit("|", 1)
        elif "::" in s:
            act, vt = s.rsplit("::", 1)
        else:
            return None
        act, vt = act.strip(), vt.strip()
    vt = _VTYPE_FROM_TOKEN.get(vt.lower(), vt)
    key = (act, vt)
    return key if key in trace_coverage else None


def _resolve_violations(target_violations, trace_coverage):
    """Resolve a list of 'activity|move_type' specs to (act, vt) tuples present in data.

    Preserves order; silently drops specs that cannot be matched.
    """
    if not target_violations:
        return []
    if isinstance(target_violations, str):
        target_violations = [target_violations]
    seen = set()
    resolved = []
    for spec in target_violations:
        key = _resolve_target(spec, trace_coverage)
        if key is not None and key not in seen:
            seen.add(key)
            resolved.append(key)
    return resolved


# ── Label / layout helpers ────────────────────────────────────────────────────

def _short_label(label, max_len=26):
    return label if len(label) <= max_len else label[:max_len - 1] + "…"


def _violation_label(act, vt, max_act_len=26):
    return f"{_short_label(act, max_act_len)} · {_VTYPE_SHORT.get(vt, vt)}"


def _save_empty(output_dir, filename, message="No data available"):
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.axis("off")
    ax.text(0.5, 0.5, message, ha="center", va="center",
            fontsize=11, color="#888888", transform=ax.transAxes)
    save_svg(fig, os.path.join(output_dir, filename))


def _no_violations(output_dir, name):
    _save_empty(output_dir, f"task11_{name}.svg",
                "No guideline violations found in this log.")


def _sorted_selected(selected, trace_coverage):
    """Return selected pairs sorted by trace count descending."""
    return sorted(selected, key=lambda p: -trace_coverage.get(p, 0))


# ── Idiom 1: Bar Chart — trace count per predefined violation ─────────────────

def task11_bar_chart(selected, trace_coverage, n_traces, output_dir):
    """Horizontal bar per selected violation, sorted by trace count descending.

    Each bar shows the number of traces in which that violation occurs,
    labelled with the count and its percentage of all traces.
    """
    if not selected:
        _no_violations(output_dir, "bar_chart")
        return

    data = [(act, vt, trace_coverage.get((act, vt), 0))
            for act, vt in _sorted_selected(selected, trace_coverage)]
    labels = [_violation_label(act, vt) for act, vt, _ in data]
    counts = [c for _, _, c in data]
    pcts   = [c / n_traces * 100 if n_traces > 0 else 0 for c in counts]
    max_c  = max(counts) if counts else 1
    shades = [str(round(1 - (c / max_c) * 0.72, 3)) for c in counts]

    n      = len(data)
    fig_h  = max(3.5, n * 0.70 + 2.2)
    fig, ax = plt.subplots(figsize=(12, fig_h))
    ax.set_facecolor("#fafbfc")

    for i, (lbl, cnt, pct, shade) in enumerate(zip(labels, counts, pcts, shades)):
        ax.barh(i, cnt, color=shade, edgecolor=_C_DARK, linewidth=0.8, height=0.65)
        ax.text(cnt + max_c * 0.012, i,
                f"{cnt:,} traces  ({pct:.1f}%)",
                va="center", fontsize=FONT_ANNOT, color=_C_DARK)

    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=FONT_ANNOT)
    ax.invert_yaxis()
    ax.set_xlabel("Number of traces containing this violation", fontsize=FONT_LABEL)
    ax.set_title(
        f"Predefined Violation Frequency  ({n} violation{'s' if n != 1 else ''})\n"
        f"Bars = traces in which the violation appears at least once  ·  "
        f"{n_traces:,} total traces",
        fontsize=FONT_TITLE,
    )
    ax.spines[["top", "right"]].set_visible(False)
    ax.xaxis.grid(True, linestyle="--", alpha=0.45)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max_c * 1.42)
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task11_bar_chart.svg"))


# ── Idiom 2: Heatmap — activity × type for selected violations ────────────────

def task11_heatmap(selected, trace_coverage, n_traces, output_dir):
    """Activity × violation-type grid restricted to the selected violations.

    Rows = distinct activities in the selection (ordered by descending total
    trace coverage across their selected move types).  Columns = the subset of
    the three move types that appears at least once among the selected pairs,
    in canonical order.  Cell = # traces containing that (activity, type) pair;
    annotated with count and %; unselected cells are left at 0 and shown pale.
    """
    if not selected:
        _no_violations(output_dir, "heatmap")
        return

    selected_set = set(selected)

    # Determine axes — only the vtypes that appear in the selection, canonical order
    selected_vtypes = [vt for vt in _VTYPES if any(vt == v for _, v in selected)]

    # Activities ordered by descending sum of trace coverage across their selected vtypes
    act_score = {}
    for act, vt in selected:
        act_score[act] = act_score.get(act, 0) + trace_coverage.get((act, vt), 0)
    selected_acts = sorted(act_score, key=lambda a: -act_score[a])

    n_rows = len(selected_acts)
    n_cols = len(selected_vtypes)

    mat = np.zeros((n_rows, n_cols))
    for i, act in enumerate(selected_acts):
        for j, vt in enumerate(selected_vtypes):
            if (act, vt) in selected_set:
                mat[i, j] = trace_coverage.get((act, vt), 0)

    fig_h  = max(3.5, n_rows * 0.70 + 2.5)
    fig, ax = plt.subplots(figsize=(10, fig_h))
    ax.set_facecolor("#fafbfc")

    vmax = mat.max() if mat.max() > 0 else 1
    im   = ax.imshow(mat, cmap=_CMAP_SEQ, aspect="auto",
                     norm=mcolors.PowerNorm(gamma=0.5, vmin=0, vmax=vmax))

    ax.set_xticks(range(n_cols))
    ax.set_xticklabels(selected_vtypes, fontsize=FONT_LABEL)
    ax.set_yticks(range(n_rows))
    ax.set_yticklabels([_short_label(a, 30) for a in selected_acts], fontsize=FONT_ANNOT)

    # Annotate each selected cell with count + %
    for i in range(n_rows):
        for j in range(n_cols):
            val = int(mat[i, j])
            if val > 0:
                pct = val / n_traces * 100 if n_traces > 0 else 0
                brightness = mat[i, j] / vmax
                tc = "white" if brightness > 0.55 else _C_DARK
                ax.text(j, i, f"{val:,}\n({pct:.1f}%)",
                        ha="center", va="center",
                        fontsize=max(FONT_ANNOT - 1, 6), color=tc)

    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.01)
    cbar.set_label("Traces containing violation", fontsize=FONT_ANNOT)
    cbar.outline.set_visible(False)

    ax.set_title(
        "Predefined Violation Frequency: Activity × Type\n"
        f"Cell = # traces containing that violation  ·  {n_traces:,} total traces",
        fontsize=FONT_TITLE,
    )
    ax.tick_params(axis="both", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)

    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task11_heatmap.svg"))


# ── Idiom 3: Table — violations ranked by trace frequency ─────────────────────

def task11_table(selected, trace_coverage, n_traces, output_dir):
    """Ranked table: Rank | Violation | # Traces | % of All Traces.

    Rows correspond 1-to-1 to the selected violations, sorted descending by
    trace count.  Percentages are independent (no cumulative column — traces
    containing multiple violations overlap).
    """
    if not selected:
        _no_violations(output_dir, "table")
        return

    data = [(act, vt, trace_coverage.get((act, vt), 0))
            for act, vt in _sorted_selected(selected, trace_coverage)]

    cell_text = []
    for rank, (act, vt, count) in enumerate(data, 1):
        pct = count / n_traces * 100 if n_traces > 0 else 0
        cell_text.append([str(rank), _short_label(act, 32),
                          _VTYPE_SHORT.get(vt, vt),
                          f"{count:,}",
                          f"{pct:.1f}%"])

    n_rows = len(cell_text)
    fig_h  = max(3.5, 1.3 + n_rows * 0.46)
    fig, ax = plt.subplots(figsize=(13, fig_h))
    ax.axis("off")

    make_table(
        ax,
        cell_text=cell_text,
        col_labels=["#", "Activity", "Type", "# Traces", "% of All"],
        bbox=[0.01, 0.05, 0.98, 0.80],
        col_widths=[0.05, 0.42, 0.16, 0.20, 0.14],
        font_size=9.5,
        scale_xy=(1, 1.75),
        cell_pad=0.09,
    )
    ax.set_title(
        f"Predefined Violation Frequency  ({n_rows} violation{'s' if n_rows != 1 else ''})\n"
        f"% = traces containing that violation ÷ {n_traces:,} total traces",
        fontsize=FONT_TITLE, pad=14,
    )
    fig.tight_layout(pad=1.2)
    save_svg(fig, os.path.join(output_dir, "task11_table.svg"))


# ── Idiom 4: Table & Bar Chart ────────────────────────────────────────────────

def task11_table_bar_chart(selected, trace_coverage, n_traces, output_dir):
    """Left: compact violation table. Right: gradient horizontal bars by trace count."""
    if not selected:
        _no_violations(output_dir, "table_bar_chart")
        return

    data = [(act, vt, trace_coverage.get((act, vt), 0))
            for act, vt in _sorted_selected(selected, trace_coverage)]
    n     = len(data)
    max_c = max(c for _, _, c in data) if data else 1

    rows = []
    for act, vt, count in data:
        pct = count / n_traces * 100 if n_traces > 0 else 0
        rows.append([_violation_label(act, vt, 22),
                     f"{count:,}",
                     f"{pct:.1f}%"])

    fig, (ax_tbl, ax_bar) = plt.subplots(
        1, 2, figsize=(16, max(4.0, n * 0.65 + 2.5)),
        gridspec_kw={"width_ratios": [3, 4]},
    )

    # ── Left: table ───────────────────────────────────────────────────────────
    ax_tbl.axis("off")
    make_table(
        ax_tbl,
        cell_text=rows,
        col_labels=["Violation", "# Traces", "% of All"],
        bbox=[0.01, 0.05, 0.98, 0.80],
        col_widths=[0.64, 0.20, 0.16],
        font_size=9,
        scale_xy=(1, 1.7),
        cell_pad=0.09,
    )

    # ── Right: gradient bars ──────────────────────────────────────────────────
    ax_bar.set_facecolor("#fafbfc")
    for i, (act, vt, cnt) in enumerate(data):
        shade = str(round(1 - (cnt / max_c) * 0.72, 3))
        ax_bar.barh(i, cnt, color=shade,
                    edgecolor=_C_DARK, linewidth=0.8, height=0.65)
        pct = cnt / n_traces * 100 if n_traces > 0 else 0
        ax_bar.text(cnt + max_c * 0.012, i,
                    f"{cnt:,}  ({pct:.1f}%)",
                    va="center", fontsize=FONT_ANNOT, color=_C_DARK)

    bar_labels = [_violation_label(act, vt, 24) for act, vt, _ in data]
    ax_bar.set_yticks(range(n))
    ax_bar.set_yticklabels(bar_labels, fontsize=FONT_ANNOT)
    ax_bar.invert_yaxis()
    ax_bar.set_xlabel("Traces containing violation", fontsize=FONT_LABEL)
    ax_bar.set_title("Frequency  (darker = more traces)", fontsize=FONT_TITLE)
    ax_bar.spines[["top", "right"]].set_visible(False)
    ax_bar.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax_bar.set_axisbelow(True)
    ax_bar.set_xlim(0, max_c * 1.38)

    fig.suptitle(
        f"Predefined Violation Frequency  ({n} violation{'s' if n != 1 else ''})"
        f"  ·  {n_traces:,} total traces",
        fontsize=FONT_TITLE + 1, y=1.01,
    )
    fig.tight_layout()
    save_svg(fig, os.path.join(output_dir, "task11_table_bar_chart.svg"))


# ── BPMN helpers ──────────────────────────────────────────────────────────────

def _import_task09_bpmn():
    try:
        from tasks.task09 import _make_bpmn_violation_svg
    except ImportError:
        from task09 import _make_bpmn_violation_svg
    return _make_bpmn_violation_svg


def _svg_dims(svg_str):
    m = _re.search(r'<svg[^>]*\bwidth="([^"]+)"[^>]*\bheight="([^"]+)"', svg_str)
    if m:
        w = float(_re.sub(r"[^\d.]", "", m.group(1)))
        h = float(_re.sub(r"[^\d.]", "", m.group(2)))
        return w, h
    return None, None


# ── Idiom 5: Flow Chart Elaborate BPMN & Table ────────────────────────────────

def task11_flow_chart_elaborate_bpmn_table(selected, trace_coverage, n_traces,
                                           activity_trace_count, model_path, output_dir):
    """Composite SVG: BPMN heatmap (top, coloured by per-activity trace coverage)
    + violation frequency table (bottom, one row per selected violation).

    activity_trace_count maps activity → # traces containing any selected violation
    there (computed with proper set-union in generate(), so no double-counting).
    """
    if not selected:
        _no_violations(output_dir, "flow_chart_elaborate_bpmn_table")
        return

    # ── Violation table SVG ───────────────────────────────────────────────────
    data = [(act, vt, trace_coverage.get((act, vt), 0))
            for act, vt in _sorted_selected(selected, trace_coverage)]
    n_rows   = len(data)
    tbl_w_in = 14.0
    tbl_h_in = max(3.0, 1.3 + n_rows * 0.46)
    tbl_fig, tbl_ax = plt.subplots(figsize=(tbl_w_in, tbl_h_in))
    tbl_ax.axis("off")

    tbl_cell_text = []
    for i, (act, vt, count) in enumerate(data):
        pct = count / n_traces * 100 if n_traces > 0 else 0
        tbl_cell_text.append([str(i + 1), _short_label(act, 32),
                               _VTYPE_SHORT.get(vt, vt), f"{count:,}", f"{pct:.1f}%"])

    make_table(
        tbl_ax,
        cell_text=tbl_cell_text,
        col_labels=["#", "Activity", "Type", "# Traces", "% of All"],
        bbox=[0.01, 0.05, 0.98, 0.80],
        col_widths=[0.05, 0.42, 0.16, 0.20, 0.14],
        font_size=9.5,
        scale_xy=(1, 1.75),
        cell_pad=0.09,
    )
    tbl_ax.set_title(
        f"Predefined Violation Frequency  ({n_rows} violation{'s' if n_rows != 1 else ''})  "
        f"·  {n_traces:,} total traces  ·  % = traces containing violation",
        fontsize=FONT_TITLE, pad=14,
    )
    tbl_fig.tight_layout(pad=1.2)

    buf = _io.BytesIO()
    tbl_fig.savefig(buf, format="svg", bbox_inches="tight")
    plt.close(tbl_fig)
    buf.seek(0)
    tbl_svg_str = buf.read().decode("utf-8")
    tbl_w, tbl_h = _svg_dims(tbl_svg_str)
    if tbl_w is None:
        tbl_w, tbl_h = tbl_w_in * 72, tbl_h_in * 72

    # ── BPMN SVG — coloured by per-activity trace coverage ───────────────────
    bpmn_svg = None
    if model_path is not None and activity_trace_count:
        try:
            _make_bpmn_violation_svg = _import_task09_bpmn()
            bpmn_svg = _make_bpmn_violation_svg(activity_trace_count, model_path)
        except Exception:
            logger.exception("task11: failed to render BPMN for flow_chart_elaborate_bpmn_table")

    path = os.path.join(output_dir, "task11_flow_chart_elaborate_bpmn_table.svg")
    if bpmn_svg is None:
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
        f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink"',
        f'     width="{bpmn_w:.1f}" height="{total_h:.1f}" viewBox="0 0 {bpmn_w:.1f} {total_h:.1f}">',
        '  <rect width="100%" height="100%" fill="white"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_bpmn}"',
        f'         x="0" y="0" width="{bpmn_w:.1f}" height="{bpmn_h:.1f}"/>',
        f'  <image href="data:image/svg+xml;base64,{b64_tbl}"',
        f'         x="0" y="{bpmn_h:.1f}" width="{bpmn_w:.1f}" height="{tbl_h_scl:.1f}"/>',
        '</svg>',
    ])
    with open(path, "w", encoding="utf-8") as f:
        f.write(composite)


# ── Public entry point ────────────────────────────────────────────────────────

def generate(log, alignments, output_dir, model_path=None, target_violations=None):
    """Generate all Task 11 SVGs into output_dir.

    target_violations: list of 'activity|move_type' strings (the predefined set
    chosen by the admin on /specify). Each identifies one (activity, move_type)
    pair to summarise. Move type may be a full name or a short code (MoM/MoL/MM).

    When omitted or empty, all distinct violations in the log are shown (fallback
    for legacy / CLI use). Unresolvable specs (activity not in log, etc.) are
    silently dropped and logged.
    """
    os.makedirs(output_dir, exist_ok=True)
    logger.info("\n--- Generating Task 11 visualizations (Predefined guideline violations) ---")

    trace_coverage, n_traces = _extract_trace_coverage(alignments)

    if not trace_coverage:
        logger.warning("      Skipped Task 11: no violations found in alignments.")
        for name in IDIOMS:
            _save_empty(output_dir, f"task11_{name}.svg",
                        "No guideline violations found in this log.")
        return

    # Resolve the predefined set.
    if target_violations:
        selected = _resolve_violations(target_violations, trace_coverage)
        if not selected:
            logger.error(
                "task11: none of the specified violations were found in the log. "
                "Specified: %s. Available: %s",
                target_violations,
                [f"{a}|{v}" for (a, v) in trace_coverage.most_common(20)],
            )
            for name in IDIOMS:
                _save_empty(output_dir, f"task11_{name}.svg",
                            "None of the specified violations were found in this log.")
            return
        dropped = [s for s in (target_violations if isinstance(target_violations, list)
                               else [target_violations])
                   if _resolve_target(s, trace_coverage) is None]
        if dropped:
            logger.warning("task11: unresolved violation specs (ignored): %s", dropped)
    else:
        # Fallback: show all violations sorted by trace count
        selected = [pair for pair, _ in trace_coverage.most_common()]
        logger.info("task11: no violations specified — showing all %d distinct violations.",
                    len(selected))

    logger.info("task11: %d violation(s) selected, %d total traces.", len(selected), n_traces)

    # Compute per-activity trace coverage (set-union across selected vtypes) for the BPMN.
    selected_set = set(selected)
    activity_trace_count: Counter = Counter()
    for aln in alignments:
        seen_acts: set = set()
        for step in aln.get("alignment", []):
            if not isinstance(step, (list, tuple)) or len(step) < 2:
                continue
            act, vtype = _classify_step(step[0], step[1])
            if act is None:
                continue
            if (act, vtype) in selected_set and act not in seen_acts:
                seen_acts.add(act)
                activity_trace_count[act] += 1

    task11_bar_chart(selected, trace_coverage, n_traces, output_dir)
    task11_heatmap(selected, trace_coverage, n_traces, output_dir)
    task11_table(selected, trace_coverage, n_traces, output_dir)
    task11_table_bar_chart(selected, trace_coverage, n_traces, output_dir)
    task11_flow_chart_elaborate_bpmn_table(
        selected, trace_coverage, n_traces, activity_trace_count, model_path, output_dir
    )
