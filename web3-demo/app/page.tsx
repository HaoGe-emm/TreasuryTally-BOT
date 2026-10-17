import TaskFlow from "./components/TaskFlow";
import HistoricalProof from "./components/HistoricalProof";
import CopyButton from "./components/CopyButton";
import { anchorAddress } from "@/lib/anchor";
import { latestAnchor } from "@/lib/anchor-proof";

export default function Home() {
  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span>
      <span>TreasuryTally <small>BOT CHAIN EDITION</small></span></div>
      <a href="https://github.com/HaoGe-emm/TreasuryTally-BOT" target="_blank" rel="noreferrer">GitHub 源码 ↗</a></header>
    <section className="lead" aria-label="产品与主网信息">
      <div><div className="eyebrow">ETH WUHAN 2026 · BOT CHAIN MAINNET</div>
        <h1>创建任务，<em>登记链上承诺。</em></h1>
        <p>TreasuryTally 使用 BOT Chain 登记任务承诺；任何人都能通过公开链上证据验证登记记录。</p>
      </div>
    </section>
    <TaskFlow />
    <section className="network-card" aria-label="主网部署与验证"><strong>主网部署与验证</strong>
        <span>BOT Chain Mainnet · Chain ID 677</span>
        <div><small>CommitmentAnchor</small><a href={`https://scan.botchain.ai/address/${anchorAddress}`}
          target="_blank" rel="noreferrer">{anchorAddress} ↗</a><CopyButton value={anchorAddress} label="复制合约地址" /></div>
        <div><small>最新 anchorTask</small><a href={`https://scan.botchain.ai/tx/${latestAnchor.transactionHash}`}
          target="_blank" rel="noreferrer">{latestAnchor.transactionHash} ↗</a><CopyButton value={latestAnchor.transactionHash} label="复制交易 Hash" /></div>
        <a href="#chain-proof">查看实时 Receipt、事件与存储核验 ↓</a>
    </section>
    <HistoricalProof />
    <footer><span>BOT Chain · 可公开核验的任务承诺</span>
      <span><a href="https://github.com/CH-ZHOU-0512/TreasuryTally" target="_blank" rel="noreferrer">原项目与作者 ↗</a>
        {process.env.NODE_ENV === "development" && <> · <a href="/lab">本地实验页 ↗</a></>}</span></footer>
  </main>;
}
