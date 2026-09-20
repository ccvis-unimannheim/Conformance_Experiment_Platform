"use client";

import { useRef, useState } from "react";

/**
 * The second route out of /new: an experiment whose images already exist.
 *
 * Instead of choosing a dataset and generating, the admin uploads a zip
 * downloaded from this platform ("Download idiom images"), and the zip decides
 * the tasks, the idioms and — from version 3 on — the answer formats. Collapsed
 * by default so it does not compete with the dataset route, which is what most
 * experiments use.
 */
export default function BundleStartCard({ name, designType, randomizeOrder, onCreated }) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [rejected, setRejected] = useState([]);
  const inputRef = useRef(null);

  async function upload() {
    if (!file || busy) return;
    setBusy(true);
    setError(null);
    setRejected([]);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("name", (name || "").trim());
      body.append("design_type", designType);
      body.append("within_sequence_mode", randomizeOrder ? "random" : "fixed");
      const res = await fetch("/api/admin/experiments/from-bundle", { method: "POST", body });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        if (detail && typeof detail === "object") {
          setRejected(detail.rejected || []);
          throw new Error(detail.message || "The zip could not be used.");
        }
        throw new Error(detail || `Server error: ${res.status}`);
      }
      setRejected(data.rejected || []);
      onCreated(data);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="mb-8 rounded-xl border border-outline-variant bg-surface-container-lowest">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-3 px-gutter py-4 text-left"
      >
        <span className="material-symbols-outlined text-primary text-[20px]">folder_zip</span>
        <span className="flex-1">
          <span className="text-body-sm font-medium text-on-surface">
            Already have the images? Start from a downloaded zip
          </span>
          <span className="block text-body-xs text-secondary">
            Skips choosing a dataset, selecting idioms and generating — the zip already holds them.
          </span>
        </span>
        <span className="material-symbols-outlined text-secondary text-[20px]">
          {open ? "expand_less" : "expand_more"}
        </span>
      </button>

      {open && (
        <div className="px-gutter pb-gutter pt-2 border-t border-outline-variant space-y-4">
          <div className="text-body-xs text-secondary space-y-2">
            <p>
              Use a zip downloaded from this platform (<em>Download idiom images</em> on the Overview
              page or the experiment list). Its layout:
            </p>
            <pre className="bg-surface-container rounded-lg p-3 leading-relaxed text-on-surface-variant overflow-x-auto">
{`manifest.json              ← required; says which tasks, idioms and settings
task01/bar_chart.svg       ← one folder per task, one image per idiom
task01/table.svg
task01/traces.json         ← only tasks that show given traces
custom-a1b2c3/my_idiom.png ← tasks you added yourself work the same way`}
            </pre>
            <p>
              Tasks the zip contains that this server does not have — your own custom tasks and
              idioms — are recreated for this experiment. Images may be SVG, PNG or JPG.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <input
              ref={inputRef}
              type="file"
              accept=".zip,application/zip"
              onChange={(e) => { setFile(e.target.files?.[0] || null); setError(null); }}
              className="hidden"
            />
            <button
              type="button"
              onClick={() => inputRef.current?.click()}
              disabled={busy}
              className="px-4 py-2 rounded-lg border border-outline-variant text-body-sm hover:border-primary/50 disabled:opacity-50"
            >
              Choose zip
            </button>
            <span className="text-body-xs text-secondary flex-1 min-w-[8rem] truncate">
              {file ? file.name : "No file chosen"}
            </span>
            <button
              type="button"
              onClick={upload}
              disabled={!file || busy}
              className="px-4 py-2 rounded-lg bg-primary text-on-primary text-body-sm font-medium disabled:opacity-50"
            >
              {busy ? "Creating…" : "Create experiment from zip"}
            </button>
          </div>

          {error && (
            <p className="text-body-xs text-error bg-error/5 border border-error/30 rounded-lg px-3 py-2">
              {error}
            </p>
          )}
          {rejected.length > 0 && (
            <div className="text-body-xs text-secondary border border-outline-variant rounded-lg px-3 py-2">
              <p className="font-medium text-on-surface mb-1">Not used from the zip:</p>
              <ul className="space-y-0.5">
                {rejected.map((r, i) => (
                  <li key={i}>
                    <span className="font-mono">{r.file}</span> — {r.reason}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
