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

Stage 3D adds the **unsigned** fixed EIP-712 preview at `public/bot677-demo/task-commitment-preview.json`. It displays every domain, type and message field before any wallet action. The domain is `TrustReceipt` version `1`, chain 677; it lacks `verifyingContract`. The original message does not bind `serviceSigner`, which the application checks separately. Its EIP-712 message digest is `0x193954b4c310b54ac5b93bf9cb546d31f831f40b76378a100c53010d93fb7f2a`; this is **not** the signature-dependent `taskDigest`. The Python checker at `../scripts/bot/check_demo_signing_preview.py` validates the TaskSpec and preview using the upstream model. No real signature or task registration exists yet.

Both `NEXT_PUBLIC_ENABLE_TASK_SIGNATURES` and `NEXT_PUBLIC_ENABLE_MAINNET_WRITES` remain `false`. Each may only be enabled in local development after its own explicit user approval. The later signature flow recovers the requester in viem and cross-checks the signature-dependent digest with the upstream Python implementation through a local, development-only endpoint. The raw signature is never committed or logged. After a valid signature, the later read-only `anchorTask` quote simulates the call, checks duplication, pending nonce, Gas and balance, and displays all parameters. Sending still needs a separate approval and a manual MetaMask confirmation. A public digest and transaction hash may be kept in browser storage for read-only receipt, event and contract storage recovery after refresh; a missing or uncertain broadcast blocks automatic retry.

The published `CommitmentAnchor.paris.json` is generated from the unchanged upstream contract with solc 0.8.30, optimizer enabled with 200 runs, EVM paris. The local EVM test checks its ABI and both bytecodes against a fresh compilation. Deployment review compares the artifact with fixed SHA-256 values before quoting. Prior to any later write, recheck the wallet account, network, nonce, Gas and bytecode. Mainnet `anchorTask` requires its own explicit approval and the user's wallet confirmation. No GitHub or hosting publication is included here.
