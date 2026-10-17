# TreasuryTally BOT Chain Web3 Demo

Standalone Next.js application for the TreasuryTally BOT Chain Edition. It preserves the original project’s task model and attribution while presenting the confirmed BOT Chain 677 demo registration and a separate visitor-owned demo flow.

## Run locally

```powershell
cd D:\TreasuryTally-BOT\web3-demo
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. The homepage `/` directly provides wallet connection, BOT Chain 677 switching, TaskSpec creation, EIP-712 review and signing, read-only simulation and fee preview, and the visitor's separately confirmed `anchorTask` transaction. Below the task flow, it rechecks the historical deployment, transaction receipt, `TaskAnchored` event and contract storage against BOT Chain RPC. The former `/try` URL permanently redirects to `/`; it contains no second transaction implementation. `/lab` and `/deploy` are local-development-only legacy tools and return 404 in production.

## Historical on-chain proof

- Network: BOT Chain Mainnet, Chain ID 677
- Contract: [`0xAf845BA2D1aF0e842FD2185fa081720D6D3D7148`](https://scan.botchain.ai/address/0xaf845ba2d1af0e842fd2185fa081720d6d3d7148)
- Deployment transaction: [`0x93f4f6ce8f4cffa249db4af14687af3ed1b64f1d82db8befd30efc444579ec2a`](https://scan.botchain.ai/tx/0x93f4f6ce8f4cffa249db4af14687af3ed1b64f1d82db8befd30efc444579ec2a)
- Historical task registration: [`0x3727bca4c744308638da4dfcc79a5c2d86f1f0a81d0eaff8df2fa9e994435c4d`](https://scan.botchain.ai/tx/0x3727bca4c744308638da4dfcc79a5c2d86f1f0a81d0eaff8df2fa9e994435c4d)
- `taskDigest`: `0xc3702a7758dc0eb150ed0a51c13c8c30dd7b6b850f41c0abdcb446778361b25d`

This is an internal Demo task scope, not an ERC-8004 identity. Earlier read-only filtering found no matching USDT Transfer logs for its fixed block scope. The registration proves only that a commitment was recorded; it does not prove a transfer occurred, that a report is accurate, or that financial verification passed. Refreshing the page performs a new read-only RPC check; a saved hash or successful historical record is never presented as a new visitor transaction.

## Visitor flow and public-write gate

The homepage task flow uses the original `TaskSpec` fields, canonicalization, SHA-256 and EIP-712/taskDigest algorithms. Python ↔ TypeScript cross-vectors are generated from the original Python model and tested with `npm run test:visitor-cross`; production task signing and recovery run in TypeScript and do not call a localhost Python service. The legacy `/api/verify-signed-demo` endpoint is restricted to local development and is not used by the public task flow.

The visitor becomes both requester and the self-demo `serviceSigner`; this does not represent an independently authorized service provider. The page requires the visitor to review the task and complete an EIP-712 signature, a read-only duplicate check/simulation/fee quote, an explicit acknowledgement, and a separate wallet transaction confirmation. It records no automatic transaction. On Vercel Production, visitor writes are enabled by default when `ENABLE_PUBLIC_DEMO_WRITES` is unset or `true`; set it to `false` to close the gate. The independent emergency switch `DISABLE_PUBLIC_DEMO_WRITES=true` always closes writes. Local development and Vercel Preview default closed. This website gate does not change the deployed contract, which is permissionless.

The original EIP-712 domain does not include `verifyingContract`; the signed message does not directly bind `serviceSigner`; and `expiresAt` is empty. The deployed contract does not verify signatures or service authorization. The UI describes these limits before the wallet action. A wallet rejection is treated as no broadcast and permits a fresh user-requested preview; ambiguous send failures retain a one-shot guard and require manual transaction/nonce inspection.

## Published deployment

The independent public repository is [HaoGe-emm/TreasuryTally-BOT](https://github.com/HaoGe-emm/TreasuryTally-BOT), and the live Production demo is [treasurytally-bot.vercel.app](https://treasurytally-bot.vercel.app). Production visitors can initiate a new `anchorTask` registration with their own wallet and task digest. They must personally sign, review the transaction parameters and fee preview, explicitly submit, confirm in their wallet, and pay BOT Gas themselves. The application never signs or sends automatically and does not pay visitors' Gas.

The Vercel project uses **Root Directory** `web3-demo`, the Next.js framework preset, `npm ci`, and `npm run build`. Leave Next.js output handling to the platform; Vercel uses the standard `.next` build directory, while local production builds use `.next-build`. No public Python executable or local Windows path is needed. Production is configured with `ENABLE_PUBLIC_DEMO_WRITES=true` and `DISABLE_PUBLIC_DEMO_WRITES=false`; set `DISABLE_PUBLIC_DEMO_WRITES=true` as an independent emergency stop. Preview deployments remain closed by default. No `NEXT_PUBLIC_*` secret or user-specific RPC credential is required; the BOT RPC and verified contract are public constants. The live gate status is available at [`/api/visitor-write-status`](https://treasurytally-bot.vercel.app/api/visitor-write-status). Source and authorization details remain in [`../SOURCE_AND_AUTHORIZATION.md`](../SOURCE_AND_AUTHORIZATION.md); [`../docs/bot/stage4-release-readiness.md`](../docs/bot/stage4-release-readiness.md) records the earlier pre-release checks.
