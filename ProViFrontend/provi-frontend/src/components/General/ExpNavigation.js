import Link from "next/link";
import Image from "next/image";
import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";
/*
Second Navigation for Experiment
*/
const ExpNavigation = () => {
  return (
    <nav className="flex items-center justify-between px-8 py-4 bg-white shadow-md">
      <div className="flex flex-row items-center">
        <div>
          <Image
            priority
            src={ProjectLogo}
            width={100}
            height={100}
            alt="Project Logo"
          />
        </div>
        <div>
          <Image
            priority
            src={UniLogo}
            width={200}
            height={200}
            alt="Uni Logo"
          />
        </div>
      </div>
      <div></div>
    </nav>
  );
};

export default ExpNavigation;
