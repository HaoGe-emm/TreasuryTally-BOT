"use client";

import { useWalletConnection } from "@/lib/use-wallet";
import CopyButton from "./CopyButton";

type WalletState = ReturnType<typeof useWalletConnection>;
export default function WalletPanel({ wallet }: { wallet: WalletState }) {
  return <div className="wallet-panel">
    {wallet.wallets.length ? <label>选择钱包
      <select value={wallet.choiceId} disabled={wallet.busy || !!wallet.address}
        onChange={event => wallet.setChoiceId(event.target.value)}>
        <option value="">请选择钱包</option>
        {wallet.wallets.map(item => <option key={item.id} value={item.id}>
          {item.name} · {item.source}{item.rdns ? ` · ${item.rdns}` : ""}
        </option>)}
      </select>
    </label> : <p className="empty">未发现 EVM 钱包。请安装 MetaMask、OKX Wallet，或使用钱包内置浏览器。</p>}
    <div className="actions">
      {wallet.address ? <button className="secondary" onClick={wallet.disconnect}>断开页面连接</button>
        : <button disabled={!wallet.selected || wallet.busy} onClick={wallet.connect}>Connect Wallet</button>}
      {wallet.address && wallet.chainId !== 677 && <button disabled={wallet.busy}
        onClick={wallet.switchNetwork}>切换到 BOT Chain 677</button>}
    </div>
    <dl className="facts">
      <div><dt>当前钱包</dt><dd>{wallet.address || "尚未连接"} {wallet.address &&
        <CopyButton value={wallet.address} label="复制当前钱包地址" />}</dd></div>
      <div><dt>钱包 Chain ID</dt><dd>{wallet.chainId ?? "—"}</dd></div>
    </dl>
    {wallet.error && <p className="warning" role="status">{wallet.error}</p>}
    <p className="muted">连接和切换网络只由你点击触发；钱包名称由扩展声明，请核对实际钱包弹窗。</p>
  </div>;
}
