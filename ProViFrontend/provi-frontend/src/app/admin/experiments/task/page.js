"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";
import EditTaskModal from "../../../../components/Admin/EditTaskModal";
import { saveWizardStep } from "../../../../utils/wizardSave";

// ---------------------------------------------------------------------------
// Static classification characteristics from the task taxonomy.
// Source: "Conformance Checking Tasks Working Table.xlsx" columns B / C / D.
// ---------------------------------------------------------------------------
const TASK_CHARACTERISTICS = {
  task01: { goal: "Confirm",  means: "Compare",      chars: "Process conformance" },
  task02: { goal: "Confirm",  means: "Present",      chars: "Process conformance" },
  task03: { goal: "Describe", means: "Compare",      chars: "Conformant and non-conformant traces" },
  task04: { goal: "Describe", means: "Compare",      chars: "Process conformance" },
  task05: { goal: "Describe", means: "Compare",      chars: "Violation patterns" },
  task06: { goal: "Describe", means: "Derive",       chars: "Process conformance" },
  task07: { goal: "Describe", means: "Derive",       chars: "Process conformance over time" },
  task08: { goal: "Describe", means: "Derive",       chars: "Violation patterns" },
  task09: { goal: "Describe", means: "Identify",     chars: "Guideline violations" },
  task10: { goal: "Describe", means: "Present",      chars: "Conformance distribution" },
  task11: { goal: "Describe", means: "Summarize",    chars: "Guideline violations" },
  task12: { goal: "Describe", means: "Summarize",    chars: "Process conformance" },
  task13: { goal: "Explain",  means: "(not known)",  chars: "Reasons for guideline violations" },
  task14: { goal: "Explain",  means: "Annotate",     chars: "Guideline violations" },
  task15: { goal: "Explain",  means: "Annotate",     chars: "Reasons for process conformance" },
  task16: { goal: "Explain",  means: "Annotate",     chars: "Reasons for guideline violations" },
  task17: { goal: "Explain",  means: "Annotate",     chars: "Severity of guideline violations" },
  task18: { goal: "Explain",  means: "Derive",       chars: "Reasons for guideline violations" },
  task19: { goal: "Explain",  means: "Discover",     chars: "Effects of goal deviations" },
  task20: { goal: "Explain",  means: "Discover",     chars: "Reasons for guideline violations" },
  task21: { goal: "Explain",  means: "Identify",     chars: "Reasons for guideline violations" },
  task22: { goal: "Explain",  means: "Summarize",    chars: "Reasons for process conformance" },
  task23: { goal: "Explore",  means: "Compare",      chars: "Guideline violations" },
  task24: { goal: "Explore",  means: "Discover",     chars: "Guideline violations in model" },
  task25: { goal: "Explore",  means: "Discover",     chars: "Process conformance" },
  task26: { goal: "Present",  means: "Present",      chars: "Severity of guideline violations" },
  task27: { goal: "Explore",  means: "Identify",     chars: "Conformant and non-conformant traces" },
  task28: { goal: "Explore",  means: "Identify",     chars: "Guideline violations" },
  task29: { goal: "Explore",  means: "Summarize",    chars: "Guideline violations" },
  task30: { goal: "Present",  means: "Compare",      chars: "Guideline violations" },
  task31: { goal: "Present",  means: "Compare",      chars: "Impact of conformance on process outcome" },
  task32: { goal: "Present",  means: "Compare",      chars: "Most frequent guideline violations" },
  task33: { goal: "Present",  means: "Compare",      chars: "Process conformance" },
  task34: { goal: "Present",  means: "Present",      chars: "Guideline violations" },
  task35: { goal: "Present",  means: "Present",      chars: "Guideline violations in model" },
  task36: { goal: "Present",  means: "Present",      chars: "Process conformance per rule" },
  task37: { goal: "Present",  means: "Summarize",    chars: "Process conformance" },
};

const DIMS = [
  { id: "goal",  label: "Task Goal",      color: "#6366f1", dot: "bg-indigo-400",  tag: "bg-indigo-100 text-indigo-700" },
  { id: "means", label: "Task Means",     color: "#10b981", dot: "bg-emerald-400", tag: "bg-emerald-100 text-emerald-700" },
  { id: "chars", label: "Characteristics",color: "#f59e0b", dot: "bg-amber-400",   tag: "bg-amber-100 text-amber-700" },
];

function getTaskId(task) {
  return task._id || task.id;
}

