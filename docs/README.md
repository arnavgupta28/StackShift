# StackShift

**Legacy in. Migration plan, code, tests and evidence out.**

You point StackShift at a legacy repo. It works out what the code *actually does*,
shows you three ways to modernize it with the cost of each, waits for you to pick one,
then does the work and proves it didn't break anything.

Nasiko is the control plane underneath: it routes the agents, governs what each one is
allowed to touch, stops them running away, and records every decision as a trace.

---

## Read in this order

| # | Doc | What's in it |
|---|-----|--------------|
| 1 | [01-problem-and-diff.md](01-problem-and-diff.md) | The problem, and the 7 things that make this different from "ask an LLM to rewrite my code" |
| 2 | [02-architecture.md](02-architecture.md) | The 5 agents, the control plane, how they're wired |
| 3 | [03-inputs-and-context.md](03-inputs-and-context.md) | What you feed it: repo, the aim, Jira/docs/OpenAPI/traffic, and the `stackshift.json` input |
| 4 | [04-approval-portal.md](04-approval-portal.md) | The input portal, the 3 tiers + custom, the approval gate |
| 5 | [05-developer-experience.md](05-developer-experience.md) | What a developer actually does, start to finish |
| 6 | [06-nasiko-map.md](06-nasiko-map.md) | Every Nasiko feature we use, where, and how we prove it on stage |
| 7 | [07-build-plan.md](07-build-plan.md) | What we build today, in what order, with the cut lines |
| 8 | [08-demo-script.md](08-demo-script.md) | The run-of-show and the 2-minute pitch |
| 9 | [09-findings.md](09-findings.md) | **What we measured after building it** — including what did not work |
| 10 | [10-recording-steps.md](10-recording-steps.md) | **Recording the demo** — checklist, beat-by-beat script, fallbacks |
| — | [TODO.md](TODO.md) | Live build checklist and how to run everything |

---

## The 60-second version

```
  YOU                                        STACKSHIFT
   │
   ├─ "here's my repo, get me off Flask" ──►  Discovery   reads the code
   │                                          Assessment  scores the difficulty
   │                                          Planning    drafts the migration
   │
   │  ◄────── 3 tiers, each priced ─────────  APPROVAL GATE ⏸
   │
   ├─ "do Tier 2" ────────────────────────►  Execution   writes the new code
   │                                          Validation  tests it against the old behavior
   │                                              ↕        (repairs what it broke, up to a limit)
   │
   │  ◄──── branch + readiness report ───────  DONE
```

Nothing is written to your code until you approve. Before that point the agents
are not merely *told* not to write — they are not **granted** write access at all.

---

## Status

This is a hackathon build. Two things are deliberately separated so nobody is misled:

- **The product** is what these docs describe.
- **What ships today** is marked in [07-build-plan.md](07-build-plan.md). Where today's
  build fakes or skips something, it says so.

Ground truth verified against the running stack on 2026-09-20:

- Nasiko is up and healthy (7/7 containers)
- LLM backend live: `qwen.qwen3-coder-next` via Bedrock's OpenAI-compatible endpoint
- A2A proxy, ACL, flow guards, MCP gateway, observability, MAF: all present and working
- Nasiko's own `hitl/` crate is **scaffolding only** — nothing imports it, so we build
  the approval gate ourselves. See [04-approval-portal.md](04-approval-portal.md).
