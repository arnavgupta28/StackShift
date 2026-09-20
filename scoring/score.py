#!/usr/bin/env python3
"""Deterministic migration readiness score.

No LLM is involved. Agents supply counted evidence; this file does the
arithmetic. That is the point: when someone asks "why 78%?", the answer is a
formula you can read, not a model's opinion.

Usage:
    python3 scoring/score.py validation_report.json
    python3 scoring/score.py --demo
"""

import json
import sys

# Each dimension is scored 0..1, then weighted. Weights sum to 1.0.
WEIGHTS = {
    "architecture_confidence": 0.15,
    "api_compatibility": 0.25,
    "database_compatibility": 0.20,
    "behavioral_parity": 0.30,
    "test_coverage": 0.10,
}

# A dimension cannot score above this if the context it depends on was missing.
# We do not claim confidence we have no basis for. See docs/03-inputs-and-context.md
CONTEXT_CAPS = {
    "api_compatibility": {"openapi": 1.00, None: 0.70},
    "behavioral_parity": {"traffic": 1.00, None: 0.85},
}

BLOCKER_RULES = [
    ("behavior_mismatches", 0, "behavior mismatch(es)"),
    ("schema_incompatibilities", 0, "schema incompatibility(ies)"),
    ("unresolved_dependencies", 0, "unresolved dependency(ies)"),
    ("failed_contract_tests", 0, "failed contract test(s)"),
]

MERGE_THRESHOLD = 0.90


def _ratio(passed, total):
    """Passed out of total, where an empty set scores 0 rather than 1.

    Zero tests is not a perfect score. It is no evidence.
    """
    if total <= 0:
        return 0.0
    return max(0.0, min(1.0, passed / total))


def compute(ev):
    """ev: counted evidence emitted by the Validation agent."""
    dims = {}

    modules = ev.get("modules_total", 0)
    dims["architecture_confidence"] = _ratio(
        modules - ev.get("unresolved_dependencies", 0), modules
    )

    contracts = ev.get("contract_tests_total", 0)
    dims["api_compatibility"] = _ratio(
        contracts - ev.get("failed_contract_tests", 0), contracts
    )

    tables = ev.get("tables_total", 0)
    dims["database_compatibility"] = _ratio(
        tables - ev.get("schema_incompatibilities", 0), tables
    )

    rules = ev.get("behavior_rules_total", 0)
    dims["behavioral_parity"] = _ratio(
        rules - ev.get("behavior_mismatches", 0), rules
    )

    stmts = ev.get("statements_total", 0)
    dims["test_coverage"] = _ratio(ev.get("statements_covered", 0), stmts)

    # Apply context caps — we cannot claim what we never had evidence for.
    context = ev.get("context_linked", [])
    caps_applied = {}
    for dim, table in CONTEXT_CAPS.items():
        source = next((s for s in table if s and s in context), None)
        cap = table[source] if source else table[None]
        if dims[dim] > cap:
            caps_applied[dim] = cap
            dims[dim] = cap

    overall = sum(dims[k] * w for k, w in WEIGHTS.items())

    blockers = []
    for key, limit, label in BLOCKER_RULES:
        n = ev.get(key, 0)
        if n > limit:
            blockers.append({"count": n, "label": label, "key": key})

    return {
        "overall": round(overall, 4),
        "dimensions": {k: round(v, 4) for k, v in dims.items()},
        "weights": WEIGHTS,
        "caps_applied": caps_applied,
        "blockers": blockers,
        "recommendation": (
            "READY FOR HUMAN REVIEW"
            if overall >= MERGE_THRESHOLD and not blockers
            else "DO NOT MERGE YET"
        ),
        "evidence": ev,
    }


def render(result):
    pct = lambda x: "%d%%" % round(x * 100)
    out = []
    out.append("")
    out.append("  MIGRATION READINESS · %s" % pct(result["overall"]))
    out.append("  " + "-" * 40)
    for key, weight in WEIGHTS.items():
        val = result["dimensions"][key]
        bar = "#" * int(val * 20)
        capped = " (capped: missing context)" if key in result["caps_applied"] else ""
        out.append("  %-26s %-20s %4s%s"
                   % (key.replace("_", " "), bar, pct(val), capped))
    out.append("")
    if result["blockers"]:
        out.append("  BLOCKERS")
        for b in result["blockers"]:
            out.append("   - %d %s" % (b["count"], b["label"]))
    else:
        out.append("  No blockers.")
    out.append("")
    out.append("  RECOMMENDATION: %s" % result["recommendation"])
    out.append("  " + "-" * 40)
    out.append("")
    return "\n".join(out)


DEMO_EVIDENCE = {
    "modules_total": 12,
    "unresolved_dependencies": 2,
    "contract_tests_total": 37,
    "failed_contract_tests": 0,
    "tables_total": 5,
    "schema_incompatibilities": 1,
    "behavior_rules_total": 8,
    "behavior_mismatches": 3,
    "statements_total": 420,
    "statements_covered": 311,
    "context_linked": [],
}


def main():
    args = sys.argv[1:]
    if not args or args[0] == "--demo":
        evidence = DEMO_EVIDENCE
    else:
        with open(args[0]) as fh:
            report = json.load(fh)
        evidence = report.get("evidence", report)

    result = compute(evidence)
    if "--json" in args:
        print(json.dumps(result, indent=2))
    else:
        print(render(result))
    return 0 if not result["blockers"] else 1


if __name__ == "__main__":
    sys.exit(main())
