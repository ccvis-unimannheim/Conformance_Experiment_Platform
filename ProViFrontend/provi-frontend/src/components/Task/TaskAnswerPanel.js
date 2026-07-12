"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { taskDescriptions, idiomDescriptions } from "./descriptions";
import AnswerInput, { initialAnswer, isAnswered, serializeAnswer } from "./AnswerWidgets";

// ── Term definitions (short, inline versions) ──────────────────────────────
const TERM_DEFS = {
  guideline:            { label: "Guideline",                       def: "A formal description of how a process is intended to be executed. It defines the allowed activities and sequences, and serves as the reference for conformance checking." },
  trace:                { label: "Trace",                           def: "The sequence of activities recorded for a single process execution (one case). Each trace can be compared against the guideline to check whether it was executed correctly." },
  event_log:            { label: "Event Log",                       def: "A collection of recorded events from process executions. Events sharing the same case identifier form a trace. The event log is what is checked against the guideline." },
  guideline_violation:  { label: "Guideline Violation",             def: "Occurs when the recorded behaviour of a trace does not match the guideline. Two common types: an extra activity was performed (not allowed by the guideline), or a required activity was missing." },
  conformant_trace:     { label: "Conformant Trace",                def: "A trace where every activity follows a path the guideline allows — no steps are missing and no unexpected steps occur." },
  non_conformant_trace: { label: "Non-conformant Trace",            def: "A trace that contains at least one activity violating the guideline — e.g. a required step was skipped or an unexpected step was performed." },
  degree_of_conformance:{ label: "Degree of Conformance (Fitness)", def: "A value between 0 and 1 measuring how well the overall event log matches the guideline. Note: this is NOT the same as conformance rate. Fitness accounts for the extent of violations, not just whether a trace is fully conformant." },
  conformance_rate:     { label: "Conformance Rate",                def: "The percentage of traces in the event log that are fully conformant with the guideline. A trace is either conformant (counts) or not — it is a binary measure per trace." },
  process_goal:         { label: "Process Goal",                    def: "A desired outcome that a process execution aims to achieve (e.g. a successful treatment or an approved application). Violations may affect whether the goal is reached." },
  attribute:            { label: "Attribute",                       def: "A data property recorded alongside events or traces. Types include: control-flow (activity order), data (values like amount or status), resource (who performed the activity), and time (when or how long)." },
};

// ── Per-task term mapping ───────────────────────────────────────────────────
const TASK_TERMS = {
  task03: ["conformant_trace", "non_conformant_trace", "trace"],
  task04: ["degree_of_conformance", "event_log", "trace"],
  task06: ["degree_of_conformance", "event_log", "guideline"],
  task10: ["trace", "event_log"],
  task11: ["guideline_violation", "guideline"],
  task19: ["guideline_violation", "process_goal"],
  task20: ["attribute", "trace", "event_log", "guideline_violation"],
  task34: ["guideline_violation", "trace", "guideline"],
};

