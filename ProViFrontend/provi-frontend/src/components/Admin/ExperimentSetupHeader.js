import Link from "next/link";
import Image from "next/image";
import ProViLogo from "../../public/images/logo-no-background.png";
import UMALogo from "../../public/images/Logo_UMA_EN_RGB.png";

export default function ExperimentSetupHeader() {
  return (
    <header className="bg-white dark:bg-slate-900 border-b border-slate-200 dark:border-slate-800 sticky top-0 z-50">
      <div className="flex justify-between items-center w-full px-8 py-4 max-w-screen-2xl mx-auto">
        <div className="flex items-center gap-8">
          <Image
            alt="ProVi Logo"
            src={ProViLogo}
            height={32}
            className="h-8 w-auto"
          />
          <Image
            alt="University of Mannheim Logo"
            src={UMALogo}
            height={32}
            className="h-8 w-auto ml-4 pl-4 border-l border-slate-200 dark:border-slate-700"
          />
          <nav className="hidden md:flex gap-6">
            <Link
              href="/admin"
              className="font-sans antialiased text-sm font-medium text-slate-600 dark:text-slate-400 hover:text-[#0f3463] transition-colors"
            >
              Home
            </Link>
            <span className="font-sans antialiased text-sm font-medium text-[#0f3463] dark:text-blue-400 border-b-2 border-[#0f3463] pb-1">
              Experiment Setup
            </span>
          </nav>
        </div>
        <div>
          <span className="bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 font-sans text-xs font-bold px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 uppercase tracking-wider">
            Admin
          </span>
        </div>
      </div>
    </header>
  );
}
