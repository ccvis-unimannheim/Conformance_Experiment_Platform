"use client";

import React from "react";
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

export default function ConformanceTermsPage() {
  const router = useRouter();

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
        </div>
      </header>

      {/* ── Main */}
      <main style={{ paddingTop: "6rem", paddingBottom: "6rem", minHeight: "100vh" }}>
        <div style={{ maxWidth: "48rem", margin: "0 auto", padding: "0 1.5rem" }}>

          {/* Page heading */}
          <header style={{ marginBottom: "2.5rem", textAlign: "center" }}>
            <h1 style={{
              fontFamily: "'Work Sans', 'Inter', sans-serif",
              fontSize: "1.875rem", fontWeight: 700,
              color: C.primary, letterSpacing: "-0.02em", marginBottom: "0.5rem",
            }}>
              Key Concept: Fitness
            </h1>
            <p style={{ fontSize: "0.875rem", color: C.onVariant, maxWidth: "36rem", margin: "0 auto", lineHeight: 1.6 }}>
              Before you begin the tasks, please read the following definition. It explains the core metric used throughout this study.
            </p>
          </header>

          {/* Content card */}
          <div style={{
            backgroundColor: C.white,
            border: `1px solid ${C.containerHigh}`,
            borderRadius: "0.75rem",
            boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
            overflow: "hidden",
          }}>
            <div style={{ padding: "2.5rem 3rem", display: "flex", flexDirection: "column", gap: "1.75rem" }}>

              {/* Definition */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>speed</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    What is Fitness?
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  <strong>Fitness</strong> measures the ability of a process model to explain the execution of a process
                  as recorded in an event log. It is the main measure used to assess whether a model is well-suited to
                  explain the recorded behaviour.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* Formula block */}
              <section>
                <h3 style={{ fontSize: "0.875rem", fontWeight: 700, color: C.onVariant, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "0.875rem" }}>
                  How it is calculated
                </h3>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  In general, fitness is the <strong>fraction of the behaviour recorded in the log that is also
                  allowed by the model</strong>:
                </p>
                {/* Formula display */}
                <div style={{
                  backgroundColor: C.containerLow,
                  borderRadius: "0.5rem",
                  padding: "1.25rem 1.5rem",
                  textAlign: "center",
                  fontFamily: "'Georgia', serif",
                  fontSize: "1.0625rem",
                  color: C.onSurface,
                  letterSpacing: "0.02em",
                  margin: "0 0 1rem",
                }}>
                  fitness = |L ∩ M| / |L|
                </div>
                <p style={{ fontSize: "0.875rem", color: C.onVariant, lineHeight: 1.7, margin: 0 }}>
                  where <em>L</em> is the set of behaviours observed in the event log and <em>M</em> is the set of
                  behaviours allowed by the process model.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* Extreme values */}
              <section>
                <h3 style={{ fontSize: "0.875rem", fontWeight: 700, color: C.onVariant, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: "1rem" }}>
                  Interpreting fitness values
                </h3>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                  <div style={{
                    display: "flex", alignItems: "flex-start", gap: "1rem",
                    padding: "1rem 1.25rem",
                    backgroundColor: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: "0.5rem",
                  }}>
                    <span style={{
                      flexShrink: 0, fontWeight: 800, fontSize: "1rem",
                      color: "#15803d", minWidth: "2.5rem", paddingTop: "0.1rem",
                    }}>1.0</span>
                    <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                      <strong>Perfect fitness.</strong> The entire behaviour recorded in the log is covered by the model
                      (<em>L ⊆ M</em>). Every trace follows the expected process exactly.
                    </p>
                  </div>
                  <div style={{
                    display: "flex", alignItems: "flex-start", gap: "1rem",
                    padding: "1rem 1.25rem",
                    backgroundColor: "#fef2f2",
                    border: "1px solid #fecaca",
                    borderRadius: "0.5rem",
                  }}>
                    <span style={{
                      flexShrink: 0, fontWeight: 800, fontSize: "1rem",
                      color: "#dc2626", minWidth: "2.5rem", paddingTop: "0.1rem",
                    }}>0.0</span>
                    <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                      <strong>No fitness.</strong> No behaviour in the log is captured by the model
                      (<em>L ∩ M = ∅</em>). No trace follows the expected process in any way.
                    </p>
                  </div>
                  <div style={{
                    display: "flex", alignItems: "flex-start", gap: "1rem",
                    padding: "1rem 1.25rem",
                    backgroundColor: C.containerLow,
                    border: `1px solid ${C.containerHigh}`,
                    borderRadius: "0.5rem",
                  }}>
                    <span style={{
                      flexShrink: 0, fontWeight: 800, fontSize: "1rem",
                      color: C.primary, minWidth: "2.5rem", paddingTop: "0.1rem",
                    }}>0–1</span>
                    <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                      <strong>Partial fitness.</strong> A trace is considered <em>fitting</em> if it corresponds to a
                      valid execution sequence of the model, and <em>non-fitting</em> if there is any deviation. Values
                      between 0 and 1 reflect the proportion of fitting traces in the log.
                    </p>
                  </div>
                </div>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* Citation */}
              <section>
                <div style={{
                  display: "flex", alignItems: "flex-start", gap: "0.75rem",
                  padding: "0.875rem 1rem",
                  backgroundColor: C.containerLow,
                  borderRadius: "0.5rem",
                  borderLeft: `3px solid ${C.outlineVar}`,
                }}>
                  <span className="material-symbols-outlined" style={{ color: C.outlineVar, fontSize: "1.1rem", flexShrink: 0, marginTop: "0.1rem" }}>menu_book</span>
                  <p style={{ margin: 0, fontSize: "0.8125rem", color: C.onVariant, lineHeight: 1.65 }}>
                    Definition adapted from: Carmona, J., van Dongen, B., Solti, A., &amp; Weidlich, M. (2018).{" "}
                    <em>Conformance Checking: Relating Processes and Models</em>. Springer, Section 3.2.{" "}
                    <span style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
                      ISBN 978-3-319-99413-0 · DOI 10.1007/978-3-319-99414-7
                    </span>
                  </p>
                </div>
              </section>

            </div>

            {/* CTA area */}
            <div style={{
              backgroundColor: C.containerLow,
              borderTop: `1px solid ${C.containerHigh}`,
              padding: "2rem 3rem",
              display: "flex", justifyContent: "space-between", alignItems: "center",
            }}>
              <button
                type="button"
                onClick={() => router.push("/knowledgequestion")}
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
                onClick={() => router.push("/taskexecution")}
                style={{
                  padding: "0.75rem 2.5rem", borderRadius: "0.5rem", border: "none",
                  backgroundColor: C.primary, color: C.white,
                  fontWeight: 700, fontSize: "0.875rem",
                  cursor: "pointer",
                  boxShadow: "0 2px 8px rgba(0,48,94,0.25)",
                  display: "flex", alignItems: "center", gap: "0.5rem",
                  transition: "background-color 0.15s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = C.primaryDim; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = C.primary; }}
              >
                Begin the Experiment
                <span className="material-symbols-outlined" style={{ fontSize: "1.1rem" }}>arrow_forward</span>
              </button>
            </div>
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
