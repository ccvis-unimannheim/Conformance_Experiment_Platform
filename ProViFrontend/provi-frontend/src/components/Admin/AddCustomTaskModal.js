"use client";

import { useState } from "react";

// "Add Task" modal for /admin/experiments/task. The task is created for the
// current experiment only (POST /admin/experiments/{id}/custom-tasks) — it is
// not added to the shared task list other experiments choose from.
export default function AddCustomTaskModal({ experimentId, onClose, onCreated }) {
  const [label, setLabel] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!label.trim()) {
      setError("The task question is required.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/custom-tasks`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ label: label.trim(), description: description.trim() }),
        }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      await onCreated(await res.json());
    } catch (e) {
      setError(`Error: ${e.message}`);
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget && !saving) onClose(); }}
    >
      <div className="bg-white rounded-xl p-6 w-full max-w-[500px] shadow-xl flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-bold text-on-surface">Add Task</h3>
          <button onClick={onClose} disabled={saving} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <p className="text-xs text-on-surface-variant leading-relaxed">
          This task is added to <strong>this experiment only</strong> and is not saved to the task
          list of other experiments. It has no generated visualizations — in the next step, use{" "}
          <strong>Upload Custom Idiom</strong> to add at least one image or SVG for it.
        </p>
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
              Task Question *
            </label>
            <textarea
              rows={3}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="e.g. Which activity is skipped most often?"
              className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
            />
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
              Description
            </label>
            <textarea
              rows={2}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Brief explanation of the task…"
              className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
            />
          </div>
        </div>
        {error && (
          <div className="text-error text-xs bg-error-container px-3 py-2 rounded">
            {error}
          </div>
        )}
        <div className="flex gap-2 justify-end pt-1">
          <button
            onClick={onClose}
            disabled={saving}
            className="text-sm text-on-surface-variant border border-border-subtle px-4 py-2 rounded hover:bg-surface-container transition-colors disabled:opacity-60"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="text-sm bg-primary text-white px-5 py-2 rounded font-semibold hover:bg-primary-container transition-colors disabled:opacity-60"
          >
            {saving ? "Adding…" : "Add Task"}
          </button>
        </div>
      </div>
    </div>
  );
}
