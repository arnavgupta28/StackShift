# Build checklist

Live status. Tick as you go. Full reasoning in [07-build-plan.md](07-build-plan.md).

```
Deadline  2026-09-20 16:30 IST
```

---

## Phase 0 · Foundation — target 14:35

No agents needed. Everything else blocks on this.

- [x] `.gitignore` covering `.env` and `*resources.yaml`
- [x] Docs committed and pushed
- [ ] `legacy/acme-orders/` — Flask + MySQL + Celery demo app (~20 files)
  - [ ] `app.py`, routes for `/orders`
  - [ ] `services/pricing.py` ← **trap T1** lives here
  - [ ] `services/orders.py` ← **trap T2** lives here
  - [ ] `services/inventory.py`, `auth.py`, `notifications.py`
  - [ ] `models/`, `repositories/`, `workers/`
  - [ ] `schema.sql` ← **trap T3** lives here
- [ ] `contracts/schemas/*.json` — the 6 JSON contracts agents exchange
- [ ] `scoring/score.py` — deterministic readiness, no LLM
- [ ] `fixtures/expected_behavior.json` — the parity baseline

**Gate:** legacy repo exists, all 3 traps verified real.

## Phase 1 · Agents — target 15:00

- [ ] Fork `agents/coding` → `discovery`, build + deploy **one** agent
- [ ] 🚦 **GATE 14:30** — if that one agent isn't deployed, switch all agents to the
      Python `agents/openai` template and don't look back
- [ ] Deploy `assessment`, `planning`, `execution`, `validation`
- [ ] Trim each agent's tool list to its role
- [ ] ACL grants set; **Execution has NO write grant yet**

**Gate:** `nasiko ps` shows 5 active agents.

## Phase 2 · Spine — target 15:35

- [ ] All 5 agents deployed *before* creating the workflow (endpoints pin at create time)
- [ ] `nasiko maf workflow create --name stackshift` (3 steps)
- [ ] Run it end to end
- [ ] Confirm Discovery caught T1, Planning caught T2
- [ ] Render tier cards from `migration_plan.json`

🚦 **CUT LINE — a demo exists here. Everything after is upside.**

## Phase 3 · Approval + repair — target 16:00

- [ ] Approval flips the ACL write grant
- [ ] **Rehearse:** run Execution → denied → approve → succeeds
- [ ] Wire Validation → Execution over A2A
- [ ] Confirm T3 caught, repaired, re-validated
- [ ] Lower flow guard caps; confirm attempt 4 is killed

## Phase 4 · Evidence — target 16:15

- [ ] Screenshot the end-to-end trace
- [ ] `nasiko observe stats` → agents, A2A calls, tokens, cost
- [ ] Run `score.py`, capture the readiness card
- [ ] Capture the branch diff

## Phase 5 · Freeze — 16:15–16:30 · **non-negotiable**

- [ ] **Stop building**
- [ ] Screen-record one full successful run
- [ ] Rehearse the 2-minute pitch twice

---

## The three traps

If you break one while debugging, fix it before moving on. **T3 is the one that
must survive to demo time** — it triggers the repair loop.

| | What | Who catches it |
|---|---|---|
| **T1** | VIP discount rule, documented nowhere | Discovery |
| **T2** | `OrderService` → `InventoryService`, invisible from the API layer | Planning |
| **T3** | NULL quantity behaves differently in Postgres vs MySQL | Validation |

## Branches

| Branch | For |
|---|---|
| `main` | Integrated, demo-ready |
| `docs/architecture-and-plan` | The docs ✅ merged |
| `feat/legacy-demo-repo` | Phase 0 |
| `feat/agent-fleet` | Phase 1 |
| `feat/maf-spine` | Phase 2 |
| `feat/approval-and-repair` | Phase 3 |
