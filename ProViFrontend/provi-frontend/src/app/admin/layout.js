"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { Inter } from "next/font/google";
import "material-symbols";
import LoginModal from "../../components/Admin/LoginModal";

const inter = Inter({ subsets: ["latin"] });

const AUTH_KEY = "adminAuthed";

export default function AdminLayout({ children }) {
  const pathname = usePathname();
  const router = useRouter();

  const [hydrated, setHydrated] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    setAuthed(localStorage.getItem(AUTH_KEY) === "1");
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (!authed && pathname !== "/admin") {
      router.replace("/admin");
    }
  }, [hydrated, authed, pathname, router]);

  const handleLoginSuccess = () => {
    localStorage.setItem(AUTH_KEY, "1");
    setAuthed(true);
  };

  if (!hydrated) {
    return <div className={inter.className} />;
  }

  const onAdminRoot = pathname === "/admin";

  return (
    <div className={inter.className}>
      {authed || onAdminRoot ? children : null}
      {!authed && onAdminRoot && (
        <LoginModal onLoginSuccess={handleLoginSuccess} />
      )}
    </div>
  );
}
