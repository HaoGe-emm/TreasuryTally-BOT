"use client";

import { useState } from "react";

export default function CopyButton({ value, label }: { value: string; label: string }) {
  const [status, setStatus] = useState("");
  async function copy() {
    try { await navigator.clipboard.writeText(value); setStatus("已复制"); }
    catch { setStatus("复制失败，请手动选择"); }
  }
  return <span className="copy-control"><button className="copy-button secondary" type="button"
    aria-label={label} onClick={() => void copy()}>复制</button>
    <span className="copy-status" role="status">{status}</span></span>;
}
