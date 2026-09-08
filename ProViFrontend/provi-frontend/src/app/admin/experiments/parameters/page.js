"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";
import { saveWizardStep } from "../../../../utils/wizardSave";

function getId(obj) {
  return obj._id || obj.id;
}

function rowsEqual(a, b) {
  return (
    a.enabled === b.enabled &&
    String(a.default ?? "") === String(b.default ?? "") &&
    !!a.required === !!b.required &&
    String(a.min ?? "") === String(b.min ?? "") &&
    String(a.max ?? "") === String(b.max ?? "") &&
    String(a.step ?? "") === String(b.step ?? "")
  );
}

// One parameter's configuration for one task. Kept as local draft state so
// edits don't fire a save on every keystroke — only on explicit "Save".
function ParamRow({ param, onSave }) {
  const [draft, setDraft] = useState(param);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(param);
  }, [param]);

  const dirty = !rowsEqual(draft, param);
  const isNumeric = param.widget === "threshold";

  async function save() {
    setSaving(true);
    try {
      await onSave(draft);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid grid-cols-[minmax(0,1fr)_auto_auto_auto_auto_auto] items-center gap-3 py-2.5 border-t border-border-subtle first:border-t-0">
      <div className="flex items-start gap-2 min-w-0">
        <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded flex-shrink-0 mt-0.5">
          {param.key}
        </span>
        <span className="text-xs text-on-surface-variant">{param.label}</span>
      </div>

      <label className="flex items-center gap-1.5 text-xs text-on-surface cursor-pointer select-none">
        <input
          type="checkbox"
          checked={!!draft.enabled}
          onChange={(e) => setDraft((d) => ({ ...d, enabled: e.target.checked }))}
        />
        Enabled
      </label>

      <input
        type={isNumeric ? "number" : "text"}
        value={draft.default ?? ""}
        onChange={(e) => setDraft((d) => ({ ...d, default: e.target.value }))}
        placeholder="default"
        className="w-28 text-xs border border-border-subtle rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
      />

      <label className="flex items-center gap-1.5 text-xs text-on-surface cursor-pointer select-none">
        <input
          type="checkbox"
          checked={!!draft.required}
          onChange={(e) => setDraft((d) => ({ ...d, required: e.target.checked }))}
        />
        Required
      </label>

      {isNumeric ? (
        <div className="flex items-center gap-1">
          <input
            type="number"
            value={draft.min ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, min: e.target.value }))}
            placeholder="min"
            className="w-16 text-xs border border-border-subtle rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <input
            type="number"
            value={draft.max ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, max: e.target.value }))}
            placeholder="max"
            className="w-16 text-xs border border-border-subtle rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <input
            type="number"
            value={draft.step ?? ""}
            onChange={(e) => setDraft((d) => ({ ...d, step: e.target.value }))}
            placeholder="step"
            className="w-16 text-xs border border-border-subtle rounded-lg px-2 py-1.5 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>
      ) : (
        <div />
      )}

      <button
        onClick={save}
        disabled={!dirty || saving}
        className="justify-self-end text-xs font-semibold text-primary border border-primary/30 px-3 py-1.5 rounded hover:bg-blue-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {saving ? "Saving…" : "Save"}
      </button>
    </div>
  );
}

