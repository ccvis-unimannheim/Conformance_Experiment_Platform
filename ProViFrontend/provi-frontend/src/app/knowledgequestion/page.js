"use client";

import React, { useState, useEffect } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

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

// ── Correct answers for scoring (Q1=B, Q2=C, Q3=C, Q4=C, Q5=C, Q6=B)
const CORRECT = {
  q1: "To compare observed process behavior in an event log against a reference process model",
  q2: "The sequence of activities belonging to one process instance",
  q3: "75%",
  q4: "The model expected an activity to occur, but no corresponding activity was found in the log",
  q5: "Designing a new process model from scratch based on user preferences",
  q6: "Model A has a higher fitness with respect to the event log",
  q7: "A collection of recorded events during the execution of a business process",
  q8: "A sequence of activities belonging to one process instance",
  q9: "The trace follows the allowed behavior defined by the model",
  q10: "A step where an activity in the event log matches the model",
};

const TOOL_OPTIONS = [
  "Celonis", "Disco (Fluxicon)", "ProM", "PM4Py",
  "Apromore", "SAP Signavio", "None / I have not used process mining tools yet",
];

const SECTIONS = [
  {
    id: "A",
    icon: "rule",
    title: "Conformance Checking Knowledge",
    questions: [
      {
        key: "q1",
        text: "1. What is the primary purpose of conformance checking in process mining?",
        options: [
          "To predict future process behavior based on historical data",
          "To compare observed process behavior in an event log against a reference process model",
          "To automatically optimize the execution speed of a business process",
          "I don't know",
        ],
      },
      {
        key: "q2",
        text: "2. In a process mining event log, what does a single trace represent?",
        options: [
          "A single event recorded at one point in time",
          "The aggregate of all activities recorded across the entire log",
          "The sequence of activities belonging to one process instance",
          "I don't know",
        ],
      },
      {
        key: "q3",
        text: "3. A process log contains 200 traces. 150 traces fully comply with the process model, and 50 contain at least one violation. What is the approximate conformance rate of this log?",
        options: [
          "25%",
          "50%",
          "75%",
          "I don't know",
        ],
      },
      {
        key: "q4",
        text: "4. In alignment-based conformance checking, what does a model move indicate?",
        options: [
          "The process model was updated to reflect a new process variant",
          "An activity was executed in the log that the model did not expect at that point",
          "The model expected an activity to occur, but no corresponding activity was found in the log",
          "I don't know",
        ],
      },
      {
        key: "q5",
        text: "5. Which of the following is NOT typically considered a root cause analysis task in conformance checking?",
        options: [
          "Identifying which data attributes correlate with guideline violations",
          "Detecting which resources or time patterns are associated with non-conformant traces",
          "Designing a new process model from scratch based on user preferences",
          "I don't know",
        ],
      },
      {
        key: "q6",
        text: "6. When comparing two process models for the same event log, Model A replays 95% of traces without violations, while Model B replays only 60%. Which statement is most accurate?",
        options: [
          "Model B is preferable because it is more flexible",
          "Model A has a higher fitness with respect to the event log",
          "Both models are equally valid since they describe the same process",
          "I don't know",
        ],
      },
      {
        key: "q7",
        text: "7. What is an event log in process mining?",
        options: [
          "A list of software errors",
          "A collection of recorded events during the execution of a business process",
          "A diagram showing the structure of a company",
          "I don't know",
        ],
      },
      {
        key: "q8",
        text: "8. What is a trace in the context of process mining?",
        options: [
          "A type of process model",
          "A single event recorded at one point in time",
          "A sequence of activities belonging to one process instance",
          "I don't know",
        ],
      },
      {
        key: "q9",
        text: "9. What does it mean if a process trace 'conforms' to a process model?",
        options: [
          "The trace was executed faster than expected",
          "The trace follows the allowed behavior defined by the model",
          "The trace contains no events",
          "I don't know",
        ],
      },
      {
        key: "q10",
        text: "10. What does a synchronous move indicate in alignment-based conformance checking?",
        options: [
          "An activity in the log that the model did not expect",
          "A step where an activity in the event log matches the model",
          "A skipped activity in the trace",
          "I don't know",
        ],
      },
    ],
  },
];

const fieldLabelStyle = {
  fontSize: "0.75rem", fontWeight: 700,
  textTransform: "uppercase", letterSpacing: "0.1em",
  color: C.onVariant, display: "block", marginBottom: "1rem",
};

const sectionHeadStyle = {
  fontSize: "1.25rem", fontWeight: 700,
  color: C.onSurface, margin: 0,
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
  const [tools, setTools] = useState([]);
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

  const toggleTool = (tool) =>
    setTools((prev) =>
      prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]
    );

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
        body: JSON.stringify({ answers, tools }),
      });
      if (!res.ok) {
        setError("Submission failed. Please try again.");
        return;
      }
      router.push("/taskexecution");
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
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Image priority src={ProjectLogo} width={90} height={36} alt="ProVi Logo" style={{ objectFit: "contain" }} />
            <Image priority src={UniLogo} width={140} height={36} alt="University of Mannheim Logo" style={{ objectFit: "contain" }} />
          </div>
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

                {/* ── Tool Experience (unscored, hardcoded checkboxes) */}
                <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
                <section>
                  <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
                    <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>build</span>
                    <h2 style={{ fontSize: "1.25rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>Tool Experience</h2>
                  </div>
                  <p style={{ fontSize: "0.875rem", fontWeight: 600, color: C.onSurface, marginBottom: "1rem" }}>
                    Which of the following process mining tools have you used in a professional or academic setting? (Select all that apply)
                  </p>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "0.625rem" }}>
                    {TOOL_OPTIONS.map((tool) => {
                      const checked = tools.includes(tool);
                      const fullWidth = tool === "None / I have not used process mining tools yet";
                      return (
                        <div
                          key={tool}
                          onClick={() => toggleTool(tool)}
                          style={{
                            gridColumn: fullWidth ? "1 / -1" : undefined,
                            display: "flex", alignItems: "center", gap: "0.75rem",
                            padding: "1rem 1.25rem",
                            borderRadius: "0.5rem",
                            border: checked ? `1px solid ${C.primary}` : `1px solid ${C.containerHigh}`,
                            backgroundColor: checked ? "rgba(0,48,94,0.05)" : C.white,
                            cursor: "pointer",
                            transition: "all 0.15s ease",
                            boxShadow: checked ? `inset 0 0 0 1px ${C.primary}` : "none",
                          }}
                        >
                          <div style={{
                            width: "1rem", height: "1rem", borderRadius: "0.2rem", flexShrink: 0,
                            border: checked ? `2px solid ${C.primary}` : `2px solid ${C.outlineVar}`,
                            backgroundColor: checked ? C.primary : C.white,
                            display: "flex", alignItems: "center", justifyContent: "center",
                            transition: "all 0.15s ease",
                          }}>
                            {checked && (
                              <span className="material-symbols-outlined" style={{ color: C.white, fontSize: "0.75rem", fontVariationSettings: "'FILL' 1" }}>
                                check
                              </span>
                            )}
                          </div>
                          <span style={{ fontSize: "0.875rem", fontWeight: 500, color: checked ? C.primary : C.onSurface }}>
                            {tool}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </section>
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
                  {submitting ? "Submitting…" : "Begin Conformance Checking Task"}
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
