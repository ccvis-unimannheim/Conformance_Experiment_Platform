"use client";

import { Suspense } from "react";
import { Inter } from "next/font/google";
import "material-symbols";

const inter = Inter({ subsets: ["latin"] });

// Access to /admin and /api/admin is controlled by nginx basic auth
// (provibackend/nginx/nginx.conf); the admin UI has no login of its own.
// The Suspense boundary lets the wizard pages that call useSearchParams()
// fall back to client rendering instead of failing the static prerender.
export default function AdminLayout({ children }) {
  return (
    <div className={inter.className}>
      <Suspense fallback={null}>{children}</Suspense>
    </div>
  );
}
