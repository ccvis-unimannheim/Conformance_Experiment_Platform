"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";

import TaskVisualizationPanel from "../../components/Task/TaskVisualizationPanel";
import TaskAnswerPanel from "../../components/Task/TaskAnswerPanel";
import { UITrackingProvider } from "../../utils/usertracking";

import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";

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
        setTaskGroups(groupTrialsByTask(trialsData.trials ?? []));

      } catch (error) {
        console.error("Error fetching tasks:", error.message);
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
          boxSizing: "border-box",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "0 2rem", maxWidth: "56rem", margin: "0 auto" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
              <Image priority src={ProjectLogo} width={90} height={36} alt="ProVi Logo" style={{ objectFit: "contain" }} />
              <Image priority src={UniLogo} width={140} height={36} alt="University of Mannheim Logo" style={{ objectFit: "contain" }} />
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

        <main style={{ flexGrow: 1, paddingTop: "5.5rem", paddingBottom: "2rem", paddingLeft: "1.5rem", paddingRight: "1.5rem", maxWidth: "1800px", margin: "0 auto", width: "100%" }}>
          {showSkeleton ? (
            <LoadingSkeleton />
          ) : (
            <div style={{ display: "grid", gridTemplateColumns: "1fr 440px", gap: "1.5rem", alignItems: "start" }}>
              <TaskVisualizationPanel
                svgUrl={svgUrl}
                taskNumber={currentStep}
                loadingSvg={loadingSvg}
              />
              <TaskAnswerPanel
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
              />
            </div>
          )}
        </main>
      </div>
    </UITrackingProvider>
  );
}