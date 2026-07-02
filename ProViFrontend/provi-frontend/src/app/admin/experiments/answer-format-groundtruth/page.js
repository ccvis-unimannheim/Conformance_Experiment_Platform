"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../../components/Admin/Toast";

function getId(obj) {
  return obj._id || obj.id;
}

const FALLBACK_ANSWER_FORMATS = [
  { key: "free-text", gt_shape: "reference", decisive_default: false },
];

// --- Ground-truth shape helpers (ADMIN_SPECIFY_GROUNDTRUTH_PLAN.md §8, §11) ---
//
// `gt_shape` (declared per answer format in ANSWER_FORMATS) selects the editor
// below: "scalar" -> ScalarEditor, "labelled-set" -> LabelledSetEditor,
// "mc" -> ChoiceSetEditor, "rank" -> RankEditor, "matrix" -> MatrixEditor,
// anything else (incl. "reference") -> ReferenceEditor.

function findFormat(key, answerFormats) {
  return (answerFormats || []).find((f) => f.key === key);
}

function shapeFor(formatKey, answerFormats) {
  return findFormat(formatKey, answerFormats)?.gt_shape || "reference";
}

function decisiveDefaultFor(formatKey, answerFormats) {
  return findFormat(formatKey, answerFormats)?.decisive_default ?? false;
}

function seedGroundTruth(formatKey, answerFormats, gtTier) {
  const shape = shapeFor(formatKey, answerFormats);
  // The grading rubric is task-level and read-only (served by
  // /tasks/{task_key}/rubric); it is never seeded into the per-instance GT.
  return {
    tier: gtTier || "MANUAL",
    format: formatKey,
    decisive: decisiveDefaultFor(formatKey, answerFormats),
    value: shape === "scalar" ? "" : null,
    options: [],
    reference: null,
    artefact_path: null,
  };
}

function emptyOption() {
  return { label: "", value: "", correct: false };
}

// --- Generic GT editors, one per gt_shape ---

function ScalarEditor({ gt, onChange, placeholder = "e.g. 96% / 42 / 0.42" }) {
  return (
    <div className="flex flex-col gap-1 max-w-xs">
      <label className="text-xs font-semibold text-on-surface">Ground-truth value</label>
      <input
        type="text"
        value={gt.value ?? ""}
        onChange={(e) => onChange({ ...gt, value: e.target.value })}
        placeholder={placeholder}
        className="w-full text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
      />
    </div>
  );
}

function OptionRows({ options, onChange, renderExtra, addLabel, emptyHint }) {
  function updateRow(i, field, val) {
    onChange(options.map((o, idx) => (idx === i ? { ...o, [field]: val } : o)));
  }
  function addRow() {
    onChange([...options, emptyOption()]);
  }
  function removeRow(i) {
    onChange(options.filter((_, idx) => idx !== i));
  }

  return (
    <div className="flex flex-col gap-2">
      {options.length === 0 && (
        <p className="text-xs text-on-surface-variant italic">{emptyHint}</p>
      )}
      {options.map((opt, i) => (
        <div key={i} className="flex items-center gap-2">
          {renderExtra && renderExtra(opt, i, updateRow)}
          <input
            type="text"
            placeholder="Label"
            value={opt.label}
            onChange={(e) => updateRow(i, "label", e.target.value)}
            className="flex-1 text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <input
            type="text"
            placeholder="Value"
            value={opt.value}
            onChange={(e) => updateRow(i, "value", e.target.value)}
            className="w-28 text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <button onClick={() => removeRow(i)} className="text-on-surface-variant hover:text-error">
            <span className="material-symbols-outlined text-sm">delete</span>
          </button>
        </div>
      ))}
      <button onClick={addRow} className="self-start text-xs font-semibold text-primary hover:underline flex items-center gap-1">
        <span className="material-symbols-outlined text-sm">add</span> {addLabel}
      </button>
    </div>
  );
}

function LabelledSetEditor({ gt, onChange }) {
  return (
    <div className="flex flex-col gap-2 max-w-md">
      <label className="text-xs font-semibold text-on-surface">Ground-truth value per row</label>
      <OptionRows
        options={gt.options || []}
        onChange={(options) => onChange({ ...gt, options })}
        addLabel="Add row"
        emptyHint="No rows yet — add one per labelled item, with its ground-truth value."
      />
    </div>
  );
}

