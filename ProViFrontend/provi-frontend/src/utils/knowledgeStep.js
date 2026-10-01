// Does this experiment ask any knowledge questions?
//
// The admin can deselect every one, and then the step does not exist: the page
// would render with nothing to answer and a Continue button that never enables,
// because it requires every question to be answered. So both neighbours of the
// step route around it rather than through it.
//
// Fails open. A failed or malformed request keeps the step in the journey,
// since wrongly skipping it would silently drop data the study asked for.
// Only a definite answer is cached, so a blip doesn't stick for the session.
let cached = null;

export async function hasKnowledgeQuestions() {
  if (cached !== null) return cached;
  try {
    const res = await fetch("/api/participant/knowledge-questions", {
      credentials: "include",
    });
    if (!res.ok) return true;
    const data = await res.json();
    cached = (data.questions ?? []).length > 0;
    return cached;
  } catch {
    return true;
  }
}
