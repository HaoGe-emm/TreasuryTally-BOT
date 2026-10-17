"use client";

import { useCallback, useEffect, useState } from "react";
import { createWalletClient, custom, formatEther, getAddress, hexToBytes,
  isAddress, type Address, type Hex } from "viem";
import WalletPanel from "./WalletPanel";
import { anchorAbi, anchorAddress, anchorRuntimeHash, publicClient } from "@/lib/anchor";
import { verifyTaskAnchorEvidence, type ExpectedTaskAnchor,
  type VerifiedTaskAnchor } from "@/lib/anchor-proof";
import { botChain } from "@/lib/chain";
import { sha256, taskDomain, taskTypes, typedDataDigest, verifySpec,
  type TaskCommitmentMessage, type TaskSpec } from "@/lib/task";
import { useWalletConnection } from "@/lib/use-wallet";
import { createVisitorMessage, createVisitorTask, verifyVisitorCommitment,
  visitorServiceId, visitorServiceIdHash } from "@/lib/visitor-task";
import { friendlyWalletError, isWalletUserRejection, walletAccounts, walletChainId } from "@/lib/wallet";

type Draft = { task: TaskSpec; message: TaskCommitmentMessage };
type Signed = Draft & { signature: Hex; digest: Hex; serviceIdHash: Hex };
type Quote = { digest: Hex; gas: bigint; limit: bigint; price: bigint;
  maxFee: bigint; balance: bigint; nonce: number; at: number };
type Intent = Omit<ExpectedTaskAnchor, "transactionHash"> & { transactionHash?: Hex };
const intentKeyPrefix = "treasurytally-bot677-visitor-anchor-intent-v1:";
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

