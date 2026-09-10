"use client";

import React, { useRef, useState } from "react";

const DatasetUploadBox = ({ title, refreshDatasetList }) => {
  const fileInputRef = useRef(null);
  const [uploadMessage, setUploadMessage] = useState("");

  const handleUploadClick = () => {
    fileInputRef.current.click();
  };

  const handleFileChange = async (event) => {
    const file = event.target.files[0];
    if (file) {
      if (!file.name.endsWith(".xes")) {
        alert("Please upload a valid .xes file.");
        return;
      }

      const formData = new FormData();
      formData.append("file", file);

      try {
        const response = await fetch("/dfg/api/admin/upload", {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          console.error(`Failed to upload the file. Status: ${response.status}`);
          alert(`Failed to upload the file: ${response.statusText}`);
          return;
        }

        const result = await response.json();
        console.log("Dataset uploaded successfully:", result);

        setUploadMessage("Dataset uploaded successfully! It's processing in the background.");

        if (refreshDatasetList) {
          refreshDatasetList();
        }

        setTimeout(() => {
          setUploadMessage("");
        }, 5000);
      } catch (error) {
        console.error("Error during file upload:", error.message);
        alert("An error occurred while uploading the dataset. Please try again.");
      }
    }
  };

  return (
    <div className="bg-white p-6 shadow-md rounded-md h-auto w-full flex flex-col gap-4 max-h-[500px]">
      <h3 className="text-lg font-semibold">{title}</h3>
      <div className="flex items-center justify-center border-2 border-dashed border-gray-300 h-32 rounded-md">
        <button
          className="bg-gray-500 text-white px-4 py-2 rounded-md"
          onClick={handleUploadClick}
        >
          New Upload
        </button>
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: "none" }}
          accept=".xes"
          onChange={handleFileChange}
        />
      </div>
      {uploadMessage && (
        <div className="bg-green-100 text-green-700 p-4 rounded-md mt-4">
          {uploadMessage}
        </div>
      )}
    </div>
  );
};

export default DatasetUploadBox;
