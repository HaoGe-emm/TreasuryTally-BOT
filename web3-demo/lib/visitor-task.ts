import { getAddress, isAddress, type Address, type Hex } from "viem";
import { parseTaskSpec, sha256, stableHash, taskDigest, utcTimestamp,
  verifySignature, verifySpec, type TaskCommitmentMessage, type TaskSpec } from "./task";

// This label describes a visitor's self-service demo, not a TreasuryTally
// provider or registered ERC-8004 identity. The serviceSigner is the visitor.
export const visitorServiceId = "treasurytally-bot-self-demo-v1";

export type VisitorTaskInput = {
  requester: Address; token: string; recipient: string; block: number;
  taskId: string; confirmedAt: string;
};

export async function createVisitorTask(input: VisitorTaskInput): Promise<TaskSpec> {
  if (!isAddress(input.requester) || !isAddress(input.token) || !isAddress(input.recipient))
    throw new Error("Token、请求者和收款方必须是有效 EVM 地址");
  if (input.requester.toLowerCase() === input.recipient.toLowerCase())
    throw new Error("Demo 收款方须与请求者不同");
  if (!Number.isSafeInteger(input.block) || input.block < 0)
    throw new Error("区块高度必须是非负整数");
  if (!/^bot677-visitor-demo-[a-zA-Z0-9-]{1,120}$/.test(input.taskId))
    throw new Error("访客 Demo 任务 ID 格式无效");
  const unsigned = {
    schema_version: "1.0" as const, task_id: input.taskId, chain_id: 677,
    token_address: getAddress(input.token),
    treasury_addresses: [getAddress(input.requester)],
    recipient_addresses: [getAddress(input.recipient)],
    start_block: input.block, end_block: input.block,
    exclusion_rules: [], max_records: 200 as const,
    confirmed_at: utcTimestamp(input.confirmedAt)
  };
  return parseTaskSpec({ ...unsigned, spec_hash: await stableHash(unsigned) });
}

export async function createVisitorMessage(
  task: TaskSpec, requester: Address, commitmentId: string
): Promise<TaskCommitmentMessage> {
  if (task.chain_id !== 677 || task.treasury_addresses.length !== 1 ||
      task.treasury_addresses[0].toLowerCase() !== requester.toLowerCase() ||
      !/^task-commitment-[a-zA-Z0-9-]{1,120}$/.test(commitmentId))
    throw new Error("TaskSpec 请求者或承诺 ID 与访客 Demo 不一致");
  await verifySpec(task);
  return { commitmentId, taskId: task.task_id, specHash: task.spec_hash,
    requester: getAddress(requester), serviceId: visitorServiceId,
    createdAt: utcTimestamp(task.confirmed_at, true), expiresAt: "" };
}

export async function visitorServiceIdHash(): Promise<Hex> {
  return sha256(new TextEncoder().encode(visitorServiceId));
}

export async function verifyVisitorCommitment(
  task: TaskSpec, message: TaskCommitmentMessage, signature: Hex,
  activeAccount: Address
): Promise<{ digest: Hex; serviceIdHash: Hex }> {
  const specHash = await verifySpec(task);
  if (task.chain_id !== 677 || message.specHash !== specHash ||
      message.taskId !== task.task_id || message.serviceId !== visitorServiceId ||
      message.requester.toLowerCase() !== activeAccount.toLowerCase() ||
      task.treasury_addresses.length !== 1 ||
      task.treasury_addresses[0].toLowerCase() !== activeAccount.toLowerCase() ||
      message.createdAt !== utcTimestamp(task.confirmed_at, true) || message.expiresAt !== "")
    throw new Error("TaskSpec、签名消息或当前账户绑定不一致");
  if (!(await verifySignature(message, signature)))
    throw new Error("EIP-712 签名不能恢复为当前请求者");
  return { digest: await taskDigest(message, signature),
    serviceIdHash: await visitorServiceIdHash() };
}
