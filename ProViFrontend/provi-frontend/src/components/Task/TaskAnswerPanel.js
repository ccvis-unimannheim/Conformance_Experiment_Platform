"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { taskDescriptions, idiomDescriptions } from "./descriptions";
import AnswerInput, { initialAnswer, isAnswered, serializeAnswer } from "./AnswerWidgets";

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

  const startTimeRef = useRef(Date.now());

  const isLastTask = currentTaskIndex >= totalTasks - 1;

  const taskDesc = taskDescriptions[taskKey] ?? null;
  const idiomDesc = idiomDescriptions[idiomKey] ?? null;

  useEffect(() => {
    setAnswer(initialAnswer(answerType, options));
    setIdiomExpanded(false);
    startTimeRef.current = Date.now();
  }, [currentTaskIndex, answerType]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!isAnswered(answerType, answer)) {
      alert("Please provide an answer before submitting.");
      return;
    }

    setSubmitting(true);
    const response_time_ms = Date.now() - startTimeRef.current;

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
      else console.log(`Answer saved for task ${taskId}, response_time_ms: ${response_time_ms}`);
    } catch (error) {
      console.warn("Backend unreachable — continuing:", error.message);
    } finally {
      setSubmitting(false);
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

          {/* Parameter hints callout */}
          {paramHints.length > 0 && (
            <div style={{
              background: "#f0f4f8",
              borderLeft: "3px solid #00305e",
              borderRadius: "0 0.375rem 0.375rem 0",
              padding: "0.625rem 0.75rem",
              marginBottom: "0.875rem",
            }}>
              <p style={{
                fontSize: "0.62rem",
                fontWeight: 700,
                textTransform: "uppercase",
                letterSpacing: "0.12em",
                color: "#5a6061",
                margin: "0 0 0.375rem 0",
              }}>
                Chart parameters
              </p>
              {paramHints.map((hint, i) => (
                <div key={i} style={{ fontSize: "0.72rem", lineHeight: 1.8 }}>
                  <span style={{ fontWeight: 700, color: "#00305e" }}>
                    {hint.label}:
                  </span>
                  {" "}
                  <span style={{ fontFamily: "monospace", color: "#2d3435" }}>
                    {hint.value}
                  </span>
                </div>
              ))}
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
    </aside>
  );
};

export default TaskAnswerPanel;