export default function TaskSelectionPage() {
  const router       = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [allTasks,    setAllTasks]    = useState([]);
  const [loadError,   setLoadError]   = useState(null);
  const [selectedIds, setSelectedIds] = useState([]);

  // Filter state: null = no filter for that dim
  const [filterState, setFilterState] = useState({ goal: null, means: null, chars: null });
  const [openFilter,  setOpenFilter]  = useState(null);
  const filterBarRef = useRef(null);

  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => {
    setToast((t) => ({ ...t, visible: false }));
  }, []);

  // Edit Task modal state
  const [editingTask, setEditingTask] = useState(null);

  useEffect(() => {
    if (!experimentId) router.replace("/admin/experiments/new");
  }, [experimentId, router]);

  // Resume: pre-select tasks already saved on this draft experiment
  useEffect(() => {
    if (!experimentId) return;
    fetch(`/api/admin/experiments/${encodeURIComponent(experimentId)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((exp) => {
        if (exp?.task_configs?.length) {
          setSelectedIds(exp.task_configs.map((tc) => tc.task_id));
        }
      })
      .catch(() => {});
  }, [experimentId]);

  const fetchTasks = useCallback(() => {
    return fetch("/api/admin/tasks")
      .then((r) => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(setAllTasks)
      .catch((e) => setLoadError(e.message));
  }, []);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  async function saveEditedTask(payload) {
    const taskId = getTaskId(editingTask);
    const res = await fetch(`/api/admin/tasks/${encodeURIComponent(taskId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    showToast("Task updated successfully!");
    await fetchTasks();
  }

  // Close dropdown on outside click
  useEffect(() => {
    function onMouseDown(e) {
      if (filterBarRef.current && !filterBarRef.current.contains(e.target)) {
        setOpenFilter(null);
      }
    }
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, []);

  // Tasks visible given current filter selections (AND across dims)
  const visibleTasks = useMemo(() => {
    return allTasks.filter((t) => {
      const c = TASK_CHARACTERISTICS[t.task_key];
      if (!c) return true; // unclassified tasks always shown
      return (
        (!filterState.goal  || c.goal  === filterState.goal)  &&
        (!filterState.means || c.means === filterState.means) &&
        (!filterState.chars || c.chars === filterState.chars)
      );
    });
  }, [allTasks, filterState]);

  // Context-aware options: only show values that yield ≥1 task given the OTHER dims
  function getOptions(dimId) {
    const counts = {};
    allTasks.forEach((t) => {
      const c = TASK_CHARACTERISTICS[t.task_key];
      if (!c) return;
      const othersMatch = DIMS.every((d) => {
        if (d.id === dimId) return true;
        return !filterState[d.id] || c[d.id] === filterState[d.id];
      });
      if (othersMatch) counts[c[dimId]] = (counts[c[dimId]] || 0) + 1;
    });
    return Object.entries(counts).sort((a, b) => a[0].localeCompare(b[0]));
  }

  function selectFilter(dimId, val) {
    setFilterState((prev) => ({ ...prev, [dimId]: prev[dimId] === val ? null : val }));
    setOpenFilter(null);
  }

  function clearFilter(e, dimId) {
    e.stopPropagation();
    setFilterState((prev) => ({ ...prev, [dimId]: null }));
  }

  function resetFilters() {
    setFilterState({ goal: null, means: null, chars: null });
  }

  const anyFilter = DIMS.some((d) => filterState[d.id]);

  function buildTaskConfigs(ids) {
    return ids.map((taskId) => ({
      task_id: taskId,
      idiom_id: "",
      dataset_id: "",
      question_ids: [],
    }));
  }

  function toggleTask(id) {
    setSelectedIds((prev) => {
      const next = prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id];
      if (experimentId) {
        saveWizardStep(experimentId, "task", { task_configs: buildTaskConfigs(next) })
          .catch((e) => showToast(`Failed to save tasks: ${e.message}`, true));
      }
      return next;
    });
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
    try {
      await saveWizardStep(experimentId, "task", { task_configs: buildTaskConfigs(selectedIds) });
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
          {/* Left column */}
          <div className="col-span-8 flex flex-col gap-4">

            {/* ── Filter bars ─────────────────────────────── */}
            <div className="flex flex-col gap-2" ref={filterBarRef}>
              {DIMS.map((dim) => {
                const options = getOptions(dim.id);
                const isOpen  = openFilter === dim.id;
                const current = filterState[dim.id];
                return (
                  <div key={dim.id} className="relative">
                    {/* Bar button */}
                    <button
                      type="button"
                      onClick={() => setOpenFilter(isOpen ? null : dim.id)}
                      className={`w-full flex items-center justify-between px-3 py-2.5 bg-white rounded-lg border text-sm transition-colors select-none
                        ${isOpen   ? "border-primary rounded-b-none shadow-sm" :
                          current  ? "border-primary"
                                   : "border-slate-200 hover:border-primary/50"}`}
                    >
                      <div className="flex items-center gap-2">
                        <span
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{ background: dim.color }}
                        />
                        <span className="text-xs font-bold uppercase tracking-wider text-slate-500">
                          {dim.label}
                        </span>
                        <span className="text-slate-300 text-xs">|</span>
                        {current
                          ? <span className="text-primary font-semibold text-xs">{current}</span>
                          : <span className="text-slate-400 text-xs">All</span>
                        }
                      </div>
                      <div className="flex items-center gap-2">
                        {current && (
                          <span
                            onClick={(e) => clearFilter(e, dim.id)}
                            className="text-slate-400 hover:text-red-500 text-xs font-semibold cursor-pointer px-1"
                          >
                            ✕
                          </span>
                        )}
                        <span className={`text-slate-400 text-xs transition-transform duration-150 ${isOpen ? "rotate-180" : ""}`}>
                          ▾
                        </span>
                      </div>
                    </button>

                    {/* Dropdown */}
                    {isOpen && (
                      <div className="absolute top-full left-0 right-0 z-50 bg-white border border-primary border-t-0 rounded-b-lg shadow-lg overflow-hidden">
                        {options.length === 0 ? (
                          <div className="px-3 py-3 text-xs text-slate-400 text-center">
                            No options available
                          </div>
                        ) : (
                          options.map(([val, count]) => (
                            <button
                              key={val}
                              type="button"
                              onClick={() => selectFilter(dim.id, val)}
                              className={`w-full flex items-center justify-between px-3 py-2 text-sm text-left transition-colors
                                ${current === val
                                  ? "bg-blue-50 text-primary font-semibold"
                                  : "hover:bg-slate-50 text-slate-700"
                                }`}
                            >
                              <span>{val}</span>
                              <div className="flex items-center gap-2">
                                <span className={`text-xs ${current === val ? "text-primary/60" : "text-slate-400"}`}>
                                  {count}
                                </span>
                                {current === val && (
                                  <span className="text-primary text-xs">✓</span>
                                )}
                              </div>
                            </button>
                          ))
                        )}
                      </div>
                    )}
                  </div>
                );
              })}

              {/* Reset row */}
              {anyFilter && (
                <div className="flex items-center justify-between px-1">
                  <span className="text-xs text-slate-400">
                    Showing {visibleTasks.length} of {allTasks.length} tasks
                  </span>
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="text-xs text-primary font-semibold hover:underline"
                  >
                    Reset filters
                  </button>
                </div>
              )}
            </div>

            {/* ── Task list header ─────────────────────────── */}
            <div className="flex justify-between items-center">
              <h2 className="text-base font-semibold text-on-surface">
                Available Tasks
                {allTasks.length > 0 && (
                  <span className={`ml-2 text-xs font-normal px-1.5 py-0.5 rounded-full
                    ${anyFilter ? "bg-blue-100 text-primary" : "text-on-surface-variant bg-slate-100"}`}>
                    {anyFilter ? `${visibleTasks.length} / ${allTasks.length}` : allTasks.length}
                  </span>
                )}
              </h2>
            </div>

            {/* ── Task cards ───────────────────────────────── */}
            <div className="flex flex-col gap-3">
              {loadError ? (
                <div className="text-sm text-error bg-error-container px-4 py-3 rounded-lg">
                  Could not load tasks from backend. Make sure the backend is running.
                  <br /><span className="text-xs opacity-70">{loadError}</span>
                </div>
              ) : allTasks.length === 0 ? (
                <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
                  <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">inbox</span>
                  No tasks in database yet.
                </div>
              ) : visibleTasks.length === 0 ? (
                <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
                  <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                    filter_alt_off
                  </span>
                  No tasks match the selected filters.
                  <br />
                  <button
                    type="button"
                    onClick={resetFilters}
                    className="mt-2 text-xs text-primary font-semibold hover:underline"
                  >
                    Clear filters
                  </button>
                </div>
              ) : (
                visibleTasks.map((task) => {
                  const id       = getTaskId(task);
                  const selected = selectedIds.includes(id);
                  const chars    = TASK_CHARACTERISTICS[task.task_key];
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
                          <p className="text-sm font-semibold text-on-surface leading-snug mb-2">
                            {task.label}
                          </p>
                          {/* Characteristic tags */}
                          {chars && (
                            <div className="flex flex-wrap gap-1.5">
                              {DIMS.map((dim) => (
                                <span
                                  key={dim.id}
                                  className={`inline-flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full ${dim.tag}`}
                                >
                                  <span
                                    className="w-1.5 h-1.5 rounded-full flex-shrink-0"
                                    style={{ background: dim.color }}
                                  />
                                  {chars[dim.id]}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={(e) => { e.stopPropagation(); setEditingTask(task); }}
                          title="Edit task question"
                          className="text-on-surface-variant hover:text-primary flex-shrink-0 transition-colors p-1 rounded"
                        >
                          <span className="material-symbols-outlined text-sm">edit</span>
                        </button>
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
                    <span className="material-symbols-outlined text-2xl mb-1 text-outline-variant">list_alt</span>
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

      {/* Footer */}
      <div className="border-t border-border-subtle bg-white sticky bottom-0">
        <div className="max-w-[1140px] mx-auto px-8 py-4 flex justify-between items-center">
          <Link
            href="/admin/experiments/new"
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <button
            onClick={goToStep2}
            className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95"
          >
            Next
            <span className="material-symbols-outlined text-sm">chevron_right</span>
          </button>
        </div>
      </div>

      {editingTask && (
        <EditTaskModal
          task={editingTask}
          onClose={() => setEditingTask(null)}
          onSave={saveEditedTask}
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