function TaskParamCard({ task, params, sharedWith, onSaveParam }) {
  const [expanded, setExpanded] = useState(false);
  const enabledParams = params.filter((p) => p.enabled);
  const disabledParams = params.filter((p) => !p.enabled);

  return (
    <div className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden">
      <div className="border-l-4 border-primary p-5">
        <div className="flex items-start gap-3">
          <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded flex-shrink-0 mt-0.5">
            {task.task_key}
          </span>
          <p className="text-sm font-semibold text-on-surface leading-snug">{task.label}</p>
        </div>
      </div>

      <div className="px-5 pb-4">
        {params.length === 0 ? (
          <p className="text-xs text-on-surface-variant italic py-3">
            This task has no configurable parameters.
          </p>
        ) : (
          <>
            {enabledParams.length === 0 && (
              <p className="text-xs text-on-surface-variant italic py-3">
                No parameters enabled for this task.
              </p>
            )}
            {enabledParams.map((param) => (
              <div key={param.key}>
                <ParamRow param={param} onSave={(draft) => onSaveParam(param.key, draft)} />
                {sharedWith[param.key]?.length > 0 && (
                  <p className="text-[10px] text-on-surface-variant italic pb-2">
                    Also used by: {sharedWith[param.key].join(", ")}
                  </p>
                )}
              </div>
            ))}

            {disabledParams.length > 0 && (
              <div className="border-t border-border-subtle mt-1 pt-2">
                <button
                  onClick={() => setExpanded((v) => !v)}
                  className="flex items-center gap-1 text-xs font-semibold text-primary hover:underline"
                >
                  <span className="material-symbols-outlined text-sm">
                    {expanded ? "expand_less" : "add"}
                  </span>
                  {expanded
                    ? "Hide other parameters"
                    : `Enable another parameter (${disabledParams.length} available)`}
                </button>
                {expanded && (
                  <div className="mt-2">
                    {disabledParams.map((param) => (
                      <div key={param.key}>
                        <ParamRow param={param} onSave={(draft) => onSaveParam(param.key, draft)} />
                        {sharedWith[param.key]?.length > 0 && (
                          <p className="text-[10px] text-on-surface-variant italic pb-2">
                            Also used by: {sharedWith[param.key].join(", ")}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

function ParameterMatchingContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [selectedTasks, setSelectedTasks] = useState([]);
  const [paramsByTaskKey, setParamsByTaskKey] = useState({});
  const [sharedWithByTaskKey, setSharedWithByTaskKey] = useState({});
  const [taskIdByKey, setTaskIdByKey] = useState({});
  const [loading, setLoading] = useState(true);

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
    saveWizardStep(experimentId, "parameters", {}).catch(() => {});
    init();
  }, [experimentId]);

  async function init() {
    setLoading(true);
    let taskIds = [];
    try {
      const res = await fetch(`/api/admin/experiments`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const exps = await res.json();
      const draft = exps.find((e) => getId(e) === experimentId);
      if (!draft) throw new Error("Draft experiment not found.");
      taskIds = (draft.task_configs || []).map((tc) => tc.task_id);
    } catch (e) {
      showToast(`Could not load draft experiment: ${e.message}`, true);
      setLoading(false);
      return;
    }

    try {
      const [tasksRes, catalogRes] = await Promise.all([
        fetch("/api/admin/tasks"),
        fetch("/api/admin/param-catalog"),
      ]);
      if (!tasksRes.ok) throw new Error(`tasks HTTP ${tasksRes.status}`);
      if (!catalogRes.ok) throw new Error(`param-catalog HTTP ${catalogRes.status}`);
      const allTasks = await tasksRes.json();
      const catalogData = await catalogRes.json();

      const tasks = allTasks.filter((t) => taskIds.includes(getId(t)));
      if (tasks.length === 0) {
        router.replace(`/admin/experiments/idiom?experiment_id=${encodeURIComponent(experimentId)}`);
        return;
      }
      setSelectedTasks(tasks);

      const idMap = {};
      allTasks.forEach((t) => { idMap[t.task_key] = getId(t); });
      setTaskIdByKey(idMap);

      const selectedTaskKeys = new Set(tasks.map((t) => t.task_key));
      const byTask = {};
      const sharedWith = {};
      selectedTaskKeys.forEach((tk) => { byTask[tk] = []; sharedWith[tk] = {}; });

      (catalogData.parameters || []).forEach((param) => {
        const otherTaskKeys = param.tasks
          .filter((row) => !selectedTaskKeys.has(row.task_key) && row.enabled)
          .map((row) => row.task_key);

        param.tasks.forEach((row) => {
          if (!selectedTaskKeys.has(row.task_key)) return;
          byTask[row.task_key].push({
            key: param.key,
            label: param.label,
            widget: param.widget,
            source: param.source,
            enabled: row.enabled,
            default: row.default,
            required: row.required,
            min: row.min,
            max: row.max,
            step: row.step,
          });
          sharedWith[row.task_key][param.key] = otherTaskKeys;
        });
      });

      setParamsByTaskKey(byTask);
      setSharedWithByTaskKey(sharedWith);
    } catch (e) {
      showToast(`Could not load parameters: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function handleSaveParam(taskKey, paramKey, draftRow) {
    const nextParams = (paramsByTaskKey[taskKey] || []).map((p) =>
      p.key === paramKey ? draftRow : p
    );

    const taskId = taskIdByKey[taskKey];
    if (!taskId) {
      showToast(`Unknown task '${taskKey}'.`, true);
      return;
    }

    const overrides = {};
    nextParams.forEach((p) => {
      overrides[p.key] = {
        enabled: p.enabled,
        default: p.default,
        required: p.required,
        min: p.min,
        max: p.max,
        step: p.step,
      };
    });

    try {
      const res = await fetch(`/api/admin/tasks/${encodeURIComponent(taskId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ param_overrides: overrides }),
      });
      if (!res.ok) throw new Error(await res.text());
      setParamsByTaskKey((prev) => ({ ...prev, [taskKey]: nextParams }));
      showToast("Parameter setting saved.");
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, true);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Parameter Matching</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            For each task you selected, every parameter declared by any task is available to
            enable, with its own default value, required flag, and range. Enabling a parameter a
            task&apos;s own generation code doesn&apos;t read is harmless but has no effect — the
            value is collected on /specify but ignored at generation time. These settings are
            shared across every experiment, not just this one.
          </p>
        </div>

        {loading ? (
          <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
            <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
              hourglass_empty
            </span>
            Loading…
          </div>
        ) : selectedTasks.length === 0 ? (
          <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
            <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
              inbox
            </span>
            No tasks selected for this experiment.
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {selectedTasks.map((task) => (
              <TaskParamCard
                key={getId(task)}
                task={task}
                params={paramsByTaskKey[task.task_key] || []}
                sharedWith={sharedWithByTaskKey[task.task_key] || {}}
                onSaveParam={(paramKey, draft) => handleSaveParam(task.task_key, paramKey, draft)}
              />
            ))}
          </div>
        )}
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
          <button
            onClick={() => router.push(`/admin/experiments/specify?experiment_id=${encodeURIComponent(experimentId)}`)}
            className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95"
          >
            Next
            <span className="material-symbols-outlined text-sm">chevron_right</span>
          </button>
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

export default function ParameterMatchingPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface">
          <span className="text-on-surface-variant text-sm">Loading…</span>
        </div>
      }
    >
      <ParameterMatchingContent />
    </Suspense>
  );
}
