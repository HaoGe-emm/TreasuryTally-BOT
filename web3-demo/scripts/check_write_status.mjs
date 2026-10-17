import assert from "node:assert/strict";
import { join } from "node:path";
import { GET } from "../app/api/mainnet-write-status/route.ts";

const previousNodeEnv = process.env.NODE_ENV;
const originalCwd = process.cwd();
process.env.NODE_ENV = "development";
try {
  const local = await GET(new Request("http://127.0.0.1:3000/api/mainnet-write-status", {
    headers: { host: "127.0.0.1:3000" }
  }));
  assert.equal(local.status, 200);
  assert.deepEqual(await local.json(), {
    enabled: false, status: "disabled", scope: "LOCAL_DEVELOPMENT_ONLY"
  });
  assert.equal(local.headers.get("Cache-Control"), "no-store");

  const nonlocal = await GET(new Request("http://example.com/api/mainnet-write-status", {
    headers: { host: "example.com" }
  }));
  assert.equal(nonlocal.status, 403);
  const blocked = await nonlocal.json();
  assert.equal(blocked.enabled, false);
  assert.equal(blocked.status, "unavailable");
  process.chdir(join(originalCwd, "scripts"));
  const missingConfig = await GET(new Request("http://127.0.0.1:3000/api/mainnet-write-status", {
    headers: { host: "127.0.0.1:3000" }
  }));
  assert.equal(missingConfig.status, 503);
  assert.deepEqual((await missingConfig.json()).status, "unavailable");
  console.log("PASS: disabled authorization is distinct from unavailable API/config; nonlocal checks fail closed");
} finally {
  process.chdir(originalCwd);
  if (previousNodeEnv === undefined) delete process.env.NODE_ENV;
  else process.env.NODE_ENV = previousNodeEnv;
}
