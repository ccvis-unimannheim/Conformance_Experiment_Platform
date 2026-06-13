"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import AdminNav from "../../../../components/Admin/AdminNav";
import ExperimentDetailsForm from "../../../../components/Admin/ExperimentDetailsForm";
import DatasetSelectTable from "../../../../components/Admin/DatasetSelectTable";

export default function NewExperimentPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedIds, setSelectedIds] = useState(new Set());

  const [pairs, setPairs] = useState([]);
  const [loadingPairs, setLoadingPairs] = useState(true);
  const [pairsError, setPairsError] = useState(null);

  const [randomizeOrder, setRandomizeOrder] = useState(true);

  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

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

  function handleFormChange(field, value) {
    if (field === "name") setName(value);
    else setDescription(value);
  }

  function handleToggle(datasetId) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(datasetId) ? next.delete(datasetId) : next.add(datasetId);
      return next;
    });
  }

  async function handleNext() {
    if (!name.trim()) {
      setSubmitError("Please enter an experiment name.");
      return;
    }
    if (selectedIds.size === 0) {
      setSubmitError("Please select at least one dataset.");
      return;
    }

    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const experimentId = crypto.randomUUID();
      const response = await fetch(`/api/admin/experiments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          _id: experimentId,
          name: name.trim(),
          type: "CC",
          status: "draft",
          design_type: "between",
          between_factors: [],
          within_factors: [],
          stratification_fields: [],
          between_balance_mode: "random",
          within_sequence_mode: randomizeOrder ? "random" : "fixed",
          dataset_ids: Array.from(selectedIds),
          task_configs: [],
          created_by: "admin",
          created_at: new Date().toISOString(),
        }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.detail || `Server error: ${response.status}`);
      }

      router.push(`/admin/experiments/knowledge?experiment_id=${encodeURIComponent(experimentId)}`);
    } catch (e) {
      setSubmitError(e.message);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <AdminNav activeLink="experiment-setup" />

      <main className="flex-grow max-w-[900px] mx-auto w-full px-6 py-12 pb-32">
        <div className="mb-12">
          <h1 className="text-h1 text-primary mb-2">Create New Experiment</h1>
          <p className="text-body-lg text-secondary">
            Set up your research environment by defining project details and choosing your dataset(s).
          </p>
        </div>

        <div className="space-y-section-gap">
          <ExperimentDetailsForm
            name={name}
            description={description}
            onChange={handleFormChange}
          />

          <DatasetSelectTable
            pairs={pairs}
            selectedIds={selectedIds}
            onToggle={handleToggle}
            isLoading={loadingPairs}
            error={pairsError}
          />
        </div>

        <div className="mt-8 flex items-center gap-3">
          <input
            id="randomize-order"
            type="checkbox"
            checked={randomizeOrder}
            onChange={(e) => setRandomizeOrder(e.target.checked)}
            className="w-4 h-4 accent-primary cursor-pointer"
          />
          <label htmlFor="randomize-order" className="text-body-sm text-on-surface cursor-pointer select-none">
            Randomize question order for each participant
          </label>
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
            {isSubmitting ? "Saving…" : "Next"}
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
