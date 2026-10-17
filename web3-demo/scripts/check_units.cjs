const assert = require("node:assert/strict");
const { createHash } = require("node:crypto");
const fs = require("node:fs");
const { generatePrivateKey, privateKeyToAccount } = require("viem/accounts");
const { parseTaskSpec, verifySpec, stableHash, utcTimestamp, requireBotContext,
  taskDigest, typedDataDigest, verifySignature, taskDomain, taskTypes } = require("../.tmp/test-lib/lib/task.js");
const { collectWallets, switchToBot, walletChainId, friendlyWalletError } = require("../.tmp/test-lib/lib/wallet.js");
const { anchorAbi } = require("../.tmp/test-lib/lib/anchor.js");
const { confirmedDemo, requireConfirmedDemoBinding } = require("../.tmp/test-lib/lib/demo.js");
const { recoverHistoricalDigest, requireHistoricalObservation } = require("../.tmp/test-lib/lib/historical.js");
const historical = require("../.tmp/test-lib/public/bot677-demo/historical-signature-observation.json");
const compiledAbi = JSON.parse(fs.readFileSync("public/CommitmentAnchor.paris.json", "utf8")).abi;
function abiShape(item) {
  return { type: item.type, name: item.name,
    inputs: (item.inputs || []).map(x => [x.type, !!x.indexed]),
    outputs: (item.outputs || []).map(x => x.type) };
}
for (const item of anchorAbi) {
  const matching = compiledAbi.find(x => x.type === item.type && x.name === item.name);
  assert.ok(matching, `missing compiled ABI item ${item.name}`);
  assert.deepEqual(abiShape(item), abiShape(matching), `ABI mismatch ${item.name}`);
}

