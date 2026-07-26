"use client";

import React, { useState, useEffect, useRef } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";

import HeaderLogos from "../../components/General/HeaderLogos";

// ── Design tokens (from test.html color palette)
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

const GENDER_OPTIONS = [
  "Female",
  "Male",
  "Non-binary",
  "Prefer not to say",
];


const EDUCATION_OPTIONS = [
  "Undergraduate / Bachelor",
  "Master",
  "Doctorate / PhD",
  "Other",
];

const ROLE_OPTIONS = [
  "Student",
  "Researcher / Academic",
  "Industry Professional",
  "Other",
];

const TOOL_OPTIONS = [
  "Celonis", "Disco (Fluxicon)", "ProM", "PM4Py",
  "Apromore", "SAP Signavio", "None / I have not used process mining tools yet",
];

const RATING_FIELDS = [
  { key: "businessProcessManagement", label: "Business Process Management" },
  { key: "processMining",             label: "Process Mining" },
  { key: "conformanceChecking",       label: "Conformance Checking" },
];

// ── n-column grid option button (education / role / gender / age)
function OptionGrid({ options, value, onChange, columns = 4 }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: `repeat(${columns}, 1fr)`, gap: "0.75rem" }}>
      {options.map((opt) => {
        const active = value === opt;
        return (
          <button
            key={opt}
            type="button"
            onClick={() => onChange(opt)}
            style={{
              padding: "0.75rem 0.5rem",
              borderRadius: "0.5rem",
              border: active
                ? `1px solid ${C.primary}`
                : `1px solid ${C.containerHigh}`,
              backgroundColor: active ? "rgba(0,48,94,0.05)" : C.white,
              color: active ? C.primary : C.onSurface,
              boxShadow: active ? `inset 0 0 0 1px ${C.primary}` : "none",
              fontSize: "0.75rem",
              fontWeight: 600,
              cursor: "pointer",
              textAlign: "center",
              lineHeight: 1.4,
              transition: "all 0.15s ease",
            }}
          >
            {opt}
          </button>
        );
      })}
    </div>
  );
}

// ── Rating row: label left, 1-5 buttons right
function RatingRow({ label, value, onChange }) {
  return (
    <div style={{
      display: "flex", alignItems: "center",
      justifyContent: "space-between", gap: "1rem",
    }}>
      <span style={{ fontSize: "0.875rem", fontWeight: 600, color: C.onSurface, minWidth: "12rem" }}>
        {label}
      </span>
      <div style={{ display: "flex", gap: "0.5rem" }}>
        {[1, 2, 3, 4, 5].map((n) => {
          const active = value === n;
          return (
            <button
              key={n}
              type="button"
              onClick={() => onChange(n)}
              style={{
                width: "2.5rem", height: "2.5rem",
                borderRadius: "0.25rem",
                border: active ? `1px solid ${C.primary}` : `1px solid ${C.containerHigh}`,
                backgroundColor: active ? C.primary : C.white,
                color: active ? C.white : C.onSurface,
                fontWeight: 700,
                fontSize: "0.875rem",
                cursor: "pointer",
                display: "flex", alignItems: "center", justifyContent: "center",
                transition: "all 0.15s ease",
                flexShrink: 0,
              }}
            >
              {n}
            </button>
          );
        })}
      </div>
    </div>
  );
}

const fieldLabelStyle = {
  fontSize: "0.75rem", fontWeight: 700,
  textTransform: "uppercase", letterSpacing: "0.1em",
  color: C.onVariant, display: "block", marginBottom: "1rem",
};

const sectionHeadStyle = {
  fontSize: "1.25rem", fontWeight: 700,
  color: C.onSurface, margin: 0,
};

const ALL_SECTION_KEYS = ["personal_info", "academic_profile", "technical_expertise", "tool_experience"];

