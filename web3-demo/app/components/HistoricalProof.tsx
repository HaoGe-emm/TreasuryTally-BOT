"use client";

import { useCallback, useEffect, useState } from "react";
import { formatEther } from "viem";
import { anchorAddress } from "@/lib/anchor";
import { historicalAnchor, verifyTaskAnchorEvidence,
  type VerifiedTaskAnchor } from "@/lib/anchor-proof";
import { friendlyWalletError } from "@/lib/wallet";

export default function HistoricalProof() {
  const [state, setState] = useState<"checking" | "verified" | "error">("checking");
  const [evidence, setEvidence] = useState<VerifiedTaskAnchor | null>(null);
  const [error, setError] = useState("");
  const refresh = useCallback(async () => {
    setState("checking"); setEvidence(null); setError("");
    try {
      const result = await verifyTaskAnchorEvidence(historicalAnchor);
      setEvidence(result); setState("verified");
    } catch (failure) { setError(friendlyWalletError(failure)); setState("error"); }
  }, []);
  useEffect(() => { void refresh(); }, [refresh]);
  return <section className="panel proof-panel" aria-labelledby="historical-heading">
    <div className="panel-head"><span className="step">01</span><h2 id="historical-heading">已完成的主网任务登记</h2>
      <span className="pill">历史交易</span></div>
    <p className="muted">2026-10-17 的内部 Demo 任务已由请求者钱包在 BOT Chain 登记。以下交易和地址是公开链上证据；本页每次打开都会重新读取合约、回执、事件和存储。</p>
    <div className="proof-status" role="status">
      <strong>历史登记：已完成</strong>
      <span>{state === "checking" ? "实时链上复核中…" : state === "verified"
        ? "实时核验通过 · Receipt / TaskAnchored / tasks 一致"
        : "实时复核暂不可用 · 保留历史记录，未伪造本次核验"}</span>
      <button className="secondary" onClick={() => void refresh()} disabled={state === "checking"}>重新读链核验</button>
    </div>
    {state === "error" && <p className="warning" role="status">BOT RPC 读取失败或证据不一致：{error}。请稍后重试，并到 BOTScan 核对交易；这不是新的成功核验。</p>}
    <dl className="facts">
      <div><dt>业务合约</dt><dd><a href={`https://scan.botchain.ai/address/${anchorAddress}`}
        target="_blank" rel="noreferrer">{anchorAddress} ↗</a></dd></div>
      <div><dt>anchorTask 交易</dt><dd><a href={`https://scan.botchain.ai/tx/${historicalAnchor.transactionHash}`}
        target="_blank" rel="noreferrer">{historicalAnchor.transactionHash} ↗</a></dd></div>
      <div><dt>taskDigest</dt><dd>{historicalAnchor.taskDigest}</dd></div>
      <div><dt>请求者</dt><dd>{historicalAnchor.requester}</dd></div>
      <div><dt>serviceSigner</dt><dd>{historicalAnchor.serviceSigner}</dd></div>
      <div><dt>TaskSpec SHA-256</dt><dd>{historicalAnchor.specHash}</dd></div>
      <div><dt>service ID SHA-256</dt><dd>{historicalAnchor.serviceIdHash}</dd></div>
      <div><dt>TaskAnchored 事件</dt><dd>{state === "verified"
        ? `字段全部匹配 · log index ${evidence?.logIndex}` : "等待实时读回"}</dd></div>
      <div><dt>tasks 存储</dt><dd>{state === "verified"
        ? "requester 与 serviceSigner 读回一致" : "等待实时读回"}</dd></div>
      {evidence && <>
        <div><dt>区块 / Gas</dt><dd>{evidence.blockNumber.toString()} / {evidence.gasUsed.toString()}</dd></div>
        <div><dt>实际费用</dt><dd>{formatEther(evidence.feeWei)} BOT</dd></div>
      </>}
    </dl>
    <p className="hint">BOT Chain 在此承担任务承诺的时间顺序与公开读回：请求者将任务摘要及服务身份哈希登记，合约发出 TaskAnchored 事件，任何访客可对照交易输入、事件和 tasks 存储。它不验证报表或实际转账。</p>
  </section>;
}
