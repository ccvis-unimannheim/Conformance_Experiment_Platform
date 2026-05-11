"use client";

const DatasetSelectTable = ({ pairs, selectedIds, onToggle, isLoading, error }) => {
  if (isLoading) {
    return (
      <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
        <h2 className="text-h2 text-primary mb-6">Choose Dataset(s)</h2>
        <p className="text-body-sm text-secondary">Loading datasets…</p>
      </section>
    );
  }

  if (error) {
    return (
      <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
        <h2 className="text-h2 text-primary mb-6">Choose Dataset(s)</h2>
        <p className="text-body-sm text-error">{error}</p>
      </section>
    );
  }

  return (
    <section className="bg-surface-container-lowest p-gutter rounded-xl border border-outline-variant">
      <div className="flex items-baseline justify-between mb-6">
        <h2 className="text-h2 text-primary">Choose Dataset(s)</h2>
        {selectedIds.size > 0 && (
          <span className="text-label-caps text-primary">
            Selected: {selectedIds.size}
          </span>
        )}
      </div>

      {pairs.length === 0 ? (
        <p className="text-body-sm text-secondary">
          No datasets uploaded yet. Upload a dataset pair from the{" "}
          <a href="/admin" className="text-primary underline">
            admin home
          </a>
          .
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-outline-variant">
                <th className="py-4 px-2 w-10" />
                <th className="py-4 px-4 text-label-caps text-on-surface-variant">
                  DATASET NAME
                </th>
                <th className="py-4 px-4 text-label-caps text-on-surface-variant">
                  EVENT LOG
                </th>
                <th className="py-4 px-4 text-label-caps text-on-surface-variant">
                  PROCESS GUIDELINE
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/30">
              {pairs.map((pair) => {
                const checked = selectedIds.has(pair.dataset_id);
                return (
                  <tr
                    key={pair.dataset_id}
                    onClick={() => onToggle(pair.dataset_id)}
                    className={`hover:bg-surface-container-low transition-colors cursor-pointer ${
                      checked ? "bg-primary/5" : ""
                    }`}
                  >
                    <td className="py-5 px-2">
                      <input
                        type="checkbox"
                        checked={checked}
                        onChange={() => onToggle(pair.dataset_id)}
                        onClick={(e) => e.stopPropagation()}
                        className="w-4 h-4 text-primary focus:ring-primary border-outline-variant cursor-pointer rounded"
                      />
                    </td>
                    <td className="py-5 px-4">
                      <span className="text-[15px] font-semibold text-on-surface">
                        {pair.dataset_title}
                      </span>
                    </td>
                    <td className="py-5 px-4">
                      <div className="flex flex-col">
                        <span className="text-body-sm text-on-surface truncate max-w-[150px]">
                          {pair.log?.filename ?? "—"}
                        </span>
                        <span className="text-[11px] text-on-surface-variant">
                          Uploaded: {pair.insert_datetime ? new Date(pair.insert_datetime).toLocaleDateString() : "—"}
                        </span>
                      </div>
                    </td>
                    <td className="py-5 px-4">
                      <div className="flex flex-col">
                        <span className="text-body-sm text-on-surface truncate max-w-[150px]">
                          {pair.guideline?.filename ?? "—"}
                        </span>
                        <span className="text-[11px] text-on-surface-variant">
                          Uploaded: {pair.insert_datetime ? new Date(pair.insert_datetime).toLocaleDateString() : "—"}
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
  );
};

export default DatasetSelectTable;
