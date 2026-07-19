"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";
import ProjectLogo from "../../public/images/logo-no-background.png";

export default function ConsentPage() {
  const router = useRouter();
  const [consentGiven, setConsentGiven] = useState(false);
  const [declined, setDeclined] = useState(false);

  const handleContinue = () => {
    if (consentGiven) router.push("/prequestionnaire");
  };

  const handleDecline = () => {
    setDeclined(true);
  };

  return (
    <div className="bg-surface text-on-surface font-body min-h-screen">

      {/* Decline Popup */}
      {declined && (
        <div style={{
          position: "fixed", top: 0, left: 0, width: "100%", height: "100%",
          backgroundColor: "rgba(0,0,0,0.5)", display: "flex",
          alignItems: "center", justifyContent: "center", zIndex: 100
        }}>
          <div style={{
            backgroundColor: "white", padding: "3rem", borderRadius: "0.75rem",
            maxWidth: "28rem", textAlign: "center", boxShadow: "0 12px 32px rgba(0,0,0,0.2)"
          }}>
            <span className="material-symbols-outlined" style={{ color: "#00305e", fontSize: "3rem", marginBottom: "1rem", display: "block" }}>
              sentiment_neutral
            </span>
            <h2 style={{ color: "#00305e", fontWeight: 700, fontSize: "1.25rem", marginBottom: "1rem" }}>
              Thank you for your time
            </h2>
            <p style={{ color: "#5a6061", lineHeight: 1.6 }}>
              You have chosen not to participate. You can close this page now.
            </p>
          </div>
        </div>
      )}

      {/* Header */}
      <nav style={{
        backgroundColor: "#ffffff",
        position: "fixed", top: 0, zIndex: 50, width: "100%",
        borderBottom: "1px solid #e4e9ea",
        height: "4rem", display: "flex", alignItems: "center",
        boxSizing: "border-box",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", padding: "0 2rem", maxWidth: "56rem", margin: "0 auto" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Image priority src={ProjectLogo} width={90} height={36} alt="ProVi Logo" style={{ objectFit: "contain" }} />
            <Image priority src={UniLogo} width={140} height={36} alt="University of Mannheim Logo" style={{ objectFit: "contain" }} />
          </div>
        </div>
      </nav>

      {/* Main */}
      <main className="pb-32 min-h-screen" style={{ paddingTop: "6rem" }}>
        <div className="max-w-3xl mx-auto px-6">

          {/* Title */}
          <header className="mb-10 text-center">
            <h1 className="font-headline text-3xl font-bold text-primary tracking-tight mb-2">
              Informed Consent
            </h1>
            <p className="text-sm text-on-surface-variant">
              Conformance Checking Experiment
            </p>
          </header>

          {/* Content Card */}
          <div className="bg-white border border-surface-container-high rounded-xl shadow-sm overflow-hidden">
            <div className="p-8 md:p-12 space-y-10">

              {/* Study Purpose */}
              <section>
                <div className="flex items-center gap-3 mb-4">
                  <span className="material-symbols-outlined text-primary">biotech</span>
                  <h2 className="font-headline text-xl font-bold text-on-surface">Study Purpose</h2>
                </div>
                <p className="text-on-surface-variant leading-relaxed">
                  This research study is conducted by the University of Mannheim as part of a quantitative research initiative. The primary purpose is to evaluate how different interface layouts and data visualization idioms affect user comprehension and task performance. Your participation will help us understand the impact of these design choices on information processing.
                </p>
              </section>

              {/* Your Participation */}
              <section>
                <div className="flex items-center gap-3 mb-4">
                  <span className="material-symbols-outlined text-primary">assignment_ind</span>
                  <h2 className="font-headline text-xl font-bold text-on-surface">Your Participation</h2>
                </div>
                <ul className="space-y-3">
                  <li className="flex gap-3 text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm text-primary pt-1">check_circle</span>
                    <span>Participation is entirely voluntary and takes approximately <strong>25–30 minutes</strong>.</span>
                  </li>
                  <li className="flex gap-3 text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm text-primary pt-1">check_circle</span>
                    <span>You will interact with specific visual representations or structural layouts.</span>
                  </li>
                </ul>
              </section>

              {/* Privacy & Data */}
              <section>
                <div className="flex items-center gap-3 mb-4">
                  <span className="material-symbols-outlined text-primary">security</span>
                  <h2 className="font-headline text-xl font-bold text-on-surface">Privacy &amp; Data</h2>
                </div>
                <ul className="space-y-3">
                  <li className="flex gap-3 text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm text-primary pt-1">check_circle</span>
                    <span><strong>Full Anonymization:</strong> No personally identifiable information (PII) is recorded.</span>
                  </li>
                  <li className="flex gap-3 text-on-surface-variant">
                    <span className="material-symbols-outlined text-sm text-primary pt-1">check_circle</span>
                    <span><strong>GDPR Compliance:</strong> Data is stored on secure, encrypted servers at the University of Mannheim for academic research only.</span>
                  </li>
                </ul>
                <p className="text-on-surface-variant leading-relaxed mt-4">
                  For full details on what data is collected and how it is processed, see our{" "}
                  <Link href="/dataprotection" className="text-primary font-semibold underline hover:opacity-80">
                    Data Protection Declaration
                  </Link>.
                </p>
              </section>

              {/* Withdrawal Rights */}
              <section>
                <div className="flex items-center gap-3 mb-4">
                  <span className="material-symbols-outlined text-primary">exit_to_app</span>
                  <h2 className="font-headline text-xl font-bold text-on-surface">Withdrawal Rights</h2>
                </div>
                <p className="text-on-surface-variant leading-relaxed">
                  You have the right to withdraw from this experiment at any time without providing a reason. If you exit the study before completion, no data will be submitted or recorded.
                </p>
              </section>
            </div>

            {/* Decision Area */}
            <div className="bg-surface-container-low p-8 border-t border-surface-container-high">
              <label className="flex items-start gap-4 cursor-pointer group mb-8">
                <div className="relative flex items-center pt-1">
                  <input
                    type="checkbox"
                    id="consent-check"
                    checked={consentGiven}
                    onChange={(e) => setConsentGiven(e.target.checked)}
                    className="h-6 w-6 rounded border-outline-variant text-primary focus:ring-primary focus:ring-offset-0 transition-colors"
                  />
                </div>
                <div className="flex-1">
                  <span className="block font-bold text-on-surface text-base leading-snug group-hover:text-primary transition-colors">
                    I have read and understand the terms of participation and agree to the use of my anonymized data for research purposes.
                  </span>
                  <span className="block text-sm text-on-surface-variant mt-1">
                    By continuing, you also certify that you are over 18 years of age.
                  </span>
                </div>
              </label>

              <div className="flex flex-col sm:flex-row items-center gap-4">
                <button
                  onClick={handleContinue}
                  disabled={!consentGiven}
                  className={`w-full sm:w-auto px-10 py-3 rounded-lg font-bold shadow-md transition-all ${
                    consentGiven
                      ? "bg-primary text-on-primary hover:opacity-90"
                      : "bg-surface-dim text-on-surface-variant cursor-not-allowed"
                  }`}
                >
                  Agree and Continue
                </button>
                <button
                  onClick={handleDecline}
                  className="w-full sm:w-auto px-8 py-3 rounded-lg text-secondary font-semibold hover:bg-surface-container transition-colors"
                >
                  Decline and Exit
                </button>
              </div>
            </div>
          </div>
        </div>
      </main>

    </div>
  );
}