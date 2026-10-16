# TreasuryTally BOT Chain Web3 Demo

Local Next.js preview for the BOT Chain Edition. The approved demo CommitmentAnchor was deployed to BOT Chain 677 at `0xAf845BA2D1aF0e842FD2185fa081720D6D3D7148` (transaction `0x93f4f6ce8f4cffa249db4af14687af3ed1b64f1d82db8befd30efc444579ec2a`). See `../docs/bot/mainnet-deployment.json` for read-only RPC verification. Task signatures, further deployment, and mainnet business writes remain disabled in `.env.example` and local development config.

```powershell
cd D:\TreasuryTally-BOT\web3-demo
npm install
npm run dev
```

Open http://127.0.0.1:3000. `/preflight` performs read-only RPC calls without a wallet. `/deploy` lets a user connect a wallet, switch to BOT 677, and request a read-only deployment quote. Its deployment button is disabled by default. Connection and network changes happen only after clicks. Wallet names and rdns are extension supplied and should be checked against the wallet popup.

The homepage has two distinct task examples. The upstream public fixture is a Sepolia Demo and cannot be submitted as a BOT task. `public/bot677-demo/task-spec.json` is a user-confirmed **BOT 677 Demo request scope** using the upstream `TaskSpec` model. The matching canonical JSON, hash proof and provenance are adjacent. The fixed one-block RPC filter returned zero matching USDT Transfer logs. The task only asks for inspection of that scope; there is no claim that a transfer occurred or that financial verification passed.

TaskSpec hash: `0x9e0073e83868993f4da3bc013fe8aca7e90af7a99fb80bcda8d593963528d093`. The homepage recomputes it using the original model's canonical SHA-256 rules. A task digest does not exist until the requester supplies a real EIP-712 signature. The candidate contract stores a digest/requester/service signer mapping and emits the task and service hashes, but does not verify a signature, service authorization, funds, or report truth. The Demo account/service binding is checked in the frontend; the unmodified contract does not enforce it.

The published `CommitmentAnchor.paris.json` is generated from the unchanged upstream contract with solc 0.8.30, optimizer enabled with 200 runs, EVM paris. The local EVM test checks its ABI and both bytecodes against a fresh compilation. Deployment review compares the artifact with fixed SHA-256 values before quoting. Prior to any later write, recheck the wallet account, network, nonce, Gas and bytecode. Separate explicit approvals are required for mainnet contract deployment and `anchorTask`, and both require the user's own wallet confirmation. No GitHub or hosting publication is included here.
