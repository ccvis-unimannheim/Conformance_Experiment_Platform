"use client";

import React, { useMemo, useRef } from "react";

/**
 * Answer widgets for the Task Execution panel.
 *
 * One widget per `answer_type` returned by the backend
 * (participant.py ANSWER_FORMAT_TO_ANSWER_TYPE). The panel picks a widget with
 * <AnswerInput answerType=… />; helpers below define the per-type value shape,
 * the "is it answered" check, and how the value is serialized into the single
 * `answer: str` field the backend stores.
 *
 *   answer_type        value shape          serialized form
 *   ----------------   ------------------   --------------------------
 *   single_choice      string (token)       token
 *   multiple_choice    string[] (tokens)    JSON array
 *   numeric            string               string
 *   numeric_set        { [label]: string }  JSON object
 *   rank               string[] (ordered)   JSON array (top → bottom)
 *   matrix             string[] (pair toks) JSON array (sorted)
 *   free_text          string               string
 */

// ---------------------------------------------------------------- shared style
const COLORS = {
  navy: "#00305e",
  accent: "#3c5f90",
  accentSoft: "#eef2f8",
  ink: "#2d3435",
  muted: "#5a6061",
  line: "#dde4e5",
  fieldBg: "#fafbfc",
  chipBg: "#f2f4f4",
};

const choiceRowStyle = (selected) => ({
  display: "flex",
  alignItems: "center",
  gap: "0.875rem",
  width: "100%",
  padding: "0.9rem 1.1rem",
  backgroundColor: selected ? COLORS.accentSoft : COLORS.chipBg,
  border: `2px solid ${selected ? COLORS.accent : "transparent"}`,
  borderRadius: "0.5rem",
  cursor: "pointer",
  textAlign: "left",
  transition: "all 0.15s ease",
});

const choiceLabelStyle = (selected) => ({
  fontSize: "0.875rem",
  fontWeight: selected ? 600 : 500,
  color: selected ? COLORS.navy : COLORS.ink,
  lineHeight: 1.4,
});

const fieldStyle = {
  width: "100%",
  padding: "0.9rem 1rem",
  border: `2px solid ${COLORS.line}`,
  borderRadius: "0.5rem",
  fontSize: "0.95rem",
  color: COLORS.ink,
  backgroundColor: COLORS.fieldBg,
  outline: "none",
  fontFamily: "inherit",
  boxSizing: "border-box",
  transition: "border-color 0.15s ease",
};

const hintStyle = { fontSize: "0.72rem", color: COLORS.muted, margin: "0.45rem 0 0" };

const focusOn = (e) => { e.target.style.borderColor = COLORS.accent; };
const focusOff = (e) => { e.target.style.borderColor = COLORS.line; };

// ----------------------------------------------------------- numeric metadata
function numericMeta(answerFormat) {
  switch (answerFormat) {
    case "pct":
    case "pct-set":
      return { suffix: "%", step: "0.1", min: 0, max: 100, hint: "Enter a percentage (0–100)." };
    case "count":
    case "count-set":
      return { suffix: "", step: "1", min: 0, max: undefined, hint: "Enter a whole number (≥ 0)." };
    case "decimal":
      return { suffix: "", step: "any", min: undefined, max: undefined, hint: "Enter a decimal value." };
    default:
      return { suffix: "", step: "any", min: undefined, max: undefined, hint: "" };
  }
}

const optValue = (o) => (typeof o === "string" ? o : o.value ?? o.label ?? "");
const optLabel = (o) => (typeof o === "string" ? o : o.label ?? o.value ?? "");

// ============================================================= value helpers
export function initialAnswer(answerType, options = []) {
  switch (answerType) {
    case "multiple_choice":
    case "matrix":
      return [];
    case "rank":
      return options.map(optValue);
    case "numeric_set":
      return {};
    default:
      return "";
  }
}

