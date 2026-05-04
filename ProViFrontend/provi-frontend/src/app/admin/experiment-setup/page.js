"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import ExperimentSetupHeader from "../../../components/Admin/ExperimentSetupHeader";
import Toast from "../../../components/Admin/Toast";

const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:1234/api";

export default function ExperimentSetupPage() {
  const router = useRouter();

  const [expName, setExpName] = useState("");
  const [expDesc, setExpDesc] = useState("");
  const [datasets, setDatasets] = useState([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState(null);
  const [loadError, setLoadError] = useState(null);

  const [toast, setToast] = useState({ visible: false, message: "", isError: false });
  const showToast = (message, isError = false) =>
    setToast({ visible: true, message, isError });
  const hideToast = () => setToast((t) => ({ ...t, visible: false }));

  useEffect(() => {
    fetchDatasets();
  }, []);

  async function fetchDatasets() {
    try {
      const res = await fetch(`${BASE_URL}/admin/datasets`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setDatasets(data);
      if (data.length > 0) setSelectedDatasetId(data[0].dataset_id ?? data[0]._id ?? null);
    } catch (e) {
      setLoadError(e.message);
    }
  }

  function handleNext() {
    if (!expName.trim()) {
      showToast("Please enter an experiment name before continuing.", true);
      return;
    }
    const params = new URLSearchParams({
      name: expName.trim(),
      ...(expDesc.trim() && { desc: expDesc.trim() }),
      ...(selectedDatasetId && { dataset_id: selectedDatasetId }),
    });
    router.push(`/admin/task-selection?${params.toString()}`);
  }

  return (
    <div className="bg-surface text-on-surface min-h-screen flex flex-col antialiased">
      <ExperimentSetupHeader />

      <main className="flex-grow max-w-[900px] mx-auto w-full px-6 py-12 pb-32">
        {/* Main Heading */}
        <div className="mb-12">
          <h1 className="font-h1 text-h1 text-primary mb-2">Create New Experiment</h1>
          <p className="font-body-lg text-body-lg text-secondary">
            Set up your research environment by defining project details and choosing your dataset.
          </p>
        </div>

        <div className="space-y-12">
          {/* Basic Information Section */}
          <section className="bg-white p-6 rounded-xl border border-outline-variant">
            <h2 className="text-2xl font-semibold text-primary mb-6">Experiment Details</h2>
            <div className="space-y-6">
              <div>
                <label
                  htmlFor="exp-name"
                  className="block text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-2"
                >
                  Experiment Name
                </label>
                <input
                  id="exp-name"
                  type="text"
                  value={expName}
                  onChange={(e) => setExpName(e.target.value)}
                  placeholder="Enter experiment name..."
                  className="w-full bg-white border border-outline-variant rounded-lg px-4 py-3 focus:border-primary focus:ring-1 focus:ring-primary transition-all text-sm outline-none"
                />
              </div>
              <div>
                <label
                  htmlFor="exp-desc"
                  className="block text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-2"
                >
                  Description
                </label>
                <textarea
                  id="exp-desc"
                  rows={4}
                  value={expDesc}
                  onChange={(e) => setExpDesc(e.target.value)}
                  placeholder="Enter an optional description for your experiment..."
                  className="w-full bg-white border border-outline-variant rounded-lg px-4 py-3 focus:border-primary focus:ring-1 focus:ring-primary transition-all text-sm outline-none resize-none"
                />
              </div>
            </div>
          </section>

          {/* Dataset Selection Section */}
          <section className="bg-white p-6 rounded-xl border border-outline-variant">
            <h2 className="text-2xl font-semibold text-primary mb-6">Choose Dataset</h2>
            {loadError ? (
              <div className="text-sm text-error bg-error-container px-4 py-3 rounded-lg">
                Could not load datasets from backend (<strong>{BASE_URL}</strong>).
                <br />
                <span className="text-xs opacity-70">{loadError}</span>
              </div>
            ) : datasets.length === 0 ? (
              <div className="text-center text-on-surface-variant text-sm py-10 border-2 border-dashed border-outline-variant rounded-lg">
                <span className="material-symbols-outlined text-3xl block mb-2 text-outline-variant">
                  inbox
                </span>
                No datasets available. Upload a dataset first.
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left border-collapse">
                  <thead>
                    <tr className="border-b border-outline-variant">
                      <th className="py-4 px-2 w-10"></th>
                      <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                        Dataset Name
                      </th>
                      <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                        Event Log
                      </th>
                      <th className="py-4 px-4 text-xs font-bold uppercase tracking-wider text-on-surface-variant">
                        Process Guideline
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-outline-variant/30">
                    {datasets.map((ds) => {
                      const dsId = ds.dataset_id ?? ds._id;
                      return (
                        <tr
                          key={dsId}
                          onClick={() => setSelectedDatasetId(dsId)}
                          className="hover:bg-surface-container-low transition-colors cursor-pointer"
                        >
                          <td className="py-5 px-2">
                            <input
                              type="radio"
                              name="dataset-selection"
                              checked={selectedDatasetId === dsId}
                              onChange={() => setSelectedDatasetId(dsId)}
                              className="w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer"
                            />
                          </td>
                          <td className="py-5 px-4">
                            <div className="text-[15px] font-semibold text-on-surface">
                              {ds.dataset_title || ds.name || dsId}
                            </div>
                          </td>
                          <td className="py-5 px-4">
                            <div className="flex flex-col">
                              <span className="text-sm text-on-surface truncate max-w-[150px]">
                                {ds.event_log || ds.location || "—"}
                              </span>
                            </div>
                          </td>
                          <td className="py-5 px-4">
                            <div className="flex flex-col">
                              <span className="text-sm text-on-surface truncate max-w-[150px]">
                                {ds.process_guideline || "—"}
                              </span>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </div>

        {/* Primary Action */}
        <div className="mt-12 flex justify-end">
          <button
            onClick={handleNext}
            className="flex items-center gap-2 font-button text-button bg-primary text-on-primary px-12 py-3 rounded-lg hover:opacity-90 transition-all active:scale-95"
          >
            Next
            <span className="material-symbols-outlined text-sm">chevron_right</span>
          </button>
        </div>
      </main>

      {/* Decorative background elements */}
      <div className="fixed top-24 -right-24 w-96 h-96 bg-primary/5 rounded-full blur-3xl -z-10" />
      <div className="fixed bottom-24 -left-24 w-96 h-96 bg-[#5b5f62]/5 rounded-full blur-3xl -z-10" />

      <Toast
        message={toast.message}
        isError={toast.isError}
        visible={toast.visible}
        onHide={hideToast}
      />
    </div>
  );
}
