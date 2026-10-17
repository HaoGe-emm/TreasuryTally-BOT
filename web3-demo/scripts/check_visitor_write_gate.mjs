import assert from "node:assert/strict";
import { GET, resolveVisitorWriteStatus } from "../app/api/visitor-write-status/route.ts";

const productionVercel = {
  NODE_ENV: "production", VERCEL: "1", VERCEL_ENV: "production"
};
const productionPreview = { ...productionVercel, VERCEL_ENV: "preview" };
const localDevelopment = { NODE_ENV: "development" };

assert.deepEqual(resolveVisitorWriteStatus(productionVercel), {
  enabled: true, scope: "VISITOR_SELF_DEMO_ONLY", reason: "enabled"
});
assert.equal(resolveVisitorWriteStatus({ ...productionVercel,
  ENABLE_PUBLIC_DEMO_WRITES: "true" }).enabled, true);
assert.equal(resolveVisitorWriteStatus({ ...productionVercel,
  ENABLE_PUBLIC_DEMO_WRITES: "false" }).reason, "explicitly_disabled");
assert.equal(resolveVisitorWriteStatus({ ...productionVercel,
  DISABLE_PUBLIC_DEMO_WRITES: "true" }).reason, "emergency_switch");
assert.equal(resolveVisitorWriteStatus({ ...productionVercel,
  DISABLE_PUBLIC_DEMO_WRITES: "unexpected" }).enabled, false);
assert.equal(resolveVisitorWriteStatus(productionPreview).reason, "preview_environment");
assert.equal(resolveVisitorWriteStatus({ ...productionPreview,
  ENABLE_PUBLIC_DEMO_WRITES: "true" }).enabled, false);
assert.equal(resolveVisitorWriteStatus(localDevelopment).reason, "local_default_closed");
assert.equal(resolveVisitorWriteStatus({ ...localDevelopment,
  ENABLE_PUBLIC_DEMO_WRITES: "true" }).enabled, true);
assert.equal(resolveVisitorWriteStatus({ ...localDevelopment,
  ENABLE_PUBLIC_DEMO_WRITES: "true", DISABLE_PUBLIC_DEMO_WRITES: "true" }).enabled, false);

const previous = { ...process.env };
try {
  process.env.NODE_ENV = "production";
  process.env.VERCEL = "1";
  process.env.VERCEL_ENV = "production";
  delete process.env.ENABLE_PUBLIC_DEMO_WRITES;
  delete process.env.DISABLE_PUBLIC_DEMO_WRITES;
  const response = await GET();
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal((await response.json()).enabled, true);
  console.log("PASS: Vercel Production defaults open; explicit and emergency closes fail closed; local and Preview remain closed by default");
} finally {
  for (const key of ["NODE_ENV", "VERCEL", "VERCEL_ENV", "ENABLE_PUBLIC_DEMO_WRITES",
    "DISABLE_PUBLIC_DEMO_WRITES"]) {
    if (previous[key] === undefined) delete process.env[key];
    else process.env[key] = previous[key];
  }
}
