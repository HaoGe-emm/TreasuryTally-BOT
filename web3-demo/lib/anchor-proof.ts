import { decodeEventLog, decodeFunctionData, hexToBytes, type Address, type Hex } from "viem";
import { anchorAbi, anchorAddress, anchorRuntimeHash, publicClient } from "./anchor";
import { sha256 } from "./task";

export const historicalAnchor = {
  requester: "0x89F415bb42e356E8b892C10B05522e0a8Ef151F3",
  taskDigest: "0xc3702a7758dc0eb150ed0a51c13c8c30dd7b6b850f41c0abdcb446778361b25d",
  specHash: "0x9e0073e83868993f4da3bc013fe8aca7e90af7a99fb80bcda8d593963528d093",
  serviceIdHash: "0x540bafe01cfa9731e46b8116f8dc63fa62e3a2853b0cb28beeabdaaa0ddbd7cd",
  serviceSigner: "0xb6bF6a936F529650992B71e2DeB79E80Fd3da71B",
  transactionHash: "0x3727bca4c744308638da4dfcc79a5c2d86f1f0a81d0eaff8df2fa9e994435c4d"
} as const;

export type ExpectedTaskAnchor = {
  requester: Address; taskDigest: Hex; specHash: Hex; serviceIdHash: Hex;
  serviceSigner: Address; transactionHash: Hex;
};
export type VerifiedTaskAnchor = {
  transactionHash: Hex; blockNumber: bigint; gasUsed: bigint;
  effectiveGasPrice: bigint; feeWei: bigint; logIndex: number;
};
const same = (a: string | null | undefined, b: string) => a?.toLowerCase() === b.toLowerCase();

// Every success label is derived from a fresh BOT 677 RPC receipt, decoded
// transaction/event, reviewed runtime code and the contract's tasks mapping.
export async function verifyTaskAnchorEvidence(expected: ExpectedTaskAnchor): Promise<VerifiedTaskAnchor> {
  const [chainId, code, transaction, receipt] = await Promise.all([
    publicClient.getChainId(), publicClient.getCode({ address: anchorAddress }),
    publicClient.getTransaction({ hash: expected.transactionHash }),
    publicClient.getTransactionReceipt({ hash: expected.transactionHash })
  ]);
  if (chainId !== 677 || !code || code === "0x" ||
      (await sha256(hexToBytes(code))).toLowerCase() !== anchorRuntimeHash.toLowerCase())
    throw new Error("BOT 677 或已部署合约字节码核对失败");
  if (receipt.status !== "success" || !same(receipt.transactionHash, expected.transactionHash) ||
      transaction.chainId !== 677 || !same(transaction.from, expected.requester) ||
      !same(transaction.to, anchorAddress) || transaction.value !== 0n)
    throw new Error("回执状态、交易网络、来源、目标或转账金额不一致");
  const call = decodeFunctionData({ abi: anchorAbi, data: transaction.input });
  if (call.functionName !== "anchorTask" ||
      !same(call.args[0], expected.taskDigest) || !same(call.args[1], expected.specHash) ||
      !same(call.args[2], expected.serviceIdHash) || !same(call.args[3], expected.serviceSigner))
    throw new Error("anchorTask 交易输入与任务承诺不一致");
  const matching = receipt.logs.filter(log => same(log.address, anchorAddress)).flatMap(log => {
    try {
      const event = decodeEventLog({ abi: anchorAbi, topics: log.topics, data: log.data });
      return event.eventName === "TaskAnchored" ? [{ log, event }] : [];
    } catch { return []; }
  });
  if (matching.length !== 1) throw new Error("回执缺少唯一的 TaskAnchored 事件");
  const { log, event } = matching[0];
  if (event.eventName !== "TaskAnchored" ||
      !same(event.args.taskDigest, expected.taskDigest) ||
      !same(event.args.requester, expected.requester) ||
      !same(event.args.serviceSigner, expected.serviceSigner) ||
      !same(event.args.specHash, expected.specHash) ||
      !same(event.args.serviceIdHash, expected.serviceIdHash))
    throw new Error("TaskAnchored 事件字段与任务承诺不一致");
  const stored = await publicClient.readContract({
    address: anchorAddress, abi: anchorAbi, functionName: "tasks",
    args: [expected.requester, expected.taskDigest]
  });
  if (!same(stored[0], expected.requester) || !same(stored[1], expected.serviceSigner))
    throw new Error("tasks 链上存储与回执事件不一致");
  return { transactionHash: expected.transactionHash, blockNumber: receipt.blockNumber,
    gasUsed: receipt.gasUsed, effectiveGasPrice: receipt.effectiveGasPrice,
    feeWei: receipt.gasUsed * receipt.effectiveGasPrice, logIndex: log.logIndex };
}
