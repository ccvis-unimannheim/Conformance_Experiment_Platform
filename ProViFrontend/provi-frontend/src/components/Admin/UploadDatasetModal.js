"use client";

import { useState } from "react";
import FileUploadCard from "./FileUploadCard";

function deriveTitle(file) {
  if (!file?.name) return "";
  const lastDot = file.name.lastIndexOf(".");
  return lastDot > 0 ? file.name.slice(0, lastDot) : file.name;
}

function nextAvailableTitle(base, existingTitles) {
  let n = 2;
  while (existingTitles.has(`${base} (${n})`)) n++;
  return `${base} (${n})`;
}

const UploadDatasetModal = ({ existingDatasets, onClose, onUploaded }) => {
  const [logFile, setLogFile] = useState(null);
  const [guidelineFile, setGuidelineFile] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [conflict, setConflict] = useState(null); // { title, existing }

  const existingTitleSet = new Set(
    (existingDatasets || []).map((d) => d.dataset_title)
  );

  async function postUpload(titleOverride = null) {
    const formData = new FormData();
    formData.append("log", logFile);
    formData.append("guideline", guidelineFile);
    if (titleOverride) formData.append("dataset_title", titleOverride);

    const res = await fetch("/api/admin/datasets/pair", {
      method: "POST",
      body: formData,
    });
    if (!res.ok) {
      const data = await res.json().catch(() => ({}));
      throw new Error(data.detail || `Server error: ${res.status}`);
    }
    return res.json();
  }

  async function handleSave() {
    setErrorMessage("");
    if (!logFile || !guidelineFile) {
      setErrorMessage("Please select both a log file and a guideline file.");
      return;
    }
    const title = deriveTitle(logFile);
    const existing = (existingDatasets || []).find(
      (d) => d.dataset_title === title
    );
    if (existing) {
      setConflict({ title, existing });
      return;
    }
    setIsSaving(true);
    try {
      await postUpload();
      onUploaded?.();
    } catch (e) {
      setErrorMessage(e.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleKeepBoth() {
    const newTitle = nextAvailableTitle(conflict.title, existingTitleSet);
    setConflict(null);
    setIsSaving(true);
    try {
      await postUpload(newTitle);
      onUploaded?.();
    } catch (e) {
      setErrorMessage(e.message);
    } finally {
      setIsSaving(false);
    }
  }

  async function handleReplace() {
    const existingId = conflict.existing.dataset_id;
    setConflict(null);
    setIsSaving(true);
    try {
      const delRes = await fetch(
        `/api/admin/datasets/${encodeURIComponent(existingId)}?force=true`,
        { method: "DELETE" }
      );
      if (!delRes.ok) {
        const data = await delRes.json().catch(() => ({}));
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `Failed to replace existing dataset (HTTP ${delRes.status})`
        );
      }
      await postUpload();
      onUploaded?.();
    } catch (e) {
      setErrorMessage(e.message);
    } finally {
      setIsSaving(false);
    }
  }

  function handleBackdropClick() {
    if (isSaving) return;
    onClose?.();
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-white rounded-xl shadow-xl p-8 w-full max-w-2xl mx-4 flex flex-col gap-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-h2 text-primary">Upload Dataset</h2>
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="text-on-surface-variant hover:text-on-surface disabled:opacity-30 disabled:cursor-not-allowed"
            aria-label="Close"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-gutter">
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

        {errorMessage && (
          <p className="text-body-sm text-error">{errorMessage}</p>
        )}

        <div className="flex justify-end pt-4 border-t border-surface-variant gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-2 text-button bg-primary text-on-primary px-8 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSaving ? "Saving and generating..." : "Save and Generate Graphs"}
            {!isSaving && (
              <span className="material-symbols-outlined text-sm">chevron_right</span>
            )}
          </button>
        </div>
      </div>

      {conflict && (
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-md mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-amber-500">warning</span>
              <h2 className="text-h2 text-on-surface">Dataset name already exists</h2>
            </div>
            <p className="text-body-sm text-on-surface-variant">
              A dataset named "<span className="font-semibold">{conflict.title}</span>" already exists. How would you like to proceed?
            </p>
            <div className="flex justify-end gap-3 mt-2 flex-wrap">
              <button
                type="button"
                onClick={() => setConflict(null)}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleKeepBoth}
                className="text-sm font-semibold border border-primary text-primary px-5 py-2 rounded-lg hover:bg-primary/5 transition-colors"
              >
                Keep Both
              </button>
              <button
                type="button"
                onClick={handleReplace}
                className="text-sm font-semibold bg-primary text-on-primary px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95"
              >
                Replace
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default UploadDatasetModal;
