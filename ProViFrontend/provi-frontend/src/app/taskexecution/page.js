"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";

import TaskVisualizationPanel from "../../components/Task/TaskVisualizationPanel";
import TaskAnswerPanel from "../../components/Task/TaskAnswerPanel";
import { UITrackingProvider } from "../../utils/usertracking";

import HeaderLogos from "../../components/General/HeaderLogos";

function groupTrialsByTask(trials) {
  const groups = [];
  const seen = new Map();

  for (const trial of trials) {
    if (!seen.has(trial.task_key)) {
      seen.set(trial.task_key, groups.length);
      groups.push({
        task_key:      trial.task_key,
        task_id:       trial.task_id,
        task_label:    trial.task_label,
        answer_type:   trial.answer_type,
        answer_format: trial.answer_format,
        options:       trial.options ?? [],
        param_hints:   trial.param_hints ?? [],
        idioms: [],
      });
    }
    const idx = seen.get(trial.task_key);
    groups[idx].idioms.push({
      idiom_id:      trial.idiom_id,
      idiom_key:     trial.idiom_key,
      idiom_label:   trial.idiom_label,
      dataset_id:    trial.dataset_id,
      trial_index:   trial.trial_index,
      svg_available: trial.svg_available,
    });
  }
  return groups;
}

function FitnessHelpButton({ experimentId }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  const openCountRef = useRef(0);
  const openTimeRef  = useRef(null);

  // Send one open→close event to the backend
  async function sendEvent(openIndex, dwellMs) {
    try {
      await fetch("/api/uitracking/fitness-help", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          experiment_id:   experimentId ?? null,
          open_index:      openIndex,
          dwell_ms:        dwellMs,
          insert_datetime: new Date().toISOString(),
        }),
      });
    } catch (e) {
      console.warn("Fitness help tracking failed:", e.message);
    }
  }

  // Track open / close transitions
  useEffect(() => {
    if (open) {
      openCountRef.current += 1;
      openTimeRef.current = Date.now();
    } else if (openTimeRef.current !== null) {
      const dwellMs = Date.now() - openTimeRef.current;
      openTimeRef.current = null;
      sendEvent(openCountRef.current, dwellMs);
    }
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function handleClick(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [open]);

  return (
    <div ref={ref} style={{ position: "relative", display: "inline-flex", alignItems: "center" }}>
      <button
        onClick={() => setOpen((v) => !v)}
        aria-label="What is fitness?"
        style={{
          width: "20px", height: "20px", borderRadius: "50%",
          backgroundColor: "#ebeeef", border: "1.5px solid #adb3b4",
          color: "#5a6061", fontSize: "11px", fontWeight: 700,
          cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
          transition: "background-color 0.15s, color 0.15s",
          flexShrink: 0,
        }}
        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = "#00305e"; e.currentTarget.style.color = "#ffffff"; e.currentTarget.style.borderColor = "#00305e"; }}
        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "#ebeeef"; e.currentTarget.style.color = "#5a6061"; e.currentTarget.style.borderColor = "#adb3b4"; }}
      >
        ?
      </button>
      {open && (
        <div style={{
          position: "absolute", right: 0, top: "calc(100% + 8px)", zIndex: 100,
          width: "340px", backgroundColor: "#ffffff",
          border: "1px solid #e4e9ea", borderRadius: "12px",
          boxShadow: "0 8px 24px rgba(45,52,53,0.12)", padding: "1.125rem",
        }}>
          <p style={{ fontSize: "10px", fontWeight: 700, color: "#5a6061", textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.625rem" }}>
            What is Fitness?
          </p>
          <p style={{ fontSize: "0.8125rem", color: "#2d3435", lineHeight: 1.7, marginBottom: "0.625rem" }}>
            <strong>Fitness</strong> measures the ability of a model to explain the execution of a
            process as recorded in an event log. It captures the fraction of the log&apos;s
            behaviour that the model also allows:
          </p>
          {/* Formula */}
          <div style={{
            backgroundColor: "#f2f4f4", borderRadius: "6px",
            padding: "0.5rem 0.75rem", textAlign: "center",
            fontFamily: "Georgia, serif", fontSize: "0.875rem",
            color: "#2d3435", marginBottom: "0.625rem",
          }}>
            fitness = |L ∩ M| / |L|
          </div>
          <p style={{ fontSize: "0.8125rem", color: "#2d3435", lineHeight: 1.7, marginBottom: "0.625rem" }}>
            A fitness of <strong>1.0</strong> means every recorded trace is fully covered by
            the model; <strong>0.0</strong> means no recorded behaviour matches the model at all.
          </p>
          {/* Citation */}
          <p style={{ fontSize: "0.7rem", color: "#757c7d", lineHeight: 1.5, borderTop: "1px solid #e4e9ea", paddingTop: "0.5rem", margin: 0 }}>
            Carmona et al. (2018). <em>Conformance Checking</em>. Springer, §3.2.
          </p>
        </div>
      )}
    </div>
  );
}

