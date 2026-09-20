#!/usr/bin/env python3
"""Create and run the migration spine as a Nasiko MAF workflow.

    python3 run/maf.py create     create the workflow
    python3 run/maf.py run        run it and wait
    python3 run/maf.py ls         list workflows and executions
    python3 run/maf.py result <execution-id>

The three read-only steps (discovery -> assessment -> planning) map onto MAF
exactly, because MAF is a straight line and so are they.

The repair loop does NOT go here. MafDefinition.steps is a Vec and the executor
is a flat for-loop, so there is no back-edge to express it with. It runs over
direct A2A instead, where Nasiko's flow guards bound it. See run/validate.py.

Steps are created WITHOUT an agent_id on purpose, so Nasiko's routing engine
picks the agent for each one from its description. With one agent that would be
a gimmick; with five specialists it is the point.

Two things worth knowing, both learned the hard way:
- MAF resolves and PINS agent endpoints at CREATE time. Redeploy an agent and
  the workflow silently points at a stale URL. Re-create it after any redeploy.
- Every run re-plans, at roughly 8 LLM calls per 3 steps. Keep the spine short.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from deploy import BASE, _api, login  # noqa: E402

NAME = "stackshift-spine"

STEPS = [
    "Read every file in the legacy Flask application under legacy/ in your "
    "workspace, especially legacy/services/ and legacy/repositories/. Inventory "
    "the modules, API endpoints and database tables, and extract the business "
    "rules that are implemented in code but documented nowhere. Write "
    "system_map.json and behavior_contract.json.",

    "Score every module of the legacy application for migration complexity and "
    "risk, and profile its MySQL schema for behavioural differences against "
    "PostgreSQL. Write assessment.json.",

    "Produce a phased migration plan from Flask and MySQL to FastAPI and "
    "PostgreSQL, with three costed tiers and a recommendation. Flag the phases "
    "that touch undocumented business rules. Write migration_plan.json.",
]


# Which agent each step belongs to. These are PINNED rather than left to the
# routing engine.
#
# Routing was tried first and put all three steps on the validation agent. The
# cause is not a bug in Nasiko: semantic routing discriminates by description,
# and five agents that all describe themselves as migration specialists are
# genuinely hard to tell apart by embedding similarity. Routing is for when a
# user asks a question and does not know which agent owns it. A pipeline whose
# steps are known in advance should say which agent runs each one.
STEP_AGENTS = ["discovery", "assessment", "planning"]


def agent_ids(token):
    out = _api("/api/agents", token=token)
    items = out if isinstance(out, list) else (out.get("agents") or out.get("items") or [])
    return {a.get("name"): a.get("id") for a in items}


def create(token):
    ids = agent_ids(token)
    steps = []
    for role, text in zip(STEP_AGENTS, STEPS):
        aid = ids.get("stackshift-%s" % role)
        if not aid:
            print("\n  %s is not deployed — run: python3 run/deploy.py\n" % role)
            return None
        steps.append({"task_description": text, "agent_id": aid})

    payload = {
        "name": NAME,
        "description": ("StackShift read-only migration spine: discover the "
                        "legacy system, assess its risk, plan the migration."),
        "steps": steps,
    }
    out = _api("/api/maf/workflows", token=token, data=payload)
    if out.get("error"):
        print("\n  create failed: %s\n" % (out.get("detail") or out["error"])[:300])
        return None
    wid = out.get("id") or out.get("workflow_id")
    print("\n  created workflow %s" % wid)
    for i, step in enumerate(out.get("steps") or [], 1):
        print("    step %d -> %s" % (i, step.get("agent_name") or "?"))
    print()
    return wid


def find(token):
    out = _api("/api/maf/workflows", token=token)
    items = out if isinstance(out, list) else (out.get("workflows") or out.get("items") or [])
    for w in items:
        if w.get("name") == NAME:
            return w.get("id")
    return None


def run(token, wid):
    out = _api("/api/maf/workflow/%s/run" % wid, token=token, data={}, method="POST")
    if out.get("error"):
        print("\n  run failed: %s\n" % (out.get("detail") or out["error"])[:300])
        return None
    exec_id = out.get("execution_id") or out.get("id")
    print("\n  execution %s queued" % exec_id)
    print("  " + "-" * 56)

    began = time.time()
    last = None
    while time.time() - began < 1800:
        time.sleep(10)
        detail = _api("/api/maf/execution/%s" % exec_id, token=token)
        status = detail.get("status") or detail.get("state")
        if status != last:
            print("  [%4ds] %s" % (int(time.time() - began), status))
            last = status
        for step in detail.get("step_results") or []:
            if step.get("status") == "completed" and not step.get("_seen"):
                step["_seen"] = True
        if status in ("completed", "failed", "error", "cancelled"):
            break

    print("  " + "-" * 56)
    detail = _api("/api/maf/execution/%s" % exec_id, token=token)
    for i, step in enumerate(detail.get("step_results") or [], 1):
        print("  step %d  %-22s %-10s %ss  %s tok"
              % (i, (step.get("agent_name") or "?")[:22], step.get("status"),
                 round((step.get("latency_ms") or 0) / 1000, 1),
                 step.get("tokens_used")))
    print()
    print("  total tokens: %s" % detail.get("tokens_used"))
    print("  result:  python3 run/maf.py result %s" % exec_id)
    print()
    return exec_id


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    token = login()
    cmd = args[0]

    if cmd == "create":
        return 0 if create(token) else 1

    if cmd == "run":
        wid = find(token) or create(token)
        if not wid:
            return 1
        return 0 if run(token, wid) else 1

    if cmd == "ls":
        out = _api("/api/maf/workflows", token=token)
        items = out if isinstance(out, list) else (out.get("workflows") or [])
        print("\n  WORKFLOWS")
        for w in items:
            print("    %-24s %s steps  %s" % (w.get("name"),
                                              len(w.get("steps") or []),
                                              (w.get("id") or "")[:8]))
        execs = _api("/api/maf/executions", token=token)
        rows = execs if isinstance(execs, list) else (execs.get("executions") or [])
        print("\n  EXECUTIONS")
        for e in rows[:10]:
            print("    %-10s %-12s %s tok" % ((e.get("id") or "")[:8],
                                              e.get("status"), e.get("tokens_used")))
        print()
        return 0

    if cmd == "result":
        out = _api("/api/maf/workflow/result/%s" % args[1], token=token)
        print(json.dumps(out, indent=2)[:4000])
        return 0

    print(__doc__)
    return 1


if __name__ == "__main__":
    sys.exit(main())
