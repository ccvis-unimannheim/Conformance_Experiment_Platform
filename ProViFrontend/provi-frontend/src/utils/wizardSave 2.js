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
