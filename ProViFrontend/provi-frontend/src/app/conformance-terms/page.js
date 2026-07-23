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

export default function ConformanceTermsPage() {
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
              Key Concepts in Conformance Checking
            </h1>
            <p style={{ fontSize: "0.875rem", color: C.onVariant, maxWidth: "36rem", margin: "0 auto", lineHeight: 1.6 }}>
              Before you begin the tasks, please read the following definitions. They explain the core concepts used throughout this study.
            </p>
          </header>

          {/* Process model illustration */}
          <div style={{
            backgroundColor: C.white,
            border: `1px solid ${C.containerHigh}`,
            borderRadius: "0.75rem",
            boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
            padding: "1.5rem 1.5rem 1.25rem",
            marginBottom: "1.5rem",
          }}>
            <p style={{ fontSize: "0.8125rem", color: C.onVariant, margin: "0 0 0.75rem", lineHeight: 1.6 }}>
              This is the <strong>process model (guideline)</strong> used throughout this study — an order-to-cash
              process. The definitions below refer back to it. Click the diagram to enlarge.
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
          </div>

          {imageZoomOpen && (
            <ImageLightbox onClose={() => setImageZoomOpen(false)}>
              <ProcessModelDiagram
                role="img"
                aria-label="Order-to-cash process model (BPMN): Receive Order, Check Credit, Confirm Order, Prepare Shipment, Issue Invoice, Ship Order, Receive Payment, Cancel Order"
                style={{ maxWidth: "85vw", maxHeight: "80vh", borderRadius: "0.5rem" }}
              />
            </ImageLightbox>
          )}

          {/* Content card */}
          <div style={{
            backgroundColor: C.white,
            border: `1px solid ${C.containerHigh}`,
            borderRadius: "0.75rem",
            boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
            overflow: "hidden",
          }}>
            <div style={{ padding: "2.5rem 3rem", display: "flex", flexDirection: "column", gap: "1.75rem" }}>

              {/* ── 1. Process */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>hub</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Process
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>process</strong> is a set of activities that are executed in a coordinated manner to
                  achieve a certain goal — for example, order-to-cash, the process used throughout this study
                  (shown at the top of this page).
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 2. Case */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>assignment</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Case
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>case</strong> represents an instance of the process, defined by all activity
                  executions that relate to one specific trigger or input to the system whose behaviour is
                  described by the process — for example, one customer order.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 3. Trace */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>linear_scale</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Trace
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>trace</strong> is a recorded representation of a case of the process — i.e. all events
                  in the event log that share the same case identifier. Each trace can be compared against the
                  guideline to assess whether it was executed correctly.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 4. Event */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>bolt</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Event
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  An <strong>event</strong> is a single recorded occurrence in the process, indicating (1) at
                  what point in time, (2) which activity was executed, and (3) for which case.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 5. Event Log */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>table_rows</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Event Log
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  An <strong>event log</strong> is a collection of events. Events that share the same case
                  identifier form a <strong>trace</strong>, representing one complete process execution from
                  start to finish.
                </p>
                <Collapsible label="See an example event log">
                  <div style={{ overflowX: "auto" }}>
                    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.875rem", color: C.onSurface }}>
                      <thead>
                        <tr style={{ backgroundColor: C.containerLow }}>
                          {["Event", "Case ID", "Activity", "Timestamp"].map(h => (
                            <th key={h} style={{ padding: "0.5rem 0.75rem", textAlign: "left", fontWeight: 600, borderBottom: `1px solid ${C.containerHigh}` }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {[
                          ["e₁","id-4","Receive Order","01.01.24  09:00"],
                          ["e₂","id-4","Check Credit","01.01.24  09:14"],
                          ["e₃","id-4","Confirm Order","01.01.24  09:28"],
                          ["e₄","id-4","Ship Order","01.01.24  09:57"],
                          ["e₅","id-4","Receive Payment","01.01.24  10:20"],
                          ["e₆","id-7","Receive Order","01.01.24  11:12"],
                          ["e₇","id-7","Confirm Order","01.01.24  11:55"],
                          ["e₈","id-7","Check Credit","01.01.24  12:38"],
                          ["e₉","id-7","Cancel Order","01.01.24  13:21"],
                        ].map(([ev, cid, act, ts], i) => (
                          <tr key={i} style={{ backgroundColor: i % 2 === 0 ? C.white : C.surface }}>
                            <td style={{ padding: "0.4rem 0.75rem", fontStyle: "italic" }}>{ev}</td>
                            <td style={{ padding: "0.4rem 0.75rem" }}>{cid}</td>
                            <td style={{ padding: "0.4rem 0.75rem", fontWeight: 600 }}>{act}</td>
                            <td style={{ padding: "0.4rem 0.75rem", color: C.onVariant }}>{ts}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    <p style={{ fontSize: "0.8125rem", color: C.onVariant, marginTop: "0.75rem", lineHeight: 1.6 }}>
                      Events e₁–e₅ (Case id-4) form one trace: Receive Order→Check Credit→Confirm Order→Ship Order→Receive Payment.
                      Events e₆–e₉ (Case id-7) form another: Receive Order→Confirm Order→Check Credit→Cancel Order.
                    </p>
                  </div>
                </Collapsible>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 6. Attribute */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>tune</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Attribute
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  Events may be characterised by various <strong>attributes</strong>; for example, an event may
                  have a timestamp, correspond to an activity, be executed by a particular person, or have
                  associated costs.
                </p>
                <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                  {[
                    ["compare_arrows", "#15803d", "#f0fdf4", "#bbf7d0", "Control-flow attribute", "The activity label itself — which step was performed (e.g. \"Check Credit\" or \"Ship Order\")."],
                    ["storage",        "#1d4ed8", "#eff6ff", "#bfdbfe", "Data attribute",         "Captures data values associated with an event or case (e.g. amount, category, status)."],
                    ["person",         "#7c3aed", "#f5f3ff", "#ddd6fe", "Resource attribute",     "Records who or what performed an activity (e.g. a specific employee or system)."],
                    ["schedule",       "#b45309", "#fffbeb", "#fde68a", "Time attribute",          "Captures when an activity occurred or how long it took (e.g. timestamp, duration)."],
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

              {/* ── 7. Guideline */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>account_tree</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Guideline
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>guideline</strong> is the technology-agnostic expression of a process model, where a
                  process model serves as an abstract representation of the process for specific modelling goals
                  and describes the allowed execution sequences for different process cases. In this study, we
                  represent multiple guidelines collectively in an imperative process model as a
                  <strong> BPMN</strong> (Business Process Model and Notation) diagram — the order-to-cash
                  diagram shown at the top of this page. &ldquo;Guideline&rdquo; and &ldquo;process
                  model&rdquo; therefore refer to the same underlying reference behaviour and are used
                  interchangeably throughout.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 8. Alignment */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>compare_arrows</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Alignment
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  An <strong>alignment</strong> relates the events recorded in a trace to the activities
                  expected by the process model. For example, aligning the trace ⟨Receive Order, Check Credit,
                  Cancel Order⟩ against a guideline requiring ⟨Receive Order, Check Credit, Confirm Order⟩
                  matches Receive Order and Check Credit, but finds Confirm Order missing. If the trace instead
                  contained an unexpected activity at that point, such as Escalate Case, this would be recorded
                  as a different kind of step. These three kinds of steps — log move, model move, and
                  synchronous move — are defined below.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 9. Log Move */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>add_circle</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Log Move
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  When an event in the trace indicates that an activity has been executed even though it should
                  not have been executed according to the model, the alignment contains a <strong>log move</strong>.
                  As the counterpart of a model move, a log move represents a deviation in the sense of a
                  superfluous execution of an activity.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 10. Model Move */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>remove_circle</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Model Move
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  When an activity should have been executed according to the model but there is no related event
                  in the trace, we refer to this situation as a <strong>model move</strong>. The move represents a
                  deviation between the trace and the execution sequence of the model in the sense that the
                  execution of an activity has been skipped.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 11. Synchronous Move */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>check_circle</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Synchronous Move
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>synchronous move</strong> is a step in which the event of the trace and the task in
                  the execution sequence correspond to each other, i.e., both refer to the same activity.
                  Synchronous moves denote the expected situation in which the recorded events in the trace are
                  in line with the tasks of an execution sequence of the process model.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 12. Guideline Violation */}
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

              {/* ── 13. Conformant / Nonconformant Traces */}
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

              {/* ── 14. Degree of Conformance / Fitness */}
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
