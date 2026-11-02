"""Shopkart checkout.

Discounts are applied as a multiplier, never as a divisor. A 100% coupon must
produce a zero total instead of dividing by zero.
"""

from __future__ import annotations

import math


def compute_total(items: list[dict], discount: float) -> float:
    """Return the charged total.

    ``discount`` is a fraction (0.2 == 20% off). A 100% coupon arrives as 1.0.
    """
    if not items:
        raise ValueError("cart is empty")

    discount_value = float(discount)
    if not math.isfinite(discount_value):
        raise ValueError("discount must be a finite number")
    if discount_value < 0 or discount_value > 1:
        raise ValueError("discount must be between 0 and 1")

    subtotal = 0.0
    for item in items:
        subtotal += float(item["price"]) * int(item["qty"])
    return round(subtotal * (1 - discount_value), 2)
