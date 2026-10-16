import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, mkdirSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { createPublicClient, createWalletClient, custom, decodeEventLog } from "viem";
import { privateKeyToAccount } from "viem/accounts";
import ganache from "ganache";
import solc from "solc";

const root = resolve(import.meta.dirname, "../..");
const project = resolve(import.meta.dirname, "..");
const sha = bytes => "0x" + createHash("sha256").update(bytes).digest("hex");
const canonical = value => Array.isArray(value) ? "[" + value.map(canonical).join(",") + "]"
  : value && typeof value === "object" ? "{" + Object.keys(value).sort()
    .map(key => JSON.stringify(key) + ":" + canonical(value[key])).join(",") + "}"
  : JSON.stringify(value);
const stable = value => sha(Buffer.from(canonical(value), "utf8"));
const source = readFileSync(join(root, "contracts/CommitmentAnchor.sol"), "utf8");
const input = {
  language: "Solidity",
  sources: { "CommitmentAnchor.sol": { content: source } },
  settings: { evmVersion: "paris", optimizer: { enabled: true, runs: 200 },
    outputSelection: { "*": { "*": ["abi", "evm.bytecode.object", "evm.deployedBytecode.object"] } } }
};
const result = JSON.parse(solc.compile(JSON.stringify(input)));
const errors = (result.errors || []).filter(x => x.severity === "error");
assert.equal(errors.length, 0, errors.map(x => x.formattedMessage).join("\n"));
const artifact = result.contracts["CommitmentAnchor.sol"].CommitmentAnchor;
const artifactDir = join(project, ".tmp");
mkdirSync(artifactDir, { recursive: true });
writeFileSync(join(artifactDir, "CommitmentAnchor.paris.json"),
  JSON.stringify({ compiler: solc.version(), evmVersion: "paris",
    abi: artifact.abi, bytecode: "0x" + artifact.evm.bytecode.object,
    deployedBytecode: "0x" + artifact.evm.deployedBytecode.object }, null, 2));
// The unchanged upstream M8 integration script expects these filenames.
writeFileSync(join(artifactDir, "contracts_CommitmentAnchor_sol_CommitmentAnchor.abi"), JSON.stringify(artifact.abi));
writeFileSync(join(artifactDir, "contracts_CommitmentAnchor_sol_CommitmentAnchor.bin"), artifact.evm.bytecode.object);

const fixture = JSON.parse(readFileSync(join(root, "fixtures/m11/task-spec.json"), "utf8"));
const { spec_hash: originalHash, ...originalBody } = fixture;
assert.equal(stable(originalBody), originalHash, "upstream fixture canonical hash");
const localTask = { ...originalBody, chain_id: 1337 };
const specHash = stable(localTask);
const dev = ganache.provider({
  chain: { chainId: 1337, hardfork: "merge" },
  wallet: { deterministic: true },
  logging: { quiet: true }
});
const accounts = Object.entries(dev.getInitialAccounts());
const requester = privateKeyToAccount(accounts[0][1].secretKey);
const service = privateKeyToAccount(accounts[1][1].secretKey);
const stranger = privateKeyToAccount(accounts[2][1].secretKey);
const chain = { id: 1337, name: "Local EVM", nativeCurrency: { name: "ETH", symbol: "ETH", decimals: 18 },
  rpcUrls: { default: { http: ["http://127.0.0.1:18549"] } } };
const publicClient = createPublicClient({ chain, transport: custom(dev) });
const requesterWallet = createWalletClient({ account: requester, chain, transport: custom(dev) });
const serviceWallet = createWalletClient({ account: service, chain, transport: custom(dev) });
const strangerWallet = createWalletClient({ account: stranger, chain, transport: custom(dev) });
assert.equal(await publicClient.getChainId(), 1337);
const deploymentHash = await requesterWallet.deployContract({
  abi: artifact.abi, bytecode: "0x" + artifact.evm.bytecode.object, gas: 2_000_000n
});
const deployment = await publicClient.waitForTransactionReceipt({ hash: deploymentHash });
assert.equal(deployment.status, "success");
assert.ok(deployment.contractAddress);
const contract = deployment.contractAddress;
const code = await publicClient.getCode({ address: contract });
assert.ok(code && code !== "0x");
assert.equal(code.toLowerCase(), ("0x" + artifact.evm.deployedBytecode.object).toLowerCase());
const codeHash = sha(Buffer.from(code.slice(2), "hex"));

