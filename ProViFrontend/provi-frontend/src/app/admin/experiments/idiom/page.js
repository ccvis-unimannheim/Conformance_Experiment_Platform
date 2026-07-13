"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";
import { TASK_IDIOM_LABEL_OVERRIDES } from "../../../../utils/idiomLabels";

function getId(obj) {
  return obj._id || obj.id;
}

// ---------------------------------------------------------------------------
// Idiom Preview Modal
// ---------------------------------------------------------------------------
function IdiomPreviewModal({ taskKey, idiomKey, idiomLabel, onClose }) {
  const [status, setStatus] = useState("idle"); // "idle"|"generating"|"ready"|"failed"
  const [enlarged, setEnlarged] = useState(false);
  const pollRef = useRef(null);

  useEffect(() => {
    if (!taskKey || !idiomKey) return;

    async function trigger() {
      try {
        const res = await fetch(`/api/admin/idiom-preview/${taskKey}`, { method: "POST" });
        if (!res.ok) { setStatus("failed"); return; }
        const data = await res.json();
        if (data.status === "ready") { setStatus("ready"); return; }
        setStatus("generating");
        startPolling();
      } catch {
        setStatus("failed");
      }
    }

    function startPolling() {
      if (pollRef.current) clearInterval(pollRef.current);
      pollRef.current = setInterval(async () => {
        try {
          const res = await fetch(`/api/admin/idiom-preview/${taskKey}/status`);
          if (!res.ok) return;
          const data = await res.json();
          if (data.status === "ready" || data.status === "failed") {
            clearInterval(pollRef.current);
            setStatus(data.status);
          }
        } catch {}
      }, 1500);
    }

    trigger();
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [taskKey, idiomKey]);

  // Close on Escape key
  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const svgSrc = `/api/admin/idiom-preview/${taskKey}/${idiomKey}`;

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
      onClick={onClose}
    >
      <div
        className={`bg-white flex flex-col overflow-hidden transition-all duration-200 ${
          enlarged
            ? "fixed inset-4 z-50 rounded-xl shadow-2xl"
            : "rounded-xl shadow-xl w-[720px] max-w-[95vw] max-h-[90vh]"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle flex-shrink-0">
          <div>
            <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded mr-2">
              {taskKey}
            </span>
            <span className="text-sm font-semibold text-on-surface">{idiomLabel}</span>
            <span className="ml-2 text-xs text-on-surface-variant">(sample data · default params)</span>
          </div>
          <div className="flex items-center gap-2">
            {status === "ready" && (
              <button
                onClick={() => setEnlarged((v) => !v)}
                title={enlarged ? "Shrink" : "Enlarge"}
                className="text-on-surface-variant hover:text-primary transition-colors"
              >
                <span className="material-symbols-outlined text-[20px]">
                  {enlarged ? "close_fullscreen" : "open_in_full"}
                </span>
              </button>
            )}
            <button
              onClick={onClose}
              className="text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>

        {/* Body — white background so SVGs with white bg are visible */}
        <div className="flex-1 flex items-center justify-center p-6 overflow-auto bg-white min-h-[320px]">
          {status === "idle" || status === "generating" ? (
            <div className="flex flex-col items-center gap-3 text-on-surface-variant">
              <span className="material-symbols-outlined text-4xl animate-spin">autorenew</span>
              <span className="text-sm">Generating preview…</span>
            </div>
          ) : status === "failed" ? (
            <div className="flex flex-col items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-error">error_outline</span>
              <p className="text-sm text-on-surface-variant text-center">
                Preview generation failed.<br/>
                <span className="text-xs">Make sure the backend is up to date (rebuild Docker if needed).</span>
              </p>
            </div>
          ) : (
            <img
              src={svgSrc}
              alt={`${taskKey} ${idiomKey} preview`}
              className={enlarged ? "max-w-full max-h-full object-contain" : "max-w-full max-h-[65vh] object-contain"}
              onError={(e) => {
                e.currentTarget.style.display = "none";
                e.currentTarget.nextSibling.style.display = "flex";
              }}
            />
          )}
          {status === "ready" && (
            <div
              className="hidden flex-col items-center gap-2 text-on-surface-variant"
            >
              <span className="material-symbols-outlined text-3xl">broken_image</span>
              <span className="text-sm">Image failed to load.</span>
              <a href={svgSrc} target="_blank" rel="noopener noreferrer"
                 className="text-xs text-primary underline">Open directly</a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------
function IdiomSelectionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [selectedTasks, setSelectedTasks] = useState([]);
  const [allIdioms, setAllIdioms] = useState([]);
  const [taskIdiomKeys, setTaskIdiomKeys] = useState({});
  const [taskIdiomMap, setTaskIdiomMap] = useState({});
  const [datasetIds, setDatasetIds] = useState([]);

  // Preview modal state
  const [previewModal, setPreviewModal] = useState(null); // { taskKey, idiomKey, idiomLabel }

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
    const idioms = allowed
      ? allIdioms.filter((i) => allowed.includes(i.idiom_key))
      : allIdioms;
    const overrides = TASK_IDIOM_LABEL_OVERRIDES[task.task_key] || {};
    return idioms.map((i) =>
      overrides[i.idiom_key] ? { ...i, label: overrides[i.idiom_key] } : i
    );
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

  function handleSelectAll() {
    const newMap = {};
    selectedTasks.forEach((task) => {
      const tid = getId(task);
      newMap[tid] = getIdiomsForTask(task).map((i) => getId(i));
    });
    setTaskIdiomMap((prev) => ({ ...prev, ...newMap }));
  }

  function handleDeselectAll() {
    const newMap = {};
    selectedTasks.forEach((task) => { newMap[getId(task)] = []; });
    setTaskIdiomMap((prev) => ({ ...prev, ...newMap }));
  }

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
            have at least one idiom assigned before saving. Click{" "}
            <span className="material-symbols-outlined text-sm align-middle">visibility</span>{" "}
            to preview what an idiom looks like using sample data.
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
          {selectedTasks.length > 0 && (
            <div className="flex items-center gap-2">
              <button
                onClick={handleSelectAll}
                className="flex items-center gap-1.5 text-sm font-medium text-primary border border-primary/30 bg-blue-50 hover:bg-blue-100 px-4 py-2 rounded-lg transition-all active:scale-95"
              >
                <span className="material-symbols-outlined text-[16px]">select_all</span>
                Select All Idioms
              </button>
              <button
                onClick={handleDeselectAll}
                className="flex items-center gap-1.5 text-sm font-medium text-on-surface-variant border border-outline-variant bg-white hover:bg-surface-container-low px-4 py-2 rounded-lg transition-all active:scale-95"
              >
                <span className="material-symbols-outlined text-[16px]">deselect</span>
                Deselect All
              </button>
            </div>
          )}
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
                    <div className="flex items-center justify-between mb-3">
                      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                        Select Idioms{" "}
                        <span
                          className={`ml-2 font-normal normal-case tracking-normal ${
                            selectedForTask.length > 0 ? "text-primary" : "text-on-surface-variant"
                          }`}
                        >
                          ({selectedForTask.length} selected)
                        </span>
                      </p>
                      {taskIdioms.length > 0 && (
                        <div className="flex items-center gap-1.5">
                          <button
                            onClick={() =>
                              setTaskIdiomMap((prev) => ({
                                ...prev,
                                [tid]: taskIdioms.map((i) => getId(i)),
                              }))
                            }
                            className="flex items-center gap-1 text-xs font-medium text-primary border border-primary/30 bg-blue-50 hover:bg-blue-100 px-3 py-1 rounded-lg transition-all active:scale-95"
                          >
                            <span className="material-symbols-outlined text-[14px]">select_all</span>
                            Select All
                          </button>
                          {selectedForTask.length > 0 && (
                            <button
                              onClick={() =>
                                setTaskIdiomMap((prev) => ({ ...prev, [tid]: [] }))
                              }
                              className="flex items-center gap-1 text-xs font-medium text-on-surface-variant border border-outline-variant bg-white hover:bg-surface-container-low px-3 py-1 rounded-lg transition-all active:scale-95"
                            >
                              <span className="material-symbols-outlined text-[14px]">deselect</span>
                              Deselect All
                            </button>
                          )}
                        </div>
                      )}
                    </div>
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
                              <div className="min-w-0 flex-1">
                                <p className="text-xs font-semibold text-on-surface truncate">
                                  {idiom.label}
                                </p>
                              </div>
                              {/* Eye button — preview this idiom */}
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setPreviewModal({
                                    taskKey: task.task_key,
                                    idiomKey: idiom.idiom_key,
                                    idiomLabel: idiom.label,
                                  });
                                }}
                                title="Preview this idiom with sample data"
                                className="flex-shrink-0 text-on-surface-variant hover:text-primary transition-colors p-0.5 rounded"
                              >
                                <span className="material-symbols-outlined text-[16px]">visibility</span>
                              </button>
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

      {/* Idiom preview modal */}
      {previewModal && (
        <IdiomPreviewModal
          taskKey={previewModal.taskKey}
          idiomKey={previewModal.idiomKey}
          idiomLabel={previewModal.idiomLabel}
          onClose={() => setPreviewModal(null)}
        />
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
