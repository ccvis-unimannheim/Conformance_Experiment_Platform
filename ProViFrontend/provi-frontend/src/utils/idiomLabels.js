// Per-task idiom display-label overrides: { task_key: { idiom_key: label } }.
// Mirrors the backend source of truth in
// provibackend/ProViBackend/app/label_overrides.py. Keep the two in sync.
export const TASK_IDIOM_LABEL_OVERRIDES = {
  task10: { heatmap: "Matrix" },
};

// Return the display label for an idiom in the context of a task, applying any
// per-task override and falling back to the idiom's global label.
export function resolveIdiomLabel(taskKey, idiomKey, defaultLabel) {
  return TASK_IDIOM_LABEL_OVERRIDES[taskKey]?.[idiomKey] ?? defaultLabel;
}