(async () => {
  const sample = JSON.parse(fs.readFileSync("public/demo-task-spec.json", "utf8"));
  assert.equal(await verifySpec(parseTaskSpec(sample)), sample.spec_hash);
  assert.equal(await verifySpec(parseTaskSpec({ ...sample,
    confirmed_at: sample.confirmed_at.replace("Z", "+00:00") })), sample.spec_hash);
  await assert.rejects(() => verifySpec({ ...sample, end_block: sample.end_block + 1 }));
  await assert.rejects(() => verifySpec({ ...sample, spec_hash: "0x" + sample.spec_hash.slice(2).toUpperCase() }));
  assert.throws(() => parseTaskSpec({ ...sample, chain_id: 677.1 }));
  assert.throws(() => parseTaskSpec({ ...sample, private_report: "forbidden" }));
  assert.throws(() => parseTaskSpec({ ...sample, confirmed_at: "2026-02-31T00:00:00Z" }));
  assert.throws(() => parseTaskSpec({ ...sample, exclusion_rules: [
    { rule_id: "r", rule_type: "UNKNOWN", reason: "x" } ] }));
  await assert.rejects(() => stableHash({ amount: 0.1 }));
  assert.equal(utcTimestamp("2026-10-16T00:00:00.123Z", true), "2026-10-16T00:00:00.123000+00:00");
  assert.equal(utcTimestamp("2026-10-16T00:00:00.000Z", true), "2026-10-16T00:00:00+00:00");
  const confirmedTask = parseTaskSpec(JSON.parse(fs.readFileSync("public/bot677-demo/task-spec.json", "utf8")));
  const demoProvenance = JSON.parse(fs.readFileSync("public/bot677-demo/demo-provenance.json", "utf8"));
  assert.equal(await verifySpec(confirmedTask), confirmedDemo.specHash);
  assert.equal(demoProvenance.requester, confirmedDemo.requester);
  assert.equal(demoProvenance.service_signer, confirmedDemo.serviceSigner);
  assert.equal(demoProvenance.service_id, confirmedDemo.serviceId);
  requireConfirmedDemoBinding(confirmedTask, confirmedDemo.requester, confirmedDemo.serviceId, confirmedDemo.serviceSigner);
  const signingPreview = JSON.parse(fs.readFileSync("public/bot677-demo/task-commitment-preview.json", "utf8"));
  assert.equal(signingPreview.status, "UNSIGNED_PREVIEW");
  assert.equal(signingPreview.task_spec_hash, confirmedDemo.specHash);
  assert.equal(signingPreview.service_signer, confirmedDemo.serviceSigner);
  assert.equal(signingPreview.service_id_hash, "0x540bafe01cfa9731e46b8116f8dc63fa62e3a2853b0cb28beeabdaaa0ddbd7cd");
  assert.deepEqual(signingPreview.domain, taskDomain);
  assert.deepEqual(signingPreview.types.TaskCommitment, taskTypes.TaskCommitment);
  assert.equal(signingPreview.primaryType, "TaskCommitment");
  assert.equal(typedDataDigest(signingPreview.message), confirmedDemo.typedDataDigest);
  assert.equal(signingPreview.typed_data_digest, confirmedDemo.typedDataDigest);
  assert.ok(!("signature" in signingPreview) && !("taskDigest" in signingPreview));
  assert.equal(requireHistoricalObservation(), confirmedDemo.historicalTaskDigest);
  assert.equal(historical.signature_retained, false);
  assert.equal(historical.source_report_sha256, confirmedDemo.historicalReportSha256);
  const reportSha = "0x" + createHash("sha256").update(fs.readFileSync(
    "../docs/bot/stage3d-signature-observation.md")).digest("hex");
  assert.equal(reportSha, historical.source_report_sha256, "the public historical record has its original report");
  const recovery = { task: confirmedTask, specHash: confirmedDemo.specHash,
    address: confirmedDemo.requester, walletAccounts: [confirmedDemo.requester],
    walletChainId: 677, serviceId: confirmedDemo.serviceId,
    serviceSigner: confirmedDemo.serviceSigner };
  assert.equal(await recoverHistoricalDigest(recovery), confirmedDemo.historicalTaskDigest);
  await assert.rejects(() => recoverHistoricalDigest({ ...recovery, walletChainId: 1 }), /钱包账户或钱包 Chain ID/);
  await assert.rejects(() => recoverHistoricalDigest({ ...recovery, walletAccounts: [confirmedDemo.serviceSigner] }), /钱包账户或钱包 Chain ID/);
  await assert.rejects(() => recoverHistoricalDigest({ ...recovery, specHash: "0x" + "00".repeat(32) }), /任务哈希或服务 ID/);
  const originalDigest = historical.task_digest;
  historical.task_digest = "0x" + "00".repeat(32);
  assert.throws(() => requireHistoricalObservation(), /不一致/);
  historical.task_digest = originalDigest;
  assert.throws(() => requireConfirmedDemoBinding(confirmedTask, confirmedDemo.serviceSigner, confirmedDemo.serviceId, confirmedDemo.serviceSigner));
  assert.throws(() => requireConfirmedDemoBinding(confirmedTask, confirmedDemo.requester, "wrong-service", confirmedDemo.serviceSigner));
  assert.throws(() => requireConfirmedDemoBinding(confirmedTask, confirmedDemo.requester, confirmedDemo.serviceId, confirmedDemo.requester));
  assert.throws(() => requireConfirmedDemoBinding({ ...confirmedTask, spec_hash: "0x" + "00".repeat(32) },
    confirmedDemo.requester, confirmedDemo.serviceId, confirmedDemo.serviceSigner));
  const requester = privateKeyToAccount(generatePrivateKey());
  const other = privateKeyToAccount(generatePrivateKey());
  const botTask = { ...sample, chain_id: 677 };
  requireBotContext(botTask, requester.address, requester.address, 677, 677);
  assert.throws(() => requireBotContext(sample, requester.address, requester.address, 677, 677));
  assert.throws(() => requireBotContext(botTask, requester.address, other.address, 677, 677));
  assert.throws(() => requireBotContext(botTask, requester.address, requester.address, 1, 677));
  assert.throws(() => requireBotContext(botTask, requester.address, requester.address, 677, 1));
  const message = { commitmentId: "local-unit-signature-only", taskId: sample.task_id,
    specHash: sample.spec_hash, requester: requester.address, serviceId: "unit-service",
    createdAt: "2026-10-16T00:00:00+00:00", expiresAt: "" };
  const signature = await requester.signTypedData({ domain: taskDomain, types: taskTypes,
    primaryType: "TaskCommitment", message });
  assert.equal(await verifySignature(message, signature), true);
  assert.equal(await verifySignature({ ...message, requester: other.address }, signature), false);
  assert.equal(await taskDigest(message, signature),
    await stableHash({ message, chain_id: 677, signature }));

  // These are protocol test doubles; no real extension is controlled or signed.
  let discovered = [], calls = [];
  global.window = new EventTarget();
  const meta = { request: async args => { calls.push(args); return "0x2a5"; } };
  const okx = { request: async args => { calls.push(args); return "0x2a5"; } };
  window.ethereum = { providers: [meta, okx] };
  window.addEventListener("eip6963:requestProvider", () => {
    for (const [uuid, name, rdns, provider] of [["m", "MetaMask", "io.metamask", meta],
      ["o", "OKX Wallet", "com.okex.wallet", okx]])
      window.dispatchEvent(new CustomEvent("eip6963:announceProvider", {
        detail: { info: { uuid, name, rdns }, provider }
      }));
  });
  const cleanup = collectWallets(value => { discovered = value; });
  assert.deepEqual(discovered.map(x => x.name), ["MetaMask", "OKX Wallet"]);
  assert.deepEqual(discovered.map(x => x.source), ["EIP-6963", "EIP-6963"]);
  const original = discovered[0].provider;
  window.dispatchEvent(new CustomEvent("eip6963:announceProvider", { detail: {
    info: { uuid: "m", name: "Impersonator", rdns: "io.metamask" },
    provider: { request: async () => "0x1" }
  } }));
  assert.equal(discovered[0].provider, original, "duplicate ID cannot redirect the selected provider");
  assert.equal(calls.length, 0, "discovery must not request accounts or network changes");
  assert.equal(await walletChainId(meta), 677);
  cleanup();
  let network = "0x1", switches = 0;
  const newNetworkProvider = { request: async args => {
    calls.push(args);
    if (args.method === "wallet_switchEthereumChain") {
      if (++switches === 1) throw { code: 4902 };
      network = "0x2a5";
    }
    if (args.method === "eth_chainId") return network;
  } };
  calls = [];
  await switchToBot(newNetworkProvider);
  assert.deepEqual(calls.map(x => x.method), ["wallet_switchEthereumChain", "wallet_addEthereumChain", "wallet_switchEthereumChain", "eth_chainId"]);
  assert.equal(calls[1].params[0].chainId, "0x2a5");
  assert.equal(await walletChainId(newNetworkProvider), 677);
  await assert.rejects(() => switchToBot({ request: async args =>
    args.method === "eth_chainId" ? "0x1" : null }), /仍未返回/);
  await assert.rejects(() => walletChainId({ request: async () => "0xffffffffffffffff" }), /安全范围/);
  const rejected = { request: async () => { throw { code: 4001 }; } };
  await assert.rejects(() => switchToBot(rejected));
  assert.match(friendlyWalletError({ code: 4001 }), /取消/);
  await assert.rejects(() => walletChainId({ request: async () => "677" }));
  console.log("PASS: canonical task hashes, microseconds, tampering, requester/chain guards, EIP-712 recovery, EIP-6963 MetaMask/OKX discovery, add/switch/refusal protocol tests (mock providers only)");
})().catch(error => { console.error(error); process.exitCode = 1; });
