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

function Collapsible({ label, children }) {
  const [open, setOpen] = React.useState(false);
  return (
    <div style={{ marginTop: "0.875rem", borderRadius: "0.375rem", border: `1px solid ${C.containerHigh}`, overflow: "hidden" }}>
      <button
        type="button"
        onClick={() => setOpen(o => !o)}
        style={{
          width: "100%", display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "0.625rem 1rem",
          backgroundColor: C.containerLow,
          border: "none", cursor: "pointer",
          fontSize: "0.8125rem", fontWeight: 600, color: C.onVariant,
          textAlign: "left",
        }}
        onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = C.container; }}
        onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = C.containerLow; }}
      >
        <span>{label}</span>
        <span
          className="material-symbols-outlined"
          style={{ fontSize: "1.1rem", transition: "transform 0.2s", transform: open ? "rotate(180deg)" : "rotate(0deg)" }}
        >
          expand_more
        </span>
      </button>
      {open && (
        <div style={{ padding: "1rem 1rem 1rem", backgroundColor: C.white }}>
          {children}
        </div>
      )}
    </div>
  );
}

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
              Key Concepts in Conformance Checking
            </h1>
            <p style={{ fontSize: "0.875rem", color: C.onVariant, maxWidth: "36rem", margin: "0 auto", lineHeight: 1.6 }}>
              Before you begin the tasks, please read the following definitions. They explain the core concepts used throughout this study.
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

              {/* ── Process Model */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>account_tree</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Process Model
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>process model</strong> is a formal description of how a process is prescribed to be
                  executed — specifying which activities are involved and the allowed ways they can be performed.
                  Since every model is an abstraction, it cannot fully capture all real-world complexity; a model
                  may also become outdated or contain inaccuracies.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── Fitness */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>speed</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Fitness
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  <strong>Fitness</strong> measures the ability of a process model to explain the execution of a process
                  as recorded in an event log — how well the model covers the observed behaviour.
                </p>

                <Collapsible label="How it is calculated">
                  <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                    Fitness is the <strong>fraction of the behaviour recorded in the log that is also
                    allowed by the model</strong>:
                  </p>
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
                </Collapsible>

                <Collapsible label="Interpreting fitness values">
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem",
                      backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: "0.5rem",
                    }}>
                      <span style={{ flexShrink: 0, fontWeight: 800, fontSize: "1rem", color: "#15803d", minWidth: "2.5rem", paddingTop: "0.1rem" }}>1.0</span>
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
                      <span style={{ flexShrink: 0, fontWeight: 800, fontSize: "1rem", color: "#dc2626", minWidth: "2.5rem", paddingTop: "0.1rem" }}>0.0</span>
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
                      <span style={{ flexShrink: 0, fontWeight: 800, fontSize: "1rem", color: C.primary, minWidth: "2.5rem", paddingTop: "0.1rem" }}>0–1</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Partial fitness.</strong> A trace is considered <em>fitting</em> if it corresponds to a
                        valid execution sequence of the model, and <em>non-fitting</em> if there is any deviation. Values
                        between 0 and 1 reflect the proportion of fitting traces in the log.
                      </p>
                    </div>
                  </div>
                </Collapsible>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── Conformant / Nonconformant Traces */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>route</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Conformant and Nonconformant Traces
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>trace</strong> is a sequence of recorded activities belonging to one case of the process.
                  A trace is <strong>conformant</strong> if it can be fully replayed on the model without deviation,
                  and <strong>nonconformant</strong> if it contains activities that violate the model's prescribed steps.
                </p>

                <Collapsible label="See examples">
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem",
                      backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#15803d", fontSize: "1.2rem", flexShrink: 0, marginTop: "0.1rem" }}>check_circle</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        A <strong>conformant trace</strong> can be fully replayed on the process model without any deviation. Every activity follows a path that the model allows.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem",
                      backgroundColor: "#fef2f2",
                      border: "1px solid #fecaca",
                      borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#dc2626", fontSize: "1.2rem", flexShrink: 0, marginTop: "0.1rem" }}>cancel</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        A <strong>nonconformant trace</strong> contains at least one activity that violates the model's prescribed behaviour. It cannot be replayed without skipping or inserting steps.
                      </p>
                    </div>
                  </div>
                </Collapsible>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── Deviation */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>warning</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Deviation
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>deviation</strong> (or violation) is a mismatch between the behaviour recorded in the event
                  log and the behaviour prescribed by the process model.
                </p>

                <Collapsible label="Types of deviations">
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "0.875rem",
                      padding: "0.875rem 1rem",
                      backgroundColor: "#fef2f2",
                      border: "1px solid #fecaca",
                      borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#dc2626", fontSize: "1.1rem", flexShrink: 0, marginTop: "0.15rem" }}>add_circle</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Extra activity:</strong> An activity was executed in a case that the model does not allow at that point.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "0.875rem",
                      padding: "0.875rem 1rem",
                      backgroundColor: "#fffbeb",
                      border: "1px solid #fde68a",
                      borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#d97706", fontSize: "1.1rem", flexShrink: 0, marginTop: "0.15rem" }}>remove_circle</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Missing activity:</strong> An activity required by the model was not executed in the case.
                      </p>
                    </div>
                  </div>
                </Collapsible>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── Alignment Move Types */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>compare_arrows</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Alignment Move Types
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  An <strong>alignment</strong> compares a trace from the event log with a process model step by step,
                  finding the closest matching path. Each step is classified as one of three move types.
                </p>

                <Collapsible label="See move types">
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem",
                      backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0",
                      borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#15803d", fontSize: "1.2rem", flexShrink: 0, marginTop: "0.1rem" }}>sync</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Synchronous Move:</strong> The activity appears in both the trace and the model at the same step — no deviation occurs.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem",
                      backgroundColor: "#fef2f2",
                      border: "1px solid #fecaca",
                      borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#dc2626", fontSize: "1.2rem", flexShrink: 0, marginTop: "0.1rem" }}>description</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Move on Log:</strong> An activity appears in the trace but is not expected by the model at this point — the process executed something the model does not allow.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem",
                      backgroundColor: "#fffbeb",
                      border: "1px solid #fde68a",
                      borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#d97706", fontSize: "1.2rem", flexShrink: 0, marginTop: "0.1rem" }}>account_tree</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Move on Model:</strong> The model requires an activity, but it does not appear in the trace — the process skipped a step that the model prescribes.
                      </p>
                    </div>
                  </div>
                </Collapsible>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── Variants */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>format_list_bulleted</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Variants
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>variant</strong> is a distinct sequence of activities observed across multiple cases in the
                  event log. Cases that follow the same sequence of activities in the same order belong to the same variant.
                  Analysing variants reveals how many different execution paths exist in the recorded process behaviour.
                </p>
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
                    Definitions adapted from: Carmona, J., van Dongen, B., Solti, A., &amp; Weidlich, M. (2018).{" "}
                    <em>Conformance Checking: Relating Processes and Models</em>. Springer.{" "}
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
