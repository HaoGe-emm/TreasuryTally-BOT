"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  custom, decodeEventLog, decodeFunctionData, formatEther, getAddress, hexToBytes, isAddress, type Address, type Hex
} from "viem";
import { createWalletClient } from "viem";
import { anchorAbi, anchorAddress, anchorRuntimeHash, publicClient } from "@/lib/anchor";
import { botChain } from "@/lib/chain";
import { confirmedDemo, matchesConfirmedDemoBinding, requireConfirmedDemoBinding } from "@/lib/demo";
import { historicalObservation, recoverHistoricalDigest, requireHistoricalObservation } from "@/lib/historical";
import signingPreview from "@/public/bot677-demo/task-commitment-preview.json";
import { collectWallets, friendlyWalletError, switchToBot, walletAccounts, walletChainId,
  type Provider, type WalletChoice } from "@/lib/wallet";
import { parseTaskSpec, requireBotContext, sha256, taskDigest, taskDomain, taskTypes, utcTimestamp,
  typedDataDigest, verifySignature, verifySpec, type TaskCommitmentMessage, type TaskSpec } from "@/lib/task";

const samplePath = "/demo-task-spec.json";
const confirmedDemoPath = "/bot677-demo/task-spec.json";
type Preview = { task: TaskSpec; hash: Hex; label: string };
type Signed = { message: TaskCommitmentMessage; signature: Hex; digest: Hex; serviceIdHash: Hex; serviceSigner: Address };
type Prepared = Omit<Signed, "signature" | "digest">;
type AnchorQuote = { digest: Hex; gas: bigint; gasLimit: bigint; gasPrice: bigint;
  maxFee: bigint; balance: bigint; nonce: number; createdAt: number };
type AnchorRecord = { digest: Hex; hash: Hex; block: string; fee: string };
const intentKey = "treasurytally-bot677-demo-anchor-intent-v1";
const signatureAttemptKey = `treasurytally:task-sign-requested:${confirmedDemo.typedDataDigest}`;
const zeroAddress = "0x0000000000000000000000000000000000000000";
const reviewedMessage: TaskCommitmentMessage = {
  ...signingPreview.message,
  specHash: signingPreview.message.specHash as Hex,
  requester: signingPreview.message.requester as Address
};
const reviewedTypedData = {
  domain: signingPreview.domain,
  types: signingPreview.types,
  primaryType: signingPreview.primaryType,
  message: signingPreview.message
};
function requireReviewedSigningPreview(): void {
  if (signingPreview.status !== "UNSIGNED_PREVIEW" || !signingPreview.demo_data ||
      signingPreview.domain.name !== taskDomain.name ||
      signingPreview.domain.version !== taskDomain.version ||
      signingPreview.domain.chainId !== taskDomain.chainId ||
      Object.keys(signingPreview.domain).length !== 3 ||
      signingPreview.primaryType !== "TaskCommitment" ||
      JSON.stringify(signingPreview.types.TaskCommitment) !== JSON.stringify(taskTypes.TaskCommitment) ||
      signingPreview.task_spec_hash !== confirmedDemo.specHash ||
      reviewedMessage.taskId !== confirmedDemo.taskId ||
      reviewedMessage.specHash !== confirmedDemo.specHash ||
      reviewedMessage.requester !== confirmedDemo.requester ||
      reviewedMessage.serviceId !== confirmedDemo.serviceId ||
      signingPreview.service_signer !== confirmedDemo.serviceSigner ||
      signingPreview.typed_data_digest !== confirmedDemo.typedDataDigest ||
      typedDataDigest(reviewedMessage) !== confirmedDemo.typedDataDigest ||
      utcTimestamp(reviewedMessage.createdAt, true) !== reviewedMessage.createdAt ||
      reviewedMessage.expiresAt !== "")
    throw new Error("签名前消息与已审核的 BOT Demo EIP-712 预览不一致");
}

async function requireLiveBotContract(): Promise<void> {
  if (!anchorAddress || !anchorRuntimeHash)
    throw new Error("缺少经过审阅的主网合约地址或字节码哈希");
  const rpcChain = await publicClient.getChainId();
  if (rpcChain !== 677) throw new Error(`BOT RPC 返回 Chain ID ${rpcChain}，预期 677`);
  const code = await publicClient.getCode({ address: anchorAddress });
  if (!code || code === "0x") throw new Error("目标地址没有合约字节码");
  const actual = await sha256(hexToBytes(code));
  if (actual.toLowerCase() !== anchorRuntimeHash.toLowerCase())
    throw new Error("目标合约运行时代码 SHA-256 与已部署版本不一致");
}

