"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";

import TaskVisualizationPanel from "../../components/Task/TaskVisualizationPanel";
import TaskAnswerPanel from "../../components/Task/TaskAnswerPanel";
import { UITrackingProvider } from "../../utils/usertracking";

import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";


// Group flat trials array by task_key, preserving order
function groupTrialsByTask(trials) {
  const groups = [];
  const seen = new Map();

  for (const trial of trials) {
    if (!seen.has(trial.task_key)) {
      seen.set(trial.task_key, groups.length);
      groups.push({
        task_key:    trial.task_key,
        task_id:     trial.task_id,
        task_label:  trial.task_label,
        answer_type: trial.answer_type,
        idioms: [],
      });
    }
    const idx = seen.get(trial.task_key);
    groups[idx].idioms.push({
      idiom_id:      trial.idiom_id,
      idiom_key:     trial.idiom_key,
      idiom_label:   trial.idiom_label,
      dataset_id:    trial.dataset_id,
      svg_available: trial.svg_available,
    });
  }
  return groups;
}

// Skeleton placeholder
function LoadingSkeleton() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(12, minmax(0,1fr))", gap: "2rem", alignItems: "start" }}>
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
      </aside>
    </div>
  );
}

// TaskExecutionPage
export default function TaskExecutionPage() {
  const [taskGroups, setTaskGroups]               = useState([]);
  const [currentGroupIndex, setCurrentGroupIndex] = useState(0);
  const [currentIdiomIndex, setCurrentIdiomIndex] = useState(0);
  const [svgUrl, setSvgUrl]                       = useState(null);
  const [loadingTasks, setLoadingTasks]           = useState(true);
  const [loadingSvg, setLoadingSvg]               = useState(false);

  // ── Fetch & group trials on mount 
  useEffect(() => {
    const fetchTasks = async () => {
      try {
        const response = await fetch(
          `/api/participant/experiment/active`,
          { method: "GET", credentials: "include" }
        );
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        setTaskGroups(groupTrialsByTask(data.trials ?? []));
      } catch (error) {
        console.error("Error fetching tasks:", error.message);
      } finally {
        setLoadingTasks(false);
      }
    };
    fetchTasks();
  }, []);

  // ── Fetch SVG when group or idiom index changes
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
        const response = await fetch(
          `/api/participant/vis/${idiom.dataset_id}/${group.task_id}/${idiom.idiom_id}`,
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
  }, [currentGroupIndex, currentIdiomIndex, taskGroups]);

  // ── Advance: idiom-first, then task 
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

  // ── Derived display values 
  const currentGroup = taskGroups[currentGroupIndex];
  const currentIdiom = currentGroup?.idioms[currentIdiomIndex];

  const totalTasks      = taskGroups.length;
  const currentStep     = currentGroupIndex + 1;
  const progressPercent = totalTasks > 0 ? (currentStep / totalTasks) * 100 : 0;

  const flatTrialIndex = taskGroups
    .slice(0, currentGroupIndex)
    .reduce((sum, g) => sum + g.idioms.length, 0) + currentIdiomIndex;
  const totalTrials = taskGroups.reduce((sum, g) => sum + g.idioms.length, 0);

  const showSkeleton = loadingTasks;

  return (
    <UITrackingProvider>
      <div style={{ backgroundColor: "#f9f9f9", color: "#2d3435", minHeight: "100vh", display: "flex", flexDirection: "column" }}>

        {/* ── Nav Bar */}
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

        {/* ── Main Content */}
        <main style={{ flexGrow: 1, paddingTop: "6rem", paddingBottom: "3rem", paddingLeft: "2rem", paddingRight: "2rem", maxWidth: "1440px", margin: "0 auto", width: "100%" }}>

          <header style={{ marginBottom: "3rem" }}>
            {showSkeleton ? (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ height: "2.5rem", width: "50%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
                <div style={{ height: "1.5rem", width: "70%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
              </div>
            ) : currentGroup ? (
              <>
                <h1 style={{ fontSize: "2.25rem", fontWeight: 900, color: "#00305e", letterSpacing: "-0.025em", marginBottom: "0.75rem" }}>
                  Task {currentStep}: {currentGroup.task_label}
                </h1>
                <p style={{ color: "#5a6061", maxWidth: "42rem", lineHeight: 1.6, fontSize: "1.25rem", fontWeight: 700 }}>
                  {currentIdiom?.idiom_label ?? ""}
                </p>
              </>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <div style={{ height: "2.5rem", width: "50%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
                <div style={{ height: "1.5rem", width: "70%", backgroundColor: "#e5e7eb", borderRadius: "0.5rem" }} />
              </div>
            )}
          </header>

          {showSkeleton ? (
            <LoadingSkeleton />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "repeat(12, minmax(0,1fr))", gap: "2rem", alignItems: "start" }}>
              <TaskVisualizationPanel
                idiom={currentIdiom?.idiom_label ?? null}
                svgUrl={svgUrl}
                taskNumber={currentStep}
                loadingSvg={loadingSvg}
              />
              <TaskAnswerPanel
                options={[]}
                taskId={currentGroup?.task_id ?? currentStep}
                idiomId={currentIdiom?.idiom_id ?? ""}
                datasetId={currentIdiom?.dataset_id ?? ""}
                trialIndex={flatTrialIndex}
                presentationOrder={flatTrialIndex}
                totalTasks={totalTrials}
                currentTaskIndex={flatTrialIndex}
                onAnswerSubmit={handleAnswerSubmit}
              />
            </div>
          )}
        </main>
      </div>
    </UITrackingProvider>
  );
}