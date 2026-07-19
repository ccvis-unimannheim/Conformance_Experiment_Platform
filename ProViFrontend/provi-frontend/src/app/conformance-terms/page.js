"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";
import ProcessModelImage from "../../public/images/order_to_cash_model.jpeg";

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
              process. The definitions below refer back to it.
            </p>
            <div style={{ overflowX: "auto" }}>
              <Image
                src={ProcessModelImage}
                alt="Order-to-cash process model (BPMN): Receive Order, Check Credit, Confirm Order, Prepare Shipment, Issue Invoice, Ship Order, Receive Payment, Cancel Order"
                style={{ width: "100%", height: "auto", borderRadius: "0.5rem" }}
              />
            </div>
          </div>

          {/* Content card */}
          <div style={{
            backgroundColor: C.white,
            border: `1px solid ${C.containerHigh}`,
            borderRadius: "0.75rem",
            boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
            overflow: "hidden",
          }}>
            <div style={{ padding: "2.5rem 3rem", display: "flex", flexDirection: "column", gap: "1.75rem" }}>

              {/* ── 1. Guideline */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>account_tree</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Guideline
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>guideline</strong> is a set of rules that describe the intended, imperative behaviour
                  of a process — which activities are involved and the allowed sequences in which they may be
                  performed. It serves as the reference against which actual process behaviour is compared. In
                  this study, we represent a guideline using a <strong>process model</strong> — a diagram that
                  maps out the process&apos;s activities and the order in which they may occur (e.g. a BPMN diagram,
                  Petri net, or DFG), such as the order-to-cash process shown at the top of this page.
                  &ldquo;Guideline&rdquo; and &ldquo;process model&rdquo; therefore refer to the same underlying
                  reference behaviour and are used interchangeably throughout.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 2. Event Log */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>table_rows</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Event Log
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  An <strong>event log</strong> is a collection of events recorded during the execution of a process.
                  Each event captures information such as a case identifier, an activity name, and a timestamp.
                  Events that share the same case identifier form a <strong>trace</strong>, representing one complete
                  process execution from start to finish.
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

              {/* ── 3. Trace */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>linear_scale</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Trace
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>trace</strong> is the sequence of activities recorded for a single process execution (one case) —
                  i.e. all events in the event log that share the same case identifier. For example, one customer order
                  corresponds to one trace. Each trace can be compared against the guideline to
                  assess whether it was executed correctly.
                </p>
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
                  A <strong>guideline violation</strong> occurs when the behaviour recorded in a trace does not
                  match what the guideline prescribes. We detect violations by <strong>aligning</strong> each
                  trace with the guideline: every step in the alignment is either a match, or a deviation. By
                  construction, a deviation is always exactly one of two types — never anything else.
                </p>
                <Collapsible label="The two deviation types">
                  <div style={{ display: "flex", flexDirection: "column", gap: "0.625rem" }}>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "0.875rem",
                      padding: "0.875rem 1rem", backgroundColor: "#fef2f2",
                      border: "1px solid #fecaca", borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#dc2626", fontSize: "1.1rem", flexShrink: 0, marginTop: "0.15rem" }}>add_circle</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Extra activity (Log move):</strong> An activity was executed that the guideline does not permit at that point in the process.
                      </p>
                    </div>
                    <div style={{
                      display: "flex", alignItems: "flex-start", gap: "0.875rem",
                      padding: "0.875rem 1rem", backgroundColor: "#fffbeb",
                      border: "1px solid #fde68a", borderRadius: "0.5rem",
                    }}>
                      <span className="material-symbols-outlined" style={{ color: "#d97706", fontSize: "1.1rem", flexShrink: 0, marginTop: "0.15rem" }}>remove_circle</span>
                      <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                        <strong>Missing activity (Model move):</strong> An activity required by the guideline was not executed in the trace.
                      </p>
                    </div>
                  </div>
                </Collapsible>
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
                  A trace is <strong>conformant</strong> if every activity in it follows a path permitted by the guideline —
                  no steps are missing and no unexpected steps occur. A trace is <strong>non-conformant</strong> if it
                  contains at least one activity that violates the guideline's prescribed behaviour.
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

              {/* ── 6. Conformance Rate */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>percent</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Conformance Rate
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  The <strong>conformance rate</strong> is the percentage of traces in the event log that are
                  fully conformant with the guideline. A trace is counted as conformant only if it contains
                  no violations at all — it is a binary measure per trace. For example, a conformance rate of
                  70% means that 70 out of every 100 traces are fully conformant.
                </p>
              </section>

              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />

              {/* ── 7. Degree of Conformance / Fitness */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>speed</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Degree of Conformance (Fitness)
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  The <strong>degree of conformance</strong> describes how closely the behaviour recorded in an
                  event log matches a guideline overall. In this study we measure it as <strong>fitness</strong> —
                  a value between 0 (no match at all) and 1 (perfect match). Fitness is not just a count of how
                  many traces are conformant: it also weighs <em>how many</em> deviations occur within each trace,
                  so a trace with only one small deviation scores higher than one with many. Fitness can be
                  computed in different ways — e.g. token-based <strong>replay fitness</strong> or
                  <strong> alignment fitness</strong>; this study uses alignment fitness throughout, since
                  alignments also pinpoint exactly which activities deviated. When shown as a percentage, fitness
                  values are rounded to one decimal place (e.g. 97.9%).
                </p>
                <div style={{
                  display: "flex", alignItems: "flex-start", gap: "0.75rem",
                  padding: "0.75rem 1rem", backgroundColor: "#fffbeb",
                  border: "1px solid #fde68a", borderLeft: "3px solid #d97706",
                  borderRadius: "0.5rem", marginBottom: "1rem",
                }}>
                  <span className="material-symbols-outlined" style={{ color: "#d97706", fontSize: "1.1rem", flexShrink: 0, marginTop: "0.1rem" }}>warning</span>
                  <p style={{ margin: 0, fontSize: "0.875rem", color: C.onSurface, lineHeight: 1.7 }}>
                    <strong>Degree of conformance (fitness) ≠ Conformance rate.</strong> Fitness is a weighted measure
                    of how much of the recorded behaviour conforms to the guideline. Conformance rate is simply the
                    percentage of traces that are fully conformant. A log can have high fitness but a low conformance
                    rate if many traces have only minor violations.
                  </p>
                </div>
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

              {/* ── 8. Attribute */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>tune</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Attribute
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: "0 0 1rem" }}>
                  An <strong>attribute</strong> is a data property recorded alongside events or traces in the event
                  log. Attributes can provide context that helps explain why guideline violations occur.
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

              {/* ── 9. Process Goal */}
              <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "1rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>flag</span>
                  <h2 style={{ fontSize: "1.125rem", fontWeight: 700, color: C.onSurface, margin: 0 }}>
                    Process Goal
                  </h2>
                </div>
                <p style={{ fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.8, margin: 0 }}>
                  A <strong>process goal</strong> is a desired outcome or objective that a process execution is
                  intended to achieve — for example, successfully shipping an order and receiving payment for it.
                  Guideline violations may affect whether a process goal is reached, and understanding this
                  relationship helps explain the impact of non-conformant behaviour.
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
