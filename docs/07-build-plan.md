# 6. Build plan — what ships today

Docs 1–5 describe **the product**. This doc is **today's build**, and it is much
smaller. Where today fakes or skips something, it says so.

```
Written  2026-09-20 13:45 IST
Deadline 2026-09-20 16:30 IST
Left     2h 45m
```

---

## The honest cut

| Piece | Today | Notes |
|---|---|---|
| 5 agents deployed | ✅ | Forks of `agents/coding`, differing by prompt + tool list |
| Discovery finds hidden rules | ✅ | Real. This is the core claim |
| MAF spine (3 steps) | ✅ | Discovery → Assessment → Planning |
| Tier cards with costs | ⚠️ **partly** | Structure and numbers real; **estimates are calibrated from one measured run**, not modelled per-repo |
| Approval flips an ACL grant | ✅ | Real, and it's the best demo beat |
| A2A repair loop | ✅ | Validation → Execution |
| Flow guard stops attempt 4 | ✅ | Real |
| Deterministic readiness score | ✅ | `score.py`, no LLM |
| Migration branch + diff | ✅ | Local branch |
| **Web portal UI** | ❌ **CLI + rendered cards instead** | A web app does not fit in 2h45m |
| **Custom tier picker** | ❌ | Tiers 1–3 only today |
| Live behavior diff vs running legacy app | ❌ | Parity asserted from a fixture — saves ~2 hours |
| GitHub PR creation | ❌ | Local branch only; push if time allows |
| Tier 3 microservices split | ❌ | Tier 1 + 2 execute; Tier 3 is priced but not executed |

**Say the ❌ rows out loud in the pitch** as "what's next". Nobody expects a
finished product from a hackathon; everybody notices a bluff.

---

## Order of work

### Phase 0 · Foundation — 13:45–14:10

Do this first because everything else depends on it, and none of it needs agents.

- [ ] **`.gitignore` for `Tasks/resources.yaml` and `.env`** — there's a live
      Bedrock credential in plaintext one directory over. Do this before any commit
- [ ] Generate `acme-orders`, the legacy Flask demo repo (~20 files) with 3 planted traps
- [ ] Write `score.py` + the JSON schemas agents exchange
- [ ] Write the expected-results fixture (the behavioral baseline)

**Gate:** the legacy repo exists and its traps are real.

### Phase 1 · Agents — 14:10–15:00

- [ ] **Spike first:** fork `agents/coding` → `discovery`, build and deploy **one** agent
- [ ] 🚦 **Gate at 14:30** — if one Rust agent hasn't built and deployed, abandon the
      Rust fork and move all agents to the Python `agents/openai` template
- [ ] Deploy `assessment`, `planning`, `execution`, `validation`
- [ ] Trim each agent's tool list to its role — this *is* the least-privilege demo
- [ ] Set ACL grants; leave Execution **without** write

**Gate:** `nasiko ps` shows 5 agents active.

### Phase 2 · Spine — 15:00–15:35

- [ ] Deploy all 5 agents **before** creating the workflow (endpoints pin at create time)
- [ ] `nasiko maf workflow create --name stackshift` (3 steps)
- [ ] Run it; confirm Discovery caught trap 1 and Planning caught trap 2
- [ ] Render the tier cards from `migration_plan.json`

🚦 **CUT LINE — you have a demo here.** Everything after is upside.

### Phase 3 · Approval + repair — 15:35–16:00

- [ ] Approval flips the ACL grant → **rehearse the denied-then-allowed sequence**
- [ ] Wire Validation → Execution over A2A
- [ ] Confirm trap 3 is caught, repaired, re-validated
- [ ] Drop the flow guard caps; confirm attempt 4 is killed

### Phase 4 · Evidence — 16:00–16:15

- [ ] Screenshot the end-to-end trace
- [ ] `nasiko observe stats` → agents, A2A calls, tokens, cost
- [ ] Run `score.py`, capture the readiness card
- [ ] Capture the branch diff

### Phase 5 · Freeze — 16:15–16:30 · **non-negotiable**

- [ ] **Stop building.** No exceptions
- [ ] Screen-record one full successful run as the fallback
- [ ] Rehearse the 2-minute pitch out loud, twice

> A recorded run that works beats a live run that might not.

---

## The demo repo

`acme-orders` — Flask + MySQL + Celery + Jinja, ~20 files. We migrate only
`/orders`, but deliberately couple it to `auth`, `inventory`, `pricing` and
`notifications` so a 20-file repo shows the same complexity pattern as a real one.

Three planted traps, one per agent:

| Trap | What it is | Who catches it |
|---|---|---|
| **T1** | `if customer.vip and total > 5000: discount = 15` — documented nowhere | Discovery |
| **T2** | `OrderService` calls `InventoryService`, invisible from the API layer | Planning |
| **T3** | NULL quantity behaves differently in Postgres than MySQL | Validation |

**T3 is the one that must survive to demo time** — it's what triggers the repair
loop. If you break T3 while debugging, fix T3 before anything else.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Rust agent builds blow the schedule | medium | high | 14:30 gate → Python template |
| Stale pinned agent endpoints after redeploy | **high** | medium | Re-create the workflow. You *will* hit this once |
| MAF slow/flaky under iteration | medium | medium | 3 steps only; test agents individually first |
| Live demo fails on stage | medium | high | Phase 5 recording. Non-negotiable |
| Bedrock credential expires | low | total | Expires 23:05 IST — outlasts the demo |

---

## Verified environment

- Nasiko: 7/7 containers up, server healthy, dashboard at `localhost:8080`
- LLM: `qwen.qwen3-coder-next` via Bedrock OpenAI-compatible endpoint — smoke-tested, HTTP 200
- Reusable: `agents/coding` ships `read_file` `edit_file` `list_directory` `glob`
  `run_command` — the single biggest shortcut available
