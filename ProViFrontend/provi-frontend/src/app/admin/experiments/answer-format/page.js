"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";

function getId(obj) {
  return obj._id || obj.id;
}

// Mirrors app/answer_formats.py; only used if /admin/answer-formats is unreachable.
const FALLBACK_ANSWER_FORMATS = [
  { key: "free-text", label: "Free text", widget: "free_text", needs_options: false },
];
const FALLBACK_NUMBER_KINDS = ["percentage", "integer", "decimal"];

const NUMBER_KIND_HINT = {
  percentage: "0–100, one decimal, shown with a % suffix",
  integer: "whole numbers ≥ 0",
  decimal: "any decimal value",
};

function emptyOption() {
  return { label: "", value: "" };
}

function formatByKey(formats, key) {
  return (formats || []).find((f) => f.key === key);
}

// --- Option editing ------------------------------------------------------
//
// One editor for every option-bearing format (mc-single, mc-multi, rank,
// matrix, number-set). Options are authored by the admin: either imported from
// an event-log source (task-independent — see admin.OPTION_SOURCES) or typed by
// hand. They carry no correctness marking; nothing here is graded.

function OptionRows({ options, onChange, wideValue = false }) {
  function updateRow(i, field, val) {
    onChange(options.map((o, idx) => (idx === i ? { ...o, [field]: val } : o)));
  }
  function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= options.length) return;
    const next = [...options];
    [next[i], next[j]] = [next[j], next[i]];
    onChange(next);
  }
  return (
    <div className="flex flex-col gap-2">
      {options.map((opt, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-xs text-on-surface-variant w-6 text-right tabular-nums">{i + 1}.</span>
          <input
            type="text"
            placeholder="Label (what the participant sees)"
            value={opt.label ?? ""}
            onChange={(e) => updateRow(i, "label", e.target.value)}
            className="flex-1 text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <input
            type="text"
            placeholder="Value"
            value={opt.value ?? ""}
            onChange={(e) => updateRow(i, "value", e.target.value)}
            title={opt.value ?? ""}
            className={`${wideValue ? "w-72" : "w-40"} text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white font-mono text-xs focus:outline-none focus:ring-2 focus:ring-primary/30`}
          />
          <button
            onClick={() => move(i, -1)}
            disabled={i === 0}
            title="Move up"
            className="text-on-surface-variant hover:text-primary disabled:opacity-25"
          >
            <span className="material-symbols-outlined text-sm">arrow_upward</span>
          </button>
          <button
            onClick={() => move(i, 1)}
            disabled={i === options.length - 1}
            title="Move down"
            className="text-on-surface-variant hover:text-primary disabled:opacity-25"
          >
            <span className="material-symbols-outlined text-sm">arrow_downward</span>
          </button>
          <button
            onClick={() => onChange(options.filter((_, idx) => idx !== i))}
            title="Remove"
            className="text-on-surface-variant hover:text-error"
          >
            <span className="material-symbols-outlined text-sm">delete</span>
          </button>
        </div>
      ))}
      <button
        onClick={() => onChange([...options, emptyOption()])}
        className="self-start text-xs font-semibold text-primary hover:underline flex items-center gap-1"
      >
        <span className="material-symbols-outlined text-sm">add</span> Add option
      </button>
    </div>
  );
}

