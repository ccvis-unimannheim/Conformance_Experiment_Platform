"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";

import TaskVisualizationPanel from "../../components/Task/TaskVisualizationPanel";
import TaskAnswerPanel from "../../components/Task/TaskAnswerPanel";
import { UITrackingProvider } from "../../utils/usertracking";

import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";

// Step counter is fully dynamic — derived from tasks loaded from DB


// ---------------------------------------------------------------------------
// Skeleton placeholder — shown while data is loading
// ---------------------------------------------------------------------------
function LoadingSkeleton() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(12, minmax(0,1fr))", gap: "2rem", alignItems: "start" }}>
      {/* Visualization skeleton */}
      <section style={{ gridColumn: "1 / span 8" }}>
        <div style={{ backgroundColor: "white", borderRadius: "0.75rem", padding: "2.5rem", boxShadow: "0 4px 16px rgba(45,52,53,0.06)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "2.5rem" }}>
            <div style={{ height: "0.75rem", width: "5rem", backgroundColor: "#e5e7eb", borderRadius: "0.25rem" }} />
            <div style={{ display: "flex", gap: "1rem" }}>
              <div style={{ height: "0.75rem", width: "6rem", backgroundColor: "#e5e7eb", borderRadius: "0.25rem" }} />
              <div style={{ height: "0.75rem", width: "7rem", backgroundColor: "#e5e7eb", borderRadius: "0.25rem" }} />
            </div>
          </div>
          <div style={{ height: "400px", backgroundColor: "#f3f4f6", borderRadius: "0.5rem", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <span style={{ color: "#9ca3af", fontSize: "0.875rem", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>
              Loading visualization…
            </span>
          </div>
        </div>
      </section>

      {/* Answer skeleton */}
      <aside style={{ gridColumn: "span 4", display: "flex", flexDirection: "column", gap: "1.5rem" }}>
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
        <div style={{ padding: "1.5rem", borderLeft: "2px solid #e5e7eb" }}>
          <div style={{ height: "0.75rem", backgroundColor: "#e5e7eb", borderRadius: "0.25rem", marginBottom: "0.5rem" }} />
          <div style={{ height: "0.75rem", backgroundColor: "#e5e7eb", borderRadius: "0.25rem", width: "83%" }} />
        </div>
      </aside>
    </div>
  );
}

// ---------------------------------------------------------------------------
// TaskExecutionPage
// ---------------------------------------------------------------------------
export default function TaskExecutionPage() {
  const [tasks, setTasks] = useState([]);
  const [currentTaskIndex, setCurrentTaskIndex] = useState(0);
  const [svgUrl, setSvgUrl] = useState(null);
  const [loadingTasks, setLoadingTasks] = useState(true);
  const [loadingSvg, setLoadingSvg] = useState(false);

  // ── Fetch task list on mount ──────────────────────────────────────
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const response = await fetch(
          "https://pm-vis.uni-mannheim.de/api/survey/questionnaire",
          { method: "GET", credentials: "include" }
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        setTasks(data);
      } catch (error) {
        console.error("Error fetching tasks:", error.message);
      } finally {
        setLoadingTasks(false);
      }
    };
    fetchTasks();
  }, []);

  // ── Fetch SVG for the current task ───────────────────────────────
  useEffect(() => {
    if (!tasks[currentTaskIndex]) return;

    let objectUrl = null;
    setLoadingSvg(true);
    setSvgUrl(null);

    const fetchSvg = async () => {
      try {
        const taskId = tasks[currentTaskIndex].id ?? currentTaskIndex + 1;
        const response = await fetch(
          `https://pm-vis.uni-mannheim.de/api/vis/${taskId}`,
          { method: "GET", credentials: "include" }
        );
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
  }, [currentTaskIndex, tasks]);

  const handleAnswerSubmit = () => setCurrentTaskIndex((prev) => prev + 1);

  const currentTask = tasks[currentTaskIndex];
  const taskOptions = currentTask?.options
    ? currentTask.options.map((opt) => ({ label: opt, value: opt }))
    : [];

  // Idiom name comes from the task data (set by admin) — e.g. "Bar Chart", "Flow Chart"
  const idiom = currentTask?.idiom ?? currentTask?.chart_type ?? null;

  // Dynamic step counter — based on actual number of tasks from DB
  const totalTasks = tasks.length;
  const currentStep = currentTaskIndex + 1;
  const progressPercent = totalTasks > 0 ? (currentStep / totalTasks) * 100 : 0;

  // Show skeleton only during the initial load
  const showSkeleton = loadingTasks;

  // ── Render ───────────────────────────────────────────────────────
  return (
    <UITrackingProvider>
      <div style={{ backgroundColor: "#f9f9f9", color: "#2d3435", minHeight: "100vh", display: "flex", flexDirection: "column" }}>

        {/* ── Nav Bar ────────────────────────────────────────────── */}
        <nav style={{
          backgroundColor: "rgba(249,249,249,0.85)",
          backdropFilter: "blur(16px)",
          position: "fixed", top: 0, zIndex: 50, width: "100%",
          borderBottom: "1px solid rgba(173,179,180,0.15)"
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "1rem 2rem", maxWidth: "1440px", margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Image priority src={ProjectLogo} width={100} height={40} alt="ProVi Logo" style={{ objectFit: "contain" }} />
              <Image priority src={UniLogo} width={160} height={40} alt="University of Mannheim Logo" style={{ objectFit: "contain" }} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
              {totalTasks > 0 && (
                <span style={{ fontSize: "10px", fontWeight: 700, color: "#5a6061", textTransform: "uppercase", letterSpacing: "0.1em" }}>
                  Task {currentStep} of {totalTasks}
                </span>
              )}
              <span style={{ color: "#3c5f90", fontWeight: 700, fontSize: "0.875rem" }}>
                Task Execution
              </span>
              <div style={{ width: "4rem", height: "6px", backgroundColor: "#ebeeef", borderRadius: "9999px", overflow: "hidden" }}>
                <div style={{ width: `${progressPercent}%`, height: "100%", backgroundColor: "#3c5f90" }} />
              </div>
            </div>
          </div>
        </nav>

        {/* ── Main Content ─────────────────────────────────────── */}
        <main style={{ flexGrow: 1, paddingTop: "6rem", paddingBottom: "3rem", paddingLeft: "2rem", paddingRight: "2rem", maxWidth: "1440px", margin: "0 auto", width: "100%" }}>

          {/* Header — skeleton while loading, real data when available, placeholder label when no data */}
          <header style={{ marginBottom: "3rem" }}>
            {showSkeleton ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ height: "2.5rem", width: "50%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
                <div style={{ height: "1.5rem", width: "70%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
              </div>
            ) : currentTask ? (
              <>
                <h1 style={{ fontSize: "2.25rem", fontWeight: 900, color: "#00305e", letterSpacing: "-0.025em", marginBottom: "0.75rem" }}>
                  Task {currentTaskIndex + 1}: {currentTask.title}
                </h1>
                <p style={{ color: "#5a6061", maxWidth: "42rem", lineHeight: 1.6, fontSize: "1.25rem", fontWeight: 700 }}>
                  {currentTask.question_text}
                </p>
              </>
            ) : (
              /* Placeholder header when backend not connected */
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ height: "2.5rem", width: "50%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
                <div style={{ height: "1.5rem", width: "70%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
              </div>
            )}
          </header>

          {/* Two-column area — always rendered, panels handle their own placeholder state */}
          {showSkeleton ? (
            <LoadingSkeleton />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(12, minmax(0,1fr))", gap: "2rem", alignItems: "start" }}>
              <TaskVisualizationPanel
                idiom={idiom}
                svgUrl={svgUrl}
                taskNumber={currentTaskIndex + 1}
                loadingSvg={loadingSvg}
              />
              <TaskAnswerPanel
                options={taskOptions}
                taskId={currentTask?.id ?? currentTaskIndex + 1}
                totalTasks={tasks.length}
                currentTaskIndex={currentTaskIndex}
                onAnswerSubmit={handleAnswerSubmit}
              />
            </div>
          )}
        </main>
      </div>
    </UITrackingProvider>
  );
}
