import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const host = request.headers.get("host") || "";
  if (process.env.NODE_ENV !== "development" ||
      !/^(127\.0\.0\.1|localhost)(:\d+)?$/i.test(host))
    return Response.json({ enabled: false, status: "unavailable",
      reason: "仅本地开发页面可检查写入授权", scope: "LOCAL_DEVELOPMENT_ONLY" },
      { status: 403, headers: { "Cache-Control": "no-store" } });
  try {
    const config = await readFile(resolve(process.cwd(), ".env.local"), "utf8");
    const enabled = /^\s*NEXT_PUBLIC_ENABLE_MAINNET_WRITES\s*=\s*true\s*$/m.test(config);
    return Response.json({
      enabled, status: enabled ? "enabled" : "disabled", scope: "LOCAL_DEVELOPMENT_ONLY"
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ enabled: false, status: "unavailable",
      reason: "本地授权配置读取失败", scope: "LOCAL_DEVELOPMENT_ONLY" },
      { status: 503, headers: { "Cache-Control": "no-store" } });
  }
}