async function verifySignatureWithPython(
  signature: Hex, message: TaskCommitmentMessage, specHash: Hex,
  serviceIdHash: Hex, serviceSigner: Address
): Promise<Hex> {
  if (!(await verifySignature(message, signature)))
    throw new Error("TypeScript 无法将钱包签名恢复到 Requester");
  const digest = await taskDigest(message, signature);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetch("/api/verify-signed-demo", { method: "POST",
      headers: { "content-type": "application/json" }, body: JSON.stringify({ signature }),
      signal: controller.signal, cache: "no-store" });
    const result = await response.json().catch(() => ({})) as Record<string, unknown>;
    if (!response.ok) {
      const reason = typeof result.error === "string" ? result.error : "本地校验接口返回非成功状态。";
      if (response.status === 403)
        throw new Error(`HTTP 403：签名未送入 Python；${reason}`);
      if (response.status === 422)
        throw new Error(`HTTP 422：Python 已运行但拒绝签名；${reason}`);
      throw new Error(`本地签名校验接口 HTTP ${response.status}：${reason}`);
    }
    const check = result as { requester?: string; taskDigest?: string; specHash?: string;
      serviceIdHash?: string; serviceSigner?: string; typedDataDigest?: string; scope?: string };
    if (check.scope !== "LOCAL_PYTHON_SIGNATURE_CHECK_ONLY" ||
        check.requester?.toLowerCase() !== message.requester.toLowerCase() ||
        check.taskDigest !== digest || check.specHash !== specHash ||
        check.serviceIdHash !== serviceIdHash ||
        check.serviceSigner?.toLowerCase() !== serviceSigner.toLowerCase() ||
        check.typedDataDigest !== confirmedDemo.typedDataDigest)
      throw new Error("Python 与 TypeScript 的签名者、任务摘要或绑定字段不一致");
    return digest;
  } finally { clearTimeout(timer); }
}

