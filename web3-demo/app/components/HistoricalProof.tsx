"use client";

import { useCallback, useEffect, useState } from "react";
import { formatEther } from "viem";
import { anchorAddress } from "@/lib/anchor";
import { historicalAnchor, latestAnchor, verifyTaskAnchorEvidence,
  type VerifiedTaskAnchor } from "@/lib/anchor-proof";
import { friendlyWalletError } from "@/lib/wallet";
import CopyButton from "./CopyButton";

export default function HistoricalProof() {
  const [state, setState] = useState<"checking" | "verified" | "error">("checking");
  const [evidence, setEvidence] = useState<VerifiedTaskAnchor | null>(null);
  const [error, setError] = useState("");
  const [priorState, setPriorState] = useState<"idle" | "checking" | "verified" | "error">("idle");
  const [priorError, setPriorError] = useState("");
  const refresh = useCallback(async () => {
    setState("checking"); setEvidence(null); setError("");
    try {
      const result = await verifyTaskAnchorEvidence(latestAnchor);
      setEvidence(result); setState("verified");
    } catch (failure) { setError(friendlyWalletError(failure)); setState("error"); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  async function verifyPrior() {
    setPriorState("checking"); setPriorError("");
    try { await verifyTaskAnchorEvidence(historicalAnchor); setPriorState("verified"); }
    catch (failure) { setPriorError(friendlyWalletError(failure)); setPriorState("error"); }
  }
  return <section id="chain-proof" className="panel proof-panel" aria-labelledby="historical-heading">
    <div className="panel-head"><span className="step">04</span><h2 id="historical-heading">链上记录与验证</h2>
      <span className="pill">真实主网记录</span></div>
    <p className="muted">最新登记来自 BOT Chain 677。页面打开时读取交易回执、TaskAnchored 事件与合约存储；也可主动重新核验。</p>
    <div className="proof-status" role="status">
      <strong>最新任务登记</strong>
      <span>{state === "checking" ? "实时链上复核中…" : state === "verified"
        ? "实时核验通过 · Receipt / TaskAnchored / tasks 一致"
        : "实时复核暂不可用，请重试或查看 BOTScan"}</span>
      <button className="secondary" onClick={() => void refresh()} disabled={state === "checking"}>重新读链核验</button>
    </div>
    {state === "error" && <p className="warning" role="status">BOT RPC 读取失败或证据不一致：{error}。请稍后重试，并到 BOTScan 核对交易。</p>}
    <dl className="facts">
      <div><dt>业务合约</dt><dd><a href={`https://scan.botchain.ai/address/${anchorAddress}`}
        target="_blank" rel="noreferrer">{anchorAddress} ↗</a> <CopyButton value={anchorAddress} label="复制合约地址" /></dd></div>
      <div><dt>anchorTask 交易</dt><dd><a href={`https://scan.botchain.ai/tx/${latestAnchor.transactionHash}`}
        target="_blank" rel="noreferrer">{latestAnchor.transactionHash} ↗</a> <CopyButton value={latestAnchor.transactionHash} label="复制交易 Hash" /></dd></div>
      <div><dt>taskDigest</dt><dd>{latestAnchor.taskDigest}</dd></div>
      <div><dt>请求者</dt><dd>{latestAnchor.requester}</dd></div>
      <div><dt>serviceSigner</dt><dd>{latestAnchor.serviceSigner}</dd></div>
      <div><dt>TaskSpec SHA-256</dt><dd>{latestAnchor.specHash}</dd></div>
      <div><dt>service ID SHA-256</dt><dd>{latestAnchor.serviceIdHash}</dd></div>
      <div><dt>TaskAnchored 事件</dt><dd>{state === "verified"
        ? `字段全部匹配 · log index ${evidence?.logIndex}` : "等待实时读回"}</dd></div>
      <div><dt>tasks 存储</dt><dd>{state === "verified"
        ? "requester 与 serviceSigner 读回一致" : "等待实时读回"}</dd></div>
      {evidence && <>
        <div><dt>区块 / Gas</dt><dd>{evidence.blockNumber.toString()} / {evidence.gasUsed.toString()}</dd></div>
        <div><dt>实际费用</dt><dd>{formatEther(evidence.feeWei)} BOT</dd></div>
      </>}
    </dl>
    <details className="past-record"><summary>此前登记 · 0x3727…435c4d</summary>
      <p><a href={`https://scan.botchain.ai/tx/${historicalAnchor.transactionHash}`}
        target="_blank" rel="noreferrer">{historicalAnchor.transactionHash} ↗</a>
        <CopyButton value={historicalAnchor.transactionHash} label="复制此前交易 Hash" /></p>
      <p className="muted">taskDigest：{historicalAnchor.taskDigest}</p>
      <button className="secondary" onClick={() => void verifyPrior()} disabled={priorState === "checking"}>
        只读核验此前记录</button>
      <p role="status" className="hint">{priorState === "checking" ? "正在读链…"
        : priorState === "verified" ? "回执、TaskAnchored 事件与 tasks 存储一致"
        : priorState === "error" ? `复核失败：${priorError}` : "点击后实时核验"}</p>
    </details>
  </section>;
}
