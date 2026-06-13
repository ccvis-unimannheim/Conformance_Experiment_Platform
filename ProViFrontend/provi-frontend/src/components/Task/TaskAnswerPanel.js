"use client";

import React, { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { taskDescriptions, idiomDescriptions } from "./descriptions";

const TaskAnswerPanel = ({
  options = [],
  taskLabel = "",
  taskId,
  idiomId = "",
  idiomKey = "",
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
  const [idiomExpanded, setIdiomExpanded] = useState(false);
  const [showTaskTooltip, setShowTaskTooltip] = useState(false);

  const startTimeRef = useRef(Date.now());

  const hasOptions = options.length > 0;
  const isLastTask = currentTaskIndex >= totalTasks - 1;

  const taskDesc = taskDescriptions[Number(taskId)] ?? null;
  const idiomDesc = idiomDescriptions[idiomKey] ?? null;

  useEffect(() => {
    setSelectedAnswer("");
    setIdiomExpanded(false);
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
  
  // temporary debug — remove after testing
  console.log("taskId:", taskId, typeof taskId);
  console.log("taskDesc:", taskDescriptions[Number(taskId)]);

  return (
    <aside style={{ display: "flex", flexDirection: "column", gap: "1.5rem", position: "sticky", top: "5rem", maxHeight: "calc(100vh - 6rem)", overflowY: "auto", scrollbarWidth: "none" }}>
      <div style={cardStyle}>

        {/* Task Label with hover tooltip */}
        {taskLabel && (
          <div style={{ position: "relative", marginBottom: "1rem", paddingBottom: "1rem", borderBottom: "1px solid #f0f0f0" }}>
            <p
              style={{
                fontSize: "1.05rem",
                fontWeight: 700,
                color: "#00305e",
                lineHeight: 1.5,
                margin: 0,
                cursor: taskDesc ? "help" : "default",
              }}
              onMouseEnter={() => setShowTaskTooltip(true)}
              onMouseLeave={() => setShowTaskTooltip(false)}
            >
              {taskLabel}
            </p>

            {showTaskTooltip && taskDesc && (
              <div style={{
                position: "absolute",
                top: "calc(100% + 0.5rem)",
                left: 0,
                right: 0,
                zIndex: 100,
                backgroundColor: "#00305e",
                color: "white",
                padding: "0.875rem 1rem",
                borderRadius: "0.5rem",
                fontSize: "0.8rem",
                lineHeight: 1.6,
                boxShadow: "0 8px 24px rgba(0,0,0,0.15)",
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

        {/* Answer section */}
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
                  <div style={{
                    width: "1.1rem",
                    height: "1.1rem",
                    borderRadius: "50%",
                    border: `2px solid ${isSelected ? "#3c5f90" : "#adb3b4"}`,
                    backgroundColor: isSelected ? "#3c5f90" : "transparent",
                    flexShrink: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
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

          <button type="submit" disabled={submitting} style={submitBtnStyle}>
            {submitting ? "Saving…" : isLastTask ? "Finish Experiment" : "Submit & Next →"}
          </button>
        </form>
      </div>
    </aside>
  );
};

export default TaskAnswerPanel;