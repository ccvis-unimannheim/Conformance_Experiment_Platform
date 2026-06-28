"use client";

import React, { useState, useEffect, useRef } from "react";
import {
  TransformWrapper,
  TransformComponent,
  useControls,
} from "react-zoom-pan-pinch";

const LOUPE_R = 80;
const MAGNIFY = 2.5;

const btnStyle = {
  background: "none", border: "none", cursor: "pointer",
  fontSize: "16px", fontWeight: 700, color: "#3c5f90",
  padding: "2px 6px", borderRadius: "4px", lineHeight: 1,
};

function ZoomControls({ scale }) {
  const { zoomIn, zoomOut, resetTransform } = useControls();
  return (
    <div style={{
      position: "absolute", bottom: "12px", right: "12px",
      display: "flex", alignItems: "center", gap: "4px",
      background: "white", borderRadius: "8px",
      boxShadow: "0 2px 8px rgba(0,0,0,0.12)",
      padding: "4px 8px", zIndex: 10,
    }}>
      <button onClick={zoomIn} style={btnStyle} title="Zoom in" aria-label="Zoom in">+</button>
      <span style={{ fontSize: "12px", fontWeight: 600, color: "#374151", minWidth: "38px", textAlign: "center" }}>
        {Math.round(scale * 100)}%
      </span>
      <button onClick={zoomOut} style={btnStyle} title="Zoom out" aria-label="Zoom out">−</button>
      <button onClick={resetTransform} style={{ ...btnStyle, fontSize: "14px" }} title="Reset zoom" aria-label="Reset zoom">↺</button>
    </div>
  );
}

const TaskVisualizationPanel = ({ svgUrl, taskNumber = 1, loadingSvg = false }) => {
  const [imgError, setImgError] = useState(false);
  const [loupeOn,  setLoupeOn]  = useState(false);
  const [loupe,    setLoupe]    = useState({ x: 0, y: 0, relX: 0, relY: 0, w: 0, h: 0 });
  const [scale,    setScale]    = useState(1);

  const imgRef = useRef(null);

  useEffect(() => { setImgError(false); }, [svgUrl]);

  const showPlaceholder = !svgUrl || imgError;
  const showLoupe = loupeOn && !showPlaceholder && !loadingSvg;

  function handleMouseMove(e) {
    if (!imgRef.current) return;
    // Always get a fresh rect — stale cache gives wrong coords after zoom/pan
    const rect = imgRef.current.getBoundingClientRect();
    if (!rect.width) return;
    const relX = Math.max(0, Math.min(e.clientX - rect.left, rect.width));
    const relY = Math.max(0, Math.min(e.clientY - rect.top,  rect.height));
    setLoupe({ x: e.clientX, y: e.clientY, relX, relY, w: rect.width, h: rect.height });
  }

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
          <div style={{
            height: "calc(100vh - 12rem)", minHeight: "460px",
            display: "flex", alignItems: "center", justifyContent: "center",
            position: "relative",
          }}>
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
              <TransformWrapper
                initialScale={1}
                minScale={0.5}
                maxScale={6}
                wheel={{ step: 0.1 }}
                doubleClick={{ mode: "zoomIn" }}
                onZoomStop={(ref) => setScale(ref.state.scale)}
                onPanningStop={(ref) => setScale(ref.state.scale)}
                onPanningStart={() => setLoupeOn(false)}
              >
                <div style={{ position: "relative", width: "100%", height: "100%" }}>
                  <TransformComponent
                    wrapperStyle={{ width: "100%", height: "100%" }}
                    contentStyle={{ width: "100%", height: "100%", display: "flex", alignItems: "center", justifyContent: "center" }}
                  >
                    <img
                      ref={imgRef}
                      src={svgUrl}
                      alt={`Task ${taskNumber} visualization`}
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
                  </TransformComponent>
                  <ZoomControls scale={scale} />
                </div>
              </TransformWrapper>
            )}
          </div>
        </div>
      </section>

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
            boxShadow: "0 8px 32px rgba(60,95,144,0.25)",
            pointerEvents: "none",
            zIndex: 1000,
            backgroundImage: `url("${svgUrl}")`,
            backgroundSize: `${(loupe.w || 0) * MAGNIFY}px ${(loupe.h || 0) * MAGNIFY}px`,
            backgroundPosition: `${LOUPE_R - loupe.relX * MAGNIFY}px ${LOUPE_R - loupe.relY * MAGNIFY}px`,
            backgroundRepeat: "no-repeat",
            backgroundColor: "white",
          }}
        />
      )}
    </>
  );
};

export default TaskVisualizationPanel;
