"use client";

import React from "react";

// Citation box at the bottom of the participant intro pages. `text` null shows
// the default Carmona et al. (2018) reference with its original formatting;
// admin-entered text is shown as plain text, line breaks kept.
export default function IntroCitation({ text }) {
  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: "0.75rem",
      padding: "0.875rem 1rem",
      backgroundColor: "#f2f4f4",
      borderRadius: "0.5rem",
      borderLeft: "3px solid #adb3b4",
    }}>
      <span className="material-symbols-outlined" style={{ color: "#adb3b4", fontSize: "1.1rem", flexShrink: 0, marginTop: "0.1rem" }}>menu_book</span>
      {text ? (
        <p style={{ margin: 0, fontSize: "0.8125rem", color: "#5a6061", lineHeight: 1.65, whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>
          {text}
        </p>
      ) : (
        <p style={{ margin: 0, fontSize: "0.8125rem", color: "#5a6061", lineHeight: 1.65 }}>
          Definitions adapted from: Carmona, J., van Dongen, B., Solti, A., &amp; Weidlich, M. (2018).{" "}
          <em>Conformance Checking: Relating Processes and Models</em>. Springer.{" "}
          <span style={{ fontFamily: "monospace", fontSize: "0.75rem" }}>
            ISBN 978-3-319-99413-0 · DOI 10.1007/978-3-319-99414-7
          </span>
        </p>
      )}
    </div>
  );
}
