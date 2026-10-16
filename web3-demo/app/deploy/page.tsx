"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { createWalletClient, custom, formatEther, getAddress, getContractAddress,
  hexToBytes, isAddress, type Abi, type Address, type Hex } from "viem";
import { botChain } from "@/lib/chain";
import { publicClient } from "@/lib/anchor";
import { sha256 } from "@/lib/task";
import { collectWallets, friendlyWalletError, switchToBot, walletAccounts, walletChainId,
  type Provider, type WalletChoice } from "@/lib/wallet";

const deploymentEnabled = process.env.NODE_ENV === "development" &&
  process.env.NEXT_PUBLIC_ENABLE_MAINNET_DEPLOY === "true";
const authorizedDeployer = getAddress("0x89F415bb42e356E8b892C10B05522e0a8Ef151F3");
const attemptStorageKey = "treasurytally:bot677:commitment-anchor:deployment-attempt:v1";
const previousBudget = 8_095_360_000_000_000n;
const reviewCeiling = previousBudget * 110n / 100n;
const creationSha256 = "0x189ea148974f79cee0447b7e763295f2727e50f4d29b16540e4de2ab57c9a85a";
const runtimeSha256 = "0xe19c6b11680cbd60c5fb6061d52052c65596e48b9c10cbc59415538e03a75eaf";
type Artifact = { compiler: string; evmVersion: string; optimizer: { enabled: boolean; runs: number };
  abi: readonly unknown[]; bytecode: Hex; deployedBytecode: Hex };
type Quote = { address: Address; artifact: Artifact; nonce: number; latestNonce: number;
  balance: bigint; gasEstimate: bigint; gasLimit: bigint; gasPrice: bigint;
  maxCost: bigint; predicted: Address; quotedAt: string };
type DeploymentAttempt = { address: Address; nonce: number; predicted: Address;
  creationSha256: string; startedAt: string; hash?: Hex };

async function reviewedArtifact(): Promise<Artifact> {
  const response = await fetch("/CommitmentAnchor.paris.json", { cache: "no-store" });
  if (!response.ok) throw new Error("无法读取本地候选合约产物");
  const artifact = await response.json() as Artifact;
  if (artifact.compiler !== "0.8.30+commit.73712a01.Emscripten.clang" ||
      artifact.evmVersion !== "paris" || !artifact.optimizer?.enabled || artifact.optimizer.runs !== 200 ||
      !/^0x[0-9a-f]+$/i.test(artifact.bytecode) ||
      await sha256(hexToBytes(artifact.bytecode)) !== creationSha256 ||
      await sha256(hexToBytes(artifact.deployedBytecode)) !== runtimeSha256)
    throw new Error("候选合约编译设置或字节码校验值不匹配");
  return artifact;
}

