import React, { useState, useEffect, useContext } from "react";
import Papa from "papaparse";
import { useRouter } from "next/navigation";
import { UITrackingContext } from "../../utils/usertracking";

const QuestionnaireComponent = ({ onQuestionSubmit }) => {
  const router = useRouter();
  const { trackingData, addTrackingChange } = useContext(UITrackingContext);
  const [questions, setQuestions] = useState([]);
  const [currentQuestionIndex, setCurrentQuestionIndex] = useState(0);
  const [currentAnswer, setCurrentAnswer] = useState("");
  const [answers, setAnswers] = useState([]);
  const { clearTrackingData } = useContext(UITrackingContext);
  const [showFrontPage, setShowFrontPage] = useState(true); // state to handle front page visibility

  // handle the start Questionnaire button to start the Questionnaire
  const handleStart = () => {
    clearTrackingData();
    setShowFrontPage(false); // Hide front page and show the questionnaire
    // Trigger zoom reset after starting experiment
    onQuestionSubmit();
  };

  useEffect(() => {
    console.log("Questionnaire data:", trackingData);
  }, [trackingData]);

  // parses the question csv to json fetch version
  useEffect(() => {
    const fetchQuestions = async () => {
      try {
        const response = await fetch(
          "https://pm-vis.uni-mannheim.de/api/survey/questionnaire",
          {
            method: "GET",
            credentials: "include",
            headers: {
              "Content-Type": "text/csv", // Adjust based on API response type
            },
          }
        );

        if (!response.ok) {
          throw new Error(`Failed to fetch questions: ${response.statusText}`);
        }

        const csvData = await response.text();
        console.log(csvData);

        // Parse the CSV into a JSON format using PapaParse
        Papa.parse(csvData, {
          header: true,
          skipEmptyLines: true,
          delimiter: ";",
          // quoteChar: '"',
          transformHeader: (header) => header.trim(),
          complete: (result) => {
            const processedData = result.data.map((question) => ({
              ...question,
              "Question Text": question["Question Text"]?.replace(
                /\\n\\n/g,
                "\n\n"
              ),
            }));
            console.log("processed Data: ", processedData);

            setQuestions(processedData);
            setAnswers(new Array(processedData.length).fill(""));
          },
        });
      } catch (error) {
        console.error("Error fetching questionnaire data:", error);
      }
    };
    fetchQuestions();
  }, []);

  // Function to send questionnaire answers
  const sendAnswerData = async (questionId, answer) => {
    const answerPayload = {
      question_id: questionId.toString(),
      answer: answer.toString(),
      insert_datetime: new Date().toISOString(),
    };

    try {
      const response = await fetch(
        `https://pm-vis.uni-mannheim.de/api/survey/answer`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include", // Include cookies if required
          body: JSON.stringify(answerPayload),
        }
      );

      if (!response.ok) {
        console.error(`Failed to send Question answer: ${response.status}`);
        return false; // Return false to indicate failure
      } else {
        const responseData = await response.json();
        console.log(
          `Answer submitted successfully for question ${questionId}`,
          responseData.message
        );
        return true; // Return true to indicate success
      }
    } catch (error) {
      console.error("Error sending questionnaire answer: ", error);
      return false; // Return false to indicate failure
    }
  };


  // Ui Tracking Data Post Call
  const sendUITrackingData = async () => {
    // Default UI logs array
    let uiLogs = [];
  
    if (trackingData?.userActivity?.length > 0) {
      // Map the trackingData into the required format
      uiLogs = trackingData.userActivity.map((entry) => ({
        activity: entry.activity || "unknown",
        uiElement: entry.uiElement || "unknown",
        uiGroup: entry.uiGroup || "unknown",
        value: entry.value || "unknown",
        insert_datetime: new Date().toISOString(),
      }));
    } else {
      // If no user activity, send an empty log
      console.log("No tracking data by the user. Sending an empty log.");
      uiLogs.push({
        activity: "no activity from user",
        uiElement: "none",
        uiGroup: "none",
        value: "none",
        insert_datetime: new Date().toISOString(),
      });
    }
  
    // Prepare the payload with question_id outside the ui_logs array
    const payload = {
      question_id: (currentQuestionIndex + 1).toString(), // Include the current question ID
      ui_logs: uiLogs, // Include the array of UI logs
    };
  
    console.log("Payload", payload);
  
    try {
      const response = await fetch("https://pm-vis.uni-mannheim.de/api/uitracking/", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        credentials: "include", // Include cookies if required
        body: JSON.stringify(payload),
      });
  
      if (!response.ok) {
        console.error(`Failed to send UI tracking data: ${response.status}`);
      } else {
        const responseData = await response.json();
        console.log("Success: ", responseData.message);
        clearTrackingData(); // Clear the tracking data after successful submission
      }
    } catch (error) {
      console.error("Error sending UI tracking data:", error);
    }
  };
  

  // handles next question button, sends answer + ui tracking to backend
  const handleNextQuestion = async () => {
    if (
      currentAnswer === "" ||
      (Array.isArray(currentAnswer) && currentAnswer.length === 0)
    ) {
      alert("Please answer the question.");
      return;
    }
  
    const success = await sendAnswerData(
      currentQuestionIndex + 1, // Current question ID
      currentAnswer // Current answer
    );
  
    if (success) {
      // Send UI tracking data after successfully submitting the answer
      await sendUITrackingData();
  
      // Trigger zoom reset after successful submission
      onQuestionSubmit();
  
      // Update the local answer state
      const updatedAnswers = [...answers];
      updatedAnswers[currentQuestionIndex] = currentAnswer;
      setAnswers(updatedAnswers);
  
      // Handle follow-up question logic
      if (
        currentQuestion["Answer Type"] === "follow-up question" &&
        currentAnswer === "No"
      ) {
        setCurrentQuestionIndex(currentQuestionIndex + 2);
        setCurrentAnswer("");
        return;
      }
  
      if (currentQuestionIndex < questions.length - 1) {
        setCurrentQuestionIndex(currentQuestionIndex + 1);
        setCurrentAnswer(answers[currentQuestionIndex + 1] || ""); // Pre-fill answer if already answered
      }
    } else {
      console.error("Failed to submit answer, retrying...");
    }
  };

  const handleFinish = async () => {
    if (
      currentAnswer === "" ||
      (Array.isArray(currentAnswer) && currentAnswer.length === 0)
    ) {
      alert("Please answer the question before finishing.");
      return;
    }
  
    const success = await sendAnswerData(
      currentQuestionIndex + 1, // Current question ID
      currentAnswer // Current answer
    );
  
    if (success) {
      // Send UI tracking data after successfully submitting the answer
      await sendUITrackingData();
  
      // Navigate to the end page
      router.push("/endpage");
    } else {
      console.error("Failed to submit final answer.");
    }
  };
  
  
  // for question 17 => method handling the order selection + function to count the already used numbers (no double numbers allowed)
  const handleDropdownChange = (value, item) => {
    // Parse the currentAnswer string into an object, or start with an empty object
    const tempAnswers = currentAnswer
      ? Object.fromEntries(
          currentAnswer.split(", ").map((entry) => {
            const [order, option] = entry.split(". ");
            return [option, parseInt(order)];
          })
        )
      : {};

    if (value === "") {
      // If value is cleared (changed back to "Order"), remove the item
      delete tempAnswers[item];
    } else {
      // Update the selected order for the current item
      tempAnswers[item] = parseInt(value);
    }

    // Convert the updated object back into a sorted formatted string
    const formattedString = Object.entries(tempAnswers)
      .sort(([, orderA], [, orderB]) => orderA - orderB) // Sort by order
      .map(([option, order]) => `${order}. ${option}`) // Format each option
      .join(", "); // Join into a single string

    // Update the state with the formatted string
    setCurrentAnswer(formattedString);
  };

  const currentQuestion = questions[currentQuestionIndex];

  return (
    <div className="flex flex-col w-full p-6 bg-white rounded-md shadow-md">
      {showFrontPage ? (
        <div className="flex flex-col items-center gap-4 text-center">
          <h1 className="text-2xl font-bold">Welcome to the Experiment</h1>
          <br />
          <p className="mb-8 text-lg leading-relaxed text-center">
            On the <strong>left</strong>, you can now see the{" "}
            <strong>Directly-Follow-Graph (DFG)</strong> which will help you
            answer the upcoming questions. The{" "}
            <strong>two sliders on the right</strong> of the DFG allow you to
            adjust the <strong>activities shown (upper slider)</strong> and the{" "}
            <strong>number of paths displayed (lower slider)</strong>. At the
            bottom, you can <strong>zoom in and out</strong> for a closer view
            of specific activities or paths.
          </p>
          <p className="mb-8 text-lg leading-relaxed text-center">
            Feel free to take a moment to explore and familiarize yourself with
            the DFG and its features. When ready, click{" "}
            <strong>Start Experiment</strong> to proceed to the questions, which
            will appear on the right one at a time.
          </p>
          <button
            className="px-4 py-2 text-white bg-blue-500 rounded-md"
            onClick={handleStart}
          >
            Start Experiment
          </button>
        </div>
      ) : currentQuestion ? (
        <div className="flex flex-col h-full gap-4">
          <h2 className="text-lg font-semibold">
            Question {currentQuestionIndex + 1} of {questions.length}
          </h2>
          <div className="flex items-center gap-2">
            <p className="whitespace-pre-line">
              {currentQuestion["Question Text"] ||
                "Question text is unavailable"}
            </p>
          </div>

          {currentQuestion["Answer Type"] === "text" && (
            <textarea
              value={currentAnswer}
              onChange={(e) => setCurrentAnswer(e.target.value)}
              className="w-full p-2 border rounded-md"
              placeholder="Enter a text"
              rows={3}
            />
          )}
          {currentQuestion["Answer Type"] === "numeric" && (
            <input
              type="number"
              value={currentAnswer}
              onChange={(e) => {
                const value = e.target.value;
                if (/^\d*$/.test(value)) {
                  setCurrentAnswer(value);
                }
              }}
              className="w-full p-2 border rounded-md"
              placeholder="Enter a number"
            />
          )}

          {(currentQuestion["Answer Type"] === "multiple choice" ||
            currentQuestion["Answer Type"] === "follow-up question") && (
            <div className="flex flex-col gap-2">
              {currentQuestion["Options"].split("|").map((option, index) => (
                <label key={index} className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="question-option"
                    value={option}
                    checked={currentAnswer === option}
                    onChange={(e) => setCurrentAnswer(e.target.value)}
                    className="w-4 h-4"
                  />
                  {option}
                </label>
              ))}
            </div>
          )}
          {currentQuestion["Answer Type"] === "multiple select" && (
            <div className="flex flex-col gap-2">
              {currentQuestion["Options"].split("|").map((option, index) => (
                <label key={index} className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    name="question-option"
                    value={option}
                    checked={
                      Array.isArray(currentAnswer) &&
                      currentAnswer.includes(option)
                    }
                    onChange={(e) => {
                      const updatedAnswers = Array.isArray(currentAnswer)
                        ? [...currentAnswer]
                        : [];
                      if (e.target.checked) {
                        updatedAnswers.push(option);
                      } else {
                        const optionIndex = updatedAnswers.indexOf(option);
                        if (optionIndex > -1) {
                          updatedAnswers.splice(optionIndex, 1);
                        }
                      }
                      setCurrentAnswer(updatedAnswers);
                    }}
                    className="w-4 h-4"
                  />
                  {option}
                </label>
              ))}
            </div>
          )}
          {currentQuestion["Answer Type"] === "order question" && (
            <div className="flex flex-col gap-4">
              {currentQuestion["Options"].split("|").map((option, index) => (
                <div
                  key={index}
                  className="flex items-center justify-between gap-2"
                >
                  <p className="flex-grow">{option}</p>
                  <select
                    value={
                      currentAnswer
                        .split(", ")
                        .find((entry) => entry.includes(option))
                        ?.split(". ")[0] || ""
                    }
                    onChange={(e) =>
                      handleDropdownChange(e.target.value, option)
                    }
                    className="p-2 border rounded-md"
                  >
                    <option value="">Order</option>
                    {[...Array(currentQuestion["Options"].split("|").length)]
                      .map((_, i) => i + 1)
                      .map((order) => (
                        <option
                          key={order}
                          value={order}
                          disabled={currentAnswer
                            .split(", ")
                            .some((entry) => entry.startsWith(`${order}.`))}
                        >
                          {order}
                        </option>
                      ))}
                  </select>
                </div>
              ))}
            </div>
          )}
          <div className="flex justify-end mt-4">
            {currentQuestionIndex < questions.length - 1 ? (
              <button
                onClick={handleNextQuestion}
                className="px-4 py-2 text-white bg-blue-500 rounded-md"
              >
                Next Question
              </button>
            ) : (
              <button
                onClick={handleFinish}
                className="px-4 py-2 text-white bg-blue-500 rounded-md"
              >
                Finish
              </button>
            )}
          </div>
        </div>
      ) : (
        <p>Loading questions...</p>
      )}
    </div>
  );
};

export default QuestionnaireComponent;
