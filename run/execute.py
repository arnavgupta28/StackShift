#!/usr/bin/env python3
"""Run the Execution agent against the approved migration plan.

    python3 run/execute.py           run the approved tier
    python3 run/execute.py --force   run without approval (to show the denial)

Without an approval the workspace is mounted read-only and every write fails.
That is the point: run this before approving and watch it be refused.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from approve import mount_mode, read_approval  # noqa: E402
from fleet import WORKSPACE, ask_expecting  # noqa: E402

PROMPT = """\
Execute the approved migration plan.

Read migration_plan.json, behavior_contract.json and assessment.json with
read_artifact first. You are migrating ONLY the approved tier: %s.

Write the migrated application under migrated/. Never modify anything under
legacy/ -- it is the reference the migration is validated against.

Target: FastAPI + PostgreSQL (psycopg) + Docker, Python 3.12.

Produce at minimum:
  migrated/app.py               FastAPI app with the same routes as legacy/app.py
  migrated/services/pricing.py  the pricing rules, behaviour preserved exactly
  migrated/services/orders.py   order orchestration
  migrated/repositories/order_repo.py   data access, PostgreSQL dialect
  migrated/schema.sql           the PostgreSQL schema
  migrated/tests/behavior/test_rules.py  one test per rule in the contract,
                                each docstring citing the legacy source line

Every rule in behavior_contract.json must survive. Where the legacy code looks
odd, preserve its effect and add a comment citing the legacy line. Then write
execution_report.json.
"""


def main():
    force = "--force" in sys.argv
    approval = read_approval()

    print()
    print("  EXECUTION")
    print("  " + "-" * 56)
    mode = mount_mode("ss-execution")
    print("  workspace mount : %s" % mode)

    if not approval and not force:
        print("  approval        : NONE")
        print()
        print("  Refusing to run: no tier has been approved.")
        print("  Approve one first:   python3 run/approve.py --tier 1")
        print("  Or run anyway to see the control plane refuse the writes:")
        print("                       python3 run/execute.py --force")
        print()
        return 1

    tier = approval["tier"] if approval else "1 (UNAPPROVED)"
    print("  approved tier   : %s" % tier)
    if not approval:
        print()
        print("  No approval on record. The workspace is read-only, so the")
        print("  agent's writes are expected to fail. This is the demo.")
    print()

    began = time.time()
    result = ask_expecting("execution",
                           PROMPT % tier,
                           ["execution_report.json"],
                           attempts=1)
    print()
    if not result["ok"]:
        print("  ERROR: %s\n" % result["error"])
        return 1

    print(result["text"][:2000])
    print()
    written = []
    root = os.path.join(WORKSPACE, "migrated")
    for dirpath, _, files in os.walk(root):
        for name in files:
            written.append(os.path.relpath(os.path.join(dirpath, name), WORKSPACE))

    print("  " + "-" * 56)
    print("  %ds, %d file(s) under migrated/" % (int(time.time() - began), len(written)))
    for path in sorted(written)[:25]:
        print("    %s" % path)
    print()
    if not written:
        print("  NO FILES WRITTEN — the workspace is %s." % mode)
        print("  The agent was not refused by a prompt or an if-statement; the")
        print("  write failed because it does not have the capability.")
        print()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
