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

const sectionCardStyle = {
  backgroundColor: C.white,
  border: `1px solid ${C.containerHigh}`,
  borderRadius: "0.75rem",
  boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
  padding: "2rem",
};

const sectionHeadingStyle = {
  fontFamily: "'Work Sans', 'Inter', sans-serif",
  fontSize: "1.125rem",
  fontWeight: 700,
  color: C.primary,
  marginBottom: "0.75rem",
  letterSpacing: "-0.01em",
};

const linkStyle = {
  color: C.primary,
  textDecoration: "none",
  fontWeight: 500,
};

export default function DataInformation() {
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
              Information on Data Protection<br />according to Art. 13, 14 GDPR
            </h1>
          </header>

          {/* ── Intro paragraph */}
          <p style={{
            fontSize: "0.9375rem", color: C.onSurface, lineHeight: 1.7,
            textAlign: "center", marginBottom: "2.5rem",
            maxWidth: "40rem", margin: "0 auto 2.5rem",
          }}>
            In the following, you will learn which personal data we process for which purposes,
            which legal basis allows us to do so, how long we process the data, to whom the data
            may be disclosed and which rights you can assert.
          </p>
          {/* ── Single card with separated sections */}
          <div style={{
            backgroundColor: C.white,
            border: `1px solid ${C.containerHigh}`,
            borderRadius: "0.75rem",
            boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
            overflow: "hidden",
          }}>
            <div style={{ padding: "3rem", display: "flex", flexDirection: "column", gap: "2.5rem" }}>
 
              {/* Controller & DPO */}
              <section>
                <h2 style={sectionHeadingStyle}>Controller and data protection officer</h2>
                <div style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(auto-fit, minmax(15rem, 1fr))",
                  gap: "1.5rem",
                  fontSize: "0.875rem",
                  lineHeight: 1.6,
                }}>
                  <div>
                    <p style={{ fontWeight: 700, marginBottom: "0.25rem", color: C.onSurface }}>University of Mannheim</p>
                    <p>Schloss</p>
                    <p>68161 Mannheim</p>
                    <p style={{ marginBottom: "0.25rem" }}>Germany</p>
                    <a href="mailto:rektor@uni-mannheim.de" style={linkStyle}>
                      rektor@uni-mannheim.de
                    </a>
                  </div>
                  <div>
                    <p style={{ fontWeight: 700, marginBottom: "0.25rem", color: C.onSurface }}>Jan Morgenstern</p>
                    <p style={{ marginBottom: "0.25rem" }}>
                      Rechtsanwalt und Fachanwalt für IT-Recht, Datenschutzbeauftragter
                    </p>
                    <a href="mailto:datenschutzbeauftragter@uni-mannheim.de" style={linkStyle}>
                      datenschutzbeauftragter@uni-mannheim.de
                    </a>
                  </div>
                </div>
              </section>
 
              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
 
              {/* Purpose */}
              <section>
                <h2 style={sectionHeadingStyle}>
                  Purpose of data processing and possible consequences of failure to provide personal data
                </h2>
                <div style={{ fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface }}>
                  <p style={{ marginBottom: "0.5rem" }}>
                    The personal data will be processed by the University of Mannheim to organize and conduct,
                    including any directly related follow-up work for the ProCon research project.
                  </p>
                  <p style={{ marginBottom: "0.5rem" }}>
                    The participation is not possible without the data.
                  </p>
                  <p>
                    There will be no disadvantages in the event of non-participation.
                  </p>
                </div>
              </section>
 
              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
 
              {/* Type of data */}
              <section>
                <h2 style={sectionHeadingStyle}>Type of data</h2>
                <p style={{ fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface }}>
                  Demographic data (e.g., age or gender), subjective evaluations (e.g., perceived level of difficulty),
                  interaction metrics (e.g., completion time or number of errors), and tracking data (e.g., User Interface tracking).
                </p>
              </section>
 
              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
 
              {/* Legal basis */}
              <section>
                <h2 style={sectionHeadingStyle}>Legal basis</h2>
                <p style={{ fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface }}>
                  The processing of personal data by University of Mannheim is based on consent according to
                  Art. 6 paragraph 1(a) of the General Data Protection Regulation (GDPR).
                </p>
              </section>
 
              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
 
              {/* Recipients */}
              <section>
                <h2 style={sectionHeadingStyle}>Recipients</h2>
                <p style={{ fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface }}>
                  Your personal data will not be transmitted to third parties.
                </p>
              </section>
 
              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
 
              {/* Duration */}
              <section>
                <h2 style={sectionHeadingStyle}>Duration of storage</h2>
                <p style={{ fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface }}>
                  In the case of consent, processing will take place until consent is withdrawn but no later than 31.12.2029.
                </p>
              </section>
 
              <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />
 
              {/* Rights */}
              <section>
                <h2 style={sectionHeadingStyle}>You have rights to</h2>
                <ul style={{
                  fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface,
                  paddingLeft: "1.25rem", margin: 0,
                  display: "flex", flexDirection: "column", gap: "0.5rem",
                }}>
                  <li>
                    Obtain information about your personal data stored by University of Mannheim according to Art. 15 GDPR
                  </li>
                  <li>
                    Obtain from the University of Mannheim without undue delay the rectification of inaccurate personal data
                    or have incomplete personal data completed according to Art. 16 GDPR
                  </li>
                  <li>
                    Obtain from the University of Mannheim the erasure of your personal data according to Art. 17 GDPR
                  </li>
                  <li>
                    Obtain from the University of Mannheim restriction of processing according to Art. 18 GDPR
                  </li>
                  <li>
                    Receive your personal data, which you have provided to University of Mannheim, in a structured,
                    commonly used and machine-readable format and to transmit those data to another controller according to Art. 20 GDPR
                  </li>
                  <li>
                    Furthermore, in case you gave your consent, you have the right to withdraw consent at any time without
                    giving any reason, without affecting the lawfulness of processing based on consent before its withdrawal
                  </li>
                  <li>
                    Lodge a complaint with a supervisory authority (The supervisory authority in Baden-Württemberg is the
                    commissioner for data protection and freedom of information of Baden-Württemberg (Der Landesbeauftragte
                    für Datenschutz und Informationsfreiheit Baden-Württemberg) according to Art. 77 GDPR
                  </li>
                </ul>
 
                <div style={{
                  marginTop: "1.5rem",
                  paddingTop: "1.25rem",
                  borderTop: `1px solid ${C.containerHigh}`,
                  fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface,
                }}>
                  <p>
                    Please contact us to exercise your rights as data subject:{" "}
                    <a href="mailto:anyi.zhu@students.uni-mannheim.de" style={linkStyle}>anyi.zhu@students.uni-mannheim.de</a>
                  </p>
                </div>
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
