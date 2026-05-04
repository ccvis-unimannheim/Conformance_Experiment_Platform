"use client";

import { usePathname } from "next/navigation";
import Footer from "./Footer";

const HIDDEN_FOOTER_PATHS = [
  "/admin/experiment-setup",
  "/admin/task-selection",
  "/admin/idiom-selection",
];

export default function ConditionalFooter() {
  const pathname = usePathname();
  if (HIDDEN_FOOTER_PATHS.some((p) => pathname.startsWith(p))) return null;
  return <Footer />;
}
