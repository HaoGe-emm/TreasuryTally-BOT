import ganache from "ganache";

const server = ganache.server({ chain: { chainId: 1337, hardfork: "merge" },
  wallet: { deterministic: true }, logging: { quiet: true } });
await server.listen(18549, "127.0.0.1");
console.log("LOCAL SIMULATION ONLY: http://127.0.0.1:18549, chain 1337, Merge EVM; no mainnet or real keys");
for (const signal of ["SIGINT", "SIGTERM"])
  process.on(signal, async () => { await server.close(); process.exit(0); });
