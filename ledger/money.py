"""Amount parsing and formatting. All stored amounts are integer cents."""
from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

MAX_CENTS = 999_999_999  # 9,999,999.99 yuan
_AMOUNT_RE = re.compile(r"^\d{1,9}(\.\d{1,2})?$")


def parse_amount(text):
    """Parse user input into cents. Raises ValueError with a friendly message."""
    if text is None:
        raise ValueError("请输入金额")
    cleaned = str(text).strip().replace(" ", "").replace(",", "").replace("，", "")
    cleaned = cleaned.replace("¥", "").replace("￥", "")
    if not cleaned:
        raise ValueError("请输入金额")
    if cleaned.startswith("-"):
        raise ValueError("金额必须大于 0")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if not _AMOUNT_RE.match(cleaned):
        raise ValueError("金额格式不正确，最多两位小数")
    try:
        value = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError("金额格式不正确") from None
    cents = int((value * 100).to_integral_value(rounding=ROUND_HALF_UP))
    if cents <= 0:
        raise ValueError("金额必须大于 0")
    if cents > MAX_CENTS:
        raise ValueError("金额太大，单笔不能超过 9,999,999.99")
    return cents


def format_cents(cents, symbol="¥"):
    cents = int(cents or 0)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    yuan, fraction = divmod(cents, 100)
    return "%s%s%s.%02d" % (sign, symbol, format(yuan, ","), fraction)


def format_plain(cents):
    cents = int(cents or 0)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    yuan, fraction = divmod(cents, 100)
    return "%s%d.%02d" % (sign, yuan, fraction)


def format_compact(cents):
    """Compact yuan amount used by chart axes."""
    cents = int(cents or 0)
    if cents >= 100_000_000:  # 1,000,000 yuan
        return "¥%.0f万" % (cents / 10_000_000.0)
    if cents >= 1_000_000:  # 10,000 yuan
        return "¥%.1f万" % (cents / 1_000_000.0)
    yuan = cents / 100.0
    if yuan >= 1000:
        return "¥%.0f" % yuan
    if yuan >= 10:
        return "¥%.0f" % yuan
    if yuan >= 1:
        return "¥%.1f" % yuan
    return "¥%.2f" % yuan


def format_signed(cents, kind):
    prefix = "-" if kind == "expense" else "+"
    return prefix + format_cents(cents)