// ── TermsStrip component ────────────────────────────────────────────────────
function TermsStrip({ taskKey, experimentId }) {
  const termKeys = TASK_TERMS[taskKey] ?? [];
  const [openTerm, setOpenTerm] = useState(null);
  const openCountsRef = useRef({});
  const openTimeRef   = useRef(null);

  // Reset when task changes
  useEffect(() => {
    setOpenTerm(null);
    openCountsRef.current = {};
    openTimeRef.current = null;
  }, [taskKey]);

  if (termKeys.length === 0) return null;

  async function sendTermEvent(termKey, openIndex, dwellMs) {
    try {
      await fetch("/api/uitracking/term-help", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          experiment_id:   experimentId ?? null,
          task_key:        taskKey,
          term_key:        termKey,
          open_index:      openIndex,
          open_datetime:   openTimeRef.current,
          dwell_ms:        dwellMs,
          insert_datetime: new Date().toISOString(),
        }),
      });
    } catch (_) {}
  }

  function handleChipClick(termKey) {
    const now = new Date().toISOString();
    if (openTerm === termKey) {
      // closing
      const dwellMs = openTimeRef.current ? Date.now() - new Date(openTimeRef.current).getTime() : 0;
      sendTermEvent(termKey, openCountsRef.current[termKey] ?? 1, dwellMs);
      setOpenTerm(null);
      openTimeRef.current = null;
    } else {
      // closing previous if any
      if (openTerm) {
        const dwellMs = openTimeRef.current ? Date.now() - new Date(openTimeRef.current).getTime() : 0;
        sendTermEvent(openTerm, openCountsRef.current[openTerm] ?? 1, dwellMs);
      }
      // opening new
      openCountsRef.current[termKey] = (openCountsRef.current[termKey] ?? 0) + 1;
      openTimeRef.current = now;
      setOpenTerm(termKey);
    }
  }

  const activeDef = openTerm ? TERM_DEFS[openTerm] : null;

  return (
    <div style={{ marginBottom: "1rem", paddingBottom: "1rem", borderBottom: "1px solid #f0f0f0" }}>
      <p style={{ fontSize: "0.62rem", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.15em", color: "#5a6061", margin: "0 0 0.5rem 0" }}>
        Key Terms
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "0.375rem" }}>
        {termKeys.map(key => {
          const term = TERM_DEFS[key];
          if (!term) return null;
          const isActive = openTerm === key;
          return (
            <button
              key={key}
              type="button"
              onClick={() => handleChipClick(key)}
              style={{
                padding: "0.25rem 0.625rem",
                borderRadius: "999px",
                border: isActive ? "1.5px solid #00305e" : "1.5px solid #cbd5e1",
                backgroundColor: isActive ? "#00305e" : "transparent",
                color: isActive ? "white" : "#00305e",
                fontSize: "0.72rem",
                fontWeight: 600,
                cursor: "pointer",
                transition: "all 0.15s ease",
                display: "flex", alignItems: "center", gap: "0.3rem",
              }}
            >
              <span style={{ fontSize: "0.65rem" }}>{isActive ? "▲" : "?"}</span>
              {term.label}
            </button>
          );
        })}
      </div>
      {activeDef && (
        <div style={{
          marginTop: "0.625rem",
          backgroundColor: "#eef2f8",
          borderLeft: "3px solid #00305e",
          borderRadius: "0 0.375rem 0.375rem 0",
          padding: "0.625rem 0.75rem",
          fontSize: "0.78rem",
          color: "#2d3435",
          lineHeight: 1.65,
        }}>
          <strong style={{ color: "#00305e" }}>{activeDef.label}:</strong>{" "}
          {activeDef.def}
        </div>
      )}
    </div>
  );
}

