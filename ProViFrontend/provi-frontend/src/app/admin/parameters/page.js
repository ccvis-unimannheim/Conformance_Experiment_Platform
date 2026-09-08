"use client";

import { useState, useEffect, useCallback } from "react";
import AdminNav from "../../../components/Admin/AdminNav";
import Toast from "../../../components/Admin/Toast";

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

// One task's configuration of one shared parameter. Kept as local draft state
// so edits don't fire a save on every keystroke — only on explicit "Save".
function ParamTaskRow({ param, row, onSave }) {
  const [draft, setDraft] = useState(row);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(row);
  }, [row]);

  const dirty = !rowsEqual(draft, row);
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
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded flex-shrink-0">
          {row.task_key}
        </span>
        <span className="text-xs text-on-surface-variant truncate">{row.task_label}</span>
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

function ParamCard({ param, onSaveRow }) {
  return (
    <div className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden">
      <div className="border-l-4 border-primary p-5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded">
            {param.key}
          </span>
          <span className="text-sm font-semibold text-on-surface">{param.label}</span>
          <span className="text-[10px] uppercase tracking-wider font-semibold text-on-surface-variant bg-surface-container px-2 py-0.5 rounded-full">
            {param.widget}
          </span>
          {param.source && (
            <span className="text-[10px] text-on-surface-variant italic">source: {param.source}</span>
          )}
        </div>
        <p className="text-xs text-on-surface-variant mt-1">
          Shared by {param.tasks.length} task{param.tasks.length !== 1 ? "s" : ""} — only these tasks&apos;
          generation code reads this parameter, so it can&apos;t be attached to any other task.
        </p>
      </div>

      <div className="px-5 pb-4">
        {param.tasks.map((row) => (
          <ParamTaskRow
            key={row.task_key}
            param={param}
            row={row}
            onSave={(draft) => onSaveRow(param.key, draft)}
          />
        ))}
      </div>
    </div>
  );
}

export default function ParameterMatchingPage() {
  const [catalog, setCatalog] = useState([]);
  const [taskIdByKey, setTaskIdByKey] = useState({});
  const [loading, setLoading] = useState(true);

  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => setToast((t) => ({ ...t, visible: false })), []);

  useEffect(() => {
    init();
  }, []);

  async function init() {
    setLoading(true);
    try {
      const [catalogRes, tasksRes] = await Promise.all([
        fetch("/api/admin/param-catalog"),
        fetch("/api/admin/tasks"),
      ]);
      if (!catalogRes.ok) throw new Error(`param-catalog HTTP ${catalogRes.status}`);
      if (!tasksRes.ok) throw new Error(`tasks HTTP ${tasksRes.status}`);
      const catalogData = await catalogRes.json();
      const tasks = await tasksRes.json();

      const idMap = {};
      tasks.forEach((t) => { idMap[t.task_key] = getId(t); });

      setCatalog(catalogData.parameters || []);
      setTaskIdByKey(idMap);
    } catch (e) {
      showToast(`Could not load parameters: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  function buildOverridesForTask(nextCatalog, taskKey) {
    const overrides = {};
    nextCatalog.forEach((param) => {
      const row = param.tasks.find((t) => t.task_key === taskKey);
      if (!row) return;
      overrides[param.key] = {
        enabled: row.enabled,
        default: row.default,
        required: row.required,
        min: row.min,
        max: row.max,
        step: row.step,
      };
    });
    return overrides;
  }

  async function handleSaveRow(paramKey, draftRow) {
    const taskKey = draftRow.task_key;
    const nextCatalog = catalog.map((param) =>
      param.key !== paramKey
        ? param
        : { ...param, tasks: param.tasks.map((t) => (t.task_key === taskKey ? draftRow : t)) }
    );

    const taskId = taskIdByKey[taskKey];
    if (!taskId) {
      showToast(`Unknown task '${taskKey}'.`, true);
      return;
    }

    try {
      const res = await fetch(`/api/admin/tasks/${encodeURIComponent(taskId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ param_overrides: buildOverridesForTask(nextCatalog, taskKey) }),
      });
      if (!res.ok) throw new Error(await res.text());
      setCatalog(nextCatalog);
      showToast("Parameter setting saved.");
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, true);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <AdminNav activeLink="parameters" />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Parameter Matching</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Every task&apos;s hyperparameters, grouped by parameter — so you can see at a glance which
            tasks already share a parameter (e.g. an outcome activity) and enable, disable, or
            reconfigure it per task. A parameter can only be turned on for a task whose own
            generation code already reads it.
          </p>
        </div>

        {loading ? (
          <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
            <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
              hourglass_empty
            </span>
            Loading…
          </div>
        ) : catalog.length === 0 ? (
          <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
            <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
              inbox
            </span>
            No task parameters found.
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {catalog.map((param) => (
              <ParamCard key={param.key} param={param} onSaveRow={handleSaveRow} />
            ))}
          </div>
        )}
      </main>

      <Toast
        message={toast.message}
        isError={toast.isError}
        visible={toast.visible}
        onHide={hideToast}
      />
    </div>
  );
}
