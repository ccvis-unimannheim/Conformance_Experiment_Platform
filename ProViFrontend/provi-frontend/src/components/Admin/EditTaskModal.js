"use client";

import { useState } from "react";

// Reusable "Edit Task" modal used by the task-selection and experiment
// overview admin pages. The caller owns the actual PATCH request (via
// onSave) since the two pages talk to the backend through different base
// URLs (direct BASE_URL vs. the /api/admin proxy).
export default function EditTaskModal({ task, onClose, onSave }) {
  const [label, setLabel] = useState(task.label || "");
  const [description, setDescription] = useState(task.description || "");
  const [answerType, setAnswerType] = useState(task.answer_type || "single_choice");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function handleSave() {
    if (!label.trim()) {
      setError("Label is required.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      await onSave({
        label: label.trim(),
        description: description.trim(),
        answer_type: answerType,
      });
      onClose();
    } catch (e) {
      setError(`Error: ${e.message}`);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div className="bg-white rounded-xl p-6 w-full max-w-[500px] shadow-xl flex flex-col gap-4">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-bold text-on-surface">Edit Task</h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <div className="flex flex-col gap-3">
          <div>
            <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
              Task Key
            </label>
            <input
              type="text"
              value={task.task_key}
              disabled
              className="w-full border border-border-subtle rounded px-3 py-2 text-sm bg-surface-container text-on-surface-variant"
            />
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
              Label / Question *
            </label>
            <textarea
              rows={3}
              value={label}
              onChange={(e) => setLabel(e.target.value)}
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
              className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary resize-none"
            />
          </div>
          <div>
            <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
              Answer Type
            </label>
            <select
              value={answerType}
              onChange={(e) => setAnswerType(e.target.value)}
              className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
            >
              <option value="single_choice">Single Choice</option>
              <option value="multiple_choice">Multiple Choice</option>
              <option value="numeric">Numeric</option>
              <option value="text">Free Text</option>
            </select>
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
            className="text-sm text-on-surface-variant border border-border-subtle px-4 py-2 rounded hover:bg-surface-container transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="text-sm bg-primary text-white px-5 py-2 rounded font-semibold hover:bg-primary-container transition-colors disabled:opacity-60"
          >
            {saving ? "Saving…" : "Save Changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
