"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../components/Admin/Toast";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1234";

const ALL_TASKS = [
  {
    task_key: "T-01",
    label: "What is the overall degree of conformance between an event log and a set of guidelines?",
    description: "Assess the overall conformance rate of the entire event log against the process model.",
    answer_type: "numeric",
  },
  {
    task_key: "T-02",
    label: "Where exactly does the process execution differ from the guideline? What does the violating behavior look like?",
    description: "Pinpoint specific violations in traces against the expected model.",
    answer_type: "single_choice",
  },
  {
    task_key: "T-03",
    label: "What type of guideline violations happen in different traces? How often do they happen?",
    description: "Classify violation types and quantify their occurrences across traces.",
    answer_type: "multiple_choice",
  },
  {
    task_key: "T-04",
    label: "What control-flow, data, resource, or time attributes of events, traces, or event logs lead to guideline violations?",
    description: "Identify potential root causes of non-conformance.",
    answer_type: "single_choice",
  },
  {
    task_key: "T-05",
    label: "Which percentage of traces in the event log fall into which conformance category?",
    description: "Group traces by conformance ranges and determine their distribution.",
    answer_type: "single_choice",
  },
  {
    task_key: "T-06",
    label: "Do cases with a higher degree of conformance lead to a higher probability of a positive process outcome?",
    description: "Explore the relationship between conformance and process outcomes.",
    answer_type: "single_choice",
  },
];

function getTaskId(task) {
  return task._id || task.id;
}

