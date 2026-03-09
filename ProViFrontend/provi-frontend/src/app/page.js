"use client";

import React, { useState } from "react";
import { useRouter } from "next/navigation";
import AlertPopup from "../components/Questionnaire/AlertPopup";
import ScrollProgressBar from "../components/WelcomePage/ScrollProgressBar";
import Timeline from "../public/images/Timeline_Experiment.png";
import Image from "next/image";
import ExpNavigation from "../components/General/ExpNavigation";

import "@coreui/coreui/dist/css/coreui.min.css";

export default function WelcomeComponent() {
  const router = useRouter();
  const [consentGiven, setConsentGiven] = useState(false);
  const [showModal, setShowModal] = useState(false); // Modal visibility
  const [alertMessage, setAlertMessage] = useState(""); // sets alertMessage
  const [authMessage, setAuthMessage] = useState("");
  

  const handleConsentChange = (e) => {
    setConsentGiven(e.target.checked);
  };

  const handleSubmit = async (e) => {
    if (!consentGiven) {
      setAlertMessage("Please give your consent to proceed.");
      setShowModal(true);
      return;
    }

    router.push("/prequestionnaire");
  };

  return (
    <div className="">
      <ExpNavigation />
    
      <div className="flex flex-col items-center justify-center w-3/5 h-auto gap-10 p-10 mx-auto rounded-lg shadow-xl bg-gray-50 my-10">
        <ScrollProgressBar />
        <h1 className="text-3xl font-bold">Process Visualization Experiment</h1>
        

        <AlertPopup
          visible={showModal}
          message={alertMessage}
          onClose={() => setShowModal(false)}
        />

        <p className="text-xl text-left">
          Dear Participant,
          <br />
          <br />
          My name is Marie-Christin Häge, and I am conducting this experiment as
          part of my PhD. The purpose of this study is to investigate Process
          Mining Visualizations. Your participation is greatly appreciated and 
          will take around 20-30 minutes to complete. Please use a computer or 
          laptop to conduct this experiment, as a larger display is helpful for a proper execution.
          <br />
          <br />
          The survey is structured in 4 parts: 
          </p>

        <div className="my-6 flex justify-center">
          <Image
                      priority
                      src={Timeline}
                      width={1000}
                      height={600}
                      alt="Project Logo"
                    />
        </div>

        <p className="text-xl text-left">
          <br />
          1) <strong>Consent:</strong> If you approve of the described procedure, you consent to 
          participate in this experiment for the Process Mining Visualizations (ProVi) research project.
          <br />
          <br />
          2) <strong>Pre-Experiment Questions:</strong> You will be presented with general questions and questions on Process
          Mining.
          <br />
          <br />
          3) <strong>Experiment:</strong> You will then see an interactive process model visualization where
          you will have to answer some questions about the process shown. You can
          interact with the visualization to get the information you need.
          <br />
          <br />
          4) <strong>Post-Experiment Questions:</strong> Finally, there is a post-experiment question.
          <br />
          <br />
          <br />
          Please always read the questions and tasks carefully and take the time
          for exploration with the visualization that you need to answer the
          questions.
          <br />
          Please be sure that the data collected from you will only be stored and
          analyzed for the purpose of conducting this experiment and the
          presentation of the results. Only data that is necessary and relevant
          for the evaluation of the study will be asked for.
          <br />
          <br />
          Thank you in advance for your participation and contribution to
          research! <br />
          <br />
          Best, <br />
          Marie-Christin Häge
          <br />
          <br />
        </p>
        <div>
          <h2 className="mb-4 text-3xl font-bold color-red">Consent</h2>
          <div className="flex items-start gap-4">
            <input
              type="checkbox"
              id="consent"
              onChange={handleConsentChange}
              className="w-6 h-6 accent-blue-500"
            />
            <label htmlFor="consent" className="text-2xl font-semibold leading-6">
              I have read the general information and the data protection
              information on the ProVi research project and consent to
              participation in the research project and to my data being processed
              within this scope.
            </label>
          </div>
          <br />
          <p className="mt-6 text-xl">
            I am aware that I give my consent voluntarily and that I can withdraw
            my consent (completely or for individual cases of processing) at any
            time without having to state any reasons, and that withdrawing my
            consent does not have any negative consequences. Withdrawing consent
            does not affect the lawfulness of processing based on consent before
            its withdrawal. I have understood that in order to withdraw my
            consent, I can turn to the person listed as contact in the information
            above and that refusing to give consent or withdrawing consent does
            not have any negative consequences. I was provided with the
            information on the collection of personal data in the research project
            ProVi. The text of this declaration of consent was made available to
            me at{" "}
            <span
              className="text-blue-500 underline cursor-pointer"
              onClick={() => router.push("dataprotection")}
            >
              https://pm-vis.uni-mannheim.de/dataprotection
            </span>{" "}
            where also all the detailed information can be found.
          </p>
        </div>
        <button
          type="submit"
          onClick={handleSubmit}
          className="self-center px-10 py-3 mt-4 text-white bg-blue-500 rounded-lg hover:bg-blue-600"
        >
          Enter Pre-Questions
        </button>
        <br />
      </div>
    </div>
  );
}
