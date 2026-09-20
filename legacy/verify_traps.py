#!/usr/bin/env python3
"""Verify the three planted traps are still real.

Run this whenever you touch the legacy app. If a trap breaks while you are
debugging something else, the demo loses its point. T3 especially: it is what
triggers the repair loop.

    python3 legacy/verify_traps.py
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
APP = os.path.join(HERE, "acme-orders")
sys.path.insert(0, APP)


def check_t1():
    from services import pricing

    class C:
        def __init__(self, vip, region="W"):
            self.vip, self.region = vip, region

    items = [{"price": "7200", "quantity": 1}]
    vip_plain = pricing.calculate_total(C(True), items)
    vip_coupon = pricing.calculate_total(C(True), items, "SAVE10")
    reg_coupon = pricing.calculate_total(C(False), items, "SAVE10")

    assert str(vip_plain) == "6120.00", "VIP discount rule changed: %s" % vip_plain
    assert vip_plain == vip_coupon, "coupon is no longer swallowed for VIP"
    assert reg_coupon != vip_coupon, "coupon no longer applies to non-VIP"
    return "VIP=%s  VIP+coupon=%s (ignored)  nonVIP+coupon=%s" % (
        vip_plain, vip_coupon, reg_coupon)


def check_t2():
    api = open(os.path.join(APP, "app.py")).read()
    svc = open(os.path.join(APP, "services", "orders.py")).read()
    assert "reserve_stock" not in api, "dependency is now visible from the API layer"
    assert "reserve_stock" in svc, "orders.py no longer calls inventory"
    return "inventory.reserve_stock hidden from app.py, called in services/orders.py"


def check_t3():
    """Confirm PostgreSQL orders NULLs last, opposite to MySQL."""
    sql = (
        "CREATE TEMP TABLE t(sku text, quantity int);"
        "INSERT INTO t VALUES ('DISCONTINUED-1',NULL),('WIDGET-A',3),('WIDGET-B',50);"
        "SELECT sku FROM t ORDER BY quantity ASC LIMIT 1;"
    )
    try:
        out = subprocess.check_output(
            ["docker", "exec", "nasiko-postgres-1", "psql", "-U", "nasiko",
             "-d", "postgres", "-t", "-A", "-c", sql],
            stderr=subprocess.STDOUT, timeout=30).decode()
    except Exception as exc:
        return "SKIPPED (postgres unavailable: %s)" % str(exc).split("\n")[0]

    first = [l for l in out.strip().split("\n") if l.strip()][-1].strip()
    assert first == "WIDGET-A", "postgres returned %r, expected WIDGET-A" % first
    return ("postgres ORDER BY quantity ASC -> %s (MySQL would return "
            "DISCONTINUED-1). Reorder report breaks silently." % first)


CHECKS = [
    ("T1", "undocumented pricing rules", check_t1),
    ("T2", "hidden InventoryService dependency", check_t2),
    ("T3", "NULL ordering differs MySQL vs Postgres", check_t3),
]


def main():
    failures = 0
    print()
    for tid, desc, fn in CHECKS:
        try:
            detail = fn()
            status = "SKIP" if detail.startswith("SKIPPED") else "OK"
        except AssertionError as exc:
            detail, status, failures = str(exc), "FAIL", failures + 1
        print("  [%s] %s - %s" % (status, tid, desc))
        print("         %s" % detail)
    print()
    print("  %d/%d traps intact" % (len(CHECKS) - failures, len(CHECKS)))
    print()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
