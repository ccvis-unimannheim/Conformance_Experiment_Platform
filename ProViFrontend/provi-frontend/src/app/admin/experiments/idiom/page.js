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

  async function handleNext() {
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

    const taskConfigs = [];
    for (const task of selectedTasks) {
      const tid = getId(task);
      for (const idiomId of taskIdiomMap[tid] || []) {
        taskConfigs.push({ task_id: tid, idiom_id: idiomId, dataset_id: datasetIds[0] || "", question_ids: [] });
      }
    }

    try {
      const res = await fetch(`/api/admin/experiments/${experimentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_configs: taskConfigs }),
      });
      if (!res.ok) throw new Error(await res.text());
      router.push(`/admin/experiments/specify?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      showToast(`Failed to save experiment: ${e.message}`, true);
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
          <div className="flex items-center gap-4">
            {assignmentTotal > 0 && (
              <span className="text-xs text-on-surface-variant">
                {assignmentTotal} idiom assignment{assignmentTotal !== 1 ? "s" : ""}
              </span>
            )}
            <button
              onClick={handleNext}
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
