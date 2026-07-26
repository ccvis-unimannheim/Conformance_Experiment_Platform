"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";

import HeaderLogos from "../../components/General/HeaderLogos";

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

const LIKERT_COLOR = "#00305e";
const LIKERT_BG     = "#e8eef5";

// Each item cites a source instrument; scale adaptations (point count, and for
// NASA-TLX also wording: "the task" -> "the tasks", since this is asked once
// at the end covering the whole multi-task session) are deliberate and should
// be reported as "adapted from" the source in the methods write-up.
// NASA-TLX Likert questions (1–6) temporarily removed from the end page.
// Kept here so they can be restored: move the definitions back into QUESTIONS
// and un-comment the survey render block in the JSX below.
// const QUESTIONS = [
//   {
//     key:    "mentalDemand",
//     label:  "1. How mentally demanding were the tasks?",
//     labels: ["Very low", "Low", "Somewhat low", "Moderate", "Somewhat high", "High", "Very high"],
//   },
//   {
//     key:    "physicalDemand",
//     label:  "2. How physically demanding were the tasks?",
//     labels: ["Very low", "Low", "Somewhat low", "Moderate", "Somewhat high", "High", "Very high"],
//   },
//   {
//     key:    "temporalDemand",
//     label:  "3. How hurried or rushed was the pace of the tasks?",
//     labels: ["Very low", "Low", "Somewhat low", "Moderate", "Somewhat high", "High", "Very high"],
//   },
//   {
//     // NASA-TLX defines Performance in the opposite direction from the other
//     // five subscales (1 = good, not 1 = low) - kept faithful to the source
//     // rather than flipped, since each item shows its own anchor labels.
//     key:    "performance",
//     label:  "4. How successful were you in accomplishing what you were asked to do?",
//     labels: ["Very good", "Good", "Somewhat good", "Moderate", "Somewhat bad", "Bad", "Very bad"],
//   },
//   {
//     key:    "effort",
//     label:  "5. How hard did you have to work to accomplish your level of performance?",
//     labels: ["Very low", "Low", "Somewhat low", "Moderate", "Somewhat high", "High", "Very high"],
//   },
//   {
//     key:    "frustration",
//     label:  "6. How insecure, discouraged, irritated, stressed, and annoyed were you?",
//     labels: ["Very low", "Low", "Somewhat low", "Moderate", "Somewhat high", "High", "Very high"],
//   },
// ];
const QUESTIONS = [];