function OptionsEditor({ datasetId, format, options, onChange, showToast }) {
  const [sources, setSources] = useState([]);
  const [source, setSource] = useState("");
  const [granularity, setGranularity] = useState("month");
  const [axisLimit, setAxisLimit] = useState(10);
  const [importing, setImporting] = useState(false);
  const isMatrix = format === "matrix";

  useEffect(() => {
    if (!datasetId) return;
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`/api/admin/datasets/${encodeURIComponent(datasetId)}/option-sources`);
        if (!res.ok) return;
        const data = await res.json();
        if (cancelled) return;
        setSources(data.option_sources || []);
        if (data.matrix_axis_default) setAxisLimit(data.matrix_axis_default);
      } catch {
        // Importing is a convenience; hand-authoring still works without it.
      }
    })();
    return () => { cancelled = true; };
  }, [datasetId]);

  const selected = sources.find((s) => s.source === source);

  async function handleImport() {
    if (!source) return;
    setImporting(true);
    try {
      const qs = new URLSearchParams({ source });
      if (selected?.granularity) qs.set("granularity", granularity);
      if (isMatrix) { qs.set("pairs", "true"); qs.set("axis_limit", String(axisLimit)); }
      const res = await fetch(
        `/api/admin/datasets/${encodeURIComponent(datasetId)}/option-candidates?${qs}`
      );
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const rows = data.options || [];
      if (rows.length === 0) {
        showToast("That source produced no options for this dataset.", true);
        return;
      }
      onChange(rows);
      const truncated = isMatrix && data.axis_total > (data.axis || []).length
        ? ` (axis limited to ${data.axis.length} of ${data.axis_total})`
        : "";
      showToast(`Imported ${rows.length} option${rows.length === 1 ? "" : "s"}${truncated}.`);
    } catch (e) {
      showToast(`Import failed: ${e.message}`, true);
    } finally {
      setImporting(false);
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2 flex-wrap">
        <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Options</p>
        <span className="text-xs text-on-surface-variant">
          {options.length} configured
        </span>
      </div>

      {/* Import from the event log */}
      <div className="flex items-center gap-2 flex-wrap bg-surface-container-low rounded-lg px-3 py-2">
        <span className="text-xs text-on-surface-variant">Import from</span>
        <select
          value={source}
          onChange={(e) => setSource(e.target.value)}
          disabled={!datasetId || sources.length === 0}
          className="text-sm border border-border-subtle rounded-lg px-2 py-1.5 bg-white disabled:opacity-40 focus:outline-none focus:ring-2 focus:ring-primary/30"
        >
          <option value="">Select a source…</option>
          {sources.map((s) => (
            <option key={s.source} value={s.source}>{s.label}</option>
          ))}
        </select>
        {selected?.granularity && (
          <select
            value={granularity}
            onChange={(e) => setGranularity(e.target.value)}
            className="text-sm border border-border-subtle rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          >
            <option value="day">day</option>
            <option value="month">month</option>
            <option value="year">year</option>
          </select>
        )}
        {isMatrix && (
          <label className="text-xs text-on-surface-variant flex items-center gap-1">
            axis
            <input
              type="number"
              min={2}
              max={16}
              value={axisLimit}
              onChange={(e) => setAxisLimit(Number(e.target.value))}
              className="w-16 text-sm border border-border-subtle rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </label>
        )}
        <button
          onClick={handleImport}
          disabled={!source || importing}
          className="text-xs font-semibold text-primary hover:underline disabled:opacity-40 disabled:no-underline flex items-center gap-1"
        >
          <span className="material-symbols-outlined text-sm">download</span>
          {importing ? "Importing…" : options.length > 0 ? "Replace options" : "Import"}
        </button>
        {!datasetId && (
          <span className="text-xs text-on-surface-variant italic">
            No dataset assigned to this task — add options by hand.
          </span>
        )}
      </div>

      {options.length === 0 ? (
        <p className="text-xs text-on-surface-variant italic">
          No options yet — import a set from the event log, or add them by hand.
        </p>
      ) : null}

      <OptionRows options={options} onChange={onChange} wideValue={isMatrix} />

      {isMatrix && options.length > 0 && (
        <p className="text-[11px] text-on-surface-variant italic">
          Matrix cells use an <span className="font-mono">a__b</span> value token; the participant grid
          derives both axes from it. Hand-written rows must follow the same shape.
        </p>
      )}
    </div>
  );
}

function NumberKindSelector({ kinds, value, onChange }) {
  return (
    <div className="flex items-center gap-2 flex-wrap">
      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">Number type</p>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
        className="text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
      >
        {kinds.map((k) => (
          <option key={k} value={k}>{k}</option>
        ))}
      </select>
      <span className="text-xs text-on-surface-variant italic">
        {NUMBER_KIND_HINT[value] || ""}
      </span>
    </div>
  );
}

