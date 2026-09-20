"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import AdminNav from "../../../../components/Admin/AdminNav";
import WizardSteps from "../../../../components/Admin/WizardSteps";
import ProcessModelImage from "../../../../components/General/ProcessModelImage";
import IntroCitation from "../../../../components/General/IntroCitation";
import { queueWizardSave } from "../../../../utils/wizardSave";
import {
  CONCEPT_SECTIONS,
  TASKINTRO_SECTIONS,
  CONCEPT_DEFINITION_SECTIONS,
  TASKINTRO_DEFINITION_SECTIONS,
  DEFAULT_CITATION_TEXT,
  DEFAULT_INTRO_PAGES,
} from "../../../../utils/introPages";

// The two participant pages configured on this step, in the order participants see them.
const PAGES = [
  {
    field: "concept_sections",
    citation: "concept",
    number: 1,
    title: "Key Concepts",
    heading: "Key Concepts in Conformance Checking",
    sections: CONCEPT_SECTIONS,
    definitionSections: CONCEPT_DEFINITION_SECTIONS,
  },
  {
    field: "taskintro_sections",
    citation: "taskintro",
    number: 2,
    title: "Before You Begin",
    heading: "Before You Begin",
    sections: TASKINTRO_SECTIONS,
    definitionSections: TASKINTRO_DEFINITION_SECTIONS,
  },
];

// Unchanged or blank text is stored as null, i.e. "the default reference".
function normalizeCitationText(text) {
  const t = (text ?? "").trim();
  return !t || t === DEFAULT_CITATION_TEXT ? null : text;
}

function FlowStep({ label, sub, skipped, muted }) {
  return (
    <div
      className={`px-3 py-2 rounded-lg border text-center ${
        muted
          ? "border-outline-variant/40 bg-surface-container text-on-surface-variant"
          : skipped
            ? "border-dashed border-outline-variant text-on-surface-variant/60"
            : "border-primary/40 bg-primary/5 text-primary"
      }`}
    >
      <p className={`text-xs font-semibold whitespace-nowrap ${skipped ? "line-through" : ""}`}>{label}</p>
      {sub && <p className="text-[10px] whitespace-nowrap">{sub}</p>}
    </div>
  );
}

function FlowArrow() {
  return <span className="material-symbols-outlined text-on-surface-variant text-sm">arrow_forward</span>;
}

