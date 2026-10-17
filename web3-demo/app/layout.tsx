import type { Metadata } from "next";
import "./style.css";

export const metadata: Metadata = {
  title: "TreasuryTally · BOT Chain",
  description: "TreasuryTally 在 BOT Chain Mainnet 登记任务承诺，并公开读回真实交易、事件与合约状态。"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="zh-CN"><body>{children}</body></html>;
}
