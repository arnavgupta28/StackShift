#!/usr/bin/env python3
"""Validate the migrated code, and run the repair loop.

    python3 run/validate.py              validate once
    python3 run/validate.py --repair     validate, then repair and re-validate
    python3 run/validate.py --repair --max-attempts 3

The repair loop is Validation -> Execution -> Validation over direct A2A calls.
It is NOT a MAF workflow: MAF is strictly linear (MafDefinition.steps is a Vec
and the executor is a flat for-loop), so it cannot express a back-edge. See
docs/02-architecture.md.

Because it is a loop with a model in it, it is bounded. The caps below mirror
Nasiko's flow guards, which enforce the same limits on A2A hops once the fleet
is deployed to the control plane:

    NASIKO_FLOW_MAX_DEPTH      how deep a call chain may go
    NASIKO_FLOW_MAX_FAN_OUT    how wide
    NASIKO_FLOW_TIMEOUT_SECS   wall clock
    NASIKO_FLOW_MAX_TOKENS     spend

Hitting the cap is a success, not a failure. It is the difference between a
system that repairs itself and one that bills you all night.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleet import WORKSPACE, ask, ask_expecting  # noqa: E402

ARTIFACTS = os.path.join(WORKSPACE, ".stackshift")
REPORT = os.path.join(ARTIFACTS, "validation_report.json")

# Mirrors NASIKO_FLOW_MAX_DEPTH. The control plane enforces this on A2A hops;
# here the harness does, so the local run behaves like the deployed one.
MAX_ATTEMPTS = 3

VALIDATE_PROMPT = """\
Validate the migrated application against the legacy one.

Read behavior_contract.json and execution_report.json with read_artifact.
Then list migrated/ and read every file you find there, and compare it against
the corresponding file under legacy/.

Check three things, in this order:

1. COMPLETENESS. Does migrated/ contain a counterpart for every module in
   legacy/? List anything missing. An absent file is a regression.
2. BEHAVIOUR. For each rule in behavior_contract.json, read the migrated
   implementation and decide whether the rule still holds. Cite the migrated
   file:line you checked. Do not assume a rule survived because a file exists.
3. TESTS. Run any tests under migrated/ with run_command and report failures.

Write validation_report.json. Its `evidence` block must contain counts you
actually measured, because a deterministic scorer consumes them. Never report a
readiness percentage yourself.

For each regression give a `diagnosis` naming the specific cause, and a
`suggested_fix` the Execution agent can act on without guessing.
"""

REPAIR_PROMPT = """\
The Validation agent found regressions in your migration. Read
validation_report.json with read_artifact.

Fix ONLY what it reports. Do not refactor anything else while you are in here:
a repair that also changes three other things cannot be verified.

For each regression, apply the suggested fix, preserving the rule exactly as
behavior_contract.json states it. Then update execution_report.json with what
you changed.

This is repair attempt %d of %d.
"""


def load_report():
    if not os.path.isfile(REPORT):
        return None
    try:
        with open(REPORT) as fh:
            return json.load(fh)
    except ValueError:
        return None


def contract_rule_count():
    path = os.path.join(ARTIFACTS, "behavior_contract.json")
    if not os.path.isfile(path):
        return 0
    try:
        with open(path) as fh:
            return len(json.load(fh).get("rules", []))
    except ValueError:
        return 0


def reject_hollow(report):
    """Refuse a report that checked nothing.

    The agent's first run returned a correctly-shaped report with every count
    zero and no regressions — which reads as "migration is perfect". A clean
    bill of health backed by no measurement is the most dangerous output this
    system could produce, so it is rejected rather than displayed.
    """
    expected = contract_rule_count()
    checked = report.get("rules_checked") or 0
    if expected and checked == 0:
        return ("reports 0 rules checked, but behavior_contract.json has %d. "
                "Check each rule against the migrated code." % expected)

    evidence = report.get("evidence") or {}
    if not evidence:
        return "has no evidence block"
    if all((evidence.get(k) or 0) == 0 for k in evidence if k != "context_linked"):
        return "has an all-zero evidence block; report counts you measured"

    migrated = os.path.join(WORKSPACE, "migrated")
    files = sum(len(f) for _, _, f in os.walk(migrated)) if os.path.isdir(migrated) else 0
    legacy = os.path.join(WORKSPACE, "legacy")
    legacy_files = sum(len(f) for _, _, f in os.walk(legacy)) if os.path.isdir(legacy) else 0
    if legacy_files and files < legacy_files * 0.6 and not report.get("regressions"):
        return ("reports no regressions, but migrated/ has %d files against "
                "legacy/'s %d. Missing modules are regressions — list them."
                % (files, legacy_files))
    return None


def summarise(report, attempt):
    regressions = report.get("regressions", []) if report else []
    checked = report.get("rules_checked", "?") if report else "?"
    passed = report.get("rules_passed", "?") if report else "?"
    print("    rules %s/%s passed, %d regression(s)"
          % (passed, checked, len(regressions)))
    for reg in regressions[:6]:
        print("      - %-9s %s" % (reg.get("rule_id", "?"),
                                   (reg.get("rule") or "")[:60]))
        if reg.get("diagnosis"):
            print("          %s" % (reg["diagnosis"][:70]))
    return regressions


def main():
    repair = "--repair" in sys.argv
    max_attempts = MAX_ATTEMPTS
    if "--max-attempts" in sys.argv:
        max_attempts = int(sys.argv[sys.argv.index("--max-attempts") + 1])

    print()
    print("  VALIDATION")
    print("  " + "-" * 60)
    began = time.time()

    result = ask_expecting("validation", VALIDATE_PROMPT,
                           ["validation_report.json"], attempts=2,
                           validator=reject_hollow)
    if not result["ok"]:
        print("    ERROR: %s\n" % result["error"])
        return 1
    report = load_report()
    regressions = summarise(report, 0)
    print("    (%ss)" % result["seconds"])

    if not repair or not regressions:
        print()
        if not regressions:
            print("  No regressions. Migration matches the legacy behaviour.")
        else:
            print("  %d regression(s). Re-run with --repair to fix them."
                  % len(regressions))
        print()
        return 0

    attempt = 0
    while regressions and attempt < max_attempts:
        attempt += 1
        print()
        print("  REPAIR attempt %d of %d   (validation -> execution, A2A)"
              % (attempt, max_attempts))
        print("  " + "-" * 60)

        fix = ask("execution", REPAIR_PROMPT % (attempt, max_attempts))
        if not fix["ok"]:
            print("    execution failed: %s" % fix["error"])
            break
        print("    execution responded (%ss)" % fix["seconds"])

        result = ask_expecting("validation", VALIDATE_PROMPT,
                               ["validation_report.json"], attempts=1,
                               validator=reject_hollow)
        if not result["ok"]:
            print("    re-validation failed: %s" % result["error"])
            break
        report = load_report()
        regressions = summarise(report, attempt)

    print()
    print("  " + "=" * 60)
    if not regressions:
        print("  REPAIRED after %d attempt(s) in %ds"
              % (attempt, int(time.time() - began)))
    elif attempt >= max_attempts:
        print("  FLOW GUARD — stopped after %d attempts, %d regression(s) remain"
              % (attempt, len(regressions)))
        print()
        print("  The loop was terminated by the depth cap, not by the agents")
        print("  deciding to stop. Deployed on Nasiko this is")
        print("  NASIKO_FLOW_MAX_DEPTH doing the same job on A2A hops.")
        print()
        print("  ESCALATED TO HUMAN REVIEW")
    print("  " + "=" * 60)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
