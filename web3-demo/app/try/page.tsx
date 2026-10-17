"use client";

import { useCallback, useEffect, useState } from "react";
import { createWalletClient, custom, formatEther, getAddress, hexToBytes,
  isAddress, type Address, type Hex } from "viem";
import WalletPanel from "../components/WalletPanel";
import { anchorAbi, anchorAddress, anchorRuntimeHash, publicClient } from "@/lib/anchor";
import { verifyTaskAnchorEvidence, type ExpectedTaskAnchor,
  type VerifiedTaskAnchor } from "@/lib/anchor-proof";
import { botChain } from "@/lib/chain";
import { sha256, taskDomain, taskTypes, typedDataDigest, verifySpec,
  type TaskCommitmentMessage, type TaskSpec } from "@/lib/task";
import { useWalletConnection } from "@/lib/use-wallet";
import { createVisitorMessage, createVisitorTask, verifyVisitorCommitment,
  visitorServiceId, visitorServiceIdHash } from "@/lib/visitor-task";
import { friendlyWalletError, walletAccounts, walletChainId } from "@/lib/wallet";

type Draft = { task: TaskSpec; message: TaskCommitmentMessage };
type Signed = Draft & { signature: Hex; digest: Hex; serviceIdHash: Hex };
type Quote = { digest: Hex; gas: bigint; limit: bigint; price: bigint;
  maxFee: bigint; balance: bigint; nonce: number; at: number };
type Intent = Omit<ExpectedTaskAnchor, "transactionHash"> & { transactionHash?: Hex };
const intentKey = "treasurytally-bot677-visitor-anchor-intent-v1";
const zeroAddress = "0x0000000000000000000000000000000000000000";
const demoToken = "0xaBabc7Ddc03e501d190C676BF3d92ef0e6e87a3C";

function parseIntent(value: string | null): Intent | null {
  if (!value) return null;
  try {
    const item = JSON.parse(value) as Record<string, unknown>;
    for (const field of ["requester", "serviceSigner"])
      if (typeof item[field] !== "string" || !isAddress(item[field])) return null;
    for (const field of ["taskDigest", "specHash", "serviceIdHash"])
      if (typeof item[field] !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(item[field])) return null;
    if (item.transactionHash !== undefined &&
        (typeof item.transactionHash !== "string" || !/^0x[0-9a-fA-F]{64}$/.test(item.transactionHash)))
      return null;
    return item as Intent;
  } catch { return null; }
}