function RubricPanel({ rubric }) {
  return (
    <div className="flex flex-col gap-1">
      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
        Grading rubric
      </p>
      {rubric ? (
        <p className="text-sm text-on-surface whitespace-pre-wrap bg-surface-container-low rounded-lg px-3 py-2">
          {rubric}
        </p>
      ) : (
        <p className="text-xs text-on-surface-variant italic bg-surface-container-low rounded-lg px-3 py-2">
          No rubric authored for this task yet — add a RUBRIC constant to the task module to display one here.
        </p>
      )}
      <p className="text-[11px] text-on-surface-variant italic">
        Reference text for manually coding answers. Defined per task, shared across experiments, read-only here.
      </p>
    </div>
  );
}

function FormatSelector({ formats, value, onChange }) {
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      className="text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
    >
      <option value="" disabled>Select format…</option>
      {formats.map((f) => (
        <option key={f.key} value={f.key}>{f.label || f.key}</option>
      ))}
    </select>
  );
}

function AnswerFormatContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [taskInstances, setTaskInstances] = useState([]);
  const [tasksById, setTasksById] = useState({});
  const [idiomsById, setIdiomsById] = useState({});
  const [answerFormats, setAnswerFormats] = useState(FALLBACK_ANSWER_FORMATS);
  const [numberKinds, setNumberKinds] = useState(FALLBACK_NUMBER_KINDS);
  const [defaultNumberKind, setDefaultNumberKind] = useState("decimal");
  const [rubricsByTask, setRubricsByTask] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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
    setLoading(true);
    try {
      const [expRes, tasksRes, idiomsRes, formatsRes] = await Promise.all([
        fetch(`/api/admin/experiments/${experimentId}`),
        fetch(`/api/admin/tasks`),
        fetch(`/api/admin/idioms`),
        fetch(`/api/admin/answer-formats`),
      ]);
      if (!expRes.ok) throw new Error(`Experiment HTTP ${expRes.status}`);
      if (!tasksRes.ok) throw new Error(`Tasks HTTP ${tasksRes.status}`);
      if (!idiomsRes.ok) throw new Error(`Idioms HTTP ${idiomsRes.status}`);

      const [exp, tasks, idioms] = await Promise.all([
        expRes.json(), tasksRes.json(), idiomsRes.json(),
      ]);

      if (formatsRes.ok) {
        const fmt = await formatsRes.json();
        if (Array.isArray(fmt.answer_formats) && fmt.answer_formats.length > 0) {
          setAnswerFormats(fmt.answer_formats);
        }
        if (Array.isArray(fmt.number_kinds) && fmt.number_kinds.length > 0) {
          setNumberKinds(fmt.number_kinds);
        }
        if (fmt.default_number_kind) setDefaultNumberKind(fmt.default_number_kind);
      }

      const tMap = {};
      tasks.forEach((t) => { tMap[getId(t)] = t; });
      setTasksById(tMap);

      const iMap = {};
      idioms.forEach((i) => { iMap[getId(i)] = i; });
      setIdiomsById(iMap);

      const instances = (exp.task_instances || []).map((ti) => ({
        ...ti,
        answer_format: ti.answer_format ?? null,
        number_kind: ti.number_kind ?? null,
        answer_options: ti.answer_options ?? [],
      }));
      setTaskInstances(instances);
      await loadRubrics(instances, tMap);
    } catch (e) {
      showToast(`Could not load experiment: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function loadRubrics(instances, tMap) {
    const rubrics = {};
    await Promise.all(
      instances.map(async (ti) => {
        const taskKey = tMap[ti.task_id]?.task_key;
        if (!taskKey) return;
        try {
          const res = await fetch(`/api/admin/tasks/${encodeURIComponent(taskKey)}/rubric`);
          if (res.ok) rubrics[ti.task_id] = (await res.json()).rubric ?? null;
        } catch {
          // A missing rubric is fine — the panel says so.
        }
      })
    );
    setRubricsByTask(rubrics);
  }

  function patchInstance(taskId, patch) {
    setTaskInstances((prev) =>
      prev.map((ti) => (ti.task_id === taskId ? { ...ti, ...patch } : ti))
    );
  }

  function handleFormatChange(taskId, formatKey) {
    const fmt = formatByKey(answerFormats, formatKey);
    setTaskInstances((prev) =>
      prev.map((ti) => {
        if (ti.task_id !== taskId) return ti;
        return {
          ...ti,
          answer_format: formatKey,
          // Drop state the new format cannot use, so nothing stale is persisted.
          answer_options: fmt?.needs_options ? (ti.answer_options || []) : [],
          number_kind: fmt?.numeric ? (ti.number_kind || defaultNumberKind) : null,
        };
      })
    );
  }

  async function persist() {
    const res = await fetch(`/api/admin/experiments/${experimentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_instances: taskInstances }),
    });
    if (!res.ok) throw new Error(await res.text());
  }

  async function handleSave() {
    setSaving(true);
    try {
      await persist();
      showToast("Answer formats saved.");
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, true);
    } finally {
      setSaving(false);
    }
  }

  // A format alone isn't enough: an option-bearing format with no options would
  // show the participant an empty question.
  const incomplete = taskInstances.filter((ti) => {
    if (!ti.answer_format) return true;
    const fmt = formatByKey(answerFormats, ti.answer_format);
    return !!fmt?.needs_options && (ti.answer_options || []).length === 0;
  });
  const ready = taskInstances.length > 0 && incomplete.length === 0;

  async function handleNext() {
    if (!ready) {
      showToast(
        "Every task needs an answer format, and option-based formats need at least one option.",
        true
      );
      return;
    }
    setSaving(true);
    try {
      await persist();
      router.push(`/admin/experiments/overview?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Answer Format</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Choose how participants answer each task. Every format is available to every task.
            Formats that present a closed set need options, which you can import from the event log
            or write by hand.
          </p>
        </div>

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
              const fmt = formatByKey(answerFormats, ti.answer_format);
              return (
                <div
                  key={ti.task_id}
                  className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden"
                >
                  <div className="border-l-4 border-primary p-5 flex items-start gap-3">
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

                  <div className="p-5 pt-3 border-t border-border-subtle flex flex-col gap-4">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                        Answer format
                      </p>
                      <FormatSelector
                        formats={answerFormats}
                        value={ti.answer_format}
                        onChange={(key) => handleFormatChange(ti.task_id, key)}
                      />
                    </div>

                    {!ti.answer_format ? (
                      <p className="text-xs text-on-surface-variant italic">
                        Select an answer format to configure this task.
                      </p>
                    ) : (
                      <>
                        {fmt?.numeric && (
                          <NumberKindSelector
                            kinds={numberKinds}
                            value={ti.number_kind || defaultNumberKind}
                            onChange={(kind) => patchInstance(ti.task_id, { number_kind: kind })}
                          />
                        )}
                        {fmt?.needs_options && (
                          <OptionsEditor
                            datasetId={ti.dataset_id}
                            format={ti.answer_format}
                            options={ti.answer_options || []}
                            onChange={(options) => patchInstance(ti.task_id, { answer_options: options })}
                            showToast={showToast}
                          />
                        )}
                      </>
                    )}

                    <RubricPanel rubric={rubricsByTask[ti.task_id]} />
                  </div>
                </div>
              );
            })
          )}
        </div>
      </main>

      <div className="border-t border-border-subtle bg-white sticky bottom-0">
        <div className="max-w-[1140px] mx-auto px-8 py-4 flex justify-between items-center">
          <Link
            href={`/admin/experiments/specify${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <div className="flex items-center gap-3">
            {!loading && incomplete.length > 0 && (
              <span className="text-xs text-on-surface-variant italic">
                {incomplete.length} task{incomplete.length === 1 ? "" : "s"} still incomplete
              </span>
            )}
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="flex items-center gap-2 text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-sm">save</span>
              Save
            </button>
            <button
              onClick={handleNext}
              disabled={!ready || saving || loading}
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

export default function AnswerFormatPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface">
          <span className="text-on-surface-variant text-sm">Loading…</span>
        </div>
      }
    >
      <AnswerFormatContent />
    </Suspense>
  );
}
