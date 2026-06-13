"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../components/Admin/Toast";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1234";

const ALL_IDIOMS = [
  { idiom_key: "bar_chart",            label: "Bar Chart",                             granularity: "log",   renderer_type: "echarts", active: true },
  { idiom_key: "tile_metric",          label: "Tile Metric",                           granularity: "log",   renderer_type: "html",    active: true },
  { idiom_key: "scatterplot",          label: "Scatterplot (Dotted Chart)",            granularity: "trace", renderer_type: "echarts", active: true },
  { idiom_key: "table",                label: "Table",                                 granularity: "log",   renderer_type: "html",    active: true },
  { idiom_key: "heatmap",              label: "Heatmap",                               granularity: "log",   renderer_type: "echarts", active: true },
  { idiom_key: "boxplot",              label: "Box and Whisker Plot",                  granularity: "log",   renderer_type: "echarts", active: true },
  { idiom_key: "flow_chart_basic",     label: "Flow Chart (Chevron Diagram)",          granularity: "trace", renderer_type: "svg",     active: true },
  { idiom_key: "flow_chart_elaborate", label: "Flow Chart+ (BPMN Diagram)",            granularity: "trace", renderer_type: "bpmn",    active: true },
  { idiom_key: "pie_chart",            label: "Pie Chart",                             granularity: "log",   renderer_type: "echarts", active: true },
  { idiom_key: "tree",                  label: "Decision Tree",                         granularity: "log",   renderer_type: "d3",      active: true },
  { idiom_key: "flow_chart_table",     label: "Flow Chart & Table",                    granularity: "trace", renderer_type: "html",    active: true },
  { idiom_key: "table_bar_chart",      label: "Table & Bar Chart",                     granularity: "log",   renderer_type: "html",    active: true },
];

const TASK_IDIOM_KEYS = {
  "T-01": ["bar_chart", "tile_metric", "scatterplot", "table", "heatmap", "boxplot"],
  "T-02": ["flow_chart_basic", "table", "flow_chart_table", "flow_chart_elaborate"],
  "T-03": ["bar_chart", "heatmap", "pie_chart", "flow_chart_table", "table", "table_bar_chart"],
  "T-04": ["tile_metric", "tree", "table"],
  "T-05": ["bar_chart", "pie_chart", "scatterplot", "heatmap", "table"],
  "T-06": ["table", "tree"],
};

function getId(obj) {
  return obj._id || obj.id;
}

function IdiomSelectionContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [selectedTasks, setSelectedTasks] = useState([]);
  const [allIdioms, setAllIdioms] = useState([]);
  // taskIdiomMap: { [taskId]: string[] }
  const [taskIdiomMap, setTaskIdiomMap] = useState({});
  const [isSeeding, setIsSeeding] = useState(false);

  // Create idiom modal
  const [idiomModalOpen, setIdiomModalOpen] = useState(false);
  const [newIdiomKey, setNewIdiomKey] = useState("");
  const [newIdiomLabel, setNewIdiomLabel] = useState("");
  const [newIdiomGranularity, setNewIdiomGranularity] = useState("log");
  const [newIdiomRenderer, setNewIdiomRenderer] = useState("echarts");
  const [idiomModalError, setIdiomModalError] = useState("");

  // Toast
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
    // Load draft experiment to get task IDs
    let taskIds = [];
    try {
      const res = await fetch(`${BASE_URL}/admin/experiments`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const exps = await res.json();
      const draft = exps.find((e) => getId(e) === experimentId);
      if (!draft) throw new Error("Draft experiment not found.");
      taskIds = draft.task_configs.map((tc) => tc.task_id);
    } catch (e) {
      showToast(`Could not load draft experiment: ${e.message}`, true);
      return;
    }

    // Load full task objects
    try {
      const res = await fetch(`${BASE_URL}/admin/tasks`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const allTasks = await res.json();
      const tasks = allTasks.filter((t) => taskIds.includes(getId(t)));
      if (tasks.length === 0) {
        router.replace("/admin/task-selection");
        return;
      }
      setSelectedTasks(tasks);
      const map = {};
      tasks.forEach((t) => { map[getId(t)] = []; });
      setTaskIdiomMap(map);
    } catch (e) {
      showToast(`Could not load tasks: ${e.message}`, true);
      return;
    }

    await fetchIdioms();
  }

  async function fetchIdioms() {
    try {
      const res = await fetch(`${BASE_URL}/admin/idioms`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setAllIdioms(await res.json());
    } catch (e) {
      showToast(`Could not load idioms: ${e.message}`, true);
    }
  }

  function getIdiomsForTask(task) {
    const allowed = TASK_IDIOM_KEYS[task.task_key];
    if (!allowed) return allIdioms;
    return allIdioms.filter((i) => allowed.includes(i.idiom_key));
  }

  function toggleIdiom(taskId, idiomId) {
    setTaskIdiomMap((prev) => {
      const arr = prev[taskId] || [];
      const newArr = arr.includes(idiomId)
        ? arr.filter((id) => id !== idiomId)
        : [...arr, idiomId];
      return { ...prev, [taskId]: newArr };
    });
  }

  const assignmentTotal = Object.values(taskIdiomMap).reduce(
    (sum, arr) => sum + arr.length,
    0
  );

  async function seedIdioms() {
    setIsSeeding(true);
    let existingKeys = new Set();
    try {
      const res = await fetch(`${BASE_URL}/admin/idioms`);
      if (res.ok) {
        const existing = await res.json();
        existing.forEach((i) => existingKeys.add(i.idiom_key));
      }
    } catch {}

    let created = 0, skipped = 0;
    for (const idiom of ALL_IDIOMS) {
      if (existingKeys.has(idiom.idiom_key)) { skipped++; continue; }
      try {
        const res = await fetch(`${BASE_URL}/admin/idioms`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ _id: crypto.randomUUID(), ...idiom }),
        });
        if (res.ok) created++;
      } catch {}
    }

    showToast(
      skipped === ALL_IDIOMS.length
        ? "All idioms already exist."
        : `Seeded ${created} idiom(s). ${skipped} already existed.`
    );
    await fetchIdioms();
    setIsSeeding(false);
  }

  async function submitCreateIdiom() {
    if (!newIdiomKey.trim() || !newIdiomLabel.trim()) {
      setIdiomModalError("Idiom Key and Label are required.");
      return;
    }
    setIdiomModalError("");
    const payload = {
      _id: crypto.randomUUID(),
      idiom_key: newIdiomKey.trim(),
      label: newIdiomLabel.trim(),
      granularity: newIdiomGranularity,
      renderer_type: newIdiomRenderer,
      active: true,
    };
    try {
      const res = await fetch(`${BASE_URL}/admin/idioms`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error(await res.text());
      setIdiomModalOpen(false);
      setNewIdiomKey("");
      setNewIdiomLabel("");
      showToast("Idiom created successfully!");
      await fetchIdioms();
    } catch (e) {
      setIdiomModalError(`Error: ${e.message}`);
    }
  }

  async function handleNext() {
    const unassigned = selectedTasks.filter(
      (t) => (taskIdiomMap[getId(t)] || []).length === 0
    );
    if (unassigned.length > 0) {
      showToast(
        `Please assign at least one idiom to: ${unassigned.map((t) => t.task_key).join(", ")}`,
        true
      );
      return;
    }

    const taskConfigs = [];
    for (const task of selectedTasks) {
      const tid = getId(task);
      for (const idiomId of taskIdiomMap[tid] || []) {
        taskConfigs.push({ task_id: tid, idiom_id: idiomId, dataset_id: "", question_ids: [] });
      }
    }

    try {
      const res = await fetch(`${BASE_URL}/admin/experiments/${experimentId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task_configs: taskConfigs }),
      });
      if (!res.ok) throw new Error(await res.text());
      router.push(`/admin/experiments/overview?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      showToast(`Failed to save experiment: ${e.message}`, true);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        {/* Page heading */}
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Allocate Idioms to Tasks</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Choose which visualization idioms should be shown for each selected task. Each task must
            have at least one idiom assigned before saving.
          </p>
        </div>

        {/* Toolbar */}
        <div className="flex justify-between items-center">
          <h2 className="text-base font-semibold text-on-surface">
            Task Cards
            {selectedTasks.length > 0 && (
              <span className="ml-2 text-xs text-on-surface-variant font-normal">
                ({selectedTasks.length} task{selectedTasks.length !== 1 ? "s" : ""})
              </span>
            )}
          </h2>
          <button
            onClick={seedIdioms}
            disabled={isSeeding}
            className="flex items-center gap-1.5 text-xs border border-border-subtle text-on-surface-variant px-3 py-1.5 rounded hover:bg-surface-container transition-colors disabled:opacity-50"
          >
            <span className="material-symbols-outlined text-sm">
              {isSeeding ? "hourglass_empty" : "download"}
            </span>
            {isSeeding ? "Seeding…" : "Seed Idioms"}
          </button>
        </div>

        {/* Task cards with idiom allocation */}
        <div className="flex flex-col gap-6">
          {selectedTasks.length === 0 ? (
            <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
              <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                hourglass_empty
              </span>
              Loading…
            </div>
          ) : (
            selectedTasks.map((task) => {
              const tid = getId(task);
              const taskIdioms = getIdiomsForTask(task);
              const selectedForTask = taskIdiomMap[tid] || [];
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

                  {/* Idiom options */}
                  <div className="p-5 pt-3 border-t border-border-subtle">
                    <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">
                      Select Idioms{" "}
                      <span
                        className={`ml-2 font-normal normal-case tracking-normal ${
                          selectedForTask.length > 0 ? "text-primary" : "text-on-surface-variant"
                        }`}
                      >
                        ({selectedForTask.length} selected)
                      </span>
                    </p>
                    {allIdioms.length === 0 ? (
                      <p className="text-xs text-on-surface-variant italic">
                        No idioms in database yet. Click <strong>Seed Idioms</strong> above.
                      </p>
                    ) : taskIdioms.length === 0 ? (
                      <p className="text-xs text-on-surface-variant italic">
                        No matching idioms in database. Click <strong>Seed Idioms</strong> above.
                      </p>
                    ) : (
                      <div className="grid grid-cols-2 gap-2">
                        {taskIdioms.map((idiom) => {
                          const iid = getId(idiom);
                          const selected = selectedForTask.includes(iid);
                          return (
                            <div
                              key={iid}
                              onClick={() => toggleIdiom(tid, iid)}
                              className={`cursor-pointer flex items-center gap-2 p-3 rounded-lg border transition-all select-none
                                ${selected
                                  ? "bg-blue-50 border-primary/30"
                                  : "bg-surface-container-low border-transparent hover:border-outline-variant"
                                }`}
                            >
                              <span
                                className={`material-symbols-outlined text-base flex-shrink-0 transition-colors
                                  ${selected ? "text-primary icon-filled" : "text-outline-variant"}`}
                              >
                                {selected ? "check_circle" : "radio_button_unchecked"}
                              </span>
                              <div className="min-w-0">
                                <p className="text-xs font-semibold text-on-surface truncate">
                                  {idiom.label}
                                </p>
                                <p className="text-[10px] text-on-surface-variant">
                                  {idiom.granularity} · {idiom.renderer_type}
                                </p>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </main>

      {/* Footer action bar */}
      <div className="border-t border-border-subtle bg-white sticky bottom-0">
        <div className="max-w-[1140px] mx-auto px-8 py-4 flex justify-between items-center">
          <Link
            href={`/admin/task-selection${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <div className="flex items-center gap-4">
            {assignmentTotal > 0 && (
              <span className="text-xs text-on-surface-variant">
                {assignmentTotal} idiom assignment{assignmentTotal !== 1 ? "s" : ""}
              </span>
            )}
            <button
              onClick={handleNext}
              className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95"
            >
              Next
              <span className="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </div>
        </div>
      </div>

      {/* Create Idiom Modal */}
      {idiomModalOpen && (
        <div
          className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4"
          onClick={(e) => { if (e.target === e.currentTarget) setIdiomModalOpen(false); }}
        >
          <div className="bg-white rounded-xl p-6 w-full max-w-[480px] shadow-xl flex flex-col gap-4">
            <div className="flex justify-between items-center">
              <h3 className="text-lg font-bold text-on-surface">Create New Idiom</h3>
              <button onClick={() => setIdiomModalOpen(false)} className="text-on-surface-variant hover:text-on-surface">
                <span className="material-symbols-outlined">close</span>
              </button>
            </div>
            <div className="flex flex-col gap-3">
              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                  Idiom Key *
                </label>
                <input
                  type="text"
                  value={newIdiomKey}
                  onChange={(e) => setNewIdiomKey(e.target.value)}
                  placeholder="e.g. bar_chart"
                  className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>
              <div>
                <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                  Display Label *
                </label>
                <input
                  type="text"
                  value={newIdiomLabel}
                  onChange={(e) => setNewIdiomLabel(e.target.value)}
                  placeholder="e.g. Bar Chart"
                  className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                    Granularity
                  </label>
                  <select
                    value={newIdiomGranularity}
                    onChange={(e) => setNewIdiomGranularity(e.target.value)}
                    className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
                  >
                    <option value="log">Log</option>
                    <option value="trace">Trace</option>
                    <option value="event">Event</option>
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant block mb-1">
                    Renderer
                  </label>
                  <select
                    value={newIdiomRenderer}
                    onChange={(e) => setNewIdiomRenderer(e.target.value)}
                    className="w-full border border-border-subtle rounded px-3 py-2 text-sm focus:outline-none focus:border-primary"
                  >
                    <option value="echarts">ECharts</option>
                    <option value="html">HTML / Table</option>
                    <option value="svg">SVG</option>
                    <option value="bpmn">BPMN</option>
                    <option value="d3">D3</option>
                  </select>
                </div>
              </div>
            </div>
            {idiomModalError && (
              <div className="text-error text-xs bg-error-container px-3 py-2 rounded">
                {idiomModalError}
              </div>
            )}
            <div className="flex gap-2 justify-end pt-1">
              <button
                onClick={() => setIdiomModalOpen(false)}
                className="text-sm text-on-surface-variant border border-border-subtle px-4 py-2 rounded hover:bg-surface-container transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={submitCreateIdiom}
                className="text-sm bg-primary text-white px-5 py-2 rounded font-semibold hover:bg-primary-container transition-colors"
              >
                Create Idiom
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

export default function IdiomSelectionPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface">
          <span className="text-on-surface-variant text-sm">Loading…</span>
        </div>
      }
    >
      <IdiomSelectionContent />
    </Suspense>
  );
}
