"use client";

import HistoricalProof from "./components/HistoricalProof";
import WalletPanel from "./components/WalletPanel";
import { useWalletConnection } from "@/lib/use-wallet";

export default function Home() {
  const wallet = useWalletConnection();
  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span>
      <span>TreasuryTally <small>BOT CHAIN EDITION</small></span></div>
      <a href="https://github.com/CH-ZHOU-0512/TreasuryTally" target="_blank" rel="noreferrer">原项目与作者 ↗</a></header>
    <section className="hero"><div className="eyebrow">ETH WUHAN 2026 · BOT CHAIN MAINNET</div>
      <h1>任务承诺已上链。<br/><em>证据随时可读。</em></h1>
      <p>TreasuryTally 将核查范围写成可复核的 TaskSpec，再由请求者钱包登记承诺。这里展示已发生的 BOT Chain 主网交易，并现场读取它的事件和合约状态。</p>
      <div className="hero-meta"><span>真实合约</span><span>真实 anchorTask 交易</span><span>实时只读核验</span></div>
    </section>
    <HistoricalProof />
    <div className="grid">
      <section className="panel"><div className="panel-head"><span className="step">02</span><h2>当前访客的钱包</h2></div>
        <p className="muted">这是你的当前会话状态，与上方已经完成的历史登记是两件事。连接钱包本身不会签名或发送交易。</p>
        <WalletPanel wallet={wallet} />
        <p className="hint">{wallet.address ? "当前访客已连接；尚未为访客创建或签署新任务。"
          : "当前访客尚未连接或签署任务；历史登记照常可读。"}</p>
      </section>
      <section className="panel"><div className="panel-head"><span className="step">03</span><h2>自己创建一份演示承诺</h2></div>
        <p className="muted">新访客可以使用自己的钱包和选定的 BOT 区块范围生成新的 Demo TaskSpec，审阅完整 EIP-712 消息，再主动签名。写链前会检查合约、重复登记、模拟结果和费用，并由钱包本人确认。</p>
        <a className="button-link" href="/try">打开访客任务流程 →</a>
        <p className="hint">Production 已开放访客主动发起 BOT Chain 677 主网登记。请使用自己的钱包和任务摘要，由本人签名、审阅交易参数与费用预览，再主动提交并在钱包中确认，自行支付 BOT Gas。应急开关可暂停写入，只读预览不受影响。</p>
      </section>
    </div>
    <section className="panel"><div className="panel-head"><span className="step">?</span><h2>任务范围与技术限制</h2></div>
      <p className="muted">已登记任务是内部 Demo：检查固定区块 26,879,920 的指定 USDT、财库和收款方。此前一次 RPC 日志过滤返回零条匹配 Transfer。交易成功只证明任务承诺已登记，不证明真实 USDT 转账、服务报表正确或财务验收通过。内部 service_id 不是已注册的 ERC-8004 身份。</p>
      <details><summary>EIP-712、合约及来源说明</summary>
        <p className="muted">原 TreasuryTally TaskCommitment 使用 TrustReceipt v1、Chain ID 677。签名域没有 verifyingContract，消息不直接绑定 serviceSigner，已登记 Demo 的 expiresAt 为空。应用在发送前检查请求者、任务和服务方，但已部署合约本身不验证 EIP-712 签名、服务方授权、资金转账或财务结论。历史签名未保存，页面刷新后只重新验证公开的交易、事件和存储，不声称重新验证原签名。</p>
        <p className="muted">本独立版本保留<a href="https://github.com/CH-ZHOU-0512/TreasuryTally" target="_blank" rel="noreferrer">上游 TreasuryTally</a> 来源与作者署名。公开页面不上传私有报表、密钥或原始钱包签名。</p>
      </details>
    </section>
    <footer><span>公开 Demo · 链上任务承诺 ≠ 财务核验</span>
      <span><a href="/try">新访客演示 ↗</a>{process.env.NODE_ENV === "development" && <> · <a href="/lab">本地实验页 ↗</a></>}</span></footer>
  </main>;
}
