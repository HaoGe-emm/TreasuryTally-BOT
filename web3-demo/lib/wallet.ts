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
    if (![...discovered.values()].some(x => x.provider === choice.provider)) {
      discovered.set(choice.id, choice);
      publish();
    }
  };
  const onAnnounce = (event: Event) => {
    const detail = (event as CustomEvent<Announcement>).detail;
    if (!detail?.provider?.request || !detail.info?.uuid) return;
    add({ id: detail.info.uuid, name: detail.info.name, rdns: detail.info.rdns, provider: detail.provider });
  };
  window.addEventListener("eip6963:announceProvider", onAnnounce);
  window.dispatchEvent(new Event("eip6963:requestProvider"));
  const injected = (window as Window & {
    ethereum?: Provider; okxwallet?: { ethereum?: Provider };
  });
  const legacy = injected.ethereum?.providers?.length
    ? injected.ethereum.providers : injected.ethereum ? [injected.ethereum] : [];
  for (const provider of legacy) {
    const name = provider.isOkxWallet || provider.isOKExWallet ? "OKX Wallet"
      : provider.isMetaMask ? "MetaMask" : "EVM Wallet";
    add({ id: "legacy-" + name + "-" + discovered.size, name, provider });
  }
  if (injected.okxwallet?.ethereum)
    add({ id: "legacy-okx", name: "OKX Wallet", provider: injected.okxwallet.ethereum });
  return () => window.removeEventListener("eip6963:announceProvider", onAnnounce);
}

export async function walletChainId(provider: Provider): Promise<number> {
  const value = await provider.request({ method: "eth_chainId" });
  if (typeof value !== "string" || !/^0x[\da-f]+$/i.test(value))
    throw new Error("钱包未返回有效 Chain ID");
  return Number.parseInt(value, 16);
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
}
