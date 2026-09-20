# 3. The approval portal — human in the loop

The agents propose. **The human decides.** Nothing touches the code until someone
picks a tier and clicks approve.

This exists because "modernize my app" is not one job. How far you go depends on
budget, deadline and appetite for risk — and that is the customer's call.

---

## Step 1 — Input

What the developer gives us. This is the short version — the full input
model (the aim, Jira, OpenAPI, traffic data, `stackshift.json`, org guardrails)
is in [03-inputs-and-context.md](03-inputs-and-context.md).

```
┌─────────────────────────────────────────────────────┐
│  Repository    github.com/acme/acme-orders          │
│  Branch        main                                 │
│                                                     │
│  Migrate from  Flask + MySQL + Celery   [detected]  │
│  Migrate to    FastAPI + PostgreSQL     [dropdown]  │
│                                                     │
│  Constraints   ☑ preserve API behavior              │
│                ☑ no breaking API changes            │
│                ☑ generate tests                     │
│                ☑ Dockerize                          │
│                ☐ keep Python 3.9 compatibility      │
│                                                     │
│  Scope         ◉ whole repo   ○ just /orders        │
│                                                     │
│                            [ Start Discovery ]      │
└─────────────────────────────────────────────────────┘
```

"Migrate from" is **detected, not typed**. Discovery fills it in. If we can't
detect it, that's a finding worth showing, not a form field to nag about.

---

## Step 2 — Discovery runs (read-only)

The developer watches it work. Live, not a spinner.

```
  Discovery    ████████████████████  done   42 modules, 37 endpoints, 28 tables
  Assessment   ████████████░░░░░░░░  working…
  Planning     ░░░░░░░░░░░░░░░░░░░░  queued

  ▸ found: 3 undocumented business rules
  ▸ found: 1 hidden dependency (OrderService → InventoryService)
  ▸ found: 2 modules with no test coverage at all
```

Findings stream in as they're discovered. A developer who sees "3 undocumented
business rules" already got value, before any code was written.

**Nothing has write access at this point.** Not by policy — by permission.

---

## Step 3 — Choose a tier

This is the heart of the portal. Three costed options plus custom.

### Tier 1 · Refresh — *cheapest, safest*

> Same architecture, modern stack. Get off Flask without redesigning anything.

| | |
|---|---|
| **What changes** | Flask → FastAPI, MySQL → PostgreSQL (1:1 schema), adds OpenAPI, Dockerfile, basic pytest |
| **What stays** | Monolith structure, module layout, Celery workers, all existing logic |
| **Files** | ~31 modified, ~9 new, ~7 deleted |
| **Agents** | Discovery, Assessment, Planning, Execution, Validation |
| **Est. runtime** | ~4 min |
| **Est. cost** | ~180k tokens · ~$0.40 |
| **Risk** | **Low** — smallest behavior surface, easiest parity to prove |
| **Pick this if** | The stack is the problem, not the design. Deadline pressure. |

### Tier 2 · Restructure — *recommended*

> Layered architecture. Code that will survive another five years.

| | |
|---|---|
| **What changes** | Everything in Tier 1, plus: api/service/repository split, Pydantic models, dependency injection, async workers replacing Celery, contract tests, real test suite |
| **What stays** | One deployable. One database. |
| **Files** | ~48 modified, ~34 new, ~12 deleted |
| **Agents** | All 5, deeper Assessment pass |
| **Est. runtime** | ~9 min |
| **Est. cost** | ~520k tokens · ~$1.15 |
| **Risk** | **Medium** — code moves between files, more to validate |
| **Pick this if** | This app matters and people will keep working on it. |

### Tier 3 · Re-architect — *most ambitious*

> Split into services. Cloud-native.

| | |
|---|---|
| **What changes** | Everything in Tier 2, plus: split into orders / auth / inventory services, per-service database, message bus between them, per-service Dockerfile, Terraform |
| **What stays** | The business rules. Nothing else is guaranteed. |
| **Files** | ~48 modified, ~90 new, ~40 deleted |
| **Agents** | All 5, fanned out per service — **this is where flow guards earn their keep** |
| **Est. runtime** | ~25 min |
| **Est. cost** | ~1.8M tokens · ~$4.10 |
| **Risk** | **High** — biggest behavior surface; expect human review on every service boundary |
| **Pick this if** | You're scaling teams, not just modernizing code. |

