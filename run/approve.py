#!/usr/bin/env python3
"""The approval gate.

    python3 run/approve.py --status      show the current grant
    python3 run/approve.py --tier 1      approve, and grant Execution write
    python3 run/approve.py --revoke      take the grant back

Approving is not a flag an agent could decide to ignore. It changes what the
Execution agent is physically able to do:

    before   workspace mounted read-only  -> a write fails in the kernel
    after    workspace mounted read-write -> a write succeeds

Locally that boundary is the container mount. Deployed on Nasiko it is a
per-agent ACL grant, enforced by the control plane on the same principle: the
agent is not asked to behave, it is not given the capability.

The other four agents are never granted write. For them this is not a gate,
it is what they are.
"""

import json
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fleet import AGENTS, WORKSPACE, start_agent  # noqa: E402

ARTIFACTS = os.path.join(WORKSPACE, ".stackshift")
APPROVAL = os.path.join(ARTIFACTS, "approval.json")
PLAN = os.path.join(ARTIFACTS, "migration_plan.json")


def read_approval():
    if not os.path.isfile(APPROVAL):
        return None
    with open(APPROVAL) as fh:
        return json.load(fh)


def mount_mode(container="ss-execution"):
    """Ask Docker how the workspace is actually mounted, rather than trusting
    our own record of what we asked for."""
    proc = subprocess.run(
        ["docker", "inspect", "-f",
         "{{range .Mounts}}{{if eq .Destination \"/workspace\"}}{{.RW}}{{end}}{{end}}",
         container],
        capture_output=True, text=True)
    if proc.returncode != 0:
        return "not running"
    return "read-write" if proc.stdout.strip() == "true" else "read-only"


def status():
    approval = read_approval()
    print()
    print("  APPROVAL STATUS")
    print("  " + "-" * 56)
    if approval:
        print("  approved    tier %s" % approval["tier"])
        print("  by          %s" % approval["approved_by"])
        print("  at          %s" % approval["approved_at"])
    else:
        print("  approved    NO -- no tier has been approved")
    print()
    print("  AGENT GRANTS")
    print("  " + "-" * 56)
    for name in AGENTS:
        mode = mount_mode("ss-%s" % name)
        note = ""
        if name == "execution":
            note = "  <- granted by approval" if mode == "read-write" else "  <- no write grant"
        print("  %-12s source: %-12s%s" % (name, mode, note))
    print()
    return 0


def approve(tier):
    if not os.path.isfile(PLAN):
        sys.exit("no migration_plan.json — run: python3 run/spine.py")
    with open(PLAN) as fh:
        plan = json.load(fh)

    ids = [t.get("id") for t in plan.get("tiers", [])]
    if tier not in ids:
        sys.exit("tier %s is not in the plan (have: %s)"
                 % (tier, ", ".join(str(i) for i in ids)))

    chosen = next(t for t in plan["tiers"] if t.get("id") == tier)
    record = {
        "tier": tier,
        "tier_name": chosen.get("name"),
        "approved_by": os.environ.get("USER", "unknown"),
        "approved_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "plan_strategy": plan.get("strategy"),
        "recommended_tier": plan.get("recommended_tier"),
        "followed_recommendation": tier == plan.get("recommended_tier"),
    }
    os.makedirs(ARTIFACTS, exist_ok=True)
    with open(APPROVAL, "w") as fh:
        json.dump(record, fh, indent=2)
        fh.write("\n")

    print()
    print("  APPROVED — Tier %s (%s)" % (tier, chosen.get("name")))
    if not record["followed_recommendation"]:
        print("  NOTE: this is not the recommended tier (%s)."
              % plan.get("recommended_tier"))
    print()
    print("  granting Execution write access ...")
    ok, err = start_agent("execution", writable=True)
    if not ok:
        sys.exit("  failed to restart execution agent: %s" % err[:200])
    time.sleep(5)
    print("  execution agent restarted, workspace now %s"
          % mount_mode("ss-execution"))
    print()
    print("      python3 run/execute.py")
    print()
    return 0


def revoke():
    if os.path.isfile(APPROVAL):
        os.remove(APPROVAL)
    print("\n  revoking Execution write access ...")
    ok, err = start_agent("execution", writable=False)
    if not ok:
        sys.exit("  failed to restart execution agent: %s" % err[:200])
    time.sleep(5)
    print("  execution agent restarted, workspace now %s\n"
          % mount_mode("ss-execution"))
    return 0


def main():
    args = sys.argv[1:]
    if "--status" in args or not args:
        return status()
    if "--revoke" in args:
        return revoke()
    if "--tier" in args:
        try:
            return approve(int(args[args.index("--tier") + 1]))
        except (IndexError, ValueError):
            sys.exit("usage: approve.py --tier N")
    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
