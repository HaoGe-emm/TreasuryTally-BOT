"""Lossless formatting: integer arithmetic only, no rounding or float money."""

import re

from trust_receipt.reporting.models import AddressView, AmountView


def address_view(address: str) -> AddressView:
    return AddressView(full=address, short=f"{address[:8]}...{address[-6:]}")


def format_amount(base_units: str, decimals: int | None, *, signed: bool = False) -> AmountView:
    pattern = r"^-?(0|[1-9][0-9]*)$" if signed else r"^(0|[1-9][0-9]*)$"
    if not re.fullmatch(pattern, base_units) or base_units == "-0":
        raise ValueError("amount must be a canonical integer string")
    if decimals is not None and (type(decimals) is not int or not 0 <= decimals <= 255):
        raise ValueError("decimals must be an integer between 0 and 255")
    sign = "-" if base_units.startswith("-") else ""
    digits = base_units.removeprefix("-")
    if decimals is None or decimals == 0:
        display = sign + f"{int(digits):,}"
    else:
        padded = digits.zfill(decimals + 1)
        whole, fraction = padded[:-decimals], padded[-decimals:].rstrip("0")
        display = sign + f"{int(whole):,}" + ("." + fraction if fraction else "")
    return AmountView(
        base_units=base_units,
        display=display,
        unit="代币" if decimals is not None else "最小单位",
        decimals=decimals,
    )
