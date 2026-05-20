"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";

/**
 * TaskAnswerPanel
 * Right panel — answer box for each task.
 *
 * Behaviour:
 *  - If options are provided  → show each as a selectable answer box
 *  - If no options            → show a free-text box (default)
 *
 * On submit: saves answer + response_time_ms to backend, then advances to next task.
 *
 * Props:
 *  - options            : [{ label, value }]  — if empty, free-text is shown
 *  - taskId             : number/string
 *  - idiomId            : string
 *  - datasetId          : string
 *  - trialIndex         : number
 *  - presentationOrder  : number
 *  - totalTasks         : total number of tasks
 *  - currentTaskIndex   : 0-based index
 *  - onAnswerSubmit     : callback fired after submit to advance to next task
 */
const TaskAnswerPanel = ({
  options = [],
  taskId,
  idiomId = "",
  datasetId = "",
  experimentId = "",
  trialIndex = 0,
  presentationOrder = 0,
  totalTasks = 1,
  currentTaskIndex = 0,
  onAnswerSubmit,
}) => {
  const router = useRouter();
  const [selectedAnswer, setSelectedAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Track when the current task started
  const startTimeRef = useRef(Date.now());

  const hasOptions = options.length > 0;
  const isLastTask = currentTaskIndex >= totalTasks - 1;

  useEffect(() => {
    setSelectedAnswer("");
    startTimeRef.current = Date.now();
  }, [currentTaskIndex]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedAnswer.trim()) {
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
      experiment_id: experimentId,
      trial_index: trialIndex,
      presentation_order: presentationOrder,
      answer: selectedAnswer.toString(),
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
      setSelectedAnswer("");
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
    fontSize: "0.7rem", fontWeight: 700, color: "#5a6061",
    letterSpacing: "0.2em", textTransform: "uppercase",
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
    <aside style={{ gridColumn: "span 4", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
      <div style={cardStyle}>
        <h2 style={headerStyle}>Your Answer</h2>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>

          {hasOptions ? (
            options.map((option, index) => {
              const isSelected = selectedAnswer === option.value;
              return (
                <button
                  key={index}
                  type="button"
                  onClick={() => setSelectedAnswer(option.value)}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.875rem",
                    width: "100%",
                    padding: "1rem 1.25rem",
                    backgroundColor: isSelected ? "#eef2f8" : "#f2f4f4",
                    border: `2px solid ${isSelected ? "#3c5f90" : "transparent"}`,
                    borderRadius: "0.5rem",
                    cursor: "pointer",
                    textAlign: "left",
                    transition: "all 0.15s ease",
                  }}
                >
                  {/* Circle indicator */}
                  <div style={{
                    width: "1.1rem", height: "1.1rem",
                    borderRadius: "50%",
                    border: `2px solid ${isSelected ? "#3c5f90" : "#adb3b4"}`,
                    backgroundColor: isSelected ? "#3c5f90" : "transparent",
                    flexShrink: 0,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    transition: "all 0.15s ease",
                  }}>
                    {isSelected && (
                      <div style={{ width: "0.4rem", height: "0.4rem", borderRadius: "50%", backgroundColor: "white" }} />
                    )}
                  </div>
                  <span style={{
                    fontSize: "0.875rem",
                    fontWeight: isSelected ? 600 : 500,
                    color: isSelected ? "#00305e" : "#2d3435",
                    lineHeight: 1.4,
                  }}>
                    {option.label}
                  </span>
                </button>
              );
            })
          ) : (
            <textarea
              value={selectedAnswer}
              onChange={(e) => setSelectedAnswer(e.target.value)}
              placeholder="Type your answer here…"
              rows={7}
              style={{
                width: "100%",
                padding: "1rem",
                border: "2px solid #dde4e5",
                borderRadius: "0.5rem",
                fontSize: "0.875rem",
                color: "#2d3435",
                resize: "vertical",
                outline: "none",
                fontFamily: "inherit",
                lineHeight: 1.6,
                boxSizing: "border-box",
                backgroundColor: "#fafbfc",
                transition: "border-color 0.15s ease",
              }}
              onFocus={(e) => { e.target.style.borderColor = "#3c5f90"; }}
              onBlur={(e) => { e.target.style.borderColor = "#dde4e5"; }}
            />
          )}

          {/* Submit button — same for both types */}
          <button type="submit" disabled={submitting} style={submitBtnStyle}>
            {submitting ? "Saving…" : isLastTask ? "Finish Experiment" : "Submit & Next →"}
          </button>
        </form>
      </div>
    </aside>
  );
};

export default TaskAnswerPanel;