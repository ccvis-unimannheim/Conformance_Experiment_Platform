"use client";

import Head from "next/head";
import { useEffect, useState } from "react";

import LoginModal from "../../components/Admin/LoginModal";
import DatasetUploadBox from "../../components/Admin/DatasetUploadBox";
import QuestionnaireUploadBox from "../../components/Admin/QuestionnaireUploadBox";
import DownloadBox from "../../components/Admin/DownloadBox";
import Navigation from "../../components/General/Navigation";

export default function AdminPage() {
  const [datasets, setDatasets] = useState([]);
  const [dataset1, setDataset1] = useState("");
  const [dataset2, setDataset2] = useState("");
  const [dataset1ID, setDataset1ID] = useState("");
  const [dataset2ID, setDataset2ID] = useState("");
  const [userCountDataset1, setuserCountDataset1] = useState("");
  const [userCountDataset2, setuserCountDataset2] = useState("");
  const [successMessage, setSuccessMessage] = useState("");
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  const fetchDatasets = async () => {
    try {
      const response = await fetch("/dfg/api/admin/datasets");
      if (!response.ok) throw new Error("Failed to fetch datasets");

      const data = await response.json();

      const sortedDatasets = [...data].sort((a, b) => {
        if (a.dataset_is_active && !b.dataset_is_active) return -1;
        if (!a.dataset_is_active && b.dataset_is_active) return 1;
        return 0;
      });

      const activeDatasets = sortedDatasets.filter((dataset) => dataset.dataset_is_active);

      const dataset1ID = activeDatasets[0]?.dataset_id || "";
      const dataset2ID = activeDatasets[1]?.dataset_id || "";

      setDataset1(activeDatasets[0]?.dataset_title || "");
      setDataset2(activeDatasets[1]?.dataset_title || "");
      setDataset1ID(dataset1ID);
      setDataset2ID(dataset2ID);

      setDatasets(sortedDatasets);

      await fetchUserCounts(dataset1ID, dataset2ID);
    } catch (error) {
      console.error("Error fetching datasets:", error);
    }
  };

  const fetchUserCounts = async (dataset1ID, dataset2ID) => {
    try {
      const response = await fetch("/dfg/api/admin/usagedataset");
      if (!response.ok) throw new Error("Failed to fetch usage dataset info");

      const data = await response.json();
      const counts = Object.entries(data).reduce((acc, [key, value]) => {
        acc[key] = value;
        return acc;
      }, {});

      setuserCountDataset1(counts[dataset1ID] || 0);
      setuserCountDataset2(counts[dataset2ID] || 0);
    } catch (error) {
      console.error("Error fetching usage dataset info:", error);
    }
  };

  useEffect(() => {
    if (isLoggedIn) {
      fetchDatasets();
    }
  }, [isLoggedIn]);

  const handleLoginSuccess = () => {
    setIsLoggedIn(true);
  };

  if (!isLoggedIn) {
    return <LoginModal onLoginSuccess={handleLoginSuccess} />;
  }

  const handleCompareDatasets = async () => {
    if (dataset1 && dataset2) {
      await handleSaveActiveDatasets();

      setSuccessMessage("Datasets selected successfully!");
      setTimeout(() => {
        setSuccessMessage("");
      }, 5000);

      await fetchDatasets();
    } else {
      console.log("Please select both datasets to compare.");
    }
  };

  const handleSaveActiveDatasets = async () => {
    const updatedDatasets = datasets.map((dataset) => ({
      ...dataset,
      dataset_is_active: dataset.dataset_title === dataset1 || dataset.dataset_title === dataset2,
    }));

    const selectedDatasets = { datasets: updatedDatasets };

    try {
      const response = await fetch("/dfg/api/admin/datasets", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(selectedDatasets),
      });

      if (!response.ok) {
        throw new Error("Failed to update active datasets.");
      }

      const sortedDatasets = [...updatedDatasets].sort((a, b) => {
        if (a.dataset_is_active && !b.dataset_is_active) return -1;
        if (!a.dataset_is_active && b.dataset_is_active) return 1;
        return 0;
      });

      setDatasets(sortedDatasets);
    } catch (error) {
      console.error("Error saving active datasets:", error);
    }
  };

  return (
    <div className="flex flex-col min-h-screen bg-gray-100">
      <Head>
        <title>Admin Dashboard - ProVi</title>
      </Head>
      <Navigation />

      <div className="p-4 text-center">
        <div className="flex justify-around mt-6">
          <p className="text-xl font-semibold">{dataset1} Users: {userCountDataset1}</p>
          <p className="text-xl font-semibold">{dataset2} Users: {userCountDataset2}</p>
        </div>
      </div>

      <main>
        <section className="p-12 m-12 mx-auto bg-white rounded-md shadow-md max-w-7xl">
          <h1 className="mb-8 text-2xl font-bold text-center">
            Choose the two Datasets to compare
          </h1>

          <div className="flex items-center justify-center gap-8">
            <div>
              <label htmlFor="dataset1" className="block mb-2 text-lg font-semibold">
                Dataset 1
              </label>
              <select
                id="dataset1"
                value={dataset1}
                onChange={(e) => setDataset1(e.target.value)}
                className="p-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:border-indigo-500"
              >
                {datasets.map((dataset) => (
                  <option key={dataset.dataset_id} value={dataset.dataset_title}>
                    {dataset.dataset_title}
                    {dataset.dataset_is_active ? " (Active)" : ""}
                  </option>
                ))}
              </select>
            </div>

            <div className="text-lg font-bold">compare to</div>

            <div>
              <label htmlFor="dataset2" className="block mb-2 text-lg font-semibold">
                Dataset 2
              </label>
              <select
                id="dataset2"
                value={dataset2}
                onChange={(e) => setDataset2(e.target.value)}
                className="p-3 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:border-indigo-500"
              >
                {datasets
                  .filter((dataset) => dataset.dataset_title !== dataset1)
                  .map((dataset) => (
                    <option key={dataset.dataset_id} value={dataset.dataset_title}>
                      {dataset.dataset_title}
                      {dataset.dataset_is_active ? " (Active)" : ""}
                    </option>
                  ))}
              </select>
            </div>
          </div>

          <div className="flex justify-center mt-8">
            <button
              onClick={handleCompareDatasets}
              className="px-8 py-3 font-semibold text-white transition duration-300 bg-green-500 rounded-full shadow-md hover:bg-green-600"
            >
              Use these 2 datasets
            </button>
          </div>
          <br />
          {successMessage && (
            <div className="bg-green-100 text-green-700 p-4 rounded-md">
              {successMessage}
            </div>
          )}
        </section>

        <div className="flex gap-8 mx-auto max-w-7xl">
          <div className="flex flex-col flex-1 gap-4 py-12">
            <h1 className="text-2xl font-bold">Upload Datasets</h1>
            <DatasetUploadBox title="Upload Dataset" refreshDatasetList={fetchDatasets} />
          </div>

          <div className="flex flex-col flex-1 gap-4 py-12">
            <h1 className="text-2xl font-bold">Upload/ Change Questionnaire</h1>
            <QuestionnaireUploadBox title="Upload/Change Questionnaire" />
          </div>
        </div>

        <div className="h-8"></div>
        <h1 className="text-2xl font-bold text-center">
          Download all collected Data
        </h1>
        <div className="grid flex-grow grid-cols-1 gap-8 p-16 md:grid-cols-3">
          <DownloadBox title="Download Questionnaire Data" />
          <DownloadBox title="Download UI Tracking Data" />
          <DownloadBox title="Download User Data" />
        </div>
      </main>
    </div>
  );
}
