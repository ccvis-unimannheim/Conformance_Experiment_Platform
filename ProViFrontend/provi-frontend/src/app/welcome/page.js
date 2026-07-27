"use client";

import { useRouter } from "next/navigation";
import Image from "next/image";
import HeaderLogos from "../../components/General/HeaderLogos";

const STEPS = [
  {
    num: "01",
    title: "Consent",
    desc: "If you approve of the described procedure, you consent to participate in this survey for the research project.",
  },
  {
    num: "02",
    title: "Knowledge Questions",
    desc: "You will be asked a few knowledge questions about conformance checking.",
  },
  {
    num: "03",
    title: "Concepts & Terms",
    desc: "We will provide definitions of essential terms that are necessary to understand for the survey.",
  },
  {
    num: "04",
    title: "Experiment",
    desc: "We will present you with conformance checking tasks. You will be asked to answer questions with the help of the visualizations you will see. Afterwards, you can optionally share additional feedback.",
  },
  // Feedback Survey step temporarily removed from the structure list while the
  // endpage's NASA-TLX questions are hidden (see endpage/page.js). Restore this
  // alongside those questions when they come back.
  // {
  //   num: "05",
  //   title: "Feedback Survey",
  //   desc: "You will be asked a few short questions about your experience during the experiment, with an option to leave additional feedback.",
  // },
];

export default function WelcomePage() {
  const router = useRouter();

  return (
    <div className="bg-surface text-on-surface font-body min-h-screen">

      {/* Header — matches consent/endpage */}
      <nav style={{
        backgroundColor: "#ffffff",
        position: "fixed", top: 0, zIndex: 50, width: "100%",
        borderBottom: "1px solid #e4e9ea",
        height: "4rem", display: "flex", alignItems: "center",
        boxSizing: "border-box",
      }}>
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          width: "100%", padding: "0 2rem", maxWidth: "56rem", margin: "0 auto",
        }}>
          <HeaderLogos />
        </div>
      </nav>

      {/* Main */}
      <main className="pb-32 min-h-screen" style={{ paddingTop: "6rem" }}>
        <div className="max-w-3xl mx-auto px-6">

          {/* Card */}
          <div className="bg-white border border-surface-container-high rounded-xl shadow-sm overflow-hidden">
            <div className="p-8 md:p-12 space-y-10">

              {/* Hero */}
              <section>
                <h1 className="font-headline text-3xl font-bold text-primary tracking-tight mb-6">
                  Welcome to this Experiment!
                </h1>
                <p className="text-on-surface-variant leading-relaxed">
                  Dear participant,
                </p>
                <p className="text-on-surface-variant leading-relaxed mt-3">
                  We are a team of master&apos;s students conducting this experiment as part of our research project in Process Mining at the University of Mannheim. The purpose of this study is to investigate which visualization idioms best support users in performing conformance checking tasks.
                </p>
                <p className="text-on-surface-variant leading-relaxed mt-3">
                  Your participation is greatly appreciated!
                </p>

                {/* Info chips */}
                <div className="mt-8 flex gap-3 border-t border-outline-variant pt-6">
                  <div className="flex flex-1 items-center justify-center gap-2 bg-surface-container-low border border-outline-variant rounded-lg px-4 py-2.5 text-sm text-on-surface-variant font-medium">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: "1.1rem" }}>schedule</span>
                    <span>Estimated time: <span className="font-bold text-on-surface">20–30 min</span></span>
                  </div>
                  <div className="flex flex-1 items-center justify-center gap-2 bg-surface-container-low border border-outline-variant rounded-lg px-4 py-2.5 text-sm text-on-surface-variant font-medium">
                    <span className="material-symbols-outlined text-primary" style={{ fontSize: "1.1rem" }}>laptop_mac</span>
                    <span>Use a <span className="font-bold text-on-surface">computer or laptop</span></span>
                  </div>
                </div>
              </section>

              {/* Experiment structure */}
              <section>
                <h2 className="font-headline text-xl font-bold text-on-surface mb-4">
                  Experiment Structure
                </h2>

                <div className="divide-y divide-outline-variant" style={{ "--tw-divide-opacity": 0.1 }}>
                  {STEPS.map((s) => (
                    <div key={s.num} className="py-4 flex gap-4 items-start">
                      <span
                        className="font-headline font-bold text-primary shrink-0 text-xs w-7 leading-4"
                        style={{ letterSpacing: "0.15em" }}
                      >
                        {s.num}
                      </span>
                      <div>
                        <h4 className="font-headline text-xs font-bold uppercase tracking-wider text-primary mb-1 leading-4">
                          {s.title}
                        </h4>
                        <p className="text-on-surface-variant leading-relaxed">{s.desc}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              {/* Please note */}
              <div className="border-l-4 border-primary bg-primary-container rounded-r-lg p-5" style={{ "--tw-bg-opacity": 0.1 }}>
                <div className="flex items-center gap-2 mb-1">
                  <span className="material-symbols-outlined text-primary" style={{ fontSize: "1.1rem" }}>info</span>
                  <span className="font-bold text-on-surface text-sm">Please note</span>
                </div>
                <p className="text-on-surface-variant text-sm italic">
                  Once you proceed to the next page, you will not be able to return to the previous one.
                </p>
              </div>

              {/* Thank you */}
              <p className="text-on-surface font-medium italic">
                Thank you in advance for your participation and contribution to research!
              </p>

              {/* Button */}
              <div className="flex justify-center pt-2 pb-2">
                <button
                  onClick={() => router.push("/consent")}
                  className="bg-primary text-on-primary font-headline font-bold px-16 py-4 rounded-lg shadow-md hover:opacity-90 transition-all flex items-center gap-3 text-base"
                >
                  <span>Start</span>
                  <span className="material-symbols-outlined" style={{ fontSize: "1.25rem" }}>arrow_forward</span>
                </button>
              </div>

              {/* Research team */}
              <footer className="pt-6 border-t border-outline-variant text-center" style={{ opacity: 0.55 }}>
                <p className="text-[10px] uppercase tracking-widest text-on-surface-variant mb-2 font-bold">
                  Research Team
                </p>
                <ul className="text-xs text-on-surface-variant leading-relaxed list-none p-0">
                  <li>Anyi Zhu, University of Mannheim</li>
                  <li>Henri Clausnitzer, University of Mannheim</li>
                  <li>Shiqi Zhou, University of Mannheim</li>
                  <li>Tayyaba Zafar, University of Mannheim</li>
                  <li>Zihan Zhang, University of Mannheim</li>
                </ul>
              </footer>

            </div>
          </div>
        </div>
      </main>

      {/* Footer — matches consent/endpage */}
      <footer style={{
        position: "fixed", bottom: 0, left: 0, width: "100%",
        padding: "0.75rem 2rem",
        backgroundColor: "rgba(255,255,255,0.85)",
        backdropFilter: "blur(8px)",
        borderTop: "1px solid #e4e9ea",
        zIndex: 40, boxSizing: "border-box",
      }}>
        <div style={{
          maxWidth: "56rem", margin: "0 auto",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span style={{ fontSize: "10px", color: "#5a6061", textTransform: "uppercase", letterSpacing: "0.15em", fontWeight: 500 }}>
            © University of Mannheim
          </span>
          <div style={{ display: "flex", gap: "1.5rem" }}>
            {[
              { label: "Imprint", href: "/imprint" },
              { label: "About", href: "/about" },
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
    </div>
  );
}