export default function VisitorDemo() {
  const wallet = useWalletConnection();
  const [token, setToken] = useState(demoToken);
  const [recipient, setRecipient] = useState("");
  const [block, setBlock] = useState("");
  const [latestBlock, setLatestBlock] = useState<bigint | null>(null);
  const [rpcStatus, setRpcStatus] = useState("BOT RPC 读取中…");
  const [writeEnabled, setWriteEnabled] = useState(false);
  const [writeStatus, setWriteStatus] = useState("公网写入状态检查中…");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [signed, setSigned] = useState<Signed | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [evidence, setEvidence] = useState<VerifiedTaskAnchor | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const invalidateDraft = () => {
    setDraft(null); setSigned(null); setQuote(null); setAcknowledged(false);
  };

  const refreshRpc = useCallback(async () => {
    setRpcStatus("BOT RPC 读取中…");
    try {
      const [chainId, head] = await Promise.all([publicClient.getChainId(), publicClient.getBlockNumber()]);
      if (chainId !== 677) throw new Error(`RPC Chain ID ${chainId} 与 677 不一致`);
      setLatestBlock(head); setBlock(current => current || head.toString());
      setRpcStatus(`BOT Chain 677 · 最新区块 ${head}`);
    } catch (error) { setLatestBlock(null); setRpcStatus("RPC 不可用或超时：" + friendlyWalletError(error)); }
  }, []);
  const refreshWriteStatus = useCallback(async () => {
    setWriteEnabled(false); setWriteStatus("公网写入状态检查中…");
    try {
      const response = await fetch("/api/visitor-write-status", { cache: "no-store" });
      const result = await response.json() as { enabled?: boolean; scope?: string };
      if (!response.ok || result.scope !== "VISITOR_SELF_DEMO_ONLY" || typeof result.enabled !== "boolean")
        throw new Error("写入状态接口返回无效结果");
      setWriteEnabled(result.enabled);
      setWriteStatus(result.enabled ? "访客 Demo 写入已开放；仍需本人钱包确认"
        : "访客 Demo 写入未开放；可继续签名和只读模拟");
    } catch (error) { setWriteStatus("写入状态检查失败，保持关闭：" + friendlyWalletError(error)); }
  }, []);
  useEffect(() => { void refreshRpc(); void refreshWriteStatus();
    setIntent(parseIntent(localStorage.getItem(intentKey))); }, [refreshRpc, refreshWriteStatus]);
  useEffect(() => { setDraft(null); setSigned(null); setQuote(null); setAcknowledged(false);
  }, [wallet.address, wallet.chainId]);
  useEffect(() => {
    if (!intent?.transactionHash) return;
    void verifyTaskAnchorEvidence(intent as ExpectedTaskAnchor)
      .then(setEvidence).catch(() => setEvidence(null));
  }, [intent]);

  async function requireContext(): Promise<Address> {
    if (!wallet.provider || !wallet.address || wallet.chainId !== 677)
      throw new Error("请先连接自己的钱包并切换到 BOT Chain 677");
    const [accounts, walletChain, rpcChain, code] = await Promise.all([
      walletAccounts(wallet.provider), walletChainId(wallet.provider),
      publicClient.getChainId(), publicClient.getCode({ address: anchorAddress })
    ]);
    if (accounts[0]?.toLowerCase() !== wallet.address.toLowerCase() ||
        walletChain !== 677 || rpcChain !== 677)
      throw new Error("钱包账户或钱包/RPC Chain ID 已变化");
    if (!code || code === "0x" ||
        (await sha256(hexToBytes(code))).toLowerCase() !== anchorRuntimeHash.toLowerCase())
      throw new Error("主网合约字节码与已核验版本不一致");
    return wallet.address;
  }
  async function prepare() {
    setBusy(true); setNotice(""); setDraft(null); setSigned(null); setQuote(null);
    try {
      const requester = await requireContext();
      const head = await publicClient.getBlockNumber();
      const height = Number(block);
      if (!Number.isSafeInteger(height) || height < 0 || BigInt(height) > head)
        throw new Error("请输入已产生且不超过当前最新区块的区块高度");
      if (!isAddress(token) || !isAddress(recipient))
        throw new Error("Token 和收款方必须是有效 EVM 地址");
      const id = crypto.randomUUID();
      const task = await createVisitorTask({ requester, token, recipient, block: height,
        taskId: `bot677-visitor-demo-${id}`, confirmedAt: new Date().toISOString() });
      const message = await createVisitorMessage(task, requester, `task-commitment-${id}`);
      await verifySpec(task);
      setDraft({ task, message });
      setNotice("已按原 TaskSpec 模型生成规范化任务。请审阅所有字段；此时尚未签名或写链。");
    } catch (error) { setNotice("任务准备失败：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function sign() {
    if (!draft || !wallet.provider || !wallet.address || busy) return;
    setBusy(true); setNotice(""); setSigned(null); setQuote(null);
    try {
      const requester = await requireContext();
      if (requester.toLowerCase() !== draft.message.requester.toLowerCase())
        throw new Error("当前钱包不是 TaskCommitment 的 requester");
      const client = createWalletClient({ account: requester, chain: botChain,
        transport: custom(wallet.provider) });
      const signature = await client.signTypedData({ domain: taskDomain, types: taskTypes,
        primaryType: "TaskCommitment", message: draft.message });
      const verified = await verifyVisitorCommitment(draft.task, draft.message, signature, requester);
      setSigned({ ...draft, signature, digest: verified.digest, serviceIdHash: verified.serviceIdHash });
      setNotice("EIP-712 签名已在浏览器恢复为当前 requester，按原算法生成 taskDigest。尚未上链。原始签名仅保留在此标签页内存中。");
    } catch (error) { setNotice("签名未完成或校验失败：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function preview() {
    if (!signed || !wallet.address || busy) return;
    setBusy(true); setNotice(""); setQuote(null);
    try {
      const requester = await requireContext();
      const verified = await verifyVisitorCommitment(signed.task, signed.message,
        signed.signature, requester);
      if (verified.digest !== signed.digest || verified.serviceIdHash !== signed.serviceIdHash)
        throw new Error("签名摘要或服务 ID 哈希变化");
      const existing = await publicClient.readContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "tasks", args: [requester, signed.digest] });
      if (existing[0] !== zeroAddress) throw new Error("该请求者已登记同一任务摘要");
      const args = [signed.digest, signed.task.spec_hash, signed.serviceIdHash, requester] as const;
      await publicClient.simulateContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "anchorTask", args, account: requester });
      const [gas, price, balance, latest, pending] = await Promise.all([
        publicClient.estimateContractGas({ address: anchorAddress, abi: anchorAbi,
          functionName: "anchorTask", args, account: requester }),
        publicClient.getGasPrice(), publicClient.getBalance({ address: requester }),
        publicClient.getTransactionCount({ address: requester, blockTag: "latest" }),
        publicClient.getTransactionCount({ address: requester, blockTag: "pending" })
      ]);
      if (latest !== pending) throw new Error("账户存在待处理交易，请先查询钱包活动");
      const limit = gas * 12n / 10n;
      if (balance < limit * price) throw new Error("BOT 余额不足以覆盖最高 Gas 预算");
      setQuote({ digest: signed.digest, gas, limit, price, maxFee: limit * price,
        balance, nonce: pending, at: Date.now() });
      setNotice("只读 eth_call 模拟成功；请查看网络、四个参数和最新费用。尚未发送交易。");
    } catch (error) { setNotice("只读预览失败：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function send() {
    if (!signed || !quote || !wallet.provider || !wallet.address || intent ||
        !writeEnabled || !acknowledged || busy) return;
    setBusy(true); setNotice("");
    try {
      const response = await fetch("/api/visitor-write-status", { cache: "no-store" });
      const gate = await response.json() as { enabled?: boolean; scope?: string };
      if (!response.ok || gate.enabled !== true || gate.scope !== "VISITOR_SELF_DEMO_ONLY")
        throw new Error("公网访客写入入口未开放");
      if (Date.now() - quote.at > 60_000 || quote.digest !== signed.digest)
        throw new Error("费用预览已过期，请重新运行只读模拟");
      const requester = await requireContext();
      const verified = await verifyVisitorCommitment(signed.task, signed.message,
        signed.signature, requester);
      if (verified.digest !== signed.digest || verified.serviceIdHash !== signed.serviceIdHash)
        throw new Error("签名校验或任务摘要变化");
      const args = [signed.digest, signed.task.spec_hash, signed.serviceIdHash, requester] as const;
      const [existing, nonce, gas, price, balance] = await Promise.all([
        publicClient.readContract({ address: anchorAddress, abi: anchorAbi,
          functionName: "tasks", args: [requester, signed.digest] }),
        publicClient.getTransactionCount({ address: requester, blockTag: "pending" }),
        publicClient.estimateContractGas({ address: anchorAddress, abi: anchorAbi,
          functionName: "anchorTask", args, account: requester }),
        publicClient.getGasPrice(), publicClient.getBalance({ address: requester })
      ]);
      if (existing[0] !== zeroAddress || nonce !== quote.nonce || gas > quote.limit ||
          price !== quote.price || balance < quote.maxFee)
        throw new Error("登记状态、nonce、Gas 报价或余额变化，请重新预览");
      await publicClient.simulateContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "anchorTask", args, account: requester });
      const attempt: Intent = { requester, taskDigest: signed.digest,
        specHash: signed.task.spec_hash, serviceIdHash: signed.serviceIdHash,
        serviceSigner: requester };
      localStorage.setItem(intentKey, JSON.stringify(attempt));
      setIntent(attempt);
      const client = createWalletClient({ account: requester, chain: botChain,
        transport: custom(wallet.provider) });
      let transactionHash: Hex;
      try {
        transactionHash = await client.writeContract({ address: anchorAddress,
          abi: anchorAbi, functionName: "anchorTask", args,
          gas: quote.limit, gasPrice: quote.price, nonce: quote.nonce });
      } catch (error) {
        // A wallet rejection is conclusive: no transaction was broadcast. Clear
        // the local one-shot guard so the visitor may review a fresh quote and
        // decide again. Keep the guard for every ambiguous transport failure.
        if (typeof error === "object" && error !== null &&
            "code" in error && (error as { code?: unknown }).code === 4001) {
          localStorage.removeItem(intentKey);
          setIntent(null);
          setAcknowledged(false);
          throw new Error("你在钱包中拒绝了交易；未发送交易。可重新运行只读预览后自行决定是否重试。");
        }
        throw error;
      }
      const submitted = { ...attempt, transactionHash };
      localStorage.setItem(intentKey, JSON.stringify(submitted));
      setIntent(submitted);
      await publicClient.waitForTransactionReceipt({ hash: transactionHash,
        confirmations: 2, timeout: 60_000 });
      setEvidence(await verifyTaskAnchorEvidence(submitted));
      setNotice("BOT 677 成功回执、TaskAnchored 事件与 tasks 存储已交叉核验。");
    } catch (error) { setNotice("提交或核验状态需人工确认，禁止重复点击：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function recheck() {
    if (!intent?.transactionHash) return;
    setBusy(true); setNotice("");
    try { setEvidence(await verifyTaskAnchorEvidence(intent as ExpectedTaskAnchor));
      setNotice("BOT 677 回执、事件与存储已重新核验。此读回不重验已丢失的原始签名。"); }
    catch (error) { setEvidence(null); setNotice("链上读回尚未成功：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }

  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span>
      <span>TreasuryTally <small>VISITOR DEMO · BOT 677</small></span></div>
      <a href="/">返回历史登记 ↗</a></header>
    <section className="hero compact"><div className="eyebrow">自己创建 · 自己签署 · 自己审阅</div>
      <h1>新的任务，<em>新的承诺。</em></h1>
      <p>用你的钱包作为请求者和自助演示服务签名者，为一个指定区块的 ERC-20 转账核查范围生成 TaskSpec。登记只记录任务承诺；不会代你检查报表，也不会转移代币。</p>
    </section>
    <section className="panel"><div className="panel-head"><span className="step">01</span><h2>连接自己的钱包</h2></div>
      <WalletPanel wallet={wallet} /><p className="hint">{rpcStatus}</p>
      <button className="secondary" onClick={() => void refreshRpc()}>重查 BOT RPC</button></section>
    <section className="panel"><div className="panel-head"><span className="step">02</span><h2>定义 Demo 核查范围</h2></div>
      <p className="muted">你的钱包将成为 TaskSpec 财库和 requester；你填写 Token、不同的收款方与已产生的单个区块。仅指定核查范围，不声称该区块有转账。排除规则为空，最多 200 条。</p>
      <div className="inputs"><label>ERC-20 Token 地址<input value={token}
        onChange={event => { setToken(event.target.value); invalidateDraft(); }} placeholder="0x…"/></label>
        <label>收款方地址<input value={recipient}
          onChange={event => { setRecipient(event.target.value); invalidateDraft(); }} placeholder="0x…"/></label>
        <label>BOT Chain 区块高度<input value={block} inputMode="numeric"
          onChange={event => { setBlock(event.target.value); invalidateDraft(); }} placeholder="已产生的区块"/></label></div>
      <button onClick={prepare} disabled={busy || !wallet.address || wallet.chainId !== 677 || latestBlock === null}>
        生成并审阅 TaskSpec</button>
      {draft && <div className="preview"><h3>规范化 TaskSpec · 尚未签名</h3>
        <pre>{JSON.stringify(draft.task, null, 2)}</pre>
        <dl className="facts"><div><dt>specHash</dt><dd>{draft.task.spec_hash}</dd></div>
          <div><dt>内部服务 ID</dt><dd>{visitorServiceId}（非 ERC-8004 身份）</dd></div>
          <div><dt>serviceSigner</dt><dd>{draft.message.requester}（访客本人）</dd></div></dl>
        <h3>完整 EIP-712 签名内容</h3>
        <pre>{JSON.stringify({ domain: taskDomain, types: taskTypes,
          primaryType: "TaskCommitment", message: draft.message }, null, 2)}</pre>
        <p className="hint">EIP-712 消息摘要：{typedDataDigest(draft.message)}</p>
        <button onClick={sign} disabled={busy || !!signed}>Sign Task · 请求钱包签名</button>
      </div>}
    </section>
    <section className="panel"><div className="panel-head"><span className="step">03</span><h2>模拟与钱包交易</h2>
      <span className="pill caution">{writeEnabled ? "访客写入已开放" : "访客写入未开放"}</span></div>
      <p className="muted">签名完成仍未上链。只有主动运行只读预览、审阅参数、勾选确认并点击登记，才会出现钱包交易请求。</p>
      <p className="hint" role="status">{writeStatus}</p>
      <button className="secondary" onClick={() => void refreshWriteStatus()}>检查公网写入状态</button>
      {signed && <dl className="facts"><div><dt>已恢复签名者</dt><dd>{signed.message.requester}</dd></div>
        <div><dt>taskDigest</dt><dd>{signed.digest}</dd></div>
        <div><dt>serviceIdHash</dt><dd>{signed.serviceIdHash}</dd></div></dl>}
      <div className="actions"><button className="secondary" onClick={preview}
        disabled={!signed || busy || !!intent}>运行只读 anchorTask 模拟与费用预览</button></div>
      {quote && signed && <div className="preview"><h3>真实主网交易预览 · 尚未发送</h3>
        <dl className="facts"><div><dt>From</dt><dd>{signed.message.requester}</dd></div>
          <div><dt>To</dt><dd>{anchorAddress}</dd></div>
          <div><dt>网络 / 函数</dt><dd>BOT Chain 677 · anchorTask(bytes32,bytes32,bytes32,address)</dd></div>
          <div><dt>taskDigest</dt><dd>{signed.digest}</dd></div>
          <div><dt>specHash</dt><dd>{signed.task.spec_hash}</dd></div>
          <div><dt>serviceIdHash</dt><dd>{signed.serviceIdHash}</dd></div>
          <div><dt>serviceSigner</dt><dd>{signed.message.requester}</dd></div>
          <div><dt>Gas 估算 / 上限</dt><dd>{quote.gas.toString()} / {quote.limit.toString()}</dd></div>
          <div><dt>Gas 报价</dt><dd>{quote.price.toString()} wei</dd></div>
          <div><dt>最高费用 / 余额</dt><dd>{formatEther(quote.maxFee)} / {formatEther(quote.balance)} BOT</dd></div>
          <div><dt>nonce</dt><dd>{quote.nonce}</dd></div></dl>
        <label className="acknowledge"><input type="checkbox" checked={acknowledged}
          onChange={event => setAcknowledged(event.target.checked)}/>
          我确认这是自己的 Demo 核查任务；登记会消耗 BOT Gas，不能证明转账或财务核验通过。</label>
        <button disabled={!writeEnabled || !acknowledged || busy || !!intent}
          onClick={send}>在 BOT Chain 登记我的任务（仅一次）</button>
      </div>}
      {intent && <div className="warning">本机已有提交尝试，禁止盲目重复：{intent.transactionHash
        ? <a href={`https://scan.botchain.ai/tx/${intent.transactionHash}`} target="_blank"
            rel="noreferrer">{intent.transactionHash} ↗</a>
        : "尚无交易 Hash；请检查钱包活动和 nonce，勿再次点击。"}</div>}
      {intent?.transactionHash && <button className="secondary" onClick={recheck} disabled={busy}>
        只读重查回执、TaskAnchored 与 tasks 存储</button>}
      {evidence && <dl className="facts signed"><div><dt>链上状态</dt><dd>成功回执、事件与存储一致</dd></div>
        <div><dt>区块 / Gas</dt><dd>{evidence.blockNumber.toString()} / {evidence.gasUsed.toString()}</dd></div>
        <div><dt>实际费用</dt><dd>{formatEther(evidence.feeWei)} BOT</dd></div></dl>}
      {notice && <p className="notice" role="status">{notice}</p>}
    </section>
    <section className="panel"><div className="panel-head"><span className="step">i</span><h2>技术与业务边界</h2></div>
      <p className="muted">本流程使用原 TaskSpec 字段与规范化 SHA-256、TrustReceipt v1 EIP-712 消息及原 taskDigest 算法。签名在浏览器恢复为当前 requester；原始签名不上传或持久化。刷新后只能读回公开交易，无法重验已丢失的原始签名。</p>
      <p className="muted">EIP-712 domain 没有 verifyingContract，消息不直接绑定 serviceSigner，expiresAt 为空。已部署合约只记录调用者、摘要和服务地址，不能代替服务方授权、转账核查或财务审计。此处 serviceSigner 是访客本人，service_id 仅为自助 Demo 标签。</p>
    </section>
    <footer><span>访客自行签名与支付 Gas · 不自动发送交易</span><a href="/">查看已登记的历史任务 ↗</a></footer>
  </main>;
}