const message = {
  commitmentId: "task-commitment-local-demo-1", taskId: localTask.task_id,
  specHash, requester: requester.address, serviceId: "local-evm-service",
  createdAt: "2026-10-16T00:00:00+00:00", expiresAt: ""
};
const types = { TaskCommitment: [
  { name: "commitmentId", type: "string" }, { name: "taskId", type: "string" },
  { name: "specHash", type: "bytes32" }, { name: "requester", type: "address" },
  { name: "serviceId", type: "string" }, { name: "createdAt", type: "string" },
  { name: "expiresAt", type: "string" }
] };
const signature = await requester.signTypedData({
  domain: { name: "TrustReceipt", version: "1", chainId: 1337 },
  types, primaryType: "TaskCommitment", message
});
const taskDigest = stable({ message, chain_id: 1337, signature });
const serviceIdHash = sha(Buffer.from(message.serviceId, "utf8"));
const taskArgs = [taskDigest, specHash, serviceIdHash, service.address];
async function transaction(wallet, functionName, args) {
  const hash = await wallet.writeContract({ address: contract, abi: artifact.abi,
    functionName, args, gas: 500_000n });
  return publicClient.waitForTransactionReceipt({ hash });
}
const anchored = await transaction(requesterWallet, "anchorTask", taskArgs);
assert.equal(anchored.status, "success");
const minedTransaction = await publicClient.getTransaction({ hash: anchored.transactionHash });
assert.equal(minedTransaction.from.toLowerCase(), requester.address.toLowerCase());
assert.equal(minedTransaction.to.toLowerCase(), contract.toLowerCase());
assert.equal((await publicClient.getBlock({ blockNumber: anchored.blockNumber })).hash, anchored.blockHash);
const taskLogs = anchored.logs.filter(x => x.address.toLowerCase() === contract.toLowerCase())
  .map(log => decodeEventLog({ abi: artifact.abi, data: log.data, topics: log.topics }));
assert.equal(taskLogs.length, 1);
assert.equal(taskLogs[0].eventName, "TaskAnchored");
assert.equal(taskLogs[0].args.taskDigest, taskDigest);
assert.equal(taskLogs[0].args.requester.toLowerCase(), requester.address.toLowerCase());
assert.equal(taskLogs[0].args.serviceSigner.toLowerCase(), service.address.toLowerCase());
assert.equal(taskLogs[0].args.specHash, specHash);
assert.equal(taskLogs[0].args.serviceIdHash, serviceIdHash);
const stored = await publicClient.readContract({ address: contract, abi: artifact.abi,
  functionName: "tasks", args: [requester.address, taskDigest] });
assert.equal(stored[1].toLowerCase(), service.address.toLowerCase());
assert.equal((await transaction(requesterWallet, "anchorTask", taskArgs)).status, "reverted");
const otherNamespace = await transaction(strangerWallet, "anchorTask", taskArgs);
assert.equal(otherNamespace.status, "success");

// Model-shaped synthetic report only for the isolated local EVM, matching the
// upstream check_m8_anchor_local.py zero-record submission. No financial claim.
const nowJson = "2026-10-16T00:00:00Z";
const submissionBody = {
  schema_version: "1.0", submission_id: "local-only-1", task_id: localTask.task_id,
  service_id: message.serviceId, service_version: "local-only", attempt: 1,
  claimed_total_base_units: "0", claimed_count: 0, transfers: [], report_text: "{}", created_at: nowJson
};
const reportHash = stable(submissionBody);
const submission = { ...submissionBody, report_hash: reportHash, signature: null };
const submissionIdHash = sha(Buffer.from(submission.submission_id, "utf8"));
const acceptanceFields = [
  { name: "taskCommitmentId", type: "string" }, { name: "taskCommitmentHash", type: "bytes32" },
  { name: "specHash", type: "bytes32" }, { name: "serviceId", type: "string" },
  { name: "attempt", type: "uint256" }, { name: "acceptedAt", type: "string" }
];
const acceptanceMessage = { taskCommitmentId: message.commitmentId, taskCommitmentHash: taskDigest,
  specHash, serviceId: message.serviceId, attempt: 1, acceptedAt: message.createdAt };
const domain = { name: "TrustReceipt", version: "1", chainId: 1337 };
const acceptanceSignature = await service.signTypedData({ domain,
  types: { DeliveryAcceptance: acceptanceFields }, primaryType: "DeliveryAcceptance", message: acceptanceMessage });
const deliveryMessage = { ...acceptanceMessage, submissionId: submission.submission_id,
  reportHash, submittedAt: message.createdAt };
