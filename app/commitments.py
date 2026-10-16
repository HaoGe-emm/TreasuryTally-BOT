"""Presentation-only helpers for M8 commitments."""

from __future__ import annotations

import streamlit as st

from trust_receipt.commitments import verify_delivery_commitment, verify_task_commitment


def render_commitments(task, task_commitment, delivery_commitment, submission, expected_signer, anchor_status) -> None:
    with st.expander("任务、接单与交付承诺", expanded=False):
        if task_commitment is None:
            st.caption("开始核验时才会为选定服务形成 EIP-712 任务承诺。")
            return
        task_valid = verify_task_commitment(task_commitment, task)
        st.write(f"任务承诺签名：{'有效' if task_valid else '无效'}")
        st.caption("任务签名使用本地临时 requester 密钥，不是 Reviewer 钱包，也不证明真实委托方身份。")
        st.code(task_commitment.spec_hash, language=None)
        st.caption(anchor_status)
        st.write(f"锚定状态：`{task_commitment.anchor.status.value}`")
        if delivery_commitment is None or submission is None:
            st.caption("服务尚未接单并提交报告。")
            return
        delivery_valid = verify_delivery_commitment(
            delivery_commitment,
            task_commitment,
            submission,
            expected_signer=expected_signer,
        )
        st.write(f"服务接单签名：{'有效' if delivery_valid else '无效'}")
        st.write(f"报告交付签名：{'有效' if delivery_valid else '无效'}")
        st.code(delivery_commitment.report_hash, language=None)
        st.caption("签名只证明承诺者与内容绑定；`NOT_SUBMITTED` 不表示已经上链。")
