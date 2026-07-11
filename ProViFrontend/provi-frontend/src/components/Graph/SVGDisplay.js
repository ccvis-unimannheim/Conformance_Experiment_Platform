import React, { useState, useEffect, useContext, useRef } from "react";
import { IconButton, Stack } from "@mui/material";
import {
  AddCircle as AddCircleIcon,
  RemoveCircle as RemoveCircleIcon,
  RestartAlt as RestartAltIcon,
} from "@mui/icons-material";
import {
  TransformWrapper,
  TransformComponent,
  useControls,
} from "react-zoom-pan-pinch";
import useSWR from "swr";
import { UITrackingContext } from "../../utils/usertracking";

//async function to get image data from server

const fetcher = async (route) => {
  const response = await fetch(
    `https://pm-vis.uni-mannheim.de/api/vis/${route}`,
    {
      cache: "no-cache",
      credentials: "include",
    }
  );
  if (!response.ok) {
    throw new Error("Failed to fetch SVG");
  }
  const svgData = await response.text();

  const parser = new DOMParser();
  const svgDocument = parser.parseFromString(svgData, "image/svg+xml");
  const svgElement = svgDocument.querySelector("svg");

  if (svgElement) {
    const titleElements = svgElement.getElementsByTagName("title");
    Array.from(titleElements).forEach((title) => title.remove());
    svgElement.setAttribute("width", "100%");
    svgElement.setAttribute("height", "100%");
    svgElement.setAttribute("preserveAspectRatio", "xMidYMid meet");

    if (!svgElement.hasAttribute("viewBox")) {
      const width = svgElement.getAttribute("width") || "100";
      const height = svgElement.getAttribute("height") || "100";
      svgElement.setAttribute("viewBox", `0 0 ${width} ${height}`);
    }
  }

  const serializer = new XMLSerializer();
  const updatedSVG = serializer.serializeToString(svgDocument);

  return updatedSVG;
};

const Controls = ({ scale }) => {
  const { addTrackingChange } = useContext(UITrackingContext);
  const { zoomIn, zoomOut, resetTransform } = useControls();

  return (
    <div className="flex justify-end m-5 ">
      <Stack
        direction="row"
        spacing={1}
        className="items-center p-2 bg-white rounded-md shadow-md"
      >
        <IconButton
          aria-label="delete"
          onClick={() => {
            zoomIn();
            addTrackingChange("zoomIn", "zoom", "Graph", null);
          }}
        >
          <AddCircleIcon />
        </IconButton>
        <div className="font-medium font-semibold">
          {Math.round(scale * 100)}%
        </div>
        <IconButton
          aria-label="delete"
          onClick={() => {
            zoomOut();
            addTrackingChange("zoomOut", "zoom", "Graph", null);
          }}
        >
          <RemoveCircleIcon />
        </IconButton>
        <IconButton
          aria-label="delete"
          onClick={() => {
            resetTransform();
            addTrackingChange("resetZoom", "zoom", "Graph", 100);
          }}
        >
          <RestartAltIcon />
        </IconButton>
      </Stack>
    </div>
  );
};

const SVGDisplay = ({ selectedSVG, zoomResetTrigger }) => {
  const [scale, setScale] = useState(1); // State to hold current scale
  const { addTrackingChange } = useContext(UITrackingContext); // Access tracking function
  const { data: svgContent, error } = useSWR(selectedSVG, fetcher);
  const transformComponentRef = useRef(null);
  const previousSVGRef = useRef(selectedSVG);

  useEffect(() => {
    if (transformComponentRef.current) {
      if (previousSVGRef.current !== selectedSVG || zoomResetTrigger) {
        transformComponentRef.current.resetTransform();
        setScale(1);
      }
      previousSVGRef.current = selectedSVG;
    }
  }, [selectedSVG, zoomResetTrigger]);

  if (!svgContent) {
    return (
      <div className="flex items-center justify-center h-full">
        <p>Loading...</p>
      </div>
    );
  }

  const handleTransform = (e) => {
    setScale(e.instance.transformState.scale); // Update scale in state
  };
  const handleZoomStop = (e) => {
    addTrackingChange(
      "zoomChange",
      "zoom",
      "Graph",
      Math.round(e.instance.transformState.scale * 100)
    );
  };

  return (
    <div className="flex items-center justify-center w-full h-full">
      <TransformWrapper
        initialScale={1}
        onTransformed={handleTransform}
        onZoomStop={handleZoomStop}
        maxScale={4}
        ref={transformComponentRef}
      >
        {({ zoomIn, zoomOut, resetTransform, ...rest }) => (
          <div className="flex flex-col items-center justify-center w-full h-full p-5">
            <TransformComponent
              wrapperStyle={{
                width: "100%",
                height: "100%",
              }}
              contentStyle={{ width: "100%", height: "100%" }}
            >
              <div
                dangerouslySetInnerHTML={{ __html: svgContent }}
                style={{ width: "100%", height: "100%", objectFit: "contain" }}
              />
            </TransformComponent>
            <Controls scale={scale} transformRef={transformComponentRef} />
          </div>
        )}
      </TransformWrapper>
    </div>
  );
};

export default SVGDisplay;
