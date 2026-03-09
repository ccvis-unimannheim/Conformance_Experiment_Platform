import React, { useEffect, useState } from "react";

const ScrollProgressBar = () => {
  const [scrollProgress, setScrollProgress] = useState(0);

  const updateScrollProgress = () => {
    const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
    const totalScroll = scrollHeight - clientHeight;
    const scrollValue = (scrollTop / totalScroll) * 100;
    setScrollProgress(scrollValue);
  };

  useEffect(() => {
    window.addEventListener("scroll", updateScrollProgress);
    return () => {
      window.removeEventListener("scroll", updateScrollProgress);
    };
  }, []);

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: `${scrollProgress}%`,
        height: "10px",
        backgroundColor: "#4caf50",
        zIndex: 1000,
        transition: "width 0.2s ease-out",
      }}
    ></div>
  );
};

export default ScrollProgressBar;
