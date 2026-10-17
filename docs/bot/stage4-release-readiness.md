# Stage 4 local release readiness

Date: 2026-10-17 (Asia/Shanghai)

## Scope and attribution

This is a local release-preparation record for `web3-demo`. Upstream sources, fixed snapshot SHAs, source archive hashes, license findings and the user's independent deployment authorization are recorded in [`../../SOURCE_AND_AUTHORIZATION.md`](../../SOURCE_AND_AUTHORIZATION.md). The business repository did not provide a repository-wide LICENSE at the pinned source snapshot; do not imply that it did. The unchanged `CommitmentAnchor.sol` source contains its own SPDX identifier. No upstream website or server was accessed for modification.

## Production routes and behavior

- `/`: historical BOT Chain registration, verified deployment reference and a live read-only check of chain, code hash, deployment/anchor receipts, event and `tasks` storage.
- `/try`: visitor-owned TaskSpec, EIP-712 display/signature verification, read-only duplicate/simulation/Gas preview, and a wallet-submitted `anchorTask` flow gated by `ENABLE_PUBLIC_DEMO_WRITES`.
- `/lab`, `/deploy`: local legacy tools only; production routes return 404.
- `/api/verify-signed-demo`: local Python cross-check endpoint only; production rejects it and `/try` does not call it.
- `/api/visitor-write-status`: uncached runtime status. Default is closed. The gate does not alter contract permissions; the contract itself is permissionless.

Visitor write flow is implemented but the public gate remains false by default. Thus, a deployment with the documented setting can connect wallets, switch to BOT Chain 677, create/sign its own task and perform read-only checks, but cannot submit a new registration. Competition claims must distinguish the previously successful historical wallet transaction from the currently gated visitor flow. Enabling public writes is a separate release-risk decision and has not occurred here.

## Vercel setup for a later approved release

- Root Directory: `web3-demo`
- Framework: Next.js
- Install: `npm ci` from `package-lock.json`
- Build: `npm run build`
- Output Directory: use the Next.js platform integration (custom Next build directory is `.next-build`)
- Environment: `ENABLE_PUBLIC_DEMO_WRITES=false` in Preview and Production by default
- No Python runtime, `BOT_DEMO_PYTHON`, localhost URL, Windows path, or secret RPC key is required for the public visitor route.

There is no `web3-demo/vercel.json`; set project configuration in the Vercel project when separately authorized. This report does not publish or change any hosting settings.

## Acceptance evidence and limits

Automated production smoke checks should use a locally built Next server, not infer app failure from a separate sandbox's inability to reach Windows localhost. The previously attempted port 3100 reported `EADDRINUSE`, while process/connection enumeration was blocked or empty in the constrained host context and curl timed out. The owning process could not be identified safely. Do not terminate an unknown process. The app was therefore smoke-tested on an alternate local port; see the final stage report for exact results.

Real MetaMask/OKX extensions and the live BOT RPC must be verified in a normal browser after any public release. Automated mocks do not count as real wallet acceptance. Do not claim the new visitor transaction flow is publicly available until the gate is explicitly enabled and a visitor independently confirms a real wallet transaction.

No new wallet signature, BOT Chain transaction, deployment, GitHub push or Vercel release was performed for Stage 4.
