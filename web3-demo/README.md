# TreasuryTally BOT Chain Web3 Demo

Standalone Next.js application for the TreasuryTally BOT Chain Edition. It preserves the original project’s task model and attribution while presenting the confirmed BOT Chain 677 demo registration and a separate visitor-owned demo flow.

## Run locally

```powershell
cd D:\TreasuryTally-BOT\web3-demo
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. `/` displays the historical registration and rechecks the deployment, transaction receipt, `TaskAnchored` event and contract storage against BOT Chain RPC. `/try` lets a visitor connect a supported EVM wallet, create a new TaskSpec, inspect its EIP-712 data, sign it, and run a read-only simulation and fee preview. `/lab` and `/deploy` are local-development-only legacy tools and return 404 in production.

## Historical on-chain proof

- Network: BOT Chain Mainnet, Chain ID 677
- Contract: [`0xAf845BA2D1aF0e842FD2185fa081720D6D3D7148`](https://scan.botchain.ai/address/0xaf845ba2d1af0e842fd2185fa081720d6d3d7148)
- Deployment transaction: [`0x93f4f6ce8f4cffa249db4af14687af3ed1b64f1d82db8befd30efc444579ec2a`](https://scan.botchain.ai/tx/0x93f4f6ce8f4cffa249db4af14687af3ed1b64f1d82db8befd30efc444579ec2a)
- Historical task registration: [`0x3727bca4c744308638da4dfcc79a5c2d86f1f0a81d0eaff8df2fa9e994435c4d`](https://scan.botchain.ai/tx/0x3727bca4c744308638da4dfcc79a5c2d86f1f0a81d0eaff8df2fa9e994435c4d)
- `taskDigest`: `0xc3702a7758dc0eb150ed0a51c13c8c30dd7b6b850f41c0abdcb446778361b25d`

This is an internal Demo task scope, not an ERC-8004 identity. Earlier read-only filtering found no matching USDT Transfer logs for its fixed block scope. The registration proves only that a commitment was recorded; it does not prove a transfer occurred, that a report is accurate, or that financial verification passed. Refreshing the page performs a new read-only RPC check; a saved hash or successful historical record is never presented as a new visitor transaction.

## Visitor flow and public-write gate

`/try` uses the original `TaskSpec` fields, canonicalization, SHA-256 and EIP-712/taskDigest algorithms. Python ↔ TypeScript cross-vectors are generated from the original Python model and tested with `npm run test:visitor-cross`; production visitor signing and recovery run in TypeScript and do not call a localhost Python service. The legacy `/api/verify-signed-demo` endpoint is restricted to local development and is not used by the visitor page.

The visitor becomes both requester and the self-demo `serviceSigner`; this does not represent an independently authorized service provider. The page requires the visitor to review the task and complete an EIP-712 signature, a read-only duplicate check/simulation/fee quote, an explicit acknowledgement, and a separate wallet transaction confirmation. It records no automatic transaction. On Vercel Production, visitor writes are enabled by default when `ENABLE_PUBLIC_DEMO_WRITES` is unset or `true`; set it to `false` to close the gate. The independent emergency switch `DISABLE_PUBLIC_DEMO_WRITES=true` always closes writes. Local development and Vercel Preview default closed. This website gate does not change the deployed contract, which is permissionless.

The original EIP-712 domain does not include `verifyingContract`; the signed message does not directly bind `serviceSigner`; and `expiresAt` is empty. The deployed contract does not verify signatures or service authorization. The UI describes these limits before the wallet action. A wallet rejection is treated as no broadcast and permits a fresh user-requested preview; ambiguous send failures retain a one-shot guard and require manual transaction/nonce inspection.

## Deployment preparation (not published)

For a later Vercel release, set **Root Directory** to `web3-demo`, use the Next.js framework preset and the lockfile-backed default install (`npm ci`) with `npm run build`. Leave Next.js output handling to the platform; this app uses `.next-build` as its Next build directory. No public Python executable or local Windows path is needed. In Vercel Production, leave `ENABLE_PUBLIC_DEMO_WRITES` unset or set it to `true` for the intended public demo behavior; set `DISABLE_PUBLIC_DEMO_WRITES=true` as an independent emergency stop. Preview deployments remain closed by default. No `NEXT_PUBLIC_*` secret or user-specific RPC credential is required; the BOT RPC and verified contract are public constants. See [`../docs/bot/stage4-release-readiness.md`](../docs/bot/stage4-release-readiness.md) and [`../SOURCE_AND_AUTHORIZATION.md`](../SOURCE_AND_AUTHORIZATION.md).

No GitHub push, Vercel deployment, new mainnet transaction, or contract redeployment is included in local preparation.
