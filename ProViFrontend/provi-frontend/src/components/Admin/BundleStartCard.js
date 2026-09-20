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
  // The zip settles the tasks, idioms and images; how they are shown to
  // participants is still the admin's to choose, and this route leaves the page
  // as soon as the zip is accepted — so it asks here rather than relying on the
  // form below, which the admin never reaches.
  const [expName, setExpName] = useState(name || "");
  const [design, setDesign] = useState(designType || "between");
  const [randomize, setRandomize] = useState(randomizeOrder !== false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [rejected, setRejected] = useState([]);
  // A created experiment whose zip was only partly usable. Holding it here
  // instead of leaving at once is the only chance the admin gets to see what
  // was left out — on the next page the experiment simply looks short.
  const [partial, setPartial] = useState(null);
  const inputRef = useRef(null);

  async function upload() {
    if (!file || busy) return;
    if (!file.name.toLowerCase().endsWith(".zip")) {
      setError("Choose a .zip file — the one downloaded from this platform, not a single image.");
      return;
    }
    setBusy(true);
    setError(null);
    setRejected([]);
    setPartial(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("name", expName.trim());
      body.append("design_type", design);
      body.append("within_sequence_mode", randomize ? "random" : "fixed");
      const res = await fetch("/api/admin/experiments/from-bundle", { method: "POST", body });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        const detail = data.detail;
        if (Array.isArray(detail)) {
          // FastAPI validation error — nothing the admin can act on beyond the file.
          throw new Error("The upload was rejected. Choose the zip again and retry.");
        }
        if (detail && typeof detail === "object") {
          setRejected(detail.rejected || []);
          throw new Error(detail.message || "The zip could not be used.");
        }
        throw new Error(detail || `Server error: ${res.status}`);
      }
      setRejected(data.rejected || []);
      if ((data.rejected || []).length > 0) {
        setPartial(data);  // say what was left out before leaving this page
        return;
      }
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

          <div className="space-y-3 border-t border-outline-variant pt-3">
            <div>
              <label htmlFor="bundle-name" className="block text-body-xs font-medium text-on-surface mb-1">
                Experiment name
              </label>
              <input
                id="bundle-name"
                type="text"
                value={expName}
                onChange={(e) => setExpName(e.target.value)}
                placeholder="Leave empty to use the name in the zip"
                className="w-full px-3 py-2 rounded-lg border border-outline-variant text-body-sm bg-surface"
              />
            </div>

            <div>
              <p className="text-body-xs font-medium text-on-surface mb-1">Study design</p>
              <div className="flex flex-wrap gap-2">
                {[
                  { value: "between", label: "Between-subjects", desc: "one idiom per task, balanced across participants" },
                  { value: "within", label: "Within-subjects", desc: "every participant sees all idioms of every task" },
                ].map(({ value, label, desc }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setDesign(value)}
                    className={`flex-1 min-w-[14rem] text-left px-3 py-2 rounded-lg border transition-all ${
                      design === value ? "border-primary bg-primary/5" : "border-outline-variant hover:border-primary/50"
                    }`}
                  >
                    <span className={`block text-body-xs font-medium ${design === value ? "text-primary" : "text-on-surface"}`}>
                      {label}
                    </span>
                    <span className="block text-body-xs text-secondary">{desc}</span>
                  </button>
                ))}
              </div>
            </div>

            <label className="flex items-center gap-2 text-body-xs text-on-surface">
              <input
                type="checkbox"
                checked={randomize}
                onChange={() => setRandomize((v) => !v)}
              />
              Randomise the order tasks are shown in
            </label>
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
          {partial && (
            <div className="text-body-xs rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-amber-900">
              <p className="font-medium mb-1">
                The experiment was created with {partial.tasks} task{partial.tasks !== 1 ? "s" : ""}, but
                part of the zip was not used.
              </p>
              <p>
                Check the list below. If something is missing, delete the experiment on the admin page
                and upload a corrected zip; you can also replace single images on the Overview page.
              </p>
              <button
                type="button"
                onClick={() => onCreated(partial)}
                className="mt-2 px-3 py-1.5 rounded-lg bg-primary text-on-primary font-medium"
              >
                Continue to the experiment
              </button>
            </div>
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
