"use client";

const SaveResultModal = ({ success, errorMessage, onClose }) => {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-sm mx-4 flex flex-col items-center gap-4">
        {success ? (
          <>
            <span className="material-symbols-outlined text-5xl text-primary">
              check_circle
            </span>
            <h2 className="text-h2 text-on-surface">Upload Successful</h2>
            <p className="text-body-sm text-on-surface-variant text-center">
              Dataset saved. Graph generation is running in the background — allow ~30 seconds before publishing an experiment using this dataset.
            </p>
          </>
        ) : (
          <>
            <span className="material-symbols-outlined text-5xl text-error">
              error
            </span>
            <h2 className="text-h2 text-on-surface">Save Failed</h2>
            <p className="text-body-sm text-on-surface-variant text-center">
              {errorMessage || "An unexpected error occurred. Please try again."}
            </p>
          </>
        )}
        <button
          type="button"
          onClick={onClose}
          className="mt-2 text-button bg-primary text-on-primary px-8 py-2.5 rounded-lg hover:opacity-90 transition-all active:scale-95"
        >
          Close
        </button>
      </div>
    </div>
  );
};

export default SaveResultModal;
