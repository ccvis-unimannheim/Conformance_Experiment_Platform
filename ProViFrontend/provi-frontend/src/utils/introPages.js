// Per-experiment config for the two participant intro pages shown between the
// knowledge questions and the tasks:
//   1. Key Concepts     (/conformance-terms)
//   2. Before You Begin (/taskintro)
// The admin picks which sections each page shows (/admin/experiments/concepts);
// a page with no sections selected is skipped entirely.

export const CONCEPT_SECTIONS = [
  { key: "process_model", label: "Process Model Diagram", icon: "account_tree",
    description: "The process model (guideline) used throughout the study — the uploaded image, or the default order-to-cash diagram." },
  { key: "event_log", label: "Process, Event, Case, Trace & Event Log", icon: "table_rows",
    description: "Definitions of the five nested concepts, with an example trace and an example event log." },
  { key: "attribute", label: "Attribute", icon: "tune",
    description: "Control-flow, data, resource and time attributes of events." },
  { key: "guideline", label: "Guideline", icon: "rule",
    description: "What a guideline is and how it relates to the BPMN process model." },
];

export const TASKINTRO_SECTIONS = [
  { key: "the_process", label: "The Process", icon: "hub",
    description: "Reminder that all tasks are about the same process, with the process model diagram." },
  { key: "what_to_expect", label: "What to Expect", icon: "quiz",
    description: "How the task pages work (question + visualisation, Key Terms chips)." },
  { key: "alignment", label: "Alignment & Move Types", icon: "compare_arrows",
    description: "Alignment example table; synchronous, model and log moves." },
  { key: "violation", label: "Guideline Violation", icon: "warning",
    description: "Log and model moves as the two types of guideline violation." },
  { key: "conformant_traces", label: "Conformant and Non-conformant Traces", icon: "route",
    description: "Definitions with examples." },
  { key: "fitness", label: "Degree of Conformance (Fitness)", icon: "speed",
    description: "Trace and log fitness, with how to interpret the values." },
];

// Sections whose definitions come from the cited source. A page's citation is
// only shown when at least one of them is, so a page left with just the diagram
// or "What to Expect" doesn't claim "Definitions adapted from…".
export const CONCEPT_DEFINITION_SECTIONS = ["event_log", "attribute", "guideline"];
export const TASKINTRO_DEFINITION_SECTIONS = ["alignment", "violation", "conformant_traces", "fitness"];

// Plain-text form of the default reference; IntroCitation renders it with the
// book title in italics when no custom text is set.
export const DEFAULT_CITATION_TEXT =
  "Definitions adapted from: Carmona, J., van Dongen, B., Solti, A., & Weidlich, M. (2018). " +
  "Conformance Checking: Relating Processes and Models. Springer. " +
  "ISBN 978-3-319-99413-0 · DOI 10.1007/978-3-319-99414-7";

const DEFAULT_CITATION = { enabled: true, text: null };  // text null = default reference

export const DEFAULT_INTRO_PAGES = {
  concept_sections: CONCEPT_SECTIONS.map((s) => s.key),
  taskintro_sections: TASKINTRO_SECTIONS.map((s) => s.key),
  concept_citation: DEFAULT_CITATION,
  taskintro_citation: DEFAULT_CITATION,
  process_model_url: null,
};

function normalizeCitation(c) {
  if (!c || typeof c !== "object") return DEFAULT_CITATION;
  return { enabled: c.enabled !== false, text: typeof c.text === "string" && c.text.trim() ? c.text : null };
}

export function showsCitation(citation, shownSections, definitionSections) {
  return citation.enabled && definitionSections.some((k) => shownSections.has(k));
}

// Falls back to showing everything with the default diagram, so a failed
// request never hides content participants would otherwise have seen.
export async function fetchIntroPages() {
  try {
    const res = await fetch("/api/participant/intro-pages", { credentials: "include" });
    if (!res.ok) return DEFAULT_INTRO_PAGES;
    const data = await res.json();
    return {
      concept_sections: Array.isArray(data.concept_sections) ? data.concept_sections : DEFAULT_INTRO_PAGES.concept_sections,
      taskintro_sections: Array.isArray(data.taskintro_sections) ? data.taskintro_sections : DEFAULT_INTRO_PAGES.taskintro_sections,
      concept_citation: normalizeCitation(data.concept_citation),
      taskintro_citation: normalizeCitation(data.taskintro_citation),
      process_model_url: data.process_model_url ?? null,
    };
  } catch {
    return DEFAULT_INTRO_PAGES;
  }
}

// Where to go after the knowledge questions / Key Concepts, and where Back on
// Before You Begin leads, skipping any page that has no sections enabled.
export function pageAfterKnowledge(cfg) {
  if (cfg.concept_sections.length > 0) return "/conformance-terms";
  return pageAfterConcepts(cfg);
}

export function pageAfterConcepts(cfg) {
  return cfg.taskintro_sections.length > 0 ? "/taskintro" : "/taskexecution";
}

// The knowledge step can be skipped too (see utils/knowledgeStep.js), so pass
// whether it has any questions.
export function pageBeforeTaskintro(cfg, hasKnowledgeQuestions) {
  if (cfg.concept_sections.length > 0) return "/conformance-terms";
  return hasKnowledgeQuestions ? "/knowledgequestion" : "/prequestionnaire";
}
