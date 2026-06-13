"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";

function getId(obj) {
  return obj._id || obj.id;
}

const STATUS_STYLES = {
  pending: { label: "Pending", icon: "schedule", className: "bg-surface-container text-on-surface-variant" },
  running: { label: "Generating…", icon: "autorenew", className: "bg-yellow-100 text-yellow-800", spin: true },
  ready: { label: "Ready", icon: "check_circle", className: "bg-green-100 text-green-800" },
  failed: { label: "Failed", icon: "error", className: "bg-red-100 text-red-800" },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${s.className}`}>
      <span className={`material-symbols-outlined text-sm ${s.spin ? "animate-spin" : ""}`}>{s.icon}</span>
      {s.label}
    </span>
  );
}

// Generic param widget — renders per PARAM_SPEC entry (see ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §4-5, §10).
function ParamField({ entry, value, onChange }) {
  const options = entry.options || [];

  if (entry.widget === "select-one") {
    return (
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
      >
        <option value="">Select…</option>
        {options.map((opt) => {
          const optValue = typeof opt === "string" ? opt : opt.value;
          const optLabel = typeof opt === "string" ? opt : opt.label ?? opt.value;
          return (
            <option key={optValue} value={optValue}>
              {optLabel}
            </option>
          );
        })}
      </select>
    );
  }

  if (entry.widget === "select-many") {
    const selected = Array.isArray(value) ? value : [];
    return (
      <select
        multiple
        value={selected}
        onChange={(e) => onChange(Array.from(e.target.selectedOptions, (o) => o.value))}
        className="w-full text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
      >
        {options.map((opt) => {
          const optValue = typeof opt === "string" ? opt : opt.value;
          const optLabel = typeof opt === "string" ? opt : opt.label ?? opt.value;
          return (
            <option key={optValue} value={optValue}>
              {optLabel}
            </option>
          );
        })}
      </select>
    );
  }

  if (entry.widget === "number" || entry.widget === "threshold") {
    return (
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        className="w-full text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
    );
  }

  // text, activity-picker, attribute-picker, time-binning, severity-map, etc.:
  // free-text input, with a datalist of candidates if the spec provides any.
  const listId = `param-${entry.key}-options`;
  return (
    <>
      <input
        type="text"
        list={options.length > 0 ? listId : undefined}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="w-full text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
      {options.length > 0 && (
        <datalist id={listId}>
          {options.map((opt) => {
            const optValue = typeof opt === "string" ? opt : opt.value;
            return <option key={optValue} value={optValue} />;
          })}
        </datalist>
      )}
    </>
  );
}

function SpecifyContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [taskInstances, setTaskInstances] = useState([]);
  const [tasksById, setTasksById] = useState({});
  const [idiomsById, setIdiomsById] = useState({});
  const [paramSpecs, setParamSpecs] = useState({}); // task_id -> PARAM_SPEC[]
  const [paramValues, setParamValues] = useState({}); // task_id -> { [key]: value }
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const pollRef = useRef(null);

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
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [experimentId]);

  async function init() {
    setLoading(true);
    try {
      const [expRes, tasksRes, idiomsRes] = await Promise.all([
        fetch(`/api/admin/experiments/${experimentId}`),
        fetch(`/api/admin/tasks`),
        fetch(`/api/admin/idioms`),
      ]);
      if (!expRes.ok) throw new Error(`Experiment HTTP ${expRes.status}`);
      if (!tasksRes.ok) throw new Error(`Tasks HTTP ${tasksRes.status}`);
      if (!idiomsRes.ok) throw new Error(`Idioms HTTP ${idiomsRes.status}`);

      const [exp, tasks, idioms] = await Promise.all([expRes.json(), tasksRes.json(), idiomsRes.json()]);

      const tMap = {};
      tasks.forEach((t) => { tMap[getId(t)] = t; });
      setTasksById(tMap);

      const iMap = {};
      idioms.forEach((i) => { iMap[getId(i)] = i; });
      setIdiomsById(iMap);

      const instances = exp.task_instances || [];
      setTaskInstances(instances);

      await loadParamSpecs(instances, tMap);

      if (instances.length > 0 && instances.some((ti) => ti.generation_status === "running")) {
        startPolling();
      }
    } catch (e) {
      showToast(`Could not load experiment: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function loadParamSpecs(instances, tMap) {
    const specs = {};
    const values = {};
    await Promise.all(
      instances.map(async (ti) => {
        const task = tMap[ti.task_id];
        const taskKey = task?.task_key;
        let paramSpec = [];
        if (taskKey) {
          try {
            const res = await fetch(
              `/api/admin/tasks/${encodeURIComponent(taskKey)}/param-spec?dataset_id=${encodeURIComponent(ti.dataset_id || "")}`
            );
            if (res.ok) {
              const data = await res.json();
              paramSpec = data.param_spec || [];
            }
          } catch {
            // fall through with empty param_spec — task degrades to "no parameters" stub
          }
        }
        specs[ti.task_id] = paramSpec;

        const existing = ti.parameters || {};
        const vals = { ...existing };
        paramSpec.forEach((entry) => {
          if (vals[entry.key] === undefined) vals[entry.key] = entry.default ?? "";
        });
        values[ti.task_id] = vals;
      })
    );
    setParamSpecs(specs);
    setParamValues(values);
  }

  function setParamValue(taskId, key, value) {
    setParamValues((prev) => ({
      ...prev,
      [taskId]: { ...(prev[taskId] || {}), [key]: value },
    }));
  }

  function requiredParamsMissing() {
    const missing = [];
    for (const ti of taskInstances) {
      const spec = paramSpecs[ti.task_id] || [];
      const vals = paramValues[ti.task_id] || {};
      for (const entry of spec) {
        if (entry.required && (vals[entry.key] === undefined || vals[entry.key] === "")) {
          const task = tasksById[ti.task_id];
          missing.push(`${task?.task_key || ti.task_id}: ${entry.label || entry.key}`);
        }
      }
    }
    return missing;
  }

  function startPolling() {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const res = await fetch(`/api/admin/experiments/${experimentId}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const exp = await res.json();
        const instances = exp.task_instances || [];
        setTaskInstances(instances);
        if (instances.length > 0 && instances.every((ti) => ti.generation_status === "ready" || ti.generation_status === "failed")) {
          clearInterval(pollRef.current);
          pollRef.current = null;
          setGenerating(false);
        }
      } catch (e) {
        clearInterval(pollRef.current);
        pollRef.current = null;
        setGenerating(false);
        showToast(`Lost connection while polling generation status: ${e.message}`, true);
      }
    }, 2500);
  }

  async function handleGenerate() {
    const missing = requiredParamsMissing();
    if (missing.length > 0) {
      showToast(`Please fill in required parameters: ${missing.join(", ")}`, true);
      return;
    }

    setGenerating(true);
    try {
      const updatedInstances = taskInstances.map((ti) => ({
        ...ti,
        parameters: paramValues[ti.task_id] || {},
      }));

      let res = await fetch(`/api/admin/experiments/${experimentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_instances: updatedInstances }),
      });
      if (!res.ok) throw new Error(await res.text());

      res = await fetch(`/api/admin/experiments/${experimentId}/generate`, { method: "POST" });
      if (!res.ok) throw new Error(await res.text());

      // Reflect the "running" status immediately, then poll for completion.
      setTaskInstances(updatedInstances.map((ti) => ({ ...ti, generation_status: "running", generation_error: null })));
      startPolling();
    } catch (e) {
      setGenerating(false);
      showToast(`Failed to start generation: ${e.message}`, true);
    }
  }

  const allReady = taskInstances.length > 0 && taskInstances.every((ti) => ti.generation_status === "ready");

  function handleNext() {
    if (!allReady) {
      showToast("All tasks must finish generating (status: Ready) before continuing.", true);
      return;
    }
    router.push(`/admin/experiments/overview?experiment_id=${encodeURIComponent(experimentId)}`);
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        {/* Page heading */}
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Specify &amp; Generate</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Set any task-specific hyperparameters, then generate the visualizations for the
            selected idioms. Tasks with no parameters are ready to generate immediately.
          </p>
        </div>

        {/* Task cards */}
        <div className="flex flex-col gap-6">
          {loading ? (
            <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
              <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                hourglass_empty
              </span>
              Loading…
            </div>
          ) : taskInstances.length === 0 ? (
            <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
              <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                inbox
              </span>
              No tasks found for this experiment.
            </div>
          ) : (
            taskInstances.map((ti) => {
              const task = tasksById[ti.task_id] || {};
              const spec = paramSpecs[ti.task_id] || [];
              const vals = paramValues[ti.task_id] || {};
              return (
                <div
                  key={ti.task_id}
                  className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden"
                >
                  <div className="border-l-4 border-primary p-5 flex items-start justify-between gap-3">
                    <div className="flex items-start gap-3">
                      <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded flex-shrink-0 mt-0.5">
                        {task.task_key || ti.task_id}
                      </span>
                      <div>
                        <p className="text-sm font-semibold text-on-surface leading-snug">
                          {task.label || "(unknown task)"}
                        </p>
                        {ti.idiom_ids?.length > 0 && (
                          <p className="text-xs text-on-surface-variant mt-1">
                            {ti.idiom_ids.map((iid) => idiomsById[iid]?.label || iid).join(", ")}
                          </p>
                        )}
                      </div>
                    </div>
                    <StatusBadge status={ti.generation_status || "pending"} />
                  </div>

                  <div className="p-5 pt-3 border-t border-border-subtle">
                    <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                      Parameters
                    </p>
                    {spec.length === 0 ? (
                      <p className="text-xs text-on-surface-variant italic">
                        No parameters required — ready to generate.
                      </p>
                    ) : (
                      <div className="grid grid-cols-2 gap-4">
                        {spec.map((entry) => (
                          <div key={entry.key} className="flex flex-col gap-1">
                            <label className="text-xs font-semibold text-on-surface">
                              {entry.label || entry.key}
                              {entry.required && <span className="text-error ml-0.5">*</span>}
                            </label>
                            <ParamField
                              entry={entry}
                              value={vals[entry.key]}
                              onChange={(v) => setParamValue(ti.task_id, entry.key, v)}
                            />
                          </div>
                        ))}
                      </div>
                    )}

                    {ti.generation_status === "failed" && ti.generation_error && (
                      <p className="text-xs text-error mt-3">
                        Generation error: {ti.generation_error}
                      </p>
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
            href={`/admin/experiments/idiom${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerate}
              disabled={generating || loading}
              className="flex items-center gap-2 text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <span className={`material-symbols-outlined text-sm ${generating ? "animate-spin" : ""}`}>
                {generating ? "autorenew" : "play_arrow"}
              </span>
              {generating ? "Generating…" : "Generate Visualizations"}
            </button>
            <button
              onClick={handleNext}
              disabled={!allReady}
              className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
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

export default function SpecifyPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface">
          <span className="text-on-surface-variant text-sm">Loading…</span>
        </div>
      }
    >
      <SpecifyContent />
    </Suspense>
  );
}