// ── ConfidenceModal ─────────────────────────────────────────────────────────
// Shown after the participant clicks "Submit & Next". They must rate how
// confident they are (1 = least, 5 = most); selecting a score submits the
// answer together with the rating and advances to the next task.
function ConfidenceModal({ submitting, onSelect }) {
  const [hovered, setHovered] = useState(null);

  return (
    <div style={{
      position: "fixed", inset: 0, zIndex: 1000,
      backgroundColor: "rgba(45,52,53,0.55)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "1.5rem",
    }}>
      <div style={{
        backgroundColor: "white",
        borderRadius: "0.9rem",
        boxShadow: "0 24px 60px rgba(45,52,53,0.35)",
        padding: "2rem 2.25rem",
        width: "100%", maxWidth: "440px",
        textAlign: "center",
      }}>
        <h2 style={{
          fontSize: "1.05rem", fontWeight: 700, color: "#00305e",
          margin: "0 0 0.5rem 0", lineHeight: 1.4,
        }}>
          How confident are you in your answer?
        </h2>
        <p style={{ fontSize: "0.8rem", color: "#5a6061", margin: "0 0 1.5rem 0", lineHeight: 1.5 }}>
          Select a score from 1 (least confident) to 5 (most confident).
        </p>

        <div style={{ display: "flex", justifyContent: "center", gap: "0.625rem", marginBottom: "0.75rem" }}>
          {[1, 2, 3, 4, 5].map((n) => {
            const active = hovered === n;
            return (
              <button
                key={n}
                type="button"
                disabled={submitting}
                onClick={() => onSelect(n)}
                onMouseEnter={() => setHovered(n)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  width: "3.25rem", height: "3.25rem",
                  borderRadius: "0.6rem",
                  border: active ? "2px solid #00305e" : "2px solid #cbd5e1",
                  backgroundColor: active ? "#00305e" : "white",
                  color: active ? "white" : "#00305e",
                  fontSize: "1.15rem", fontWeight: 700,
                  cursor: submitting ? "not-allowed" : "pointer",
                  transition: "background-color 0.12s, border-color 0.12s, color 0.12s",
                }}
              >
                {n}
              </button>
            );
          })}
        </div>

        <div style={{
          display: "flex", justifyContent: "space-between",
          fontSize: "0.68rem", fontWeight: 600, color: "#9199a0",
          textTransform: "uppercase", letterSpacing: "0.06em",
          padding: "0 0.25rem",
        }}>
          <span>Least confident</span>
          <span>Most confident</span>
        </div>

        {submitting && (
          <p style={{ fontSize: "0.8rem", color: "#5a6061", margin: "1.25rem 0 0 0" }}>
            Saving…
          </p>
        )}
      </div>
    </div>
  );
}

