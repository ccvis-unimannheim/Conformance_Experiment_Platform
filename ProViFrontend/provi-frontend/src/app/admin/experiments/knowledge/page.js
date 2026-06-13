"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AdminNav from "../../../../components/Admin/AdminNav";

// ── Add Question Modal ──────────────────────────────────────────────────────

function AddQuestionModal({ onClose, onSaved }) {
  const [sectionTitle, setSectionTitle] = useState("Conformance Checking Knowledge");
  const [text, setText] = useState("");
  const [options, setOptions] = useState(["", ""]);
  const [includeIdk, setIncludeIdk] = useState(true);
  const [correctIndex, setCorrectIndex] = useState(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function setOption(i, val) {
    setOptions((prev) => prev.map((o, idx) => (idx === i ? val : o)));
  }
  function addOption() {
    if (options.length < 6) setOptions((prev) => [...prev, ""]);
  }
  function removeOption(i) {
    if (options.length <= 2) return;
    setOptions((prev) => prev.filter((_, idx) => idx !== i));
    if (correctIndex === i) setCorrectIndex(null);
    else if (correctIndex > i) setCorrectIndex(correctIndex - 1);
  }

  async function handleSave() {
    setError("");
    if (!text.trim()) { setError("Question text is required."); return; }
    if (options.some((o) => !o.trim())) { setError("All options must be non-empty."); return; }

    setSaving(true);
    try {
      const res = await fetch("/api/admin/knowledge-questions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          section_title: sectionTitle.trim(),
          text: text.trim(),
          options: options.map((o) => o.trim()),
          include_idk: includeIdk,
          correct_option_index: correctIndex,
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      const data = await res.json();
      onSaved(data.question_id);
    } catch (e) {
      setError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl shadow-xl p-8 w-full max-w-2xl mx-4 flex flex-col gap-5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-h2 text-primary">Add Knowledge Question</h2>
          <button type="button" onClick={onClose} disabled={saving}
            className="text-on-surface-variant hover:text-on-surface disabled:opacity-30"
            aria-label="Close">
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-label-caps text-on-surface-variant">Section Title</label>
          <input value={sectionTitle} onChange={(e) => setSectionTitle(e.target.value)}
            className="border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40" />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-label-caps text-on-surface-variant">Question Text</label>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3}
            className="border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40 resize-none" />
        </div>

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <label className="text-label-caps text-on-surface-variant">Options (select correct answer)</label>
            {options.length < 6 && (
              <button type="button" onClick={addOption}
                className="text-xs text-primary hover:underline flex items-center gap-1">
                <span className="material-symbols-outlined text-sm">add</span>
                Add option
              </button>
            )}
          </div>
          {options.map((opt, i) => (
            <div key={i} className="flex items-center gap-2">
              <input
                type="radio"
                name="correct"
                checked={correctIndex === i}
                onChange={() => setCorrectIndex(i)}
                className="w-4 h-4 text-primary cursor-pointer flex-shrink-0"
                title="Mark as correct"
              />
              <input value={opt} onChange={(e) => setOption(i, e.target.value)}
                placeholder={`Option ${i + 1}`}
                className="flex-1 border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40" />
              <button type="button" onClick={() => removeOption(i)}
                disabled={options.length <= 2}
                className="text-on-surface-variant hover:text-error disabled:opacity-30 transition-colors">
                <span className="material-symbols-outlined text-sm">remove_circle</span>
              </button>
            </div>
          ))}
          <p className="text-[11px] text-on-surface-variant">Click a radio button to mark the correct answer (leave unselected = unscored).</p>
        </div>

        <label className="flex items-center gap-3 cursor-pointer select-none">
          <input type="checkbox" checked={includeIdk} onChange={(e) => setIncludeIdk(e.target.checked)}
            className="w-4 h-4 text-primary rounded border-outline-variant cursor-pointer" />
          <span className="text-sm text-on-surface">Append "I don't know" option</span>
        </label>

        {error && <p className="text-body-sm text-error">{error}</p>}

        <div className="flex justify-end gap-3 pt-4 border-t border-surface-variant">
          <button type="button" onClick={onClose} disabled={saving}
            className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40">
            Cancel
          </button>
          <button type="button" onClick={handleSave} disabled={saving}
            className="flex items-center gap-2 text-button bg-primary text-on-primary px-8 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-50">
            {saving ? "Saving…" : "Save Question"}
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────────────────────

export default function KnowledgeSetupPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [questions, setQuestions] = useState([]);
  const [selectedIds, setSelectedIds] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [showAddModal, setShowAddModal] = useState(false);

  const fetchQuestions = useCallback(() => {
    setLoading(true);
    fetch("/api/admin/knowledge-questions")
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => {
        const qs = Array.isArray(data) ? data : [];
        setQuestions(qs);
        // Pre-select all by default (empty list = all system; for new wizard step, select all)
        setSelectedIds((prev) => {
          if (prev.size > 0) return prev;
          return new Set(qs.map((q) => q._id));
        });
      })
      .catch(() => setError("Failed to load knowledge questions."))
      .finally(() => setLoading(false));
  }, []);

  // Also load the experiment's existing knowledge_question_ids to pre-populate selection
  useEffect(() => {
    if (!experimentId) return;
    Promise.all([
      fetch("/api/admin/knowledge-questions").then((r) => r.ok ? r.json() : []),
      fetch(`/api/admin/experiments`).then((r) => r.ok ? r.json() : []),
    ])
      .then(([qs, exps]) => {
        const allQs = Array.isArray(qs) ? qs : [];
        setQuestions(allQs);
        const exp = Array.isArray(exps) ? exps.find((e) => e._id === experimentId) : null;
        const existingIds = exp?.knowledge_question_ids;
        if (existingIds && existingIds.length > 0) {
          setSelectedIds(new Set(existingIds));
        } else {
          // Default: select all questions
          setSelectedIds(new Set(allQs.map((q) => q._id)));
        }
      })
      .catch(() => setError("Failed to load data."))
      .finally(() => setLoading(false));
  }, [experimentId]);

  function toggleQuestion(id) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  async function handleDelete(qid) {
    const res = await fetch(`/api/admin/knowledge-questions/${encodeURIComponent(qid)}`, { method: "DELETE" });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      setSaveError(typeof data.detail === "string" ? data.detail : "Failed to delete question.");
      return;
    }
    setQuestions((prev) => prev.filter((q) => q._id !== qid));
    setSelectedIds((prev) => { const n = new Set(prev); n.delete(qid); return n; });
  }

  async function handleNext() {
    if (!experimentId) {
      router.push("/admin/experiments/task");
      return;
    }
    setSaveError(null);
    setSaving(true);
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/knowledge-questions`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ knowledge_question_ids: Array.from(selectedIds) }),
        }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      router.push(`/admin/experiments/task?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  }

  function onQuestionSaved(newId) {
    setShowAddModal(false);
    // Reload questions and auto-select the new one
    fetch("/api/admin/knowledge-questions")
      .then((r) => r.ok ? r.json() : [])
      .then((data) => {
        const qs = Array.isArray(data) ? data : [];
        setQuestions(qs);
        setSelectedIds((prev) => { const n = new Set(prev); n.add(newId); return n; });
      });
  }

  const systemQs = questions.filter((q) => q.is_system);
  const customQs = questions.filter((q) => !q.is_system);

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="experiment-setup" />

      <main className="flex-grow max-w-[900px] mx-auto w-full px-6 py-12 pb-32">
        <div className="mb-12">
          <h1 className="text-h1 text-primary mb-2">Knowledge Questions</h1>
          <p className="text-body-lg text-secondary">
            Choose which knowledge questions participants will answer before the experiment.
            System questions cannot be deleted. Uncheck any you want to skip.
          </p>
        </div>

        {loading && <p className="text-body-sm text-secondary">Loading questions…</p>}
        {error && <p className="text-body-sm text-error">{error}</p>}

        {!loading && !error && (
          <div className="space-y-section-gap">

            {/* System questions */}
            <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
              <div className="flex items-baseline justify-between mb-6">
                <h2 className="text-h2 text-primary">System Questions</h2>
                <span className="text-label-caps text-on-surface-variant">
                  {Array.from(selectedIds).filter((id) => systemQs.some((q) => q._id === id)).length} / {systemQs.length} selected
                </span>
              </div>

              {systemQs.length === 0 ? (
                <p className="text-body-sm text-secondary">No system questions found. Restart the backend to seed them.</p>
              ) : (
                <div className="space-y-3">
                  {systemQs.map((q) => {
                    const checked = selectedIds.has(q._id);
                    return (
                      <div
                        key={q._id}
                        onClick={() => toggleQuestion(q._id)}
                        className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-colors ${
                          checked ? "border-primary/40 bg-primary/5" : "border-outline-variant/40 hover:bg-surface-container"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleQuestion(q._id)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-0.5 w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-on-surface">{q.text}</p>
                          <p className="text-[11px] text-on-surface-variant mt-1">
                            {q.options.length} option{q.options.length !== 1 ? "s" : ""} · {q.correct_option_index != null ? "Scored" : "Unscored"}
                          </p>
                        </div>
                        <span className="text-[10px] bg-surface-container text-on-surface-variant px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider flex-shrink-0">
                          System
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>

            {/* Custom questions */}
            <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
              <div className="flex items-baseline justify-between mb-6">
                <h2 className="text-h2 text-primary">Custom Questions</h2>
                <button
                  type="button"
                  onClick={() => setShowAddModal(true)}
                  className="flex items-center gap-1 text-sm font-semibold text-primary hover:opacity-80 transition-opacity"
                >
                  <span className="material-symbols-outlined text-sm">add_circle</span>
                  Add Question
                </button>
              </div>

              {customQs.length === 0 ? (
                <p className="text-body-sm text-secondary">
                  No custom questions yet. Click "Add Question" to create one.
                </p>
              ) : (
                <div className="space-y-3">
                  {customQs.map((q) => {
                    const checked = selectedIds.has(q._id);
                    return (
                      <div
                        key={q._id}
                        onClick={() => toggleQuestion(q._id)}
                        className={`flex items-start gap-3 p-4 rounded-xl border cursor-pointer transition-colors ${
                          checked ? "border-primary/40 bg-primary/5" : "border-outline-variant/40 hover:bg-surface-container"
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleQuestion(q._id)}
                          onClick={(e) => e.stopPropagation()}
                          className="mt-0.5 w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded flex-shrink-0"
                        />
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold text-on-surface">{q.text}</p>
                          <p className="text-[11px] text-on-surface-variant mt-1">
                            {q.options.length} option{q.options.length !== 1 ? "s" : ""} · {q.correct_option_index != null ? "Scored" : "Unscored"}
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => { e.stopPropagation(); handleDelete(q._id); }}
                          className="text-on-surface-variant hover:text-error transition-colors flex-shrink-0 ml-2"
                          title="Delete question"
                        >
                          <span className="material-symbols-outlined text-sm">delete</span>
                        </button>
                      </div>
                    );
                  })}
                </div>
              )}
            </section>
          </div>
        )}

        {saveError && <p className="mt-6 text-body-sm text-error">{saveError}</p>}

        <div className="mt-12 flex justify-end">
          <button
            type="button"
            onClick={handleNext}
            disabled={saving}
            className="flex items-center gap-2 text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving…" : "Next"}
            {!saving && (
              <span className="material-symbols-outlined text-sm">chevron_right</span>
            )}
          </button>
        </div>
      </main>

      {showAddModal && (
        <AddQuestionModal
          onClose={() => setShowAddModal(false)}
          onSaved={onQuestionSaved}
        />
      )}

      <div className="fixed top-24 -right-24 w-96 h-96 bg-primary/5 rounded-full blur-3xl -z-10" />
      <div className="fixed bottom-24 -left-24 w-96 h-96 bg-secondary/5 rounded-full blur-3xl -z-10" />
    </div>
  );
}
