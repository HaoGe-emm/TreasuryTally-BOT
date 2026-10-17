# Stage 4 local release readiness

Date: 2026-10-17 (Asia/Shanghai)

## Scope and attribution

This is a local release-preparation record for `web3-demo`. Upstream sources, fixed snapshot SHAs, source archive hashes, license findings and the user's independent deployment authorization are recorded in [`../../SOURCE_AND_AUTHORIZATION.md`](../../SOURCE_AND_AUTHORIZATION.md). The business repository did not provide a repository-wide LICENSE at the pinned source snapshot; do not imply that it did. The unchanged `CommitmentAnchor.sol` source contains its own SPDX identifier. No upstream website or server was accessed for modification.

## Production routes and behavior

- `/`: historical BOT Chain registration, verified deployment reference and a live read-only check of chain, code hash, deployment/anchor receipts, event and `tasks` storage.
- `/try`: visitor-owned TaskSpec, EIP-712 display/signature verification, read-only duplicate/simulation/Gas preview, and a wallet-submitted `anchorTask` flow.
- `/lab`, `/deploy`: local legacy tools only; production routes return 404.
- `/api/verify-signed-demo`: local Python cross-check endpoint only; production rejects it and `/try` does not call it.
- `/api/visitor-write-status`: uncached runtime status. Vercel Production defaults open; Vercel Preview, local production builds and development default closed. `ENABLE_PUBLIC_DEMO_WRITES=false` explicitly closes the gate; `DISABLE_PUBLIC_DEMO_WRITES=true` is an independent emergency stop. The gate does not alter contract permissions; the contract itself is permissionless.

The production Vercel deployment will offer visitor writes by default under this policy, provided its runtime reports `VERCEL=1` and `VERCEL_ENV=production`, and it has no explicit `ENABLE_PUBLIC_DEMO_WRITES=false` value. Before launch, remove any old Production value set to `false` or change it to `true`. The independent emergency variable can close the route immediately. Local and Preview remain closed unless the development environment explicitly enables its test gate. This local code change does not publish the site or verify Vercel's runtime environment.

Every visitor task is generated from the connected requester, a new random task identifier, visitor-entered token/recipient/block and the original TaskSpec canonical hash. The browser verifies the visitor's EIP-712 signature and recovered requester; before send it rechecks the active wallet/network, fixed contract bytecode, task signature/digest, duplicate state, latest/pending nonce, simulation, gas quote and balance. It displays all four parameters and maximum fee; only the visitor's explicit click calls the wallet provider. Attempt records are scoped per requester in browser storage to prevent one visitor from blocking another. A rejected wallet request is cleared as unbroadcast; an ambiguous send error is locked for manual lookup and not retried.

## Vercel setup for a later approved release

- Root Directory: `web3-demo`
- Framework: Next.js
- Install: `npm ci` from `package-lock.json`
- Build: `npm run build`
- Output Directory: use the Next.js platform integration (Vercel uses `.next`; local builds use `.next-build`)
- Production environment: leave `ENABLE_PUBLIC_DEMO_WRITES` unset or set it to `true`; remove any inherited `false` value from the prior read-only plan
- Emergency stop: set `DISABLE_PUBLIC_DEMO_WRITES=true`; normal state is unset or `false`
- Preview/local environment: default closed; the development gate requires explicit `ENABLE_PUBLIC_DEMO_WRITES=true`
- No Python runtime, `BOT_DEMO_PYTHON`, localhost URL, Windows path, or secret RPC key is required for the public visitor route.

There is no `web3-demo/vercel.json`; set project configuration in the Vercel project when separately authorized. This report does not publish or change any hosting settings.

## Acceptance evidence and limits

Automated production smoke checks should use a locally built Next server, not infer app failure from a separate sandbox's inability to reach Windows localhost. The previously attempted port 3100 reported `EADDRINUSE`, while process/connection enumeration was blocked or empty in the constrained host context and curl timed out. The owning process could not be identified safely. Do not terminate an unknown process. The app was therefore smoke-tested on an alternate local port; see the final stage report for exact results.

Real MetaMask/OKX extensions and the live BOT RPC must be verified in a normal browser after any public release. Automated mocks do not count as real wallet acceptance. The code path is an actual wallet write flow, but no new visitor signature or transaction was requested or sent in this local preparation. Public availability still depends on Vercel deployment and verifying the runtime status endpoint.

Security boundary: the contract is permissionless and does not verify the EIP-712 signature or bind it to `serviceSigner`; the original domain has no `verifyingContract` and `expiresAt` is empty. The frontend enforces its own flow, but an external caller can bypass the site and call the contract directly. A chain record only anchors the supplied task commitment; it does not validate a financial report, actual token transfer, or service authorization. Visitors pay their own wallet's gas. No project-funded wallet or transaction relayer exists.

No new wallet signature, BOT Chain transaction, deployment, GitHub push or Vercel release was performed for Stage 4.
