"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { getAddress, isAddress, type Address } from "viem";
import { collectWallets, friendlyWalletError, switchToBot, walletAccounts,
  walletChainId, type Provider, type WalletChoice } from "./wallet";

export function useWalletConnection() {
  const [wallets, setWallets] = useState<WalletChoice[]>([]);
  const [choiceId, setChoiceId] = useState("");
  const [provider, setProvider] = useState<Provider | null>(null);
  const [address, setAddress] = useState<Address | null>(null);
  const [chainId, setChainId] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  useEffect(() => collectWallets(setWallets), []);
  const selected = useMemo(() => wallets.find(wallet => wallet.id === choiceId) || null,
    [wallets, choiceId]);
  const refresh = useCallback(async (active: Provider) => {
    const [accounts, chain] = await Promise.all([walletAccounts(active), walletChainId(active)]);
    setAddress(accounts[0] && isAddress(accounts[0]) ? getAddress(accounts[0]) : null);
    setChainId(chain);
  }, []);
  useEffect(() => {
    if (!provider) return;
    const changed = () => void refresh(provider).catch(error => {
      setAddress(null); setChainId(null); setError(friendlyWalletError(error));
    });
    const disconnected = () => { setAddress(null); setChainId(null); setProvider(null); };
    provider.on?.("accountsChanged", changed);
    provider.on?.("chainChanged", changed);
    provider.on?.("disconnect", disconnected);
    return () => {
      provider.removeListener?.("accountsChanged", changed);
      provider.removeListener?.("chainChanged", changed);
      provider.removeListener?.("disconnect", disconnected);
    };
  }, [provider, refresh]);
  const connect = async () => {
    if (!selected || busy) return;
    setBusy(true); setError("");
    try {
      const accounts = await selected.provider.request({ method: "eth_requestAccounts" });
      if (!Array.isArray(accounts) || !accounts[0] || !isAddress(accounts[0]))
        throw new Error("钱包未返回有效账户");
      setProvider(selected.provider);
      await refresh(selected.provider);
    } catch (error) { setError(friendlyWalletError(error)); }
    finally { setBusy(false); }
  };
  const switchNetwork = async () => {
    if (!provider || busy) return;
    setBusy(true); setError("");
    try { await switchToBot(provider); await refresh(provider); }
    catch (error) { setError(friendlyWalletError(error)); }
    finally { setBusy(false); }
  };
  const disconnect = () => { setProvider(null); setAddress(null); setChainId(null); setError(""); };
  return { wallets, choiceId, setChoiceId, selected, provider, address, chainId,
    busy, error, connect, switchNetwork, disconnect };
}
