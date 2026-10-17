export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export type VisitorWriteStatus = {
  enabled: boolean;
  scope: "VISITOR_SELF_DEMO_ONLY";
  reason: "enabled" | "emergency_switch" | "explicitly_disabled" |
    "local_default_closed" | "preview_environment" | "unsupported_host";
};

export function resolveVisitorWriteStatus(
  env: Record<string, string | undefined> = process.env
): VisitorWriteStatus {
  if (env.DISABLE_PUBLIC_DEMO_WRITES !== undefined &&
      env.DISABLE_PUBLIC_DEMO_WRITES !== "false")
    return { enabled: false, scope: "VISITOR_SELF_DEMO_ONLY", reason: "emergency_switch" };
  if (env.ENABLE_PUBLIC_DEMO_WRITES === "false")
    return { enabled: false, scope: "VISITOR_SELF_DEMO_ONLY", reason: "explicitly_disabled" };
  if (env.NODE_ENV === "development") {
    const enabled = env.ENABLE_PUBLIC_DEMO_WRITES === "true";
    return { enabled, scope: "VISITOR_SELF_DEMO_ONLY",
      reason: enabled ? "enabled" : "local_default_closed" };
  }
  if (env.VERCEL === "1" && env.VERCEL_ENV === "production") {
    if (env.ENABLE_PUBLIC_DEMO_WRITES !== undefined && env.ENABLE_PUBLIC_DEMO_WRITES !== "true")
      return { enabled: false, scope: "VISITOR_SELF_DEMO_ONLY", reason: "explicitly_disabled" };
    return { enabled: true, scope: "VISITOR_SELF_DEMO_ONLY", reason: "enabled" };
  }
  return { enabled: false, scope: "VISITOR_SELF_DEMO_ONLY",
    reason: env.VERCEL === "1" ? "preview_environment" : "unsupported_host" };
}

export async function GET() {
  // Production Vercel enables this public, permissionless demo by default.
  // DISABLE_PUBLIC_DEMO_WRITES=true is the independent emergency stop.
  return Response.json(resolveVisitorWriteStatus(),
    { headers: { "Cache-Control": "no-store" } });
}
