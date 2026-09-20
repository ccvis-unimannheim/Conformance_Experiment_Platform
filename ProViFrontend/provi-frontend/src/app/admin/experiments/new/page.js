"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import AdminNav from "../../../../components/Admin/AdminNav";
import ExperimentDetailsForm from "../../../../components/Admin/ExperimentDetailsForm";
import DatasetSelectTable from "../../../../components/Admin/DatasetSelectTable";
import BundleStartCard from "../../../../components/Admin/BundleStartCard";
import WizardSteps from "../../../../components/Admin/WizardSteps";
import { queueWizardSave } from "../../../../utils/wizardSave";

export default function NewExperimentPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  // Reached with an id when the admin steps back here from a later wizard step:
  // that draft is edited in place. Without one, this is a new experiment and the
  // draft is created as soon as the form has a name and a dataset.
  const resumedId = searchParams.get("experiment_id");
  // Set when reached by jumping back from a later step; Next then returns
  // there instead of continuing forward (see WizardSteps.js).
  const returnTo = searchParams.get("return_to");
  const [experimentId] = useState(() => resumedId || crypto.randomUUID());
  const createdRef = useRef(Boolean(resumedId));

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedIds, setSelectedIds] = useState(new Set());

  const [pairs, setPairs] = useState([]);
  const [loadingPairs, setLoadingPairs] = useState(true);
  const [pairsError, setPairsError] = useState(null);

  const [randomizeOrder, setRandomizeOrder] = useState(true);
  const [designType, setDesignType] = useState("between");

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);
  // This draft's images came from an uploaded zip: it has no dataset, and
  // taking one would mean generating over those images (the backend refuses).
  const [bundleOnly, setBundleOnly] = useState(false);
  // Whether the zip-upload card is open. Lifted up (rather than the card's own
  // state) so the dataset table below can be swapped for a note while it is —
  // a dataset genuinely isn't needed for that route, and showing both at once
  // is what made the previous, duplicated-fields layout confusing.
  const [bundleCardOpen, setBundleCardOpen] = useState(false);

  // Fill the form from the draft being edited, so stepping back shows what was
  // entered rather than a blank page that would overwrite it on the next edit.
  useEffect(() => {
    if (!resumedId) return;
    fetch(`/api/admin/experiments/${encodeURIComponent(resumedId)}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((exp) => {
        if (!exp) return;
        setName(exp.name || "");
        setSelectedIds(new Set(exp.dataset_ids || []));
        if (exp.design_type) setDesignType(exp.design_type);
        setRandomizeOrder((exp.within_sequence_mode || "random") === "random");
        setBundleOnly(!!exp.bundle_only);
      })
      .catch(() => {});
  }, [resumedId]);

  // Undo a bundle upload: the images, the tasks and idioms that came with them
  // go, and the experiment can take a dataset like any other.
  async function discardBundle() {
    if (!window.confirm(
      "Discard the uploaded images? This experiment's tasks, idioms and images all came from that " +
      "zip, so all three are removed and it starts again from choosing a dataset. Its name and " +
      "study design are kept. Download the zip again from the source experiment if you need it."
    )) return;
    try {
      const res = await fetch(
        `/api/admin/experiments/${encodeURIComponent(resumedId)}/discard-bundle`,
        { method: "POST" }
      );
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`);
      }
      setBundleOnly(false);
      setSelectedIds(new Set());
    } catch (e) {
      setSubmitError(e.message);
    }
  }

  useEffect(() => {
    fetch(`/api/admin/datasets`)
      .then((r) => {
        if (!r.ok) throw new Error(`Server error: ${r.status}`);
        return r.json();
      })
      .then((data) => setPairs(data))
      .catch((e) => setPairsError(e.message))
      .finally(() => setLoadingPairs(false));
  }, []);

  // Create the draft experiment as soon as it becomes valid (name + ≥1 dataset),
  // so every subsequent edit on this page can autosave via PATCH instead of
  // waiting for "Next".
  useEffect(() => {
    if (createdRef.current) return;
    if (!name.trim() || selectedIds.size === 0) return;
    createdRef.current = true;
    fetch(`/api/admin/experiments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        _id: experimentId,
        name: name.trim(),
        type: "CC",
        status: "draft",
        design_type: designType,
        between_factors: [],
        within_factors: [],
        stratification_fields: [],
        between_balance_mode: "random",
        within_sequence_mode: randomizeOrder ? "random" : "fixed",
        dataset_ids: Array.from(selectedIds),
        task_configs: [],
        current_step: "prequestionnaire",
        created_by: "admin",
        created_at: new Date().toISOString(),
      }),
    })
      .then((r) => {
        if (!r.ok) throw new Error(`Server error: ${r.status}`);
      })
      .catch((e) => {
        createdRef.current = false;
        setSubmitError(e.message);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [name, selectedIds]);

  function persistField(fields) {
    if (!createdRef.current) return;
    queueWizardSave(experimentId, "prequestionnaire", fields).catch((e) => setSubmitError(e.message));
  }

  function handleFormChange(field, value) {
    if (field === "name") {
      setName(value);
      if (createdRef.current) persistField({ name: value.trim() });
    } else {
      setDescription(value);
    }
  }

  function handleToggle(datasetId) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(datasetId) ? next.delete(datasetId) : next.add(datasetId);
      if (createdRef.current) persistField({ dataset_ids: Array.from(next) });
      return next;
    });
  }

  function handleDesignTypeChange(value) {
    setDesignType(value);
    persistField({ design_type: value });
  }

  function handleRandomizeOrderChange() {
    setRandomizeOrder((v) => {
      const next = !v;
      persistField({ within_sequence_mode: next ? "random" : "fixed" });
      return next;
    });
  }

  async function handleNext() {
    if (!name.trim()) {
      setSubmitError("Please enter an experiment name.");
      return;
    }
    // A bundle experiment has no dataset by design, and already exists.
    if (!bundleOnly && selectedIds.size === 0) {
      setSubmitError("Please select at least one dataset.");
      return;
    }

    setSubmitError(null);
    setIsSubmitting(true);
    try {
      if (!createdRef.current) {
        // Fallback: creation-on-input never fired (e.g. re-cleared then re-filled
        // in the same tick) — create the draft now.
        const response = await fetch(`/api/admin/experiments`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            _id: experimentId,
            name: name.trim(),
            type: "CC",
            status: "draft",
            design_type: designType,
            between_factors: [],
            within_factors: [],
            stratification_fields: [],
            between_balance_mode: "random",
            within_sequence_mode: randomizeOrder ? "random" : "fixed",
            dataset_ids: Array.from(selectedIds),
            task_configs: [],
            current_step: "prequestionnaire",
            created_by: "admin",
            created_at: new Date().toISOString(),
          }),
        });
        if (!response.ok) {
          const err = await response.json().catch(() => ({}));
          throw new Error(err.detail || `Server error: ${response.status}`);
        }
        createdRef.current = true;
      }
      router.push(
        returnTo
          ? `/admin/experiments/${returnTo}?experiment_id=${encodeURIComponent(experimentId)}`
          : `/admin/experiments/prequestionnaire?experiment_id=${encodeURIComponent(experimentId)}`
      );
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="experiment-setup" />
      <WizardSteps experimentId={resumedId} current="new" bundleOnly={bundleOnly} />

      <main className="flex-grow max-w-[900px] mx-auto w-full px-6 py-12 pb-32">
        <div className="mb-12">
          <h1 className="text-h1 text-primary mb-2">
            {resumedId ? "Experiment Details" : "Create New Experiment"}
          </h1>
          <p className="text-body-lg text-secondary">
            Set up your research environment: name it, choose its design, then either pick a dataset
            to generate from or upload a zip that already has its images.
          </p>
        </div>

        <div className="space-y-section-gap">
          <ExperimentDetailsForm
            name={name}
            description={description}
            onChange={handleFormChange}
          />
        </div>

        {/* Study design and trial order apply whichever way the experiment gets
            its content below, so they are set once here rather than repeated
            in the zip route too — the previous layout asked for the name and
            the design twice, in two different-looking forms, for no reason. */}
        <section className="mt-section-gap bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
          <h2 className="text-h2 text-primary mb-6">Experiment Settings</h2>
          <div className="space-y-6">
            <div>
              <p className="text-label-caps text-on-surface-variant mb-3">STUDY DESIGN</p>
              <div className="flex gap-3">
                {[
                  { value: "between", label: "Between-subjects", desc: "Each participant sees one idiom per task (balanced random allocation)." },
                  { value: "within",  label: "Within-subjects",  desc: "Each participant sees all idioms for every task." },
                ].map(({ value, label, desc }) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => handleDesignTypeChange(value)}
                    className={`flex-1 text-left px-4 py-3 rounded-lg border transition-all ${
                      designType === value
                        ? "border-primary bg-primary/5"
                        : "border-outline-variant hover:border-primary/50"
                    }`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <div className={`w-4 h-4 rounded-full border-2 flex-shrink-0 flex items-center justify-center transition-all ${
                        designType === value ? "border-primary" : "border-outline-variant"
                      }`}>
                        {designType === value && (
                          <div className="w-2 h-2 rounded-full bg-primary" />
                        )}
                      </div>
                      <span className={`text-body-sm font-medium ${designType === value ? "text-primary" : "text-on-surface"}`}>
                        {label}
                      </span>
                    </div>
                    <p className="text-body-xs text-secondary ml-6">{desc}</p>
                  </button>
                ))}
              </div>
            </div>

            <div>
              <p className="text-label-caps text-on-surface-variant mb-3">TRIAL ORDER</p>
              <div
                className="flex items-center gap-3 cursor-pointer"
                onClick={handleRandomizeOrderChange}
              >
                <div className={`w-4 h-4 rounded border-2 flex-shrink-0 flex items-center justify-center transition-all ${
                  randomizeOrder ? "bg-primary border-primary" : "border-outline-variant"
                }`}>
                  {randomizeOrder && (
                    <span className="material-symbols-outlined text-white leading-none" style={{ fontSize: "11px" }}>check</span>
                  )}
                </div>
                <span className="text-body-sm text-on-surface select-none">
                  Randomize question order for each participant
                </span>
              </div>
            </div>
          </div>
        </section>

        {/* How this experiment gets its tasks, idioms and images: a dataset it
            generates from, or a zip that already has everything. A dataset is
            meaningless for the zip route, so opening the card replaces the
            table with a one-line note instead of leaving both on screen. */}
        <div className="mt-section-gap space-y-section-gap">
          {bundleOnly ? (
            <>
              <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
                <h2 className="text-h2 text-primary mb-3">Dataset</h2>
                <p className="text-body-sm text-secondary mb-2">
                  The zip you uploaded is saved — this experiment shows exactly its images, so it
                  needs no dataset and nothing is generated for it. A dataset cannot be added while
                  that is the case.
                </p>
                <p className="text-body-sm text-secondary mb-4">
                  Uploaded the wrong zip, or want a different one? Replace it below without starting
                  over, or discard it to build this experiment from a dataset instead — either way its
                  tasks and idioms go with the images, since neither exists without them; the name and
                  study design stay.
                </p>
                <button
                  type="button"
                  onClick={discardBundle}
                  className="px-4 py-2 rounded-lg border border-outline-variant text-body-sm hover:border-primary/50"
                >
                  Discard the uploaded images and choose a dataset
                </button>
              </section>

              <BundleStartCard
                name={name}
                designType={designType}
                randomizeOrder={randomizeOrder}
                open={bundleCardOpen}
                onToggle={() => setBundleCardOpen((v) => !v)}
                replaceExperimentId={resumedId}
                onCreated={(data) => {
                  const next = data.needs_answer_format ? "answer-format" : "overview";
                  router.push(
                    `/admin/experiments/${next}?experiment_id=${encodeURIComponent(data.experiment_id)}`
                  );
                }}
              />
            </>
          ) : (
            <>
              {!resumedId && (
                <BundleStartCard
                  name={name}
                  designType={designType}
                  randomizeOrder={randomizeOrder}
                  open={bundleCardOpen}
                  onToggle={() => setBundleCardOpen((v) => !v)}
                  onCreated={(data) => {
                    const next = data.needs_answer_format ? "answer-format" : "overview";
                    router.push(
                      `/admin/experiments/${next}?experiment_id=${encodeURIComponent(data.experiment_id)}`
                    );
                  }}
                />
              )}
              {bundleCardOpen ? (
                <p className="text-body-sm text-secondary bg-surface-container-lowest border border-outline-variant rounded-xl p-gutter">
                  No dataset needed — this experiment&apos;s images will come from the zip above.
                </p>
              ) : (
                <DatasetSelectTable
                  pairs={pairs}
                  selectedIds={selectedIds}
                  onToggle={handleToggle}
                  isLoading={loadingPairs}
                  error={pairsError}
                />
              )}
            </>
          )}
        </div>

        {submitError && (
          <p className="mt-6 text-body-sm text-error">{submitError}</p>
        )}

        <div className="mt-12 flex justify-end">
          <button
            type="button"
            onClick={handleNext}
            disabled={isSubmitting}
            className="flex items-center gap-2 text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isSubmitting ? "Saving…" : returnTo ? "Save & Return" : "Next"}
            {!isSubmitting && (
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