function LikertQuestion({ question, value, onChange }) {
  return (
    <div style={{ width: "100%", marginBottom: "2rem" }}>
      <p style={{
        fontSize: "0.875rem", fontWeight: 700, color: C.onSurface,
        marginBottom: "0.75rem", textAlign: "left", lineHeight: 1.5,
      }}>
        {question.label}
      </p>

      {/* Scale boxes */}
      <div style={{ display: "flex", gap: "6px", width: "100%" }}>
        {question.labels.map((lbl, i) => {
          const val = i + 1;
          const selected = value === val;
          return (
            <button
              key={val}
              onClick={() => onChange(val)}
              style={{
                flex: 1,
                height: "2.75rem",
                borderRadius: "0.5rem",
                border: selected
                  ? `2px solid ${LIKERT_COLOR}`
                  : "1.5px solid #e2e8f0",
                backgroundColor: selected ? LIKERT_BG : C.white,
                color: selected ? LIKERT_COLOR : "#94a3b8",
                fontSize: "1rem",
                fontWeight: selected ? 800 : 500,
                cursor: "pointer",
                transform: selected ? "translateY(-2px) scale(1.06)" : "none",
                transition: "all 0.12s ease",
                boxShadow: selected ? `0 2px 8px ${LIKERT_COLOR}44` : "none",
              }}
              onMouseEnter={(e) => {
                if (!selected) {
                  e.currentTarget.style.borderColor = LIKERT_COLOR;
                  e.currentTarget.style.color = LIKERT_COLOR;
                  e.currentTarget.style.backgroundColor = LIKERT_BG;
                }
              }}
              onMouseLeave={(e) => {
                if (!selected) {
                  e.currentTarget.style.borderColor = "#e2e8f0";
                  e.currentTarget.style.color = "#94a3b8";
                  e.currentTarget.style.backgroundColor = C.white;
                }
              }}
            >
              {val}
            </button>
          );
        })}
      </div>

      {/* Option labels beneath each box */}
      <div style={{ display: "flex", gap: "6px", width: "100%", marginTop: "0.35rem" }}>
        {question.labels.map((lbl, i) => (
          <div key={i} style={{
            flex: 1, textAlign: "center",
            fontSize: "0.625rem", lineHeight: 1.3,
            color: LIKERT_COLOR, fontWeight: 600,
          }}>
            {lbl}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EndPage() {
  const [ratings,     setRatings]     = useState({});
  const [feedback,    setFeedback]    = useState("");
  const [finished,    setFinished]    = useState(false);
  const [closeFailed, setCloseFailed] = useState(false);

  const canFinish = QUESTIONS.every(q => ratings[q.key] != null);

  useEffect(() => {
    fetch("/api/participant/complete", { method: "POST", credentials: "include" }).catch(() => {});
  }, []);

  const handleFinish = async () => {
    if (!canFinish) return;
    setFinished(true);
    try {
      await fetch("/api/auth/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ ratings, feedback: feedback.trim() || null }),
      });
    } catch {
      // best-effort
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
          <HeaderLogos />
          <div />
        </div>
      </header>

      {/* ── Main */}
      <main style={{
        paddingTop: "6rem", paddingBottom: "8rem", minHeight: "100vh",
        display: "flex", alignItems: "flex-start", justifyContent: "center",
        padding: "6rem 1.5rem 8rem",
        boxSizing: "border-box",
      }}>
        <div style={{ maxWidth: "48rem", width: "100%", textAlign: "center", display: "flex", flexDirection: "column", alignItems: "center" }}>

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
            Thank You for Your Contribution!
          </h1>

          {/* Body text */}
          <p style={{
            fontSize: "1.0625rem", color: C.onSurface, lineHeight: 1.7,
            maxWidth: "36rem", marginBottom: "2.5rem",
          }}>
            Your participation is now complete. Your responses have been saved and will contribute to our research.
          </p>

          {/* ── Survey section (NASA-TLX questions 1–6) temporarily removed.
               Restore by re-populating QUESTIONS above and un-commenting the
               block below.
          <div style={{ width: "100%", marginBottom: "0.5rem" }}>
            <p style={{
              fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.12em", color: C.onVariant, marginBottom: "1.75rem",
              textAlign: "left",
            }}>
              Please answer the following questions
            </p>

            {QUESTIONS.map(q => (
              <LikertQuestion
                key={q.key}
                question={q}
                value={ratings[q.key] ?? null}
                onChange={(val) => setRatings(prev => ({ ...prev, [q.key]: val }))}
              />
            ))}
          </div>
          */}

          {/* Feedback textarea */}
          <div style={{ width: "100%", marginBottom: "2rem", textAlign: "center" }}>
            <p style={{
              fontSize: "0.6875rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.12em", color: C.onVariant, marginBottom: "1rem",
              textAlign: "left",
            }}>
              Any additional feedback?{" "}
              <span style={{ fontWeight: 500, fontSize: "0.6875rem", color: C.outlineVar, letterSpacing: "0.08em" }}>
                (optional)
              </span>
            </p>
            <textarea
              value={feedback}
              onChange={(e) => setFeedback(e.target.value)}
              placeholder="Share any thoughts about the visualizations, tasks, or your experience…"
              maxLength={1000}
              rows={4}
              style={{
                width: "100%", padding: "0.875rem 1rem",
                border: "1.5px solid #dde4e5", borderRadius: "0.625rem",
                fontSize: "0.875rem", color: C.onSurface,
                lineHeight: 1.6, resize: "vertical", outline: "none",
                fontFamily: "inherit", background: C.white,
                transition: "border-color 0.15s ease",
                boxSizing: "border-box",
              }}
              onFocus={(e)  => { e.target.style.borderColor = "#3D4F7C"; }}
              onBlur={(e)   => { e.target.style.borderColor = "#dde4e5"; }}
            />
            <p style={{ fontSize: "0.7rem", color: C.outlineVar, textAlign: "right", marginTop: "0.35rem" }}>
              {feedback.length} / 1000
            </p>
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
            width: "100%",
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
              href="mailto:anyi.zhu@students.uni-mannheim.de"
              style={{
                fontSize: "0.875rem", fontWeight: 600, color: C.primary,
                textDecoration: "none",
              }}
              onMouseEnter={(e) => { e.currentTarget.style.textDecoration = "underline"; }}
              onMouseLeave={(e) => { e.currentTarget.style.textDecoration = "none"; }}
            >
              anyi.zhu@students.uni-mannheim.de
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
              { label: "About",                        href: "/about" },
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