function ChoiceSetEditor({ gt, format, groupName, onChange }) {
  const multi = format === "mc-multi";
  const options = gt.options || [];

  function updateText(i, text) {
    const next = options.map((o, idx) => (idx === i ? { ...o, label: text, value: text } : o));
    onChange({ ...gt, options: next });
  }

  function updateCorrect(i, val) {
    let next = options.map((o, idx) => (idx === i ? { ...o, correct: val } : o));
    if (!multi && val) {
      next = next.map((o, idx) => ({ ...o, correct: idx === i }));
    }
    onChange({ ...gt, options: next });
  }

  function addRow() {
    onChange({ ...gt, options: [...options, emptyOption()] });
  }

  function removeRow(i) {
    onChange({ ...gt, options: options.filter((_, idx) => idx !== i) });
  }

  return (
    <div className="flex flex-col gap-2 max-w-md">
      <label className="text-xs font-semibold text-on-surface">
        Options ({multi ? "check all correct options" : "select the one correct option"})
      </label>
      {options.length === 0 && (
        <p className="text-xs text-on-surface-variant italic">No options yet — add the correct answer plus distractors.</p>
      )}
      {options.map((opt, i) => (
        <div key={i} className="flex items-center gap-2">
          <input
            type={multi ? "checkbox" : "radio"}
            name={`gt-correct-${groupName}`}
            checked={!!opt.correct}
            onChange={(e) => updateCorrect(i, e.target.checked)}
            className="flex-shrink-0"
          />
          <input
            type="text"
            placeholder="Option text"
            value={opt.label}
            onChange={(e) => updateText(i, e.target.value)}
            className="flex-1 text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <button onClick={() => removeRow(i)} className="text-on-surface-variant hover:text-error">
            <span className="material-symbols-outlined text-sm">delete</span>
          </button>
        </div>
      ))}
      <button onClick={addRow} className="self-start text-xs font-semibold text-primary hover:underline flex items-center gap-1">
        <span className="material-symbols-outlined text-sm">add</span> Add option
      </button>
    </div>
  );
}

function RankEditor({ gt, onChange }) {
  const options = gt.options || [];

  function move(i, dir) {
    const j = i + dir;
    if (j < 0 || j >= options.length) return;
    const next = [...options];
    [next[i], next[j]] = [next[j], next[i]];
    onChange({ ...gt, options: next });
  }
  function addRow() {
    onChange({ ...gt, options: [...options, emptyOption()] });
  }
  function removeRow(i) {
    onChange({ ...gt, options: options.filter((_, idx) => idx !== i) });
  }

  return (
    <div className="flex flex-col gap-2 max-w-md">
      <label className="text-xs font-semibold text-on-surface">Correct ordering (top = rank 1)</label>
      {options.length === 0 && (
        <p className="text-xs text-on-surface-variant italic">No items yet — add items in the correct rank order.</p>
      )}
      {options.map((opt, i) => (
        <div key={i} className="flex items-center gap-2">
          <span className="text-xs font-semibold text-on-surface-variant w-5">{i + 1}.</span>
          <input
            type="text"
            placeholder="Item name"
            value={opt.label}
            onChange={(e) => {
              const v = e.target.value;
              onChange({ ...gt, options: options.map((o, idx) => idx === i ? { ...o, label: v, value: v } : o) });
            }}
            className="flex-1 text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
          />
          <button onClick={() => move(i, -1)} disabled={i === 0} className="text-on-surface-variant hover:text-primary disabled:opacity-30">
            <span className="material-symbols-outlined text-sm">arrow_upward</span>
          </button>
          <button onClick={() => move(i, 1)} disabled={i === options.length - 1} className="text-on-surface-variant hover:text-primary disabled:opacity-30">
            <span className="material-symbols-outlined text-sm">arrow_downward</span>
          </button>
          <button onClick={() => removeRow(i)} className="text-on-surface-variant hover:text-error">
            <span className="material-symbols-outlined text-sm">delete</span>
          </button>
        </div>
      ))}
      <button onClick={addRow} className="self-start text-xs font-semibold text-primary hover:underline flex items-center gap-1">
        <span className="material-symbols-outlined text-sm">add</span> Add item
      </button>
    </div>
  );
}

