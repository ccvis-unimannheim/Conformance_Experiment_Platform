"use client";

import React from "react";

const DownloadBox = ({ title }) => {
  const handleDownload = async () => {
    let apiUrl = "";
    if (title === "Download Questionnaire Data") {
      apiUrl = "/dfg/api/admin/answers";
    } else if (title === "Download UI Tracking Data") {
      apiUrl = "/dfg/api/admin/uitracking";
    } else if (title === "Download User Data") {
      apiUrl = "/dfg/api/admin/users";
    } else {
      alert("No matching API endpoint found.");
      return;
    }

    try {
      const response = await fetch(apiUrl, {
        method: "GET",
        credentials: "include",
      });

      if (!response.ok) {
        console.error(`Failed to fetch data from ${apiUrl}:`, response.status);
        alert(`Failed to download data: ${response.statusText}`);
        return;
      }

      const csvData = await response.text();
      const blob = new Blob([csvData], { type: "text/csv" });
      const url = window.URL.createObjectURL(blob);

      const link = document.createElement("a");
      link.href = url;
      link.download = `${title.replace("Download ", "").replace(" ", "_")}.csv`;
      link.click();

      window.URL.revokeObjectURL(url);
    } catch (error) {
      console.error("Error during data download:", error.message);
    }
  };

  return (
    <div className="bg-white p-6 shadow-md rounded-md h-auto w-full flex flex-col gap-4 items-center max-h-[200px]">
      <h3 className="text-lg font-semibold">{title}</h3>
      <button className="bg-gray-500 text-white px-4 py-2 rounded-md mt-4" onClick={handleDownload}>
        Download
      </button>
    </div>
  );
};

export default DownloadBox;
