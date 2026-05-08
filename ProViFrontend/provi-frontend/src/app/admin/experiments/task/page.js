"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";

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

  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => {
    setToast((t) => ({ ...t, visible: false }));
  }, []);

  useEffect(() => {
    if (!experimentId) router.replace("/admin/experiments/new");
  }, [experimentId, router]);

  useEffect(() => {
    fetch("/api/admin/tasks")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setAllTasks)
      .catch((e) => setLoadError(e.message));
  }, []);

  function toggleTask(id) {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
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
      const res = await fetch(`/api/admin/experiments/${encodeURIComponent(experimentId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_configs: taskConfigs }),
      });
      if (!res.ok) throw new Error(await res.text());
    } catch (e) {
      showToast(`Failed to save tasks: ${e.message}`, true);
      return;
    }
    router.push(`/admin/experiments/idiom?experiment_id=${encodeURIComponent(experimentId)}`);
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
            </div>

            {/* Task cards */}
            <div className="flex flex-col gap-3">
              {loadError ? (
                <div className="text-sm text-error bg-error-container px-4 py-3 rounded-lg">
                  Could not load tasks from backend. Make sure the backend is running.
                  <br /><span className="text-xs opacity-70">{loadError}</span>
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
                          </div>
                          <p className="text-sm font-semibold text-on-surface leading-snug">
                            {task.label}
                          </p>
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

      <Toast
        message={toast.message}
        isError={toast.isError}
        visible={toast.visible}
        onHide={hideToast}
      />
    </div>
  );
}