export function isAnswered(answerType, value) {
  switch (answerType) {
    case "multiple_choice":
    case "matrix":
      return Array.isArray(value) && value.length > 0;
    case "rank":
      return Array.isArray(value) && value.length > 0;
    case "numeric_set":
      return value && typeof value === "object" &&
        Object.values(value).some((v) => v !== "" && v !== undefined && v !== null);
    default:
      return typeof value === "string" && value.trim() !== "";
  }
}

export function serializeAnswer(answerType, value) {
  switch (answerType) {
    case "multiple_choice":
      return JSON.stringify([...value].sort());
    case "matrix":
      return JSON.stringify([...value].sort());
    case "rank":
      return JSON.stringify(value);
    case "numeric_set":
      return JSON.stringify(value);
    default:
      return (value ?? "").toString();
  }
}

// =================================================================== widgets
function SingleChoice({ options, value, onChange }) {
  return (
    <>
      {options.map((opt, i) => {
        const v = optValue(opt);
        const selected = value === v;
        return (
          <button key={i} type="button" onClick={() => onChange(v)} style={choiceRowStyle(selected)}>
            <span style={{
              width: "1.1rem", height: "1.1rem", borderRadius: "50%",
              border: `2px solid ${selected ? COLORS.accent : "#adb3b4"}`,
              backgroundColor: selected ? COLORS.accent : "transparent",
              flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
              transition: "all 0.15s ease",
            }}>
              {selected && <span style={{ width: "0.4rem", height: "0.4rem", borderRadius: "50%", backgroundColor: "white" }} />}
            </span>
            <span style={choiceLabelStyle(selected)}>{optLabel(opt)}</span>
          </button>
        );
      })}
    </>
  );
}

function MultipleChoice({ options, value, onChange }) {
  const toggle = (v) => {
    onChange(value.includes(v) ? value.filter((x) => x !== v) : [...value, v]);
  };
  return (
    <>
      {options.map((opt, i) => {
        const v = optValue(opt);
        const selected = value.includes(v);
        return (
          <button key={i} type="button" onClick={() => toggle(v)} style={choiceRowStyle(selected)}>
            <span style={{
              width: "1.1rem", height: "1.1rem", borderRadius: "0.28rem",
              border: `2px solid ${selected ? COLORS.accent : "#adb3b4"}`,
              backgroundColor: selected ? COLORS.accent : "transparent",
              flexShrink: 0, display: "flex", alignItems: "center", justifyContent: "center",
              color: "white", fontSize: "0.72rem", fontWeight: 800,
              transition: "all 0.15s ease",
            }}>
              {selected && "✓"}
            </span>
            <span style={choiceLabelStyle(selected)}>{optLabel(opt)}</span>
          </button>
        );
      })}
    </>
  );
}

function NumericInput({ value, onChange, answerFormat }) {
  const meta = numericMeta(answerFormat);
  return (
    <>
      <div style={{ position: "relative", display: "flex", alignItems: "center" }}>
        <input
          type="number"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Enter a number…"
          step={meta.step}
          min={meta.min}
          max={meta.max}
          style={{ ...fieldStyle, paddingRight: meta.suffix ? "2.4rem" : fieldStyle.padding }}
          onFocus={focusOn}
          onBlur={focusOff}
        />
        {meta.suffix && (
          <span style={{ position: "absolute", right: "1rem", color: COLORS.muted, fontWeight: 700, fontSize: "0.9rem", pointerEvents: "none" }}>
            {meta.suffix}
          </span>
        )}
      </div>
      {meta.hint && <p style={hintStyle}>{meta.hint}</p>}
    </>
  );
}

