"use client";

import React, { useState, useEffect } from "react";
import Head from "next/head";

import GraphVisualComponent from "../components/Graph/GraphVisualComponent";
import QuestionnaireComponent from "../components/Questionnaire/QuestionnaireComponent";
import ExpNavigation from "../components/General/ExpNavigation";
import { UITrackingProvider } from "../utils/usertracking";

// The backend assigns a dataset per participant via the `dfg_user_id` cookie.
// Reuse an existing session so a reload does not count as a new participant;
// otherwise start one. Every /vis and /survey call needs the cookie, so the
// graph and questionnaire only mount once this has finished.
const startSession = async () => {
  const check = await fetch("/dfg/api/auth/test", { credentials: "include" });
  if (check.ok && (await check.json()).user_id) return;

  const response = await fetch("/dfg/api/auth/", {
    method: "POST",
    credentials: "include",
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.message || `Could not start a session (${response.status}).`);
  }
};

export default function Home() {
  const [zoomResetTrigger, setZoomResetTrigger] = useState(0);
  const [sessionReady, setSessionReady] = useState(false);
  const [sessionError, setSessionError] = useState("");

  useEffect(() => {
    startSession()
      .then(() => setSessionReady(true))
      .catch((error) => setSessionError(error.message));
  }, []);

  useEffect(() => {
    const handleBeforeUnload = (e) => {
      e.preventDefault();
      // This message might not be displayed in some browsers as they show their own custom message
      e.returnValue = "";
      return e.returnValue;
    };

    // Add event listener
    window.addEventListener("beforeunload", handleBeforeUnload);

    // Cleanup function
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
    };
  }, []);

  const handleQuestionSubmit = () => {
    setZoomResetTrigger((prev) => prev + 1); // Increment to trigger zoom reset
  };

  const [showPrePage, setShowPrePage] = useState(true);

  const handleStartExperiment = () => {
    setShowPrePage(false);
  };
  return (
    <div className="flex flex-col min-h-screen bg-gray-100">
      <Head>
        <title>ProVi - Directly Follows Graph</title>
      </Head>

      {/* Navigation Bar */}
      <ExpNavigation />
      {/* Main Content */}
      {sessionError ? (
        <main className="flex-grow p-8">
          <p className="p-4 text-red-700 bg-red-100 rounded-md">{sessionError}</p>
        </main>
      ) : !sessionReady ? (
        <main className="flex items-center justify-center flex-grow p-8">
          <p>Starting session...</p>
        </main>
      ) : (
        <main className="flex-grow p-8 grid grid-cols-1 gap-8 md:grid-cols-[2fr_1fr]">
          {/* Left : DFG Graph + Sliders */}
          <UITrackingProvider>
            <div className="h-full">
              <GraphVisualComponent zoomResetTrigger={zoomResetTrigger} />
            </div>

            {/* Right: Questionnaire */}
            <div className="flex flex-col gap-8">
              <QuestionnaireComponent onQuestionSubmit={handleQuestionSubmit} />
            </div>
          </UITrackingProvider>
        </main>
      )}
    </div>
  );
}
