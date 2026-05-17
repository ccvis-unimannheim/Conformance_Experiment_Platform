"use client";

import { usePathname } from "next/navigation";
import Footer from "./Footer";

const HIDDEN_FOOTER_PATHS = [
  "/prequestionnaire",
  "/knowledgequestion",
  "/endpage",
];

export default function ConditionalFooter() {
  const pathname = usePathname();
  if (HIDDEN_FOOTER_PATHS.some((p) => pathname.startsWith(p))) return null;
  return <Footer />;
}
