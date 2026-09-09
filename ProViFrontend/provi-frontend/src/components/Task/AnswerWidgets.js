"use client";

import React, { useState, useMemo, useRef } from "react";

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
// Numeric presets, keyed by the task instance's `number_kind`
// (app/answer_formats.py NUMBER_KINDS). These replace the old separate
// pct / count / decimal answer formats.
function numericMeta(numberKind) {
  switch (numberKind) {
    case "percentage":
      return { suffix: "%", step: "0.1", min: 0, max: 100, hint: "Enter a number between 0 and 100, including decimals where applicable." };
    case "integer":
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
    case "matrix":
      // Empty selection is a valid answer (the participant may select no cells).
      return Array.isArray(value);
    case "multiple_choice":
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

function NumericInput({ value, onChange, numberKind }) {
  const meta = numericMeta(numberKind);
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

function NumericSet({ options, value, onChange, numberKind }) {
  const meta = numericMeta(numberKind);
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

function RankList({ value, onChange, options }) {
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
        Drag, or use ▲▼, to rank from most conformant (highest fitness) at top to least conformant at bottom. Ties in fitness are broken by frequency (more frequent = higher rank).
      </p>
    </>
  );
}

const arrowBtnStyle = (disabled) => ({
  background: "none", border: "none", cursor: disabled ? "default" : "pointer",
  color: disabled ? "#cbd1d2" : COLORS.muted, fontSize: "0.6rem", lineHeight: 1, padding: 0,
});

// Shorten long violation labels for chips and left-panel badges.
function abbrevViolation(label) {
  return label
    .replace(/^Move on Model:\s*/i, "Mdl:")
    .replace(/^Move on Log:\s*/i, "Log:");
}

// Separator for pairByKey map keys. Must be a char that never appears in a
// violation label so two different pairs can never collide on the same key.
const PAIR_SEP = "\u0000";

// Parse pair-shaped options ("a__b") into a symmetric grid.
// The two value tokens are the (human-readable) axis labels. We DON'T align them
// against the " × " label, because the value is the sorted pair while the label
// keeps the original order — positional alignment would mislabel the axes. Pairs
// are matched order-independently so the stored submit token (= option.value) is
// preserved regardless of which cell the user clicks.
function parsePairs(options) {
  const axisOrder = [];
  const seen = new Set();
  const pairByKey = {}; // unordered "a<SEP>b" -> submit token (original option.value)
  for (const o of options) {
    const v = optValue(o);
    const vt = v.split("__");
    if (vt.length !== 2) return null;
    vt.forEach((t) => { if (!seen.has(t)) { seen.add(t); axisOrder.push(t); } });
    pairByKey[[...vt].sort().join(PAIR_SEP)] = v;
  }
  return { axisOrder, pairByKey };
}

function MatrixGrid({ options, value, onChange }) {
  const parsed = useMemo(() => parsePairs(options), [options]);
  const [activeIdx, setActiveIdx] = useState(0);

  // Fallback: not pair-shaped → render as a checkbox list.
  if (!parsed) {
    return <MultipleChoice options={options} value={value} onChange={onChange} />;
  }

  const { axisOrder, pairByKey } = parsed;
  const tokenForPair = (a, b) => pairByKey[[a, b].sort().join(PAIR_SEP)];
  const toggle = (token) => {
    onChange(value.includes(token) ? value.filter((x) => x !== token) : [...value, token]);
  };

  const safeIdx = Math.min(activeIdx, axisOrder.length - 1);
  const activeViolation = axisOrder[safeIdx];

  const pairCountFor = (v) =>
    axisOrder.reduce((n, other) => {
      if (other === v) return n;
      const tok = tokenForPair(v, other);
      return tok && value.includes(tok) ? n + 1 : n;
    }, 0);

  return (
    <div>
      {/* Instruction banner */}
      <div style={{
        display: "flex", alignItems: "flex-start", gap: "6px",
        padding: "7px 10px", background: "#f0f7ff",
        borderRadius: "7px", marginBottom: "10px",
        border: "1px solid #dbeafe",
      }}>
        <svg style={{ width: "14px", height: "14px", flexShrink: 0, marginTop: "1px" }} viewBox="0 0 20 20" fill="#1e40af" aria-hidden="true">
          <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
        </svg>
        <span style={{ fontSize: "0.72rem", color: "#1e40af", lineHeight: 1.4 }}>
          <strong>Select a violation</strong> on the left, then{" "}
          <strong>tick</strong> which violations it co-occurs with on the right.
        </span>
      </div>

      {/* Two-panel — height grows with N, capped at 320px */}
      <div style={{ display: "flex", gap: "8px", height: `${Math.min(320, Math.max(200, axisOrder.length * 44))}px` }}>

        {/* Left panel: violation list */}
        <div style={{
          flex: "0 0 100px", border: `1px solid ${COLORS.line}`,
          borderRadius: "8px", overflowY: "auto", background: COLORS.fieldBg,
        }}>
          <div style={{
            padding: "5px 7px", fontSize: "0.6rem", fontWeight: 700,
            color: COLORS.muted, textTransform: "uppercase",
            borderBottom: `1px solid ${COLORS.line}`, letterSpacing: "0.06em",
          }}>
            VIOLATION
          </div>
          {axisOrder.map((v, i) => {
            const active = i === safeIdx;
            const count = pairCountFor(v);
            return (
              <div
                key={v}
                onClick={() => setActiveIdx(i)}
                style={{
                  display: "flex", alignItems: "center", gap: "6px",
                  padding: "6px 8px",
                  background: active ? COLORS.accentSoft : "transparent",
                  borderLeft: `3px solid ${active ? COLORS.accent : "transparent"}`,
                  borderBottom: i < axisOrder.length - 1 ? `1px solid ${COLORS.line}` : "none",
                  cursor: "pointer",
                }}
              >
                <span style={{
                  flex: 1, minWidth: 0,
                  fontSize: "0.7rem", color: active ? COLORS.navy : COLORS.ink,
                  fontWeight: active ? 700 : 500, lineHeight: 1.3,
                  wordBreak: "break-word",
                }}>
                  {v}
                </span>
                {count > 0 && (
                  <span style={{
                    flexShrink: 0,
                    background: COLORS.accent, color: "white",
                    fontSize: "0.6rem", fontWeight: 900,
                    width: "14px", height: "14px", borderRadius: "50%",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    {count}
                  </span>
                )}
              </div>
            );
          })}
        </div>

        {/* Right panel: co-occurrence checkboxes */}
        <div style={{
          flex: 1, border: `1px solid ${COLORS.line}`,
          borderRadius: "8px", overflowY: "auto", background: "white",
        }}>
          <div style={{
            padding: "5px 8px", fontSize: "0.6rem", fontWeight: 700,
            color: COLORS.muted, textTransform: "uppercase",
            borderBottom: `1px solid ${COLORS.line}`, letterSpacing: "0.06em",
          }}>
            CO-OCCURS WITH
          </div>
          {axisOrder
            .filter((v) => v !== activeViolation)
            .map((v, i, arr) => {
              const token = tokenForPair(activeViolation, v);
              const checked = token !== undefined && value.includes(token);
              return (
                <div
                  key={v}
                  role="button"
                  tabIndex={0}
                  style={{
                    display: "flex", alignItems: "flex-start", gap: "8px",
                    padding: "7px 10px",
                    background: checked ? COLORS.accentSoft : "white",
                    borderBottom: i < arr.length - 1 ? `1px solid ${COLORS.line}` : "none",
                    cursor: token !== undefined ? "pointer" : "default",
                    userSelect: "none",
                  }}
                  onClick={() => token !== undefined && toggle(token)}
                  onKeyDown={(e) => (e.key === " " || e.key === "Enter") && token !== undefined && toggle(token)}
                >
                  <div style={{
                    width: "15px", height: "15px", borderRadius: "4px",
                    border: `2px solid ${checked ? COLORS.accent : "#c2c8c9"}`,
                    background: checked ? COLORS.accent : "transparent",
                    flexShrink: 0, marginTop: "1px",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    color: "white", fontSize: "9px", fontWeight: 900,
                    transition: "all 0.12s ease",
                  }}>
                    {checked && "✓"}
                  </div>
                  <div>
                    <span style={{
                      fontSize: "0.78rem", color: checked ? COLORS.navy : COLORS.ink,
                      fontWeight: checked ? 600 : 400, lineHeight: 1.3, display: "block",
                    }}>
                      {v}
                    </span>
                    {checked && (
                      <span style={{ fontSize: "0.65rem", color: COLORS.muted, fontStyle: "italic" }}>
                        ↔ symmetric pair
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
        </div>
      </div>

      {/* Summary chip area */}
      {value.length > 0 ? (
        <div style={{ marginTop: "10px", paddingTop: "8px", borderTop: `1px solid ${COLORS.line}` }}>
          <p style={{
            fontSize: "0.6rem", fontWeight: 700, color: COLORS.muted,
            textTransform: "uppercase", letterSpacing: "0.06em", margin: "0 0 6px",
          }}>
            SELECTED PAIRS · {value.length}
          </p>
          <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
            {value.map((token) => {
              const parts = token.split("__");
              const label = parts.length === 2
                ? `${abbrevViolation(parts[0])} × ${abbrevViolation(parts[1])}`
                : token;
              return (
                <div
                  key={token}
                  style={{
                    display: "inline-flex", alignItems: "center", gap: "5px",
                    background: COLORS.accentSoft,
                    border: "1px solid #b8cce4",
                    borderRadius: "20px", padding: "3px 8px",
                  }}
                >
                  <span style={{ fontSize: "0.68rem", fontWeight: 700, color: COLORS.navy }}>
                    {label}
                  </span>
                  <span
                    onClick={() => toggle(token)}
                    style={{
                      color: COLORS.accent, fontSize: "0.75rem",
                      cursor: "pointer", fontWeight: 900, lineHeight: 1,
                    }}
                  >
                    ×
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      ) : (
        <p style={{ ...hintStyle, marginTop: "10px" }}>
          No pairs selected. If no violations co-occur above the threshold, leave all unchecked.
        </p>
      )}
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
export default function AnswerInput({ answerType, numberKind, options = [], value, onChange }) {
  switch (answerType) {
    case "single_choice":
      return <SingleChoice options={options} value={value} onChange={onChange} />;
    case "multiple_choice":
      return <MultipleChoice options={options} value={value} onChange={onChange} />;
    case "numeric":
      return <NumericInput value={value} onChange={onChange} numberKind={numberKind} />;
    case "numeric_set":
      return <NumericSet options={options} value={value} onChange={onChange} numberKind={numberKind} />;
    case "rank":
      return <RankList options={options} value={value} onChange={onChange} />;
    case "matrix":
      return <MatrixGrid options={options} value={value} onChange={onChange} />;
    case "free_text":
    default:
      return <FreeText value={value} onChange={onChange} />;
  }
}
