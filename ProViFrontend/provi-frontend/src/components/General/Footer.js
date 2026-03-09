import Link from "next/link";
import Image from "next/image";
import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";

const Footer = () => {
  return (
    <div className="flex flex-row justify-between px-8 py-4 bg-white shadow-md">
      <div className="flex flex-row items-center">
        <div className="py-2">
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
      <div className="flex flex-col pr-10 ">
        <h3 className="text-xl font-bold">Legal</h3>
        <Link
          href="/imprint"
          className="pt-1 font-medium text-gray-600 hover:text-gray-900"
        >
          Imprint
        </Link>
        <Link
          href="/dataprotection"
          className="pt-1 font-medium text-gray-600 hover:text-gray-900"
        >
          Data Protection Declaration
        </Link>
      </div>
    </div>
  );
};

export default Footer;
