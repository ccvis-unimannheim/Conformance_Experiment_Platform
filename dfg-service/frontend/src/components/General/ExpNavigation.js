import Link from "next/link";
import HeaderLogos from "./HeaderLogos";
/*
Second Navigation for Experiment
*/
const ExpNavigation = () => {
  return (
    <nav className="flex items-center justify-between px-8 py-4 bg-white shadow-md">
      <HeaderLogos />
      <div></div>
    </nav>
  );
};

export default ExpNavigation;
