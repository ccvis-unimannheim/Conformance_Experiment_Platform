"use client";

import Link from "next/link";
import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";

const navItems = [
  { key: "home", label: "Home", href: "/admin" },
  { key: "experiment-setup", label: "Experiment Setup", href: "/admin/experiments/new" },
];

/** Next static image import → string URL (or StaticImageData with .src) */
function logoSrc(imp) {
  if (imp && typeof imp === "object" && "src" in imp) return imp.src;
  return imp;
}

const AdminNav = ({ activeLink = "home" }) => {
  return (
    <header className="bg-white border-b border-outline-variant sticky top-0 z-50">
      <div className="flex justify-between items-center w-full px-8 py-4 max-w-screen-2xl mx-auto">
        <div className="flex items-center gap-8">
          <img
            src={logoSrc(ProjectLogo)}
            alt="ProVi Logo"
            className="h-8 w-auto"
            width={32}
            height={32}
          />
          <img
            src={logoSrc(UniLogo)}
            alt="University of Mannheim Logo"
            className="h-8 w-auto ml-4 pl-4 border-l border-outline-variant"
            width={32}
            height={32}
          />
          <nav className="hidden md:flex gap-6">
            {navItems.map((item) => {
              const isActive = item.key === activeLink;
              return (
                <Link
                  key={item.key}
                  href={item.href}
                  className={
                    isActive
                      ? "text-sm font-medium text-primary-container border-b-2 border-primary-container pb-1"
                      : "text-sm font-medium text-secondary hover:text-primary-container transition-colors"
                  }
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <span className="bg-surface-container text-on-surface-variant text-xs font-bold px-3 py-1.5 rounded-lg border border-outline-variant uppercase tracking-wider">
          Admin
        </span>
      </div>
    </header>
  );
};

export default AdminNav;