// Parse pair-shaped options ("a__b") into a symmetric axis + pair→index lookup,
// mirroring the participant MatrixGrid (AnswerWidgets.js parsePairs). Returns null
// when options are not pair-shaped, so the editor can fall back to a flat list.
function parseMatrixPairs(options) {
  const axisOrder = [];
  const seen = new Set();
  const idxByPair = {}; // sorted "a b" -> option index
  for (let i = 0; i < options.length; i++) {
    const parts = String(options[i].value ?? "").split("__");
    if (parts.length !== 2) return null;
    parts.forEach((t) => { if (!seen.has(t)) { seen.add(t); axisOrder.push(t); } });
    idxByPair[[...parts].sort().join(" ")] = i;
  }
  return { axisOrder, idxByPair };
}

function MatrixEditor({ gt, onChange }) {
  const options = gt.options || [];

  function updateRow(i, field, val) {
    onChange({ ...gt, options: options.map((o, idx) => (idx === i ? { ...o, [field]: val } : o)) });
  }

  const parsed = options.length ? parseMatrixPairs(options) : null;

  // Fallback: not pair-shaped → flat per-cell list (legacy behaviour).
  if (!parsed) {
    return (
      <div className="flex flex-col gap-2 max-w-md">
        <label className="text-xs font-semibold text-on-surface">Selected cells</label>
        <p className="text-xs text-on-surface-variant">
          Each row is one grid cell; check it if that cell belongs in the correct selection.
        </p>
        <OptionRows
          options={options}
          onChange={(opts) => onChange({ ...gt, options: opts })}
          addLabel="Add cell"
          emptyHint="No cells yet — add the cells that make up the correct selection."
          renderExtra={(opt, i, _updateRow) => (
            <input
              type="checkbox"
              checked={!!opt.correct}
              onChange={(e) => updateRow(i, "correct", e.target.checked)}
              className="flex-shrink-0"
            />
          )}
        />
      </div>
    );
  }

  const { axisOrder, idxByPair } = parsed;
  const idxForPair = (a, b) => idxByPair[[a, b].sort().join(" ")];

  return (
    <div className="flex flex-col gap-2">
      <label className="text-xs font-semibold text-on-surface">Co-occurrence matrix</label>
      <p className="text-xs text-on-surface-variant">
        Tick each pair of violations that co-occur. Both axes share the same violation set;
        the matrix is symmetric, so only the upper triangle is editable (the diagonal is blank).
      </p>
      <div className="overflow-x-auto border border-border-subtle rounded-lg">
        <table className="border-collapse text-xs">
          <thead>
            <tr>
              <th className="p-1" />
              {axisOrder.map((c) => (
                <th key={c} title={c}
                    className="px-2 py-1 text-on-surface-variant font-semibold whitespace-nowrap align-bottom">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {axisOrder.map((r) => (
              <tr key={r} className="border-t border-border-subtle">
                <td title={r} className="pr-2 py-1 font-semibold text-on-surface whitespace-nowrap">
                  {r}
                </td>
                {axisOrder.map((c) => {
                  const idx = r === c ? undefined : idxForPair(r, c);
                  return (
                    <td key={c} className="text-center px-2 py-1">
                      {idx === undefined ? (
                        <span className="text-border-subtle">·</span>
                      ) : (
                        <input
                          type="checkbox"
                          checked={!!options[idx].correct}
                          onChange={() =>
                            onChange({
                              ...gt,
                              options: options.map((o, k) =>
                                k === idx ? { ...o, correct: !o.correct } : o),
                            })
                          }
                        />
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ReferenceEditor({ gt, rubricInfo }) {
  return (
    <div className="flex flex-col gap-3">
      {gt.reference && (
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">
            Reference answer
          </p>
          <p className="text-sm text-on-surface whitespace-pre-wrap bg-surface-container-low rounded-lg px-3 py-2">
            {gt.reference}
          </p>
        </div>
      )}
      <div>
        <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-1">
          Supporting artefact
        </p>
        {gt.artefact_path ? (
          <p className="text-xs text-on-surface-variant font-mono bg-surface-container-low rounded px-3 py-2">
            {gt.artefact_path}
          </p>
        ) : (
          <p className="text-xs text-on-surface-variant italic bg-surface-container-low rounded px-3 py-2">
            No supporting data computed for this task yet — it will appear here once this task&apos;s
            ground-truth computation is authored.
          </p>
        )}
      </div>
      <div className="flex flex-col gap-1">
        <label className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
          Grading rubric
        </label>
        {rubricInfo?.rubric ? (
          <p className="text-sm text-on-surface whitespace-pre-wrap bg-surface-container-low rounded-lg px-3 py-2">
            {rubricInfo.rubric}
          </p>
        ) : (
          <p className="text-xs text-on-surface-variant italic bg-surface-container-low rounded-lg px-3 py-2">
            No rubric authored for this task yet — add a RUBRIC constant to this task to display one here.
          </p>
        )}
        <p className="text-[11px] text-on-surface-variant italic">
          The rubric is defined per task and shared across all experiments; it is read-only here.
        </p>
      </div>
    </div>
  );
}

function GroundTruthEditor({ gt, format, answerFormats, rubricInfo, groupName, onChange }) {
  const shape = shapeFor(format, answerFormats);
  switch (shape) {
    case "scalar":
      return <ScalarEditor gt={gt} onChange={onChange} placeholder={format === "count" ? "e.g. 42" : "e.g. 96%"} />;
    case "labelled-set":
      return <LabelledSetEditor gt={gt} onChange={onChange} />;
    case "mc":
      return <ChoiceSetEditor gt={gt} format={format} groupName={groupName} onChange={onChange} />;
    case "rank":
      return <RankEditor gt={gt} onChange={onChange} />;
    case "matrix":
      return <MatrixEditor gt={gt} onChange={onChange} />;
    default:
      return <ReferenceEditor gt={gt} rubricInfo={rubricInfo} />;
  }
}

function FormatSelector({ formats, value, onChange }) {
  if (formats.length <= 1) {
    const fmt = formats[0];
    return (
      <span className="inline-flex items-center gap-1 text-xs font-semibold bg-surface-container text-on-surface-variant px-2.5 py-1 rounded-full">
        <span className="material-symbols-outlined text-sm">lock</span>
        {fmt?.key || "free-text"}
      </span>
    );
  }
  return (
    <select
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      className="text-sm border border-border-subtle rounded-lg px-3 py-2 bg-white focus:outline-none focus:ring-2 focus:ring-primary/30"
    >
      <option value="" disabled>
        Select format…
      </option>
      {formats.map((f) => (
        <option key={f.key} value={f.key}>
          {f.key}
        </option>
      ))}
    </select>
  );
}

function pickGroundTruth(ti, formatKey, taskFormats, rubricInfo) {
  const precomputed = ti.ground_truth_by_format?.[formatKey];
  if (precomputed) return precomputed;
  if (ti.ground_truth && ti.ground_truth.format === formatKey) return ti.ground_truth;
  return seedGroundTruth(formatKey, taskFormats, rubricInfo.gt_tier);
}

function seedInstances(instances, formatsByTask, rubricsByTask) {
  return instances.map((ti) => {
    const taskFormats = formatsByTask[ti.task_id] || FALLBACK_ANSWER_FORMATS;
    const rubricInfo = rubricsByTask[ti.task_id] || { rubric: null, gt_tier: "MANUAL" };

    let answerFormat = ti.answer_format;
    if (!answerFormat && taskFormats.length === 1) {
      answerFormat = taskFormats[0].key;
    }
    // If GT was computed during generation, use its format as the initial selection
    if (!answerFormat && ti.ground_truth?.format) {
      answerFormat = ti.ground_truth.format;
    }

    const groundTruth = answerFormat
      ? pickGroundTruth(ti, answerFormat, taskFormats, rubricInfo)
      : (ti.ground_truth ?? null);

    return { ...ti, answer_format: answerFormat ?? null, ground_truth: groundTruth };
  });
}

function GroundTruthContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [taskInstances, setTaskInstances] = useState([]);
  const [tasksById, setTasksById] = useState({});
  const [idiomsById, setIdiomsById] = useState({});
  const [answerFormatsByTask, setAnswerFormatsByTask] = useState({});
  const [rubricsByTask, setRubricsByTask] = useState({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

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
      const [expRes, tasksRes, idiomsRes] = await Promise.all([
        fetch(`/api/admin/experiments/${experimentId}`),
        fetch(`/api/admin/tasks`),
        fetch(`/api/admin/idioms`),
      ]);
      if (!expRes.ok) throw new Error(`Experiment HTTP ${expRes.status}`);
      if (!tasksRes.ok) throw new Error(`Tasks HTTP ${tasksRes.status}`);
      if (!idiomsRes.ok) throw new Error(`Idioms HTTP ${idiomsRes.status}`);

      const [exp, tasks, idioms] = await Promise.all([expRes.json(), tasksRes.json(), idiomsRes.json()]);

      const tMap = {};
      tasks.forEach((t) => { tMap[getId(t)] = t; });
      setTasksById(tMap);

      const iMap = {};
      idioms.forEach((i) => { iMap[getId(i)] = i; });
      setIdiomsById(iMap);

      const instances = exp.task_instances || [];
      const { formats, rubrics } = await loadFormatsAndRubrics(instances, tMap);
      setTaskInstances(seedInstances(instances, formats, rubrics));
    } catch (e) {
      showToast(`Could not load experiment: ${e.message}`, true);
    } finally {
      setLoading(false);
    }
  }

  async function loadFormatsAndRubrics(instances, tMap) {
    const formats = {};
    const rubrics = {};
    await Promise.all(
      instances.map(async (ti) => {
        const task = tMap[ti.task_id];
        const taskKey = task?.task_key;
        let answerFormats = FALLBACK_ANSWER_FORMATS;
        let rubricInfo = { rubric: null, gt_tier: "MANUAL" };
        if (taskKey) {
          try {
            const res = await fetch(`/api/admin/tasks/${encodeURIComponent(taskKey)}/answer-formats`);
            if (res.ok) {
              const data = await res.json();
              if (Array.isArray(data.answer_formats) && data.answer_formats.length > 0) {
                answerFormats = data.answer_formats;
              }
            }
          } catch {
            // fall through with the free-text fallback
          }
          if (!answerFormats.find((f) => f.key === "free-text")) {
            answerFormats = [...answerFormats, { key: "free-text", gt_shape: "reference", decisive_default: false }];
          }
          try {
            const res = await fetch(`/api/admin/tasks/${encodeURIComponent(taskKey)}/rubric`);
            if (res.ok) {
              const data = await res.json();
              rubricInfo = { rubric: data.rubric ?? null, gt_tier: data.gt_tier || "MANUAL" };
            }
          } catch {
            // fall through with no default rubric
          }
        }
        formats[ti.task_id] = answerFormats;
        rubrics[ti.task_id] = rubricInfo;
      })
    );
    setAnswerFormatsByTask(formats);
    setRubricsByTask(rubrics);
    return { formats, rubrics };
  }

  function handleFormatChange(taskId, formatKey) {
    const taskFormats = answerFormatsByTask[taskId] || FALLBACK_ANSWER_FORMATS;
    const rubricInfo = rubricsByTask[taskId] || { rubric: null, gt_tier: "MANUAL" };
    setTaskInstances((prev) =>
      prev.map((ti) =>
        ti.task_id === taskId
          ? {
              ...ti,
              answer_format: formatKey,
              ground_truth: pickGroundTruth(ti, formatKey, taskFormats, rubricInfo),
            }
          : ti
      )
    );
  }

  function handleGtChange(taskId, gt) {
    setTaskInstances((prev) => prev.map((ti) => (ti.task_id === taskId ? { ...ti, ground_truth: gt } : ti)));
  }

  function handleDecisiveChange(taskId, decisive) {
    setTaskInstances((prev) =>
      prev.map((ti) => (ti.task_id === taskId ? { ...ti, ground_truth: { ...(ti.ground_truth || {}), decisive } } : ti))
    );
  }

  async function persist() {
    const res = await fetch(`/api/admin/experiments/${experimentId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_instances: taskInstances }),
    });
    if (!res.ok) throw new Error(await res.text());
  }

  async function handleSave() {
    setSaving(true);
    try {
      await persist();
      showToast("Ground truth saved.");
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, true);
    } finally {
      setSaving(false);
    }
  }

  const allFormatsChosen = taskInstances.length > 0 && taskInstances.every((ti) => !!ti.answer_format);

  async function handleNext() {
    if (!allFormatsChosen) {
      showToast("Please choose an answer format for every task.", true);
      return;
    }
    setSaving(true);
    try {
      await persist();
      router.push(`/admin/experiments/overview?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      showToast(`Failed to save: ${e.message}`, true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[1140px] mx-auto w-full px-8 py-10 flex flex-col gap-8">
        {/* Page heading */}
        <div className="flex flex-col gap-1">
          <h1 className="font-h1 text-h1 text-primary mb-2">Answer Format &amp; Ground Truth</h1>
          <p className="font-body-lg text-body-lg text-secondary max-w-2xl">
            Pick the answer format each task will use, then review and edit its ground truth. Unauthored
            tasks fall back to a generic free-text format with an editable rubric.
          </p>
        </div>

        {/* Task cards */}
        <div className="flex flex-col gap-6">
          {loading ? (
            <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
              <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                hourglass_empty
              </span>
              Loading…
            </div>
          ) : taskInstances.length === 0 ? (
            <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
              <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                inbox
              </span>
              No tasks found for this experiment.
            </div>
          ) : (
            taskInstances.map((ti) => {
              const task = tasksById[ti.task_id] || {};
              const formats = answerFormatsByTask[ti.task_id] || FALLBACK_ANSWER_FORMATS;
              const rubricInfo = rubricsByTask[ti.task_id];
              return (
                <div
                  key={ti.task_id}
                  className="bg-white rounded-lg border border-border-subtle shadow-sm overflow-hidden"
                >
                  <div className="border-l-4 border-primary p-5 flex items-start gap-3">
                    <span className="text-xs font-bold bg-blue-100 text-primary px-2 py-0.5 rounded flex-shrink-0 mt-0.5">
                      {task.task_key || ti.task_id}
                    </span>
                    <div>
                      <p className="text-sm font-semibold text-on-surface leading-snug">
                        {task.label || "(unknown task)"}
                      </p>
                      {ti.idiom_ids?.length > 0 && (
                        <p className="text-xs text-on-surface-variant mt-1">
                          {ti.idiom_ids.map((iid) => idiomsById[iid]?.label || iid).join(", ")}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="p-5 pt-3 border-t border-border-subtle flex flex-col gap-4">
                    <div className="flex items-center justify-between gap-4 flex-wrap">
                      <div className="flex items-center gap-2">
                        <p className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                          Answer format
                        </p>
                        <FormatSelector
                          formats={formats}
                          value={ti.answer_format}
                          onChange={(key) => handleFormatChange(ti.task_id, key)}
                        />
                      </div>
                      <label className="flex items-center gap-2 text-xs font-semibold text-on-surface cursor-pointer select-none">
                        <input
                          type="checkbox"
                          checked={!!ti.ground_truth?.decisive}
                          onChange={(e) => handleDecisiveChange(ti.task_id, e.target.checked)}
                        />
                        Closed-form answer
                      </label>
                    </div>

                    {ti.ground_truth ? (
                      <GroundTruthEditor
                        gt={ti.ground_truth}
                        format={ti.answer_format}
                        answerFormats={formats}
                        rubricInfo={rubricInfo}
                        groupName={ti.task_id}
                        onChange={(gt) => handleGtChange(ti.task_id, gt)}
                      />
                    ) : (
                      <p className="text-xs text-on-surface-variant italic">
                        Select an answer format to configure ground truth.
                      </p>
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
            href={`/admin/experiments/specify${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <div className="flex items-center gap-3">
            <button
              onClick={handleSave}
              disabled={saving || loading}
              className="flex items-center gap-2 text-sm font-semibold border border-border-subtle text-on-surface-variant px-6 py-2.5 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              <span className="material-symbols-outlined text-sm">save</span>
              Save
            </button>
            <button
              onClick={handleNext}
              disabled={!allFormatsChosen || saving || loading}
              className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
              <span className="material-symbols-outlined text-sm">chevron_right</span>
            </button>
          </div>
        </div>
      </div>

      <Toast
        message={toast.message}
        isError={toast.isError}
        visible={toast.visible}
        onHide={hideToast}
      />
    </div>
  );
}

export default function AnswerFormatGroundTruthPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center bg-surface">
          <span className="text-on-surface-variant text-sm">Loading…</span>
        </div>
      }
    >
      <GroundTruthContent />
    </Suspense>
  );
}
