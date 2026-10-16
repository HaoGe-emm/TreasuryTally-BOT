import { hashTypedData, isAddress, isHex, recoverTypedDataAddress, type Address, type Hex } from "viem";
import { botChain } from "./chain";

export type TaskSpec = {
  schema_version: "1.0"; task_id: string; chain_id: number;
  token_address: Address; treasury_addresses: Address[]; recipient_addresses: Address[];
  start_block: number; end_block: number;
  exclusion_rules: { rule_id: string; rule_type: string; reason: string }[];
  max_records: 200; confirmed_at: string; spec_hash: Hex;
};

export type TaskCommitmentMessage = {
  commitmentId: string; taskId: string; specHash: Hex; requester: Address;
  serviceId: string; createdAt: string; expiresAt: string;
};

export const taskTypes = {
  TaskCommitment: [
    { name: "commitmentId", type: "string" },
    { name: "taskId", type: "string" },
    { name: "specHash", type: "bytes32" },
    { name: "requester", type: "address" },
    { name: "serviceId", type: "string" },
    { name: "createdAt", type: "string" },
    { name: "expiresAt", type: "string" }
  ]
} as const;
export const taskDomain = { name: "TrustReceipt", version: "1", chainId: botChain.id } as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}
function validAddressArray(value: unknown, min: number, max = Infinity): value is Address[] {
  return Array.isArray(value) && value.length >= min && value.length <= max &&
    value.every(x => typeof x === "string" && isAddress(x, { strict: false })) &&
    new Set(value.map(x => x.toLowerCase())).size === value.length;
}
function integer(value: unknown, min: number): value is number {
  return typeof value === "number" && Number.isSafeInteger(value) && value >= min;
}
// Pydantic JSON uses UTC Z; datetime.isoformat() in upstream EIP-712 uses +00:00.
// Preserve microseconds exactly instead of rounding through JavaScript Date.
export function utcTimestamp(value: string, eip712 = false): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?(?:Z|\+00:00)$/.exec(value);
  if (!match) throw new Error("时间必须为 UTC ISO-8601，精度最多为微秒");
  const [, year, month, day, hour, minute, second, fraction = ""] = match;
  const base = `${year}-${month}-${day}T${hour}:${minute}:${second}`;
  const parsed = new Date(base + "Z");
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 19) !== base)
    throw new Error("时间日期无效");
  const micros = fraction.padEnd(6, "0");
  return base + (Number(micros) ? "." + micros : "") + (eip712 ? "+00:00" : "Z");
}
export function parseTaskSpec(raw: unknown): TaskSpec {
  if (!isRecord(raw)) throw new Error("TaskSpec 必须是 JSON 对象");
  const keys = ["schema_version", "task_id", "chain_id", "token_address",
    "treasury_addresses", "recipient_addresses", "start_block", "end_block",
    "exclusion_rules", "max_records", "confirmed_at", "spec_hash"];
  if (Object.keys(raw).some(k => !keys.includes(k)) || keys.some(k => !(k in raw)))
    throw new Error("TaskSpec 字段不符合上游模型");
  if (raw.schema_version !== "1.0" || typeof raw.task_id !== "string" ||
      raw.task_id.length < 1 || raw.task_id.length > 200 ||
      !integer(raw.chain_id, 1) || typeof raw.token_address !== "string" ||
      !isAddress(raw.token_address, { strict: false }) || !validAddressArray(raw.treasury_addresses, 1, 2) ||
      !validAddressArray(raw.recipient_addresses, 1) ||
      !integer(raw.start_block, 0) || !integer(raw.end_block, 0) ||
      raw.start_block > raw.end_block || raw.max_records !== 200 ||
      typeof raw.confirmed_at !== "string" ||
      typeof raw.spec_hash !== "string" || !isHex(raw.spec_hash, { strict: true }) ||
      raw.spec_hash.length !== 66 || !Array.isArray(raw.exclusion_rules))
    throw new Error("TaskSpec 内容不符合上游模型");
  const rules = raw.exclusion_rules;
  if (!rules.every(rule => isRecord(rule) &&
      Object.keys(rule).sort().join(",") === "reason,rule_id,rule_type" &&
      typeof rule.rule_id === "string" && rule.rule_id.length > 0 && rule.rule_id.length <= 200 &&
      typeof rule.reason === "string" && rule.reason.length > 0 &&
      rule.rule_type === "EXCLUDE_TREASURY_INTERNAL") ||
      new Set(rules.map(rule => (rule as { rule_id: string }).rule_id)).size !== rules.length)
    throw new Error("排除规则不符合上游模型");
  return { ...raw, confirmed_at: utcTimestamp(raw.confirmed_at) } as TaskSpec;
}

function canonical(value: unknown): string {
  if (Array.isArray(value)) return "[" + value.map(canonical).join(",") + "]";
  if (isRecord(value)) return "{" + Object.keys(value).sort()
    .map(k => JSON.stringify(k) + ":" + canonical(value[k])).join(",") + "}";
  if (typeof value === "number" && !Number.isSafeInteger(value)) throw new Error("不允许浮点或不安全整数");
  return JSON.stringify(value);
}
export async function sha256(bytes: Uint8Array): Promise<Hex> {
  const digest = await crypto.subtle.digest("SHA-256", bytes as BufferSource);
  return ("0x" + Array.from(new Uint8Array(digest), x => x.toString(16).padStart(2, "0")).join("")) as Hex;
}
export async function stableHash(value: unknown): Promise<Hex> {
  return sha256(new TextEncoder().encode(canonical(value)));
}
export async function verifySpec(task: TaskSpec): Promise<Hex> {
  const { spec_hash: _ignored, ...withoutHash } = task;
  const actual = await stableHash(withoutHash);
  if (actual !== task.spec_hash)
    throw new Error("TaskSpec 的规范化 SHA-256 与 spec_hash 不匹配");
  return actual;
}
export async function taskDigest(message: TaskCommitmentMessage, signature: Hex): Promise<Hex> {
  return stableHash({ message, chain_id: botChain.id, signature });
}
export function requireBotContext(task: TaskSpec, requester: Address, activeAccount: string | undefined,
  walletChain: number, rpcChain: number): void {
  if (task.chain_id !== 677 || walletChain !== 677 || rpcChain !== 677)
    throw new Error("钱包、RPC 与 TaskSpec 必须全部为 BOT Chain 677");
  if (!activeAccount || activeAccount.toLowerCase() !== requester.toLowerCase())
    throw new Error("当前钱包账户与任务请求者不匹配");
}
export async function verifySignature(message: TaskCommitmentMessage, signature: Hex): Promise<boolean> {
  const recovered = await recoverTypedDataAddress({
    domain: taskDomain, types: taskTypes, primaryType: "TaskCommitment", message, signature
  });
  return recovered.toLowerCase() === message.requester.toLowerCase();
}
export function typedDataDigest(message: TaskCommitmentMessage): Hex {
  return hashTypedData({ domain: taskDomain, types: taskTypes, primaryType: "TaskCommitment", message });
}
