"use client";

import { useRef, useState } from "react";

// Import of an idiom bundle zip into an experiment that already exists (see
// backend routers/idiom_bundle.py), from the Overview page: this experiment's
// parameters stay, and a task whose parameters — or dataset — differ from the
// zip's is rejected. Building a whole experiment out of a zip is the other
// route, on /new.
//
// The import changes what participants will see, so it asks first and says
// exactly what it touches: the images and the matched tasks' parameters, and
// nothing else the admin has set up here.

const CONFIRM_TEXT =
  "Import the images of this zip into this experiment?\n\n" +
  "• The images participants see are replaced for every task the zip matches, and pinned: " +
  "regenerating will not overwrite them.\n" +
  "• Those tasks' parameters are locked to the values the images were drawn with.\n" +
  "• A task whose parameters or dataset differ from the zip's is rejected and left as it is.\n\n" +
  "Your answer formats, task wording and the tasks and idioms this experiment uses are not changed.";

async function readError(res) {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === "string") return { message: detail };
  return {
    message: detail?.message || `HTTP ${res.status}`,
    rejected: Array.isArray(detail?.rejected) ? detail.rejected : null,
    datasetMismatch: !!detail?.dataset_mismatch,
  };
}

// Button that picks a zip and posts it. Reports every outcome through
// onResult({ imported, rejected, datasetMismatch, failed }) so the caller can
// render it with <IdiomImportResult>.
export function IdiomImportButton({ experimentId, mode, label = "Import Idioms", disabled, onImported, onResult, showToast }) {
  const inputRef = useRef(null);
  const [busy, setBusy] = useState(false);

  async function handleFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    if (!window.confirm(CONFIRM_TEXT)) return;
    setBusy(true);
    onResult(null);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/idioms/import?mode=${mode}`,
        { method: "POST", body: form }
      );
      if (!res.ok) {
        const err = await readError(res);
        onResult({ imported: [], rejected: err.rejected || [], datasetMismatch: err.datasetMismatch, failed: true });
        showToast(`Import failed: ${err.message}`, true);
        return;
      }
      const data = await res.json();
      onResult({
        imported: data.imported || [],
        rejected: data.rejected || [],
        datasetMismatch: !!data.dataset_mismatch,
        failed: false,
      });
      showToast(
        data.rejected?.length
          ? `Imported ${data.imported.length} file(s); ${data.rejected.length} rejected — see the list for reasons.`
          : data.message || "Images imported.",
        !!data.rejected?.length
      );
      await onImported?.();
    } catch (err) {
      showToast(`Import failed: ${err.message}`, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <input ref={inputRef} type="file" accept=".zip,application/zip" onChange={handleFile} className="hidden" />
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        disabled={busy || disabled}
        className="flex items-center gap-1 text-xs font-semibold border border-border-subtle text-on-surface-variant px-3 py-2 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40"
      >
        <span className="material-symbols-outlined text-sm">upload</span>
        {busy ? "Working…" : label}
      </button>
    </>
  );
}

// What an import took and what it rejected, each rejection with its reason.
export function IdiomImportResult({ result, mode }) {
  if (!result) return null;
  const { imported, rejected, datasetMismatch } = result;
  const paramsRejected = rejected.some((r) => r.reason?.startsWith("Parameters differ"));
  return (
    <div className="flex flex-col gap-3 text-xs">
      {datasetMismatch && (
        <div className="flex items-start gap-2 bg-red-50 border border-red-200 text-red-800 rounded-lg px-4 py-3">
          <span className="material-symbols-outlined text-base">warning</span>
          <p>
            <span className="font-semibold">Different dataset.</span> Some images in this zip were produced from a
            different dataset than the one this experiment uses. They were not imported, because they would show
            participants data that does not belong to this experiment.
          </p>
        </div>
      )}

      {imported.length > 0 && (
        <div className="border border-green-200 bg-green-50 rounded-lg px-4 py-3">
          <p className="font-semibold text-green-800 mb-1">
            Imported {imported.length} file{imported.length !== 1 ? "s" : ""}
          </p>
          <ul className="list-disc pl-5 space-y-0.5 max-h-40 overflow-y-auto text-green-900">
            {imported.map((f) => (
              <li key={f} className="font-mono">{f}</li>
            ))}
          </ul>
        </div>
      )}

      {rejected.length > 0 && (
        <div className="border border-red-200 bg-red-50 rounded-lg px-4 py-3">
          <p className="font-semibold text-red-800 mb-1">
            Rejected {rejected.length} file{rejected.length !== 1 ? "s" : ""}
          </p>
          <ul className="list-disc pl-5 space-y-1 max-h-56 overflow-y-auto text-red-900">
            {rejected.map((r, i) => (
              <li key={i}>
                <span className="font-mono">{r.file}</span> — {r.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {mode === "overview" && paramsRejected && (
        <p className="text-on-surface-variant">
          To use these images with the parameters they were drawn with, create a new experiment from the
          zip instead — <span className="font-medium">Start from a downloaded zip</span> on the
          Create New Experiment page.
        </p>
      )}
    </div>
  );
}
