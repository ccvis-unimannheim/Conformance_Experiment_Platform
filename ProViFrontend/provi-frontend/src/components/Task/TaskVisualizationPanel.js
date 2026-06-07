"use client";

import React, { useState } from "react";

const TaskVisualizationPanel = ({ svgUrl, taskNumber = 1, loadingSvg = false }) => {
  const [imgError, setImgError] = useState(false);

  // Reset img error when svgUrl changes
  React.useEffect(() => { setImgError(false); }, [svgUrl]);

  const showPlaceholder = !svgUrl || imgError;

  return (
    <section style={{ gridColumn: "1 / span 9" }}>
      <div style={{
        backgroundColor: "white",
        borderRadius: "0.75rem",
        padding: "2.5rem",
        boxShadow: "0 12px 32px rgba(45,52,53,0.04)",
        border: "1px solid #f0f0f0"
      }}>
        {/* Visualization area */}
        <div style={{ height: "520px", display: "flex", alignItems: "center", justifyContent: "center" }}>
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
            /* Dashed placeholder when no SVG available */
            <div style={{
              width: "100%", height: "100%",
              backgroundColor: "#fafbfc",
              borderRadius: "0.5rem",
              border: "2px dashed #dde4e5",
              display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem"
            }}>
              {/* Mini bar chart icon */}
              <div style={{ display: "flex", alignItems: "flex-end", gap: "6px", height: "60px" }}>
                {[55, 85, 40, 70, 30, 90, 50].map((h, i) => (
                  <div key={i} style={{
                    width: "20px",
                    height: `${h}%`,
                    backgroundColor: i % 2 === 0 ? "rgba(76,175,80,0.35)" : "rgba(244,67,54,0.35)",
                    borderRadius: "3px 3px 0 0",
                    transition: "height 0.3s ease"
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
              style={{ maxWidth: "100%", maxHeight: "520px", objectFit: "contain" }}
            />
          )}
        </div>
      </div>
    </section>
  );
};

export default TaskVisualizationPanel;