"use client";

import Link from "next/link";

/**
 * The setup wizard's steps, as a bar every step shows.
 *
 * Each step used to link only to its neighbour, so returning to the first one
 * from the last meant pressing "Previous Step" eight times — and an experiment
 * built from a zip could not get back at all, since the step it skips sent it
 * forward again. Any step already reachable is a link here.
 *
 * `current` is the slug of the page rendering it; without an `experimentId`
 * (a brand-new experiment that has not been created yet) the steps are shown
 * but inert, since there is no draft to open them for.
 */
const STEPS = [
  { slug: "new", label: "Details" },
  { slug: "prequestionnaire", label: "Pre-questionnaire" },
  { slug: "knowledge", label: "Knowledge" },
  { slug: "concepts", label: "Intro pages" },
  { slug: "task", label: "Tasks" },
  { slug: "idiom", label: "Idioms" },
  { slug: "specify", label: "Specify" },
  { slug: "answer-format", label: "Answer format" },
  { slug: "overview", label: "Overview" },
];

export default function WizardSteps({ experimentId, current, bundleOnly = false }) {
  // A bundle experiment generates nothing, so it has no Specify step at all.
  const steps = bundleOnly ? STEPS.filter((s) => s.slug !== "specify") : STEPS;

  return (
    <nav
      aria-label="Experiment setup steps"
      className="bg-surface-container-lowest border-b border-border-subtle"
    >
      <div className="max-w-screen-2xl mx-auto px-8 py-2 flex flex-wrap items-center gap-x-1 gap-y-1">
        {steps.map((step, i) => {
          const isCurrent = step.slug === current;
          const href = `/admin/experiments/${step.slug}${
            experimentId ? `?experiment_id=${encodeURIComponent(experimentId)}` : ""
          }`;
          return (
            <span key={step.slug} className="flex items-center gap-1">
              {i > 0 && <span className="text-on-surface-variant/40 text-xs">›</span>}
              {isCurrent || !experimentId ? (
                <span
                  aria-current={isCurrent ? "step" : undefined}
                  className={`text-xs px-2 py-1 rounded ${
                    isCurrent
                      ? "font-semibold text-primary bg-primary/5"
                      : "text-on-surface-variant/50"
                  }`}
                >
                  {step.label}
                </span>
              ) : (
                <Link
                  href={href}
                  className="text-xs px-2 py-1 rounded text-on-surface-variant hover:text-primary hover:bg-surface-container transition-colors"
                >
                  {step.label}
                </Link>
              )}
            </span>
          );
        })}
      </div>
    </nav>
  );
}
