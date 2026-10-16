# TreasuryTally BOT Chain Web3 Demo

Phase 1 local preview. No BOT Chain mainnet contract is configured or deployed. Mainnet writes are disabled by default and must remain disabled until a separate review and approval.

```powershell
npm install
npm run dev
```

Open http://127.0.0.1:3000. Wallet discovery uses EIP-6963 with a legacy injection fallback. Connecting and switching networks only occur after a click. The bundled TaskSpec is an upstream public Sepolia demo sample and cannot be submitted as a BOT task.

To prepare a real BOT TaskSpec, use the upstream `TaskSpec` model and `task_spec_hash` function. Import its JSON into the page. The page recomputes the canonical SHA-256, verifies the EIP-712 signature against the connected requester, and exposes the full task commitment digest. The contract candidate stores only digests and public addresses; it does not validate reports, funds, service ownership, or financial results.

Before any later mainnet write, separately review and set `NEXT_PUBLIC_ANCHOR_ADDRESS`, `NEXT_PUBLIC_ANCHOR_RUNTIME_SHA256`, and `NEXT_PUBLIC_ENABLE_MAINNET_WRITES=true`. The last flag is intentionally absent from `.env.example`. The UI also checks wallet and RPC Chain ID 677, runtime bytecode SHA-256, duplicate task records, receipt status, and event fields.
