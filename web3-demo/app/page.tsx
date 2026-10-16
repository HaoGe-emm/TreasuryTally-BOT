"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  custom, decodeEventLog, getAddress, hexToBytes, isAddress, type Address, type Hex
} from "viem";
import { createWalletClient } from "viem";
import { anchorAbi, anchorAddress, anchorRuntimeHash, publicClient } from "@/lib/anchor";
import { botChain } from "@/lib/chain";
import { confirmedDemo, matchesConfirmedDemoBinding, requireConfirmedDemoBinding } from "@/lib/demo";
import { collectWallets, friendlyWalletError, switchToBot, walletAccounts, walletChainId,
  type Provider, type WalletChoice } from "@/lib/wallet";
import { parseTaskSpec, requireBotContext, sha256, taskDigest, taskDomain, taskTypes, utcTimestamp,
  typedDataDigest, verifySignature, verifySpec, type TaskCommitmentMessage, type TaskSpec } from "@/lib/task";

const mainnetWritesEnabled = process.env.NEXT_PUBLIC_ENABLE_MAINNET_WRITES === "true";
const taskSignaturesEnabled = process.env.NEXT_PUBLIC_ENABLE_TASK_SIGNATURES === "true";
const samplePath = "/demo-task-spec.json";
const confirmedDemoPath = "/bot677-demo/task-spec.json";
type Preview = { task: TaskSpec; hash: Hex; label: string };
type Signed = { message: TaskCommitmentMessage; signature: Hex; digest: Hex; serviceIdHash: Hex; serviceSigner: Address };
type Prepared = Omit<Signed, "signature" | "digest">;