export default function PrequestionnaireComponent() {
  const router = useRouter();

  const [enabledSections, setEnabledSections] = useState(new Set(ALL_SECTION_KEYS));
  // While the enabled sections are being fetched we render nothing, so a page
  // with no sections is never shown before the auto-skip kicks in.
  const [loading, setLoading] = useState(true);

  const [gender,       setGender]       = useState("");
  const [age,          setAge]          = useState("");
  const [education,    setEducation]    = useState("");
  const [role,         setRole]         = useState("");
  const [fieldOfStudy, setFieldOfStudy] = useState("");
  const [ratings, setRatings] = useState({
    businessProcessManagement: 0,
    processMining:             0,
    conformanceChecking:       0,
  });
  const [yearsExp,    setYearsExp]    = useState(0);
  const [tools,       setTools]       = useState([]);
  const [error,       setError]       = useState(null);
  const [submitting,  setSubmitting]  = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/participant/prequestionnaire-sections")
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (cancelled) return;
        if (data?.sections) setEnabledSections(new Set(data.sections));
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const toggleTool = (tool) =>
    setTools((prev) =>
      prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]
    );

  const show = (key) => enabledSections.has(key);

  const isValid =
    (!show("personal_info")    || (gender !== "" && /^\d+$/.test(age) && parseInt(age, 10) >= 1)) &&
    (!show("academic_profile") || (education !== "" && role !== "" && fieldOfStudy.trim() !== "")) &&
    (!show("technical_expertise") || (ratings.businessProcessManagement > 0 && ratings.processMining > 0 && ratings.conformanceChecking > 0));

  const handleContinue = async () => {
    if (!isValid) {
      setError("Please complete all fields before continuing.");
      return;
    }
    setError(null);
    setSubmitting(true);
    try {
      const payload = {
        gender,
        age_range: String(age),
        education,
        role,
        field_of_study: fieldOfStudy,
        rating_business_process_management: ratings.businessProcessManagement,
        rating_process_mining:              ratings.processMining,
        rating_conformance_checking:        ratings.conformanceChecking,
        years_experience: yearsExp,
        tools,
      };
      const res = await fetch("/api/auth/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        setError("Submission failed. Please try again.");
        return;
      }
      router.push("/knowledgequestion");
    } catch {
      setError("Network error. Please check your connection and try again.");
    } finally {
      setSubmitting(false);
    }
  };

  const setRating = (key, val) =>
    setRatings((prev) => ({ ...prev, [key]: val }));

  // If the experiment has no enabled sections, don't show an empty page:
  // submit the (empty) background once — which still creates the user and
  // sets the auth cookie — then move straight on to the knowledge questions.
  const autoSkippedRef = useRef(false);
  useEffect(() => {
    if (loading || autoSkippedRef.current) return;
    if (enabledSections.size === 0) {
      autoSkippedRef.current = true;
      handleContinue();
    }
  }, [loading, enabledSections]); // eslint-disable-line react-hooks/exhaustive-deps

  // Render nothing while sections load, or while auto-skipping an empty page,
  // so the participant never sees a blank form. If the auto-submit fails they
  // get an error with a retry instead of being stuck.
  if (loading || enabledSections.size === 0) {
    return (
      <div style={{
        backgroundColor: C.surface, color: C.onVariant, minHeight: "100vh",
        display: "flex", alignItems: "center", justifyContent: "center",
        flexDirection: "column", gap: "1rem", padding: "1.5rem",
        fontFamily: "'Inter', Arial, sans-serif", textAlign: "center",
      }}>
        {error ? (
          <>
            <p style={{ color: "#dc2626", fontSize: "0.875rem", fontWeight: 500 }}>{error}</p>
            <button
              type="button"
              onClick={handleContinue}
              disabled={submitting}
              style={{
                padding: "0.75rem 2rem", borderRadius: "0.5rem", border: "none",
                backgroundColor: C.primary, color: C.white, fontWeight: 700,
                fontSize: "0.875rem", cursor: submitting ? "not-allowed" : "pointer",
              }}
            >
              {submitting ? "Retrying…" : "Retry"}
            </button>
          </>
        ) : (
          <p style={{ fontSize: "0.875rem" }}>Loading…</p>
        )}
      </div>
    );
  }

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

          {/* Centered page header */}
          <header style={{ marginBottom: "2.5rem", textAlign: "center" }}>
            <h1 style={{
              fontFamily: "'Work Sans', 'Inter', sans-serif",
              fontSize: "1.875rem", fontWeight: 700,
              color: C.primary, letterSpacing: "-0.02em", marginBottom: "0.5rem",
            }}>
              Participant Background
            </h1>
            <p style={{ fontSize: "0.875rem", color: C.onVariant }}>
              Please provide your details to help us contextualize the results.
            </p>
          </header>

          {/* ── Card */}
          <div style={{
            backgroundColor: C.white,
            border: `1px solid ${C.containerHigh}`,
            borderRadius: "0.75rem",
            boxShadow: "0 1px 4px rgba(45,52,53,0.06)",
            overflow: "hidden",
          }}>
            <div style={{ padding: "3rem", display: "flex", flexDirection: "column", gap: "3rem" }}>

              {/* ── Personal Information */}
              {show("personal_info") && <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>person</span>
                  <h2 style={sectionHeadStyle}>Personal Information</h2>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                  {/* Gender */}
                  <div>
                    <label style={fieldLabelStyle}>Gender</label>
                    <OptionGrid options={GENDER_OPTIONS} value={gender} onChange={setGender} columns={4} />
                  </div>

                  {/* Age */}
                  <div>
                    <label style={fieldLabelStyle}>Age</label>
                    <input
                      type="number"
                      min={1}
                      max={120}
                      step={1}
                      value={age}
                      onChange={(e) => {
                        const v = e.target.value;
                        if (v === "" || /^\d+$/.test(v)) setAge(v);
                      }}
                      placeholder="Enter your age"
                      style={{
                        width: "10rem",
                        padding: "0.75rem 1rem",
                        border: `1px solid ${C.containerHigh}`,
                        borderRadius: "0.5rem",
                        fontSize: "0.875rem",
                        color: C.onSurface,
                        backgroundColor: C.white,
                        outline: "none",
                        fontFamily: "inherit",
                        boxSizing: "border-box",
                        transition: "border-color 0.15s ease",
                        MozAppearance: "textfield",
                      }}
                      onFocus={(e) => { e.target.style.borderColor = C.primary; e.target.style.boxShadow = `0 0 0 1px ${C.primary}`; }}
                      onBlur={(e)  => { e.target.style.borderColor = C.containerHigh; e.target.style.boxShadow = "none"; }}
                    />
                  </div>
                </div>
              </section>}

              {/* ── Divider */}
              {show("personal_info") && show("academic_profile") && <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />}

              {/* ── Academic Profile */}
              {show("academic_profile") && <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>school</span>
                  <h2 style={sectionHeadStyle}>Academic Profile</h2>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                  {/* Education */}
                  <div>
                    <label style={fieldLabelStyle}>Highest Education Level</label>
                    <OptionGrid options={EDUCATION_OPTIONS} value={education} onChange={setEducation} />
                  </div>

                  {/* Role */}
                  <div>
                    <label style={fieldLabelStyle}>Current Role</label>
                    <OptionGrid options={ROLE_OPTIONS} value={role} onChange={setRole} />
                  </div>

                  {/* Field of study */}
                  <div>
                    <label style={fieldLabelStyle} htmlFor="field-study">
                      Primary Field of Study / Work
                    </label>
                    <input
                      id="field-study"
                      type="text"
                      value={fieldOfStudy}
                      onChange={(e) => setFieldOfStudy(e.target.value)}
                      placeholder="e.g. Information Systems, Computer Science, Business Administration"
                      style={{
                        width: "100%",
                        padding: "0.75rem 1rem",
                        border: `1px solid ${C.containerHigh}`,
                        borderRadius: "0.5rem",
                        fontSize: "0.875rem",
                        color: C.onSurface,
                        backgroundColor: C.white,
                        outline: "none",
                        fontFamily: "inherit",
                        boxSizing: "border-box",
                        transition: "border-color 0.15s ease",
                      }}
                      onFocus={(e) => { e.target.style.borderColor = C.primary; e.target.style.boxShadow = `0 0 0 1px ${C.primary}`; }}
                      onBlur={(e)  => { e.target.style.borderColor = C.containerHigh; e.target.style.boxShadow = "none"; }}
                    />
                    <p style={{ fontSize: "10px", color: C.onVariant, fontStyle: "italic", marginTop: "0.5rem" }}>
                      Please specify your main research or professional domain.
                    </p>
                  </div>
                </div>
              </section>}

              {/* ── Divider */}
              {show("academic_profile") && show("technical_expertise") && <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />}

              {/* ── Technical Expertise */}
              {show("technical_expertise") && <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>analytics</span>
                  <h2 style={sectionHeadStyle}>Technical Expertise</h2>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "2.5rem" }}>
                  {/* Ratings */}
                  <div>
                    <p style={{ ...fieldLabelStyle, marginBottom: "1.5rem" }}>
                      Rate your familiarity with the following (1 = Novice, 5 = Expert)
                    </p>
                    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                      {RATING_FIELDS.map(({ key, label }) => (
                        <RatingRow
                          key={key}
                          label={label}
                          value={ratings[key]}
                          onChange={(val) => setRating(key, val)}
                        />
                      ))}
                    </div>
                  </div>

                  {/* Slider */}
                  <div>
                    <label style={fieldLabelStyle}>Years of Relevant Experience in Process Management & Analytics</label>
                    <div style={{ display: "flex", alignItems: "center", gap: "1.5rem" }}>
                      <input
                        type="range"
                        min={0}
                        max={50}
                        value={yearsExp}
                        onChange={(e) => setYearsExp(Number(e.target.value))}
                        style={{
                          flex: 1,
                          height: "4px",
                          accentColor: C.primary,
                          cursor: "pointer",
                          appearance: "none",
                          backgroundColor: C.container,
                          borderRadius: "9999px",
                        }}
                      />
                      <input
                        type="number"
                        min={0}
                        max={50}
                        step={1}
                        value={yearsExp}
                        onChange={(e) => {
                          const v = parseInt(e.target.value, 10);
                          setYearsExp(isNaN(v) ? 0 : Math.min(50, Math.max(0, v)));
                        }}
                        style={{
                          width: "4rem", height: "2.5rem",
                          borderRadius: "0.5rem",
                          backgroundColor: C.containerLow,
                          border: `1px solid ${C.containerHigh}`,
                          textAlign: "center",
                          fontWeight: 700, fontSize: "0.875rem", color: C.primary,
                          flexShrink: 0,
                          outline: "none",
                          cursor: "text",
                          MozAppearance: "textfield",
                        }}
                      />
                    </div>
                    <p style={{ fontSize: "10px", color: C.onVariant, fontStyle: "italic", marginTop: "0.75rem" }}>
                      Including internships, research projects, and professional work.
                    </p>
                  </div>
                </div>
              </section>}

              {/* ── Divider */}
              {show("technical_expertise") && show("tool_experience") && <hr style={{ border: "none", borderTop: `1px solid ${C.containerHigh}`, margin: 0 }} />}

              {/* ── Tool Experience */}
              {show("tool_experience") && <section>
                <div style={{ display: "flex", alignItems: "center", gap: "0.75rem", marginBottom: "2rem" }}>
                  <span className="material-symbols-outlined" style={{ color: C.primary, fontSize: "1.5rem" }}>build</span>
                  <h2 style={sectionHeadStyle}>Tool Experience</h2>
                </div>
                <label style={fieldLabelStyle}>
                  Which of the following process mining tools have you used in a professional or academic setting? (Select all that apply)
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "0.625rem" }}>
                  {TOOL_OPTIONS.map((tool) => {
                    const checked = tools.includes(tool);
                    const fullWidth = tool === "None / I have not used process mining tools yet";
                    return (
                      <div
                        key={tool}
                        onClick={() => toggleTool(tool)}
                        style={{
                          gridColumn: fullWidth ? "1 / -1" : undefined,
                          display: "flex", alignItems: "center", gap: "0.75rem",
                          padding: "1rem 1.25rem",
                          borderRadius: "0.5rem",
                          border: checked ? `1px solid ${C.primary}` : `1px solid ${C.containerHigh}`,
                          backgroundColor: checked ? "rgba(0,48,94,0.05)" : C.white,
                          cursor: "pointer",
                          transition: "all 0.15s ease",
                          boxShadow: checked ? `inset 0 0 0 1px ${C.primary}` : "none",
                        }}
                      >
                        <div style={{
                          width: "1rem", height: "1rem", borderRadius: "0.2rem", flexShrink: 0,
                          border: checked ? `2px solid ${C.primary}` : `2px solid ${C.outlineVar}`,
                          backgroundColor: checked ? C.primary : C.white,
                          display: "flex", alignItems: "center", justifyContent: "center",
                          transition: "all 0.15s ease",
                        }}>
                          {checked && (
                            <span className="material-symbols-outlined" style={{ color: C.white, fontSize: "0.75rem", fontVariationSettings: "'FILL' 1" }}>
                              check
                            </span>
                          )}
                        </div>
                        <span style={{ fontSize: "0.875rem", fontWeight: 500, color: checked ? C.primary : C.onSurface }}>
                          {tool}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </section>}
            </div>

            {/* ── CTA area (inside card, separate bg) */}
            <div style={{
              backgroundColor: C.containerLow,
              borderTop: `1px solid ${C.containerHigh}`,
              padding: "2rem 3rem",
              display: "flex", justifyContent: "space-between", alignItems: "center", gap: "1rem",
            }}>
              <button
                type="button"
                onClick={() => router.push("/dataprotection")}
                style={{
                  padding: "0.75rem 2rem",
                  borderRadius: "0.5rem",
                  border: "none",
                  backgroundColor: "transparent",
                  color: C.onVariant,
                  fontWeight: 600,
                  fontSize: "0.875rem",
                  cursor: "pointer",
                  display: "flex", alignItems: "center", gap: "0.5rem",
                  transition: "background-color 0.15s ease",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = C.container; }}
                onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = "transparent"; }}
              >
                <span className="material-symbols-outlined" style={{ fontSize: "1.1rem" }}>arrow_back</span>
                Previous Step
              </button>

              <button
                type="button"
                onClick={handleContinue}
                disabled={submitting}
                style={{
                  padding: "0.75rem 2.5rem",
                  borderRadius: "0.5rem",
                  border: "none",
                  backgroundColor: isValid && !submitting ? C.primary : C.outlineVar,
                  color: C.white,
                  fontWeight: 700,
                  fontSize: "0.875rem",
                  cursor: isValid && !submitting ? "pointer" : "not-allowed",
                  boxShadow: isValid && !submitting ? "0 2px 8px rgba(0,48,94,0.25)" : "none",
                  display: "flex", alignItems: "center", gap: "0.5rem",
                  transition: "all 0.15s ease",
                }}
              >
                {submitting ? "Submitting…" : "Continue to Knowledge Questions"}
                <span className="material-symbols-outlined" style={{ fontSize: "1.1rem" }}>arrow_forward</span>
              </button>
            </div>
          </div>

          {/* Error banner (below card) */}
          {error && (
            <div style={{
              marginTop: "1rem",
              padding: "0.875rem 1.25rem",
              backgroundColor: "#fef2f2",
              border: "1px solid #fecaca",
              borderRadius: "0.5rem",
              color: "#dc2626",
              fontSize: "0.875rem",
              fontWeight: 500,
            }}>
              {error}
            </div>
          )}

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
              { label: "About",                        href: "/about" },
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
