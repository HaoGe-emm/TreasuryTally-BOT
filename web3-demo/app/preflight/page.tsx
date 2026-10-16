"use client";

import { useState } from "react";
import { sha256 } from "@/lib/task";
import { formatEther, hexToBytes, isAddress, keccak256, pad, stringToBytes, toHex, type Hex } from "viem";
import demoTask from "@/public/bot677-demo/task-spec.json";
import demoProvenance from "@/public/bot677-demo/demo-provenance.json";

type Probe = { method: string; result: string; status: "成功" | "失败" };
type Artifact = { compiler: string; evmVersion: string; bytecode: Hex; deployedBytecode: Hex };
const endpoint = "https://rpc.botchain.ai";

async function rpc(method: string, params: unknown[]): Promise<unknown> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 8_000);
  try {
    const response = await fetch(endpoint, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
      signal: controller.signal, cache: "no-store"
    });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = await response.json() as { result?: unknown; error?: { code: number; message: string } };
    if (body.error) throw new Error(`RPC ${body.error.code}: ${body.error.message}`);
    if (body.result === undefined) throw new Error("RPC 缺少 result");
    return body.result;
  } finally { clearTimeout(timer); }
}

export default function Preflight() {
  const [running, setRunning] = useState(false);
  const [walletAddress, setWalletAddress] = useState("");
  const [results, setResults] = useState<Probe[]>([]);
  async function run() {
    setRunning(true); setResults([]);
    const record = (probe: Probe) => setResults(current => [...current, probe]);
    async function check(method: string, params: unknown[], summary: (value: unknown) => string, label = method) {
      try { record({ method: label, status: "成功", result: summary(await rpc(method, params)) }); return true; }
      catch (error) {
        record({ method: label, status: "失败", result: String(error).slice(0, 500) }); return false;
      }
    }
    try {
      if (!(await check("eth_chainId", [], value => {
        if (value !== "0x2a5") throw new Error(`RPC Chain ID ${String(value)}，预期 0x2a5`);
        return `${value} (677)`;
      }))) return;
      const inspected = walletAddress.trim();
      if (inspected && !isAddress(inspected)) {
        record({ method: "wallet address", status: "失败", result: "请输入完整有效的 EVM 公开地址" });
      } else if (inspected) {
        await check("eth_getBalance", [inspected, "latest"], value => {
          const wei = BigInt(String(value));
          return JSON.stringify({ address: inspected, wei: wei.toString(), BOT: formatEther(wei) });
        });
        await check("eth_getTransactionCount", [inspected, "latest"], value =>
          String(BigInt(String(value))), "eth_getTransactionCount latest");
        await check("eth_getTransactionCount", [inspected, "pending"], value =>
          String(BigInt(String(value))), "eth_getTransactionCount pending");
        await check("eth_getCode", [inspected, "latest"], value =>
          JSON.stringify({ address: inspected, codeBytes: (String(value).length - 2) / 2 }));
      }
      await check("eth_getBlockByNumber", ["latest", false], value => {
        const block = value as Record<string, unknown>;
        return JSON.stringify({ number: block.number, hash: block.hash,
          timestamp: block.timestamp, gasLimit: block.gasLimit, baseFeePerGas: block.baseFeePerGas ?? null });
      });
      const fixedBlock = toHex(demoTask.start_block);
      const fixedBlockOk = await check("eth_getBlockByNumber", [fixedBlock, false], value => {
        const block = value as Record<string, unknown> | null;
        if (!block || String(block.hash).toLowerCase() !== demoProvenance.block_hash_observed.toLowerCase())
          throw new Error("Demo 区块 Hash 与任务来源记录不一致");
        return JSON.stringify({ number: block.number, hash: block.hash, demoScope: true });
      });
      if (fixedBlockOk) {
        const transferTopic = keccak256(stringToBytes("Transfer(address,address,uint256)"));
        const fromTopic = pad(demoTask.treasury_addresses[0] as Hex, { size: 32 }).toLowerCase();
        const toTopic = pad(demoTask.recipient_addresses[0] as Hex, { size: 32 }).toLowerCase();
        await check("eth_getLogs", [{ address: demoTask.token_address, fromBlock: fixedBlock,
          toBlock: fixedBlock, topics: [transferTopic, fromTopic, toTopic] }], value => {
          if (!Array.isArray(value) || value.length > demoTask.max_records)
            throw new Error("日志数量无效或超过 TaskSpec.max_records");
          const logs = value.map(item => {
            const log = item as Record<string, unknown>;
            const topics = log.topics as string[];
            if (!Array.isArray(topics) || topics.length !== 3 ||
                String(log.address).toLowerCase() !== demoTask.token_address.toLowerCase() ||
                String(log.blockHash).toLowerCase() !== demoProvenance.block_hash_observed.toLowerCase() ||
                topics[0].toLowerCase() !== transferTopic ||
                topics[1].toLowerCase() !== fromTopic || topics[2].toLowerCase() !== toTopic)
              throw new Error("RPC 日志与已确认 Demo 任务过滤条件不符");
            return { transactionHash: log.transactionHash, logIndex: log.logIndex,
              blockHash: log.blockHash, value_base_units: BigInt(String(log.data)).toString() };
          });
          return JSON.stringify({ taskSpecHash: demoTask.spec_hash, matchingTransferLogs: logs.length, logs });
        });
      }
      await check("eth_gasPrice", [], String);
      await check("eth_maxPriorityFeePerGas", [], String);
      await check("eth_feeHistory", ["0x2", "latest", [50]], value => {
        const fees = value as Record<string, unknown>;
        return JSON.stringify({ oldestBlock: fees.oldestBlock,
          baseFeePerGas: fees.baseFeePerGas, reward: fees.reward });
      });
      const artifactResponse = await fetch("/CommitmentAnchor.paris.json", { cache: "no-store" });
      if (!artifactResponse.ok) throw new Error("本地编译产物不可读取");
      const artifact = await artifactResponse.json() as Artifact;
      const runtimeHash = await sha256(hexToBytes(artifact.deployedBytecode));
      record({ method: "local artifact", status: "成功", result: JSON.stringify({
        compiler: artifact.compiler, evmVersion: artifact.evmVersion,
        creationBytes: (artifact.bytecode.length - 2) / 2,
        runtimeBytes: (artifact.deployedBytecode.length - 2) / 2, runtimeHash
      }) });
      await check("eth_estimateGas", [{ data: artifact.bytecode }], String);
      await check("eth_call", [{ data: artifact.bytecode }, "latest"], value => {
        const actual = String(value).toLowerCase();
        return JSON.stringify({ returnedBytes: (actual.length - 2) / 2,
          equalsCompiledRuntime: actual === artifact.deployedBytecode.toLowerCase() });
      });
    } catch (error) { record({ method: "local artifact", status: "失败", result: String(error) }); }
    finally { setRunning(false); }
  }
  return <main>
    <header className="topbar"><div className="brand"><span className="brand-mark">T</span><span>TreasuryTally <small>READ-ONLY PREFLIGHT</small></span></div><a href="/">返回 Demo</a></header>
    <section className="hero"><div className="eyebrow">BOT CHAIN · MAINNET 677</div><h1>主网只读预检</h1>
      <p>仅发送 JSON-RPC 读取、模拟执行与 Gas 估算请求；不会连接钱包、请求签名或发送交易。每项请求最多等待 8 秒。</p>
      <label>公开部署钱包地址（可选）<input value={walletAddress} onChange={event => setWalletAddress(event.target.value)}
        placeholder="0x…，仅用于只读查询余额和 nonce" autoComplete="off" /></label>
      <button onClick={() => void run()} disabled={running}>{running ? "检查中…" : "运行只读检查"}</button></section>
    <section className="panel"><h2>实际返回值</h2>
      <p className="muted">Demo 的 eth_getLogs 只查询已确认的 USDT、财库、收款账户与单一区块；返回零条只表示本次 RPC 过滤器没有匹配日志，不是财务核验结论。</p>
      {results.length ? <dl className="facts">{results.map((item, index) => <div key={`${item.method}-${index}`}>
        <dt>{item.method} · {item.status}</dt><dd>{item.result}</dd></div>)}</dl>
        : <div className="empty">尚未发起检查。结果仅代表本次浏览器、此 RPC 端点和此时区块状态。</div>}
    </section>
  </main>;
}
