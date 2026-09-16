"use client";

import { useState } from "react";
import FileUploadCard from "./FileUploadCard";

const ALLOWED_EXTENSIONS = [".svg", ".png", ".jpg", ".jpeg"];

function hasAllowedExtension(filename) {
  const lower = (filename || "").toLowerCase();
  return ALLOWED_EXTENSIONS.some((ext) => lower.endsWith(ext));
}

const UploadIdiomModal = ({ onClose, onUploaded }) => {
  const [file, setFile] = useState(null);
  const [label, setLabel] = useState("");
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");

  function handleBackdropClick() {
    if (isSaving) return;
    onClose?.();
  }

  async function handleSave() {
    setErrorMessage("");
    if (!file) {
      setErrorMessage("Please select an image or SVG file.");
      return;
    }
    if (!hasAllowedExtension(file.name)) {
      setErrorMessage(`File must be one of: ${ALLOWED_EXTENSIONS.join(", ")}`);
      return;
    }
    if (!label.trim()) {
      setErrorMessage("Please give this idiom a name.");
      return;
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("label", label.trim());

    setIsSaving(true);
    try {
      const res = await fetch("/api/admin/idioms/upload", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      onUploaded?.();
    } catch (e) {
      setErrorMessage(e.message);
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
      onClick={handleBackdropClick}
    >
      <div
        className="bg-white rounded-xl shadow-xl p-8 w-full max-w-lg mx-4 flex flex-col gap-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h2 className="text-h2 text-primary">Upload Custom Idiom</h2>
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

        <p className="text-body-sm text-on-surface-variant">
          Upload a fixed SVG or image visualization of your own. It will be added as a
          selectable idiom for every task — unlike the built-in idioms, it is not
          generated per dataset.
        </p>

        <div className="flex flex-col gap-2">
          <label className="text-xs font-semibold text-on-surface">Idiom name</label>
          <input
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="e.g. Custom Sankey Diagram"
            className="w-full text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
        </div>

        <FileUploadCard label="Upload Image / SVG" icon="image" onFileSelect={setFile} />

        {errorMessage && <p className="text-body-sm text-error">{errorMessage}</p>}

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
            {isSaving ? "Uploading..." : "Upload"}
            {!isSaving && <span className="material-symbols-outlined text-sm">upload</span>}
          </button>
        </div>
      </div>
    </div>
  );
};

export default UploadIdiomModal;
