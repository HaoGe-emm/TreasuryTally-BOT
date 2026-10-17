import { readFile } from "node:fs/promises";
import { resolve } from "node:path";

export const runtime = "nodejs";

export async function GET(request: Request) {
  const requestUrl = new URL(request.url);
  const host = request.headers.get("host") || "";
  if (process.env.NODE_ENV !== "development" ||
      !/^(127\.0\.0\.1|localhost)(:\d+)?$/i.test(host))
    return Response.json({ enabled: false, scope: "LOCAL_DEVELOPMENT_ONLY" },
      { headers: { "Cache-Control": "no-store" } });
  try {
    const config = await readFile(resolve(process.cwd(), ".env.local"), "utf8");
    return Response.json({
      enabled: /^\s*NEXT_PUBLIC_ENABLE_MAINNET_WRITES\s*=\s*true\s*$/m.test(config),
      scope: "LOCAL_DEVELOPMENT_ONLY"
    }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return Response.json({ enabled: false, scope: "LOCAL_DEVELOPMENT_ONLY" },
      { headers: { "Cache-Control": "no-store" } });
  }
}