export default function DeployReview() {
  const [wallets, setWallets] = useState<WalletChoice[]>([]);
  const [choiceId, setChoiceId] = useState("");
  const [provider, setProvider] = useState<Provider | null>(null);
  const activeProvider = useRef<Provider | null>(null);
  const [address, setAddress] = useState<Address | null>(null);
  const [walletChain, setWalletChain] = useState<number | null>(null);
  const [quote, setQuote] = useState<Quote | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [tx, setTx] = useState<Hex | null>(null);
  const [verifiedAddress, setVerifiedAddress] = useState<Address | null>(null);
  const [attempt, setAttempt] = useState<DeploymentAttempt | null>(null);
  const [attemptLocked, setAttemptLocked] = useState(true);
  useEffect(() => collectWallets(setWallets), []);
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(attemptStorageKey);
      if (saved) {
        const parsed = JSON.parse(saved) as DeploymentAttempt;
        if (parsed.address?.toLowerCase() !== authorizedDeployer.toLowerCase() ||
            parsed.creationSha256 !== creationSha256 || !Number.isSafeInteger(parsed.nonce))
          throw new Error("本地部署尝试记录不符合本次审阅值");
        setAttempt(parsed);
        if (parsed.hash && /^0x[0-9a-f]{64}$/i.test(parsed.hash)) setTx(parsed.hash);
      } else setAttemptLocked(false);
    } catch (error) { setNotice("部署入口已锁定：" + friendlyWalletError(error)); }
  }, []);
  const selected = useMemo(() => wallets.find(item => item.id === choiceId) || null, [wallets, choiceId]);
  useEffect(() => {
    if (!provider) return;
    const changed = async () => {
      setQuote(null); setVerifiedAddress(null);
      try {
        const [accounts, chain] = await Promise.all([walletAccounts(provider), walletChainId(provider)]);
        if (activeProvider.current !== provider) return;
        setAddress(accounts[0] && isAddress(accounts[0]) ? getAddress(accounts[0]) : null);
        setWalletChain(chain);
      } catch (error) {
        if (activeProvider.current !== provider) return;
        setAddress(null); setWalletChain(null); setNotice(friendlyWalletError(error));
      }
    };
    const disconnected = () => {
      activeProvider.current = null; setProvider(null); setAddress(null);
      setWalletChain(null); setQuote(null); setVerifiedAddress(null);
    };
    provider.on?.("accountsChanged", changed);
    provider.on?.("chainChanged", changed);
    provider.on?.("disconnect", disconnected);
    return () => {
      provider.removeListener?.("accountsChanged", changed);
      provider.removeListener?.("chainChanged", changed);
      provider.removeListener?.("disconnect", disconnected);
    };
  }, [provider]);
  async function connect() {
    if (!selected) return;
    setBusy(true); setNotice("");
    try {
      const accounts = await selected.provider.request({ method: "eth_requestAccounts" });
      if (!Array.isArray(accounts) || !isAddress(accounts[0])) throw new Error("钱包未返回有效地址");
      if (getAddress(accounts[0]) !== authorizedDeployer)
        throw new Error("这不是获授权的部署钱包，请在 MetaMask 中选择指定账户");
      activeProvider.current = selected.provider;
      setProvider(selected.provider); setAddress(getAddress(accounts[0]));
      setWalletChain(await walletChainId(selected.provider)); setQuote(null);
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  function disconnect() {
    activeProvider.current = null; setProvider(null); setAddress(null);
    setWalletChain(null); setQuote(null); setNotice("已在本页面断开。");
  }
  async function switchNetwork() {
    if (!provider) return;
    setBusy(true); setNotice(""); setQuote(null);
    try { await switchToBot(provider); setWalletChain(await walletChainId(provider)); }
    catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function makeQuote(account: Address, active: Provider): Promise<Quote> {
    const [accounts, network, rpcNetwork, artifact] = await Promise.all([
      walletAccounts(active), walletChainId(active), publicClient.getChainId(), reviewedArtifact()
    ]);
    if (activeProvider.current !== active || accounts[0]?.toLowerCase() !== account.toLowerCase() ||
        account !== authorizedDeployer || network !== 677 || rpcNetwork !== 677)
      throw new Error("钱包账户或链与 BOT Chain 677 不一致");
    const [balance, nonce, latestNonce, gasEstimate, gasPrice] = await Promise.all([
      publicClient.getBalance({ address: account }),
      publicClient.getTransactionCount({ address: account, blockTag: "pending" }),
      publicClient.getTransactionCount({ address: account, blockTag: "latest" }),
      publicClient.estimateGas({ account, data: artifact.bytecode }),
      publicClient.getGasPrice()
    ]);
    const gasLimit = (gasEstimate * 120n + 99n) / 100n;
    const maxCost = gasLimit * gasPrice;
    if (balance < maxCost) throw new Error("BOT 余额低于按当前报价计算的最高 Gas 预算");
    return { address: account, artifact, nonce, latestNonce, balance, gasEstimate, gasLimit,
      gasPrice, maxCost, predicted: getContractAddress({ from: account, nonce: BigInt(nonce) }),
      quotedAt: new Date().toISOString() };
  }
  async function preview() {
    if (!address || !provider) return;
    setBusy(true); setQuote(null); setNotice("");
    try { setQuote(await makeQuote(address, provider)); }
    catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function verifyReceipt(hash: Hex, expected: DeploymentAttempt) {
    const [network, receipt, transaction] = await Promise.all([
      publicClient.getChainId(), publicClient.getTransactionReceipt({ hash }),
      publicClient.getTransaction({ hash })
    ]);
    if (network !== 677 || receipt.status !== "success" || !receipt.contractAddress ||
        receipt.contractAddress.toLowerCase() !== expected.predicted.toLowerCase() ||
        transaction.from.toLowerCase() !== authorizedDeployer.toLowerCase() ||
        transaction.to !== null || transaction.nonce !== expected.nonce ||
        await sha256(hexToBytes(transaction.input)) !== creationSha256)
      throw new Error("主网链、交易来源、创建代码或部署回执不符合审阅值");
    const [code, block] = await Promise.all([
      publicClient.getCode({ address: receipt.contractAddress }),
      publicClient.getBlock({ blockNumber: receipt.blockNumber })
    ]);
    if (!code || await sha256(hexToBytes(code)) !== runtimeSha256 ||
        block.hash !== receipt.blockHash)
      throw new Error("链上运行时代码或区块 Hash 与预期不符");
    setVerifiedAddress(receipt.contractAddress);
    setNotice(`部署已核对：区块 ${receipt.blockNumber}，Gas ${receipt.gasUsed}，实际费用 ${formatEther(receipt.gasUsed * receipt.effectiveGasPrice)} BOT。请停止，等待 anchorTask 的独立授权。`);
  }
  async function recheckAttempt() {
    if (!attempt) return;
    setBusy(true); setNotice("");
    try {
      if (attempt.hash) await verifyReceipt(attempt.hash, attempt);
      else {
        const [latest, pending, code] = await Promise.all([
          publicClient.getTransactionCount({ address: authorizedDeployer, blockTag: "latest" }),
          publicClient.getTransactionCount({ address: authorizedDeployer, blockTag: "pending" }),
          publicClient.getCode({ address: attempt.predicted })
        ]);
        setNotice(`钱包请求的交易 Hash 未返回。只读检查：latest/pending nonce ${latest}/${pending}，预计地址代码 ${code && code !== "0x" ? "非空" : "空"}。状态仍不明；请在 MetaMask 活动记录中查找，禁止再次发送。`);
      }
    } catch (error) { setNotice("只读核验尚无成功结论：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function deploy() {
    if (!deploymentEnabled || !quote || !provider || !address || tx || attemptLocked) return;
    setBusy(true); setNotice("");
    let requestedWallet = false;
    try {
      const fresh = await makeQuote(address, provider);
      if (fresh.nonce !== fresh.latestNonce || fresh.nonce !== quote.nonce ||
          fresh.predicted !== quote.predicted ||
          fresh.gasPrice !== quote.gasPrice || fresh.gasEstimate > quote.gasLimit ||
          Date.now() - Date.parse(quote.quotedAt) > 120_000)
        throw new Error("nonce、Gas 报价或预览时效已变化，请重新运行只读预览");
      if (fresh.maxCost > reviewCeiling || quote.maxCost > reviewCeiling)
        throw new Error("最新最高 Gas 预算比上次审阅值高出 10% 以上，请停止并重新确认费用");
      const predictedCode = await publicClient.getCode({ address: quote.predicted });
      if (predictedCode && predictedCode !== "0x")
        throw new Error("预计合约地址已有代码，请重新检查 nonce");
      const wallet = createWalletClient({ account: address, chain: botChain, transport: custom(provider) });
      if (activeProvider.current !== provider) throw new Error("钱包连接已变化");
      if (window.localStorage.getItem(attemptStorageKey))
        throw new Error("已有一次部署请求记录，禁止重复发送");
      const pendingAttempt: DeploymentAttempt = { address, nonce: quote.nonce,
        predicted: quote.predicted, creationSha256, startedAt: new Date().toISOString() };
      // Persist before the wallet request. A rejection, timeout, or refresh never unlocks a retry.
      window.localStorage.setItem(attemptStorageKey, JSON.stringify(pendingAttempt));
      setAttempt(pendingAttempt); setAttemptLocked(true);
      requestedWallet = true;
      const hash = await wallet.deployContract({ abi: quote.artifact.abi as Abi,
        bytecode: quote.artifact.bytecode, gas: quote.gasLimit, gasPrice: quote.gasPrice });
      setTx(hash);
      const broadcastAttempt = { ...pendingAttempt, hash };
      window.localStorage.setItem(attemptStorageKey, JSON.stringify(broadcastAttempt));
      setAttempt(broadcastAttempt);
      await publicClient.waitForTransactionReceipt({ hash, confirmations: 2 });
      await verifyReceipt(hash, broadcastAttempt);
    } catch (error) {
      setNotice((requestedWallet ? "部署请求已发起，状态未知或核验失败，勿再次发送：" : "部署未发起：") + friendlyWalletError(error));
    }
    finally { setBusy(false); }
  }
  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span><span>TreasuryTally <small>DEPLOYMENT REVIEW</small></span></div><a href="/">返回 Demo</a></header>
    <section className="hero"><div className="eyebrow">BOT CHAIN · MAINNET 677</div><h1>合约部署预览</h1>
      <p>连接与切网需要你主动点击。运行预览仅查询 RPC 和估算 Gas。获授权的部署最多发起一次，钱包确认须由你亲自操作。</p></section>
    <section className="panel"><h2>部署钱包</h2>
      {wallets.length ? <label>选择钱包<select value={choiceId} disabled={busy || !!address} onChange={event => setChoiceId(event.target.value)}>
        <option value="">请选择钱包</option>{wallets.map(item => <option key={item.id} value={item.id}>{item.name} · {item.source}{item.rdns ? ` · ${item.rdns}` : ""}</option>)}</select></label>
        : <div className="empty">未检测到 EVM 钱包。钱包名称由扩展自报，请核对弹窗。</div>}
      <div className="actions">{!address ? <button disabled={!selected || busy} onClick={connect}>Connect Wallet</button>
        : <button className="secondary" onClick={disconnect}>断开页面连接</button>}
        {address && walletChain !== 677 && <button onClick={switchNetwork} disabled={busy}>切换到 BOT Chain</button>}
        <button className="secondary" onClick={preview} disabled={!address || walletChain !== 677 || busy}>运行只读部署预览</button></div>
      <dl className="facts"><div><dt>获授权部署钱包</dt><dd>{authorizedDeployer}</dd></div>
        <div><dt>当前连接地址</dt><dd>{address || "未连接"}</dd></div>
        <div><dt>钱包 Chain ID</dt><dd>{walletChain ?? "—"}</dd></div></dl></section>
    <section className="panel"><h2>审阅值</h2>
      <dl className="facts"><div><dt>合约 / 构造参数</dt><dd>CommitmentAnchor.sol / 无</dd></div>
        <div><dt>编译器 / 优化 / EVM</dt><dd>0.8.30+commit.73712a01 / enabled, runs 200 / paris</dd></div>
        <div><dt>创建代码 SHA-256</dt><dd>{creationSha256}</dd></div>
        <div><dt>运行时代码 SHA-256</dt><dd>{runtimeSha256}</dd></div>
        <div><dt>Gas 估算 / 上限</dt><dd>{quote ? `${quote.gasEstimate} / ${quote.gasLimit}` : "尚未针对钱包估算"}</dd></div>
        <div><dt>Gas 报价</dt><dd>{quote ? `${quote.gasPrice} wei` : "—"}</dd></div>
        <div><dt>最高 Gas 预算</dt><dd>{quote ? `${formatEther(quote.maxCost)} BOT` : "—"}</dd></div>
        <div><dt>余额</dt><dd>{quote ? `${formatEther(quote.balance)} BOT` : "—"}</dd></div>
        <div><dt>nonce latest / pending</dt><dd>{quote ? `${quote.latestNonce} / ${quote.nonce}` : "—"}</dd></div>
        <div><dt>预计合约地址</dt><dd>{quote?.predicted || "—"}</dd></div>
        <div><dt>预览时间 UTC</dt><dd>{quote?.quotedAt || "—"}</dd></div></dl>
      <p className="muted">以上是只读估计，不保证钱包最终费用或交易成功。部署只创建任务承诺合约，不核验任何报表。本次部署已获用户单独授权；钱包弹窗仍需本人核对并确认。若最高预算超过上次审阅值 10%，页面会阻止发送。</p>
      <button disabled={!deploymentEnabled || !quote || quote.latestNonce !== quote.nonce || quote.maxCost > reviewCeiling || attemptLocked || busy} onClick={deploy}>部署 CommitmentAnchor（仅一次）</button>
      {!deploymentEnabled && <p className="hint">本地开发部署开关未启用，当前不会请求交易签名或发送交易。</p>}
      {attemptLocked && attempt && <div className="warning">已经发起过一次钱包部署请求；即使拒绝、超时或刷新，也不会自动解锁或重发。{attempt.hash ? "可按交易 Hash 只读核验。" : "未收到交易 Hash，请检查 MetaMask 活动记录。"}</div>}
      {attempt && <button className="secondary" disabled={busy} onClick={recheckAttempt}>只读复查部署状态</button>}
      {tx && <p>部署交易：<a href={`https://scan.botchain.ai/tx/${tx}`} target="_blank" rel="noreferrer">{tx} ↗</a></p>}
      {verifiedAddress && <p>已核对合约：<a href={`https://scan.botchain.ai/address/${verifiedAddress}`} target="_blank" rel="noreferrer">{verifiedAddress} ↗</a></p>}
    </section>
    {notice && <div className="notice" role="status">{notice}</div>}
    <footer><span>单次部署授权 · 不包含任何业务写入</span><a href="/preflight">无需钱包的 RPC 预检 ↗</a></footer>
  </main>;
}
