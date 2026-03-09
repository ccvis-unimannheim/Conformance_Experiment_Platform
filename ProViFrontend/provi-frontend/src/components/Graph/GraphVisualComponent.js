"use client";

import React, { useState, useEffect, useRef, useContext, useMemo } from "react";
import SliderComponent from "./SliderComponent";
import SVGDisplay from "./SVGDisplay";
import useSWR from "swr";
import { UITrackingContext } from "../../utils/usertracking";

const MAPPING_URL = "https://pm-vis.uni-mannheim.de/api/vis/mapping";

const jsonFetcher = async (url) => {
  const response = await fetch(url, {
    cache: "no-cache",
    credentials: "include",
  });
  if (!response.ok) {
    throw new Error("Failed to fetch mapping.");
  }
  return response.json();
};

const GraphVisualComponent = ({ zoomResetTrigger }) => {
  const { addTrackingChange } = useContext(UITrackingContext);
  const { data: dfgMapping, error } = useSWR(MAPPING_URL, jsonFetcher);
  const [sliderAValue, setSliderAValue] = useState(0);
  const [sliderCValue, setSliderCValue] = useState(0);
  const [selectedSVG, setSelectedSVG] = useState(null);
  const initialSetRef = useRef(false);

  // Get sorted array of valid activities
  const validActivities = dfgMapping
    ? Object.keys(dfgMapping)
        .map(Number)
        .sort((a, b) => a - b)
    : [];

  console.log(validActivities);

  // Function to get sorted array of valid path numbers for a given activity
  const getValidPaths = (activityKey) => {
    if (!dfgMapping || !dfgMapping[activityKey]) return [];
    return dfgMapping[activityKey]
      .map((path) => parseInt(path.split("_")[1]))
      .sort((a, b) => a - b);
  };

  // Get current valid paths
  const currentValidPaths = getValidPaths(sliderAValue.toString());

  // Function to create marks for MUI Slider
  const createMarks = (validValues) => {
    return validValues.map((value) => ({
      value: value,
      label: value.toString(),
    }));
  };

  // Updated handler for Slider A
  const handleSliderAChange = (newValue) => {
    // Since we're using marks, newValue will already be a valid activity
    setSliderAValue(newValue);

    // Set C value to first valid path for new activity
    const validPaths = getValidPaths(newValue.toString());
    if (validPaths.length > 0) {
      setSliderCValue(validPaths[0]);
    }

    addTrackingChange("changeSliderAValue", "sliderA", "sliders", newValue);
  };

  // Handler for Slider C
  const handleSliderCChange = (newValue) => {
    // Since we're using marks, newValue will already be a valid path
    setSliderCValue(newValue);
    addTrackingChange("changeSliderCValue", "sliderC", "sliders", newValue);
  };

  // Initial setup effect
  useEffect(() => {
    if (dfgMapping && !initialSetRef.current && validActivities.length > 0) {
      const initialActivity = validActivities[0];
      setSliderAValue(initialActivity);

      const validPaths = getValidPaths(initialActivity.toString());
      if (validPaths.length > 0) {
        setSliderCValue(validPaths[0]);
      }

      addTrackingChange(
        "initializeSliderA",
        "sliderA",
        "sliders",
        initialActivity
      );
      addTrackingChange(
        "initializeSliderC",
        "sliderC",
        "sliders",
        validPaths[0]
      );

      initialSetRef.current = true;
    }
  }, [dfgMapping]);

  // Effect to update selectedSVG
  useEffect(() => {
    if (dfgMapping && sliderAValue) {
      const currentActivity = sliderAValue.toString();
      const selectedPath = `${currentActivity}_${sliderCValue}`;

      // Check if this combination exists in the mapping
      if (dfgMapping[currentActivity]?.includes(selectedPath)) {
        setSelectedSVG(selectedPath);
      } else {
        setSelectedSVG(null);
      }
    }
  }, [sliderAValue, sliderCValue, dfgMapping]);

  return (
    <div className="flex flex-col p-6 bg-white rounded-md shadow-md">
      <h2 className="text-lg font-semibold">Directly-Follows Graph</h2>
      <div className="flex flex-row mt-10 mb-4 rounded-md h-[650px] max-w-[1200px]">
        <div className="w-[85%] bg-white rounded-md shadow-md items-left">
          <SVGDisplay
            selectedSVG={selectedSVG}
            zoomResetTrigger={zoomResetTrigger}
          />
        </div>
        <div className="flex flex-col items-center justify-between w-[15%]">
          <div className="w-20">
            <SliderComponent
              label="Activities"
              id="verticalSliderA"
              value={sliderAValue}
              onChange={handleSliderAChange}
              max={Math.max(...validActivities)}
              min={Math.min(...validActivities)}
              marks={createMarks(validActivities)}
            />
            <SliderComponent
              label="Paths"
              id="verticalSliderC"
              value={sliderCValue}
              onChange={handleSliderCChange}
              max={Math.max(...currentValidPaths)}
              min={Math.min(...currentValidPaths)}
              marks={createMarks(currentValidPaths)}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default GraphVisualComponent;
