"use client";

import React, { useState } from "react";
import Image from "next/image";
import Link from "next/link";

import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";

const C = {
  primary:       "#00305e",
  primaryDim:    "#002345",
  surface:       "#f9f9f9",
  containerLow:  "#f2f4f4",
  container:     "#ebeeef",
  containerHigh: "#e4e9ea",
  onSurface:     "#2d3435",
  onVariant:     "#5a6061",
  outline:       "#757c7d",
  outlineVar:    "#adb3b4",
  white:         "#ffffff",
};

const DIFFICULTY_LABELS = ["Very Easy", "Easy", "Neutral", "Difficult", "Very Difficult"];

export default function EndPage() {
  const [difficulty, setDifficulty] = useState(null);
  const [finished, setFinished] = useState(false);
  const [closeFailed, setCloseFailed] = useState(false);

  const canFinish = difficulty !== null;

  const handleFinish = async () => {
    if (!canFinish) return;
    setFinished(true);
    try {
      await fetch("/api/auth/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ difficulty }),
      });
    } catch {
      // best-effort; don't block window.close on network error
    }
    window.close();
    setTimeout(() => setCloseFailed(true), 400);
  };

  return (
    <div style={{ backgroundColor: C.surface, color: C.onSurface, minHeight: "100vh", fontFamily: "'Inter', Arial, sans-serif" }}>

      {/* ── Top Nav */}
      <header style={{
        position: "fixed", top: 0, left: 0, width: "100%", zIndex: 50,
        backgroundColor: C.white,
        borderBottom: `1px solid ${C.containerHigh}`,
        height: "4rem",
        display: "flex", alignItems: "center", padding: "0 2rem",
        boxSizing: "border-box",
      }}>
        <div style={{
          maxWidth: "56rem", margin: "0 auto", width: "100%",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Image priority src={ProjectLogo} width={90} height={36} alt="ProVi Logo" style={{ objectFit: "contain" }} />
            <Image priority src={UniLogo} width={140} height={36} alt="University of Mannheim Logo" style={{ objectFit: "contain" }} />
          </div>
          <div />
        </div>
      </header>

      {/* ── Main */}
      <main style={{
        paddingTop: "6rem", paddingBottom: "8rem", minHeight: "100vh",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: "6rem 1.5rem 8rem",
        boxSizing: "border-box",
      }}>
        <div style={{ maxWidth: "40rem", width: "100%", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center" }}>

          {/* Check icon */}
          <div style={{
            width: "6rem", height: "6rem", borderRadius: "1rem",
            backgroundColor: C.primary,
            boxShadow: "0 0 20px rgba(34,197,94,0.4)",
            display: "flex", alignItems: "center", justifyContent: "center",
            marginBottom: "2rem",
          }}>
            <span
              className="material-symbols-outlined"
              style={{ color: C.white, fontSize: "3rem", fontVariationSettings: "'FILL' 1" }}
            >
              check_circle
            </span>
          </div>

          {/* Title */}
          <h1 style={{
            fontFamily: "'Work Sans', 'Inter', sans-serif",
            fontSize: "2.5rem", fontWeight: 800, color: C.primary,
            letterSpacing: "-0.02em", lineHeight: 1.15,
            marginBottom: "1.5rem", textAlign: "center",
          }}>
            Thank You for Your<br />Contribution
          </h1>

          {/* Body text */}
          <p style={{
            fontSize: "1.0625rem", color: C.onSurface, lineHeight: 1.7,
            maxWidth: "32rem", marginBottom: "2.5rem",
          }}>
            Your participation is now complete. Your responses have been saved and will contribute to our research.
          </p>

          {/* Difficulty rating */}
          <div style={{ width: "100%", maxWidth: "32rem", marginBottom: "2rem" }}>
            <p style={{
              fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.12em", color: C.onVariant, marginBottom: "1rem",
            }}>
              HOW DIFFICULT WERE THE TASKS?
            </p>
            <div style={{ display: "flex", gap: "6px", width: "100%" }}>
              {DIFFICULTY_LABELS.map((label) => {
                const selected = difficulty === label;
                return (
                  <button
                    key={label}
                    onClick={() => setDifficulty(label)}
                    style={{
                      flex: 1,
                      height: "2.25rem",
                      borderRadius: "0.625rem",
                      border: selected ? "2px solid #3D4F7C" : "1px solid #e2e8f0",
                      backgroundColor: selected ? "#EEF2FF" : C.white,
                      color: selected ? "#3D4F7C" : "#64748b",
                      fontSize: "0.6875rem",
                      fontWeight: selected ? 700 : 500,
                      cursor: "pointer",
                      transform: selected ? "scale(1.03)" : "scale(1)",
                      transition: "all 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      if (!selected) {
                        e.currentTarget.style.backgroundColor = "#F5F7FF";
                        e.currentTarget.style.borderColor = "#3D4F7C";
                      }
                    }}
                    onMouseLeave={(e) => {
                      if (!selected) {
                        e.currentTarget.style.backgroundColor = C.white;
                        e.currentTarget.style.borderColor = "#e2e8f0";
                      }
                    }}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Finish button */}
          <button
            onClick={handleFinish}
            disabled={!canFinish || finished}
            style={{
              backgroundColor: C.primary,
              opacity: canFinish ? 1 : 0.4,
              cursor: canFinish && !finished ? "pointer" : "not-allowed",
              color: C.white,
              fontFamily: "'Work Sans', 'Inter', sans-serif",
              fontWeight: 700,
              fontSize: "1.125rem",
              padding: "1rem 2rem",
              borderRadius: "0.375rem",
              display: "flex", alignItems: "center", gap: "0.75rem",
              border: "none",
              boxShadow: canFinish ? "0 2px 8px rgba(0,48,94,0.25)" : "none",
              transition: "all 0.15s ease",
              marginBottom: closeFailed ? "1rem" : "4rem",
            }}
            onMouseEnter={(e) => { if (canFinish && !finished) e.currentTarget.style.backgroundColor = "#00254a"; }}
            onMouseLeave={(e) => { if (canFinish && !finished) e.currentTarget.style.backgroundColor = C.primary; }}
          >
            <span>{finished ? "Thank you!" : "Finish and Exit"}</span>
            <span className="material-symbols-outlined" style={{ fontSize: "1.25rem" }}>logout</span>
          </button>

          {closeFailed && (
            <p style={{
              fontSize: "0.8125rem", color: C.onVariant, marginBottom: "3rem",
              textAlign: "center",
            }}>
              You may now close this tab.
            </p>
          )}

          {/* Support section */}
          <div style={{
            width: "100%", maxWidth: "32rem",
            borderTop: `1px solid ${C.containerHigh}`,
            paddingTop: "2.5rem",
            display: "flex", flexDirection: "column", alignItems: "center", gap: "0.25rem",
          }}>
            <p style={{
              fontSize: "0.75rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.12em", color: C.onVariant, marginBottom: "0.5rem",
            }}>
              Support
            </p>
            <p style={{ fontSize: "0.875rem", color: C.onVariant, marginBottom: "0.25rem" }}>
              Questions regarding your participation?
            </p>
            <a
              href="mailto:impressum@uni-mannheim.de"
              style={{
                fontSize: "0.875rem", fontWeight: 600, color: C.primary,
                textDecoration: "none",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.textDecoration = "underline"; }}
              onMouseLeave={(e) => { e.currentTarget.style.textDecoration = "none"; }}
            >
              impressum@uni-mannheim.de
            </a>
          </div>

        </div>
      </main>

      {/* ── Sticky Footer */}
      <footer style={{
        position: "fixed", bottom: 0, left: 0, width: "100%",
        padding: "0.75rem 2rem",
        backgroundColor: "rgba(255,255,255,0.85)",
        backdropFilter: "blur(8px)",
        borderTop: `1px solid ${C.containerHigh}`,
        zIndex: 40,
        boxSizing: "border-box",
      }}>
        <div style={{
          maxWidth: "56rem", margin: "0 auto",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ fontSize: "10px", color: C.onVariant, textTransform: "uppercase", letterSpacing: "0.15em", fontWeight: 500 }}>
            © University of Mannheim
          </span>
          <div style={{ display: "flex", gap: "1.5rem" }}>
            {[
              { label: "Imprint",                     href: "/imprint" },
              { label: "Legal",                        href: "/imprint" },
              { label: "Data Protection Declaration",  href: "/dataprotection" },
            ].map(({ label, href }) => (
              <Link key={label} href={href} style={{
                fontSize: "10px", color: C.onVariant,
                textTransform: "uppercase", letterSpacing: "0.15em", fontWeight: 500,
                textDecoration: "none", transition: "color 0.15s ease",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.color = C.primary; }}
              onMouseLeave={(e) => { e.currentTarget.style.color = C.onVariant; }}
              >
                {label}
              </Link>
            ))}
          </div>
        </div>
      </footer>
    </div>
  );
}