export default function Home() {
  const [wallets, setWallets] = useState<WalletChoice[]>([]);
  const [choiceId, setChoiceId] = useState("");
  const [provider, setProvider] = useState<Provider | null>(null);
  const activeProvider = useRef<Provider | null>(null);
  const refreshVersion = useRef(0);
  const [address, setAddress] = useState<Address | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [rpcChainId, setRpcChainId] = useState<number | null>(null);
  const [rpcError, setRpcError] = useState("");
  const [preview, setPreview] = useState<Preview | null>(null);
  const [serviceId, setServiceId] = useState("");
  const [serviceSigner, setServiceSigner] = useState("");
  const [signed, setSigned] = useState<Signed | null>(null);
  const [historicalDigest, setHistoricalDigest] = useState<Hex | null>(null);
  const [historicalAcknowledged, setHistoricalAcknowledged] = useState(false);
  const pendingSignature = useRef<Hex | null>(null);
  const [pendingSignatureAvailable, setPendingSignatureAvailable] = useState(false);
  const [taskSignaturesEnabled, setTaskSignaturesEnabled] = useState(false);
  const [mainnetWritesEnabled, setMainnetWritesEnabled] = useState(false);
  const [signRequestAttempted, setSignRequestAttempted] = useState(false);
  const [prepared, setPrepared] = useState<Prepared | null>(null);
  const [contractStatus, setContractStatus] = useState("尚未部署");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [tx, setTx] = useState<Hex | null>(null);
  const [anchorQuote, setAnchorQuote] = useState<AnchorQuote | null>(null);
  const [anchorRecord, setAnchorRecord] = useState<AnchorRecord | null>(null);
  const [anchorIntent, setAnchorIntent] = useState<{ digest: Hex; hash?: Hex } | null>(null);
  const activeDigest = signed?.digest ?? historicalDigest;

  useEffect(() => collectWallets(setWallets), []);
  const refreshWriteApproval = useCallback(async () => {
    try {
      const response = await fetch("/api/mainnet-write-status", { cache: "no-store" });
      const status = await response.json();
      setMainnetWritesEnabled(response.ok && status.enabled === true);
    } catch { setMainnetWritesEnabled(false); }
  }, []);
  useEffect(() => { void refreshWriteApproval(); }, [refreshWriteApproval]);
  useEffect(() => {
    let active = true;
    void fetch("/api/verify-signed-demo", { cache: "no-store" })
      .then(response => response.json())
      .then(result => { if (active) setTaskSignaturesEnabled(result.signatureRequestEnabled === true); })
      .catch(() => { if (active) setTaskSignaturesEnabled(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => {
    try { setSignRequestAttempted(sessionStorage.getItem(signatureAttemptKey) === "true"); }
    catch { setSignRequestAttempted(false); }
  }, []);
  const refreshRpc = useCallback(async () => {
    setRpcError("");
    try { setRpcChainId(await publicClient.getChainId()); }
    catch (error) {
      setRpcChainId(null);
      setRpcError("BOT RPC 连接失败或超时：" + friendlyWalletError(error));
    }
  }, []);
  useEffect(() => { void refreshRpc(); }, [refreshRpc]);
  // An injected provider never becomes the default signing choice.
  const selected = useMemo(() => wallets.find(x => x.id === choiceId) || null, [wallets, choiceId]);
  useEffect(() => {
    setPrepared(null); setSigned(null); setHistoricalDigest(null); setHistoricalAcknowledged(false); setAnchorQuote(null);
    pendingSignature.current = null; setPendingSignatureAvailable(false);
  }, [address, chainId, preview, serviceId, serviceSigner]);
  useEffect(() => {
    try {
      const raw = localStorage.getItem(intentKey);
      if (!raw) return;
      const saved = JSON.parse(raw) as { digest?: string; hash?: string };
      if (!/^0x[0-9a-fA-F]{64}$/.test(saved.digest || "") ||
          (saved.hash && !/^0x[0-9a-fA-F]{64}$/.test(saved.hash))) return;
      setAnchorIntent({ digest: saved.digest as Hex, hash: saved.hash as Hex | undefined });
      if (saved.hash) setTx(saved.hash as Hex);
    } catch { /* A malformed local display hint never counts as chain evidence. */ }
  }, []);

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
  const refreshContract = useCallback(async () => {
    if (!anchorAddress || !anchorRuntimeHash) {
      setContractStatus("尚未部署：未配置经过审阅的主网地址与字节码哈希");
      return;
    }
    setContractStatus("正在通过 BOT RPC 核对合约");
    try {
      await requireLiveBotContract();
      setRpcChainId(677);
      setRpcError("");
      setContractStatus("已通过 RPC 字节码核对");
    } catch (error) {
      setContractStatus("合约只读核验失败：" + friendlyWalletError(error));
    }
  }, []);
  useEffect(() => { void refreshContract(); }, [refreshContract]);

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
    setBusy(true); setNotice(""); setSigned(null); setHistoricalDigest(null); setAnchorQuote(null);
    try {
      if (contractStatus !== "已通过 RPC 字节码核对")
        throw new Error("部署合约尚未通过 BOT RPC 运行时代码核验");
      requireBotContext(preview.task, address, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      requireConfirmedDemoBinding(preview.task, address, serviceId, serviceSigner);
      requireReviewedSigningPreview();
      if (!isAddress(serviceSigner) || !serviceId.trim() || serviceId.length > 200)
        throw new Error("请输入有效服务 ID 和服务签名者地址");
      const message = reviewedMessage;
      const serviceIdHash = await sha256(new TextEncoder().encode(message.serviceId));
      if (serviceIdHash !== signingPreview.service_id_hash ||
          serviceSigner.toLowerCase() !== signingPreview.service_signer.toLowerCase())
        throw new Error("服务 ID 或签名者与审阅文件不一致");
      setPrepared({ message, serviceIdHash, serviceSigner: getAddress(serviceSigner) });
      setNotice("已准备任务承诺，请核对完整内容和服务签名者后再签署。");
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function restoreHistoricalDigest() {
    if (!provider || !address || !preview) return;
    setBusy(true); setNotice(""); setAnchorQuote(null);
    try {
      requireReviewedSigningPreview();
      const [accounts, walletNetwork] = await Promise.all([
        walletAccounts(provider), walletChainId(provider)
      ]);
      const digest = await recoverHistoricalDigest({ task: preview.task, specHash: preview.hash,
        address, walletAccounts: accounts, walletChainId: walletNetwork,
        serviceId, serviceSigner });
      setSigned(null);
      setHistoricalDigest(digest);
      setNotice("历史摘要已从固定本地记录载入；本次未重新验签。请继续运行主网只读模拟，核验 RPC、合约和登记状态。");
    } catch (error) {
      setHistoricalDigest(null);
      setNotice("历史摘要载入失败：" + friendlyWalletError(error));
    }
    finally { setBusy(false); }
  }
  async function signTask() {
    if (!taskSignaturesEnabled || !provider || !address || !preview || !prepared) return;
    setBusy(true); setNotice(""); setSigned(null); setHistoricalDigest(null);
    setHistoricalAcknowledged(false); setAnchorQuote(null);
    try {
      if (contractStatus !== "已通过 RPC 字节码核对")
        throw new Error("部署合约尚未通过 BOT RPC 运行时代码核验");
      requireReviewedSigningPreview();
      requireBotContext(preview.task, prepared.message.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      requireConfirmedDemoBinding(preview.task, prepared.message.requester, serviceId, serviceSigner);
      if (prepared.serviceSigner.toLowerCase() !== serviceSigner.toLowerCase() ||
          prepared.message.serviceId !== serviceId.trim() ||
          typedDataDigest(prepared.message) !== confirmedDemo.typedDataDigest)
        throw new Error("服务选择已变化，请重新准备承诺");
      const message = prepared.message;
      const wallet = createWalletClient({ account: address, chain: botChain, transport: custom(provider) });
      // This fixed Demo only allows one wallet prompt per browser tab. The marker
      // stores no signature and remains set even if the user rejects the prompt.
      sessionStorage.setItem(signatureAttemptKey, "true");
      setSignRequestAttempted(true);
      const signature = await wallet.signTypedData({
        domain: taskDomain, types: taskTypes, primaryType: "TaskCommitment", message
      });
      pendingSignature.current = signature;
      setPendingSignatureAvailable(true);
      if (activeProvider.current !== provider) throw new Error("钱包连接已变化，已丢弃过期签名结果");
      requireBotContext(preview.task, message.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      const digest = await verifySignatureWithPython(signature, message, preview.hash,
        prepared.serviceIdHash, prepared.serviceSigner);
      if (!anchorAddress) throw new Error("未配置经过核验的主网合约地址");
      const existing = await publicClient.readContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "tasks", args: [message.requester, digest] });
      if (existing[0] !== zeroAddress) throw new Error("该请求者的任务摘要已经登记，停止重复提交");
      setSigned({ ...prepared, signature, digest });
      setHistoricalDigest(null);
      pendingSignature.current = null;
      setPendingSignatureAvailable(false);
      setNotice("EIP-712 签名已由 TypeScript 和本机原 Python 模型交叉验证；尚未发送链上交易。");
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function retryPythonVerification() {
    const signature = pendingSignature.current;
    if (!signature || !provider || !address || !preview || !prepared) return;
    setBusy(true); setNotice("");
    try {
      requireBotContext(preview.task, prepared.message.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      const digest = await verifySignatureWithPython(signature, prepared.message, preview.hash,
        prepared.serviceIdHash, prepared.serviceSigner);
      if (!anchorAddress) throw new Error("未配置经过核验的主网合约地址");
      const existing = await publicClient.readContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "tasks", args: [prepared.message.requester, digest] });
      if (existing[0] !== zeroAddress) throw new Error("该请求者的任务摘要已经登记，停止重复提交");
      setSigned({ ...prepared, signature, digest });
      setHistoricalDigest(null); setHistoricalAcknowledged(false); setAnchorQuote(null);
      pendingSignature.current = null;
      setPendingSignatureAvailable(false);
      setNotice("原内存签名已通过 TypeScript 与原 Python 模型交叉验证；尚未发送链上交易。");
    } catch (error) { setNotice(friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function prepareAnchorQuote() {
    if (!provider || !address || !activeDigest || !preview || !anchorAddress || !anchorRuntimeHash) return;
    setBusy(true); setNotice(""); setAnchorQuote(null);
    let check = "BOT RPC Chain ID 与合约字节码";
    try {
      if (anchorIntent) throw new Error("已有本机提交记录；请先读回回执，禁止重复发送");
      await requireLiveBotContract();
      setRpcChainId(677);
      setRpcError("");
      setContractStatus("已通过 RPC 字节码核对");
      check = "钱包账户、网络与固定任务";
      requireReviewedSigningPreview();
      requireBotContext(preview.task, confirmedDemo.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      requireConfirmedDemoBinding(preview.task, address, serviceId, serviceSigner);
      if (signed) {
        if (!(await verifySignature(signed.message, signed.signature)) ||
            await taskDigest(signed.message, signed.signature) !== signed.digest ||
            signed.serviceIdHash !== signingPreview.service_id_hash ||
            signed.serviceSigner.toLowerCase() !== confirmedDemo.serviceSigner.toLowerCase())
          throw new Error("请求者签名或 Demo 参数已变化");
      } else if (activeDigest !== requireHistoricalObservation()) {
        throw new Error("既往摘要与固定观察记录不一致");
      }
      const serviceHash = await sha256(new TextEncoder().encode(serviceId));
      if (preview.hash !== confirmedDemo.specHash || serviceHash !== signingPreview.service_id_hash)
        throw new Error("TaskSpec 或服务哈希已变化");
      check = "合约重复登记读回";
      const existing = await publicClient.readContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "tasks", args: [address, activeDigest] });
      if (existing[0] !== zeroAddress) throw new Error("该请求者的任务摘要已登记");
      check = "anchorTask eth_call 模拟";
      const args = [activeDigest, preview.hash, serviceHash, getAddress(serviceSigner)] as const;
      await publicClient.simulateContract({ address: anchorAddress, abi: anchorAbi,
        functionName: "anchorTask", args, account: address });
      check = "Gas、余额与账户 nonce 只读报价";
      const [gas, gasPrice, balance, latest, pending] = await Promise.all([
        publicClient.estimateContractGas({ address: anchorAddress, abi: anchorAbi,
          functionName: "anchorTask", args, account: address }),
        publicClient.getGasPrice(), publicClient.getBalance({ address }),
        publicClient.getTransactionCount({ address, blockTag: "latest" }),
        publicClient.getTransactionCount({ address, blockTag: "pending" })
      ]);
      if (latest !== pending) throw new Error("请求者账户存在待处理交易，暂不准备登记");
      const gasLimit = gas * 12n / 10n;
      const maxFee = gasLimit * gasPrice;
      if (balance < maxFee) throw new Error("BOT 余额不足以覆盖预计最高 Gas 费用");
      setAnchorQuote({ digest: activeDigest, gas, gasLimit, gasPrice, maxFee,
        balance, nonce: pending, createdAt: Date.now() });
      setNotice("只读模拟和 Gas 估算通过；这不是签名或主网交易批准。");
    } catch (error) { setNotice(`只读预览失败（${check}）：${friendlyWalletError(error)}`); }
    finally { setBusy(false); }
  }
  async function readAnchorReceipt(hash: Hex, digest: Hex) {
    if (!anchorAddress || !anchorRuntimeHash) throw new Error("缺少经过核验的合约配置");
    if (digest !== anchorIntent?.digest && digest !== activeDigest)
      throw new Error("待查摘要不属于当前 Demo 提交记录");
    const [receipt, transaction, currentCode, currentChain] = await Promise.all([
      publicClient.getTransactionReceipt({ hash }), publicClient.getTransaction({ hash }),
      publicClient.getCode({ address: anchorAddress }), publicClient.getChainId()
    ]);
    if (receipt.status !== "success" || currentChain !== 677 || !currentCode || currentCode === "0x" ||
        (await sha256(hexToBytes(currentCode))).toLowerCase() !== anchorRuntimeHash.toLowerCase() ||
        receipt.transactionHash !== hash || transaction.from.toLowerCase() !== confirmedDemo.requester.toLowerCase() ||
        transaction.to?.toLowerCase() !== anchorAddress.toLowerCase())
      throw new Error("回执状态、网络、字节码或交易来源不匹配");
    const submittedCall = decodeFunctionData({ abi: anchorAbi, data: transaction.input });
    if (submittedCall.functionName !== "anchorTask" ||
        submittedCall.args[0].toLowerCase() !== digest.toLowerCase() ||
        submittedCall.args[1].toLowerCase() !== confirmedDemo.specHash.toLowerCase() ||
        submittedCall.args[2].toLowerCase() !== signingPreview.service_id_hash.toLowerCase() ||
        submittedCall.args[3].toLowerCase() !== confirmedDemo.serviceSigner.toLowerCase())
      throw new Error("部署合约交易输入与固定 Demo 参数不一致");
    const events = receipt.logs.filter(log => log.address.toLowerCase() === anchorAddress!.toLowerCase())
      .map(log => { try { return decodeEventLog({ abi: anchorAbi, data: log.data, topics: log.topics }); }
                    catch { return null; } })
      .filter(log => log?.eventName === "TaskAnchored");
    const event = events[0];
    if (events.length !== 1 || !event || event.eventName !== "TaskAnchored" ||
        event.args.taskDigest.toLowerCase() !== digest.toLowerCase() ||
        event.args.requester.toLowerCase() !== confirmedDemo.requester.toLowerCase() ||
        event.args.serviceSigner.toLowerCase() !== confirmedDemo.serviceSigner.toLowerCase() ||
        event.args.specHash.toLowerCase() !== confirmedDemo.specHash.toLowerCase() ||
        event.args.serviceIdHash.toLowerCase() !== signingPreview.service_id_hash.toLowerCase())
      throw new Error("TaskAnchored 事件与固定 Demo 参数不匹配");
    const stored = await publicClient.readContract({ address: anchorAddress, abi: anchorAbi,
      functionName: "tasks", args: [confirmedDemo.requester, digest] });
    if (stored[0].toLowerCase() !== confirmedDemo.requester.toLowerCase() ||
        stored[1].toLowerCase() !== confirmedDemo.serviceSigner.toLowerCase())
      throw new Error("合约 tasks 存储与事件不匹配");
    const record = { digest, hash, block: receipt.blockNumber.toString(),
      fee: (receipt.gasUsed * receipt.effectiveGasPrice).toString() };
    setAnchorRecord(record);
    setNotice("BOT 677 成功回执、TaskAnchored 事件和 tasks 存储已交叉核验。");
  }
  async function refreshAnchorReceipt() {
    if (!anchorIntent?.hash) return;
    setBusy(true); setNotice("");
    try { await readAnchorReceipt(anchorIntent.hash, anchorIntent.digest); }
    catch (error) { setNotice("回执尚未完成核验：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  async function anchorTask() {
    const contractAddress = anchorAddress;
    if (!mainnetWritesEnabled || !contractAddress || !anchorRuntimeHash ||
        contractStatus !== "已通过 RPC 字节码核对" ||
        !provider || !address || !activeDigest || !preview || !anchorQuote || anchorIntent ||
        (!signed && !historicalAcknowledged)) return;
    setBusy(true); setNotice("");
    try {
      const gate = await fetch("/api/mainnet-write-status", { cache: "no-store" });
      const approval = await gate.json();
      if (!gate.ok || approval.enabled !== true)
        throw new Error("本地主网写入开关未开放，停止发送");
      if (Date.now() - anchorQuote.createdAt > 60_000 || anchorQuote.digest !== activeDigest)
        throw new Error("交易预览已过期，请重新运行只读模拟");
      requireReviewedSigningPreview();
      requireBotContext(preview.task, confirmedDemo.requester, (await walletAccounts(provider))[0],
        await walletChainId(provider), await publicClient.getChainId());
      requireConfirmedDemoBinding(preview.task, address, serviceId, serviceSigner);
      if (signed) {
        if (signed.message.requester.toLowerCase() !== address.toLowerCase() ||
            serviceSigner.toLowerCase() !== signed.serviceSigner.toLowerCase() ||
            !(await verifySignature(signed.message, signed.signature)) ||
            await taskDigest(signed.message, signed.signature) !== signed.digest)
          throw new Error("链、请求者或签名已变化，请重新准备承诺");
      } else if (activeDigest !== requireHistoricalObservation() || !historicalAcknowledged) {
        throw new Error("既往观察记录尚未由用户核对");
      }
      const serviceHash = await sha256(new TextEncoder().encode(serviceId));
      if (preview.hash !== confirmedDemo.specHash || serviceHash !== signingPreview.service_id_hash)
        throw new Error("TaskSpec 或服务哈希已变化");
      const existing = await publicClient.readContract({
        address: contractAddress, abi: anchorAbi, functionName: "tasks",
        args: [address, activeDigest]
      });
      if (existing[0] !== zeroAddress)
        throw new Error("该请求者已登记相同任务摘要");
      const pending = await publicClient.getTransactionCount({ address, blockTag: "pending" });
      if (pending !== anchorQuote.nonce) throw new Error("账户 nonce 已变化，请重新预览");
      const args = [activeDigest, preview.hash, serviceHash, getAddress(serviceSigner)] as const;
      await publicClient.simulateContract({ address: contractAddress, abi: anchorAbi,
        functionName: "anchorTask", args, account: address });
      const [gas, gasPrice, balance] = await Promise.all([
        publicClient.estimateContractGas({ address: contractAddress, abi: anchorAbi,
          functionName: "anchorTask", args, account: address }),
        publicClient.getGasPrice(), publicClient.getBalance({ address })
      ]);
      if (gas > anchorQuote.gasLimit || gasPrice !== anchorQuote.gasPrice ||
          balance < anchorQuote.maxFee)
        throw new Error("Gas、报价或余额已变化，请重新运行只读预览");
      const wallet = createWalletClient({ account: address, chain: botChain, transport: custom(provider) });
      if (activeProvider.current !== provider) throw new Error("钱包连接已变化，请重新准备承诺");
      const intent = { digest: activeDigest };
      localStorage.setItem(intentKey, JSON.stringify(intent));
      setAnchorIntent(intent);
      const hash = await wallet.writeContract({
        address: contractAddress, abi: anchorAbi, functionName: "anchorTask",
        args, gas: anchorQuote.gasLimit, gasPrice: anchorQuote.gasPrice, nonce: anchorQuote.nonce
      });
      localStorage.setItem(intentKey, JSON.stringify({ ...intent, hash }));
      setAnchorIntent({ ...intent, hash });
      setTx(hash);
      await publicClient.waitForTransactionReceipt({ hash, confirmations: 2, timeout: 45_000 });
      await readAnchorReceipt(hash, activeDigest);
    } catch (error) { setNotice("发送或核验状态需人工确认，禁止重复提交：" + friendlyWalletError(error)); }
    finally { setBusy(false); }
  }
  useEffect(() => {
    if (anchorIntent?.hash && contractStatus === "已通过 RPC 字节码核对")
      void readAnchorReceipt(anchorIntent.hash, anchorIntent.digest).catch(() => {
        setNotice("已恢复本地交易 Hash，回执暂未核验；请点击只读重试，勿重复发送。");
      });
    // Reload uses only the public digest/hash hint; every success label requires RPC receipt and storage.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [anchorIntent?.hash, contractStatus]);
  const readyForFixedDemo = !!(provider && address && preview && preview.task.chain_id === 677 &&
    chainId === 677 && isAddress(serviceSigner) && serviceId.trim() &&
    matchesConfirmedDemoBinding(preview.task, address, serviceId, serviceSigner));
  const readyToSign = readyForFixedDemo && rpcChainId === 677 &&
    contractStatus === "已通过 RPC 字节码核对";
  const readyToQuote = !!(readyForFixedDemo && activeDigest && anchorAddress && anchorRuntimeHash);
  const readyToAnchor = !!(readyToSign && activeDigest && anchorQuote &&
    anchorQuote.digest === activeDigest && !anchorIntent &&
    (signed || historicalAcknowledged) &&
    mainnetWritesEnabled && anchorAddress && anchorRuntimeHash &&
    contractStatus === "已通过 RPC 字节码核对");
  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span><span>TreasuryTally <small>BOT CHAIN EDITION</small></span></div>
      <a href="https://github.com/CH-ZHOU-0512/TreasuryTally" target="_blank" rel="noreferrer">原项目 ↗</a></header>
    <section className="hero"><div className="eyebrow">ETH WUHAN 2026 · LOCAL DEVELOPMENT PREVIEW</div>
      <h1>让每笔任务承诺<br/><em>有据可查。</em></h1>
      <p>核验服务商报表、链上资金流与公开回执。演示合约已部署在 BOT Chain 677；本页可审阅此前签名观察记录和执行只读交易预览。主网写入需单独批准。</p>
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
        {rpcError && <p className="warning">{rpcError}。这不会清除已载入的历史摘要；只读预览会重新检查 RPC。</p>}
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
        <div className="warning">既往记录：2026-10-16 页面曾显示该固定 TaskCommitment 通过 TypeScript 与原 Python 模型校验，并产生摘要 {historicalObservation.task_digest}。原始签名未保存；当前页面无法独立重验该签名。</div>
        <button className="secondary" onClick={restoreHistoricalDigest} disabled={!readyForFixedDemo || busy || !!anchorIntent}>
          载入先前已核验的公开摘要（本地记录）</button>
        {prepared && <div className="preview"><h3>待签消息已与审阅文件核对</h3><pre>{JSON.stringify(reviewedTypedData, null, 2)}</pre>
          <p className="hint">服务签名者 {prepared.serviceSigner} 不属于上游任务签名字段；本地应用规则将它与内部 Demo 服务绑定，原合约不验证此授权。</p>
          <button onClick={signTask} disabled={busy || !taskSignaturesEnabled || pendingSignatureAvailable || signRequestAttempted || !!signed}>签署 EIP-712 任务承诺</button>
          {pendingSignatureAvailable && <button className="secondary" onClick={retryPythonVerification} disabled={busy}>
            重试本地 Python 交叉校验（不请求新签名）</button>}
          {pendingSignatureAvailable && <p className="hint">此标签页内存暂存签名，仅用于本地交叉校验；不会写入存储或日志。请勿刷新或关闭页面。</p>}
          {signRequestAttempted && !signed && !pendingSignatureAvailable && <p className="hint">此标签页已发起过一次 MetaMask 签名请求，不会自动重发。若请求被拒绝或校验失败，请先停止并联系项目维护者。</p>}
          {!taskSignaturesEnabled && <p className="hint">任务签名安全锁已启用；尚未请求 MetaMask 签名。</p>}</div>}
        {signed && <dl className="facts signed"><div><dt>签名者 / 请求者</dt><dd>{signed.message.requester}</dd></div>
          <div><dt>登记的服务签名者</dt><dd>{signed.serviceSigner}</dd></div>
          <div><dt>EIP-712 摘要</dt><dd>{typedDataDigest(signed.message)}</dd></div>
          <div><dt>完整任务摘要</dt><dd>{signed.digest}</dd></div>
          <div><dt>服务 ID SHA-256</dt><dd>{signed.serviceIdHash}</dd></div></dl>}
        {historicalDigest && <div className="preview"><h3>既往签名观察记录 · 本次未重新验签</h3>
          <p>来源：{historicalObservation.source_report}；记录 SHA-256：{historicalObservation.source_report_sha256}。</p>
          <dl className="facts"><div><dt>先前确认的 taskDigest</dt><dd>{historicalDigest}</dd></div>
            <div><dt>请求者</dt><dd>{confirmedDemo.requester}</dd></div>
            <div><dt>原始签名</dt><dd>未保存；当前无法独立重验</dd></div></dl>
          <p className="hint">仅载入本地固定记录；主网 Chain ID、合约字节码、重复登记和 eth_call 将在下一步只读预览中检查。</p></div>}
      </section>
    </div>
    <section className="panel"><div className="panel-head"><span className="step">02A</span><h2>完整 EIP-712 签名前预览</h2>
      <span className="pill caution">{signed ? "本次签名已验证" : historicalDigest ? "既往摘要已载入" : "本次未签署"}</span></div>
      <p className="muted">以下是固定的内部 Demo TaskCommitment 结构化数据，来自已确认的 TaskSpec 和原 Python 模型；查看它不会请求钱包签名。既往摘要不等于本次重新验签。</p>
      <dl className="facts"><div><dt>目标合约</dt><dd>{anchorAddress || "未配置"} · {contractStatus}</dd></div>
        <div><dt>TaskSpec SHA-256</dt><dd>{signingPreview.task_spec_hash}</dd></div>
        <div><dt>EIP-712 消息摘要</dt><dd>{signingPreview.typed_data_digest}</dd></div>
        <div><dt>服务 ID SHA-256</dt><dd>{signingPreview.service_id_hash}</dd></div>
        <div><dt>拟登记 serviceSigner</dt><dd>{signingPreview.service_signer}</dd></div></dl>
      <details open><summary>domain、types、primaryType、message 全字段</summary>
        <pre>{JSON.stringify(reviewedTypedData, null, 2)}</pre></details>
      <div className="warning">签名域没有 verifyingContract，不能阻止同链其他合约复用该签名。原 TaskCommitment 消息不含 serviceSigner；此服务地址仅由网页绑定和后续 anchorTask 参数表达。service_id 是内部 Demo 标识，不是已注册 ERC-8004 身份。这个固定区块的 RPC 查询返回零条匹配转账，签名或登记都不代表财务核验通过。获授权签名后，原始签名只会送到本机 127.0.0.1 的 Python 校验端点并保留在页面内存，不写入仓库或日志。</div>
    </section>
    <section className="panel anchor-panel"><div className="panel-head"><span className="step">03</span><h2>链上登记</h2>
      <span className="pill caution">主网写入未开放</span></div>
      <p className="muted">登记只证明请求者钱包在 BOT Chain 上承诺过指定任务摘要与服务签名者，不证明服务报表真实，也不代表财务核验通过。</p>
      <dl className="facts"><div><dt>候选合约</dt><dd>CommitmentAnchor.sol</dd></div>
        <div><dt>主网地址</dt><dd>{anchorAddress || "尚未部署"}</dd></div>
        <div><dt>字节码核对</dt><dd>{contractStatus} <button className="secondary" onClick={() => void refreshContract()}>重试只读核验</button></dd></div>
        <div><dt>交易</dt><dd>{tx ? <a href={`https://scan.botchain.ai/tx/${tx}`} target="_blank" rel="noreferrer">{tx} ↗</a> : "未提交"}</dd></div></dl>
      {activeDigest && !anchorIntent && <button className="secondary" onClick={prepareAnchorQuote}
        disabled={busy || !readyToQuote}>运行只读 anchorTask 模拟与费用预览</button>}
      {anchorQuote && activeDigest && <div className="preview"><h3>anchorTask 交易预览 · 未批准发送</h3>
        <dl className="facts"><div><dt>From</dt><dd>{confirmedDemo.requester}</dd></div>
          <div><dt>To</dt><dd>{anchorAddress}</dd></div>
          <div><dt>Network</dt><dd>BOT Chain Mainnet · 677</dd></div>
          <div><dt>Function</dt><dd>anchorTask(bytes32,bytes32,bytes32,address)</dd></div>
          <div><dt>taskDigest</dt><dd>{activeDigest}</dd></div>
          <div><dt>specHash</dt><dd>{preview?.hash}</dd></div>
          <div><dt>serviceIdHash</dt><dd>{signingPreview.service_id_hash}</dd></div>
          <div><dt>serviceSigner</dt><dd>{serviceSigner}</dd></div>
          <div><dt>Gas 估算 / 上限</dt><dd>{anchorQuote.gas.toString()} / {anchorQuote.gasLimit.toString()}</dd></div>
          <div><dt>Gas 报价</dt><dd>{anchorQuote.gasPrice.toString()} wei</dd></div>
          <div><dt>最高费用 / 余额</dt><dd>{formatEther(anchorQuote.maxFee)} BOT / {formatEther(anchorQuote.balance)} BOT</dd></div>
          <div><dt>nonce</dt><dd>{anchorQuote.nonce}</dd></div></dl>
        <div className="warning">{historicalDigest ? "此摘要来自先前签名观察记录；当前没有原始签名，未重新验签。" : "当前签名已在本次会话交叉校验。"}合约只记录承诺，不验证签名、服务方授权、资金转账或报表金额。此预览来自只读 eth_call 模拟与 Gas 估算；主网交易需另行明确批准并由你本人确认钱包弹窗。</div>
      </div>}
      {historicalDigest && <label className="acknowledge"><input type="checkbox" checked={historicalAcknowledged}
        onChange={e => setHistoricalAcknowledged(e.target.checked)}/>
        我已核对这是此前真实签名的历史观察记录，当前未重新验签；若以后获准发送，将使用上述固定摘要。</label>}
      {anchorIntent && <div className="warning">本机已有提交意图：摘要 {anchorIntent.digest}。{anchorIntent.hash
        ? "请以链上回执为准；即使超时也禁止自动重复发送。" : "尚无交易 Hash，广播状态未知；请检查钱包活动与账户 nonce，禁止重复发送。"}</div>}
      {anchorIntent?.hash && <button className="secondary" onClick={refreshAnchorReceipt} disabled={busy}>只读重查交易回执、事件与存储</button>}
      {anchorRecord && <dl className="facts signed"><div><dt>已核验 taskDigest</dt><dd>{anchorRecord.digest}</dd></div>
        <div><dt>TaskAnchored / tasks</dt><dd>回执事件和合约存储一致</dd></div>
        <div><dt>区块</dt><dd>{anchorRecord.block}</dd></div>
        <div><dt>实际 Gas 费</dt><dd>{formatEther(BigInt(anchorRecord.fee))} BOT</dd></div>
        <div><dt>BOTScan</dt><dd><a href={`https://scan.botchain.ai/tx/${anchorRecord.hash}`}
          target="_blank" rel="noreferrer">{anchorRecord.hash} ↗</a></dd></div></dl>}
      <button disabled={!readyToAnchor || busy} onClick={anchorTask}>在 BOT Chain 登记 anchorTask</button>
      <button className="secondary" onClick={() => void refreshWriteApproval()} disabled={busy}>检查本地写入授权状态</button>
      <p className="hint">本地主网写入授权：{mainnetWritesEnabled ? "开发环境已开启，仍需主动点击并亲自确认 MetaMask" : "关闭"}</p>
      {!mainnetWritesEnabled && <p className="hint">业务写入安全锁已启用：已部署合约的 anchorTask 仍需单独批准，当前不会发送交易。</p>}
    </section>
    {notice && <div className="notice" role="status">{notice}</div>}
    <footer><span>公开 Demo 数据仅用于流程展示 · 不构成财务核验</span><a href="/preflight">主网只读预检 ↗</a><a href="/deploy">部署预览 ↗</a><a href="https://scan.botchain.ai" target="_blank" rel="noreferrer">BOT Explorer ↗</a></footer>
  </main>;
}
