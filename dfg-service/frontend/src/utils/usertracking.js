import React, { createContext, useState } from "react";

export const UITrackingContext = createContext();

export const UITrackingProvider = ({ children }) => {
  const [trackingData, setTrackingData] = useState({
    userActivity: [],
  });

  /* 
  example call:
    activity: zoomIn
    uiElement: zoom
    uiGroup: Graph
    value: 120%

    activity: changeSliderAValue
    uiElement: sliderA
    uiGroup: sliders
    value: 8
  */
  const addTrackingChange = (activity, uiElement, uiGroup, setValue) => {
    const timestamp = new Date().toISOString();
    const value = JSON.stringify(setValue);
    setTrackingData((prev) => ({
      ...prev,
      ["userActivity"]: [
        ...prev["userActivity"],
        { activity, uiElement, uiGroup, value, timestamp },
      ],
    }));
  };

  const clearTrackingData = () => {
    setTrackingData({
      userActivity: [],
    });
  };

  return (
    <UITrackingContext.Provider
      value={{ trackingData, addTrackingChange, clearTrackingData }}
    >
      {children}
    </UITrackingContext.Provider>
  );
};
