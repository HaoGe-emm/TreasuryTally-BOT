import type { Metadata } from "next";
import "./style.css";

export const metadata: Metadata = {
  title: "TreasuryTally · BOT Chain",
  description: "可复核的任务承诺与 BOT Chain 本地开发演示"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