function NumericSet({ options, value, onChange, answerFormat }) {
  const meta = numericMeta(answerFormat);
  const setRow = (label, v) => onChange({ ...value, [label]: v });
  return (
    <>
      {options.map((opt, i) => {
        const label = optLabel(opt);
        return (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "0.6rem" }}>
            <label style={{ flex: 1, fontSize: "0.85rem", color: COLORS.ink, fontWeight: 500 }}>{label}</label>
            <div style={{ position: "relative", width: "120px", flexShrink: 0 }}>
              <input
                type="number"
                value={value[label] ?? ""}
                onChange={(e) => setRow(label, e.target.value)}
                placeholder="0"
                step={meta.step}
                min={meta.min}
                max={meta.max}
                style={{ ...fieldStyle, padding: "0.6rem 0.8rem", paddingRight: meta.suffix ? "1.9rem" : "0.8rem" }}
                onFocus={focusOn}
                onBlur={focusOff}
              />
              {meta.suffix && (
                <span style={{ position: "absolute", right: "0.7rem", top: "50%", transform: "translateY(-50%)", color: COLORS.muted, fontWeight: 700, fontSize: "0.8rem", pointerEvents: "none" }}>
                  {meta.suffix}
                </span>
              )}
            </div>
          </div>
        );
      })}
      {meta.hint && <p style={hintStyle}>{meta.hint}</p>}
    </>
  );
}

function RankList({ value, onChange, options, answerFormat }) {
  const dragIndex = useRef(null);
  // value is the ordered list of tokens; map token -> display label
  const labelOf = useMemo(() => {
    const m = {};
    options.forEach((o) => { m[optValue(o)] = optLabel(o); });
    return m;
  }, [options]);

  const move = (from, to) => {
    if (to < 0 || to >= value.length || from === to) return;
    const next = [...value];
    const [item] = next.splice(from, 1);
    next.splice(to, 0, item);
    onChange(next);
  };

  return (
    <>
      {value.map((token, i) => (
        <div
          key={token}
          draggable
          onDragStart={() => { dragIndex.current = i; }}
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => { move(dragIndex.current, i); dragIndex.current = null; }}
          style={{
            display: "flex", alignItems: "center", gap: "0.85rem",
            padding: "0.8rem 1rem", backgroundColor: COLORS.chipBg,
            border: "2px solid transparent", borderRadius: "0.5rem",
            marginBottom: "0.6rem", cursor: "grab",
            fontSize: "0.875rem", fontWeight: 500, color: COLORS.ink,
          }}
        >
          <span style={{
            width: "1.7rem", height: "1.7rem", borderRadius: "50%",
            backgroundColor: COLORS.navy, color: "white",
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: "0.8rem", fontWeight: 800, flexShrink: 0,
          }}>{i + 1}</span>
          <span style={{ flex: 1 }}>{labelOf[token] ?? token}</span>
          <span style={{ display: "flex", flexDirection: "column", gap: "0.15rem" }}>
            <button type="button" onClick={() => move(i, i - 1)} disabled={i === 0}
              style={arrowBtnStyle(i === 0)}>▲</button>
            <button type="button" onClick={() => move(i, i + 1)} disabled={i === value.length - 1}
              style={arrowBtnStyle(i === value.length - 1)}>▼</button>
          </span>
        </div>
      ))}
      <p style={hintStyle}>
        Drag, or use ▲▼, to rank from most conformant (highest fitness) at top to least conformant at bottom.
      </p>
    </>
  );
}

const arrowBtnStyle = (disabled) => ({
  background: "none", border: "none", cursor: disabled ? "default" : "pointer",
  color: disabled ? "#cbd1d2" : COLORS.muted, fontSize: "0.6rem", lineHeight: 1, padding: 0,
});

// Parse pair-shaped options ("a__b") into a symmetric grid.
// The two value tokens are the (human-readable) axis labels. We DON'T align them
// against the " × " label, because the value is the sorted pair while the label
// keeps the original order — positional alignment would mislabel the axes. Pairs
// are matched order-independently so the stored submit token (= option.value) is
// preserved regardless of which cell the user clicks.
function parsePairs(options) {
  const axisOrder = [];
  const seen = new Set();
  const pairByKey = {}; // unordered "a b" -> submit token (original option.value)
  for (const o of options) {
    const v = optValue(o);
    const vt = v.split("__");
    if (vt.length !== 2) return null;
    vt.forEach((t) => { if (!seen.has(t)) { seen.add(t); axisOrder.push(t); } });
    pairByKey[[...vt].sort().join(" ")] = v;
  }
  return { axisOrder, pairByKey };
}