export default function TaskSelectionPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [allTasks, setAllTasks] = useState([]);
  const [loadError, setLoadError] = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);
  const [isSeeding, setIsSeeding] = useState(false);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [newTaskKey, setNewTaskKey] = useState("");
  const [newTaskLabel, setNewTaskLabel] = useState("");
  const [newTaskDesc, setNewTaskDesc] = useState("");
  const [newTaskAnswerType, setNewTaskAnswerType] = useState("single_choice");
  const [modalError, setModalError] = useState("");

  // Toast state
  const [toast, setToast] = useState({ visible: false, message: "", isError: false });

  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);

  const hideToast = useCallback(() => {
    setToast((t) => ({ ...t, visible: false }));
  }, []);

  async function fetchTasks() {
    setLoadError(null);
    try {
      const res = await fetch(`${BASE_URL}/admin/tasks`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAllTasks(await res.json());
    } catch (e) {
      setLoadError(e.message);
    }
  }

  useEffect(() => {
    fetchTasks();
  }, []);

  function toggleTask(id) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  }

  async function seedTasks() {
    setIsSeeding(true);
    let existingKeys = new Set();
    try {
      const res = await fetch(`${BASE_URL}/admin/tasks`);
      if (res.ok) {
        const existing = await res.json();
        existing.forEach((t) => existingKeys.add(t.task_key));
      }
    } catch {}

    let created = 0,
      skipped = 0;
    for (const t of ALL_TASKS) {
      if (existingKeys.has(t.task_key)) { skipped++; continue; }
      try {
        const res = await fetch(`${BASE_URL}/admin/tasks`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ _id: crypto.randomUUID(), ...t }),
        });
        if (res.ok) created++;
      } catch {}
    }

    showToast(
      skipped === ALL_TASKS.length
        ? "All tasks already exist."
        : `Seeded ${created} task(s). ${skipped} already existed.`
    );
    await fetchTasks();
    setIsSeeding(false);
  }

  async function submitCreateTask() {
    if (!newTaskKey.trim() || !newTaskLabel.trim()) {
      setModalError("Task Key and Label are required.");
      return;
    }
    setModalError("");
    const payload = {
      _id: crypto.randomUUID(),
      task_key: newTaskKey.trim(),
      label: newTaskLabel.trim(),
      description: newTaskDesc.trim(),
      answer_type: newTaskAnswerType,
    };
    try {
      const res = await fetch(`${BASE_URL}/admin/tasks`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      setModalOpen(false);
      setNewTaskKey("");
      setNewTaskLabel("");
      setNewTaskDesc("");
      setNewTaskAnswerType("single_choice");
      showToast("Task created successfully!");
      await fetchTasks();
    } catch (e) {
      setModalError(`Error: ${e.message}`);
    }
  }

  async function goToStep2() {
    if (selectedIds.length === 0) {
      showToast("Please select at least one task before continuing.", true);
      return;
    }
    if (!experimentId) {
      showToast("No experiment found. Please go back and create an experiment first.", true);
      return;
    }
    const taskConfigs = selectedIds.map((taskId) => ({
      task_id: taskId,
      idiom_id: "",
      dataset_id: "",
      question_ids: [],
    }));
    try {
      const res = await fetch(`${BASE_URL}/admin/experiments/${encodeURIComponent(experimentId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_configs: taskConfigs }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e) {
      showToast(`Failed to save tasks: ${e.message}`, true);
      return;
    }
    router.push(`/admin/idiom-selection?experiment_id=${encodeURIComponent(experimentId)}`);
  }

  const selectedTasks = allTasks.filter((t) => selectedIds.includes(getTaskId(t)));

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        {/* Page heading */}
        <div>
          <h1 className="font-h1 text-h1 text-primary mb-2">Create New Experiment</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Select the conformance checking tasks you want to include. You can also add new tasks
            directly to the database.
          </p>
        </div>

        <div className="grid grid-cols-12 gap-6 items-start">
          {/* Left column: task list */}
          <div className="col-span-8 flex flex-col gap-4">
            {/* Toolbar */}
            <div className="flex justify-between items-center">
              <h2 className="text-base font-semibold text-on-surface">
                Available Tasks
                {allTasks.length > 0 && (
                  <span className="ml-2 text-xs text-on-surface-variant font-normal">
                    ({allTasks.length})
                  </span>
                )}
              </h2>
              <div className="flex gap-2">
                <button
                  onClick={seedTasks}
                  disabled={isSeeding}
                  className="text-xs border border-border-subtle px-3 py-1.5 rounded text-on-surface-variant hover:bg-surface-container transition-colors flex items-center gap-1 disabled:opacity-60"
                >
                  <span className="material-symbols-outlined text-sm">download</span>
                  {isSeeding ? "Seeding…" : "Seed Tasks"}
                </button>
                <button
                  onClick={() => setModalOpen(true)}
                  className="text-xs bg-primary text-white px-4 py-1.5 rounded font-semibold hover:bg-primary-container transition-colors flex items-center gap-1"
                >
                  <span className="material-symbols-outlined text-sm">add</span> Add Task
                </button>
              </div>
            </div>

            {/* Task cards */}
            <div className="flex flex-col gap-3">
              {loadError ? (
                <div className="text-sm text-error bg-error-container px-4 py-3 rounded-lg">
                  Could not load tasks from backend (<strong>{BASE_URL}</strong>). Make sure the
                  backend is running and CORS is configured.
                  <br />
                  <span className="text-xs opacity-70">{loadError}</span>
                </div>
              ) : allTasks.length === 0 ? (
                <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
                  <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                    inbox
                  </span>
                  No tasks in database yet.
                  <br />
                  <span className="text-xs mt-1 block">
                    Click <strong>Seed Tasks</strong> to add the 6 standard CC tasks.
                  </span>
                </div>
              ) : (
                allTasks.map((task) => {
                  const id = getTaskId(task);
                  const selected = selectedIds.includes(id);
                  return (
                    <div
                      key={id}
                      onClick={() => toggleTask(id)}
                      className={`cursor-pointer rounded-lg border-2 p-4 transition-all select-none
                        ${selected
                          ? "border-primary bg-blue-50 shadow-sm"
                          : "border-border-subtle bg-white hover:border-primary/40 hover:bg-surface-container-low"
                        }`}
                    >
                      <div className="flex items-start gap-3">
                        <span
                          className={`material-symbols-outlined text-xl mt-0.5 flex-shrink-0 transition-colors
                            ${selected ? "text-primary icon-filled" : "text-outline-variant"}`}
                        >
                          {selected ? "check_circle" : "radio_button_unchecked"}
                        </span>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1 flex-wrap">
                            <span className="text-xs font-bold uppercase tracking-wider bg-blue-100 text-primary px-1.5 py-0.5 rounded">
                              {task.task_key}
                            </span>
                            <span className="text-xs text-on-surface-variant">
                              {task.answer_type}
                            </span>
                          </div>
                          <p className="text-sm font-semibold text-on-surface leading-snug">
                            {task.label}
                          </p>
                          {task.description && (
                            <p className="text-xs text-on-surface-variant mt-1 leading-relaxed">
                              {task.description}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* Right column: selected tasks */}
          <div className="col-span-4">
            <div className="bg-white border border-border-subtle rounded-lg p-5 flex flex-col gap-3 sticky top-6">
              <div className="flex items-center justify-between border-b border-border-subtle pb-3">
                <h2 className="text-base font-semibold text-on-surface">Selected Tasks</h2>
                <span className="bg-primary text-white text-xs font-bold px-2 py-0.5 rounded-full min-w-[24px] text-center">
                  {selectedIds.length}
                </span>
              </div>
              <div className="flex flex-col gap-2 min-h-[100px]">
                {selectedTasks.length === 0 ? (
                  <div className="flex flex-col items-center justify-center h-20 text-center text-on-surface-variant text-xs border-2 border-dashed border-outline-variant rounded">
                    <span className="material-symbols-outlined text-2xl mb-1 text-outline-variant">
                      list_alt
                    </span>
                    No tasks selected yet
                  </div>
                ) : (
                  selectedTasks.map((t) => (
                    <div
                      key={getTaskId(t)}
                      className="flex items-start gap-2 p-2 bg-surface-container-low rounded"
                    >
                      <span className="text-xs font-bold bg-primary text-white px-1.5 py-0.5 rounded flex-shrink-0 mt-0.5">
                        {t.task_key}
                      </span>
                      <span className="text-xs text-on-surface flex-1 leading-snug line-clamp-2">
                        {t.label}
                      </span>
                      <button
                        onClick={(e) => { e.stopPropagation(); toggleTask(getTaskId(t)); }}
                        className="text-on-surface-variant hover:text-error flex-shrink-0 transition-colors ml-1"
                      >
                        <span className="material-symbols-outlined text-sm">close</span>
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      </main>

      {/* Footer action bar */}
      <div className="border-t border-border-subtle bg-white sticky bottom-0">
        <div className="max-w-[1140px] mx-auto px-8 py-4 flex justify-between items-center">
          <Link
            href="/admin/experiments/new"
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <div className="flex items-center gap-4">
            <button
              onClick={goToStep2}
              className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95"
            >
              Next
              <span className="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </div>
        </div>
      </div>

      {/* Create Task Modal */}
      {modalOpen && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setModalOpen(false); }}
        >
          <div className="bg-white rounded-xl p-6 w-full max-w-[500px] shadow-xl flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-on-surface">Create New Task</h3>
              <button onClick={() => setModalOpen(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                  Task Key *
                </label>
                <input
                  type="text"
                  value={newTaskKey}
                  onChange={(e) => setNewTaskKey(e.target.value)}
                  placeholder="e.g. T-01"
                  className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>
              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                  Label / Question *
                </label>
                <textarea
                  rows={3}
                  value={newTaskLabel}
                  onChange={(e) => setNewTaskLabel(e.target.value)}
                  placeholder="What is the overall degree of conformance…"
                  className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
                />
              </div>
              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                  Description
                </label>
                <textarea
                  rows={2}
                  value={newTaskDesc}
                  onChange={(e) => setNewTaskDesc(e.target.value)}
                  placeholder="Brief explanation of the task…"
                  className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
                />
              </div>
              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                  Answer Type
                </label>
                <select
                  value={newTaskAnswerType}
                  onChange={(e) => setNewTaskAnswerType(e.target.value)}
                  className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
                >
                  <option value="single_choice">Single Choice</option>
                  <option value="multiple_choice">Multiple Choice</option>
                  <option value="numeric">Numeric</option>
                  <option value="text">Free Text</option>
                </select>
              </div>
            </div>
            {modalError && (
              <div className="text-error text-xs bg-error-container px-3 py-2 rounded">
                {modalError}
              </div>
            )}
            <div className="flex gap-2 justify-end pt-1">
              <button
                onClick={() => setModalOpen(false)}
                className="text-sm text-on-surface-variant border border-border-subtle px-4 py-2 rounded hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={submitCreateTask}
                className="text-sm bg-primary text-white px-5 py-2 rounded font-semibold hover:bg-primary-container transition-colors"
              >
                Create Task
              </button>
            </div>
          </div>
        </div>
      )}

      <Toast
        message={toast.message}
        isError={toast.isError}
        visible={toast.visible}
        onHide={hideToast}
      />
    </div>
  );
}
