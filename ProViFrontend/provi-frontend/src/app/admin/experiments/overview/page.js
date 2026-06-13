"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";

function getId(obj) {
  return obj._id || obj.id;
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

// Generic ground-truth summary — renders whatever the GT block currently
// holds, regardless of gt_shape (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §8, §11).
function GroundTruthSummary({ gt }) {
  if (!gt) {
    return <p className="text-xs text-on-surface-variant italic">Ground truth not yet configured.</p>;
  }

  const hasValue = gt.value !== null && gt.value !== undefined && gt.value !== "";
  const hasOptions = (gt.options || []).length > 0;
  const hasReference = !!(gt.reference && gt.reference.trim());

  if (hasValue) {
    return (
      <p className="text-xs text-on-surface">
        Value: <span className="font-semibold">{String(gt.value)}</span>
      </p>
    );
  }

  if (hasOptions) {
    return (
      <ul className="flex flex-wrap gap-2">
        {gt.options.map((opt, i) => (
          <li
            key={i}
            className={`text-xs px-2 py-1 rounded-full border ${
              opt.correct ? "bg-green-50 border-green-300 text-green-800" : "border-border-subtle text-on-surface-variant"
            }`}
          >
            {opt.label || opt.value}
            {opt.correct && <span className="material-symbols-outlined text-[10px] ml-1 align-middle">check</span>}
          </li>
        ))}
      </ul>
    );
  }

  if (hasReference) {
    return <p className="text-xs text-on-surface-variant line-clamp-2">{gt.reference}</p>;
  }

  return <p className="text-xs text-on-surface-variant italic">No rubric written yet.</p>;
}

function ExperimentOverviewContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [experiment, setExperiment] = useState(null);
  const [idiomMap, setIdiomMap] = useState({});
  const [groupedTasks, setGroupedTasks] = useState([]);
  const [taskInstancesByTask, setTaskInstancesByTask] = useState({});
  const [loading, setLoading] = useState(true);
  const [status, setStatus] = useState("draft");

  const [publishConflict, setPublishConflict] = useState(null);
  const [publishing, setPublishing] = useState(false);

  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = useCallback((message, isError = false) => {
    setToast({ visible: true, message, isError });
  }, []);
  const hideToast = useCallback(() => setToast((t) => ({ ...t, visible: false })), []);

  useEffect(() => {
    if (!experimentId) {
      router.replace("/admin/task-selection");
      return;
    }
    init();
  }, [experimentId]);

  async function init() {
    setLoading(true);
    try {
      const [expRes, tasksRes, idiomsRes] = await Promise.all([
        fetch(`/api/admin/experiments`),
        fetch(`/api/admin/tasks`),
        fetch(`/api/admin/idioms`),
      ]);
      if (!expRes.ok) throw new Error(`Experiments HTTP ${expRes.status}`);
      if (!tasksRes.ok) throw new Error(`Tasks HTTP ${tasksRes.status}`);
      if (!idiomsRes.ok) throw new Error(`Idioms HTTP ${idiomsRes.status}`);

      const [exps, tasks, idioms] = await Promise.all([
        expRes.json(),
        tasksRes.json(),
        idiomsRes.json(),
      ]);

      const exp = exps.find((e) => getId(e) === experimentId);
      if (!exp) throw new Error("Experiment not found.");
      setExperiment(exp);
      setStatus(exp.status || "draft");

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
    } catch (e) {
      showToast(`Could not load experiment: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
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
  const allReadyAndFormatted =
    taskInstancesList.length > 0 &&
    taskInstancesList.every((ti) => ti.generation_status === "ready" && !!ti.answer_format);

  async function publishExperiment() {
    if (publishing) return;
    if (!allReadyAndFormatted) {
      showToast(
        "All tasks must finish generating (status: Ready) and have an answer format chosen before publishing.",
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
      <ExperimentSetupHeader />

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
            <button
              onClick={() => router.back()}
              className="text-xs text-primary mt-1 inline-block hover:underline"
            >
              ← Go back to assign idioms
            </button>
          </div>
        ) : (
          <div className="flex flex-col gap-6">
            {groupedTasks.map(({ task, idiomIds }) => {
              const tid = getId(task);
              const ti = taskInstancesByTask[tid];
              const gtHref = `/admin/experiments/answer-format-groundtruth?experiment_id=${encodeURIComponent(experimentId)}`;
              return (
                <div
                  key={tid}
                  className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden"
                >
                  {/* Task header */}
                  <div className="border-l-4 border-primary p-5">
                    <div className="flex items-start gap-3">
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
                  </div>

                  <div className="divide-y divide-border-subtle">
                    {/* Selected Idioms */}
                    <div className="p-5">
                      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                        Selected Idioms
                        <span className="ml-2 font-normal normal-case tracking-normal text-primary">
                          ({idiomIds.length})
                        </span>
                      </p>
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
                                    {idiom?.label || iid}
                                  </p>
                                  {idiom && (
                                    <p className="text-[10px] text-on-surface-variant">
                                      {idiom.granularity} · {idiom.renderer_type}
                                    </p>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}
                    </div>

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
                          <span
                            className={`text-xs font-semibold px-2.5 py-1 rounded-full ${
                              ti?.ground_truth?.decisive
                                ? "bg-green-100 text-green-800"
                                : "bg-surface-container text-on-surface-variant"
                            }`}
                          >
                            {ti?.ground_truth?.decisive ? "Decisive" : "Reference"}
                          </span>
                        </div>
                        <Link
                          href={gtHref}
                          className="text-xs text-primary border border-primary/30 px-3 py-1.5 rounded hover:bg-blue-50 transition-colors flex-shrink-0"
                        >
                          Configure
                        </Link>
                      </div>
                    </div>

                    {/* Ground Truth */}
                    <div className="p-5">
                      <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-2">
                        Ground Truth
                      </p>
                      <div className="border border-border-subtle rounded-lg p-4 flex items-start justify-between gap-4">
                        <GroundTruthSummary gt={ti?.ground_truth} />
                        <Link
                          href={gtHref}
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
          <button
            onClick={() => router.back()}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </button>
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
                    All tasks need status Ready and an answer format chosen.
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
              "<span className="font-semibold">{publishConflict.name || publishConflict.experiment_name || "(unnamed)"}</span>" is currently published. Only one experiment can be published at a time.
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