### Custom

Pick each dimension yourself. Cost and risk recompute as you click.

```
  Framework    ○ keep Flask   ◉ FastAPI      ○ Litestar
  Database     ○ keep MySQL   ◉ PostgreSQL   ○ Postgres + read replica
  Workers      ○ keep Celery  ◉ async tasks  ○ message bus
  Tests        ○ none         ○ smoke        ◉ contract + behavior
  Packaging    ○ none         ◉ Docker       ○ Docker + Helm
  Infra        ◉ none         ○ Terraform

  ─────────────────────────────────────────────
  Est. 11 min · ~610k tokens · ~$1.35 · Risk: Medium
```

---

## Step 4 — Review the plan before approving

Picking a tier doesn't start it. You see exactly what will happen first:

```
  MIGRATION PLAN · Tier 2 · Restructure
  ──────────────────────────────────────────────
  Strategy   INCREMENTAL (not big-bang)
  Reason     37 endpoints, 11 downstream deps, 4 shared tables

  PHASE 1  Extract API layer              12 files   low risk
  PHASE 2  Introduce service interfaces    8 files   low risk
  PHASE 3  Migrate data access            14 files   HIGH risk  ⚠
  PHASE 4  Convert background workers      6 files   medium
  PHASE 5  Migrate endpoints              18 files   medium
  PHASE 6  Compatibility validation         —        —
  PHASE 7  Retire legacy modules           7 files   low

  ⚠ PHASE 3 touches the VIP discount rule (pricing.py:47)
    and the NULL-quantity handling that differs in Postgres.
    These will be behavior-tested. Expect a repair cycle here.

  ──────────────────────────────────────────────
  [ Approve & Execute ]   [ Adjust ]   [ Cancel ]
```

We tell you where it's likely to go wrong **before** it goes wrong. That's the
difference between a tool that's confident and one that's honest.

---

## Step 5 — Approval flips a permission

This is the bit worth demoing.

```
BEFORE approval                 AFTER approval
───────────────                 ──────────────
Discovery    read               Discovery    read
Assessment   read               Assessment   read
Planning     read               Planning     read
Execution    read               Execution    read + WRITE ← granted now
Validation   read + exec        Validation   read + exec
```

Approval isn't a flag in our code that an agent could ignore. It's a Nasiko ACL
grant. Before you click, the Execution agent attempting a write gets **denied by
the control plane**.

**Demo beat:** try to run Execution before approving. Show the denial in the logs.
Then approve, and run it again. That's a 20-second sequence that makes the whole
security story concrete.

---

## Step 6 — Watch, then decide again at the end

During execution the developer sees the live trace (see
[06-nasiko-map.md](06-nasiko-map.md)), and at the end gets a readiness report:

```
  MIGRATION READINESS · 72%
  ─────────────────────────────────
  Architecture confidence     91%
  API compatibility           96%
  Database compatibility      71%
  Behavioral parity           82%
  Test coverage               74%

  BLOCKERS
  ─ 3 behavior mismatches
  ─ 1 schema incompatibility
  ─ 2 unresolved dependencies

  RECOMMENDATION: do not merge yet
  ─────────────────────────────────
  [ View diff ]  [ View evidence ]  [ Push branch ]
```

The number is computed by `score.py` from counted evidence — not generated by a
model. See D6 in [01-problem-and-diff.md](01-problem-and-diff.md).

---

## Implementation note — Nasiko's HITL is not usable here

Nasiko ships a `hitl/` crate with a `HitlRequest` type that looks perfect for
this: it has `question`, `human_response`, `resume_state`, and even
`maf_execution_id` + `maf_step_index` for pausing a workflow mid-step.

**It isn't wired up.** There's a DB migration (`migrations/0007_hitl.sql`) and the
crate compiles, but nothing imports it — no server routes, no orchestrator
integration. It's scaffolding for a future release.

So we build the gate ourselves:

- The spine (Discovery → Assessment → Planning) is one MAF workflow that **ends**
  at the plan. It does not continue into execution.
- The portal shows the tiers and waits.
- On approval we grant the ACL write permission, then kick off Execution as a
  separate call.

Two workflows with a human in between, rather than one workflow that pauses.
Simpler, and it works today.
