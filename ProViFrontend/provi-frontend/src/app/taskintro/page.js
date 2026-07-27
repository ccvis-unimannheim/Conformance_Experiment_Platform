"use client";

import React from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { TransformWrapper, TransformComponent } from "react-zoom-pan-pinch";

import ProcessModelDiagram from "../../public/images/order_to_cash_model.svg";
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

function ImageLightbox({ children, onClose }) {
  React.useEffect(() => {
    const onKeyDown = (e) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  return (
    <div
      onClick={onClose}
      style={{
        position: "fixed", inset: 0, zIndex: 200,
        backgroundColor: "rgba(20,24,25,1)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}
    >
      <button
        type="button"
        onClick={onClose}
        aria-label="Close"
        style={{
          position: "absolute", top: "1.25rem", right: "1.5rem",
          width: "2.5rem", height: "2.5rem", borderRadius: "50%",
          border: "none", backgroundColor: "rgba(255,255,255,0.15)", color: C.white,
          fontSize: "1.5rem", lineHeight: 1, cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}
      >
        <span className="material-symbols-outlined">close</span>
      </button>
      <p style={{
        position: "absolute", top: "1.5rem", left: "1.5rem",
        color: "rgba(255,255,255,0.7)", fontSize: "0.8125rem",
      }}>
        Scroll or pinch to zoom · drag to pan · click outside to close
      </p>
      <div
        onClick={(e) => e.stopPropagation()}
        style={{ width: "90vw", height: "85vh", display: "flex", alignItems: "center", justifyContent: "center" }}
      >
        <TransformWrapper initialScale={1} minScale={0.5} maxScale={8} centerOnInit>
          <TransformComponent>
            <div style={{ backgroundColor: C.white, borderRadius: "0.75rem", padding: "1.5rem", display: "flex" }}>
              {children}
            </div>
          </TransformComponent>
        </TransformWrapper>
      </div>
    </div>
  );
}

export default function TaskIntroPage() {
  const router = useRouter();
  const [imageZoomOpen, setImageZoomOpen] = React.useState(false);

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
              Before You Begin
            </h1>
            <p style={{ fontSize: "0.875rem", color: C.onVariant, maxWidth: "36rem", margin: "0 auto", lineHeight: 1.6 }}>
              A quick recap of what comes next, plus how the platform determines guideline violations and fitness.
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

              {/* ── 1. The process */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>hub</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    The Process
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  All of the tasks that follow are about the same order-to-cash process you saw on the previous
                  page. Click the diagram to enlarge it at any time.
                </p>
                <button
                  type="button"
                  onClick={() => setImageZoomOpen(true)}
                  aria-label="Enlarge process model diagram"
                  style={{
                    display: "block", width: "100%", padding: 0, border: "none", background: "none", cursor: "zoom-in",
                    overflowX: "auto",
                  }}
                >
                  <ProcessModelDiagram
                    role="img"
                    aria-label="Order-to-cash process model (BPMN): Receive Order, Check Credit, Confirm Order, Prepare Shipment, Issue Invoice, Ship Order, Receive Payment, Cancel Order"
                    style={{ width: "100%", height: "auto", borderRadius: "0.5rem" }}
                  />
                </button>
              </section>

              {imageZoomOpen && (
                <ImageLightbox onClose={() => setImageZoomOpen(false)}>
                  <ProcessModelDiagram
                    role="img"
                    aria-label="Order-to-cash process model (BPMN): Receive Order, Check Credit, Confirm Order, Prepare Shipment, Issue Invoice, Ship Order, Receive Payment, Cancel Order"
                    style={{ maxWidth: "85vw", maxHeight: "80vh", borderRadius: "0.5rem" }}
                  />
                </ImageLightbox>
              )}

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 2. What to expect */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>quiz</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    What to Expect
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  You will now answer a series of questions about the conformance of this process. Each
                  question is paired with a chart or diagram visualising the relevant data — use it to work
                  out your answer. If you need a reminder of a term, the &ldquo;Key Terms&rdquo; chips above
                  each question link back to short definitions. Below, we explain alignment, model move, log
                  move, guideline violation, and fitness in detail — these are the terms most of the tasks
                  will ask you about.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 3. Alignment & Move Types */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>compare_arrows</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Alignment &amp; Move Types
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  An <strong>alignment</strong> relates the events recorded in a trace to the activities
                  expected by the process model, step by step. Where the trace and the model agree at a step,
                  that step is a match; where they disagree, the step is recorded as one of two kinds of
                  deviation. The example below aligns the trace ⟨Receive Order, Check Credit, Escalate
                  Case⟩ against the guideline, which at this point expects ⟨Receive Order, Check Credit,
                  Confirm Order⟩:
                </p>
                <div style={{ overflowX: "auto", marginBottom: "1rem" }}>
                  <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem", color: C.onSurface }}>
                    <thead>
                      <tr style={{ backgroundColor: C.containerLow }}>
                        <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600, borderBottom: `1px solid ${C.containerHigh}` }}>Step</th>
                        <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600, borderBottom: `1px solid ${C.containerHigh}` }}>1</th>
                        <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600, borderBottom: `1px solid ${C.containerHigh}` }}>2</th>
                        <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600, borderBottom: `1px solid ${C.containerHigh}` }}>3</th>
                        <th style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600, borderBottom: `1px solid ${C.containerHigh}` }}>4</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr>
                        <td style={{ padding: "0.5rem 0.75rem", fontWeight: 600, color: C.onVariant }}>Trace</td>
                        <td style={{ padding: "0.5rem 0.75rem" }}>Receive Order</td>
                        <td style={{ padding: "0.5rem 0.75rem" }}>Check Credit</td>
                        <td style={{ padding: "0.5rem 0.75rem", color: C.outlineVar }}>—</td>
                        <td style={{ padding: "0.5rem 0.75rem" }}>Escalate Case</td>
                      </tr>
                      <tr>
                        <td style={{ padding: "0.5rem 0.75rem", fontWeight: 600, color: C.onVariant }}>Model</td>
                        <td style={{ padding: "0.5rem 0.75rem" }}>Receive Order</td>
                        <td style={{ padding: "0.5rem 0.75rem" }}>Check Credit</td>
                        <td style={{ padding: "0.5rem 0.75rem" }}>Confirm Order</td>
                        <td style={{ padding: "0.5rem 0.75rem", color: C.outlineVar }}>—</td>
                      </tr>
                      <tr>
                        <td style={{ padding: "0.5rem 0.75rem", fontWeight: 600, color: C.onVariant, borderTop: `1px solid ${C.containerHigh}` }}>Step type</td>
                        {[
                          ["Synchronous", "#15803d", "#f0fdf4"],
                          ["Synchronous", "#15803d", "#f0fdf4"],
                          ["Model move", "#d97706", "#fffbeb"],
                          ["Log move",   "#dc2626", "#fef2f2"],
                        ].map(([label, color, bg], i) => (
                          <td key={i} style={{ padding: "0.5rem 0.75rem", borderTop: `1px solid ${C.containerHigh}` }}>
                            <span style={{
                              display: "inline-block", padding: "0.15rem 0.5rem", borderRadius: "999px",
                              backgroundColor: bg, color, fontSize: "0.75rem", fontWeight: 700,
                            }}>
                              {label}
                            </span>
                          </td>
                        ))}
                      </tr>
                    </tbody>
                  </table>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  Steps 1–2 match, so they are synchronous moves. At step 3 the model expects Confirm Order but
                  the trace has no matching event, so it is a model move (skipped). At step 4 the trace contains
                  Escalate Case, which the model does not expect at that point, so it is a log move (unexpected).
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {[
                    ["check_circle",  "#15803d", "#f0fdf4", "#bbf7d0", "Synchronous move", "The trace event and the model activity match — the expected, conformant step."],
                    ["remove_circle", "#d97706", "#fffbeb", "#fde68a", "Model move",        "The model expected an activity but the trace has no matching event — it was skipped."],
                    ["add_circle",    "#dc2626", "#fef2f2", "#fecaca", "Log move",          "The trace contains an activity the model did not expect at that point — a superfluous execution."],
                  ].map(([icon, color, bg, border, label, desc]) => (
                    <div key={label} style={{
                      display: "flex", alignItems: "flex-start", gap: "0.875rem",
                      padding: "0.875rem 1rem", backgroundColor: bg,
                      border: `1px solid ${border}`, borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color, fontSize: "1.1rem", flexShrink: 0, marginTop: "0.15rem" }}>{icon}</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>{label}:</strong> {desc}
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 4. Guideline Violation */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>warning</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Guideline Violation
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  Log moves and model moves flag <strong>guideline violations</strong>: a trace has a guideline
                  violation wherever its alignment contains a log move or a model move — i.e. any move other
                  than a synchronous move. Note that only these two terms are <strong>types</strong>{" "}of
                  guideline violations — synchronous moves represent the absence of a violation, not a type of
                  it — and naming a guideline violation needs the naming of the activity on which a type of
                  violation occurs (e.g. &ldquo;Model move on Ship Order&rdquo;).
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 5. Conformant / Nonconformant Traces */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>route</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Conformant and Non-conformant Traces
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>conformant</strong> trace is a trace without guideline violations; a
                  <strong> non-conformant</strong> trace is a trace with at least one guideline violation.
                </p>
                <Collapsible label="See examples">
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem", backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0", borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#15803d", fontSize: "1.2rem", flexShrink: 0, marginTop: "0.1rem" }}>check_circle</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Conformant trace:</strong> Every activity follows a path the guideline allows. The trace can be fully replayed on the guideline without any deviation.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem", backgroundColor: "#fef2f2",
                      border: "1px solid #fecaca", borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#dc2626", fontSize: "1.2rem", flexShrink: 0, marginTop: "0.1rem" }}>cancel</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Non-conformant trace:</strong> At least one activity violates the guideline — e.g. a required step was skipped or an unexpected step was performed.
                      </p>
                    </div>
                  </div>
                </Collapsible>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 6. Degree of Conformance / Fitness */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>speed</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Degree of Conformance (Fitness)
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  Based on these individual guideline violations, we can compute the trace <strong>fitness</strong>
                  — i.e. the trace&apos;s degree of conformance with the rules — and the log fitness, i.e. the
                  overall degree of conformance of all traces in the log. When shown as a percentage, fitness
                  values are rounded to one decimal place (e.g. 97.9%).
                </p>
                <Collapsible label="Interpreting fitness values">
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem", backgroundColor: "#f0fdf4",
                      border: "1px solid #bbf7d0", borderRadius: "0.5rem",
                    }}>
                      <span style={{ flexShrink: 0, fontWeight: 800, fontSize: "1rem", color: "#15803d", minWidth: "2.5rem", paddingTop: "0.1rem" }}>1.0</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Perfect conformance.</strong> All recorded behaviour is fully covered by the guideline. Every trace follows the expected process exactly.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem", backgroundColor: "#fef2f2",
                      border: "1px solid #fecaca", borderRadius: "0.5rem",
                    }}>
                      <span style={{ flexShrink: 0, fontWeight: 800, fontSize: "1rem", color: "#dc2626", minWidth: "2.5rem", paddingTop: "0.1rem" }}>0.0</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>No conformance.</strong> No recorded behaviour matches the guideline at all.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "1rem",
                      padding: "1rem 1.25rem", backgroundColor: C.containerLow,
                      border: `1px solid ${C.containerHigh}`, borderRadius: "0.5rem",
                    }}>
                      <span style={{ flexShrink: 0, fontWeight: 800, fontSize: "1rem", color: C.primary, minWidth: "2.5rem", paddingTop: "0.1rem" }}>0–1</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Partial conformance.</strong> The higher the value, the closer the recorded behaviour is to the guideline overall.
                      </p>
                    </div>
                  </div>
                </Collapsible>
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
                onClick={() => router.push("/conformance-terms")}
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
