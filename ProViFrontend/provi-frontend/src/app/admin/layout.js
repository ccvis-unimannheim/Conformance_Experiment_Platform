import { Inter } from "next/font/google";
// material-symbols installed locally via npm — no Google CDN needed at runtime
import "material-symbols";

const inter = Inter({ subsets: ["latin"] });

/**
 * Admin layout — wraps all /admin/* pages.
 * Inter is self-hosted by Next.js at build time (no Google API call at runtime).
 * material-symbols is served from node_modules (no Google API call at runtime).
 */
export default function AdminLayout({ children }) {
  return (
    <div className={inter.className}>
      {children}
    </div>
  );
}
