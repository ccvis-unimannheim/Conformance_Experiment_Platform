"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import AdminNav from "../../components/Admin/AdminNav";
import UploadDatasetModal from "../../components/Admin/UploadDatasetModal";
import Toast from "../../components/Admin/Toast";

const STATUS_STYLES = {
  draft:     { border: "border-amber-400", dot: "bg-amber-400", label: "Draft" },
  published: { border: "border-blue-500",  dot: "bg-blue-500",  label: "Published" },
  finished:  { border: "border-slate-400", dot: "bg-slate-400", label: "Finished" },
};

function statusStyle(status) {
  return STATUS_STYLES[status] ?? STATUS_STYLES.draft;
}

function formatDateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "—";
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${String(d.getFullYear()).slice(-2)} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function AdminPage() {
  // ── Datasets ──────────────────────────────────────
  const [datasets, setDatasets] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [dsManageMode, setDsManageMode] = useState(false);
  const [selectedDsIds, setSelectedDsIds] = useState(new Set());
  const [uploadOpen, setUploadOpen] = useState(false);
  const [dsDeleteConfirmOpen, setDsDeleteConfirmOpen] = useState(false);
  const [dsForceConfirm, setDsForceConfirm] = useState(null);

  // ── Experiments ───────────────────────────────────
  const [experiments, setExperiments] = useState([]);
  const [experimentsLoading, setExperimentsLoading] = useState(true);
  const [expManageMode, setExpManageMode] = useState(false);
  const [selectedExpIds, setSelectedExpIds] = useState(new Set());
  const [expDeleteConfirmOpen, setExpDeleteConfirmOpen] = useState(false);
  const [expForceConfirm, setExpForceConfirm] = useState(null);

  // ── Toast ─────────────────────────────────────────
  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => setToast((t) => ({ ...t, visible: false })), []);

  // ── Fetch ─────────────────────────────────────────
  const fetchDatasets = useCallback(() => {
    setDatasetsLoading(true);
    fetch(`/api/admin/datasets`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setDatasets(Array.isArray(data) ? data : []))
      .catch(() => setDatasets([]))
      .finally(() => setDatasetsLoading(false));
  }, []);

  const fetchExperiments = useCallback(() => {
    setExperimentsLoading(true);
    fetch(`/api/admin/experiments`)
      .then((r) => (r.ok ? r.json() : []))
      .then((data) => setExperiments(data))
      .catch(() => setExperiments([]))
      .finally(() => setExperimentsLoading(false));
  }, []);

  useEffect(() => {
    fetchDatasets();
    fetchExperiments();
  }, [fetchDatasets, fetchExperiments]);

  // ── Dataset manage ────────────────────────────────
  function toggleSelectDs(id) {
    setSelectedDsIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function exitDsManage() { setDsManageMode(false); setSelectedDsIds(new Set()); }

  async function performDsDelete(ids, force) {
    const succeeded = [], conflicts = [], allDemoted = [];
    let otherError = null;
    for (const id of ids) {
      const dataset = datasets.find((d) => d.dataset_id === id);
      try {
        const res = await fetch(
          `/api/admin/datasets/${encodeURIComponent(id)}${force ? "?force=true" : ""}`,
          { method: "DELETE" }
        );
        if (res.status === 409 && !force) {
          const data = await res.json().catch(() => ({}));
          conflicts.push({ dataset, refExps: data?.detail?.referencing_experiments ?? [] });
        } else if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          otherError = typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
        } else {
          const data = await res.json().catch(() => ({}));
          succeeded.push(dataset);
          (data?.demoted_experiments ?? []).forEach((e) => allDemoted.push(e));
        }
      } catch (e) { otherError = e.message; }
    }
    return { succeeded, conflicts, allDemoted, otherError };
  }

  async function handleDsDeleteConfirmed() {
    setDsDeleteConfirmOpen(false);
    const ids = Array.from(selectedDsIds);
    const { succeeded, conflicts, allDemoted, otherError } = await performDsDelete(ids, false);
    if (otherError) showToast(otherError, true);
    if (conflicts.length > 0) {
      if (succeeded.length > 0) fetchDatasets();
      setDsForceConfirm(conflicts);
      return;
    }
    fetchDatasets();
    exitDsManage();
    if (succeeded.length > 0) {
      const note = allDemoted.length > 0 ? ` ${allDemoted.length} experiment(s) reverted to draft.` : "";
      showToast(`Deleted ${succeeded.length} dataset(s).${note}`);
    }
  }

  async function handleDsForceConfirmed() {
    const ids = dsForceConfirm.map((c) => c.dataset.dataset_id);
    setDsForceConfirm(null);
    const { succeeded, allDemoted, otherError } = await performDsDelete(ids, true);
    if (otherError) showToast(otherError, true);
    fetchDatasets(); fetchExperiments(); exitDsManage();
    if (succeeded.length > 0) {
      const names = allDemoted.map((e) => e.name || e._id).join(", ");
      showToast(`Force-deleted ${succeeded.length} dataset(s). Reverted to draft: ${names}.`);
    }
  }

  function onUploaded() {
    setUploadOpen(false);
    fetchDatasets();
    showToast("Dataset uploaded. Graph generation is running in the background — allow ~30 seconds before publishing an experiment using this dataset.");
  }

  // ── Experiment manage ─────────────────────────────
  function toggleSelectExp(id) {
    setSelectedExpIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function exitExpManage() { setExpManageMode(false); setSelectedExpIds(new Set()); }

  const markAsFinished = useCallback(async (expId) => {
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(expId)}/status?status=finished`,
        { method: "PATCH" }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      fetchExperiments();
    } catch (e) {
      showToast(`Failed to mark as finished: ${e.message}`, true);
    }
  }, [fetchExperiments, showToast]);

  async function performExpDelete(ids, force) {
    const succeeded = [], conflicts = [];
    let otherError = null;
    for (const id of ids) {
      const exp = experiments.find((e) => (e._id || e.experiment_id) === id);
      try {
        const res = await fetch(
          `/api/admin/experiments/${encodeURIComponent(id)}${force ? "?force=true" : ""}`,
          { method: "DELETE" }
        );
        if (res.status === 409 && !force) {
          const data = await res.json().catch(() => ({}));
          conflicts.push({ exp, counts: data?.detail?.counts ?? {} });
        } else if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          otherError = typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
        } else {
          succeeded.push(exp);
        }
      } catch (e) { otherError = e.message; }
    }
    return { succeeded, conflicts, otherError };
  }

  async function handleExpDeleteConfirmed() {
    setExpDeleteConfirmOpen(false);
    const ids = Array.from(selectedExpIds);
    const { succeeded, conflicts, otherError } = await performExpDelete(ids, false);
    if (otherError) showToast(otherError, true);
    if (conflicts.length > 0) {
      if (succeeded.length > 0) fetchExperiments();
      setExpForceConfirm(conflicts);
      return;
    }
    fetchExperiments(); exitExpManage();
    if (succeeded.length > 0) showToast(`Deleted ${succeeded.length} experiment(s).`);
  }

  async function handleExpForceConfirmed() {
    const ids = expForceConfirm.map((c) => (c.exp._id || c.exp.experiment_id));
    setExpForceConfirm(null);
    const { succeeded, otherError } = await performExpDelete(ids, true);
    if (otherError) showToast(otherError, true);
    fetchExperiments(); exitExpManage();
    if (succeeded.length > 0) showToast(`Force-deleted ${succeeded.length} experiment(s) and all associated data.`);
  }

  // ── Render ────────────────────────────────────────
  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="home" />

      <main className="max-w-7xl mx-auto px-8 py-section-gap flex items-center justify-center min-h-[calc(100vh-80px)]">
        <div className="grid w-full grid-cols-1 gap-8 divide-x-0 divide-outline-variant lg:grid-cols-2 lg:items-center lg:gap-x-0 lg:divide-x">

          {/* ── Left: Datasets ── */}
          <section className="min-w-0 space-y-8 lg:pr-8">
            <div className="bg-surface-container-low rounded-xl p-8">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-h2 text-primary">Datasets</h2>
                {dsManageMode && (
                  <span className="text-xs text-on-surface-variant uppercase tracking-wider">
                    Selected: {selectedDsIds.size}
                  </span>
                )}
              </div>

              <div className="space-y-3 mb-10 max-h-72 overflow-y-auto pr-1">
                {datasetsLoading && <p className="text-body-sm text-secondary">Loading…</p>}
                {!datasetsLoading && datasets.length === 0 && (
                  <p className="text-body-sm text-secondary">No datasets yet.</p>
                )}
                {datasets.map((ds) => {
                  const checked = selectedDsIds.has(ds.dataset_id);
                  return (
                    <div
                      key={ds.dataset_id}
                      onClick={dsManageMode ? () => toggleSelectDs(ds.dataset_id) : undefined}
                      className={`bg-surface-container-lowest p-4 rounded-xl flex items-center gap-3 shadow-sm border-l-4 border-primary/30 ${dsManageMode ? "cursor-pointer hover:bg-surface-container" : ""} ${checked ? "bg-primary/5" : ""}`}
                    >
                      {dsManageMode && (
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleSelectDs(ds.dataset_id)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded flex-shrink-0"
                        />
                      )}
                      <div className="min-w-0">
                        <h3 className="text-sm font-bold text-on-surface truncate">
                          {ds.dataset_title || "(unnamed)"}
                        </h3>
                        <p className="text-[11px] text-on-surface-variant font-medium tracking-wider">
                          {formatDateTime(ds.insert_datetime)}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-end gap-3">
                {dsManageMode ? (
                  <>
                    <button type="button" onClick={exitDsManage}
                      className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors">
                      Cancel
                    </button>
                    <button type="button" onClick={() => setDsDeleteConfirmOpen(true)}
                      disabled={selectedDsIds.size === 0}
                      className="flex items-center gap-2 text-sm font-semibold bg-error text-on-error px-6 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed">
                      <span className="material-symbols-outlined text-sm">delete</span>
                      Delete Selected ({selectedDsIds.size})
                    </button>
                  </>
                ) : (
                  <>
                    <button type="button" onClick={() => { setDsManageMode(true); setSelectedDsIds(new Set()); }}
                      disabled={datasets.length === 0}
                      className="flex items-center gap-2 text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                      <span className="material-symbols-outlined text-sm">tune</span>
                      Manage
                    </button>
                    <button type="button" onClick={() => setUploadOpen(true)}
                      className="flex items-center gap-2 text-button bg-primary text-on-primary px-8 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95">
                      <span className="material-symbols-outlined text-sm">upload</span>
                      Upload
                    </button>
                  </>
                )}
              </div>
            </div>
          </section>

          {/* ── Right: Experiments ── */}
          <section className="min-w-0 space-y-8 lg:pl-8">
            <div className="bg-surface-container-low rounded-xl p-8">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-h2 text-primary">Experiments</h2>
                {expManageMode && (
                  <span className="text-xs text-on-surface-variant uppercase tracking-wider">
                    Selected: {selectedExpIds.size}
                  </span>
                )}
              </div>

              <div className="space-y-4 mb-10 max-h-72 overflow-y-auto pr-1">
                {experimentsLoading && <p className="text-body-sm text-secondary">Loading…</p>}
                {!experimentsLoading && experiments.length === 0 && (
                  <p className="text-body-sm text-secondary">No experiments yet.</p>
                )}
                {experiments.map((exp) => {
                  const expId = exp._id || exp.experiment_id;
                  const status = exp.status || exp.experiment_status || "draft";
                  const s = statusStyle(status);
                  const checked = selectedExpIds.has(expId);
                  return (
                    <div
                      key={expId}
                      onClick={expManageMode ? () => toggleSelectExp(expId) : undefined}
                      className={`bg-surface-container-lowest p-5 rounded-xl flex items-center gap-3 shadow-sm border-l-4 ${s.border} ${expManageMode ? "cursor-pointer hover:bg-surface-container" : ""} ${checked ? "bg-primary/5" : ""}`}
                    >
                      {expManageMode && (
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleSelectExp(expId)}
                          onClick={(e) => e.stopPropagation()}
                          className="w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded flex-shrink-0"
                        />
                      )}
                      <div className="flex-1 min-w-0">
                        <h3 className="text-sm font-bold text-on-surface mb-1 truncate">
                          {exp.name || exp.experiment_name || "(unnamed)"}
                        </h3>
                        <p className="text-[11px] text-on-surface-variant font-medium flex items-center gap-1 uppercase tracking-wider">
                          <span className={`w-2 h-2 rounded-full flex-shrink-0 ${s.dot}`} />
                          {s.label}
                        </p>
                      </div>
                      {!expManageMode && (
                        <div className="flex items-center gap-2 ml-2 flex-shrink-0">
                          {status === "draft" && (() => {
                            const hasTasks = exp.task_configs && exp.task_configs.length > 0;
                            const href = hasTasks
                              ? `/admin/experiments/idiom?experiment_id=${encodeURIComponent(expId)}`
                              : `/admin/experiments/task?experiment_id=${encodeURIComponent(expId)}`;
                            return (
                              <Link href={href}
                                className="text-xs border border-border-subtle text-on-surface-variant px-3 py-1.5 rounded hover:bg-surface-container transition-colors flex items-center gap-1">
                                <span className="material-symbols-outlined text-sm">edit</span>
                                Continue Editing
                              </Link>
                            );
                          })()}
                          {status === "published" && (
                            <button onClick={() => markAsFinished(expId)}
                              className="text-xs border border-slate-300 text-slate-600 px-3 py-1.5 rounded hover:bg-slate-100 transition-colors flex items-center gap-1">
                              <span className="material-symbols-outlined text-sm">check_circle</span>
                              Mark as Finished
                            </button>
                          )}
                          {(status === "published" || status === "finished") && (
                            <a href={`/api/admin/experiments/${encodeURIComponent(expId)}/answers/download`}
                              className="text-xs border border-primary text-primary px-3 py-1.5 rounded hover:bg-primary hover:text-on-primary transition-colors flex items-center gap-1">
                              <span className="material-symbols-outlined text-sm">download</span>
                              Download Data
                            </a>
                          )}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-end gap-3">
                {expManageMode ? (
                  <>
                    <button type="button" onClick={exitExpManage}
                      className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors">
                      Cancel
                    </button>
                    <button type="button" onClick={() => setExpDeleteConfirmOpen(true)}
                      disabled={selectedExpIds.size === 0}
                      className="flex items-center gap-2 text-sm font-semibold bg-error text-on-error px-6 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed">
                      <span className="material-symbols-outlined text-sm">delete</span>
                      Delete Selected ({selectedExpIds.size})
                    </button>
                  </>
                ) : (
                  <>
                    <button type="button"
                      onClick={() => { setExpManageMode(true); setSelectedExpIds(new Set()); }}
                      disabled={experiments.length === 0}
                      className="flex items-center gap-2 text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed">
                      <span className="material-symbols-outlined text-sm">tune</span>
                      Manage
                    </button>
                    <Link href="/admin/experiments/new"
                      className="flex items-center gap-2 text-button bg-primary text-on-primary px-8 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95">
                      <span className="material-symbols-outlined text-sm">add_circle</span>
                      Create New
                    </Link>
                  </>
                )}
              </div>
            </div>
          </section>
        </div>
      </main>

      <div className="fixed top-24 -right-24 w-96 h-96 bg-primary/5 rounded-full blur-3xl -z-10" />
      <div className="fixed bottom-24 -left-24 w-96 h-96 bg-secondary/5 rounded-full blur-3xl -z-10" />

      {/* ── Upload modal ── */}
      {uploadOpen && (
        <UploadDatasetModal
          existingDatasets={datasets}
          onClose={() => setUploadOpen(false)}
          onUploaded={onUploaded}
        />
      )}

      {/* ── Dataset delete confirm ── */}
      {dsDeleteConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-md mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-error">delete</span>
              <h2 className="text-h2 text-on-surface">Delete {selectedDsIds.size} dataset(s)?</h2>
            </div>
            <ul className="text-sm text-on-surface-variant list-disc pl-5 max-h-40 overflow-y-auto">
              {Array.from(selectedDsIds).map((id) => {
                const ds = datasets.find((d) => d.dataset_id === id);
                return <li key={id}>{ds?.dataset_title || id}</li>;
              })}
            </ul>
            <p className="text-xs text-on-surface-variant">
              If any are used by experiments, you'll get a chance to confirm before they're force-deleted.
            </p>
            <div className="flex justify-end gap-3 mt-2">
              <button type="button" onClick={() => setDsDeleteConfirmOpen(false)}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors">
                Cancel
              </button>
              <button type="button" onClick={handleDsDeleteConfirmed}
                className="text-sm font-semibold bg-error text-on-error px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Dataset force-delete confirm ── */}
      {dsForceConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-lg mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-amber-500">warning</span>
              <h2 className="text-h2 text-on-surface">Some datasets are in use</h2>
            </div>
            <div className="text-sm text-on-surface-variant max-h-60 overflow-y-auto space-y-3">
              {dsForceConfirm.map(({ dataset, refExps }) => (
                <div key={dataset.dataset_id}>
                  <p className="font-semibold text-on-surface">{dataset.dataset_title}</p>
                  <ul className="list-disc pl-5 mt-1">
                    {refExps.map((e) => (
                      <li key={e._id}>{e.name || e._id} <span className="text-xs">({e.status || "draft"})</span></li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <p className="text-xs text-on-surface-variant">
              Force delete will revert these experiments to <span className="font-semibold">draft</span> and remove the dataset reference.
            </p>
            <div className="flex justify-end gap-3 mt-2">
              <button type="button" onClick={() => { setDsForceConfirm(null); exitDsManage(); }}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors">
                Cancel
              </button>
              <button type="button" onClick={handleDsForceConfirmed}
                className="text-sm font-semibold bg-error text-on-error px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95">
                Force Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Experiment delete confirm ── */}
      {expDeleteConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-md mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-error">delete</span>
              <h2 className="text-h2 text-on-surface">Delete {selectedExpIds.size} experiment(s)?</h2>
            </div>
            <ul className="text-sm text-on-surface-variant list-disc pl-5 max-h-40 overflow-y-auto">
              {Array.from(selectedExpIds).map((id) => {
                const exp = experiments.find((e) => (e._id || e.experiment_id) === id);
                return <li key={id}>{exp?.name || id}</li>;
              })}
            </ul>
            <p className="text-xs text-on-surface-variant">
              Draft experiments with no data will be deleted immediately. Others will require confirmation.
            </p>
            <div className="flex justify-end gap-3 mt-2">
              <button type="button" onClick={() => setExpDeleteConfirmOpen(false)}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors">
                Cancel
              </button>
              <button type="button" onClick={handleExpDeleteConfirmed}
                className="text-sm font-semibold bg-error text-on-error px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95">
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Experiment force-delete confirm ── */}
      {expForceConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-lg mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-amber-500">warning</span>
              <h2 className="text-h2 text-on-surface">Some experiments have data</h2>
            </div>
            <div className="text-sm text-on-surface-variant max-h-60 overflow-y-auto space-y-4">
              {expForceConfirm.map(({ exp, counts }) => {
                const expId = exp._id || exp.experiment_id;
                const status = exp.status || "draft";
                const hasAnswers = (counts.answers ?? 0) > 0;
                return (
                  <div key={expId}>
                    <div className="flex items-center justify-between gap-2">
                      <p className="font-semibold text-on-surface">{exp.name || expId}</p>
                      <span className={`text-[10px] px-2 py-0.5 rounded-full font-semibold uppercase ${statusStyle(status).dot} text-white`}>
                        {status}
                      </span>
                    </div>
                    <p className="text-xs mt-0.5">
                      {counts.assignments ?? 0} assignment(s) · {counts.answers ?? 0} answer(s) · {counts.ui_logs ?? 0} UI log(s)
                    </p>
                    {hasAnswers && (
                      <a
                        href={`/api/admin/experiments/${encodeURIComponent(expId)}/answers/download`}
                        className="inline-flex items-center gap-1 text-xs text-primary hover:underline mt-1"
                      >
                        <span className="material-symbols-outlined text-sm">download</span>
                        Download data first
                      </a>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-xs text-on-surface-variant">
              Force delete will <span className="font-semibold text-error">permanently remove</span> all participant data for these experiments.
            </p>
            <div className="flex justify-end gap-3 mt-2">
              <button type="button" onClick={() => { setExpForceConfirm(null); exitExpManage(); }}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors">
                Cancel
              </button>
              <button type="button" onClick={handleExpForceConfirmed}
                className="text-sm font-semibold bg-error text-on-error px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95">
                Force Delete
              </button>
            </div>
          </div>
        </div>
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
