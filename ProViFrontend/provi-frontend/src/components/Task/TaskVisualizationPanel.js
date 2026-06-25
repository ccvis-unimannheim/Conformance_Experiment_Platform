"use client";

import React, { useState, useEffect, useRef } from "react";

const LOUPE_R = 80;
const MAGNIFY = 2.5;

const TaskVisualizationPanel = ({ svgUrl, taskNumber = 1, loadingSvg = false }) => {
  const [imgError, setImgError] = useState(false);
  const [loupeOn,  setLoupeOn]  = useState(false);
  const [loupe,    setLoupe]    = useState({ x: 0, y: 0, relX: 0, relY: 0 });

  const imgRef  = useRef(null);
  const rectRef = useRef(null); // cached bounding rect — updated on load + resize

  useEffect(() => { setImgError(false); }, [svgUrl]);

  // Cache rect on mount and window resize
  useEffect(() => {
    function updateRect() {
      if (imgRef.current) rectRef.current = imgRef.current.getBoundingClientRect();
    }
    updateRect();
    window.addEventListener("resize", updateRect);
    return () => window.removeEventListener("resize", updateRect);
  }, [svgUrl]); // re-run when svgUrl changes (new img loaded)

  const showPlaceholder = !svgUrl || imgError;
  const showLoupe = loupeOn && !showPlaceholder && !loadingSvg;

  function handleMouseMove(e) {
    const rect = rectRef.current;
    if (!rect) return;
    const relX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const relY = Math.max(0, Math.min(e.clientY - rect.top,  rect.height));
    setLoupe({ x: e.clientX, y: e.clientY, relX, relY });
  }

  // Cache rect when img finishes loading
  function handleImgLoad() {
    if (imgRef.current) rectRef.current = imgRef.current.getBoundingClientRect();
  }

  // Derived loupe img dimensions from cached rect
  const loupeSrcW = rectRef.current ? rectRef.current.width  * MAGNIFY : 0;
  const loupeSrcH = rectRef.current ? rectRef.current.height * MAGNIFY : 0;

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
          {/* Visualization area */}
          <div style={{ height: "calc(100vh - 12rem)", minHeight: "460px", display: "flex", alignItems: "center", justifyContent: "center" }}>
            {loadingSvg ? (
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "1rem" }}>
                <div style={{
                  width: "2.5rem", height: "2.5rem", borderRadius: "50%",
                  border: "3px solid #ebeeef", borderTopColor: "#3c5f90",
                  animation: "spin 0.8s linear infinite",
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
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: "1rem",
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
              // Mouse handlers on <img> directly — avoids loupe misfiring in container padding
              <img
                ref={imgRef}
                src={svgUrl}
                alt={`Task ${taskNumber} visualization`}
                onLoad={handleImgLoad}
                onError={() => setImgError(true)}
                onMouseEnter={() => setLoupeOn(true)}
                onMouseLeave={() => setLoupeOn(false)}
                onMouseMove={handleMouseMove}
                style={{
                  maxWidth: "100%", maxHeight: "calc(100vh - 12rem)",
                  objectFit: "contain",
                  cursor: "crosshair",
                  display: "block",
                }}
              />
            )}
          </div>
        </div>
      </section>

      {/* Magnifier loupe — fixed overlay, pointer-events disabled */}
      {showLoupe && (
        <div
          style={{
            position: "fixed",
            left: loupe.x - LOUPE_R,
            top:  loupe.y - LOUPE_R,
            width:  LOUPE_R * 2,
            height: LOUPE_R * 2,
            borderRadius: "50%",
            border: "2.5px solid #3c5f90",
            boxShadow: "0 8px 32px rgba(60,95,144,0.25), inset 0 0 0 1px rgba(255,255,255,0.5)",
            overflow: "hidden",
            pointerEvents: "none",
            zIndex: 1000,
            background: "white",
          }}
        >
          <img
            src={svgUrl}
            alt=""
            style={{
              position: "absolute",
              width:  loupeSrcW,
              height: loupeSrcH,
              left:   LOUPE_R - loupe.relX * MAGNIFY,
              top:    LOUPE_R - loupe.relY * MAGNIFY,
              pointerEvents: "none",
            }}
          />
        </div>
      )}
    </>
  );
};

export default TaskVisualizationPanel;
