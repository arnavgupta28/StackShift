#!/usr/bin/env python3
"""Independent behavioural parity check.

    python3 run/parity.py

This does not ask any agent whether the migration worked. It imports the legacy
and migrated pricing modules side by side, runs the same inputs through both,
and compares the answers.

That matters because every other signal in the pipeline is ultimately the
fleet's own account of itself: the Validation agent reads the migrated code and
reports on it. Useful, but it is a model marking its own homework. This is the
one check that would catch the whole fleet being confidently wrong.

Exit code is non-zero if any case differs.
"""

import importlib.util
import os
import sys
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.join(ROOT, ".runs", "demo", "workspace")


class Customer:
    def __init__(self, vip=False, region="W"):
        self.vip = vip
        self.region = region


# (label, vip, region, items, coupon)
CASES = [
    ("BEH-001 VIP over 5000",        True,  "W",  [("7200", 1)], None),
    ("BEH-002 VIP + coupon",         True,  "W",  [("7200", 1)], "SAVE10"),
    ("BEH-003 non-VIP + coupon",     False, "W",  [("7200", 1)], "SAVE10"),
    ("BEH-004 NE surcharge",         False, "NE", [("3000", 1)], None),
    ("        VIP under 5000",       True,  "W",  [("4000", 1)], None),
    ("        VIP under 5000+coupon", True, "W",  [("4000", 1)], "SAVE20"),
    ("        non-VIP no coupon",    False, "W",  [("1200", 2)], None),
    ("        NE under 2000",        False, "NE", [("1500", 1)], None),
    ("        VIP + NE + coupon",    True,  "NE", [("9000", 1)], "WELCOME"),
    ("        unknown coupon",       False, "W",  [("2500", 1)], "BOGUS"),
]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def main():
    legacy_path = os.path.join(WORKSPACE, "legacy", "services", "pricing.py")
    migrated_path = os.path.join(WORKSPACE, "migrated", "services", "pricing.py")

    for path in (legacy_path, migrated_path):
        if not os.path.isfile(path):
            sys.exit("missing %s — run the migration first" % os.path.relpath(path, ROOT))

    try:
        legacy = load(legacy_path, "legacy_pricing")
        migrated = load(migrated_path, "migrated_pricing")
    except Exception as exc:
        sys.exit("could not import both modules: %s: %s" % (type(exc).__name__, exc))

    print()
    print("  BEHAVIOURAL PARITY — legacy vs migrated, run side by side")
    print("  " + "=" * 66)
    print("  %-30s %12s %12s   %s" % ("case", "legacy", "migrated", ""))
    print("  " + "-" * 66)

    failures = 0
    errors = 0
    for label, vip, region, items, coupon in CASES:
        payload = [{"price": p, "quantity": q} for p, q in items]
        customer = Customer(vip=vip, region=region)

        def call(mod):
            return mod.calculate_total(customer, [dict(i) for i in payload], coupon)

        try:
            want = call(legacy)
        except Exception as exc:
            print("  %-30s %12s %12s   LEGACY ERROR %s" % (label, "-", "-", exc))
            errors += 1
            continue
        try:
            got = call(migrated)
        except Exception as exc:
            print("  %-30s %12s %12s   MIGRATED ERROR %s"
                  % (label, want, "-", type(exc).__name__))
            errors += 1
            continue

        same = Decimal(str(want)) == Decimal(str(got))
        mark = "match" if same else "DIFFERS  <-- regression"
        if not same:
            failures += 1
        print("  %-30s %12s %12s   %s" % (label, want, got, mark))

    print("  " + "=" * 66)
    total = len(CASES)
    passed = total - failures - errors
    print("  %d/%d cases match" % (passed, total))
    if errors:
        print("  %d case(s) errored" % errors)
    if failures:
        print("  %d BEHAVIOURAL REGRESSION(S)" % failures)
    print()
    if failures or errors:
        print("  These are real differences between the two implementations,")
        print("  measured by running both. No agent was asked for an opinion.")
        print()
        return 1
    print("  The migrated pricing module is behaviourally identical to the")
    print("  legacy one across every case, including the rules that were")
    print("  documented nowhere.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
