// Immediately persists one wizard-step change to the backend, tagging the
// experiment with the step the admin was on so "Continue Editing" can
// resume at the exact same page.
export async function saveWizardStep(experimentId, stepKey, fields, { endpoint } = {}) {
  const url = endpoint
    ? `/api/admin/experiments/${encodeURIComponent(experimentId)}/${endpoint}`
    : `/api/admin/experiments/${encodeURIComponent(experimentId)}`;
  const res = await fetch(url, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...fields, current_step: stepKey }),
  });
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || `Server error: ${res.status}`);
  }
  return res;
}

// --- Ordering ---------------------------------------------------------------
//
// Every autosaving step PATCHes the *whole* state on each click (the task list,
// the selected sections, the idiom map). Fired off in parallel, those requests
// can arrive out of order, and the last one to land wins: ticking 37 task
// checkboxes quickly could leave the experiment holding whichever list the
// slowest request happened to carry. Selections then came back missing.
//
// queueWizardSave keeps one request per experiment/payload-shape in flight at a
// time and, while it is, remembers only the newest state — the intermediate
// ones describe a selection the admin has already moved past. So the writes are
// ordered and the last write is always what the page shows.
//
// The key includes the payload's field names: two steps writing different
// fields of the same document must not supersede each other.

const inFlight = new Map(); // key -> Promise of the request now running
const queued = new Map();   // key -> the one save waiting behind it

function queueKey(experimentId, fields, endpoint) {
  return `${experimentId}|${endpoint || ""}|${Object.keys(fields).sort().join(",")}`;
}

function run(key, save) {
  const promise = save().finally(() => {
    inFlight.delete(key);
    const next = queued.get(key);
    if (next) {
      queued.delete(key);
      run(key, next.save).then(next.resolve, next.reject);
    }
  });
  inFlight.set(key, promise);
  return promise;
}

export function queueWizardSave(experimentId, stepKey, fields, { endpoint } = {}) {
  const key = queueKey(experimentId, fields, endpoint);
  const save = () => saveWizardStep(experimentId, stepKey, fields, { endpoint });
  if (!inFlight.has(key)) return run(key, save);
  return new Promise((resolve, reject) => {
    // Whatever was waiting is superseded, not failed: this payload includes it.
    const superseded = queued.get(key);
    if (superseded) superseded.resolve();
    queued.set(key, { save, resolve, reject });
  });
}
