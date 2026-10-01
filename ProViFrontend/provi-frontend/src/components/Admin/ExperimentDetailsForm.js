"use client";

const ExperimentDetailsForm = ({ name, description, onChange }) => {
  return (
    <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
      <h2 className="text-h2 text-primary mb-6">Experiment Details</h2>
      <div className="space-y-6">
        <div>
          <label
            htmlFor="exp-name"
            className="block text-label-caps text-on-surface-variant mb-2"
          >
            EXPERIMENT NAME
          </label>
          <input
            id="exp-name"
            type="text"
            value={name}
            onChange={(e) => onChange("name", e.target.value)}
            placeholder="Enter experiment name..."
            className="w-full bg-white border border-outline-variant rounded-lg px-4 py-3 focus:border-primary focus:ring-1 focus:ring-primary transition-all text-body-sm outline-none"
          />
        </div>
        <div>
          <label
            htmlFor="exp-desc"
            className="block text-label-caps text-on-surface-variant mb-2"
          >
            DESCRIPTION <span className="text-secondary normal-case font-normal">(optional)</span>
          </label>
          <textarea
            id="exp-desc"
            value={description}
            onChange={(e) => onChange("description", e.target.value)}
            placeholder="Enter an optional description for your experiment..."
            rows={4}
            className="w-full bg-white border border-outline-variant rounded-lg px-4 py-3 focus:border-primary focus:ring-1 focus:ring-primary transition-all text-body-sm outline-none resize-none"
          />
        </div>
      </div>
    </section>
  );
};

export default ExperimentDetailsForm;
