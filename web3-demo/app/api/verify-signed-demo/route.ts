import { spawn } from "node:child_process";
import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

export const runtime = "nodejs";

async function localSignatureApprovalEnabled(): Promise<boolean> {
  try {
    const localEnv = await readFile(resolve(process.cwd(), ".env.local"), "utf8");
    return /^\s*NEXT_PUBLIC_ENABLE_TASK_SIGNATURES\s*=\s*true\s*$/m.test(localEnv);
  } catch { return false; }
}

type CheckResult = { requester: string; taskDigest: string; specHash: string;
  serviceIdHash: string; serviceSigner: string; typedDataDigest: string; scope: string };

function checkWithPython(signature: string, executable: string): Promise<CheckResult> {
  return new Promise((resolveResult, reject) => {
    const script = resolve(process.cwd(), "../scripts/bot/verify_signed_demo.py");
    const child = spawn(executable, [script], {
      cwd: resolve(process.cwd(), ".."), windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"]
    });
    let stdout = "";
    let stderr = "";
    let finished = false;
    const finish = (error?: Error, result?: CheckResult) => {
      if (finished) return;
      finished = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolveResult(result as CheckResult);
    };
    const timer = setTimeout(() => { child.kill(); finish(new Error("本地 Python 校验超时")); }, 8_000);
    child.stdout.on("data", chunk => {
      stdout += String(chunk);
      if (stdout.length > 4096) { child.kill(); finish(new Error("本地 Python 输出过长")); }
    });
    child.stderr.on("data", chunk => {
      stderr += String(chunk);
      if (stderr.length > 4096) { child.kill(); finish(new Error("本地 Python 错误输出过长")); }
    });
    child.on("error", () => finish(new Error("无法启动本地 Python 校验器")));
    child.on("close", code => {
      if (code !== 0) { finish(new Error("原 TreasuryTally Python 签名校验失败")); return; }
      try { finish(undefined, JSON.parse(stdout) as CheckResult); }
      catch { finish(new Error("Python 校验结果格式无效")); }
    });
    child.stdin.end(JSON.stringify({ signature }));
  });
}

export async function POST(request: Request) {
  const responseHeaders = { "Cache-Control": "no-store" };
  const origin = request.headers.get("origin");
  if (process.env.NODE_ENV !== "development")
    return Response.json({ code: "not_development", error: "签名校验接口只在本地开发模式开放。" },
      { status: 403, headers: responseHeaders });
  if (!(await localSignatureApprovalEnabled()))
    return Response.json({ code: "signature_check_disabled",
      error: "本地任务签名校验未开放；.env.local 开关未启用。" },
      { status: 403, headers: responseHeaders });
  const requestUrl = new URL(request.url);
  const host = request.headers.get("host") || "";
  const loopbackHost = /^(127\.0\.0\.1|localhost)(:\d+)?$/i.test(host);
  const hostOrigin = `${requestUrl.protocol}//${host}`;
  if (!loopbackHost || !origin || (origin !== requestUrl.origin && origin !== hostOrigin))
    return Response.json({ code: "origin_mismatch", error: "请求来源与本地页面不一致。" },
      { status: 403, headers: responseHeaders });
  const executable = process.env.BOT_DEMO_PYTHON;
  if (!executable) return Response.json({ error: "本地 Python 校验器未配置" }, { status: 503, headers: responseHeaders });
  let parsed: Record<string, unknown>;
  try {
    const raw = await request.text();
    if (raw.length > 1024) throw new Error("too_large");
    parsed = JSON.parse(raw) as Record<string, unknown>;
  } catch {
    return Response.json({ code: "invalid_request", error: "签名校验请求格式无效。" },
      { status: 400, headers: responseHeaders });
  }
  if (Object.keys(parsed).length !== 1 || typeof parsed.signature !== "string" ||
      !/^0x[0-9a-fA-F]{130}$/.test(parsed.signature))
    return Response.json({ code: "invalid_signature_format", error: "钱包返回的签名格式不符合 65 字节 EVM 签名。" },
      { status: 400, headers: responseHeaders });
  try {
    const result = await checkWithPython(parsed.signature, executable);
    return Response.json(result, { headers: responseHeaders });
  } catch {
    // Never log or return the signature, process input, stderr, or stack.
    return Response.json({ code: "python_validation_failed",
      error: "Python 模型已执行，但未验证该签名；原始签名未记录。" },
      { status: 422, headers: responseHeaders });
  }
}