function LoadingSkeleton() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 440px", gap: "1.5rem", alignItems: "start" }}>
      <section>
        <div style={{ backgroundColor: "white", borderRadius: "0.75rem", padding: "2.5rem", boxShadow: "0 4px 16px rgba(45,52,53,0.06)" }}>
          <div style={{ height: "calc(100vh - 12rem)", minHeight: "460px", backgroundColor: "#f3f4f6", borderRadius: "0.5rem", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "#9ca3af", fontSize: "0.875rem", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Loading visualization…
            </span>
          </div>
        </div>
      </section>
      <aside style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
        <div style={{ backgroundColor: "#f2f4f4", borderRadius: "0.75rem", padding: "2rem" }}>
          <div style={{ height: "0.75rem", width: "8rem", backgroundColor: "#d1d5db", borderRadius: "0.25rem", marginBottom: "2rem" }} />
          {[1, 2, 3, 4].map((i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: "1rem", padding: "1rem", backgroundColor: "white", borderRadius: "0.5rem", marginBottom: "1rem" }}>
              <div style={{ width: "1rem", height: "1rem", borderRadius: "50%", backgroundColor: "#e5e7eb", flexShrink: 0 }} />
              <div style={{ height: "0.75rem", backgroundColor: "#e5e7eb", borderRadius: "0.25rem", width: "75%" }} />
            </div>
          ))}
          <div style={{ height: "3rem", backgroundColor: "#d1d5db", borderRadius: "0.5rem", marginTop: "2rem" }} />
        </div>
      </aside>
    </div>
  );
}

