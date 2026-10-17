import type { Hex } from "viem";
import historical from "../public/bot677-demo/historical-signature-observation.json";
import { confirmedDemo } from "./demo";

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

export const historicalObservation = historical;