const TaskAnswerPanel = ({
  options = [],
  answerType = "free_text",
  answerFormat = "free-text",
  taskLabel = "",
  taskId,
  taskKey = "",
  idiomId = "",
  idiomKey = "",
  datasetId = "",
  experimentId = "",
  trialIndex = 0,
  presentationOrder = 0,
  totalTasks = 1,
  currentTaskIndex = 0,
  onAnswerSubmit,
  paramHints = [],
}) => {
  const router = useRouter();
  const [answer, setAnswer] = useState(() => initialAnswer(answerType, options));
  const [submitting, setSubmitting] = useState(false);
  const [idiomExpanded, setIdiomExpanded] = useState(false);
  const [showTaskTooltip, setShowTaskTooltip] = useState(false);
  const [showConfidence, setShowConfidence] = useState(false);

  const startTimeRef = useRef(Date.now());
  // Response time is captured the moment the participant clicks "Submit & Next"
  // (before they pick a confidence score), so rating time doesn't inflate it.
  const pendingResponseTimeRef = useRef(0);

  const isLastTask = currentTaskIndex >= totalTasks - 1;

  const taskDesc = taskDescriptions[taskKey] ?? null;
  const idiomDesc = idiomDescriptions[idiomKey] ?? null;

  useEffect(() => {
    setAnswer(initialAnswer(answerType, options));
    setIdiomExpanded(false);
    setShowConfidence(false);
    startTimeRef.current = Date.now();
  }, [currentTaskIndex, answerType]);

  // Step 1: validate the answer and open the confidence prompt. The answer is
  // not sent until a confidence score is chosen (see submitWithConfidence).
  const handleSubmit = (e) => {
    e.preventDefault();
    if (submitting) return;
    if (!isAnswered(answerType, answer)) {
      alert("Please provide an answer before submitting.");
      return;
    }
    pendingResponseTimeRef.current = Date.now() - startTimeRef.current;
    setShowConfidence(true);
  };

  // Step 2: the participant picked a confidence score → submit answer + rating,
  // then advance to the next task (or the end page on the last task).
  const submitWithConfidence = async (confidence) => {
    if (submitting) return;
    setSubmitting(true);
    const response_time_ms = pendingResponseTimeRef.current;

    const payload = {
      experiment_id: experimentId,
      question_id: taskId?.toString(),
      task_id: taskId?.toString(),
      idiom_id: idiomId,
      dataset_id: datasetId,
      trial_index: trialIndex,
      presentation_order: presentationOrder,
      answer: serializeAnswer(answerType, answer),
      response_time_ms: response_time_ms,
      confidence: confidence,
      insert_datetime: new Date().toISOString(),
    };

    try {
      const response = await fetch("/api/survey/answer", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      if (!response.ok) console.error(`Submit failed: ${response.status}`);
      else console.log(`Answer saved for task ${taskId}, response_time_ms: ${response_time_ms}, confidence: ${confidence}`);
    } catch (error) {
      console.warn("Backend unreachable — continuing:", error.message);
    } finally {
      setSubmitting(false);
      setShowConfidence(false);
      setAnswer(initialAnswer(answerType, options));
      if (isLastTask) router.push("/endpage");
      else onAnswerSubmit?.();
    }
  };

  const cardStyle = {
    backgroundColor: "white",
    borderRadius: "0.75rem",
    padding: "2rem",
    boxShadow: "0 12px 32px rgba(45,52,53,0.04)",
    border: "1px solid #f0f0f0",
  };

  const headerStyle = {
    fontSize: "0.7rem",
    fontWeight: 700,
    color: "#5a6061",
    letterSpacing: "0.2em",
    textTransform: "uppercase",
    margin: "0 0 1.5rem 0",
  };

  const submitBtnStyle = {
    marginTop: "1.25rem",
    width: "100%",
    padding: "1rem",
    backgroundColor: submitting ? "#4a7ab5" : "#00305e",
    color: "white",
    border: "none",
    borderRadius: "0.5rem",
    fontWeight: 700,
    fontSize: "0.875rem",
    letterSpacing: "0.05em",
    cursor: submitting ? "not-allowed" : "pointer",
    boxShadow: "0 4px 14px rgba(0,48,94,0.2)",
    transition: "background-color 0.15s ease",
  };

  return (
    <aside style={{
      display: "flex", flexDirection: "column",
      position: "sticky", top: "5rem",
      maxHeight: "calc(100vh - 6rem)",
    }}>
      <div style={{ ...cardStyle, display: "flex", flexDirection: "column", minHeight: 0, padding: 0 }}>

        {/* Scrollable content */}
        <div style={{ flex: 1, overflowY: "auto", scrollbarWidth: "none", padding: "2rem" }}>

          {/* Key Terms strip */}
          <TermsStrip taskKey={taskKey} experimentId={experimentId} />

          {/* Task Label with toggle info */}
          {taskLabel && (
            <div style={{ marginBottom: "1rem", paddingBottom: "1rem", borderBottom: "1px solid #f0f0f0" }}>
              <div style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem" }}>
                <p
                  style={{
                    fontSize: "1.05rem",
                    fontWeight: 700,
                    color: "#00305e",
                    lineHeight: 1.5,
                    margin: 0,
                    flex: 1,
                  }}
                >
                  {taskLabel}
                </p>
                {taskDesc && (
                  <button
                    type="button"
                    onClick={() => setShowTaskTooltip(v => !v)}
                    title="About this task"
                    style={{
                      flexShrink: 0,
                      background: "none",
                      border: "1px solid #cbd5e1",
                      borderRadius: "50%",
                      width: "1.4rem",
                      height: "1.4rem",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      fontSize: "0.72rem",
                      fontWeight: 700,
                      color: showTaskTooltip ? "white" : "#5a6061",
                      backgroundColor: showTaskTooltip ? "#00305e" : "transparent",
                      cursor: "pointer",
                      marginTop: "0.15rem",
                      transition: "background-color 0.15s, color 0.15s",
                    }}
                  >
                    i
                  </button>
                )}
              </div>

              {showTaskTooltip && taskDesc && (
                <div style={{
                  marginTop: "0.75rem",
                  backgroundColor: "#f0f4f8",
                  color: "#2d3435",
                  padding: "0.75rem 0.875rem",
                  borderRadius: "0.4rem",
                  fontSize: "0.8rem",
                  lineHeight: 1.6,
                  borderLeft: "3px solid #00305e",
                }}>
                  {taskDesc}
                </div>
              )}

              {/* Chart-parameter hint — above the divider, right under the question
                  (and below the question's info box when expanded), so participants
                  can't miss it. Light-blue hint box with an outline bulb icon. */}
              {paramHints.length > 0 && (
                <div style={{
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "0.625rem",
                  background: "#eff6ff",
                  border: "1px solid #cfe2fb",
                  borderRadius: "0.6rem",
                  padding: "0.75rem 0.875rem",
                  marginTop: "1rem",
                }}>
                  <svg
                    width="20" height="20" viewBox="0 0 24 24" fill="none"
                    stroke="#2563eb" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"
                    style={{ flexShrink: 0, marginTop: "0.05rem" }} aria-hidden="true"
                  >
                    <path d="M15 14c.2-1 .7-1.7 1.5-2.5C17.7 10.2 18 9 18 7.5A6 6 0 1 0 6 7.5c0 1.5.5 2.7 1.5 4 .8.8 1.3 1.5 1.5 2.5" />
                    <path d="M9 18h6" />
                    <path d="M10 22h4" />
                  </svg>
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem" }}>
                    {paramHints.map((hint, i) => (
                      <div key={i} style={{ fontSize: "0.8rem", lineHeight: 1.5, color: "#1e3a5f" }}>
                        <span style={{ fontWeight: 700 }}>{hint.label}:</span>{" "}
                        <span style={{ fontFamily: "monospace" }}>{hint.value}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Idiom expandable description */}
          {idiomDesc && (
            <div style={{
              marginBottom: "1.25rem",
              border: "1px solid #eef0f0",
              borderRadius: "0.5rem",
              overflow: "hidden",
            }}>
              <button
                type="button"
                onClick={() => setIdiomExpanded(!idiomExpanded)}
                style={{
                  width: "100%",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "0.6rem 0.875rem",
                  backgroundColor: "#f8f9fa",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "0.72rem",
                  fontWeight: 700,
                  color: "#5a6061",
                  letterSpacing: "0.1em",
                  textTransform: "uppercase",
                  textAlign: "left",
                }}
              >
                <span>About this visualization</span>
                <span style={{ fontSize: "0.65rem", color: "#9ca3af" }}>
                  {idiomExpanded ? "▲" : "▼"}
                </span>
              </button>
              {idiomExpanded && (
                <div style={{
                  padding: "0.875rem",
                  backgroundColor: "white",
                  fontSize: "0.8rem",
                  color: "#5a6061",
                  lineHeight: 1.7,
                  borderTop: "1px solid #eef0f0",
                }}>
                  {idiomDesc}
                </div>
              )}
            </div>
          )}

          {/* Answer section */}
          <h2 style={headerStyle}>Your Answer</h2>

          <form id="answer-form" onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
            <AnswerInput
              answerType={answerType}
              answerFormat={answerFormat}
              options={options}
              value={answer}
              onChange={setAnswer}
            />
          </form>
        </div>

        {/* Submit button — always visible at bottom */}
        <div style={{ padding: "1rem 2rem", borderTop: "1px solid #f0f0f0", backgroundColor: "white", borderRadius: "0 0 0.75rem 0.75rem" }}>
          <button type="submit" form="answer-form" disabled={submitting} style={{ ...submitBtnStyle, marginTop: 0 }}>
            {submitting ? "Saving…" : isLastTask ? "Finish Experiment" : "Submit & Next →"}
          </button>
        </div>
      </div>

      {showConfidence && (
        <ConfidenceModal submitting={submitting} onSelect={submitWithConfidence} />
      )}
    </aside>
  );
};

export default TaskAnswerPanel;