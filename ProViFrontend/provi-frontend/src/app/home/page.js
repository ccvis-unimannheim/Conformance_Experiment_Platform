"use client";

import React, { useState, useEffect } from "react";
import Head from "next/head";

import GraphVisualComponent from "../../components/Graph/GraphVisualComponent";
import QuestionnaireComponent from "../../components/Questionnaire/QuestionnaireComponent";
import ExpNavigation from "../../components/General/ExpNavigation";
import { UITrackingProvider } from "../../utils/usertracking";

export default function Home() {
  const [zoomResetTrigger, setZoomResetTrigger] = useState(0);
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
    </div>
  );
}
