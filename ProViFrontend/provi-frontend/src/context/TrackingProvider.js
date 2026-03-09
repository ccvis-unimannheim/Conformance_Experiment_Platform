import React, { createContext, useState, useContext } from 'react';

// creates the context to store data and to share data
const TrackingContext = createContext();

export const TrackingProvider = ({ children }) => {
  const [trackingData, setTrackingData] = useState([]);

  const addTrackingData = (data) => {
    setTrackingData((prev) => [...prev, data]);
  };

  return (
    <TrackingContext.Provider value={{ trackingData, addTrackingData }}>
      {children}
    </TrackingContext.Provider>
  );
};

// Custom Hook in order to simplify using the context use: useTracking()
export const useTracking = () => {
  return useContext(TrackingContext);
};
