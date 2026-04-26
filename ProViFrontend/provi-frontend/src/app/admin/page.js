"use client";

import { useState, useEffect } from "react";
import AdminNav from "../../components/Admin/AdminNav";
import FileUploadCard from "../../components/Admin/FileUploadCard";
import SaveResultModal from "../../components/Admin/SaveResultModal";
import { getApiBase, setApiBase, normalizeApiBase } from "../../lib/apiConfig";

export default function AdminPage() {
  const [logFile, setLogFile] = useState(null);
  const [guidelineFile, setGuidelineFile] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [modal, setModal] = useState(null); // { success: bool, errorMessage?: string }
  const [apiBaseInput, setApiBaseInput] = useState("");

  useEffect(() => {
    setApiBaseInput(getApiBase());
  }, []);

  const handleSave = async () => {
    if (!logFile || !guidelineFile) {
      setModal({ success: false, errorMessage: "Please select both a log file and a guideline file before saving." });
      return;
    }

    setIsSaving(true);
    try {
      const formData = new FormData();
      formData.append("log", logFile);
      formData.append("guideline", guidelineFile);

      const response = await fetch(`${getApiBase()}/admin/datasets/pair`, {
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
        <section className="w-full max-w-3xl bg-surface-container-lowest border border-outline-variant p-8 rounded-lg shadow-sm">
          <header className="mb-section-gap border-b border-surface-variant pb-4">
            <h2 className="text-h2 text-primary">Upload Dataset</h2>
            <p className="text-body-sm text-secondary mt-2">
              Initialize your experimental process by uploading the required log
              files and research guidelines.
            </p>
            <div className="mt-4 p-3 rounded-md bg-surface-container border border-outline-variant/60 text-body-sm text-secondary">
              <label htmlFor="api-base" className="block text-on-surface font-medium mb-1">
                API 基址（可粘贴公网或隧道）
              </label>
              <p className="text-xs text-secondary mb-2">
                例如 <code className="text-on-surface/80">https://你的域名/...</code> 或{" "}
                <code className="text-on-surface/80">127.0.0.1:8000</code>（会自动补为 …/api）。保存后写入本机
                浏览器，仅当前浏览器有效。
              </p>
              <div className="flex flex-col sm:flex-row gap-2 sm:items-center">
                <input
                  id="api-base"
                  type="text"
                  className="flex-1 rounded border border-outline-variant bg-surface px-3 py-2 text-on-surface text-sm"
                  value={apiBaseInput}
                  onChange={(e) => setApiBaseInput(e.target.value)}
                  placeholder="如 127.0.0.1:8000 或 https://pm-vis…"
                />
                <button
                  type="button"
                  onClick={() => {
                    setApiBase(apiBaseInput);
                    setApiBaseInput(getApiBase());
                  }}
                  className="shrink-0 text-button text-primary px-3 py-2 border border-primary rounded-md hover:bg-primary/5"
                >
                  使用此地址
                </button>
              </div>
              <p className="text-xs mt-2 text-secondary">
                当前请求：<span className="text-on-surface/90 font-mono">{normalizeApiBase(apiBaseInput || getApiBase())}/admin/…</span>
              </p>
            </div>
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
              {isSaving ? "Saving..." : "Save"}
              {!isSaving && (
                <span className="material-symbols-outlined text-sm">
                  chevron_right
                </span>
              )}
            </button>
          </div>
        </section>
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
