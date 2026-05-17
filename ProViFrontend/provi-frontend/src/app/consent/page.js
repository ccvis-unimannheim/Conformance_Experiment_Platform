"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";
import ProjectLogo from "../../public/images/logo-no-background.png";

function logoSrc(imp) {
  if (imp && typeof imp === "object" && "src" in imp) return imp.src;
  return imp;
}

export default function ConsentPage() {
  const router = useRouter();
  const [consentGiven, setConsentGiven] = useState(false);

  const handleContinue = () => {
    if (consentGiven) router.push("/prequestionnaire");
  };

  const handleDecline = () => {
    router.push("/");
  };

  return (
    <div className="bg-surface text-on-surface font-body min-h-screen">

      {/* Header */}
      <header className="bg-white border-b border-outline-variant sticky top-0 z-50">
        <div className="flex justify-between items-center w-full px-8 py-4 max-w-screen-2xl mx-auto">
          <div className="flex items-center gap-8">
            <img src={logoSrc(ProjectLogo)} alt="ProVi Logo" className="h-8 w-auto" />
            <img src={logoSrc(UniLogo)} alt="University of Mannheim Logo" className="h-8 w-auto ml-4 pl-4 border-l border-outline-variant" />
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="pt-12 pb-32 min-h-screen">
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
                    <span>Participation is entirely voluntary and takes approximately <strong>15 minutes</strong>.</span>
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

      {/* Footer */}
      <footer className="fixed bottom-0 left-0 w-full py-4 px-8 bg-surface border-t border-surface-container-high z-40">
        <div className="max-w-4xl mx-auto flex justify-between items-center">
          <span className="text-[10px] text-on-surface-variant font-medium tracking-widest uppercase">
            © University of Mannheim
          </span>
          <div className="flex gap-6 items-center">
            <a href="/imprint" className="text-[10px] text-on-surface-variant hover:text-primary font-medium tracking-widest uppercase">Imprint</a>
            <a href="/dataprotection" className="text-[10px] text-on-surface-variant hover:text-primary font-medium tracking-widest uppercase">Data Protection</a>
          </div>
        </div>
      </footer>

    </div>
  );
}