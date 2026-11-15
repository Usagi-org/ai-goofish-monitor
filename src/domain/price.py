"""Numeric prices used for comparisons, statistics and storage."""
import math


def parse_price_value(value: object) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip().replace("¥", "").replace(",", "")
    multiplier = 10000 if text.endswith("万") else 1
    try:
        price = float(text.removesuffix("万")) * multiplier
    except ValueError:
        return None
    return round(price, 2) if math.isfinite(price) else None
