"use client";

import React, { useState, useEffect, useCallback } from "react";

const TaskVisualizationPanel = ({ svgUrl, taskNumber = 1, loadingSvg = false }) => {
  const [imgError, setImgError]   = useState(false);
  const [modalOpen, setModalOpen] = useState(false);

  useEffect(() => { setImgError(false); }, [svgUrl]);

  const openModal  = () => setModalOpen(true);
  const closeModal = useCallback(() => setModalOpen(false), []);

  // Lock body scroll when modal open; Escape to close
  useEffect(() => {
    if (!modalOpen) return;
    document.body.style.overflow = "hidden";
    const onKey = (e) => { if (e.key === "Escape") closeModal(); };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("keydown", onKey);
    };
  }, [modalOpen, closeModal]);

  const showPlaceholder = !svgUrl || imgError;

  return (
    <>
      <section>
        <div style={{
          backgroundColor: "white",
          borderRadius: "0.75rem",
          padding: "2rem",
          boxShadow: "0 12px 32px rgba(45,52,53,0.04)",
          border: "1px solid #f0f0f0",
          position: "relative",
        }}>
          {/* Enlarge button — only when SVG loaded */}
          {!showPlaceholder && !loadingSvg && (
            <button
              onClick={openModal}
              title="Enlarge visualization"
              style={{
                position: "absolute", top: "1rem", right: "1rem",
                display: "flex", alignItems: "center", gap: "0.35rem",
                padding: "0.35rem 0.75rem",
                background: "white",
                border: "1.5px solid #dde4e5",
                borderRadius: "6px",
                fontSize: "0.75rem", fontWeight: 600, color: "#5a6061",
                cursor: "pointer",
                boxShadow: "0 2px 6px rgba(45,52,53,0.08)",
                zIndex: 2,
                transition: "border-color 0.15s, color 0.15s",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.borderColor = "#3c5f90"; e.currentTarget.style.color = "#3c5f90"; }}
              onMouseLeave={(e) => { e.currentTarget.style.borderColor = "#dde4e5"; e.currentTarget.style.color = "#5a6061"; }}
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="15 3 21 3 21 9" /><polyline points="9 21 3 21 3 15" />
                <line x1="21" y1="3" x2="14" y2="10" /><line x1="3" y1="21" x2="10" y2="14" />
              </svg>
              Enlarge
            </button>
          )}

          {/* Visualization area */}
          <div style={{ height: "calc(100vh - 12rem)", minHeight: "460px", display: "flex", alignItems: "center", justifyContent: "center" }}>
            {loadingSvg ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
                <div style={{
                  width: "2.5rem", height: "2.5rem", borderRadius: "50%",
                  border: "3px solid #ebeeef", borderTopColor: "#3c5f90",
                  animation: "spin 0.8s linear infinite"
                }} />
                <span style={{ fontSize: "0.75rem", color: "#9ca3af", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase" }}>
                  Loading chart…
                </span>
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
              </div>
            ) : showPlaceholder ? (
              <div style={{
                width: "100%", height: "100%",
                backgroundColor: "#fafbfc",
                borderRadius: "0.5rem",
                border: "2px dashed #dde4e5",
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem"
              }}>
                <div style={{ display: "flex", alignItems: "flex-end", gap: "6px", height: "60px" }}>
                  {[55, 85, 40, 70, 30, 90, 50].map((h, i) => (
                    <div key={i} style={{
                      width: "20px", height: `${h}%`,
                      backgroundColor: i % 2 === 0 ? "rgba(76,175,80,0.35)" : "rgba(244,67,54,0.35)",
                      borderRadius: "3px 3px 0 0",
                    }} />
                  ))}
                </div>
                <span style={{ fontSize: "0.8rem", color: "#adb3b4", fontWeight: 700, letterSpacing: "0.12em", textTransform: "uppercase" }}>
                  Visualization placeholder
                </span>
                <span style={{ fontSize: "0.7rem", color: "#c8cecc", textAlign: "center", maxWidth: "16rem" }}>
                  The chart will be loaded from the database when the backend is connected
                </span>
              </div>
            ) : (
              <img
                src={svgUrl}
                alt={`Task ${taskNumber} visualization`}
                onError={() => setImgError(true)}
                onClick={openModal}
                style={{ maxWidth: "100%", maxHeight: "calc(100vh - 12rem)", objectFit: "contain", cursor: "zoom-in" }}
              />
            )}
          </div>
        </div>
      </section>

      {/* Modal lightbox */}
      {modalOpen && (
        <div
          onClick={closeModal}
          style={{
            position: "fixed", inset: 0, zIndex: 1000,
            backgroundColor: "rgba(0,0,0,0.82)",
            display: "flex", alignItems: "center", justifyContent: "center",
            animation: "fadeIn 0.15s ease",
          }}
        >
          <style>{`
            @keyframes fadeIn  { from { opacity: 0; } to { opacity: 1; } }
            @keyframes scaleIn { from { transform: scale(0.95); opacity: 0; } to { transform: scale(1); opacity: 1; } }
          `}</style>

          {/* Close button */}
          <button
            onClick={closeModal}
            title="Close (Esc)"
            style={{
              position: "fixed", top: "1.25rem", right: "1.25rem",
              width: "2.5rem", height: "2.5rem",
              background: "rgba(255,255,255,0.12)",
              border: "1.5px solid rgba(255,255,255,0.25)",
              borderRadius: "50%",
              color: "white", fontSize: "1.1rem", fontWeight: 700,
              cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
              transition: "background 0.15s",
              zIndex: 1001,
            }}
            onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.25)"; }}
            onMouseLeave={(e) => { e.currentTarget.style.background = "rgba(255,255,255,0.12)"; }}
          >
            ×
          </button>

          {/* SVG image — stop propagation so clicking image doesn't close */}
          <img
            src={svgUrl}
            alt={`Task ${taskNumber} visualization (enlarged)`}
            onClick={(e) => e.stopPropagation()}
            style={{
              width: "92vw", height: "92vh",
              objectFit: "contain",
              borderRadius: "0.5rem",
              boxShadow: "0 24px 64px rgba(0,0,0,0.5)",
              animation: "scaleIn 0.15s ease",
              cursor: "default",
            }}
          />
        </div>
      )}
    </>
  );
};

export default TaskVisualizationPanel;
