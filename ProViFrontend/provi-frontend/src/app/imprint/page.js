"use client";

import React from "react";
import Image from "next/image";
import Link from "next/link";

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

const SOCIAL_LINKS = [
  { label: "Instagram", url: "https://www.instagram.com/uni_mannheim/",         display: "instagram.com/uni_mannheim" },
  { label: "TikTok",    url: "https://www.tiktok.com/@uni_mannheim",            display: "tiktok.com/@uni_mannheim" },
  { label: "LinkedIn",  url: "https://de.linkedin.com/school/university-of-mannheim/", display: "linkedin.com/school/university-of-mannheim" },
  { label: "Facebook",  url: "https://www.facebook.com/UniMannheim",            display: "facebook.com/UniMannheim" },
  { label: "Mastodon",  url: "https://bawü.social/@unimannheim",                display: "bawü.social/@unimannheim" },
  { label: "YouTube",   url: "https://www.youtube.com/@unimannheim",            display: "youtube.com/@unimannheim" },
];

export default function Imprint() {
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

          {/* ── Page header */}
          <header style={{ marginBottom: "2.5rem", textAlign: "center" }}>
            <h1 style={{
              fontFamily: "'Work Sans', 'Inter', sans-serif",
              fontSize: "1.875rem", fontWeight: 700,
              color: C.primary, letterSpacing: "-0.02em",
              marginBottom: "0.5rem", lineHeight: 1.2,
            }}>
              About This Site
            </h1>
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

              {/* Publisher */}
              <section>
                <h2 style={sectionHeadingStyle}>This website is published by</h2>
                <p style={paragraphStyle}>
                  University of Mannheim<br />
                  Schloss<br />
                  68161 Mannheim<br />
                  Tel. 0621/181-2222
                </p>
                <p style={paragraphStyle}>
                  E-Mail:{" "}
                  <a href="mailto:impressum@uni-mannheim.de" style={linkStyle}>impressum@uni-mannheim.de</a>
                  <br />
                  Internet:{" "}
                  <a href="https://www.uni-mannheim.de" style={linkStyle} target="_blank" rel="noreferrer">
                    https://www.uni-mannheim.de
                  </a>
                </p>
                <p style={paragraphStyle}>
                  According to section 1 and section 8 subsection 1 of the act on the higher education institutions
                  in the Land of Baden-Württemberg (Landeshochschulgesetz, LHG), the University of Mannheim is a body
                  governed by public law. The university is represented by the President.
                </p>
                <p style={{ ...paragraphStyle, marginBottom: 0 }}>
                  VAT identification number (pursuant to Section 27a of the German Value Added Tax Act): DE 143845342
                </p>
              </section>

              <hr style={dividerStyle} />

              {/* Responsibility */}
              <section>
                <h2 style={sectionHeadingStyle}>Responsible in terms of content</h2>
                <p style={paragraphStyle}>
                  The Marketing and Communications departments in the President&apos;s Office manage the contents
                  of the central websites.
                </p>
                <p style={paragraphStyle}>
                  The responsibility for journalistic and editorial contents lies with:
                </p>
                <p style={paragraphStyle}>
                  Dr. Andreas Margara (Head of the Marketing Department)
                </p>
                <p style={{ ...paragraphStyle, marginBottom: 0 }}>
                  University of Mannheim<br />
                  Rectorate, Marketing Department<br />
                  Schloss Ostflügel<br />
                  68161 Mannheim
                </p>
              </section>

              <hr style={dividerStyle} />

              {/* Copyright */}
              <section>
                <h2 style={sectionHeadingStyle}>Copyright information</h2>
                <p style={{ ...paragraphStyle, marginBottom: 0 }}>
                  The texts, images, photographs, videos or graphics as well as the layout of our website are
                  protected by copyright law. The webpages may be copied for private use only. Any other use
                  (in particular the distribution of copies or changes to the content) is prohibited unless
                  otherwise specified. If you intend to use the website or parts thereof, please contact us
                  in advance via the details above.
                </p>
              </section>

              <hr style={dividerStyle} />

              {/* Social media */}
              <section>
                <h2 style={sectionHeadingStyle}>Social media profiles</h2>
                <ul style={{
                  fontSize: "0.875rem", lineHeight: 1.7, color: C.onSurface,
                  paddingLeft: "1.25rem", margin: 0,
                  display: "flex", flexDirection: "column", gap: "0.5rem",
                }}>
                  {SOCIAL_LINKS.map(({ label, url, display }) => (
                    <li key={label}>
                      <em style={{ color: C.onVariant }}>{label}</em>:{" "}
                      <a href={url} style={linkStyle} target="_blank" rel="noreferrer">
                        {display}
                      </a>
                    </li>
                  ))}
                </ul>
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