function MatrixGrid({ options, value, onChange }) {
  const parsed = useMemo(() => parsePairs(options), [options]);

  // Fallback: not pair-shaped → render as a checkbox list.
  if (!parsed) {
    return <MultipleChoice options={options} value={value} onChange={onChange} />;
  }

  const { axisOrder, pairByKey } = parsed;
  const tokenForPair = (a, b) => pairByKey[[a, b].sort().join(" ")];
  const toggle = (token) => {
    onChange(value.includes(token) ? value.filter((x) => x !== token) : [...value, token]);
  };

  const thStyle = { padding: "0.5rem 0.4rem", color: COLORS.muted, fontWeight: 700, fontSize: "0.62rem", textTransform: "uppercase", letterSpacing: "0.04em", textAlign: "center" };
  const rowHStyle = { padding: "0.5rem 0.5rem", textAlign: "left", color: COLORS.ink, fontWeight: 600, fontSize: "0.78rem" };

  return (
    <div style={{ overflowX: "auto" }}>
      <table style={{ width: "100%", borderCollapse: "collapse" }}>
        <thead>
          <tr>
            <th style={rowHStyle}></th>
            {axisOrder.map((c) => <th key={c} style={thStyle}>{c}</th>)}
          </tr>
        </thead>
        <tbody>
          {axisOrder.map((r) => (
            <tr key={r} style={{ borderTop: "1px solid #eef0f0" }}>
              <td style={rowHStyle}>{r}</td>
              {axisOrder.map((c) => {
                const token = tokenForPair(r, c);
                const exists = r !== c && token !== undefined;
                const on = exists && value.includes(token);
                return (
                  <td key={c} style={{ textAlign: "center", padding: "0.45rem 0.4rem" }}>
                    {exists ? (
                      <div onClick={() => toggle(token)} style={{
                        width: "1.2rem", height: "1.2rem", borderRadius: "0.28rem", margin: "0 auto",
                        border: `2px solid ${on ? COLORS.accent : "#c2c8c9"}`,
                        backgroundColor: on ? COLORS.accent : "transparent",
                        cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
                        color: "white", fontSize: "0.7rem", fontWeight: 800, transition: "all 0.15s ease",
                      }}>{on && "✓"}</div>
                    ) : (
                      <span style={{ color: "#dfe3e4" }}>·</span>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p style={hintStyle}>Tick each pair that co-occurs.</p>
    </div>
  );
}

function FreeText({ value, onChange }) {
  return (
    <textarea
      value={value}
      onChange={(e) => onChange(e.target.value)}
      placeholder="Type your answer here…"
      rows={7}
      style={{ ...fieldStyle, resize: "vertical", lineHeight: 1.6 }}
      onFocus={focusOn}
      onBlur={focusOff}
    />
  );
}

// =============================================================== dispatcher
export default function AnswerInput({ answerType, answerFormat, options = [], value, onChange }) {
  switch (answerType) {
    case "single_choice":
      return <SingleChoice options={options} value={value} onChange={onChange} />;
    case "multiple_choice":
      return <MultipleChoice options={options} value={value} onChange={onChange} />;
    case "numeric":
      return <NumericInput value={value} onChange={onChange} answerFormat={answerFormat} />;
    case "numeric_set":
      return <NumericSet options={options} value={value} onChange={onChange} answerFormat={answerFormat} />;
    case "rank":
      return <RankList options={options} value={value} onChange={onChange} answerFormat={answerFormat} />;
    case "matrix":
      return <MatrixGrid options={options} value={value} onChange={onChange} />;
    case "free_text":
    default:
      return <FreeText value={value} onChange={onChange} />;
  }
}
