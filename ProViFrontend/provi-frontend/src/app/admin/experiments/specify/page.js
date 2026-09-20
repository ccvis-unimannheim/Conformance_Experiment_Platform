"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";
import { queueWizardSave } from "../../../../utils/wizardSave";

function getId(obj) {
  return obj._id || obj.id;
}

// A task whose images came from an idiom bundle import. Its parameters are the
// ones those images were drawn with, and the backend keeps them fixed.
function isImported(ti) {
  return !!ti?.images_imported_from;
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString();
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

// A PARAM_SPEC entry may declare `visible_if: {other_key: value}` — it applies
// only when that other parameter holds that value. The Violation-profile class
// uses it so the strategy picker's three selection lists don't all show at once,
// two of them inert. An entry with no `visible_if` always applies.
function entryApplies(entry, vals) {
  const cond = entry.visible_if;
  if (!cond) return true;
  return Object.entries(cond).every(([key, want]) => {
    const have = vals?.[key];
    return Array.isArray(want) ? want.includes(have) : have === want;
  });
}

// An entry whose candidates only make sense once a sibling parameter is set
// (the values of *this* attribute, not of every attribute in the log) declares
// `options_filter: {param, prefix}`. Its source lists every "<key><prefix>
// <value>" pair — /specify bakes a param's options in once per dataset, so the
// source cannot narrow itself to a choice made afterwards — and this keeps the
// ones belonging to the sibling's current value. Nothing is offered until the
// sibling is set: every option would be wrong.
function filterOptions(entry, options, siblings) {
  const rule = entry.options_filter;
  if (!rule) return options;
  const key = (siblings || {})[rule.param];
  if (!key) return [];
  const prefix = `${key}${rule.prefix ?? ""}`;
  return options
    .filter((o) => String(typeof o === "string" ? o : o.value).startsWith(prefix))
    // The field is already scoped to the attribute, so repeating it in every
    // row is noise. Only the label changes; the stored value keeps the pair.
    .map((o) => (typeof o === "string"
      ? { value: o, label: o.slice(prefix.length) }
      : { ...o, label: String(o.label ?? o.value).slice(prefix.length) }));
}

// Generic param widget — renders per PARAM_SPEC entry (see docs/ADMIN_EXPERIMENT_SETUP.md).
function ParamField({ entry, value, onChange, siblings }) {
  const options = filterOptions(entry, entry.options || [], siblings);
  const [optionFilter, setOptionFilter] = useState("");

  if (entry.widget === "select-one") {
    // A picker whose candidates come from the dataset can legitimately have
    // none — a log with no event-level attribute offers no event condition, a
    // log with no org:resource no resource. Without this the field rendered as
    // an empty dropdown, which reads as "nothing selected yet" rather than
    // "there is nothing to select". select-many has said so all along; this is
    // the same message for the single-select form. Entries whose options are
    // hard-coded (a perspective, a pick rule) are never empty and never hit it.
    if (entry.source && options.length === 0) {
      return (
        <div className="flex flex-col gap-1">
          <p className="text-sm text-on-surface/60 italic">
            No candidates available for this dataset yet.
          </p>
          {entry.options_error && (
            <p className="text-xs text-red-700 font-mono break-all">{entry.options_error}</p>
          )}
        </div>
      );
    }
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
    if (options.length === 0) {
      const waitingFor = entry.options_filter && !(siblings || {})[entry.options_filter.param];
      return (
        <div className="flex flex-col gap-1">
          <p className="text-sm text-on-surface/60 italic">
            {waitingFor
              ? "Choose the attribute above first — these are its values."
              : "No candidates available for this dataset yet."}
          </p>
          {entry.options_error && (
            <p className="text-xs text-red-700 font-mono break-all">{entry.options_error}</p>
          )}
        </div>
      );
    }
    function toggle(optValue) {
      if (selected.includes(optValue)) {
        onChange(selected.filter((v) => v !== optValue));
      } else {
        onChange([...selected, optValue]);
      }
    }
    // Trace picker: the chart labels traces by running number ("Trace 1..N") in
    // selection order, so surface the "Trace N → id" mapping for the admin.
    const isTracePicker = entry.source === "log.trace_ids";
    // A dataset can produce hundreds of candidates (every trace id, every
    // "activity · attribute = value"), and the list is a scroll box: without a
    // filter, finding one means reading all of them. Selected options always
    // stay visible so filtering cannot hide what is already chosen.
    const query = (optionFilter || "").trim().toLowerCase();
    const shownOptions = !query
      ? options
      : options.filter((opt) => {
          const v = typeof opt === "string" ? opt : opt.value;
          const l = typeof opt === "string" ? opt : opt.label ?? opt.value;
          return selected.includes(v) || String(l).toLowerCase().includes(query);
        });
    return (
      <div className="flex flex-col gap-1">
        {isTracePicker && selected.length > 0 && (
          <div className="text-xs border border-border-subtle rounded-lg px-3 py-2 bg-gray-50">
            <span className="font-semibold text-on-surface">
              Shown in the chart as (in this order):
            </span>
            <div className="mt-1 flex flex-col gap-0.5">
              {selected.map((id, i) => (
                <span key={id} className="text-on-surface-variant">
                  <span className="font-semibold text-on-surface">Trace {i + 1}:</span> ID {id}
                </span>
              ))}
            </div>
          </div>
        )}
        {options.length > 12 && (
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={optionFilter}
              onChange={(e) => setOptionFilter(e.target.value)}
              placeholder={`Filter ${options.length} options…`}
              className="w-full text-xs border border-border-subtle rounded-lg px-2 py-1 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <span className="text-xs text-on-surface-variant whitespace-nowrap">
              {shownOptions.length} shown · {selected.length} selected
            </span>
          </div>
        )}
        <div className="flex flex-col gap-0.5 max-h-72 overflow-y-auto border border-border-subtle rounded-lg px-3 py-2 bg-white">
          {shownOptions.length === 0 && (
            <span className="text-sm text-on-surface-variant italic">
              Nothing matches this filter.
            </span>
          )}
          {shownOptions.map((opt) => {
            const optValue = typeof opt === "string" ? opt : opt.value;
            const optLabel = typeof opt === "string" ? opt : opt.label ?? opt.value;
            return (
              <label
                key={optValue}
                className="flex items-center gap-2 text-sm py-0.5 px-1 rounded cursor-pointer hover:bg-gray-50"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(optValue)}
                  onChange={() => toggle(optValue)}
                  className="accent-primary"
                />
                <span>{optLabel}</span>
              </label>
            );
          })}
        </div>
      </div>
    );
  }

  if (entry.widget === "activity-picker" || entry.widget === "attribute-picker") {
    if (options.length > 0) {
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
    // No candidates loaded yet — fall through to text input below
  }

  if (entry.widget === "number" || entry.widget === "threshold") {
    return (
      <input
        type="number"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? "" : Number(e.target.value))}
        min={entry.min ?? undefined}
        max={entry.max ?? undefined}
        step={entry.step ?? "any"}
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
  // Set when reached by jumping back from a later step; Next then returns
  // there instead of continuing forward (see WizardSteps.js).
  const returnTo = searchParams.get("return_to");

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
        fetch(`/api/admin/tasks?experiment_id=${encodeURIComponent(experimentId)}`),
        fetch(`/api/admin/idioms`),
      ]);
      if (!expRes.ok) throw new Error(`Experiment HTTP ${expRes.status}`);
      if (!tasksRes.ok) throw new Error(`Tasks HTTP ${tasksRes.status}`);
      if (!idiomsRes.ok) throw new Error(`Idioms HTTP ${idiomsRes.status}`);

      const [exp, tasks, idioms] = await Promise.all([expRes.json(), tasksRes.json(), idiomsRes.json()]);

      // An experiment built from an uploaded zip has no dataset and nothing to
      // generate, so this step does not apply to it.
      // Its neighbour, not /overview: this page is only ever reached by
      // stepping back, and bouncing forward would trap the admin in a loop
      // between the two.
      if (exp.bundle_only) {
        router.replace(
          `/admin/experiments/idiom?experiment_id=${encodeURIComponent(experimentId)}` +
          (returnTo ? `&return_to=${encodeURIComponent(returnTo)}` : "")
        );
        return;
      }

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
          const emptyDefault = entry.widget === "select-many" ? [] : "";
          if (vals[entry.key] === undefined) vals[entry.key] = entry.default ?? emptyDefault;
          // If the entry has dataset-backed candidates and the stored value is no longer
          // valid for the current dataset, drop the stale value(s) so the user re-selects.
          // Not for imported tasks: their values are what the images were drawn with.
          if (!isImported(ti) && entry.options?.length > 0) {
            const validValues = entry.options.map((o) => (typeof o === "string" ? o : o.value));
            if (Array.isArray(vals[entry.key])) {
              vals[entry.key] = vals[entry.key].filter((v) => validValues.includes(v));
            } else if (vals[entry.key] && !validValues.includes(vals[entry.key])) {
              vals[entry.key] = entry.default ?? emptyDefault;
            }
          }
        });
        values[ti.task_id] = vals;
      })
    );
    setParamSpecs(specs);
    setParamValues(values);
  }

  function setParamValue(taskId, key, value) {
    setParamValues((prev) => {
      const own = { ...(prev[taskId] || {}), [key]: value };
      // A selection made from another attribute's values is not a selection
      // from this one's: the pairs it holds are no longer on offer, so they
      // would sit in the payload unseen and unremovable.
      for (const entry of paramSpecs[taskId] || []) {
        if (entry.options_filter?.param === key) own[entry.key] = [];
      }
      const next = { ...prev, [taskId]: own };
      const updatedInstances = taskInstances.map((ti) => ({
        ...ti,
        parameters: isImported(ti) ? ti.parameters || {} : next[ti.task_id] || {},
      }));
      queueWizardSave(experimentId, "specify", { task_instances: updatedInstances })
        .catch((e) => showToast(`Failed to save parameters: ${e.message}`, true));
      return next;
    });
  }

  function requiredParamsMissing() {
    const missing = [];
    for (const ti of taskInstances) {
      if (isImported(ti)) continue; // locked, and not what Generate draws
      const spec = paramSpecs[ti.task_id] || [];
      const vals = paramValues[ti.task_id] || {};
      for (const entry of spec) {
        // A hidden entry does not apply, so it cannot be missing — otherwise
        // Generate would block on a control the admin cannot even see.
        if (!entryApplies(entry, vals)) continue;
        const v = vals[entry.key];
        const empty = v === undefined || v === "" || (Array.isArray(v) && v.length === 0);
        if (entry.required && empty) {
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

    // Uploaded images take precedence over generated ones and survive
    // regeneration; say so, or the admin would wonder why nothing changed.
    // Imported tasks are left out: their lock notice already says it.
    try {
      const importedKeys = new Set(
        taskInstances.filter(isImported).map((ti) => tasksById[ti.task_id]?.task_key)
      );
      const res = await fetch(`/api/admin/experiments/${encodeURIComponent(experimentId)}/idioms/overrides`);
      const count = res.ok
        ? ((await res.json()).overrides || []).filter((o) => !importedKeys.has(o.task_key)).length
        : 0;
      if (count > 0 && !window.confirm(
        `${count} image${count !== 1 ? "s were" : " was"} uploaded for this experiment. ` +
        "They will keep being shown instead of the regenerated ones until you revert them on the Overview page. Generate anyway?"
      )) {
        return;
      }
    } catch {
      // Couldn't check — generating is still safe, the uploads just stay in place.
    }

    setGenerating(true);
    try {
      // Imported tasks' parameters are sent as they are; the backend keeps them anyway.
      const updatedInstances = taskInstances.map((ti) => ({
        ...ti,
        parameters: isImported(ti) ? ti.parameters || {} : paramValues[ti.task_id] || {},
      }));

      await queueWizardSave(experimentId, "specify", { task_instances: updatedInstances });

      let res = await fetch(`/api/admin/experiments/${experimentId}/generate`, { method: "POST" });
      if (!res.ok) {
        // Backend rejects invalid parameters with { detail: { message, errors[] } }.
        let msg = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          const detail = body?.detail;
          if (detail?.errors?.length) {
            msg = `${detail.message || "Invalid parameters."} ${detail.errors.join(" ")}`;
          } else if (typeof detail === "string") {
            msg = detail;
          }
        } catch {
          // non-JSON error body — keep the status message
        }
        throw new Error(msg);
      }

      // Reflect the "running" status immediately, then poll for completion.
      // Imported tasks that already have every image are not regenerated.
      setTaskInstances(updatedInstances.map((ti) => (
        isImported(ti) && ti.generation_status === "ready"
          ? ti
          : { ...ti, generation_status: "running", generation_error: null }
      )));
      startPolling();
    } catch (e) {
      setGenerating(false);
      showToast(`Failed to start generation: ${e.message}`, true);
    }
  }

  // Going back to change the idioms or the parameters invalidates the images
  // they produced, so they are thrown away rather than left to be mistaken for
  // the new configuration. Uploaded and imported images are not generated
  // output and are kept (admin.discard_generated_images).
  async function goBackToIdioms() {
    const generated = taskInstances.filter(
      (ti) => !isImported(ti) && ti.generation_status === "ready"
    ).length;
    if (generated > 0 && !window.confirm(
      `Going back discards the images generated for ${generated} task${generated !== 1 ? "s" : ""} — ` +
      "they were drawn with the idioms and parameters you are about to change, and you will have to " +
      "generate again. Uploaded and imported images are kept. Continue?"
    )) return;
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/generated-images`,
        { method: "DELETE" }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `HTTP ${res.status}`);
      }
    } catch (e) {
      // Staying put beats arriving on /idiom with images that no longer match.
      showToast(`Could not discard the generated images: ${e.message}`, true);
      return;
    }
    router.push(
      `/admin/experiments/idiom?experiment_id=${encodeURIComponent(experimentId)}` +
      (returnTo ? `&return_to=${encodeURIComponent(returnTo)}` : "")
    );
  }

  const allReady = taskInstances.length > 0 && taskInstances.every((ti) => ti.generation_status === "ready");
  const importedCount = taskInstances.filter(isImported).length;
  // Nothing left for Generate to draw once every task shows its imported images.
  const nothingToGenerate = taskInstances.length > 0
    && taskInstances.every((ti) => isImported(ti) && ti.generation_status === "ready");

  function handleNext() {
    if (!allReady) {
      showToast("All tasks must finish generating (status: Ready) before continuing.", true);
      return;
    }
    router.push(
      returnTo
        ? `/admin/experiments/${returnTo}?experiment_id=${encodeURIComponent(experimentId)}`
        : `/admin/experiments/answer-format?experiment_id=${encodeURIComponent(experimentId)}`
    );
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader experimentId={experimentId} step="specify" />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        {/* Page heading */}
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2 mb-2">
            <h1 className="font-h1 text-h1 text-primary">Specify &amp; Generate</h1>
          </div>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Set any task-specific hyperparameters, then generate the visualizations for the
            selected idioms. Tasks with no parameters are ready to generate immediately.
          </p>
        </div>

        {/* Tasks whose images were imported keep their locked parameters below.
            Importing itself lives on /new (a whole experiment from a zip) and
            on /overview (swapping images into this one). */}
        {!loading && importedCount > 0 && (
          <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
            <p className="text-xs text-amber-800">
              <span className="font-semibold">
                {importedCount} task{importedCount !== 1 ? "s use" : " uses"} imported images
              </span>{" "}
              — their parameters are locked below. Revert them on the Overview page to edit these again.
            </p>
          </div>
        )}


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
                    {isImported(ti) && (
                      <div className="flex items-start gap-2 text-xs text-amber-900 bg-amber-50 border border-amber-200 rounded-lg px-3 py-2 mb-3">
                        <span className="material-symbols-outlined text-sm">lock</span>
                        <p>
                          These parameters come from the imported images
                          {ti.images_imported_from.experiment_name
                            ? ` ("${ti.images_imported_from.experiment_name}"`
                            : ` (${ti.images_imported_from.file || "an idiom zip"}`}
                          {ti.images_imported_from.exported_at
                            ? `, exported ${formatDate(ti.images_imported_from.exported_at)})`
                            : ")"}{" "}
                          and are locked so that the parameters shown to participants match what the images
                          depict. To change them, discard the import and generate new images.
                        </p>
                      </div>
                    )}
                    {spec.length === 0 ? (
                      <p className="text-xs text-on-surface-variant italic">
                        No parameters required — ready to generate.
                      </p>
                    ) : (
                      // A disabled fieldset disables every control inside it,
                      // whatever widget ParamField renders.
                      <fieldset
                        disabled={isImported(ti)}
                        className={`grid grid-cols-2 gap-4 min-w-0 ${isImported(ti) ? "opacity-60" : ""}`}
                      >
                        {spec.filter((entry) => entryApplies(entry, vals)).map((entry) => (
                          <div key={entry.key} className="flex flex-col gap-1">
                            <label className="text-xs font-semibold text-on-surface">
                              {entry.label || entry.key}
                              {entry.required && <span className="text-error ml-0.5">*</span>}
                            </label>
                            <ParamField
                              entry={entry}
                              value={vals[entry.key]}
                              siblings={vals}
                              onChange={(v) => setParamValue(ti.task_id, entry.key, v)}
                            />
                          </div>
                        ))}
                      </fieldset>
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
          <button
            onClick={goBackToIdioms}
            disabled={generating}
            title={generating ? "Wait for the generation to finish." : undefined}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </button>
          <div className="flex items-center gap-3">
            <button
              onClick={handleGenerate}
              disabled={generating || loading || nothingToGenerate}
              title={nothingToGenerate ? "Every task shows imported images — nothing to generate." : undefined}
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
              {returnTo ? "Save & Return" : "Next"}
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
