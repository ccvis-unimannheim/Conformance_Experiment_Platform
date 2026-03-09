"use client";

import { useState } from "react";

export default function LoginModal({ onLoginSuccess }) {
  const [password, setPassword] = useState("");
  const [errorMessage, setErrorMessage] = useState("");

  const handleLogin = async () => {
    // The pre-computed hash of the correct password change if required
    const hashedPassword =
      "e7706d9d5f86be71deb7d7d36be1b68dfb762714fb9520a09cce1a5b4b7d42b6";

    try {
      // Hash the entered password to get the same hash format as stored password
      const encoder = new TextEncoder();
      const data = encoder.encode(password);
      const hashBuffer = await crypto.subtle.digest("SHA-256", data);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const enteredHashedPassword = hashArray
        .map((byte) => byte.toString(16).padStart(2, "0"))
        .join("");

      // Compare the hashes 
      if (enteredHashedPassword === hashedPassword) {
        onLoginSuccess();
      } else {
        setErrorMessage("Invalid password. Please try again.");
      }
    } catch (error) {
      console.error("Error hashing password:", error);
      setErrorMessage("An error occurred. Please try again.");
    }
  };

  return (
    <div className="fixed inset-0 flex items-center justify-center bg-gray-900 bg-opacity-75 z-50">
      <div className="bg-white p-6 rounded-md shadow-md w-96">
        <h2 className="text-lg font-bold mb-4">Admin Login</h2>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Enter admin password"
          className="w-full p-2 border rounded-md mb-4"
        />
        {errorMessage && <p className="text-red-500">{errorMessage}</p>}
        <div className="flex justify-end gap-4">
          <button
            onClick={handleLogin}
            className="px-4 py-2 bg-blue-500 text-white rounded-md hover:bg-blue-600"
          >
            Login
          </button>
        </div>
      </div>
    </div>
  );
}
