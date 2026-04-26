"use client";

import { useRef, useState } from "react";

const FileUploadCard = ({ label, icon, onFileSelect }) => {
  const fileInputRef = useRef(null);
  const [selectedFile, setSelectedFile] = useState(null);

  const handleClick = () => {
    fileInputRef.current?.click();
  };

  const handleChange = (event) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setSelectedFile(file);
    onFileSelect?.(file);
  };

  return (
    <div
      onClick={handleClick}
      className="flex flex-col items-center justify-center p-8 bg-surface-container-low border-2 border-dashed border-outline-variant rounded hover:border-primary transition-colors group cursor-pointer"
    >
      <div className="w-12 h-12 rounded-full bg-white flex items-center justify-center mb-4 shadow-sm">
        <span className="material-symbols-outlined text-primary text-2xl">
          {icon}
        </span>
      </div>

      <h3 className="text-h3 mb-2">{label}</h3>

      <button
        type="button"
        onClick={(e) => {
          e.stopPropagation();
          handleClick();
        }}
        className="text-button bg-white border border-outline px-6 py-2 rounded-lg hover:bg-surface-variant transition-all active:scale-95"
      >
        {selectedFile ? "Replace File" : "Select File"}
      </button>

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleChange}
        className="hidden"
      />

      {selectedFile && (
        <p className="mt-3 text-body-sm text-on-surface-variant truncate max-w-full px-2">
          {selectedFile.name}
        </p>
      )}
    </div>
  );
};

export default FileUploadCard;
