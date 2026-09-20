"use client";

import { useEffect } from "react";

export default function Toast({ message, isError, visible, onHide }) {
  useEffect(() => {
    if (!visible) return;
    const timer = setTimeout(onHide, isError ? 4000 : 3500);
    return () => clearTimeout(timer);
  }, [visible, isError, onHide]);

  if (!visible) return null;

  return (
    <div
      className={`fixed bottom-6 right-6 text-sm px-4 py-2.5 rounded-lg shadow-lg z-50 transition-all
        ${isError ? "bg-error text-white" : "bg-on-surface text-white"}`}
    >
      {message}
    </div>
  );
}
