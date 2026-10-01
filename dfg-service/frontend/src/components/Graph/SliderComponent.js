"use client";

import React from "react";
import Slider from "@mui/material/Slider";

const SliderComponent = ({ label, id, onChange, value, max, min, marks }) => {
  const marksWithoutLabels = marks.map((mark) => ({
    value: mark.value,
  }));
  const handleSliderChange = (event, newValue) => {
    onChange(newValue);
  };

  return (
    <div className="flex flex-col items-center gap-4 p-4 mb-2 bg-white rounded-md shadow-md">
      <label htmlFor={id} className="font-semibold">
        {label}:
      </label>
      <Slider
        aria-labelledby={id}
        value={value}
        valueLabelDisplay="auto"
        onChange={handleSliderChange}
        marks={marksWithoutLabels}
        min={min}
        max={max}
        orientation="vertical"
        style={{ height: 160 }}
        step={null}
      />
      <span className="font-semibold">
        {value}/{max}
      </span>
    </div>
  );
};

export default SliderComponent;
