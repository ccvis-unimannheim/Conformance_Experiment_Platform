"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import AdminNav from "../../components/Admin/AdminNav";
import UploadDatasetModal from "../../components/Admin/UploadDatasetModal";
import Toast from "../../components/Admin/Toast";

const STATUS_STYLES = {
  draft: {
    border: "border-amber-400",
    dot: "bg-amber-400",
    label: "Draft",
  },
  published: {
    border: "border-blue-500",
    dot: "bg-blue-500",
    label: "Published",
  },
  finished: {
    border: "border-slate-400",
    dot: "bg-slate-400",
    label: "Finished",
  },
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
  // Datasets section
  const [datasets, setDatasets] = useState([]);
  const [datasetsLoading, setDatasetsLoading] = useState(true);
  const [manageMode, setManageMode] = useState(false);
  const [selectedDatasetIds, setSelectedDatasetIds] = useState(new Set());
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteConfirmOpen, setDeleteConfirmOpen] = useState(false);
  const [forceConfirm, setForceConfirm] = useState(null); // array of { dataset, refExps }

  // Experiments section
  const [experiments, setExperiments] = useState([]);
  const [experimentsLoading, setExperimentsLoading] = useState(true);

  // Toast
  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => setToast((t) => ({ ...t, visible: false })), []);

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

  useEffect(() => {
    fetchDatasets();
    fetchExperiments();
  }, [fetchDatasets, fetchExperiments]);

  function toggleSelect(id) {
    setSelectedDatasetIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function enterManageMode() {
    setManageMode(true);
    setSelectedDatasetIds(new Set());
  }

  function exitManageMode() {
    setManageMode(false);
    setSelectedDatasetIds(new Set());
  }

  async function performDelete(ids, { force }) {
    const succeeded = [];
    const conflicts = [];
    const allDemoted = [];
    let otherError = null;

    for (const id of ids) {
      const dataset = datasets.find((d) => d.dataset_id === id);
      try {
        const url = `/api/admin/datasets/${encodeURIComponent(id)}${force ? "?force=true" : ""}`;
        const res = await fetch(url, { method: "DELETE" });
        if (res.status === 409 && !force) {
          const data = await res.json().catch(() => ({}));
          const refExps = data?.detail?.referencing_experiments ?? [];
          conflicts.push({ dataset, refExps });
        } else if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          otherError = typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
        } else {
          const data = await res.json().catch(() => ({}));
          succeeded.push(dataset);
          (data?.demoted_experiments ?? []).forEach((e) => allDemoted.push(e));
        }
      } catch (e) {
        otherError = e.message;
      }
    }
    return { succeeded, conflicts, allDemoted, otherError };
  }

  async function handleDeleteConfirmed() {
    setDeleteConfirmOpen(false);
    const ids = Array.from(selectedDatasetIds);
    const { succeeded, conflicts, allDemoted, otherError } = await performDelete(ids, { force: false });

    if (otherError) showToast(otherError, true);

    if (conflicts.length > 0) {
      setForceConfirm(conflicts);
      // Refresh in case some non-conflicted datasets were deleted
      if (succeeded.length > 0) fetchDatasets();
      return;
    }

    fetchDatasets();
    exitManageMode();
    if (succeeded.length > 0) {
      const demotedNote = allDemoted.length > 0
        ? ` ${allDemoted.length} experiment(s) reverted to draft.`
        : "";
      showToast(`Deleted ${succeeded.length} dataset(s).${demotedNote}`);
    }
  }

  async function handleForceConfirmed() {
    const ids = forceConfirm.map((c) => c.dataset.dataset_id);
    setForceConfirm(null);
    const { succeeded, allDemoted, otherError } = await performDelete(ids, { force: true });
    if (otherError) showToast(otherError, true);
    fetchDatasets();
    fetchExperiments();
    exitManageMode();
    if (succeeded.length > 0) {
      const demotedNames = allDemoted.map((e) => e.name || e._id).join(", ");
      showToast(
        `Force-deleted ${succeeded.length} dataset(s). Reverted to draft: ${demotedNames}.`
      );
    }
  }

  function onUploaded() {
    setUploadOpen(false);
    fetchDatasets();
    showToast("Dataset uploaded. Graph generation is running in the background — allow ~30 seconds before publishing an experiment using this dataset.");
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="home" />

      <main className="max-w-7xl mx-auto px-8 py-section-gap flex items-center justify-center min-h-[calc(100vh-80px)]">
        <div className="grid w-full grid-cols-1 gap-8 divide-x-0 divide-outline-variant lg:grid-cols-2 lg:items-center lg:gap-x-0 lg:divide-x">

          {/* Left Column: Datasets */}
          <section className="min-w-0 space-y-8 lg:pr-8">
            <div className="bg-surface-container-low rounded-xl p-8">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-h2 text-primary">Datasets</h2>
                {manageMode && (
                  <span className="text-xs text-on-surface-variant uppercase tracking-wider">
                    Selected: {selectedDatasetIds.size}
                  </span>
                )}
              </div>

              <div className="space-y-3 mb-10 max-h-72 overflow-y-auto pr-1">
                {datasetsLoading && (
                  <p className="text-body-sm text-secondary">Loading…</p>
                )}
                {!datasetsLoading && datasets.length === 0 && (
                  <p className="text-body-sm text-secondary">No datasets yet.</p>
                )}
                {datasets.map((ds) => {
                  const checked = selectedDatasetIds.has(ds.dataset_id);
                  return (
                    <div
                      key={ds.dataset_id}
                      onClick={manageMode ? () => toggleSelect(ds.dataset_id) : undefined}
                      className={`bg-surface-container-lowest p-4 rounded-xl flex items-center justify-between shadow-sm border-l-4 border-primary/30 ${manageMode ? "cursor-pointer hover:bg-surface-container" : ""} ${checked ? "bg-primary/5" : ""}`}
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        {manageMode && (
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleSelect(ds.dataset_id)}
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
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-end gap-3">
                {manageMode ? (
                  <>
                    <button
                      type="button"
                      onClick={exitManageMode}
                      className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      onClick={() => setDeleteConfirmOpen(true)}
                      disabled={selectedDatasetIds.size === 0}
                      className="flex items-center gap-2 text-sm font-semibold bg-error text-on-error px-6 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <span className="material-symbols-outlined text-sm">delete</span>
                      Delete Selected ({selectedDatasetIds.size})
                    </button>
                  </>
                ) : (
                  <>
                    <button
                      type="button"
                      onClick={enterManageMode}
                      disabled={datasets.length === 0}
                      className="flex items-center gap-2 text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
                    >
                      <span className="material-symbols-outlined text-sm">tune</span>
                      Manage
                    </button>
                    <button
                      type="button"
                      onClick={() => setUploadOpen(true)}
                      className="flex items-center gap-2 text-button bg-primary text-on-primary px-8 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95"
                    >
                      <span className="material-symbols-outlined text-sm">upload</span>
                      Upload
                    </button>
                  </>
                )}
              </div>
            </div>
          </section>

          {/* Right Column: Experiments List */}
          <section className="min-w-0 space-y-8 lg:pl-8">
            <div className="bg-surface-container-low rounded-xl p-8">
              <div className="flex items-center justify-between mb-8">
                <h2 className="text-h2 text-primary">Experiments</h2>
              </div>

              <div className="space-y-4 mb-10 max-h-72 overflow-y-auto pr-1">
                {experimentsLoading && (
                  <p className="text-body-sm text-secondary">Loading…</p>
                )}
                {!experimentsLoading && experiments.length === 0 && (
                  <p className="text-body-sm text-secondary">No experiments yet.</p>
                )}
                {experiments.map((exp) => {
                  const expId = exp._id || exp.experiment_id;
                  const status = exp.status || exp.experiment_status || "draft";
                  const s = statusStyle(status);
                  return (
                    <div
                      key={expId}
                      className={`bg-surface-container-lowest p-5 rounded-xl flex items-center justify-between shadow-sm border-l-4 ${s.border}`}
                    >
                      <div>
                        <h3 className="text-sm font-bold text-on-surface mb-1">
                          {exp.name || exp.experiment_name || "(unnamed)"}
                        </h3>
                        <p className="text-[11px] text-on-surface-variant font-medium flex items-center gap-1 uppercase tracking-wider">
                          <span className={`w-2 h-2 rounded-full ${s.dot}`} />
                          {s.label}
                        </p>
                      </div>
                      <div className="flex items-center gap-2 ml-4 flex-shrink-0">
                        {status === "draft" && (() => {
                          const hasTasks = exp.task_configs && exp.task_configs.length > 0;
                          const continueHref = hasTasks
                            ? `/admin/experiments/idiom?experiment_id=${encodeURIComponent(expId)}`
                            : `/admin/experiments/task?experiment_id=${encodeURIComponent(expId)}`;
                          return (
                            <Link
                              href={continueHref}
                              className="text-xs border border-border-subtle text-on-surface-variant px-3 py-1.5 rounded hover:bg-surface-container transition-colors flex items-center gap-1"
                            >
                              <span className="material-symbols-outlined text-sm">edit</span>
                              Continue Editing
                            </Link>
                          );
                        })()}
                        {status === "published" && (
                          <button
                            onClick={() => markAsFinished(expId)}
                            className="text-xs border border-slate-300 text-slate-600 px-3 py-1.5 rounded hover:bg-slate-100 transition-colors flex items-center gap-1"
                          >
                            <span className="material-symbols-outlined text-sm">check_circle</span>
                            Mark as Finished
                          </button>
                        )}
                        {/* Download button for published and finished experiments */}
                        {(status === "published" || status === "finished") && (
                          <a
                            href={`/api/admin/experiments/${encodeURIComponent(expId)}/answers/download`}
                            className="text-xs border border-primary text-primary px-3 py-1.5 rounded hover:bg-primary hover:text-on-primary transition-colors flex items-center gap-1"
                          >
                            <span className="material-symbols-outlined text-sm">download</span>
                            Download Data
                          </a>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>

              <div className="flex justify-end">
                <Link
                  href="/admin/experiments/new"
                  className="flex items-center gap-2 text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95"
                >
                  <span className="material-symbols-outlined">add_circle</span>
                  Create New Experiment
                </Link>
              </div>
            </div>
          </section>
        </div>
      </main>

      <div className="fixed top-24 -right-24 w-96 h-96 bg-primary/5 rounded-full blur-3xl -z-10" />
      <div className="fixed bottom-24 -left-24 w-96 h-96 bg-secondary/5 rounded-full blur-3xl -z-10" />

      {uploadOpen && (
        <UploadDatasetModal
          existingDatasets={datasets}
          onClose={() => setUploadOpen(false)}
          onUploaded={onUploaded}
        />
      )}

      {deleteConfirmOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-md mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-error">delete</span>
              <h2 className="text-h2 text-on-surface">Delete {selectedDatasetIds.size} dataset(s)?</h2>
            </div>
            <ul className="text-sm text-on-surface-variant list-disc pl-5 max-h-40 overflow-y-auto">
              {Array.from(selectedDatasetIds).map((id) => {
                const ds = datasets.find((d) => d.dataset_id === id);
                return <li key={id}>{ds?.dataset_title || id}</li>;
              })}
            </ul>
            <p className="text-xs text-on-surface-variant">
              If any are used by experiments, you'll get a chance to confirm before they're force-deleted.
            </p>
            <div className="flex justify-end gap-3 mt-2">
              <button
                type="button"
                onClick={() => setDeleteConfirmOpen(false)}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDeleteConfirmed}
                className="text-sm font-semibold bg-error text-on-error px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {forceConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-lg mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-amber-500">warning</span>
              <h2 className="text-h2 text-on-surface">Some datasets are in use</h2>
            </div>
            <div className="text-sm text-on-surface-variant max-h-60 overflow-y-auto">
              {forceConfirm.map(({ dataset, refExps }) => (
                <div key={dataset.dataset_id} className="mb-3">
                  <p className="font-semibold text-on-surface">{dataset.dataset_title}</p>
                  <ul className="list-disc pl-5 mt-1">
                    {refExps.map((e) => (
                      <li key={e._id}>
                        {e.name || e._id} <span className="text-xs">({e.status || "draft"})</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <p className="text-xs text-on-surface-variant">
              Force delete will revert these experiments to <span className="font-semibold">draft</span> and remove the dataset reference.
            </p>
            <div className="flex justify-end gap-3 mt-2">
              <button
                type="button"
                onClick={() => { setForceConfirm(null); exitManageMode(); }}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleForceConfirmed}
                className="text-sm font-semibold bg-error text-on-error px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95"
              >
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
