import { Inter } from "next/font/google";
import "material-symbols";

const inter = Inter({ subsets: ["latin"] });

export default function AdminLayout({ children }) {
  return (
    <div className={inter.className}>
      {children}
    </div>
  );
}