#!/usr/bin/env python3
"""Render the approval portal's tier cards from migration_plan.json.

    python3 run/tiers.py            show the tiers and the plan
    python3 run/tiers.py --json     machine-readable

This is the human decision point. The spine has finished, nothing has been
written to source, and the Execution agent holds no write grant. A person picks
a tier here; run/approve.py is what acts on that choice.

Cost and runtime are ESTIMATES, derived from the plan's own file counts and
calibrated against measured spine runs. They are labelled as estimates on the
card because they are not measurements.
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLAN = os.path.join(ROOT, ".runs", "demo", "workspace", ".stackshift",
                    "migration_plan.json")

# Calibrated from measured runs of this fleet: the spine cost ~62s + ~11s +
# ~33s of model time. Execution and validation scale with the number of files
# touched, so cost is estimated per file rather than per tier.
SECONDS_PER_FILE = 11
USD_PER_FILE = 0.024
TOKENS_PER_FILE = 11_000
REPAIR_MULTIPLIER = {"low": 1.0, "medium": 1.35, "high": 1.8}


def load(path=PLAN):
    if not os.path.isfile(path):
        sys.exit("no migration_plan.json yet — run: python3 run/spine.py")
    with open(path) as fh:
        return json.load(fh)


def normalise(plan):
    """Make exactly one tier recommended.

    The planning agent has twice marked two tiers `recommended: true` while
    naming a single `recommended_tier`. Rather than trust the per-tier flag, we
    derive it from `recommended_tier`, which is the field the agent reasons
    about explicitly and states a justification for. A portal that highlights
    two of three options has not made a recommendation.
    """
    tiers = plan.get("tiers", [])
    chosen = plan.get("recommended_tier")
    if chosen is None:
        flagged = [t for t in tiers if t.get("recommended")]
        chosen = flagged[0].get("id") if flagged else None
    for tier in tiers:
        tier["recommended"] = (tier.get("id") == chosen)
    plan["recommended_tier"] = chosen
    return plan


def estimate(tier):
    files = sum(int(tier.get(k) or 0) for k in
                ("files_modified", "files_new", "files_deleted"))
    mult = REPAIR_MULTIPLIER.get((tier.get("risk") or "medium").lower(), 1.35)
    return {
        "files": files,
        "seconds": int(files * SECONDS_PER_FILE * mult),
        "usd": round(files * USD_PER_FILE * mult, 2),
        "tokens": int(files * TOKENS_PER_FILE * mult),
    }


def _wrap(text, width, indent):
    words, line, out = (text or "").split(), "", []
    for word in words:
        if len(line) + len(word) + 1 > width:
            out.append(line)
            line = word
        else:
            line = (line + " " + word).strip()
    if line:
        out.append(line)
    return ("\n" + " " * indent).join(out)


def render(plan):
    out = []
    add = out.append
    add("")
    add("  MIGRATION PLAN")
    add("  " + "=" * 66)
    add("  Strategy   %s" % (plan.get("strategy") or "?").upper())
    add("  Reason     %s" % _wrap(plan.get("strategy_reason"), 54, 13))
    add("")
    add("  CHOOSE A TIER")
    add("  " + "-" * 66)

    for tier in plan.get("tiers", []):
        est = estimate(tier)
        mark = "  >>" if tier.get("recommended") else "    "
        add("")
        add("%s Tier %s · %s%s" % (mark, tier.get("id"), tier.get("name"),
                                   "   [RECOMMENDED]" if tier.get("recommended") else ""))
        add("       %s" % _wrap(tier.get("summary"), 58, 7))
        add("       files %-4s  risk %-7s  ~%dm%02ds  ~%dk tokens  ~$%.2f (est.)"
            % (est["files"], tier.get("risk"), est["seconds"] // 60,
               est["seconds"] % 60, est["tokens"] // 1000, est["usd"]))
        if tier.get("pick_this_if"):
            add("       pick if: %s" % _wrap(tier.get("pick_this_if"), 50, 16))

    add("")
    add("  " + "-" * 66)
    if plan.get("recommendation_reason"):
        add("  WHY TIER %s" % plan.get("recommended_tier"))
        add("  %s" % _wrap(plan.get("recommendation_reason"), 64, 2))
        add("")

    phases = plan.get("phases", [])
    if phases:
        add("  PHASES  (%d)" % len(phases))
        add("  " + "-" * 66)
        for ph in phases:
            risk = (ph.get("risk") or "").lower()
            flag = " !" if risk == "high" else "  "
            add("  %s%s. %-38s %-6s %s"
                % (flag, ph.get("n"), (ph.get("name") or "")[:38], risk,
                   ",".join(ph.get("touches_rules") or [])[:18]))
            if risk == "high" and ph.get("warning"):
                add("       %s" % _wrap(ph.get("warning"), 58, 7))
        add("")

    add("  " + "=" * 66)
    add("  Nothing has been written to source. The Execution agent holds no")
    add("  write grant. Approving a tier is what grants it:")
    add("")
    add("      python3 run/approve.py --tier %s" % (plan.get("recommended_tier") or 1))
    add("")
    return "\n".join(out)


def main():
    plan = normalise(load())
    if "--json" in sys.argv:
        print(json.dumps(
            {"recommended_tier": plan.get("recommended_tier"),
             "tiers": [dict(t, estimate=estimate(t)) for t in plan.get("tiers", [])]},
            indent=2))
    else:
        print(render(plan))
    return 0


if __name__ == "__main__":
    sys.exit(main())
