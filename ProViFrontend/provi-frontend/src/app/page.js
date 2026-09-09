"use client";

import Link from "next/link";
import UniLogo from "../public/images/Logo_UMA_EN_RGB.png";
import ProjectLogo from "../public/images/logo-no-background.png";

function logoSrc(imp) {
  if (imp && typeof imp === "object" && "src" in imp) return imp.src;
  return imp;
}

export default function LandingPage() {
  return (
    <div className="bg-surface text-on-surface font-body min-h-screen flex flex-col">

      {/* Navbar — matches AdminNav exactly, without nav links */}
      <header className="bg-white border-b border-outline-variant sticky top-0 z-50">
        <div className="flex justify-between items-center w-full h-16 px-8 max-w-screen-2xl mx-auto">
          <div className="flex items-center gap-8">
            <img
              src={logoSrc(ProjectLogo)}
              alt="ProVi Logo"
              className="h-11 w-auto"
              width={79}
              height={44}
            />
            <img
              src={logoSrc(UniLogo)}
              alt="University of Mannheim Logo"
              className="h-11 w-auto ml-4 pl-4 border-l border-outline-variant"
              width={110}
              height={44}
            />
          </div>
          <span className="bg-surface-container text-on-surface-variant text-xs font-bold px-3 py-1.5 rounded-lg border border-outline-variant uppercase tracking-wider">
            Admin
          </span>
        </div>
      </header>

      {/* Main */}
      <main style={{
        flexGrow: 1,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "4rem 1.5rem 3rem"
      }}>
        <div style={{ width: "100%", maxWidth: "64rem" }}>

          {/* Hero Card */}
          <div style={{
            backgroundColor: "white",
            padding: "4rem",
            borderRadius: "0.75rem",
            boxShadow: "0 12px 32px rgba(45,52,53,0.06)",
            border: "1px solid rgba(173,179,180,0.15)",
            textAlign: "center",
            position: "relative",
            overflow: "hidden"
          }}>
            {/* Accent bar */}
            <div style={{
              position: "absolute", top: 0, left: 0,
              width: "0.5rem", height: "100%",
              backgroundColor: "rgba(60,95,144,0.2)"
            }} />

            {/* Label */}
            <p style={{
              fontSize: "0.7rem", fontWeight: 700, letterSpacing: "0.2em",
              color: "#3c5f90", textTransform: "uppercase", marginBottom: "1rem"
            }}>
              Research Portal
            </p>

            {/* Title */}
            <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: "1rem", marginBottom: "0.75rem" }}>
              <span className="material-symbols-outlined" style={{ color: "#3c5f90", fontSize: "2.5rem" }}>search</span>
              <h1 style={{ fontSize: "2.5rem", fontWeight: 900, letterSpacing: "-0.025em", color: "#2d3435", margin: 0 }}>
                Process Mining Experiment Platform
              </h1>
            </div>

            <p style={{ color: "#5a6061", fontSize: "1.1rem", maxWidth: "42rem", margin: "0 auto 4rem" }}>
              Interactive study on process mining visualizations.
            </p>

            {/* Cards */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "2rem", textAlign: "left" }}>

              {/* CC Card */}
              <div style={{
                backgroundColor: "#00305e",
                borderRadius: "0.75rem",
                padding: "2rem",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                boxShadow: "0 8px 24px rgba(0,48,94,0.25)"
              }}>
                <div>
                  <h3 style={{ color: "white", fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.75rem" }}>
                    Conformance Checking
                  </h3>
                  <p style={{ color: "rgba(255,255,255,0.85)", fontSize: "0.875rem", lineHeight: 1.6, marginBottom: "2rem" }}>
                    Participate in the study on Conformance Checking visualizations
                  </p>
                </div>
                <Link href="/admin" style={{
                  backgroundColor: "white",
                  color: "#00305e",
                  padding: "0.75rem 1.5rem",
                  borderRadius: "0.5rem",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  textDecoration: "none"
                }}>
                  <span>Start Experiment</span>
                  <span className="material-symbols-outlined" style={{ fontSize: "1rem" }}>play_arrow</span>
                </Link>
              </div>

              {/* DFG Card */}
              <div style={{
                backgroundColor: "#00305e",
                borderRadius: "0.75rem",
                padding: "2rem",
                display: "flex",
                flexDirection: "column",
                justifyContent: "space-between",
                boxShadow: "0 8px 24px rgba(0,48,94,0.25)"
              }}>
                <div>
                  <h3 style={{ color: "white", fontSize: "1.5rem", fontWeight: 700, marginBottom: "0.75rem" }}>
                    Directly-Follows-Graph
                  </h3>
                  <p style={{ color: "rgba(255,255,255,0.85)", fontSize: "0.875rem", lineHeight: 1.6, marginBottom: "2rem" }}>
                    Participate in the study on Directly-Follows-graph visualizations
                  </p>
                </div>
                <a href="https://pm-vis.uni-mannheim.de/admin" target="_blank" rel="noopener noreferrer" style={{
                  backgroundColor: "white",
                  color: "#00305e",
                  padding: "0.75rem 1.5rem",
                  borderRadius: "0.5rem",
                  fontWeight: 600,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  textDecoration: "none"
                }}>
                  <span>Start Experiment</span>
                  <span className="material-symbols-outlined" style={{ fontSize: "1rem" }}>play_arrow</span>
                </a>
              </div>

            </div>

            {/* Footer context */}
            <div style={{
              marginTop: "4rem",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: "1.5rem",
              opacity: 0.6
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span className="material-symbols-outlined" style={{ fontSize: "1rem" }}>verified_user</span>
                <span style={{ fontSize: "0.75rem" }}>IRB Approved</span>
              </div>
              <div style={{ width: "1px", height: "1rem", backgroundColor: "#adb3b4" }} />
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <span className="material-symbols-outlined" style={{ fontSize: "1rem" }}>database</span>
                <span style={{ fontSize: "0.75rem" }}>Anonymized Data Processing</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}