export default function TaskExecutionPage() {
  const [taskGroups, setTaskGroups]               = useState([]);
  const [experimentId, setExperimentId]           = useState(null);
  const [currentGroupIndex, setCurrentGroupIndex] = useState(0);
  const [currentIdiomIndex, setCurrentIdiomIndex] = useState(0);
  const [svgUrl, setSvgUrl]                       = useState(null);
  const [loadingTasks, setLoadingTasks]           = useState(true);
  const [loadError, setLoadError]                 = useState(null);
  const [loadingSvg, setLoadingSvg]               = useState(false);

  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const expRes = await fetch("/api/participant/experiment/active", {
          method: "GET",
          credentials: "include",
        });
        if (!expRes.ok) throw new Error(`HTTP ${expRes.status}`);
        const expData = await expRes.json();
        const expId = expData.experiment_id;
        setExperimentId(expId);

        const assignRes = await fetch("/api/participant/assignment", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          credentials: "include",
          body: JSON.stringify({ experiment_id: expId }),
        });
        if (!assignRes.ok) throw new Error(`Assignment failed: HTTP ${assignRes.status}`);

        const trialsRes = await fetch(`/api/participant/assignment/${expId}/trials`, {
          method: "GET",
          credentials: "include",
        });
        if (!trialsRes.ok) throw new Error(`Trials fetch failed: HTTP ${trialsRes.status}`);
        const trialsData = await trialsRes.json();
        const groups = groupTrialsByTask(trialsData.trials ?? []);
        setTaskGroups(groups);
        if (groups.length === 0) {
          setLoadError("This experiment has no tasks to display. It may not have been generated or published correctly.");
        }

      } catch (error) {
        console.error("Error fetching tasks:", error.message);
        setLoadError(`Could not load the experiment: ${error.message}`);
      } finally {
        setLoadingTasks(false);
      }
    };
    fetchTasks();
  }, []);

  useEffect(() => {
    const group = taskGroups[currentGroupIndex];
    if (!group) return;
    const idiom = group.idioms[currentIdiomIndex];
    if (!idiom) return;

    let objectUrl = null;
    setLoadingSvg(true);
    setSvgUrl(null);

    const fetchSvg = async () => {
      try {
        const visUrl = `/api/participant/vis/${idiom.dataset_id}/${group.task_id}/${idiom.idiom_id}` +
          (experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : "");
        const response = await fetch(visUrl, { method: "GET", credentials: "include" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        setSvgUrl(objectUrl);
      } catch (error) {
        console.warn("SVG fetch failed — placeholder will be shown:", error.message);
        setSvgUrl(null);
      } finally {
        setLoadingSvg(false);
      }
    };

    fetchSvg();
    return () => { if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [currentGroupIndex, currentIdiomIndex, taskGroups, experimentId]);

  const handleAnswerSubmit = () => {
    const group = taskGroups[currentGroupIndex];
    if (!group) return;
    if (currentIdiomIndex < group.idioms.length - 1) {
      setCurrentIdiomIndex((prev) => prev + 1);
    } else {
      setCurrentGroupIndex((prev) => prev + 1);
      setCurrentIdiomIndex(0);
    }
  };

  const handlePreviousIdiom = () => {
    if (currentIdiomIndex > 0) {
      setCurrentIdiomIndex((prev) => prev - 1);
    } else if (currentGroupIndex > 0) {
      const prevGroup = taskGroups[currentGroupIndex - 1];
      setCurrentGroupIndex((prev) => prev - 1);
      setCurrentIdiomIndex(prevGroup.idioms.length - 1);
    }
  };

  const isFirstIdiom = currentGroupIndex === 0 && currentIdiomIndex === 0;

  const currentGroup = taskGroups[currentGroupIndex];
  const currentIdiom = currentGroup?.idioms[currentIdiomIndex];

  const totalTasks      = taskGroups.length;
  const currentStep     = currentGroupIndex + 1;
  const progressPercent = totalTasks > 0 ? (currentStep / totalTasks) * 100 : 0;

  const currentTrialIndex = currentIdiom?.trial_index ?? 0;
  const totalTrials = taskGroups.reduce((sum, g) => sum + g.idioms.length, 0);

  // Linear position in the actual UI traversal order (not the shuffled trial_index from DB).
  // Used to correctly detect the last trial regardless of shuffle order.
  const linearTrialPosition =
    taskGroups.slice(0, currentGroupIndex).reduce((sum, g) => sum + g.idioms.length, 0) +
    currentIdiomIndex;

  const showSkeleton = loadingTasks;

  return (
    <UITrackingProvider>
      <div style={{ backgroundColor: "#f9f9f9", color: "#2d3435", minHeight: "100vh", display: "flex", flexDirection: "column" }}>

        <nav style={{
          backgroundColor: "#ffffff",
          position: "fixed", top: 0, zIndex: 50, width: "100%",
          borderBottom: "1px solid #e4e9ea",
          height: "4rem", display: "flex", alignItems: "center",
          boxSizing: "border-box", padding: "0 1.25rem",
        }}>
          <button
            onClick={() => { window.location.href = "/conformance-terms"; }}
            style={{
              display: "none", alignItems: "center", gap: "0.25rem",
              fontSize: "0.75rem", fontWeight: 500, color: "#5a6061",
              background: "none", border: "1px solid #adb3b4",
              borderRadius: "999px", padding: "0.25rem 0.75rem",
              cursor: "pointer", transition: "color 0.15s, border-color 0.15s",
              whiteSpace: "nowrap", flexShrink: 0,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.color = "#00305e"; e.currentTarget.style.borderColor = "#00305e"; }}
            onMouseLeave={(e) => { e.currentTarget.style.color = "#5a6061"; e.currentTarget.style.borderColor = "#adb3b4"; }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: "14px" }}>arrow_back</span>
            Key Concept
          </button>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flex: 1, padding: "0 1rem", maxWidth: "56rem", margin: "0 auto" }}>
            <HeaderLogos />
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              {totalTasks > 0 && (
                <span style={{ fontSize: "10px", fontWeight: 700, color: "#5a6061", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                  Task {currentStep} of {totalTasks}
                </span>
              )}
              <span style={{ color: "#3c5f90", fontWeight: 700, fontSize: "0.875rem" }}>
                Task Execution
              </span>
              <span style={{ display: "none" }}><FitnessHelpButton experimentId={experimentId} /></span>
              <div style={{ width: "4rem", height: "6px", backgroundColor: "#ebeeef", borderRadius: "9999px", overflow: "hidden" }}>
                <div style={{ width: `${progressPercent}%`, height: "100%", backgroundColor: "#3c5f90" }} />
              </div>
            </div>
          </div>
        </nav>

        <main style={{ flexGrow: 1, paddingTop: "5.5rem", paddingBottom: "2rem", paddingLeft: "1.5rem", paddingRight: "1.5rem", maxWidth: "1800px", margin: "0 auto", width: "100%" }}>
          {showSkeleton ? (
            <LoadingSkeleton />
          ) : (loadError || taskGroups.length === 0) ? (
            <div style={{
              maxWidth: "32rem", margin: "4rem auto", textAlign: "center",
              background: "white", border: "1px solid #e4e9ea", borderRadius: "12px",
              padding: "2.5rem 2rem", boxShadow: "0 2px 12px rgba(45,52,53,0.06)",
            }}>
              <div style={{ fontSize: "2rem", marginBottom: "0.75rem" }}>📭</div>
              <h2 style={{ fontSize: "1.05rem", fontWeight: 700, color: "#2d3435", marginBottom: "0.5rem" }}>
                No tasks to display
              </h2>
              <p style={{ fontSize: "0.875rem", color: "#5a6061", lineHeight: 1.6 }}>
                {loadError || "This experiment has no tasks to display."}
              </p>
            </div>
          ) : (
            <>
              {!isFirstIdiom && (
                <div style={{ marginBottom: "0.75rem", display: "none" }}>
                  <button
                    onClick={handlePreviousIdiom}
                    style={{
                      display: "flex", alignItems: "center", gap: "0.35rem",
                      padding: "0.35rem 0.75rem",
                      background: "white",
                      border: "1.5px solid #dde4e5",
                      borderRadius: "6px",
                      fontSize: "0.75rem", fontWeight: 600, color: "#5a6061",
                      cursor: "pointer",
                      boxShadow: "0 2px 6px rgba(45,52,53,0.08)",
                      transition: "border-color 0.15s, color 0.15s",
                    }}
                    onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#3c5f90"; e.currentTarget.style.color = "#3c5f90"; }}
                    onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#dde4e5"; e.currentTarget.style.color = "#5a6061"; }}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="15 18 9 12 15 6" />
                    </svg>
                    Previous Visualization
                  </button>
                </div>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 440px", gap: "1.5rem", alignItems: "start" }}>
              <TaskVisualizationPanel
                svgUrl={svgUrl}
                taskNumber={currentStep}
                loadingSvg={loadingSvg}
              />
              <TaskAnswerPanel
                key={linearTrialPosition}
                options={currentGroup?.options ?? []}
                answerType={currentGroup?.answer_type ?? "free_text"}
                answerFormat={currentGroup?.answer_format ?? "free-text"}
                taskLabel={currentGroup?.task_label ?? ""}
                experimentId={experimentId}
                taskId={currentGroup?.task_id ?? currentStep}
                taskKey={currentGroup?.task_key ?? ""}
                idiomId={currentIdiom?.idiom_id ?? ""}
                idiomKey={currentIdiom?.idiom_key ?? ""}
                datasetId={currentIdiom?.dataset_id ?? ""}
                trialIndex={currentTrialIndex}
                presentationOrder={currentTrialIndex}
                totalTasks={totalTrials}
                currentTaskIndex={linearTrialPosition}
                onAnswerSubmit={handleAnswerSubmit}
                paramHints={currentGroup?.param_hints ?? []}
              />
            </div>
            </>
          )}
        </main>
      </div>
    </UITrackingProvider>
  );
}