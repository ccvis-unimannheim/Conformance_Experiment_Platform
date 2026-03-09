"use client";

import React, { useState } from "react";

export default function EndPage() {
  const [showThankYou, setShowThankYou] = useState(false);
  const [rating, setRating] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [showCompletionCode, setShowCompletionCode] = useState(false);

  const handleRatingChange = (e) => {
    setRating(e.target.value);
  };

  const handleSubmitRating = async () => {
    if (!rating) {
      setErrorMessage("Please select a rating before proceeding.");
      return;
    }

    // Construct the answer payload for the backend
    const answerPayload = {
      question_id: "100",
      answer: rating,
      insert_datetime: new Date().toISOString(),
    };

    try {
      const response = await fetch(
        "https://pm-vis.uni-mannheim.de/api/survey/answer",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          credentials: "include",
          body: JSON.stringify(answerPayload),
        }
      );

      if (!response.ok) {
        // Handle response errors
        console.error("Failed to submit rating:", response.statusText);
        setErrorMessage(
          "An error occurred while submitting your rating. Please try again."
        );
        return;
      }

      console.log("Rating submitted successfully:", answerPayload);
      setShowThankYou(true); // Show the thank-you message
      setShowCompletionCode(true);
    } catch (error) {
      console.error("Error submitting rating:", error);
      setErrorMessage("An unexpected error occurred. Please try again.");
    }
  };

  return (
    <div className="bg-gray-100 min-h-screen flex flex-col items-center justify-center">
      <div className="bg-white p-8 shadow-lg rounded-lg w-3/4 mx-auto flex flex-col gap-8 my-16">
        {showThankYou ? (
          // Thank-you text after the rating is submitted
          <>
            <h1 className="text-3xl font-bold">Thank you for participating</h1>
            <p className="text-xl">
              Thank you for taking the time and participating in this
              experiment! Your contribution is crucial to our research on
              understanding the user perspective of process mining
              visualizations.
              <br />
              If you have any questions or would like to learn more about our
              research, please don’t hesitate to contact me at
              haege@uni-mannheim.de.
              <br />
              <br />
              Best
              <br />
              Marie
            </p>
          </>
        ) : (
          // Inline question displayed initially
          <>
            <h2 className="text-xl font-bold">
              On a scale from 1 (easy) to 7 (difficult), how difficult was it to
              answer the questions?
            </h2>
            {errorMessage && (
              <p className="text-red-500 text-sm">{errorMessage}</p>
            )}
            <div className="flex flex-col gap-2">
              {[1, 2, 3, 4, 5, 6, 7].map((option) => (
                <label key={option} className="flex items-center gap-2 text-m">
                  <input
                    type="radio"
                    name="rating"
                    value={option}
                    onChange={handleRatingChange}
                    checked={rating === option.toString()}
                    className="w-4 h-4"
                  />
                  {option}
                </label>
              ))}
            </div>
            <div className="flex justify-center">
              <button
                onClick={handleSubmitRating}
                className="w-80 h-10 rounded-lg bg-blue-500 text-white hover:bg-blue-600"
              >
                Submit Rating
              </button>
            </div>
          </>
        )}
      </div>

      {showCompletionCode && (
        <div className="absolute bottom-5 text-center text-gray-600 text-xs font-semibold">
          Completion Code: H6Owc7hOdgdu21B
        </div>

      )}
    </div>
  );
}
