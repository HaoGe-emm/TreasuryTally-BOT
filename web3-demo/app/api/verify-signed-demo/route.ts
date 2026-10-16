import { spawn } from "node:child_process";
import { resolve } from "node:path";

export const runtime = "nodejs";

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
  if (process.env.NODE_ENV !== "development" ||
      process.env.NEXT_PUBLIC_ENABLE_TASK_SIGNATURES !== "true" ||
      !origin || origin !== new URL(request.url).origin)
    return Response.json({ error: "本地任务签名校验未开放" }, { status: 403, headers: responseHeaders });
  const executable = process.env.BOT_DEMO_PYTHON;
  if (!executable) return Response.json({ error: "本地 Python 校验器未配置" }, { status: 503, headers: responseHeaders });
  try {
    const raw = await request.text();
    if (raw.length > 1024) throw new Error("请求过长");
    const parsed = JSON.parse(raw) as Record<string, unknown>;
    if (Object.keys(parsed).length !== 1 || typeof parsed.signature !== "string" ||
        !/^0x[0-9a-fA-F]{130}$/.test(parsed.signature)) throw new Error("签名格式无效");
    const result = await checkWithPython(parsed.signature, executable);
    return Response.json(result, { headers: responseHeaders });
  } catch {
    // The signature and process output are never logged or returned.
    return Response.json({ error: "签名未通过原 Python 模型校验" }, { status: 422, headers: responseHeaders });
  }
}
