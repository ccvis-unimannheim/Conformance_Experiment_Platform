import Image from "next/image";
import ProjectLogo from "../../public/images/logo-no-background.png";
import UniLogo from "../../public/images/Logo_UMA_EN_RGB.png";

export default function HeaderLogos() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
      <Image priority src={ProjectLogo} width={79} height={44} alt="ProVi Logo" className="h-11 w-auto" style={{ objectFit: "contain" }} />
      <Image priority src={UniLogo} width={110} height={44} alt="University of Mannheim Logo" className="h-11 w-auto" style={{ objectFit: "contain" }} />
    </div>
  );
}
