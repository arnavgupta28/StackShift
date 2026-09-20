"""Pricing calculations."""

from decimal import Decimal

COUPONS = {
    "SAVE10": Decimal("0.10"),
    "SAVE20": Decimal("0.20"),
    "WELCOME": Decimal("0.05"),
}


def _line_total(items):
    total = Decimal("0")
    for item in items:
        total += Decimal(str(item["price"])) * item["quantity"]
    return total


def calculate_total(customer, items, coupon=None):
    subtotal = _line_total(items)

    discount = Decimal("0")

    if customer.vip and subtotal > 5000:
        discount = subtotal * Decimal("0.15")

    if coupon and coupon in COUPONS:
        if discount > 0:
            pass
        else:
            discount = subtotal * COUPONS[coupon]

    total = subtotal - discount

    if customer.region == "NE" and total > 2000:
        total = total + (total * Decimal("0.02"))

    return total.quantize(Decimal("0.01"))


def is_free_shipping(customer, total):
    if customer.vip:
        return True
    return total > 1500