export default function TaskFlow() {
  const wallet = useWalletConnection();
  const [token, setToken] = useState(demoToken);
  const [recipient, setRecipient] = useState("");
  const [block, setBlock] = useState("");
  const [latestBlock, setLatestBlock] = useState<bigint | null>(null);
  const [rpcStatus, setRpcStatus] = useState("BOT RPC 读取中…");
  const [writeEnabled, setWriteEnabled] = useState(false);
  const [writeStatus, setWriteStatus] = useState("主网登记状态检查中…");
  const [draft, setDraft] = useState<Draft | null>(null);
  const [signed, setSigned] = useState<Signed | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [intent, setIntent] = useState<Intent | null>(null);
  const [evidence, setEvidence] = useState<VerifiedTaskAnchor | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const activeIntent = intent && wallet.address &&
    intent.requester.toLowerCase() === wallet.address.toLowerCase() ? intent : null;
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
    setWriteEnabled(false); setWriteStatus("主网登记状态检查中…");
    try {
      const response = await fetch("/api/visitor-write-status", { cache: "no-store" });
      const result = await response.json() as { enabled?: boolean; scope?: string; reason?: string };
      if (!response.ok || result.scope !== "VISITOR_SELF_DEMO_ONLY" || typeof result.enabled !== "boolean")
        throw new Error("写入状态接口返回无效结果");
      setWriteEnabled(result.enabled);
      setWriteStatus(result.enabled ? "主网任务登记已开放；仍需本人审阅并确认钱包交易"
        : result.reason === "emergency_switch" ? "主网登记已由应急开关关闭；只读功能仍可使用"
        : result.reason === "preview_environment" ? "预览部署默认禁止写入；生产 Vercel 才默认开放"
        : result.reason === "unsupported_host" ? "此运行环境不开放主网写入"
        : result.reason === "local_default_closed" ? "本地开发默认禁止写入；公网生产版按部署规则开放"
        : "主网登记已关闭；可继续签名和只读模拟");
    } catch (error) { setWriteStatus("写入状态检查失败，保持关闭：" + friendlyWalletError(error)); }
  }, []);
  useEffect(() => { void refreshRpc(); void refreshWriteStatus();
  }, [refreshRpc, refreshWriteStatus]);
  useEffect(() => {
    setIntent(wallet.address
      ? parseIntent(localStorage.getItem(intentKeyPrefix + wallet.address.toLowerCase()))
      : null);
  }, [wallet.address]);
  useEffect(() => { setDraft(null); setSigned(null); setQuote(null); setAcknowledged(false);
  }, [wallet.address, wallet.chainId]);
  useEffect(() => {
    if (!activeIntent?.transactionHash) { setEvidence(null); return; }
    void verifyTaskAnchorEvidence(activeIntent as ExpectedTaskAnchor)
      .then(setEvidence).catch(() => setEvidence(null));
  }, [activeIntent]);

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
      setNotice("签名已验证，任务摘要已生成。尚未上链；请先查看模拟和费用。");
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
    if (!signed || !quote || !wallet.provider || !wallet.address || activeIntent ||
        !writeEnabled || !acknowledged || busy) return;
    setBusy(true); setNotice("");
    try {
      const response = await fetch("/api/visitor-write-status", { cache: "no-store" });
      const gate = await response.json() as { enabled?: boolean; scope?: string };
      if (!response.ok || gate.enabled !== true || gate.scope !== "VISITOR_SELF_DEMO_ONLY")
        throw new Error("主网登记入口未开放");
      if (Date.now() - quote.at > 60_000 || quote.digest !== signed.digest)
        throw new Error("费用预览已过期，请重新运行只读模拟");
      const requester = await requireContext();
      const previousAttempt = parseIntent(localStorage.getItem(intentKeyPrefix + requester.toLowerCase()));
      if (previousAttempt) {
        setIntent(previousAttempt);
        throw new Error("此钱包已有提交尝试；先只读核对交易状态，禁止重复提交");
      }
      const verified = await verifyVisitorCommitment(signed.task, signed.message,
        signed.signature, requester);
      if (verified.digest !== signed.digest || verified.serviceIdHash !== signed.serviceIdHash)
        throw new Error("签名校验或任务摘要变化");
      const args = [signed.digest, signed.task.spec_hash, signed.serviceIdHash, requester] as const;
      const [existing, latestNonce, nonce, gas, price, balance] = await Promise.all([
        publicClient.readContract({ address: anchorAddress, abi: anchorAbi,
          functionName: "tasks", args: [requester, signed.digest] }),
        publicClient.getTransactionCount({ address: requester, blockTag: "latest" }),
        publicClient.getTransactionCount({ address: requester, blockTag: "pending" }),
        publicClient.estimateContractGas({ address: anchorAddress, abi: anchorAbi,
          functionName: "anchorTask", args, account: requester }),
        publicClient.getGasPrice(), publicClient.getBalance({ address: requester })
      ]);
      if (existing[0] !== zeroAddress || latestNonce !== nonce || nonce !== quote.nonce || gas > quote.limit ||
          price !== quote.price || balance < quote.maxFee)
        throw new Error("登记状态、nonce、Gas 报价或余额变化，请重新预览");
      await publicClient.simulateContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "anchorTask", args, account: requester });
      const finalRequester = await requireContext();
      if (finalRequester.toLowerCase() !== requester.toLowerCase())
        throw new Error("发送前钱包账户已变化；请重新连接、签名并预览");
      const finalVerification = await verifyVisitorCommitment(signed.task, signed.message,
        signed.signature, finalRequester);
      if (finalVerification.digest !== signed.digest ||
          finalVerification.serviceIdHash !== signed.serviceIdHash)
        throw new Error("发送前签名、TaskSpec 或服务 ID 摘要复核失败");
      const finalGateResponse = await fetch("/api/visitor-write-status", { cache: "no-store" });
      const finalGate = await finalGateResponse.json() as { enabled?: boolean; scope?: string };
      if (!finalGateResponse.ok || finalGate.enabled !== true ||
          finalGate.scope !== "VISITOR_SELF_DEMO_ONLY")
        throw new Error("公网写入应急开关已关闭；未请求钱包交易");
      const attempt: Intent = { requester, taskDigest: signed.digest,
        specHash: signed.task.spec_hash, serviceIdHash: signed.serviceIdHash,
        serviceSigner: requester };
      const storageKey = intentKeyPrefix + requester.toLowerCase();
      localStorage.setItem(storageKey, JSON.stringify(attempt));
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
        if (isWalletUserRejection(error)) {
          localStorage.removeItem(storageKey);
          setIntent(null);
          setAcknowledged(false);
          throw new Error("你在钱包中拒绝了交易；未发送交易。可重新运行只读预览后自行决定是否重试。");
        }
        throw error;
      }
      const submitted = { ...attempt, transactionHash };
      localStorage.setItem(storageKey, JSON.stringify(submitted));
      setIntent(submitted);
      await publicClient.waitForTransactionReceipt({ hash: transactionHash,
        confirmations: 2, timeout: 60_000 });
      setEvidence(await verifyTaskAnchorEvidence(submitted));
      setNotice("BOT 677 成功回执、TaskAnchored 事件与 tasks 存储已交叉核验。");
    } catch (error) { setNotice("提交或核验状态需人工确认，禁止重复点击：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function recheck() {
    if (!activeIntent?.transactionHash) return;
    setBusy(true); setNotice("");
    try { setEvidence(await verifyTaskAnchorEvidence(activeIntent as ExpectedTaskAnchor));
      setNotice("BOT 677 回执、事件与存储已重新核验。"); }
    catch (error) { setEvidence(null); setNotice("链上读回尚未成功：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }

  return <>
    <div className="setup-grid">
    <section className="panel wallet-step"><div className="panel-head"><span className="step">01</span><h2>连接钱包</h2></div>
      <WalletPanel wallet={wallet} /><p className="hint">{rpcStatus}</p>
      <button className="secondary" onClick={() => void refreshRpc()}>重查 BOT RPC</button></section>
    <section className="panel task-step"><div className="panel-head"><span className="step">02</span><h2>创建任务</h2></div>
      <p className="muted">填写 Token、收款方和已产生的 BOT Chain 区块。当前钱包是任务请求者与财库地址；此处创建的是核查范围。</p>
      <div className="inputs"><label>ERC-20 Token 地址<input value={token}
        onChange={event => { setToken(event.target.value); invalidateDraft(); }} placeholder="0x…"/></label>
        <label>收款方地址<input value={recipient}
          onChange={event => { setRecipient(event.target.value); invalidateDraft(); }} placeholder="0x…"/></label>
        <label>BOT Chain 区块高度<input value={block} inputMode="numeric"
          onChange={event => { setBlock(event.target.value); invalidateDraft(); }} placeholder="已产生的区块"/></label></div>
      <button onClick={prepare} disabled={busy || !wallet.address || wallet.chainId !== 677 || latestBlock === null}>
        生成并审阅 TaskSpec</button>
      {(!wallet.address || wallet.chainId !== 677 || latestBlock === null) &&
        <p className="hint" role="status">先连接钱包、切换至 BOT Chain 677，并等待 RPC 读取成功后，才能创建任务。</p>}
      {draft && <div className="preview"><h3>规范化 TaskSpec · 尚未签名</h3>
        <pre>{JSON.stringify(draft.task, null, 2)}</pre>
        <dl className="facts"><div><dt>specHash</dt><dd>{draft.task.spec_hash}</dd></div>
          <div><dt>内部服务 ID</dt><dd>{visitorServiceId}（非 ERC-8004 身份）</dd></div>
          <div><dt>serviceSigner</dt><dd>{draft.message.requester}（当前钱包本人）</dd></div></dl>
        <h3>完整 EIP-712 签名内容</h3>
        <pre>{JSON.stringify({ domain: taskDomain, types: taskTypes,
          primaryType: "TaskCommitment", message: draft.message }, null, 2)}</pre>
        <p className="hint">EIP-712 消息摘要：{typedDataDigest(draft.message)}</p>
        <p className="hint">本次签名用于演示任务确认，当前合约不验证此消息签名。请确认任务内容后继续。<a href="https://github.com/HaoGe-emm/TreasuryTally-BOT/blob/main/web3-demo/README.md" target="_blank" rel="noreferrer">技术详情 ↗</a></p>
        <button onClick={sign} disabled={busy || !!signed}>Sign Task · 请求钱包签名</button>
      </div>}
    </section>
    </div>
    <section className="panel"><div className="panel-head"><span className="step">03</span><h2>签名并登记</h2>
      <span className="pill caution">{writeEnabled ? "主网登记已开放" : "主网登记暂不可用"}</span></div>
      <p className="muted">签名完成仍未上链。只有主动运行只读预览、审阅参数、勾选确认并点击登记，才会出现钱包交易请求。</p>
      {!signed && <p className="hint">请先在上方生成 TaskSpec、审阅 EIP-712 内容并亲自签名；完成后解锁只读模拟。</p>}
      <p className="hint" role="status">{writeStatus}</p>
      <button className="secondary" onClick={() => void refreshWriteStatus()}>检查主网登记状态</button>
      {signed && <dl className="facts"><div><dt>已恢复签名者</dt><dd>{signed.message.requester}</dd></div>
        <div><dt>taskDigest</dt><dd>{signed.digest}</dd></div>
        <div><dt>serviceIdHash</dt><dd>{signed.serviceIdHash}</dd></div></dl>}
      <div className="actions"><button className="secondary" onClick={preview}
        disabled={!signed || busy || !!activeIntent}>运行只读 anchorTask 模拟与费用预览</button></div>
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
          我已核对任务参数和预计费用，登记将消耗我钱包中的 BOT Gas。</label>
        <button disabled={!writeEnabled || !acknowledged || busy || !!activeIntent}
          onClick={send}>在 BOT Chain 登记我的任务（仅一次）</button>
      </div>}
      {activeIntent && <div className="warning">此钱包已有提交尝试，禁止盲目重复：{activeIntent.transactionHash
        ? <a href={`https://scan.botchain.ai/tx/${activeIntent.transactionHash}`} target="_blank"
            rel="noreferrer">{activeIntent.transactionHash} ↗</a>
        : "尚无交易 Hash；请检查钱包活动和 nonce，勿再次点击。"}</div>}
      {activeIntent?.transactionHash && <button className="secondary" onClick={recheck} disabled={busy}>
        只读重查回执、TaskAnchored 与 tasks 存储</button>}
      {evidence && <dl className="facts signed"><div><dt>链上状态</dt><dd>成功回执、事件与存储一致</dd></div>
        <div><dt>区块 / Gas</dt><dd>{evidence.blockNumber.toString()} / {evidence.gasUsed.toString()}</dd></div>
        <div><dt>实际费用</dt><dd>{formatEther(evidence.feeWei)} BOT</dd></div></dl>}
      {notice && <p className="notice" role="status">{notice}</p>}
    </section>
  </>;
}
