"use client";

import { useState, useEffect, useCallback } from "react";
import Link from "next/link";
import AdminNav from "../../components/Admin/AdminNav";
import FileUploadCard from "../../components/Admin/FileUploadCard";
import SaveResultModal from "../../components/Admin/SaveResultModal";

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

export default function AdminPage() {
  const [logFile, setLogFile] = useState(null);
  const [guidelineFile, setGuidelineFile] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [modal, setModal] = useState(null);

  const [experiments, setExperiments] = useState([]);
  const [experimentsLoading, setExperimentsLoading] = useState(true);

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
      setModal({ success: false, errorMessage: `Failed to mark as finished: ${e.message}` });
    }
  }, [fetchExperiments]);

  useEffect(() => {
    fetchExperiments();
  }, [fetchExperiments]);

  const handleSave = async () => {
    if (!logFile || !guidelineFile) {
      setModal({
        success: false,
        errorMessage: "Please select both a log file and a guideline file before saving.",
      });
      return;
    }

    setIsSaving(true);
    try {
      const formData = new FormData();
      formData.append("log", logFile);
      formData.append("guideline", guidelineFile);

      const response = await fetch(`/api/admin/datasets/pair`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `Server error: ${response.status}`);
      }

      setModal({ success: true });
    } catch (error) {
      setModal({ success: false, errorMessage: error.message });
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="home" />

      <main className="max-w-7xl mx-auto px-8 py-section-gap flex items-center justify-center min-h-[calc(100vh-80px)]">
        <div className="grid w-full grid-cols-1 gap-8 divide-x-0 divide-outline-variant lg:grid-cols-2 lg:items-center lg:gap-x-0 lg:divide-x">

          {/* Left Column: Upload Dataset */}
          <section className="min-w-0 space-y-8 lg:pr-8">
            <div className="bg-surface-container-low rounded-xl p-8">
              <header className="mb-section-gap border-b border-surface-variant pb-4">
                <h2 className="text-h2 text-primary">Upload Dataset</h2>
              </header>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter mb-section-gap">
                <FileUploadCard
                  label="Upload Log"
                  icon="upload_file"
                  onFileSelect={setLogFile}
                />
                <FileUploadCard
                  label="Upload Guideline"
                  icon="description"
                  onFileSelect={setGuidelineFile}
                />
              </div>

              <div className="flex justify-end pt-8 border-t border-surface-variant">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={isSaving}
                  className="flex items-center gap-2 text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {isSaving ? "Saving and generating..." : "Save and Generate Graphs"}
                  {!isSaving && (
                    <span className="material-symbols-outlined text-sm">chevron_right</span>
                  )}
                </button>
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

      {modal && (
        <SaveResultModal
          success={modal.success}
          errorMessage={modal.errorMessage}
          onClose={() => setModal(null)}
        />
      )}
    </div>
  );
}