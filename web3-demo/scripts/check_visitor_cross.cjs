const assert = require("node:assert/strict");
const { spawnSync } = require("node:child_process");
const { createVisitorTask, createVisitorMessage, verifyVisitorCommitment,
  visitorServiceIdHash } = require("../.tmp/test-lib/lib/visitor-task.js");
const { taskDomain, taskTypes, typedDataDigest, verifySpec } =
  require("../.tmp/test-lib/lib/task.js");
const { createHash } = require("node:crypto");

const python = process.env.BOT_TEST_PYTHON;
if (!python) throw new Error("Set BOT_TEST_PYTHON to an isolated Python with project dependencies");
const child = spawnSync(python, ["../scripts/bot/export_visitor_cross_vector.py"], {
  encoding: "utf8", timeout: 20000, maxBuffer: 512 * 1024,
  windowsHide: true
});
if (child.error || child.status !== 0)
  throw new Error("Original Python vector generator failed: " + (child.error?.message || child.stderr));
const vector = JSON.parse(child.stdout);

(async () => {
  const recreated = await createVisitorTask({ requester: vector.requester,
    token: vector.task.token_address, recipient: vector.task.recipient_addresses[0],
    block: vector.task.start_block, taskId: vector.task.task_id,
    confirmedAt: vector.task.confirmed_at });
  assert.deepEqual(recreated, vector.task, "TaskSpec normalization differs from Python");
  assert.equal(await verifySpec(recreated), vector.task.spec_hash);
  const message = await createVisitorMessage(recreated, vector.requester,
    vector.message.commitmentId);
  assert.deepEqual(message, vector.message, "TaskCommitment message differs from Python");
  assert.deepEqual(taskDomain, { name: "TrustReceipt", version: "1", chainId: 677 });
  assert.equal(taskTypes.TaskCommitment.length, 7);
  assert.equal(typedDataDigest(message), vector.typedDataDigest);
  const verified = await verifyVisitorCommitment(recreated, message,
    vector.signature, vector.requester);
  assert.equal(verified.digest, vector.taskDigest);
  assert.equal(verified.serviceIdHash, await visitorServiceIdHash());
  assert.equal(verified.serviceIdHash, "0x" + createHash("sha256")
    .update("treasurytally-bot-self-demo-v1").digest("hex"));
  await assert.rejects(() => verifyVisitorCommitment(recreated,
    { ...message, requester: vector.task.recipient_addresses[0] },
    vector.signature, vector.requester), /绑定不一致/);
  await assert.rejects(() => verifyVisitorCommitment(recreated,
    { ...message, serviceId: "different-service" },
    vector.signature, vector.requester), /绑定不一致/);
  await assert.rejects(() => verifyVisitorCommitment(recreated,
    message, vector.signature, vector.task.recipient_addresses[0]), /绑定不一致/);
  console.log("PASS: original Python ↔ TypeScript TaskSpec, canonical SHA-256, EIP-712 digest, signer recovery, taskDigest and binding guards");
})().catch(error => { console.error(error); process.exitCode = 1; });
