"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

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

function RadioOption({ label, selected, onChange, italic }) {
  return (
    <div
      role="radio"
      aria-checked={selected}
      tabIndex={0}
      onClick={onChange}
      onKeyDown={(e) => { if (e.key === " " || e.key === "Enter") onChange(); }}
      style={{
        display: "flex", alignItems: "center", gap: "0.875rem",
        padding: "1rem 1.25rem",
        borderRadius: "0.5rem",
        border: selected ? `1px solid ${C.primary}` : `1px solid ${C.containerHigh}`,
        backgroundColor: selected ? "rgba(0,48,94,0.05)" : C.containerLow,
        cursor: "pointer",
        marginBottom: "0.5rem",
        transition: "all 0.15s ease",
        boxShadow: selected ? `inset 0 0 0 1px ${C.primary}` : "none",
      }}
    >
      <div style={{
        width: "1rem", height: "1rem", borderRadius: "50%", flexShrink: 0,
        border: selected ? `5px solid ${C.primary}` : `2px solid ${C.outlineVar}`,
        backgroundColor: C.white,
        transition: "border 0.15s ease",
      }} />
      <span style={{
        fontSize: "0.875rem", color: selected ? C.primary : C.onSurface,
        fontStyle: italic ? "italic" : "normal",
        fontWeight: selected ? 600 : 400,
      }}>
        {label}
      </span>
    </div>
  );
}

