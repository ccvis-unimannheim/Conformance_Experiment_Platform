"use client";

import { useState, useEffect, useCallback, useRef, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";
import EditTaskModal from "../../../../components/Admin/EditTaskModal";
import { IdiomImportButton, IdiomImportResult } from "../../../../components/Admin/IdiomImport";
import { resolveIdiomLabel } from "../../../../utils/idiomLabels";
import { queueWizardSave } from "../../../../utils/wizardSave";

function IdiomPreviewModal({ experimentId, taskKey, idiomKey, idiomLabel, datasetTitle, paramsSummary, version, onClose }) {
  const [status, setStatus] = useState("loading");
  const [enlarged, setEnlarged] = useState(false);

  useEffect(() => {
    function onKey(e) { if (e.key === "Escape") onClose(); }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  // version busts the browser cache after an image is replaced or reverted.
  const svgSrc = `/api/admin/experiments/${experimentId}/vis/${taskKey}/${idiomKey}?v=${version}`;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className={`bg-white flex flex-col overflow-hidden transition-all duration-200 ${
          enlarged ? "fixed inset-4 z-50 rounded-xl shadow-2xl" : "rounded-xl shadow-xl w-[720px] max-w-[95vw] max-h-[90vh]"
        }`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-border-subtle flex-shrink-0">
          <div>
            <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded mr-2">{taskKey}</span>
            <span className="text-sm font-semibold text-on-surface">{idiomLabel}</span>
            <span className="ml-2 text-xs text-on-surface-variant">
              ({datasetTitle || "dataset unknown"} · {paramsSummary || "default params"})
            </span>
          </div>
          <div className="flex items-center gap-2">
            {status === "ready" && (
              <button onClick={() => setEnlarged((v) => !v)} title={enlarged ? "Shrink" : "Enlarge"} className="text-on-surface-variant hover:text-primary transition-colors">
                <span className="material-symbols-outlined text-[20px]">{enlarged ? "close_fullscreen" : "open_in_full"}</span>
              </button>
            )}
            <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface transition-colors">
              <span className="material-symbols-outlined">close</span>
            </button>
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center p-6 overflow-auto bg-white min-h-[320px]">
          {status === "loading" && (
            <div className="flex flex-col items-center gap-3 text-on-surface-variant">
              <span className="material-symbols-outlined text-4xl animate-spin">autorenew</span>
              <span className="text-sm">Loading preview…</span>
            </div>
          )}
          {status === "unavailable" && (
            <div className="flex flex-col items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-on-surface-variant">image_not_supported</span>
              <p className="text-sm text-on-surface-variant text-center">Preview not available.<br/><span className="text-xs">Generate the visualizations on the Specify step, or upload an image for this idiom.</span></p>
            </div>
          )}
          <img
            src={svgSrc}
            alt={`${taskKey} ${idiomKey} preview`}
            style={{ display: status === "ready" ? undefined : "none" }}
            className={enlarged ? "max-w-full max-h-full object-contain" : "max-w-full max-h-[65vh] object-contain"}
            onLoad={() => setStatus("ready")}
            onError={() => setStatus("unavailable")}
          />
        </div>
      </div>
    </div>
  );
}

function getId(obj) {
  return obj._id || obj.id;
}

async function errorMessage(res) {
  const body = await res.json().catch(() => null);
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (detail?.message) return detail.message;
  return `HTTP ${res.status}`;
}

function formatDate(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleString();
}

// Where the image participants will see for this idiom comes from, in the
// order participants get it (see backend utils/idiom_files.resolve_idiom_image).
function imageSourceNote(idiom, ti, uploaded, datasetTitle) {
  const muted = "text-on-surface-variant";
  if (uploaded) {
    const from = ti?.images_imported_from?.experiment_name;
    return {
      text: from ? `Imported from "${from}"` : "Uploaded image",
      className: "text-amber-800 font-semibold",
    };
  }
  if (idiom.is_custom) return { text: "Custom idiom · uploaded image", className: muted };
  switch (ti?.generation_status) {
    case "ready":
      return { text: datasetTitle ? `Generated from ${datasetTitle}` : "Generated", className: muted };
    case "running":
      return { text: "Generating…", className: muted };
    case "failed":
      return { text: "Generation failed", className: "text-error font-semibold" };
    default:
      return { text: "Not generated yet", className: "text-amber-800" };
  }
}

// Export / import of the experiment's idiom images (see backend routers/idiom_bundle.py).
// Import here keeps this experiment's parameters: a task whose zip parameters
// differ is rejected. Importing images together with their parameters happens
// on the Specify step.
function IdiomFilesPanel({ experimentId, editable, bundleOnly, overrides, importInfo, onChanged, showToast }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null); // see IdiomImportResult

  async function handleRevertAll() {
    if (!window.confirm(
      "Revert all uploaded and imported images? The generated images will be shown again, " +
      "and the parameters of imported tasks become editable on the Specify step."
    )) return;
    setBusy(true);
    try {
      const res = await fetch(`/api/admin/experiments/${encodeURIComponent(experimentId)}/idioms/overrides`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(await errorMessage(res));
      setResult(null);
      showToast("Reverted to the generated images.");
      await onChanged();
    } catch (err) {
      showToast(`Revert failed: ${err.message}`, true);
    } finally {
      setBusy(false);
    }
  }

  const from = importInfo?.from;
  return (
    <div className="bg-white border border-border-subtle rounded-lg p-5 flex flex-col gap-4">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-xl">
          <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">Idiom Images</p>
          <p className="text-xs text-on-surface-variant">
            Download the exact images participants see (with a manifest of how they were produced) to archive
            them or reproduce the study. Importing a downloaded zip keeps those images fixed, even if the
            experiment is regenerated.
          </p>
          {editable && !bundleOnly && (
            <p className="text-xs text-on-surface-variant mt-2">
              <span className="font-semibold text-on-surface">Import here only takes images that match this experiment:</span>{" "}
              a task is rejected if its images come from a different dataset or were drawn with different
              parameters than the ones set on the Specify step. It changes the images and those tasks&apos;
              parameters, and asks before it does. To use a zip with its own tasks, idioms and settings
              instead, create a new experiment from it on the{" "}
              <Link href="/admin/experiments/new" className="text-primary hover:underline">
                Create New Experiment
              </Link>{" "}
              page.
            </p>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <a
            href={`/api/admin/experiments/${encodeURIComponent(experimentId)}/idioms/export`}
            className="flex items-center gap-1 text-xs font-semibold border border-primary text-primary px-3 py-2 rounded-lg hover:bg-primary/5 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">download</span>
            Download Idioms
          </a>
          {editable && !bundleOnly && (
            <IdiomImportButton
              experimentId={experimentId}
              mode="overview"
              disabled={busy}
              onImported={onChanged}
              onResult={setResult}
              showToast={showToast}
            />
          )}
        </div>
      </div>

      {overrides.size > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 bg-amber-50 border border-amber-200 rounded-lg px-4 py-3">
          <p className="text-xs text-amber-800">
            <span className="font-semibold">{overrides.size} image{overrides.size !== 1 ? "s" : ""}</span> come from
            uploaded files rather than the generator
            {importInfo?.at && (
              <>
                {" "}— imported {formatDate(importInfo.at)}
                {from?.experiment_name ? ` from "${from.experiment_name}"` : from?.file ? ` from ${from.file}` : ""}
              </>
            )}
            {bundleOnly
              ? ". This experiment has no dataset, so these are the only images it has."
              : ". They stay in place when the experiment is regenerated."}
          </p>
          {editable && !bundleOnly && (
            <button
              type="button"
              onClick={handleRevertAll}
              disabled={busy}
              className="flex items-center gap-1 text-xs font-semibold text-amber-800 hover:underline disabled:opacity-40"
            >
              <span className="material-symbols-outlined text-sm">restart_alt</span>
              Revert all
            </button>
          )}
        </div>
      )}

      <IdiomImportResult result={result} mode="overview" />
    </div>
  );
}

// A PARAM_SPEC entry only applies when the parameters it depends on have the
// values it names — the mirror of entryApplies() on the Specify page, so this
// page lists exactly the controls that page showed.
function entryApplies(entry, values) {
  const cond = entry.visible_if;
  if (!cond) return true;
  return Object.entries(cond).every(([key, want]) => {
    const have = values?.[key];
    return Array.isArray(want) ? want.includes(have) : have === want;
  });
}

function showParamValue(value) {
  if (value === undefined || value === null || value === "") return null;
  if (Array.isArray(value)) return value.length ? value.join(", ") : null;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  return String(value);
}

const PARAMS_SHOWN = 4;

// One line of "label: value" for the preview modal's caption.
function paramSummary(spec, values) {
  const entries = Object.entries(values || {});
  if (entries.length === 0) return null;
  const labels = new Map((spec || []).map((e) => [e.key, e.label || e.key]));
  return entries
    .map(([key, value]) => [labels.get(key) || key, showParamValue(value)])
    .filter(([, value]) => value !== null)
    .map(([label, value]) => `${label}: ${value}`)
    .join(" · ") || null;
}

// The hyperparameters this task was generated with. Reviewing an experiment
// before publishing means checking what participants will be shown, and the
// parameters decide what the figures say — they were only visible on /specify,
// and in the preview modal as raw keys.
function TaskParametersSection({ spec, values, imported, editable, bundleOnly, experimentId }) {
  const [expanded, setExpanded] = useState(false);
  if (!spec || spec.length === 0) return null;

  const rows = spec
    .filter((entry) => entryApplies(entry, values))
    .map((entry) => {
      const set = showParamValue(values?.[entry.key]);
      return {
        key: entry.key,
        label: entry.label || entry.key,
        value: set ?? showParamValue(entry.default) ?? "—",
        isDefault: set === null,
      };
    });
  if (rows.length === 0) return null;

  const shown = expanded ? rows : rows.slice(0, PARAMS_SHOWN);

  return (
    <div className="p-5">
      <div className="flex items-center justify-between mb-3 gap-3">
        <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
          Parameters
          <span className="ml-2 font-normal normal-case tracking-normal text-primary">({rows.length})</span>
        </p>
        {editable && !bundleOnly && !imported && (
          <Link
            href={`/admin/experiments/specify?experiment_id=${encodeURIComponent(experimentId)}&return_to=overview`}
            className="text-xs text-primary border border-primary/30 px-3 py-1.5 rounded hover:bg-blue-50 transition-colors flex-shrink-0"
          >
            Change on Specify
          </Link>
        )}
      </div>

      {imported && (
        <p className="text-xs text-amber-800 bg-amber-50 border border-amber-200 rounded px-3 py-2 mb-3">
          These are the parameters the imported images were drawn with, so they cannot be edited.
        </p>
      )}

      <dl className="grid sm:grid-cols-2 gap-x-6 gap-y-2">
        {shown.map((row) => (
          <div key={row.key} className="min-w-0">
            <dt className="text-xs text-on-surface-variant truncate" title={row.label}>{row.label}</dt>
            <dd className="text-xs font-medium text-on-surface break-words">
              {row.value}
              {row.isDefault && <span className="ml-1 font-normal text-on-surface-variant">(default)</span>}
            </dd>
          </div>
        ))}
      </dl>

      {rows.length > PARAMS_SHOWN && (
        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          className="mt-2 text-xs text-primary hover:underline"
        >
          {expanded ? "Show fewer" : `+${rows.length - PARAMS_SHOWN} more`}
        </button>
      )}
    </div>
  );
}

// Name, design and task order, changeable while the experiment is a draft.
// The wizard asks for these on /new, which an experiment built from a zip never
// visits — and which shows a dataset table that route has no use for, so
// stepping back there is not the answer. Saved one field at a time, so a
// half-finished edit cannot be published by accident.
function ExperimentSettingsCard({ experiment, experimentId, editable, showToast, onSaved }) {
  const [name, setName] = useState(experiment.name || "");
  const [busy, setBusy] = useState(false);
  const design = experiment.design_type || "between";
  const randomised = (experiment.within_sequence_mode || "fixed") === "random";

  async function save(fields) {
    setBusy(true);
    try {
      const res = await fetch(`/api/admin/experiments/${encodeURIComponent(experimentId)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
      if (!res.ok) throw new Error(await errorMessage(res));
      await onSaved();
    } catch (e) {
      showToast(`Could not save: ${e.message}`, true);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="bg-white border border-border-subtle rounded-lg p-5">
      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">
        Experiment settings
      </p>
      <p className="text-xs text-on-surface-variant mb-3">
        {editable
          ? "How the tasks are shown to participants. Changing the design changes how idioms are allocated, so it is only possible while this is a draft."
          : "Read-only: participants have been assigned under these settings."}
      </p>

      <div className="flex flex-col gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-on-surface w-44">Name</span>
          <input
            type="text"
            value={name}
            disabled={!editable || busy}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => {
              const next = name.trim();
              if (next && next !== experiment.name) save({ name: next });
            }}
            className="flex-1 min-w-[12rem] text-xs px-3 py-2 rounded border border-border-subtle disabled:bg-surface-container"
          />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-on-surface w-44">Study design</span>
          <div className="flex gap-2 flex-1 min-w-[12rem]">
            {[
              { value: "between", label: "Between-subjects", title: "One idiom per task, balanced across participants." },
              { value: "within", label: "Within-subjects", title: "Every participant sees all idioms of every task." },
            ].map(({ value, label, title }) => (
              <button
                key={value}
                type="button"
                title={title}
                disabled={!editable || busy || design === value}
                onClick={() => save({ design_type: value })}
                className={`text-xs px-3 py-2 rounded border transition-colors ${
                  design === value
                    ? "border-primary text-primary bg-primary/5 font-semibold"
                    : "border-border-subtle text-on-surface-variant hover:bg-surface-container disabled:opacity-40"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
        </div>

        <label className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold text-on-surface w-44">Task order</span>
          <span className="flex items-center gap-2 text-xs text-on-surface-variant">
            <input
              type="checkbox"
              checked={randomised}
              disabled={!editable || busy}
              onChange={() => save({ within_sequence_mode: randomised ? "fixed" : "random" })}
            />
            Randomised per participant
          </span>
        </label>
      </div>
    </div>
  );
}

// What participants meet before the tasks. Every experiment has these, set or
// not: an experiment that skipped those wizard steps — one built from a zip
// always does — is on the defaults, which is a choice the admin never made.
// The card says what each is now and links to the step that changes it.
function ParticipantFlowCard({ experiment, experimentId }) {
  // return_to=overview: these steps otherwise send Next on to the next step in
  // sequence, which would walk the admin through the whole wizard again just to
  // fix one setting reviewed from here.
  const q = `?experiment_id=${encodeURIComponent(experimentId)}&return_to=overview`;
  const sections = (list, all) => (list ? list.length : all);
  const prequestionnaire = sections(experiment.prequestionnaire_sections, 4);
  const concepts = sections(experiment.concept_sections, 4);
  const taskintro = sections(experiment.taskintro_sections, 6);
  const knowledge = experiment.knowledge_questions_configured
    ? `${(experiment.knowledge_question_ids || []).length} selected`
    : "all system questions (default)";

  const rows = [
    {
      label: "Pre-questionnaire",
      value: prequestionnaire === 0 ? "skipped" : `${prequestionnaire} section(s)`,
      href: `/admin/experiments/prequestionnaire${q}`,
    },
    { label: "Knowledge questions", value: knowledge, href: `/admin/experiments/knowledge${q}` },
    {
      label: "Intro pages",
      value: `Key Concepts: ${concepts === 0 ? "skipped" : `${concepts} section(s)`} · `
        + `Before You Begin: ${taskintro === 0 ? "skipped" : `${taskintro} section(s)`}`,
      href: `/admin/experiments/concepts${q}`,
    },
  ];

  return (
    <div className="bg-white border border-border-subtle rounded-lg p-5">
      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">
        Participant flow
      </p>
      <p className="text-xs text-on-surface-variant mb-3">
        What participants see before the tasks. Anything not set here uses the platform&apos;s defaults.
      </p>
      <div className="flex flex-col divide-y divide-border-subtle">
        {rows.map((row) => (
          <div key={row.label} className="flex flex-wrap items-center gap-2 py-2">
            <span className="text-xs font-semibold text-on-surface w-44">{row.label}</span>
            <span className="text-xs text-on-surface-variant flex-1 min-w-[10rem]">{row.value}</span>
            <Link href={row.href} className="text-xs text-primary hover:underline">
              View / change
            </Link>
          </div>
        ))}
      </div>
    </div>
  );
}

const STATUS_STYLES = {
  pending: { label: "Pending", icon: "schedule", className: "bg-surface-container text-on-surface-variant" },
  running: { label: "Generating…", icon: "autorenew", className: "bg-yellow-100 text-yellow-800", spin: true },
  ready: { label: "Ready", icon: "check_circle", className: "bg-green-100 text-green-800" },
  failed: { label: "Failed", icon: "error", className: "bg-red-100 text-red-800" },
};

function StatusBadge({ status }) {
  const s = STATUS_STYLES[status] || STATUS_STYLES.pending;
  return (
    <span className={`inline-flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-full ${s.className}`}>
      <span className={`material-symbols-outlined text-sm ${s.spin ? "animate-spin" : ""}`}>{s.icon}</span>
      {s.label}
    </span>
  );
}

// The configured answer options, if this task's format presents a closed set.
function AnswerSummary({ ti }) {
  const options = ti?.answer_options || [];
  if (options.length === 0) {
    return (
      <p className="text-xs text-on-surface-variant italic">
        Free input — no options to configure.
      </p>
    );
  }
  const shown = options.slice(0, 8);
  return (
    <ul className="flex flex-wrap gap-2">
      {shown.map((opt, i) => (
        <li
          key={i}
          className="text-xs px-2 py-1 rounded-full border border-border-subtle text-on-surface-variant"
        >
          {opt.label || opt.value}
        </li>
      ))}
      {options.length > shown.length && (
        <li className="text-xs px-2 py-1 text-on-surface-variant italic">
          +{options.length - shown.length} more
        </li>
      )}
    </ul>
  );
}

function ExperimentOverviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [experiment, setExperiment] = useState(null);
  const [idiomMap, setIdiomMap] = useState({});
  const [groupedTasks, setGroupedTasks] = useState([]);
  const [taskInstancesByTask, setTaskInstancesByTask] = useState({});
  // Formats that present a closed option set (from /admin/answer-formats).
  const [optionFormats, setOptionFormats] = useState(new Set());
  const [datasetTitleById, setDatasetTitleById] = useState({});
  // task_key -> PARAM_SPEC, for naming each task's parameters below.
  const [paramSpecByTaskKey, setParamSpecByTaskKey] = useState({});
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("draft");

  const [publishConflict, setPublishConflict] = useState(null);
  const [publishing, setPublishing] = useState(false);

  const [previewModal, setPreviewModal] = useState(null); // { taskKey, idiomKey, idiomLabel }
  const [editingTask, setEditingTask] = useState(null);

  // Images uploaded/imported in place of generated ones, as "task_key/idiom_key".
  const [overrides, setOverrides] = useState(new Set());
  const [importInfo, setImportInfo] = useState(null); // { at, from }
  const [imageVersion, setImageVersion] = useState(0);
  const replaceInputRef = useRef(null);
  const replaceTargetRef = useRef(null); // { taskKey, idiomKey }

  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => setToast((t) => ({ ...t, visible: false })), []);

  useEffect(() => {
    if (!experimentId) {
      router.replace("/admin/experiments/task");
      return;
    }
    init();
  }, [experimentId]);

  async function init() {
    setLoading(true);
    try {
      const [expRes, tasksRes, idiomsRes, datasetsRes, formatsRes] = await Promise.all([
        fetch(`/api/admin/experiments`),
        fetch(`/api/admin/tasks?experiment_id=${encodeURIComponent(experimentId)}`),
        fetch(`/api/admin/idioms`),
        fetch(`/api/admin/datasets`),
        fetch(`/api/admin/answer-formats`),
      ]);
      if (!expRes.ok) throw new Error(`Experiments HTTP ${expRes.status}`);
      if (!tasksRes.ok) throw new Error(`Tasks HTTP ${tasksRes.status}`);
      if (!idiomsRes.ok) throw new Error(`Idioms HTTP ${idiomsRes.status}`);
      if (!datasetsRes.ok) throw new Error(`Datasets HTTP ${datasetsRes.status}`);

      const [exps, tasks, idioms, datasets] = await Promise.all([
        expRes.json(),
        tasksRes.json(),
        idiomsRes.json(),
        datasetsRes.json(),
      ]);

      if (formatsRes.ok) {
        const fmt = await formatsRes.json();
        setOptionFormats(
          new Set((fmt.answer_formats || []).filter((f) => f.needs_options).map((f) => f.key))
        );
      }

      const dMap = {};
      (datasets || []).forEach((d) => { dMap[d.dataset_id] = d.dataset_title; });
      setDatasetTitleById(dMap);

      const exp = exps.find((e) => getId(e) === experimentId);
      if (!exp) throw new Error("Experiment not found.");
      setExperiment(exp);
      setStatus(exp.status || "draft");
      if (exp.status === "draft") {
        queueWizardSave(experimentId, "overview", {}).catch(() => {});
      }

      const tMap = {};
      tasks.forEach((t) => { tMap[getId(t)] = t; });

      const iMap = {};
      idioms.forEach((i) => { iMap[getId(i)] = i; });
      setIdiomMap(iMap);

      const tiMap = {};
      (exp.task_instances || []).forEach((ti) => { tiMap[ti.task_id] = ti; });
      setTaskInstancesByTask(tiMap);

      // Group task_configs: one entry per unique task_id, collecting all idiom_ids
      const idiomsByTask = {};
      const taskOrder = [];
      const seen = new Set();
      (exp.task_configs || []).forEach((tc) => {
        if (!seen.has(tc.task_id)) {
          seen.add(tc.task_id);
          taskOrder.push(tc.task_id);
          idiomsByTask[tc.task_id] = [];
        }
        if (tc.idiom_id) idiomsByTask[tc.task_id].push(tc.idiom_id);
      });

      setGroupedTasks(
        taskOrder.map((tid) => ({
          task: tMap[tid] || { _id: tid, task_key: tid, label: "(unknown task)", description: "" },
          idiomIds: idiomsByTask[tid] || [],
        }))
      );
      await loadParamSpecs(taskOrder, tMap, tiMap);
      await loadOverrides();
    } catch (e) {
      showToast(`Could not load experiment: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  // The hyperparameters each task was generated with, read back through the
  // same PARAM_SPEC the Specify page renders, so the review step names them as
  // that step did instead of showing raw keys. Custom tasks have no generator
  // and no spec.
  async function loadParamSpecs(taskOrder, tMap, tiMap) {
    const keys = new Map(); // task_key -> dataset_id, one request per task
    taskOrder.forEach((tid) => {
      const taskKey = tMap[tid]?.task_key;
      if (taskKey && !tMap[tid]?.is_custom && !keys.has(taskKey)) {
        keys.set(taskKey, tiMap[tid]?.dataset_id || "");
      }
    });
    const specs = {};
    await Promise.all(
      [...keys].map(async ([taskKey, datasetId]) => {
        try {
          const res = await fetch(
            `/api/admin/tasks/${encodeURIComponent(taskKey)}/param-spec?dataset_id=${encodeURIComponent(datasetId)}`
          );
          if (res.ok) specs[taskKey] = (await res.json()).param_spec || [];
        } catch {
          // No spec — the task's parameters section is simply left out.
        }
      })
    );
    setParamSpecByTaskKey(specs);
  }

  async function loadOverrides() {
    const res = await fetch(`/api/admin/experiments/${encodeURIComponent(experimentId)}/idioms/overrides`);
    if (!res.ok) return;
    const data = await res.json();
    setOverrides(new Set((data.overrides || []).map((o) => `${o.task_key}/${o.idiom_key}`)));
    setImportInfo(data.imported_at ? { at: data.imported_at, from: data.imported_from } : null);
  }

  // After images change: new previews, override badges, and generation
  // statuses (the backend marks tasks ready once every idiom has an image).
  async function refreshImages() {
    setImageVersion((v) => v + 1);
    await loadOverrides();
    const res = await fetch(`/api/admin/experiments`);
    if (!res.ok) return;
    const exp = (await res.json()).find((e) => getId(e) === experimentId);
    if (!exp) return;
    setExperiment(exp);
    const tiMap = {};
    (exp.task_instances || []).forEach((ti) => { tiMap[ti.task_id] = ti; });
    setTaskInstancesByTask(tiMap);
  }

  function pickReplacement(taskKey, idiomKey) {
    replaceTargetRef.current = { taskKey, idiomKey };
    replaceInputRef.current?.click();
  }

  async function handleReplaceFile(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    const target = replaceTargetRef.current;
    if (!file || !target) return;
    // Asked only once the file is chosen: a confirm() before click() would use
    // up the user gesture the browser needs to open the file dialog.
    if (!window.confirm(
      `Show "${file.name}" to participants instead of ${target.taskKey} / ${target.idiomKey}? ` +
      "The parameters shown to participants will not change to match it, so make sure the image " +
      "depicts the same data and settings."
    )) return;
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/idioms/${encodeURIComponent(target.taskKey)}/${encodeURIComponent(target.idiomKey)}`,
        { method: "POST", body: form }
      );
      if (!res.ok) throw new Error(await errorMessage(res));
      showToast(`Replaced ${target.taskKey} / ${target.idiomKey}.`);
      await refreshImages();
    } catch (err) {
      showToast(`Replace failed: ${err.message}`, true);
    }
  }

  async function revertImage(taskKey, idiomKey) {
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/idioms/${encodeURIComponent(taskKey)}/${encodeURIComponent(idiomKey)}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error(await errorMessage(res));
      showToast(`${taskKey} / ${idiomKey} shows the generated image again.`);
      await refreshImages();
    } catch (err) {
      showToast(`Revert failed: ${err.message}`, true);
    }
  }

  async function saveEditedTask(payload) {
    const taskId = getId(editingTask);
    // Stored on this experiment's task instance, not on the shared question
    // bank — see PATCH /admin/tasks/{id} in admin.py.
    const res = await fetch(
      `/api/admin/tasks/${encodeURIComponent(taskId)}` +
        `?experiment_id=${encodeURIComponent(experimentId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await res.text());
    showToast("Task updated for this experiment.");
    await init();
  }

  async function saveAsDraft() {
    try {
      const res = await fetch(`/api/admin/experiments/${experimentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "draft" }),
      });
      if (!res.ok) throw new Error(await res.text());
      setStatus("draft");
      showToast("Experiment saved as draft.");
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, true);
    }
  }

  async function _doPublish() {
    setPublishing(true);
    try {
      const res = await fetch(
        `/api/admin/experiments/${experimentId}/status?status=published`,
        { method: "PATCH" }
      );
      if (!res.ok) throw new Error(await res.text());
      setStatus("published");
      showToast("Experiment published successfully!");
    } catch (e) {
      showToast(`Failed to publish: ${e.message}`, true);
    } finally {
      setPublishing(false);
    }
  }

  const taskInstancesList = Object.values(taskInstancesByTask);
  // A format alone isn't enough: an option-bearing format with no options would
  // show the participant an empty question.
  const answerConfigured = (ti) =>
    !!ti.answer_format &&
    (!optionFormats.has(ti.answer_format) || (ti.answer_options || []).length > 0);
  const allReadyAndFormatted =
    taskInstancesList.length > 0 &&
    taskInstancesList.every((ti) => ti.generation_status === "ready" && answerConfigured(ti));

  async function publishExperiment() {
    if (publishing) return;
    if (!allReadyAndFormatted) {
      showToast(
        "All tasks must finish generating (status: Ready) and have an answer format — with options, where the format needs them — before publishing.",
        true
      );
      return;
    }
    try {
      const res = await fetch(`/api/admin/experiments`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const exps = await res.json();
      const conflict = exps.find(
        (e) => getId(e) !== experimentId && (e.status || e.experiment_status) === "published"
      );
      if (conflict) {
        setPublishConflict(conflict);
        return;
      }
      await _doPublish();
    } catch (e) {
      showToast(`Failed to publish: ${e.message}`, true);
    }
  }

  async function confirmFinishAndPublish() {
    if (!publishConflict) return;
    const conflictId = getId(publishConflict);
    setPublishing(true);
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(conflictId)}/status?status=finished`,
        { method: "PATCH" }
      );
      if (!res.ok) throw new Error(`Failed to finish existing: ${await res.text()}`);
      setPublishConflict(null);
      await _doPublish();
    } catch (e) {
      showToast(e.message, true);
      setPublishing(false);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader
        experimentId={experimentId}
        step="overview"
        bundleOnly={!!experiment?.bundle_only}
      />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        {/* Published banner */}
        {status === "published" && (
          <div className="flex items-center gap-3 bg-green-50 border border-green-200 rounded-lg px-5 py-4">
            <span className="material-symbols-outlined text-green-600 text-2xl icon-filled">check_circle</span>
            <div>
              <p className="text-sm font-bold text-green-800">Experiment is published and active</p>
              <p className="text-xs text-green-700">Participants can now access and complete this experiment.</p>
            </div>
          </div>
        )}

        {/* Page heading */}
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Experiment Overview</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            {status === "published"
              ? "This experiment is published and accepting participants. The configuration below is read-only."
              : "Review the tasks and idioms selected for this experiment. Use the buttons below to save as a draft or publish when ready."}
          </p>
        </div>

        {/* Built from an uploaded zip: there is no dataset and nothing to generate. */}
        {experiment?.bundle_only && (
          <div className="flex items-start gap-2 bg-blue-50 border border-blue-200 text-blue-900 rounded-lg px-4 py-3">
            <span className="material-symbols-outlined text-base">folder_zip</span>
            <p className="text-xs">
              <span className="font-semibold">This experiment&apos;s images come from an uploaded zip.</span>{" "}
              Its tasks, idioms and images are the ones in that file, so it has no dataset and no
              Specify step — there is nothing to generate. Replace a single image below to change one.
            </p>
          </div>
        )}

        {/* Metadata strip */}
        {experiment && (
          <div className={`border rounded-lg p-5 flex flex-wrap items-center gap-6 ${
            status === "published" ? "bg-green-50 border-green-200" : "bg-white border-border-subtle"
          }`}>
            <div className="flex-1 min-w-[160px]">
              <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-0.5">
                Experiment Name
              </p>
              <p className="text-sm font-semibold text-on-surface">
                {experiment.name || "(unnamed)"}
              </p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-0.5">
                ID
              </p>
              <p className="text-xs text-on-surface-variant font-mono">{experimentId}</p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-0.5">
                Tasks
              </p>
              <p className="text-sm font-semibold text-on-surface">{groupedTasks.length}</p>
            </div>
            <div>
              <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-0.5">
                Status
              </p>
              {status === "published" ? (
                <span className="inline-flex items-center gap-1.5 text-sm font-bold text-green-700 bg-green-100 border border-green-300 px-3 py-1 rounded-full">
                  <span className="material-symbols-outlined text-base icon-filled">check_circle</span>
                  Published
                </span>
              ) : (
                <span className="text-xs px-2 py-0.5 rounded-full font-semibold bg-yellow-100 text-yellow-800">
                  {status}
                </span>
              )}
            </div>
          </div>
        )}

        {experiment && (
          <ExperimentSettingsCard
            experiment={experiment}
            experimentId={experimentId}
            editable={status === "draft"}
            showToast={showToast}
            onSaved={init}
          />
        )}

        {experiment && <ParticipantFlowCard experiment={experiment} experimentId={experimentId} />}

        {experiment && (
          <IdiomFilesPanel
            experimentId={experimentId}
            editable={status === "draft"}
            bundleOnly={!!experiment.bundle_only}
            overrides={overrides}
            importInfo={importInfo}
            onChanged={refreshImages}
            showToast={showToast}
          />
        )}
        <input
          ref={replaceInputRef}
          type="file"
          accept=".svg,.png,.jpg,.jpeg,image/svg+xml,image/png,image/jpeg"
          onChange={handleReplaceFile}
          className="hidden"
        />

        {/* Task cards */}
        {loading ? (
          <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
            <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
              hourglass_empty
            </span>
            Loading…
          </div>
        ) : groupedTasks.length === 0 ? (
          <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
            <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
              inbox
            </span>
            No task-idiom assignments found.
            <br />
            <Link
              href={`/admin/experiments/idiom${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`}
              className="text-xs text-primary mt-1 inline-block hover:underline"
            >
              ← Go back to assign idioms
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {groupedTasks.map(({ task, idiomIds }) => {
              const tid = getId(task);
              const ti = taskInstancesByTask[tid];
              const formatHref = `/admin/experiments/answer-format?experiment_id=${encodeURIComponent(experimentId)}&return_to=overview`;
              return (
                <div
                  key={tid}
                  className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden"
                >
                  {/* Task header */}
                  <div className="border-l-4 border-primary p-5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3 min-w-0">
                        <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded flex-shrink-0 mt-0.5">
                          {task.task_key}
                        </span>
                        <div>
                          <p className="text-sm font-semibold text-on-surface leading-snug">
                            {task.label}
                          </p>
                          {task.description && (
                            <p className="text-xs text-on-surface-variant mt-0.5">
                              {task.description}
                            </p>
                          )}
                        </div>
                      </div>
                      <button
                        onClick={() => setEditingTask(task)}
                        className="text-xs text-primary border border-primary/30 px-3 py-1.5 rounded hover:bg-blue-50 transition-colors flex-shrink-0"
                      >
                        Edit
                      </button>
                    </div>
                  </div>

                  <div className="divide-y divide-border-subtle border-t border-border-subtle">
                    {/* Selected Idioms */}
                    <div className="p-5">
                      <div className="flex items-center justify-between mb-3">
                        <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                          Selected Idioms
                          <span className="ml-2 font-normal normal-case tracking-normal text-primary">
                            ({idiomIds.length})
                          </span>
                        </p>
                        <Link
                          href={`/admin/experiments/idiom?experiment_id=${encodeURIComponent(experimentId)}&return_to=overview`}
                          className="text-xs text-primary border border-primary/30 px-3 py-1.5 rounded hover:bg-blue-50 transition-colors flex-shrink-0"
                        >
                          Edit
                        </Link>
                      </div>
                      {idiomIds.length === 0 ? (
                        <p className="text-xs text-on-surface-variant italic">No idioms assigned.</p>
                      ) : (
                        <div className="flex flex-wrap gap-2">
                          {idiomIds.map((iid) => {
                            const idiom = idiomMap[iid];
                            return (
                              <div
                                key={iid}
                                className="flex items-center gap-2 bg-blue-50 border border-primary/20 rounded-lg px-3 py-2"
                              >
                                <span className="material-symbols-outlined text-sm text-primary icon-filled">
                                  check_circle
                                </span>
                                <div>
                                  <p className="text-xs font-semibold text-on-surface">
                                    {idiom
                                      ? resolveIdiomLabel(task.task_key, idiom.idiom_key, idiom.label)
                                      : iid}
                                  </p>
                                  {idiom && (() => {
                                    const note = imageSourceNote(
                                      idiom, ti,
                                      overrides.has(`${task.task_key}/${idiom.idiom_key}`),
                                      datasetTitleById[ti?.dataset_id],
                                    );
                                    return <p className={`text-[10px] ${note.className}`}>{note.text}</p>;
                                  })()}
                                </div>
                                {idiom && status === "draft" && (
                                  <button
                                    onClick={() => pickReplacement(task.task_key, idiom.idiom_key)}
                                    title="Replace this image with a file from your computer"
                                    className="text-on-surface-variant hover:text-primary transition-colors p-0.5 rounded flex-shrink-0"
                                  >
                                    <span className="material-symbols-outlined text-[16px]">upload</span>
                                  </button>
                                )}
                                {/* A bundle experiment has no generated image to go back to. */}
                                {idiom && status === "draft" && !experiment?.bundle_only
                                  && overrides.has(`${task.task_key}/${idiom.idiom_key}`) && (
                                  <button
                                    onClick={() => revertImage(task.task_key, idiom.idiom_key)}
                                    title="Revert to the generated image"
                                    className="text-on-surface-variant hover:text-primary transition-colors p-0.5 rounded flex-shrink-0"
                                  >
                                    <span className="material-symbols-outlined text-[16px]">restart_alt</span>
                                  </button>
                                )}
                                {idiom && (
                                  <button
                                    onClick={() => setPreviewModal({
                                      taskKey: task.task_key,
                                      idiomKey: idiom.idiom_key,
                                      idiomLabel: resolveIdiomLabel(task.task_key, idiom.idiom_key, idiom.label),
                                      datasetTitle: datasetTitleById[ti?.dataset_id] || null,
                                      // Named as the Specify page named them, not by raw key.
                                      paramsSummary: paramSummary(
                                        paramSpecByTaskKey[task.task_key], ti?.parameters
                                      ),
                                    })}
                                    title="Preview this idiom"
                                    className="text-on-surface-variant hover:text-primary transition-colors p-0.5 rounded flex-shrink-0"
                                  >
                                    <span className="material-symbols-outlined text-[16px]">visibility</span>
                                  </button>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

                    {/* What this task's figures were drawn with */}
                    <TaskParametersSection
                      spec={paramSpecByTaskKey[task.task_key]}
                      values={ti?.parameters}
                      imported={!!ti?.images_imported_from}
                      editable={status === "draft"}
                      bundleOnly={!!experiment?.bundle_only}
                      experimentId={experimentId}
                    />

                    {/* Answer Format */}
                    <div className="p-5">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                          Answer Format
                        </p>
                        <StatusBadge status={ti?.generation_status || "pending"} />
                      </div>
                      <div className="border border-border-subtle rounded-lg p-4 flex items-center justify-between gap-4">
                        <div className="flex items-center gap-2">
                          {ti?.answer_format ? (
                            <span className="text-xs font-semibold bg-blue-100 text-primary px-2.5 py-1 rounded-full">
                              {ti.answer_format}
                            </span>
                          ) : (
                            <span className="text-xs text-on-surface-variant italic">Not set</span>
                          )}
                          {(ti?.answer_options || []).length > 0 && (
                            <span className="text-xs font-semibold bg-surface-container text-on-surface-variant px-2.5 py-1 rounded-full">
                              {ti.answer_options.length} option
                              {ti.answer_options.length === 1 ? "" : "s"}
                            </span>
                          )}
                          {ti?.number_kind && (
                            <span className="text-xs font-semibold bg-surface-container text-on-surface-variant px-2.5 py-1 rounded-full">
                              {ti.number_kind}
                            </span>
                          )}
                        </div>
                        <Link
                          href={formatHref}
                          className="text-xs text-primary border border-primary/30 px-3 py-1.5 rounded hover:bg-blue-50 transition-colors flex-shrink-0"
                        >
                          Configure
                        </Link>
                      </div>
                    </div>

                    {/* Answer options */}
                    <div className="p-5">
                      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-2">
                        Answer Options
                      </p>
                      <div className="border border-border-subtle rounded-lg p-4 flex items-start justify-between gap-4">
                        <AnswerSummary ti={ti} />
                        <Link
                          href={formatHref}
                          className="text-xs text-primary border border-primary/30 px-3 py-1.5 rounded hover:bg-blue-50 transition-colors flex-shrink-0"
                        >
                          Edit
                        </Link>
                      </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>

      {/* Footer action bar */}
      <div className={`border-t sticky bottom-0 ${status === "published" ? "border-green-200 bg-green-50" : "border-border-subtle bg-white"}`}>
        <div className="max-w-[1140px] mx-auto px-8 py-4 flex justify-between items-center">
          <Link
            href={
              experiment?.bundle_only
                // Its tasks, idioms and images all came from the zip uploaded
                // on /new, and a v3 zip that already carried answer formats
                // never visits /answer-format at all — /new is where editing
                // this experiment actually starts, not its bar-neighbour.
                ? `/admin/experiments/new${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`
                : `/admin/experiments/answer-format${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`
            }
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          {status === "published" ? (
            <div className="flex items-center gap-4">
              <span className="flex items-center gap-2 text-sm font-semibold text-green-700">
                <span className="material-symbols-outlined text-lg icon-filled text-green-600">check_circle</span>
                Experiment is published and active
              </span>
              <button
                onClick={() => router.push("/admin")}
                className="flex items-center gap-2 text-sm font-semibold bg-green-700 text-white px-6 py-2.5 rounded-lg hover:bg-green-800 transition-colors"
              >
                <span className="material-symbols-outlined text-sm">dashboard</span>
                Back to Admin Home page
              </button>
            </div>
          ) : (
            <div className="flex items-center gap-3">
              <button
                onClick={saveAsDraft}
                className="flex items-center gap-2 text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors"
              >
                <span className="material-symbols-outlined text-sm">save</span>
                Save as Draft
              </button>
              <div className="flex flex-col items-end gap-1">
                <button
                  onClick={publishExperiment}
                  disabled={publishing || !allReadyAndFormatted}
                  className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-8 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <span className="material-symbols-outlined text-sm">publish</span>
                  {publishing ? "Publishing..." : "Publish Experiment"}
                </button>
                {!allReadyAndFormatted && (
                  <p className="text-[10px] text-on-surface-variant">
                    All tasks need status Ready and a complete answer format.
                  </p>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {publishConflict && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-md mx-4 flex flex-col gap-4">
            <div className="flex items-center gap-3">
              <span className="material-symbols-outlined text-4xl text-amber-500">warning</span>
              <h2 className="text-h2 text-on-surface">Another experiment is published</h2>
            </div>
            <p className="text-body-sm text-on-surface-variant">
              &quot;<span className="font-semibold">{publishConflict.name || publishConflict.experiment_name || "(unnamed)"}</span>&quot; is currently published. Only one experiment can be published at a time.
            </p>
            <p className="text-body-sm text-on-surface-variant">
              Publishing this experiment will mark the existing one as <span className="font-semibold">finished</span>. Continue?
            </p>
            <div className="flex justify-end gap-3 mt-2">
              <button
                type="button"
                onClick={() => setPublishConflict(null)}
                disabled={publishing}
                className="text-sm font-semibold border border-border-subtle text-on-surface-variant px-5 py-2 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={confirmFinishAndPublish}
                disabled={publishing}
                className="text-sm font-semibold bg-primary text-on-primary px-5 py-2 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {publishing ? "Working..." : "Finish & Publish"}
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

      {previewModal && (
        <IdiomPreviewModal
          experimentId={experimentId}
          taskKey={previewModal.taskKey}
          idiomKey={previewModal.idiomKey}
          idiomLabel={previewModal.idiomLabel}
          datasetTitle={previewModal.datasetTitle}
          paramsSummary={previewModal.paramsSummary}
          version={imageVersion}
          onClose={() => setPreviewModal(null)}
        />
      )}

      {editingTask && (
        <EditTaskModal
          task={editingTask}
          onClose={() => setEditingTask(null)}
          onSave={saveEditedTask}
        />
      )}
    </div>
  );
}

export default function ExperimentOverviewPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface">
          <span className="text-on-surface-variant text-sm">Loading…</span>
        </div>
      }
    >
      <ExperimentOverviewContent />
    </Suspense>
  );
}
