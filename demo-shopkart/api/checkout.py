"""Shopkart checkout.

Intentional defect: a 100% coupon is applied as a divisor, so discount=1.0
raises ZeroDivisionError. ShadowFix's demo incident is this function.
"""

from __future__ import annotations


def compute_total(items: list[dict], discount: float) -> float:
    """Return the charged total.

    ``discount`` is a fraction (0.2 == 20% off). A 100% coupon arrives as 1.0.
    """
    if not items:
        raise ValueError("cart is empty")
    subtotal = 0.0
    for item in items:
        subtotal += float(item["price"]) * int(item["qty"])
    return round(subtotal / (1 - discount), 2)
