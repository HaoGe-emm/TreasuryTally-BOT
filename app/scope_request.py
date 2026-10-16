"""Editable scope scaffolding, not facts, authorization, or a model prompt."""

import re

GUIDED = "按模板填写范围"
RAW = "直接写说明"
TEMPLATE = """网络/链编号：[填写网络或链编号]
代币地址：[填写代币合约地址]
报表声明精度（不知道可留空）：
付款账户：[填写付款地址，最多两个]
收款账户：[填写收款地址]
起始区块（含）：[填写起始区块]
结束区块（含）：[填写结束区块]
排除规则：[填写要排除的规则，或明确写不排除]
记录上限：200"""
REQUIRED_FIELDS = (
    "网络/链编号", "代币地址", "付款账户", "收款账户",
    "起始区块（含）", "结束区块（含）", "排除规则", "记录上限",
)
_PLACEHOLDER = re.compile(r"\[(?:填写|选择)[^\]]*\]")


def has_placeholders(request: str) -> bool:
    return bool(_PLACEHOLDER.search(request))


def preserve_scope_inputs(state):
    """Prevent widget cleanup from discarding inputs when another path is shown."""
    for key in ("scope-request", "scope-request-mode", "scope-example-request"):
        if key in state:
            state[key] = state[key]


def request_ready(request: str, mode: str = RAW) -> bool:
    if not request.strip() or has_placeholders(request):
        return False
    if mode == RAW:
        return True
    fields = {}
    for line in request.splitlines():
        parts = re.split(r"[：:]", line, maxsplit=1)
        if len(parts) == 2 and parts[0].strip() in REQUIRED_FIELDS:
            key, value = (part.strip() for part in parts)
            if key in fields:
                return False
            fields[key] = value
    return all(fields.get(key) for key in REQUIRED_FIELDS) and fields["记录上限"] == "200"


def render_scope_request(st):
    state = st.session_state
    if "scope-request-mode" not in state:
        state["scope-request-mode"] = RAW if state.get("scope-request", "") else GUIDED
    if not state.get("scope-request-initialized"):
        if state["scope-request-mode"] == GUIDED and not state.get("scope-request", ""):
            state["scope-request"] = TEMPLATE
        state["scope-request-initialized"] = True
    mode = st.radio("范围填写方式", (GUIDED, RAW), key="scope-request-mode", horizontal=True)
    request = st.text_area(
        "说明要核对的范围", value=None, key="scope-request", height=245 if mode == GUIDED else 130,
        placeholder="说明网络、代币、付款与收款账户、起止区块和排除规则。",
    ) or ""
    ready = request_ready(request, mode)
    if mode == GUIDED and not ready:
        st.caption("请补齐模板中的范围；报表声明精度不知道可留空。")
    return request, ready
