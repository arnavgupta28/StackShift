#!/usr/bin/env python3
"""Run the discovery -> assessment -> planning spine.

    python3 run/spine.py                 run all three
    python3 run/spine.py --from planning re-run from one step

This is the read-only half of a migration. Nothing here can touch source code:
all three agents hold read and artifact tools only. At the end you have a plan
and three costed tiers, and a human decides whether anything happens next.

Deployed on Nasiko this is a MAF workflow. MAF is strictly linear, which suits
these three steps exactly — each one consumes the previous one's artifact. The
repair loop that comes later cannot be expressed this way and runs over direct
A2A instead; see docs/02-architecture.md.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleet import WORKSPACE, artifacts, ask_expecting  # noqa: E402

AIM = (
    "Python 3.8 goes EOL in March and we fail the security audit. We need off "
    "Flask and MySQL without a redesign. The team is 4 people."
)

STEPS = [
    {
        "agent": "discovery",
        "label": "Discovery",
        "expect": ["system_map.json", "behavior_contract.json"],
        "prompt": (
            "Analyse the legacy Flask application under legacy/ in your workspace.\n\n"
            "Read EVERY file under legacy/services/ and legacy/repositories/ before "
            "you conclude anything, plus legacy/app.py, legacy/schema.sql and "
            "legacy/config.py. Do not sample.\n\n"
            "Then write system_map.json and behavior_contract.json with "
            "write_artifact, in the shape your instructions specify.\n\n"
            "Pay particular attention to rules a rewrite would silently destroy: "
            "empty branches, thresholds in conditionals, retry limits, and SQL "
            "ordering on nullable columns."
        ),
    },
    {
        "agent": "assessment",
        "label": "Assessment",
        "expect": ["assessment.json"],
        "prompt": (
            "Read system_map.json and behavior_contract.json with read_artifact.\n\n"
            "Then read legacy/schema.sql and legacy/repositories/order_repo.py "
            "directly.\n\n"
            "Score every module for migration complexity and risk, and profile the "
            "schema for genuine MySQL-to-PostgreSQL behavioural differences — not "
            "syntax differences. Write assessment.json with write_artifact."
        ),
    },
    {
        "agent": "planning",
        "label": "Planning",
        "expect": ["migration_plan.json"],
        "prompt": (
            "Read system_map.json, behavior_contract.json and assessment.json with "
            "read_artifact.\n\n"
            "The user's stated aim is:\n\n    %s\n\n"
            "Produce a phased migration plan from Flask+MySQL+Celery to "
            "FastAPI+PostgreSQL+Docker, with exactly three costed tiers "
            "(Refresh, Restructure, Re-architect).\n\n"
            "Recommend a tier based on the AIM above, not on repository size. "
            "Flag every phase that touches a rule from the behavior contract and "
            "say where you expect regressions. Write migration_plan.json with "
            "write_artifact." % AIM
        ),
    },
]


def main():
    args = sys.argv[1:]
    start = 0
    if "--from" in args:
        name = args[args.index("--from") + 1]
        names = [s["agent"] for s in STEPS]
        if name not in names:
            sys.exit("unknown step %r; choose from %s" % (name, ", ".join(names)))
        start = names.index(name)

    print("\n  MIGRATION SPINE  (read-only: no agent here can write source)")
    print("  " + "-" * 62)
    began = time.time()
    failures = 0

    for step in STEPS[start:]:
        print("\n  %s ..." % step["label"])
        result = ask_expecting(step["agent"], step["prompt"], step["expect"])
        if not result["ok"]:
            print("    FAILED: %s" % result["error"])
            failures += 1
            break
        if result.get("missing"):
            print("    INCOMPLETE: never wrote %s" % ", ".join(result["missing"]))
            failures += 1
            break
        print("    done in %ss -> %s" % (result["seconds"], ", ".join(step["expect"])))

    print("\n  " + "-" * 62)
    print("  artifacts: %s" % ", ".join(artifacts()))
    print("  total: %ds" % int(time.time() - began))
    print("  workspace: %s" % os.path.relpath(WORKSPACE))
    print()
    if failures:
        print("  SPINE INCOMPLETE\n")
        return 1
    print("  Spine complete. A human now picks a tier -- nothing has been")
    print("  written to source, and Execution holds no write grant yet.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
