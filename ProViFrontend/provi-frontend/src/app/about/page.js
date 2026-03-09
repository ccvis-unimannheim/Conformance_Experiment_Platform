"use client";

import Head from "next/head";
import Link from "next/link";
import Navigation from "../../components/General/Navigation.js";

export default function About() {
  return (
    <div className="flex flex-col min-h-screen bg-gray-100">
      <Head>
        <title>About ProVi</title>
      </Head>
      {/* Navigation Bar */}
      <Navigation />

      {/* Main Content */}
      <main className="flex items-center justify-center flex-grow p-8">
        <div className="max-w-3xl p-6 bg-white rounded-md shadow-md">
          <h1 className="mb-4 text-2xl font-bold">About ProVi</h1>
          <p className="mb-4 text-gray-600">
            Welcome to ProVi! This page is dedicated to providing information
            about the ProVi project. Enter any necessary information.
          </p>
          <p className="mb-4 text-gray-600">
            Placeholder content: ProVi is a project aimed at visualizing
            directly-follow graphs and providing user interactions for
            educational purposes. The goal is to make process mining more
            accessible and understandable through interactive visual tools.
          </p>
          <p className="text-gray-600">
            Please feel free to explore the other sections of the website for
            more details about the features and functionalities provided by
            ProVi.
          </p>
        </div>
      </main>
    </div>
  );
}
