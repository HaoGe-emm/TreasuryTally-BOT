import TaskFlow from "./components/TaskFlow";
import HistoricalProof from "./components/HistoricalProof";
import CopyButton from "./components/CopyButton";
import { anchorAddress } from "@/lib/anchor";
import { historicalAnchor } from "@/lib/anchor-proof";

export default function Home() {
  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span>
      <span>TreasuryTally <small>BOT CHAIN EDITION</small></span></div>
      <a href="https://github.com/HaoGe-emm/TreasuryTally-BOT" target="_blank" rel="noreferrer">GitHub 源码 ↗</a></header>
    <section className="lead" aria-label="产品与主网信息">
      <div><div className="eyebrow">ETH WUHAN 2026 · BOT CHAIN MAINNET</div>
        <h1>创建任务，<em>登记链上承诺。</em></h1>
        <p>连接钱包，为指定区块生成 TaskSpec，审阅签名和费用，再决定是否登记。登记不代表资金转账或财务核验通过。</p>
      </div>
    </section>
    <TaskFlow />
    <section className="network-card" aria-label="主网部署与验证"><strong>主网部署与验证</strong>
        <span>BOT Chain Mainnet · Chain ID 677</span>
        <div><small>CommitmentAnchor</small><a href={`https://scan.botchain.ai/address/${anchorAddress}`}
          target="_blank" rel="noreferrer">{anchorAddress} ↗</a><CopyButton value={anchorAddress} label="复制合约地址" /></div>
        <div><small>已确认的 anchorTask</small><a href={`https://scan.botchain.ai/tx/${historicalAnchor.transactionHash}`}
          target="_blank" rel="noreferrer">{historicalAnchor.transactionHash} ↗</a><CopyButton value={historicalAnchor.transactionHash} label="复制交易 Hash" /></div>
        <a href="#chain-proof">查看实时 Receipt、事件与存储核验 ↓</a>
    </section>
    <HistoricalProof />
    <footer><span>公开演示 · 链上任务承诺 ≠ 财务核验</span>
      <span><a href="https://github.com/CH-ZHOU-0512/TreasuryTally" target="_blank" rel="noreferrer">原项目与作者 ↗</a>
        {process.env.NODE_ENV === "development" && <> · <a href="/lab">本地实验页 ↗</a></>}</span></footer>
  </main>;
}