const deliverySignature = await service.signTypedData({ domain,
  types: { DeliveryCommitment: [...acceptanceFields, { name: "submissionId", type: "string" },
    { name: "reportHash", type: "bytes32" }, { name: "submittedAt", type: "string" }] },
  primaryType: "DeliveryCommitment", message: deliveryMessage });
const deliveryCommitment = {
  commitment_version: "1.0", task_commitment_id: message.commitmentId,
  task_commitment_hash: taskDigest, spec_hash: specHash, submission_id: submission.submission_id,
  service_id: message.serviceId, attempt: 1, report_hash: reportHash,
  accepted_at: nowJson, submitted_at: nowJson, signer_address: service.address,
  signature_scheme: "EIP712", acceptance_signature: acceptanceSignature, signature: deliverySignature
};
const deliveryDigest = stable(deliveryCommitment);
const deliveryArgs = [requester.address, taskDigest, 1, submissionIdHash, reportHash, deliveryDigest];
assert.equal((await transaction(strangerWallet, "anchorDelivery", deliveryArgs)).status, "reverted");
assert.equal((await transaction(requesterWallet, "anchorDelivery", deliveryArgs)).status, "reverted");
const delivery = await transaction(serviceWallet, "anchorDelivery", deliveryArgs);
assert.equal(delivery.status, "success");
const deliveryLogs = delivery.logs.filter(x => x.address.toLowerCase() === contract.toLowerCase())
  .map(log => decodeEventLog({ abi: artifact.abi, data: log.data, topics: log.topics }));
assert.equal(deliveryLogs.length, 1);
assert.equal(deliveryLogs[0].eventName, "DeliveryAnchored");
for (const [key, value] of Object.entries({
  taskDigest, requester: requester.address, serviceSigner: service.address,
  attempt: 1, submissionIdHash, reportHash, deliveryDigest
})) assert.equal(String(deliveryLogs[0].args[key]).toLowerCase(), String(value).toLowerCase(), key);
assert.equal((await transaction(serviceWallet, "anchorDelivery", deliveryArgs)).status, "reverted");
assert.equal((await transaction(serviceWallet, "anchorDelivery",
  [requester.address, taskDigest, 3, submissionIdHash, reportHash, deliveryDigest])).status, "reverted");
assert.equal(await publicClient.readContract({ address: contract, abi: artifact.abi,
  functionName: "delivered", args: [requester.address, taskDigest, 1] }), true);
// Intentional adversarial payload: the candidate accepts this reused digest at
// attempt 2. It enforces sender/range/uniqueness, not off-chain signature validity.
// This is a permission/storage test, not a valid second delivery commitment.
assert.equal((await transaction(serviceWallet, "anchorDelivery",
  [requester.address, taskDigest, 2, submissionIdHash, reportHash, deliveryDigest])).status, "success");
const zeroHash = "0x" + "00".repeat(32);
assert.equal((await transaction(requesterWallet, "anchorTask",
  [zeroHash, specHash, serviceIdHash, service.address])).status, "reverted");
const wrongNetworkWallet = createWalletClient({ account: requester, chain: { ...chain, id: 677 }, transport: custom(dev) });
await assert.rejects(() => transaction(wrongNetworkWallet, "anchorTask", taskArgs));
writeFileSync(join(artifactDir, "hash-vectors.json"), JSON.stringify({
  task: { ...localTask, spec_hash: specHash }, specHash, taskDigest, deliveryDigest,
  task_commitment: { commitment_version: "1.0", commitment_id: message.commitmentId,
    task_id: message.taskId, spec_hash: specHash, requester_address: requester.address,
    service_id: message.serviceId, created_at: nowJson, expires_at: null,
    signature_scheme: "EIP712", signature,
    anchor: { chain_id: 1337, status: "NOT_SUBMITTED", transaction_hash: null, block_number: null } },
  submission, delivery_commitment: deliveryCommitment
}, null, 2));

console.log(JSON.stringify({
  scope: "LOCAL SIMULATION ONLY", chainId: 1337, hardfork: "merge", evmVersion: "paris",
  compiler: solc.version(), contract, runtimeCodeSha256: codeHash,
  upstreamFixtureSpecHash: originalHash, localSpecHash: specHash,
  taskDigest, deploymentStatus: deployment.status, taskStatus: anchored.status,
  deliveryStatus: delivery.status, duplicateAndUnauthorized: "reverted",
  taskEvent: "verified", deliveryEvent: "verified", wrongNetwork: "rejected", invalidInput: "reverted"
}, null, 2));
await dev.disconnect();