export default function Home() {
  const [wallets, setWallets] = useState<WalletChoice[]>([]);
  const [choiceId, setChoiceId] = useState("");
  const [provider, setProvider] = useState<Provider | null>(null);
  const activeProvider = useRef<Provider | null>(null);
  const refreshVersion = useRef(0);
  const [address, setAddress] = useState<Address | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [rpcChainId, setRpcChainId] = useState<number | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [serviceId, setServiceId] = useState("");
  const [serviceSigner, setServiceSigner] = useState("");
  const [signed, setSigned] = useState<Signed | null>(null);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [contractStatus, setContractStatus] = useState("尚未部署");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [tx, setTx] = useState<Hex | null>(null);

  useEffect(() => collectWallets(setWallets), []);
  const refreshRpc = useCallback(async () => {
    setRpcChainId(null);
    try { setRpcChainId(await publicClient.getChainId()); }
    catch { setRpcChainId(null); }
  }, []);
  useEffect(() => { void refreshRpc(); }, [refreshRpc]);
  // An injected provider never becomes the default signing choice.
  const selected = useMemo(() => wallets.find(x => x.id === choiceId) || null, [wallets, choiceId]);
  useEffect(() => { setPrepared(null); setSigned(null); }, [address, chainId, preview, serviceId, serviceSigner]);

  const refreshWallet = useCallback(async (active: Provider) => {
    const version = ++refreshVersion.current;
    const [accounts, network] = await Promise.all([walletAccounts(active), walletChainId(active)]);
    if (activeProvider.current !== active || refreshVersion.current !== version) return;
    setAddress(accounts[0] && isAddress(accounts[0]) ? getAddress(accounts[0]) : null);
    setChainId(network);
  }, []);
  useEffect(() => {
    if (!provider) return;
    const changed = () => { void refreshWallet(provider).catch(e => {
      if (activeProvider.current !== provider) return;
      refreshVersion.current++;
      setAddress(null); setChainId(null); setPrepared(null); setSigned(null);
      setNotice(friendlyWalletError(e));
    }); };
    provider.on?.("accountsChanged", changed);
    provider.on?.("chainChanged", changed);
    const disconnected = () => {
      activeProvider.current = null; refreshVersion.current++;
      setProvider(null); setAddress(null); setChainId(null); setPrepared(null); setSigned(null);
    };
    provider.on?.("disconnect", disconnected);
    return () => {
      provider.removeListener?.("accountsChanged", changed);
      provider.removeListener?.("chainChanged", changed);
      provider.removeListener?.("disconnect", disconnected);
    };
  }, [provider, refreshWallet]);
  useEffect(() => {
    if (!anchorAddress || !anchorRuntimeHash) {
      setContractStatus("尚未部署：未配置经过审阅的主网地址与字节码哈希");
      return;
    }
    void (async () => {
      try {
        if (await publicClient.getChainId() !== 677) throw new Error("RPC Chain ID 不匹配");
        const code = await publicClient.getCode({ address: anchorAddress });
        if (!code || code === "0x") throw new Error("地址上没有合约字节码");
        const actual = await sha256(hexToBytes(code));
        if (actual.toLowerCase() !== anchorRuntimeHash.toLowerCase())
          throw new Error("合约字节码 SHA-256 与审阅值不符");
        setContractStatus("已通过 RPC 字节码核对");
      } catch (error) { setContractStatus("合约校验失败：" + friendlyWalletError(error)); }
    })();
  }, []);

  async function connect() {
    if (!selected) { setNotice("未检测到 EVM 钱包，请安装 MetaMask 或 OKX Wallet。"); return; }
    setBusy(true); setNotice("");
    try {
      const accounts = await selected.provider.request({ method: "eth_requestAccounts" });
      if (!Array.isArray(accounts) || !accounts[0] || !isAddress(accounts[0]))
        throw new Error("钱包未返回有效地址");
      const network = await walletChainId(selected.provider);
      activeProvider.current = selected.provider; refreshVersion.current++;
      setProvider(selected.provider); setAddress(getAddress(accounts[0]));
      setChainId(network); setSigned(null);
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  function disconnect() {
    activeProvider.current = null; refreshVersion.current++;
    setProvider(null); setAddress(null); setChainId(null); setSigned(null);
    setNotice("已在本页面断开。钱包授权如需撤销，请到钱包扩展中操作。");
  }
  async function switchNetwork() {
    if (!provider) return;
    setBusy(true); setNotice("");
    try { await switchToBot(provider); await refreshWallet(provider); }
    catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function loadTask(raw: unknown, label: string) {
    setSigned(null); setPreview(null); setTx(null);
    const task = parseTaskSpec(raw);
    const hash = await verifySpec(task);
    setPreview({ task, hash, label });
    setNotice(task.chain_id === 677
      ? "TaskSpec 规范化哈希已核对。链上承诺仍需绑定请求者钱包和服务签名者。"
      : "这是上游公开 Demo 任务，原链为 Sepolia；不能当作 BOT Chain 主网任务提交。");
  }
  async function loadSample() {
    try {
      const response = await fetch(samplePath);
      if (!response.ok) throw new Error("无法读取上游 Demo 样例");
      await loadTask(await response.json(), "上游公开 Demo · Sepolia");
    } catch (error) { setNotice(friendlyWalletError(error)); }
  }
  async function loadConfirmedDemo() {
    try {
      const response = await fetch(confirmedDemoPath, { cache: "no-store" });
      if (!response.ok) throw new Error("无法读取 BOT Demo TaskSpec");
      await loadTask(await response.json(), "已确认范围 · BOT 677 内部 Demo");
      setServiceId(confirmedDemo.serviceId);
      setServiceSigner(confirmedDemo.serviceSigner);
    } catch (error) { setNotice(friendlyWalletError(error)); }
  }
  async function importTask(file?: File) {
    if (!file) return;
    try {
      if (file.size > 64 * 1024) throw new Error("TaskSpec 文件超过 64 KB");
      await loadTask(JSON.parse(await file.text()), file.name);
    } catch (error) { setNotice(friendlyWalletError(error)); }
  }
  async function prepareTask() {
    if (!provider || !address || !preview) return;
    setBusy(true); setNotice(""); setSigned(null);
    try {
      requireBotContext(preview.task, address, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      requireConfirmedDemoBinding(preview.task, address, serviceId, serviceSigner);
      if (!isAddress(serviceSigner) || !serviceId.trim() || serviceId.length > 200)
        throw new Error("请输入有效服务 ID 和服务签名者地址");
      const message: TaskCommitmentMessage = {
        commitmentId: "task-commitment-" + crypto.randomUUID(),
        taskId: preview.task.task_id,
        specHash: preview.hash,
        requester: address,
        serviceId: serviceId.trim(),
        createdAt: utcTimestamp(new Date().toISOString(), true),
        expiresAt: ""
      };
      const serviceIdHash = await sha256(new TextEncoder().encode(message.serviceId));
      setPrepared({ message, serviceIdHash, serviceSigner: getAddress(serviceSigner) });
      setNotice("已准备任务承诺，请核对完整内容和服务签名者后再签署。");
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function signTask() {
    if (!taskSignaturesEnabled || !provider || !address || !preview || !prepared) return;
    setBusy(true); setNotice(""); setSigned(null);
    try {
      requireBotContext(preview.task, prepared.message.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      requireConfirmedDemoBinding(preview.task, prepared.message.requester, serviceId, serviceSigner);
      if (prepared.serviceSigner.toLowerCase() !== serviceSigner.toLowerCase() ||
          prepared.message.serviceId !== serviceId.trim())
        throw new Error("服务选择已变化，请重新准备承诺");
      const message = prepared.message;
      const wallet = createWalletClient({ account: address, chain: botChain, transport: custom(provider) });
      const signature = await wallet.signTypedData({
        domain: taskDomain, types: taskTypes, primaryType: "TaskCommitment", message
      });
      if (activeProvider.current !== provider) throw new Error("钱包连接已变化，已丢弃过期签名结果");
      requireBotContext(preview.task, message.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      if (!(await verifySignature(message, signature))) throw new Error("钱包签名无法恢复到请求者地址");
      const digest = await taskDigest(message, signature);
      setSigned({ ...prepared, signature, digest });
      setNotice("已验证本地 EIP-712 签名；尚未发送链上交易。");
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function anchorTask() {
    const contractAddress = anchorAddress;
    if (!mainnetWritesEnabled || !contractAddress || !anchorRuntimeHash ||
        contractStatus !== "已通过 RPC 字节码核对" ||
        !provider || !address || !signed || !preview) return;
    setBusy(true); setNotice("");
    try {
      requireBotContext(preview.task, signed.message.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      requireConfirmedDemoBinding(preview.task, address, serviceId, serviceSigner);
      if (signed.message.requester.toLowerCase() !== address.toLowerCase() ||
          serviceSigner.toLowerCase() !== signed.serviceSigner.toLowerCase() ||
          !(await verifySignature(signed.message, signed.signature)))
        throw new Error("链、请求者或签名已变化，请重新准备承诺");
      const existing = await publicClient.readContract({
        address: contractAddress, abi: anchorAbi, functionName: "tasks",
        args: [address, signed.digest]
      });
      if (existing[0] !== "0x0000000000000000000000000000000000000000")
        throw new Error("该请求者已登记相同任务摘要");
      const wallet = createWalletClient({ account: address, chain: botChain, transport: custom(provider) });
      if (activeProvider.current !== provider) throw new Error("钱包连接已变化，请重新准备承诺");
      const hash = await wallet.writeContract({
        address: contractAddress, abi: anchorAbi, functionName: "anchorTask",
        args: [signed.digest, preview.hash, signed.serviceIdHash, signed.serviceSigner]
      });
      setTx(hash);
      const receipt = await publicClient.waitForTransactionReceipt({ hash, confirmations: 2 });
      if (receipt.status !== "success") throw new Error("交易回执显示执行失败");
      const [transaction, canonicalBlock, currentCode, currentChain] = await Promise.all([
        publicClient.getTransaction({ hash }), publicClient.getBlock({ blockNumber: receipt.blockNumber }),
        publicClient.getCode({ address: contractAddress }), publicClient.getChainId()
      ]);
      if (currentChain !== 677 || !currentCode || currentCode === "0x" ||
          (await sha256(hexToBytes(currentCode))).toLowerCase() !== anchorRuntimeHash.toLowerCase() ||
          canonicalBlock.hash !== receipt.blockHash || receipt.transactionHash !== hash ||
          transaction.from.toLowerCase() !== signed.message.requester.toLowerCase() ||
          transaction.to?.toLowerCase() !== contractAddress.toLowerCase())
        throw new Error("链、字节码、区块或交易来源核对失败，保留已提交交易供检查");
      const events = receipt.logs.filter(log => log.address.toLowerCase() === contractAddress.toLowerCase())
        .map(log => { try { return decodeEventLog({ abi: anchorAbi, data: log.data, topics: log.topics }); }
                      catch { return null; } })
        .filter(log => log?.eventName === "TaskAnchored");
      const event = events[0];
      if (events.length !== 1 || !event || event.eventName !== "TaskAnchored" ||
          event.args.taskDigest.toLowerCase() !== signed.digest.toLowerCase() ||
          event.args.requester.toLowerCase() !== address.toLowerCase() ||
          event.args.serviceSigner.toLowerCase() !== signed.serviceSigner.toLowerCase() ||
          event.args.specHash.toLowerCase() !== preview.hash.toLowerCase() ||
          event.args.serviceIdHash.toLowerCase() !== signed.serviceIdHash.toLowerCase())
        throw new Error("交易成功，但 TaskAnchored 事件字段不匹配");
      const stored = await publicClient.readContract({ address: contractAddress, abi: anchorAbi,
        functionName: "tasks", args: [signed.message.requester, signed.digest] });
      if (stored[0].toLowerCase() !== signed.message.requester.toLowerCase() ||
          stored[1].toLowerCase() !== signed.serviceSigner.toLowerCase())
        throw new Error("链上存储与任务承诺不匹配");
      setNotice("交易回执及 TaskAnchored 事件已核对；财务报表尚未因此获得认证。");
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  const readyToSign = !!(provider && address && preview && preview.task.chain_id === 677 &&
    chainId === 677 && rpcChainId === 677 && isAddress(serviceSigner) && serviceId.trim() &&
    matchesConfirmedDemoBinding(preview.task, address, serviceId, serviceSigner));
  const readyToAnchor = !!(readyToSign && signed && !tx && mainnetWritesEnabled && anchorAddress &&
    anchorRuntimeHash && contractStatus === "已通过 RPC 字节码核对");
  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span><span>TreasuryTally <small>BOT CHAIN EDITION</small></span></div>
      <a href="https://github.com/CH-ZHOU-0512/TreasuryTally" target="_blank" rel="noreferrer">原项目 ↗</a></header>
    <section className="hero"><div className="eyebrow">ETH WUHAN 2026 · LOCAL DEVELOPMENT PREVIEW</div>
      <h1>让每笔任务承诺<br/><em>有据可查。</em></h1>
      <p>核验服务商报表、链上资金流与公开回执。当前页面展示钱包连接和可复核的任务承诺流程，链上登记只有经过主网部署审查后才会开放。</p>
      <div className="hero-meta"><span>01 / 任务范围</span><span>02 / 钱包签名</span><span>03 / 链上登记</span></div>
    </section>
    <div className="grid">
      <section className="panel">
        <div className="panel-head"><span className="step">01</span><h2>连接钱包</h2><span className="pill">BOT Chain 677</span></div>
        <p className="muted">连接动作由你主动发起。支持发现 MetaMask、OKX Wallet 及其他 EVM 钱包。扩展名称由注入方自报，请核对钱包弹窗。</p>
        {wallets.length > 0 ? <label>选择钱包<select value={choiceId} disabled={busy || !!address} onChange={e => setChoiceId(e.target.value)}>
          <option value="">请选择钱包</option>
          {wallets.map(w => <option key={w.id} value={w.id}>{w.name} · {w.source}{w.rdns ? ` · ${w.rdns}` : ""}</option>)}</select></label>
          : <div className="empty">未检测到钱包。请安装钱包扩展或使用钱包内置浏览器。</div>}
        <div className="actions">{!address ? <button onClick={connect} disabled={busy || !selected}>Connect Wallet</button>
          : <button className="secondary" onClick={disconnect}>断开页面连接</button>}
          {address && chainId !== 677 && <button onClick={switchNetwork} disabled={busy}>切换到 BOT Chain</button>}</div>
        <dl className="facts"><div><dt>钱包地址</dt><dd>{address || "未连接"}</dd></div>
          <div><dt>钱包 Chain ID</dt><dd>{chainId ?? "—"}</dd></div>
          <div><dt>RPC Chain ID</dt><dd>{rpcChainId ?? "无法读取"} <button className="secondary" onClick={() => void refreshRpc()}>重试</button></dd></div>
          <div><dt>当前状态</dt><dd>{address ? chainId === 677 ? "钱包已连接至 BOT Chain" : "网络不匹配" : "等待连接"}</dd></div></dl>
      </section>
      <section className="panel">
        <div className="panel-head"><span className="step">02</span><h2>任务承诺预览</h2></div>
        <p className="muted">导入已确认的 TaskSpec JSON；只在浏览器中核对上游规范化 SHA-256，不上传报告。</p>
        <div className="actions"><button className="secondary" onClick={loadSample}>查看上游 Demo 任务</button>
          <button className="secondary" onClick={loadConfirmedDemo}>查看 BOT 677 Demo 任务</button>
          <label className="file-button">导入 TaskSpec<input type="file" accept="application/json,.json"
            onChange={e => void importTask(e.target.files?.[0])}/></label></div>
        {preview ? <div className="preview"><div className="eyebrow">{preview.label}</div>
          <dl className="facts"><div><dt>任务 ID</dt><dd>{preview.task.task_id}</dd></div>
            <div><dt>原任务 Chain ID</dt><dd>{preview.task.chain_id}</dd></div>
            <div><dt>Token / 区块</dt><dd>{preview.task.token_address}<br/>{preview.task.start_block} — {preview.task.end_block}</dd></div>
            <div><dt>规范化 spec_hash</dt><dd>{preview.hash}</dd></div></dl>
          {preview.task.chain_id !== 677 && <div className="warning">此上游 Demo 样例来自 Sepolia，不适合 BOT Chain 主网登记。</div>}
          {preview.task.chain_id === 677 && <div className="warning">这是用户确认的核查范围。一次只读 RPC 查询返回 0 条匹配 Transfer；这不是财务核验结论。</div>}
          {preview.hash === confirmedDemo.specHash && <p className="hint">请求者：{confirmedDemo.requester}<br/>内部 Demo 服务：{confirmedDemo.serviceId}<br/>服务签名者：{confirmedDemo.serviceSigner}</p>}
          <details><summary>完整 TaskSpec 与哈希依据</summary><pre>{JSON.stringify(preview.task, null, 2)}</pre>
            <p className="hint">SHA-256：上游 TaskSpec 模型规范化 JSON，排除 spec_hash；UTF-8、键排序、无额外空格，禁止浮点数。</p></details>
        </div> : <div className="empty">尚未选择任务。不会生成任意字符串的“业务哈希”。</div>}
        <div className="inputs"><label>服务 ID<input value={serviceId} onChange={e => { setServiceId(e.target.value); setSigned(null); }}
          placeholder="与上游 TaskCommitment.service_id 一致"/></label>
          <label>服务签名者地址<input value={serviceSigner} onChange={e => { setServiceSigner(e.target.value); setSigned(null); }}
            placeholder="0x…" autoComplete="off"/></label></div>
        <button className="secondary" onClick={prepareTask} disabled={!readyToSign || busy}>准备任务承诺</button>
        {prepared && <div className="preview"><h3>签署前核对</h3><pre>{JSON.stringify({ domain: taskDomain, ...prepared }, null, 2)}</pre>
          <p className="hint">沿用上游 EIP-712 字段；该签名域没有 verifyingContract。服务签名者由 anchorTask 交易登记，不属于上游任务签名的字段；请核对其授权来源。</p>
          <button onClick={signTask} disabled={busy || !taskSignaturesEnabled}>签署 EIP-712 任务承诺</button>
          {!taskSignaturesEnabled && <p className="hint">任务签名安全锁已启用；本阶段仅预览范围和哈希。</p>}</div>}
        {signed && <dl className="facts signed"><div><dt>签名者 / 请求者</dt><dd>{signed.message.requester}</dd></div>
          <div><dt>登记的服务签名者</dt><dd>{signed.serviceSigner}</dd></div>
          <div><dt>EIP-712 摘要</dt><dd>{typedDataDigest(signed.message)}</dd></div>
          <div><dt>完整任务摘要</dt><dd>{signed.digest}</dd></div>
          <div><dt>服务 ID SHA-256</dt><dd>{signed.serviceIdHash}</dd></div></dl>}
      </section>
    </div>
    <section className="panel anchor-panel"><div className="panel-head"><span className="step">03</span><h2>链上登记</h2>
      <span className="pill caution">主网写入未开放</span></div>
      <p className="muted">登记只证明请求者钱包在 BOT Chain 上承诺过指定任务摘要与服务签名者，不证明服务报表真实，也不代表财务核验通过。</p>
      <dl className="facts"><div><dt>候选合约</dt><dd>CommitmentAnchor.sol</dd></div>
        <div><dt>主网地址</dt><dd>{anchorAddress || "尚未部署"}</dd></div>
        <div><dt>字节码核对</dt><dd>{contractStatus}</dd></div>
        <div><dt>交易</dt><dd>{tx ? <a href={`https://scan.botchain.ai/tx/${tx}`} target="_blank" rel="noreferrer">{tx} ↗</a> : "未提交"}</dd></div></dl>
      <button disabled={!readyToAnchor || busy} onClick={anchorTask}>在 BOT Chain 登记 anchorTask</button>
      {!mainnetWritesEnabled && <p className="hint">阶段 1 安全锁已启用：主网写入必须在后续独立批准、部署和配置后开放。</p>}
    </section>
    {notice && <div className="notice" role="status">{notice}</div>}
    <footer><span>公开 Demo 数据仅用于流程展示 · 不构成财务核验</span><a href="/preflight">主网只读预检 ↗</a><a href="/deploy">部署预览 ↗</a><a href="https://scan.botchain.ai" target="_blank" rel="noreferrer">BOT Explorer ↗</a></footer>
  </main>;
}