export default function IntroPagesSetupPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [enabled, setEnabled] = useState({
    concept_sections: new Set(DEFAULT_INTRO_PAGES.concept_sections),
    taskintro_sections: new Set(DEFAULT_INTRO_PAGES.taskintro_sections),
  });
  // text: the admin's draft; null = default reference
  const [citations, setCitations] = useState({
    concept: { enabled: true, text: null },
    taskintro: { enabled: true, text: null },
  });
  const [hasCustomModel, setHasCustomModel] = useState(false);
  const [modelVersion, setModelVersion] = useState(0);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (!experimentId) {
      setLoading(false);
      return;
    }
    fetch("/api/admin/experiments")
      .then((r) => (r.ok ? r.json() : []))
      .then((exps) => {
        const exp = Array.isArray(exps) ? exps.find((e) => e._id === experimentId) : null;
        if (!exp) return;
        // An empty list is a real choice (page skipped), so only fall back to
        // the defaults when the field is missing (experiments created earlier).
        setEnabled({
          concept_sections: new Set(Array.isArray(exp.concept_sections) ? exp.concept_sections : DEFAULT_INTRO_PAGES.concept_sections),
          taskintro_sections: new Set(Array.isArray(exp.taskintro_sections) ? exp.taskintro_sections : DEFAULT_INTRO_PAGES.taskintro_sections),
        });
        setCitations({
          concept: { enabled: exp.concept_citation_enabled !== false, text: exp.concept_citation_text ?? null },
          taskintro: { enabled: exp.taskintro_citation_enabled !== false, text: exp.taskintro_citation_text ?? null },
        });
        setHasCustomModel(Boolean(exp.process_model_ext));
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [experimentId]);

  function body(sections, cites) {
    return {
      concept_sections: Array.from(sections.concept_sections),
      taskintro_sections: Array.from(sections.taskintro_sections),
      concept_citation_enabled: cites.concept.enabled,
      concept_citation_text: normalizeCitationText(cites.concept.text),
      taskintro_citation_enabled: cites.taskintro.enabled,
      taskintro_citation_text: normalizeCitationText(cites.taskintro.text),
    };
  }

  function save(sections, cites) {
    if (!experimentId) return;
    queueWizardSave(experimentId, "concepts", body(sections, cites), { endpoint: "intro-pages" })
      .catch((e) => setSaveError(e.message));
  }

  function update(field, makeSet) {
    const next = { ...enabled, [field]: makeSet(enabled[field]) };
    setEnabled(next);
    save(next, citations);
  }

  // Typing only updates the draft (persist: false); the text is saved on blur.
  function updateCitation(page, patch, { persist = true } = {}) {
    const next = { ...citations, [page]: { ...citations[page], ...patch } };
    setCitations(next);
    if (persist) save(enabled, next);
  }

  function toggleSection(field, key) {
    update(field, (prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !experimentId) return;
    setSaveError(null);
    setUploading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/process-model`,
        { method: "POST", body: form }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      setHasCustomModel(true);
      setModelVersion((v) => v + 1);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleResetModel() {
    if (!experimentId) return;
    setSaveError(null);
    setUploading(true);
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/process-model`,
        { method: "DELETE" }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      setHasCustomModel(false);
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setUploading(false);
    }
  }

  async function handleNext() {
    if (!experimentId) {
      router.push("/admin/experiments/task");
      return;
    }
    setSaveError(null);
    setSaving(true);
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/intro-pages`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body(enabled, citations)),
        }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      router.push(`/admin/experiments/task?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  }

  const modelUrl = hasCustomModel && experimentId
    ? `/api/admin/experiments/${encodeURIComponent(experimentId)}/process-model?v=${modelVersion}`
    : null;
  const diagramShown =
    enabled.concept_sections.has("process_model") || enabled.taskintro_sections.has("the_process");

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="experiment-setup" />
      <WizardSteps experimentId={experimentId} current="concepts" />

      <main className="flex-grow max-w-[900px] mx-auto w-full px-6 py-12 pb-32">
        <div className="mb-8">
          <h1 className="text-h1 text-primary mb-2">Introduction Pages</h1>
          <p className="text-body-lg text-secondary">
            After the knowledge questions, participants see <strong>two separate pages</strong> that
            introduce the concepts used in the tasks. Choose which sections each page shows. All sections
            are enabled by default; a page with no sections selected is skipped.
          </p>
        </div>

        {loading ? (
          <p className="text-body-sm text-secondary">Loading…</p>
        ) : (
          <div className="space-y-section-gap">

            {/* What participants will go through */}
            <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
              <p className="text-label-caps text-on-surface-variant mb-4">Participant flow</p>
              <div className="flex flex-wrap items-center gap-2">
                <FlowStep label="Knowledge Questions" muted />
                {PAGES.map((page) => {
                  const skipped = enabled[page.field].size === 0;
                  return [
                    <FlowArrow key={`arrow-${page.field}`} />,
                    <FlowStep
                      key={page.field}
                      label={`Page ${page.number}: ${page.title}`}
                      sub={skipped ? "skipped" : null}
                      skipped={skipped}
                    />,
                  ];
                })}
                <FlowArrow />
                <FlowStep label="Tasks" muted />
              </div>
            </section>

            {PAGES.map((page) => {
              const selected = enabled[page.field];
              const skipped = selected.size === 0;
              return (
                <section key={page.field} className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
                  <div className="flex items-start justify-between gap-4 mb-6">
                    <div>
                      <p className="text-label-caps text-on-surface-variant mb-1">
                        Participant page {page.number} of {PAGES.length}
                      </p>
                      <h2 className="text-h2 text-primary">{page.title}</h2>
                      <p className="text-[12px] text-on-surface-variant mt-1">
                        Shown to participants as &ldquo;{page.heading}&rdquo;.
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-2 flex-shrink-0">
                      <span className="text-label-caps text-on-surface-variant">
                        {selected.size} / {page.sections.length} enabled
                      </span>
                      <div className="flex gap-2">
                        <button
                          type="button"
                          onClick={() => update(page.field, () => new Set())}
                          className="text-xs font-semibold border border-border-subtle text-on-surface-variant px-3 py-1.5 rounded-lg hover:bg-surface-container transition-colors whitespace-nowrap"
                        >
                          Deselect All
                        </button>
                        <button
                          type="button"
                          onClick={() => update(page.field, () => new Set(page.sections.map((s) => s.key)))}
                          className="text-xs font-semibold border border-border-subtle text-on-surface-variant px-3 py-1.5 rounded-lg hover:bg-surface-container transition-colors whitespace-nowrap"
                        >
                          Select All
                        </button>
                      </div>
                    </div>
                  </div>

                  {skipped && (
                    <p className="mb-4 flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2">
                      <span className="material-symbols-outlined text-sm">visibility_off</span>
                      No sections selected — participants will skip this page.
                    </p>
                  )}

                  <div className="space-y-3">
                    {page.sections.map((section) => {
                      const checked = selected.has(section.key);
                      return (
                        <div
                          key={section.key}
                          onClick={() => toggleSection(page.field, section.key)}
                          className={`flex items-start gap-4 p-4 rounded-xl border cursor-pointer transition-colors ${
                            checked ? "border-primary/40 bg-primary/5" : "border-outline-variant/40 hover:bg-surface-container"
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={() => toggleSection(page.field, section.key)}
                            onClick={(e) => e.stopPropagation()}
                            className="mt-0.5 w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded flex-shrink-0"
                          />
                          <span className="material-symbols-outlined text-on-surface-variant flex-shrink-0 mt-0.5">
                            {section.icon}
                          </span>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-semibold text-on-surface">{section.label}</p>
                            <p className="text-[12px] text-on-surface-variant mt-0.5">{section.description}</p>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {!skipped && (() => {
                    const cite = citations[page.citation];
                    const hasDefinitions = page.definitionSections.some((k) => selected.has(k));
                    const isDefault = normalizeCitationText(cite.text) === null;
                    return (
                      <div className="mt-6 pt-6 border-t border-outline-variant/40">
                        <div className="flex items-start justify-between gap-4 mb-3">
                          <label className="flex items-start gap-3 cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={cite.enabled}
                              onChange={(e) => updateCitation(page.citation, { enabled: e.target.checked })}
                              className="mt-0.5 w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded flex-shrink-0"
                            />
                            <span>
                              <span className="block text-sm font-semibold text-on-surface">Show citation at the bottom of this page</span>
                              <span className="block text-[12px] text-on-surface-variant mt-0.5">
                                Only shown when at least one definition section (
                                {page.definitionSections
                                  .map((k) => page.sections.find((s) => s.key === k)?.label)
                                  .join(", ")}
                                ) is enabled.
                              </span>
                            </span>
                          </label>
                          <span className="text-[10px] bg-surface-container text-on-surface-variant px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider flex-shrink-0">
                            {isDefault ? "Default" : "Custom"}
                          </span>
                        </div>

                        {cite.enabled && !hasDefinitions && (
                          <p className="mb-3 flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2">
                            <span className="material-symbols-outlined text-sm">info</span>
                            No definition section is enabled, so participants won&apos;t see the citation on this page.
                          </p>
                        )}

                        {cite.enabled && (
                          <>
                            <textarea
                              value={cite.text ?? DEFAULT_CITATION_TEXT}
                              onChange={(e) => updateCitation(page.citation, { text: e.target.value }, { persist: false })}
                              onBlur={() => save(enabled, citations)}
                              rows={3}
                              className="w-full border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/40 resize-y"
                            />
                            <div className="flex items-center justify-between gap-4 mt-2 mb-3">
                              <p className="text-[11px] text-on-surface-variant">
                                Plain text; line breaks are kept. Leave empty to use the default reference.
                              </p>
                              {!isDefault && (
                                <button
                                  type="button"
                                  onClick={() => updateCitation(page.citation, { text: null })}
                                  className="flex items-center gap-1 text-xs font-semibold text-on-surface-variant hover:text-primary transition-colors whitespace-nowrap"
                                >
                                  <span className="material-symbols-outlined text-sm">restart_alt</span>
                                  Restore Default
                                </button>
                              )}
                            </div>
                            <p className="text-label-caps text-on-surface-variant mb-2">Preview</p>
                            <IntroCitation text={normalizeCitationText(cite.text)} />
                          </>
                        )}
                      </div>
                    );
                  })()}
                </section>
              );
            })}

            {/* Process model image, shared by both pages */}
            <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
              <div className="flex items-start justify-between gap-4 mb-4">
                <div>
                  <h2 className="text-h2 text-primary">Process Model Diagram</h2>
                  <p className="text-[12px] text-on-surface-variant mt-1">
                    Used in &ldquo;Process Model Diagram&rdquo; on page 1 and &ldquo;The Process&rdquo; on page 2.
                    Upload an image of your own BPMN model (SVG, PNG or JPG, max 10 MB), or keep the default
                    order-to-cash diagram.
                  </p>
                </div>
                <span className="text-[10px] bg-surface-container text-on-surface-variant px-2 py-0.5 rounded-full font-semibold uppercase tracking-wider flex-shrink-0">
                  {hasCustomModel ? "Custom" : "Default"}
                </span>
              </div>

              {!diagramShown && (
                <p className="mb-4 flex items-center gap-2 text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2">
                  <span className="material-symbols-outlined text-sm">info</span>
                  Neither page currently includes the diagram section, so participants won&apos;t see it.
                </p>
              )}

              <div className="rounded-lg border border-outline-variant/40 bg-white p-4 mb-4">
                <ProcessModelImage url={modelUrl} style={{ width: "100%", height: "auto" }} />
              </div>

              <input
                ref={fileInputRef}
                type="file"
                accept=".svg,.png,.jpg,.jpeg,image/svg+xml,image/png,image/jpeg"
                onChange={handleUpload}
                className="hidden"
              />
              <div className="flex gap-3">
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={uploading || !experimentId}
                  className="flex items-center gap-1 text-sm font-semibold border border-primary text-primary px-4 py-2 rounded-lg hover:bg-primary/5 transition-colors disabled:opacity-40"
                >
                  <span className="material-symbols-outlined text-sm">upload</span>
                  {uploading ? "Working…" : hasCustomModel ? "Replace Image" : "Upload Image"}
                </button>
                {hasCustomModel && (
                  <button
                    type="button"
                    onClick={handleResetModel}
                    disabled={uploading}
                    className="flex items-center gap-1 text-sm font-semibold border border-border-subtle text-on-surface-variant px-4 py-2 rounded-lg hover:bg-surface-container transition-colors disabled:opacity-40"
                  >
                    <span className="material-symbols-outlined text-sm">restart_alt</span>
                    Restore Default
                  </button>
                )}
              </div>
            </section>
          </div>
        )}

        {saveError && <p className="mt-6 text-body-sm text-error">{saveError}</p>}

        <div className="mt-12 flex justify-between items-center">
          <Link
            href={`/admin/experiments/knowledge${experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""}`}
            className="text-sm text-on-surface-variant hover:text-primary flex items-center gap-1 transition-colors"
          >
            <span className="material-symbols-outlined text-sm">arrow_back</span> Previous Step
          </Link>
          <button
            type="button"
            onClick={handleNext}
            disabled={saving || loading}
            className="flex items-center gap-2 text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {saving ? "Saving…" : "Next"}
            {!saving && (
              <span className="material-symbols-outlined text-sm">chevron_right</span>
            )}
          </button>
        </div>
      </main>

      <div className="fixed top-24 -right-24 w-96 h-96 bg-primary/5 rounded-full blur-3xl -z-10" />
      <div className="fixed bottom-24 -left-24 w-96 h-96 bg-secondary/5 rounded-full blur-3xl -z-10" />
    </div>
  );
}
