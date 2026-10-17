import type { Hex } from "viem";
import historical from "../public/bot677-demo/historical-signature-observation.json";
import { confirmedDemo, requireConfirmedDemoBinding } from "./demo";
import { sha256, type TaskSpec } from "./task";

// This record is a previous UI observation, not a substitute for a recoverable
// signature. It permits a clearly labelled read-only preview of the digest that
// the user confirmed; the contract itself accepts a digest without a signature.
export function requireHistoricalObservation(): Hex {
  if (historical.status !== "HISTORICAL_UI_OBSERVATION_ONLY" ||
      historical.signature_retained !== false ||
      historical.chain_id !== 677 ||
      historical.source_commit !== "b3cda1cd07c7d811707340afe373db70cc73e8be" ||
      historical.source_report !== "docs/bot/stage3d-signature-observation.md" ||
      historical.source_report_sha256 !== confirmedDemo.historicalReportSha256 ||
      historical.requester.toLowerCase() !== confirmedDemo.requester.toLowerCase() ||
      historical.task_id !== confirmedDemo.taskId ||
      historical.spec_hash !== confirmedDemo.specHash ||
      historical.typed_data_digest !== confirmedDemo.typedDataDigest ||
      historical.task_digest !== confirmedDemo.historicalTaskDigest ||
      historical.service_id !== confirmedDemo.serviceId ||
      historical.service_id_hash !== "0x540bafe01cfa9731e46b8116f8dc63fa62e3a2853b0cb28beeabdaaa0ddbd7cd" ||
      historical.service_signer.toLowerCase() !== confirmedDemo.serviceSigner.toLowerCase())
    throw new Error("既往签名观察记录与固定 Demo 任务不一致");
  return historical.task_digest as Hex;
}

// Local recovery intentionally does not contact RPC or need the old signature.
// The separate anchorTask preview must check live chain, code, storage and eth_call.
export async function recoverHistoricalDigest(input: {
  task: TaskSpec; specHash: Hex; address: string; walletAccounts: string[];
  walletChainId: number; serviceId: string; serviceSigner: string;
}): Promise<Hex> {
  if (input.task.chain_id !== 677 || input.walletChainId !== 677 ||
      input.walletAccounts[0]?.toLowerCase() !== confirmedDemo.requester.toLowerCase() ||
      input.address.toLowerCase() !== confirmedDemo.requester.toLowerCase())
    throw new Error("钱包账户或钱包 Chain ID 与固定 BOT 677 Demo 不一致");
  requireConfirmedDemoBinding(input.task, input.address, input.serviceId, input.serviceSigner);
  const digest = requireHistoricalObservation();
  const serviceHash = await sha256(new TextEncoder().encode(input.serviceId));
  if (input.specHash !== confirmedDemo.specHash || serviceHash !== historical.service_id_hash)
    throw new Error("当前任务哈希或服务 ID 与既往记录不一致");
  return digest;
}

export const historicalObservation = historical;
