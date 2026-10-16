export type Provider = {
  request(args: { method: string; params?: unknown[] | object }): Promise<unknown>;
  on?(event: string, listener: (...args: unknown[]) => void): void;
  removeListener?(event: string, listener: (...args: unknown[]) => void): void;
  isMetaMask?: boolean;
  isOkxWallet?: boolean;
  isOKExWallet?: boolean;
  providers?: Provider[];
};
export type WalletChoice = {
  id: string;
  name: string;
  rdns?: string;
  source: "EIP-6963" | "legacy injection";
  provider: Provider;
};
type Announcement = {
  info: { uuid: string; name: string; rdns: string };
  provider: Provider;
};

export function collectWallets(onChange: (wallets: WalletChoice[]) => void): () => void {
  const discovered = new Map<string, WalletChoice>();
  const publish = () => onChange(Array.from(discovered.values()));
  const add = (choice: WalletChoice) => {
    const existing = [...discovered.values()].find(x => x.provider === choice.provider);
    if (existing) {
      // Prefer EIP-6963 metadata when the same provider also appears as legacy injection.
      if (existing.source === "legacy injection" && choice.source === "EIP-6963") {
        discovered.set(existing.id, { ...choice, id: existing.id });
        publish();
      }
      return;
    }
    // A second provider must never replace one already selected by ID.
    if (discovered.has(choice.id)) return;
    discovered.set(choice.id, choice);
    publish();
  };
  const onAnnounce = (event: Event) => {
    const detail = (event as CustomEvent<Announcement>).detail;
    if (typeof detail?.provider?.request !== "function" ||
        typeof detail.info?.uuid !== "string" || !detail.info.uuid || detail.info.uuid.length > 128 ||
        typeof detail.info?.name !== "string" || !detail.info.name.trim() || detail.info.name.length > 100 ||
        typeof detail.info?.rdns !== "string" || detail.info.rdns.length > 200) return;
    add({ id: "eip6963:" + detail.info.uuid, name: detail.info.name,
      rdns: detail.info.rdns, source: "EIP-6963", provider: detail.provider });
  };
  window.addEventListener("eip6963:announceProvider", onAnnounce);
  window.dispatchEvent(new Event("eip6963:requestProvider"));
  const injected = (window as Window & {
    ethereum?: Provider; okxwallet?: { ethereum?: Provider };
  });
  const legacy = injected.ethereum?.providers?.length
    ? injected.ethereum.providers : injected.ethereum ? [injected.ethereum] : [];
  for (const provider of legacy) {
    if (typeof provider?.request !== "function") continue;
    const name = provider.isOkxWallet || provider.isOKExWallet ? "OKX Wallet"
      : provider.isMetaMask ? "MetaMask" : "EVM Wallet";
    add({ id: "legacy-" + discovered.size, name, source: "legacy injection", provider });
  }
  if (injected.okxwallet?.ethereum)
    add({ id: "legacy-okx", name: "OKX Wallet", source: "legacy injection",
      provider: injected.okxwallet.ethereum });
  return () => window.removeEventListener("eip6963:announceProvider", onAnnounce);
}

export async function walletChainId(provider: Provider): Promise<number> {
  const value = await provider.request({ method: "eth_chainId" });
  if (typeof value !== "string" || !/^0x[\da-f]+$/i.test(value))
    throw new Error("钱包未返回有效 Chain ID");
  const chainId = Number.parseInt(value, 16);
  if (!Number.isSafeInteger(chainId)) throw new Error("钱包返回的 Chain ID 超出安全范围");
  return chainId;
}
export async function walletAccounts(provider: Provider): Promise<string[]> {
  const accounts = await provider.request({ method: "eth_accounts" });
  return Array.isArray(accounts) ? accounts.filter(x => typeof x === "string") : [];
}
export function friendlyWalletError(error: unknown): string {
  const value = error as { code?: number; message?: string };
  if (value?.code === 4001) return "已取消钱包授权或网络切换。";
  if (value?.code === -32002) return "钱包中已有待处理请求，请先处理。";
  return value?.message || "钱包操作失败，请检查扩展或网络。";
}
export async function switchToBot(provider: Provider): Promise<void> {
  try {
    await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: "0x2a5" }] });
  } catch (error) {
    if ((error as { code?: number })?.code !== 4902) throw error;
    const { botChainAddParams } = await import("./chain");
    await provider.request({ method: "wallet_addEthereumChain", params: [botChainAddParams] });
    await provider.request({ method: "wallet_switchEthereumChain", params: [{ chainId: "0x2a5" }] });
  }
  if (await walletChainId(provider) !== 677)
    throw new Error("钱包切换后仍未返回 BOT Chain ID 677");
}
