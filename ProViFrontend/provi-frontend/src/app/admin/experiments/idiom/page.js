"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";

function getId(obj) {
  return obj._id || obj.id;
}

function IdiomSelectionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [selectedTasks, setSelectedTasks] = useState([]);
  const [allIdioms, setAllIdioms] = useState([]);
  const [taskIdiomKeys, setTaskIdiomKeys] = useState({});
  const [taskIdiomMap, setTaskIdiomMap] = useState({});
  const [datasetIds, setDatasetIds] = useState([]);
  const [showSuccess, setShowSuccess] = useState(false);
  const [successDetail, setSuccessDetail] = useState("");


  const [expModalOpen, setExpModalOpen] = useState(false);
  const [experiments, setExperiments] = useState([]);

  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => setToast((t) => ({ ...t, visible: false })), []);

  useEffect(() => {
    if (!experimentId) {
      router.replace("/admin/experiments/task");
      return;
    }
    init();
  }, [experimentId]);

  async function init() {
    let taskIds = [];
    try {
      const res = await fetch(`/api/admin/experiments`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const exps = await res.json();
      const draft = exps.find((e) => getId(e) === experimentId);
      if (!draft) throw new Error("Draft experiment not found.");
      taskIds = draft.task_configs.map((tc) => tc.task_id);
      setDatasetIds(draft.dataset_ids || []);
    } catch (e) {
      showToast(`Could not load draft experiment: ${e.message}`, true);
      return;
    }

    try {
      const res = await fetch(`/api/admin/tasks`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const allTasks = await res.json();
      const tasks = allTasks.filter((t) => taskIds.includes(getId(t)));
      if (tasks.length === 0) {
        router.replace(`/admin/experiments/task?experiment_id=${encodeURIComponent(experimentId)}`);
        return;
      }
      setSelectedTasks(tasks);
      const map = {};
      tasks.forEach((t) => { map[getId(t)] = []; });
      setTaskIdiomMap(map);
    } catch (e) {
      showToast(`Could not load tasks: ${e.message}`, true);
      return;
    }

    await fetchIdiomsAndMapping();
  }

  async function fetchIdiomsAndMapping() {
    try {
      const [idiomsRes, mappingRes] = await Promise.all([
        fetch("/api/admin/idioms"),
        fetch("/api/admin/task-idioms"),
      ]);
      if (!idiomsRes.ok) throw new Error(`idioms: HTTP ${idiomsRes.status}`);
      if (!mappingRes.ok) throw new Error(`task-idioms: HTTP ${mappingRes.status}`);
      setAllIdioms(await idiomsRes.json());
      setTaskIdiomKeys(await mappingRes.json());
    } catch (e) {
      showToast(`Could not load idioms: ${e.message}`, true);
    }
  }

  function getIdiomsForTask(task) {
    const allowed = taskIdiomKeys[task.task_key];
    if (!allowed) return allIdioms;
    return allIdioms.filter((i) => allowed.includes(i.idiom_key));
  }

  function toggleIdiom(taskId, idiomId) {
    setTaskIdiomMap((prev) => {
      const arr = prev[taskId] || [];
      const newArr = arr.includes(idiomId)
        ? arr.filter((id) => id !== idiomId)
        : [...arr, idiomId];
      return { ...prev, [taskId]: newArr };
    });
  }

  const assignmentTotal = Object.values(taskIdiomMap).reduce(
    (sum, arr) => sum + arr.length,
    0
  );

  async function saveExperiment(publish = false) {
    const unassigned = selectedTasks.filter(
      (t) => (taskIdiomMap[getId(t)] || []).length === 0
    );
    if (unassigned.length > 0) {
      showToast(
        `Please assign at least one idiom to: ${unassigned.map((t) => t.task_key).join(", ")}`,
        true
      );
      return;
    }

    if (publish) {
      try {
        const res = await fetch(`/api/admin/experiments`);
        if (res.ok) {
          const allExps = await res.json();
          const activeOthers = allExps.filter(
            (e) => ["active", "published"].includes(e.status) && getId(e) !== experimentId
          );
          for (const exp of activeOthers) {
            await fetch(
              `${BASE_URL}/admin/experiments/${getId(exp)}/status?status=finished`,
              { method: "PATCH" }
            );
          }
        }
      } catch {
        showToast("Could not deactivate previous experiments. Please try again.", true);
        return;
      }
    }

    const taskConfigs = [];
    for (const task of selectedTasks) {
      const tid = getId(task);
      for (const idiomId of taskIdiomMap[tid] || []) {
        taskConfigs.push({ task_id: tid, idiom_id: idiomId, dataset_id: datasetIds[0] || "", question_ids: [] });
      }
    }

    const newStatus = publish ? "published" : "draft";

    try {
      const res = await fetch(`/api/admin/experiments/${experimentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_configs: taskConfigs, status: newStatus }),
      });
      if (!res.ok) throw new Error(await res.text());

      if (publish) {
        setSuccessDetail(
          `Experiment (ID: ${experimentId}) — ${taskConfigs.length} task-idiom assignment(s) confirmed. Now visible to participants.`
        );
        setShowSuccess(true);
        setTimeout(() => {
          document.getElementById("success-banner")?.scrollIntoView({ behavior: "smooth" });
        }, 50);
      } else {
        showToast("Draft saved. You can continue editing later.");
      }
    } catch (e) {
      showToast(`Failed to save experiment: ${e.message}`, true);
    }
  }

  async function viewExperiments() {
    try {
      const res = await fetch(`/api/admin/experiments`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setExperiments(await res.json());
      setExpModalOpen(true);
    } catch (e) {
      showToast(`Could not load experiments: ${e.message}`, true);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        {/* Page heading */}
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Allocate Idioms to Tasks</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Choose which visualization idioms should be shown for each selected task. Each task must
            have at least one idiom assigned before saving.
          </p>
        </div>

        {/* Toolbar */}
        <div className="flex justify-between items-center">
          <h2 className="text-base font-semibold text-on-surface">
            Task Cards
            {selectedTasks.length > 0 && (
              <span className="ml-2 text-xs text-on-surface-variant font-normal">
                ({selectedTasks.length} task{selectedTasks.length !== 1 ? "s" : ""})
              </span>
            )}
          </h2>
        </div>

        {/* Task cards with idiom allocation */}
        <div className="flex flex-col gap-6">
          {selectedTasks.length === 0 ? (
            <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
              <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                hourglass_empty
              </span>
              Loading…
            </div>
          ) : (
            selectedTasks.map((task) => {
              const tid = getId(task);
              const taskIdioms = getIdiomsForTask(task);
              const selectedForTask = taskIdiomMap[tid] || [];
              return (
                <div
                  key={tid}
                  className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden"
                >
                  <div className="border-l-4 border-primary p-5">
                    <div className="flex items-start gap-3">
                      <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded flex-shrink-0 mt-0.5">
                        {task.task_key}
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-on-surface leading-snug">
                          {task.label}
                        </p>
                      </div>
                    </div>
                  </div>

                  <div className="p-5 pt-3 border-t border-border-subtle">
                    <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                      Select Idioms{" "}
                      <span
                        className={`ml-2 font-normal normal-case tracking-normal ${
                          selectedForTask.length > 0 ? "text-primary" : "text-on-surface-variant"
                        }`}
                      >
                        ({selectedForTask.length} selected)
                      </span>
                    </p>
                    {allIdioms.length === 0 ? (
                      <p className="text-xs text-on-surface-variant italic">
                        No idioms in database yet. Click <strong>Seed Idioms</strong> above.
                      </p>
                    ) : taskIdioms.length === 0 ? (
                      <p className="text-xs text-on-surface-variant italic">
                        No matching idioms in database. Click <strong>Seed Idioms</strong> above.
                      </p>
                    ) : (
                      <div className="grid grid-cols-2 gap-2">
                        {taskIdioms.map((idiom) => {
                          const iid = getId(idiom);
                          const selected = selectedForTask.includes(iid);
                          return (
                            <div
                              key={iid}
                              onClick={() => toggleIdiom(tid, iid)}
                              className={`cursor-pointer flex items-center gap-2 p-3 rounded-lg border transition-all select-none
                                ${selected
                                  ? "bg-blue-50 border-primary/30"
                                  : "bg-surface-container-low border-transparent hover:border-outline-variant"
                                }`}
                            >
                              <span
                                className={`material-symbols-outlined text-base flex-shrink-0 transition-colors
                                  ${selected ? "text-primary icon-filled" : "text-outline-variant"}`}
                              >
                                {selected ? "check_circle" : "radio_button_unchecked"}
                              </span>
                              <div className="min-w-0">
                                <p className="text-xs font-semibold text-on-surface truncate">
                                  {idiom.label}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Success banner — shown after Publish */}
        {showSuccess && (
          <div
            id="success-banner"
            className="bg-green-50 border border-green-200 rounded-lg p-5 flex items-start gap-3"
          >
            <span className="material-symbols-outlined text-green-600 text-2xl flex-shrink-0 icon-filled">
              check_circle
            </span>
            <div>
              <p className="font-semibold text-green-800">Experiment published successfully!</p>
              <p className="text-sm text-green-700 mt-0.5">{successDetail}</p>
              <div className="flex gap-3 mt-3">
                <Link
                  href="/admin/experiments/new"
                  className="text-xs bg-primary text-white px-4 py-1.5 rounded font-semibold hover:bg-primary-container transition-colors"
                >
                  Create Another Experiment
                </Link>
                <button
                  onClick={viewExperiments}
                  className="text-xs border border-border-subtle text-on-surface-variant px-4 py-1.5 rounded hover:bg-surface-container transition-colors"
                >
                  View All Experiments
                </button>
                <Link
                  href="/admin"
                  className="text-xs border border-border-subtle text-on-surface-variant px-4 py-1.5 rounded hover:bg-surface-container transition-colors"
                >
                  Back to Admin Home
                </Link>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer action bar */}
      <div className="border-t border-border-subtle bg-white sticky bottom-0">
        <div className="max-w-[1140px] mx-auto px-8 py-4 flex justify-between items-center">
          <Link
            href={`/admin/experiments/task${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <div className="flex items-center gap-3">
            {assignmentTotal > 0 && (
              <span className="text-xs text-on-surface-variant">
                {assignmentTotal} idiom assignment{assignmentTotal !== 1 ? "s" : ""}
              </span>
            )}
            <button
              onClick={() => saveExperiment(false)}
              className="flex items-center gap-2 text-sm border border-border-subtle text-on-surface-variant px-6 py-3 rounded-lg hover:bg-surface-container transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-sm">save</span>
              Save as Draft
            </button>
            <button
              onClick={() => saveExperiment(true)}
              className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-8 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95"
            >
              <span className="material-symbols-outlined text-sm">publish</span>
              Publish Experiment
            </button>
          </div>
        </div>
      </div>

      {/* View Experiments Modal */}
      {expModalOpen && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setExpModalOpen(false); }}
        >
          <div className="bg-white rounded-xl p-6 w-full max-w-[680px] shadow-xl flex flex-col gap-4 max-h-[80vh]">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-on-surface">All Experiments</h3>
              <button onClick={() => setExpModalOpen(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="overflow-y-auto flex flex-col gap-3 text-sm">
              {experiments.length === 0 ? (
                <p className="text-on-surface-variant text-sm">No experiments found.</p>
              ) : (
                experiments.map((exp) => (
                  <div key={getId(exp)} className="border border-border-subtle rounded-lg p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-semibold text-on-surface">{exp.name || "(unnamed)"}</p>
                        <p className="text-xs text-on-surface-variant mt-0.5">
                          ID: {getId(exp)} &nbsp;·&nbsp; Status: {exp.status} &nbsp;·&nbsp; Type:{" "}
                          {exp.type}
                        </p>
                        <p className="text-xs text-on-surface-variant">
                          {exp.task_configs?.length ?? 0} task-idiom assignments
                        </p>
                      </div>
                      <span
                        className={`text-xs px-2 py-0.5 rounded-full font-semibold flex-shrink-0
                          ${exp.status === "draft"
                            ? "bg-yellow-100 text-yellow-800"
                            : "bg-green-100 text-green-800"
                          }`}
                      >
                        {exp.status}
                      </span>
                    </div>
                  </div>
                ))
              )}
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

export default function IdiomSelectionPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface">
          <span className="text-on-surface-variant text-sm">Loading…</span>
        </div>
      }
    >
      <IdiomSelectionContent />
    </Suspense>
  );
}
