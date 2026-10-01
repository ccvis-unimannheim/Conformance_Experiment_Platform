"use client";

import React from "react";
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

const sectionHeadingStyle = {
  fontFamily: "'Work Sans', 'Inter', sans-serif",
  fontSize: "1.125rem",
  fontWeight: 700,
  color: C.primary,
  marginBottom: "0.75rem",
  letterSpacing: "-0.01em",
};

const paragraphStyle = {
  fontSize: "0.875rem",
  lineHeight: 1.7,
  color: C.onSurface,
  marginBottom: "0.75rem",
};

const dividerStyle = {
  border: "none",
  borderTop: `1px solid ${C.containerHigh}`,
  margin: 0,
};

export default function About() {
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

          {/* ── Page header */}
          <header style={{ marginBottom: "2.5rem", textAlign: "center" }}>
            <h1 style={{
              fontFamily: "'Work Sans', 'Inter', sans-serif",
              fontSize: "1.875rem", fontWeight: 700,
              color: C.primary, letterSpacing: "-0.02em",
              marginBottom: "0.5rem", lineHeight: 1.2,
            }}>
              About ProCon
            </h1>
            <p style={{ fontSize: "0.9375rem", color: C.onVariant, marginTop: "0.75rem" }}>
              Process Conformance Checking Visualizations Research
            </p>
          </header>

          {/* ── Single card with separated sections */}
          <div style={{
            backgroundColor: C.white,
            border: `1px solid ${C.containerHigh}`,
            borderRadius: "0.75rem",
            boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
            overflow: "hidden",
          }}>
            <div style={{ padding: "3rem", display: "flex", flexDirection: "column", gap: "2.5rem" }}>

              {/* About the project */}
              <section>
                <h2 style={sectionHeadingStyle}>About the project</h2>
                <p style={{ ...paragraphStyle, marginBottom: 0 }}>
                  ProCon is a research platform developed at the University of Mannheim to empirically evaluate
                  how different visualization idioms support users in performing conformance checking tasks. It
                  presents participants with conformance checking scenarios and measures how effectively each
                  visualization supports task completion.
                </p>
              </section>

              <hr style={dividerStyle} />

              {/* Goals */}
              <section>
                <h2 style={sectionHeadingStyle}>Goals</h2>
                <p style={{ ...paragraphStyle, marginBottom: 0 }}>
                  The project aims to identify which visualization idioms are most effective for specific
                  conformance checking tasks. From quantifying overall conformance to localizing deviations and
                  diagnosing their causes. Through controlled user studies conducted on this platform, we compare
                  idioms across objective measures (accuracy and speed) and subjective measures (perceived
                  usefulness and ease of use) to provide evidence-based guidance for visualization design in
                  process mining.
                </p>
              </section>

              <hr style={dividerStyle} />

              {/* Further information */}
              <section>
                <h2 style={sectionHeadingStyle}>Further information</h2>
                <p style={{ ...paragraphStyle, marginBottom: 0 }}>
                  For details on data handling, see the{" "}
                  <Link href="/dataprotection" style={{ color: C.primary, textDecoration: "none", fontWeight: 500 }}>
                    Data Protection Declaration
                  </Link>
                  . For information on the publisher, please refer to the{" "}
                  <Link href="/imprint" style={{ color: C.primary, textDecoration: "none", fontWeight: 500 }}>
                    Imprint
                  </Link>
                  .
                </p>
              </section>

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
