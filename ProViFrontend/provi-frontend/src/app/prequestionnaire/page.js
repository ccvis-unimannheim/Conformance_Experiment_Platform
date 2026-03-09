"use client";

import React, { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Papa from "papaparse";
import AlertPopup from '../../components/Questionnaire/AlertPopup';
import ScrollProgressBar from "../../components/WelcomePage/ScrollProgressBar";
import ExpNavigation from "../../components/General/ExpNavigation";

import "@coreui/coreui/dist/css/coreui.min.css";

export default function PrequestionComponent() {
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});
  const [showModal, setShowModal] = useState(false);
  const [alertMessage, setAlertMessage] = useState("");
  const router = useRouter();

  const csvData = `
      id,type,question,options
      1,multiple,What gender do you identify yourself with?,"Female;Male;None of the above;Prefer not to answer"
      2,open,How old are you?,
      3,multiple,What is your professional background?,"Researcher;Student (Bachelor/Master);Practitioner"
      4,multiple,How long have you been involved with Process Mining?,"Less than a month;Less than a year;Less than 3 years;3 years or longer"
      5,multiple,How often do you work on Process Mining tasks or with Process Mining tools?,"Daily;Monthly;Less frequent than monthly;Never"
      6,multiple,How would you rate your Process Mining expertise level?,"Basic;Advanced;Expert"
  `;

  useEffect(() => {
    const parsedData = Papa.parse(csvData.trim(), { header: true }).data;
    const formattedQuestions = parsedData.map((question) => ({
      ...question,
      id: String(question.id), // Ensure IDs are strings for consistent comparison
      options: question.options
        ? question.options.split(";").map((opt) => opt.trim())
        : [],
    }));
    setQuestions(formattedQuestions);
  }, []);

  const handleAnswerChange = (questionId, value) => {
    setAnswers((prevAnswers) => ({
      ...prevAnswers,
      [questionId]: value,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const unansweredQuestions = questions.filter((q) => {
      const answer = answers[q.id];
      if (q.type === "open") {
        return !answer || answer.trim() === "";
      }
      return !answer;
    });

    if (unansweredQuestions.length > 0) {
      const missingQuestions = unansweredQuestions
        .map((q, index) => `${questions.indexOf(q) + 1}. ${q.question}`)
        .join("\n");

      setAlertMessage(
        `Please answer the following questions before starting the experiment:\n\n${missingQuestions}`
      );
      setShowModal(true);
      return;
    }

    // Create ordered answers using the questions array order
    const orderedAnswers = questions.map(question => ({
      questionId: question.id,
      answer: answers[question.id]
    }));

    // Map answers to the required backend keys in the correct order
    const sendData = {
      gender: orderedAnswers[0].answer,
      age: parseInt(orderedAnswers[1].answer),
      professional_background: orderedAnswers[2].answer,
      experience_time_process_mining: orderedAnswers[3].answer,
      frequency_process_mining: orderedAnswers[4].answer,
      expertise_level_process_mining: orderedAnswers[5].answer,
    };

    try {
      const response = await fetch("https://pm-vis.uni-mannheim.de/api/auth/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include",
        body: JSON.stringify(sendData),
      });

      if (!response.ok) {
        setAlertMessage(`Error submitting your answers: ${response.statusText}`);
        setShowModal(true);
        return;
      }

      console.log("Data successfully submitted:", sendData);
      router.push("/knowledgequestion");
    } catch (error) {
      setAlertMessage(`An unexpected error occurred: ${error.message}`);
      setShowModal(true);
    }
  };

  return (
    <div>
      <ExpNavigation />
      <div className="bg-gray-50 p-10 shadow-xl rounded-lg h-auto w-3/5 mx-auto flex flex-col gap-10 items-center justify-center my-10">
        <ScrollProgressBar />
        <h1 className="text-3xl font-bold">Process Visualization Experiment</h1>
        
        <AlertPopup
          visible={showModal}
          message={alertMessage}
          onClose={() => setShowModal(false)}
        />
        <p className="text-xl mt-6">
        In the following part I kindly ask you to answer the 6 Pre-Experiment Questions. This is followed by 7 Knowledge Questions.
        </p>
        <div className="flex flex-col gap-6 mt-6">
          <h2 className="text-3xl font-semibold">Pre-Experiment Questions</h2>
          {questions.map((q, index) => (
            <div key={q.id} className="mb-6">
              <h3 className="font-semibold mb-2 text-2xl">
                {index + 1}. {q.question}
              </h3>
              {q.type === "multiple" || q.type === "knowledge" ? (
                <div>
                  {q.options.map((option, idx) => (
                    <label key={idx} className="block text-xl">
                      <input
                        type="radio"
                        name={`question-${q.id}`}
                        value={option}
                        onChange={(e) => handleAnswerChange(q.id, option)}
                        className="mr-2"
                      />
                      {option}
                    </label>
                  ))}
                </div>
              ) : (
                <input
                  type="text"
                  name={`question-${q.id}`}
                  placeholder="Your answer"
                  onChange={(e) => handleAnswerChange(q.id, e.target.value)}
                  className="border p-2 rounded w-full text-m"
                />
              )}
            </div>
          ))}
        </div>

        <button
          type="submit"
          onClick={(e) => handleSubmit(e)}
          className="px-10 py-3 rounded-lg mt-4 self-center bg-blue-500 text-white hover:bg-blue-600"
        >
          Enter Knowledge Questions
        </button>
        <br/>
      </div>
    </div>
  );
}