"use client";

import { useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AdminNav from "../../../../components/Admin/AdminNav";

const ALL_SECTIONS = [
  {
    key: "personal_info",
    label: "Personal Information",
    description: "Gender and age range of the participant.",
    icon: "person",
    fields: ["Gender", "Age range"],
  },
  {
    key: "academic_profile",
    label: "Academic Profile",
    description: "Highest education level and professional role.",
    icon: "school",
    fields: ["Education level", "Role (student / researcher / industry)"],
  },
  {
    key: "technical_expertise",
    label: "Technical Expertise",
    description: "Self-rated familiarity with process mining, conformance checking, and data visualisation.",
    icon: "bar_chart",
    fields: ["Process Mining rating", "Conformance Checking rating", "Data Visualisation rating"],
  },
  {
    key: "tool_experience",
    label: "Tool Experience",
    description: "Which process mining tools the participant has used before.",
    icon: "build",
    fields: ["Celonis", "Disco", "ProM", "PM4Py", "Apromore", "SAP Signavio", "None"],
  },
];

const DEFAULT_SECTIONS = ALL_SECTIONS.map((s) => s.key);

export default function PrequestionnairePage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const experimentId = searchParams.get("experiment_id");

  const [enabled, setEnabled] = useState(new Set(DEFAULT_SECTIONS));
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);

  // Load existing selection from the experiment if available
  useEffect(() => {
    if (!experimentId) {
      setLoading(false);
      return;
    }
    fetch("/api/admin/experiments")
      .then((r) => (r.ok ? r.json() : []))
      .then((exps) => {
        const exp = Array.isArray(exps) ? exps.find((e) => e._id === experimentId) : null;
        if (exp?.prequestionnaire_sections?.length) {
          setEnabled(new Set(exp.prequestionnaire_sections));
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [experimentId]);

  function toggleSection(key) {
    setEnabled((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  async function handleNext() {
    if (!experimentId) {
      router.push("/admin/experiments/knowledge");
      return;
    }
    setSaveError(null);
    setSaving(true);
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(experimentId)}/prequestionnaire-sections`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sections: Array.from(enabled) }),
        }
      );
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || `Server error: ${res.status}`);
      }
      router.push(`/admin/experiments/knowledge?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      setSaveError(e.message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="experiment-setup" />

      <main className="flex-grow max-w-[900px] mx-auto w-full px-6 py-12 pb-32">
        <div className="mb-12">
          <h1 className="text-h1 text-primary mb-2">Pre-Questionnaire Sections</h1>
          <p className="text-body-lg text-secondary">
            Choose which background information sections participants will fill in before the experiment.
            All sections are enabled by default. Uncheck any you want to skip.
          </p>
        </div>

        {loading ? (
          <p className="text-body-sm text-secondary">Loading…</p>
        ) : (
          <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
            <div className="flex items-baseline justify-between mb-6">
              <h2 className="text-h2 text-primary">Sections</h2>
              <span className="text-label-caps text-on-surface-variant">
                {enabled.size} / {ALL_SECTIONS.length} enabled
              </span>
            </div>

            <div className="space-y-3">
              {ALL_SECTIONS.map((section) => {
                const checked = enabled.has(section.key);
                return (
                  <div
                    key={section.key}
                    onClick={() => toggleSection(section.key)}
                    className={`flex items-start gap-4 p-4 rounded-xl border cursor-pointer transition-colors ${
                      checked
                        ? "border-primary/40 bg-primary/5"
                        : "border-outline-variant/40 hover:bg-surface-container"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleSection(section.key)}
                      onClick={(e) => e.stopPropagation()}
                      className="mt-0.5 w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded flex-shrink-0"
                    />
                    <span className="material-symbols-outlined text-on-surface-variant flex-shrink-0 mt-0.5">
                      {section.icon}
                    </span>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-semibold text-on-surface">{section.label}</p>
                      <p className="text-[12px] text-on-surface-variant mt-0.5">{section.description}</p>
                      <p className="text-[11px] text-on-surface-variant/70 mt-1">
                        {section.fields.join(" · ")}
                      </p>
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        )}

        {saveError && <p className="mt-6 text-body-sm text-error">{saveError}</p>}

        <div className="mt-12 flex justify-end">
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