export default function KnowledgeQuestionPage() {
  const router = useRouter();
  const [questions, setQuestions] = useState([]);
  const [loadingQs, setLoadingQs] = useState(true);
  const [answers, setAnswers] = useState({});
  const [error, setError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    fetch("/api/participant/knowledge-questions", { credentials: "include" })
      .then((r) => (r.ok ? r.json() : Promise.reject(r.status)))
      .then((data) => setQuestions(data.questions ?? []))
      .catch(() => setError("Failed to load knowledge questions. Please refresh the page."))
      .finally(() => setLoadingQs(false));
  }, []);

  const isValid = questions.length > 0 && questions.every((q) => answers[q._id] != null);

  const handleSubmit = async () => {
    if (!isValid) {
      setError("Please answer all questions before submitting.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const res = await fetch("/api/auth/knowledge", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ answers }),
      });
      if (!res.ok) {
        setError("Submission failed. Please try again.");
        return;
      }
      router.push("/conformance-terms");
    } catch {
      setError("Network error. Please check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  // Group questions by section_title
  const sections = questions.reduce((acc, q) => {
    const key = q.section_title || "Knowledge Questions";
    if (!acc[key]) acc[key] = [];
    acc[key].push(q);
    return acc;
  }, {});

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
      <main style={{ paddingTop: "6rem", paddingBottom: "6rem", minHeight: "100vh" }}>
        <div style={{ maxWidth: "48rem", margin: "0 auto", padding: "0 1.5rem" }}>

          <header style={{ marginBottom: "2.5rem", textAlign: "center" }}>
            <h1 style={{
              fontFamily: "'Work Sans', 'Inter', sans-serif",
              fontSize: "1.875rem", fontWeight: 700,
              color: C.primary, letterSpacing: "-0.02em", marginBottom: "0.5rem",
            }}>
              Knowledge Survey
            </h1>
            <p style={{ fontSize: "0.875rem", color: C.onVariant, maxWidth: "36rem", margin: "0 auto" }}>
              Please answer the following questions based on your current knowledge. If you are unsure, select{" "}
              <strong style={{ color: C.primary }}>&ldquo;I don&apos;t know.&rdquo;</strong>{" "}
              There is no penalty for choosing that option.
            </p>
          </header>

          {loadingQs ? (
            <div style={{ textAlign: "center", padding: "4rem", color: C.onVariant }}>Loading questions…</div>
          ) : error && questions.length === 0 ? (
            <div style={{
              padding: "0.875rem 1.25rem",
              backgroundColor: "#fef2f2", border: "1px solid #fecaca",
              borderRadius: "0.5rem", color: "#dc2626", fontSize: "0.875rem", fontWeight: 500,
            }}>{error}</div>
          ) : (
            <div style={{
              backgroundColor: C.white,
              border: `1px solid ${C.containerHigh}`,
              borderRadius: "0.75rem",
              boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
              overflow: "hidden",
            }}>
              <div style={{ padding: "3rem", display: "flex", flexDirection: "column", gap: "3rem" }}>

                {/* ── Knowledge sections (from DB) */}
                {Object.entries(sections).map(([sectionTitle, qs], sIdx) => (
                  <React.Fragment key={sectionTitle}>
                    {sIdx > 0 && (
                      <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
                    )}
                    <section>
                      <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
                        <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>rule</span>
                        <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>{sectionTitle}</h2>
                      </div>
                      <div style={{ display: "flex", flexDirection: "column", gap: "2.5rem" }}>
                        {qs.map((q) => (
                          <div key={q._id}>
                            <label style={{ display: "block", marginBottom: "0.75rem", fontSize: "0.875rem", fontWeight: 600, color: C.onSurface }}>
                              {q.text}
                            </label>
                            <div style={{ marginTop: "0.75rem" }}>
                              {q.options.map((opt, optIdx) => (
                                <RadioOption
                                  key={optIdx}
                                  label={opt}
                                  selected={answers[q._id] === optIdx}
                                  italic={opt === "I don't know"}
                                  onChange={() => setAnswers((prev) => ({ ...prev, [q._id]: optIdx }))}
                                />
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </section>
                  </React.Fragment>
                ))}

              </div>

              {/* ── CTA area */}
              <div style={{
                backgroundColor: C.containerLow,
                borderTop: `1px solid ${C.containerHigh}`,
                padding: "2rem 3rem",
                display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem",
              }}>
                <button
                  type="button"
                  onClick={() => router.push("/prequestionnaire")}
                  style={{
                    padding: "0.75rem 2rem", borderRadius: "0.5rem", border: "none",
                    backgroundColor: "transparent", color: C.onVariant,
                    fontWeight: 600, fontSize: "0.875rem", cursor: "pointer",
                    display: "flex", alignItems: "center", gap: "0.5rem",
                    transition: "background-color 0.15s ease",
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = C.container; }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
                >
                  <span className="material-symbols-outlined" style={{ fontSize: "1.1rem" }}>arrow_back</span>
                  Back
                </button>

                <button
                  type="button"
                  onClick={handleSubmit}
                  disabled={submitting}
                  style={{
                    padding: "0.75rem 2.5rem", borderRadius: "0.5rem", border: "none",
                    backgroundColor: isValid && !submitting ? C.primary : C.outlineVar,
                    color: C.white, fontWeight: 700, fontSize: "0.875rem",
                    cursor: isValid && !submitting ? "pointer" : "not-allowed",
                    boxShadow: isValid && !submitting ? "0 2px 8px rgba(0,48,94,0.25)" : "none",
                    display: "flex", alignItems: "center", gap: "0.5rem",
                    transition: "all 0.15s ease",
                  }}
                >
                  {submitting ? "Submitting…" : "Next: Key Concept"}
                  <span className="material-symbols-outlined" style={{ fontSize: "1.1rem" }}>arrow_forward</span>
                </button>
              </div>
            </div>
          )}

          {error && questions.length > 0 && (
            <div style={{
              marginTop: "1rem", padding: "0.875rem 1.25rem",
              backgroundColor: "#fef2f2", border: "1px solid #fecaca",
              borderRadius: "0.5rem", color: "#dc2626", fontSize: "0.875rem", fontWeight: 500,
            }}>
              {error}
            </div>
          )}
        </div>
      </main>

      {/* ── Sticky Footer */}
      <footer style={{
        position: "fixed", bottom: 0, left: 0, width: "100%",
        padding: "0.75rem 2rem",
        backgroundColor: "rgba(255,255,255,0.85)",
        backdropFilter: "blur(8px)",
        borderTop: `1px solid ${C.containerHigh}`,
        zIndex: 40, boxSizing: "border-box",
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
              { label: "Imprint",                    href: "/imprint" },
              { label: "About",                       href: "/about" },
              { label: "Data Protection Declaration", href: "/dataprotection" },
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
