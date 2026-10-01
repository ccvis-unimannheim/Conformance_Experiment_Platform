"use client";

// Plain <a> tags, not next/link — these point at pages on the MAIN app, and
// next.config.mjs's basePath: "/dfg" would otherwise prefix a next/link href
// with /dfg, sending the browser to a page that doesn't exist in this app.
const Footer = () => {
  return (
    <footer style={{
      position: "fixed", bottom: 0, left: 0, width: "100%",
      padding: "0.75rem 2rem",
      backgroundColor: "rgba(255,255,255,0.85)",
      backdropFilter: "blur(8px)",
      borderTop: "1px solid #e4e9ea",
      zIndex: 40,
      boxSizing: "border-box",
    }}>
      <div style={{
        maxWidth: "56rem", margin: "0 auto",
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span style={{
          fontSize: "10px", color: "#5a6061",
          textTransform: "uppercase", letterSpacing: "0.15em", fontWeight: 500,
        }}>
          © University of Mannheim
        </span>
        <div style={{ display: "flex", gap: "1.5rem" }}>
          {[
            { label: "Imprint",                    href: "/imprint" },
            { label: "About",                      href: "/about" },
            { label: "Data Protection Declaration", href: "/dataprotection" },
          ].map(({ label, href }) => (
            <a key={label} href={href} style={{
              fontSize: "10px", color: "#5a6061",
              textTransform: "uppercase", letterSpacing: "0.15em", fontWeight: 500,
              textDecoration: "none",
            }}>
              {label}
            </a>
          ))}
        </div>
      </div>
    </footer>
  );
};

export default Footer;
