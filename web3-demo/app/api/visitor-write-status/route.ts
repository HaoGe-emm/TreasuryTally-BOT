export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET() {
  // An explicit deployment decision is needed before offering public writes.
  // This controls the website only; the deployed contract is permissionless.
  const enabled = process.env.ENABLE_PUBLIC_DEMO_WRITES === "true";
  return Response.json({ enabled, scope: "VISITOR_SELF_DEMO_ONLY" },
    { headers: { "Cache-Control": "no-store" } });
}
