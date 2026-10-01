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
 *
 * `name` / `designType` / `randomizeOrder` are read from the page's own form
 * above, not asked again here: this used to keep its own copies, so an admin
 * who opened this card saw two name fields and two study-design pickers with
 * no visible connection between them. `open` is controlled by the parent so it
 * can swap the dataset table below for a note while this card is in use — a
 * zip route has no use for a dataset, and showing both at once is exactly the
 * "so what does this mean" the two name fields caused.
 *
 * `replaceExperimentId`, given, turns this into replacing that (already
 * bundle-only) experiment's tasks, idioms and images with a different zip's,
 * instead of creating a new experiment — the copy, the confirmation and the
 * request both change accordingly; the wiring (upload, error, partial-result
 * states) is shared.
 */
export default function BundleStartCard({
  name, designType, randomizeOrder, open, onToggle, onCreated, replaceExperimentId,
}) {
  const [file, setFile] = useState(null);
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
    if (replaceExperimentId && !window.confirm(
      "Replace this experiment's tasks, idioms and images with this zip's? The ones it has now — " +
      "including any single image you replaced by hand — are gone once the new zip is confirmed to " +
      "hold at least one usable task; nothing changes if it doesn't."
    )) return;
    setBusy(true);
    setError(null);
    setRejected([]);
    setPartial(null);
    try {
      const body = new FormData();
      body.append("file", file);
      body.append("name", (name || "").trim());
      body.append("design_type", designType || "between");
      body.append("within_sequence_mode", randomizeOrder ? "random" : "fixed");
      if (replaceExperimentId) body.append("experiment_id", replaceExperimentId);
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
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-gutter py-4 text-left"
      >
        <span className="material-symbols-outlined text-primary text-[20px]">folder_zip</span>
        <span className="flex-1">
          <span className="text-body-sm font-medium text-on-surface">
            {replaceExperimentId
              ? "Replace with a different zip"
              : "Already have the images? Start from a downloaded zip"}
          </span>
          <span className="block text-body-xs text-secondary">
            {replaceExperimentId
              ? "Swaps out every task, idiom and image this experiment has for a different zip's."
              : "Skips choosing a dataset, selecting idioms and generating — the zip already holds them."}
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
            <p>
              Uses the name and study design set above ({name?.trim() || "the name in the zip"}
              {" · "}
              {designType === "within" ? "within-subjects" : "between-subjects"}). Change either
              there before uploading.
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
              {busy
                ? (replaceExperimentId ? "Replacing…" : "Creating…")
                : (replaceExperimentId ? "Replace with this zip" : "Create experiment from zip")}
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
                {replaceExperimentId ? "Replaced with" : "The experiment was created with"} {partial.tasks}{" "}
                task{partial.tasks !== 1 ? "s" : ""}, but part of the zip was not used.
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
