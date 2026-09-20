# 7. Demo script

Six beats, ~6 minutes. Each beat proves one thing. Cut from the bottom if short
on time — beats 1–4 are the demo, 5–6 are the flourish.

---

## Beat 1 · The repo nobody understands — 30s

Show `acme-orders` in the editor. Scroll it.

> "Flask, MySQL, Celery. Twenty files, no docs, and the people who wrote it left.
> We want FastAPI and Postgres. The obvious move is to hand this to an LLM and ask
> for a rewrite. That fails — and it fails quietly, which is worse."

## Beat 2 · Discovery finds what nobody documented — 60s

Kick off discovery. Let findings stream.

```
  ▸ found: VIP discount rule, undocumented        pricing.py:47
  ▸ found: OrderService → InventoryService        orders.py:112
  ▸ warn:  no test coverage on payments/
```

> "Before writing a line, it found a business rule that exists only in code —
> VIP customers get 15% off above ₹5,000. Nobody wrote that down. A syntax-level
> rewrite drops it and you find out from a customer.
>
> Nothing has been written to the repo. These agents hold no write permission."

**Proves: D1 behavior-first, D4 read-only.**

## Beat 3 · Three options, priced — 45s

Show the tier cards.

> "'Modernize my app' isn't one job. Refresh gets you off Flask for about forty
> cents. Restructure rebuilds the architecture for a dollar fifteen. Re-architect
> splits it into services for four dollars and a lot more risk.
>
> Tokens, runtime and risk — before you commit, not after. That's the customer's
> call, not the AI's. We'll take Tier 2."

**Proves: D3 you choose the destination.**

## Beat 4 · Approval is a permission — 45s ⭐

**The strongest 45 seconds. Rehearse this one.**

Run execution *before* approving:

```
$ stackshift run --tier 2
  ✗ Execution agent: write denied by control plane
```

> "It's not that the agent was told not to. It doesn't have the permission."

Click approve. Run the same command:

```
$ stackshift run --tier 2
  ✓ writing to migration/fastapi-orders
```

> "Same command, twenty seconds apart. Nothing changed in our code. What changed
> was an ACL grant in Nasiko. Approval flips a permission, not a flag an agent
> could ignore."

**Proves: D4, and Nasiko ACL doing real work.**

## Beat 5 · It catches its own bug and fixes it — 90s

Let Validation find trap T3.

```
  TEST 127 · VIP discount with coupon
  input      customer=VIP  total=₹7200  coupon=SAVE10
  LEGACY     coupon rejected   final ₹6120
  MIGRATED   coupon ACCEPTED   final ₹5508
  ❌ REGRESSION → sent to Execution (attempt 1 of 3)
```

> "The migrated code compiles and its tests pass. It's still wrong. The legacy
> system rejects coupons stacked on the VIP discount; the new one doesn't.
>
> Validation found it — and Validation cannot edit code. It has no write
> permission. So it hands the failure to Execution over A2A. That hop is on the
> trace."

**Proves: D1, D7 specialists with different authority, A2A.**

## Beat 6 · Autonomous, but it can't run away — 45s ⭐

Let the loop hit the cap.

```
  attempt 1  fixed, still failing
  attempt 2  fixed, still failing
  attempt 3  fixed, still failing
  attempt 4  ✗ FLOW GUARD — max depth exceeded, chain terminated
  → escalated to human review
```

> "An LLM deciding to call another LLM is exactly how you wake up to a four
> hundred dollar bill. Nasiko's flow guards capped it. We didn't write that stop —
> it came with the control plane."

**Proves: D5 bounded autonomy.**

## Close · The evidence trail — 30s

Show the trace, then the readiness card.

```
  Agents 5 · A2A calls 19 · 4m12s · 512k tokens · $1.14 · repairs 3

  READINESS 72% — do not merge yet
  ─ 3 behavior mismatches
  ─ 1 schema incompatibility
```

> "78% isn't a model's opinion — it's computed from counted evidence. And the
> output isn't 'done', it's a branch with an audit trail: what changed, what was
> validated, what failed, what still needs a human.
>
> That's the difference between generated code and a migration you can actually
> review."

---

## The 2-minute pitch

> Migrating a legacy system isn't a code translation problem. It's a discovery,
> dependency, behavior and validation problem.
>
> StackShift turns a GitHub repo into a migration mission. A fleet of specialist
> agents discovers the architecture and the business rules nobody wrote down, maps
> the dependencies, and comes back with three costed options — because how far you
> modernize is a budget decision, not a technical one.
>
> You pick one and approve it. That approval isn't a flag in our code — it grants
> a permission the execution agent doesn't otherwise have. Until you click, no
> agent in the fleet can write to your repo.
>
> Then it migrates the APIs, the data layer and the workers, validates the result
> against the legacy system's actual behavior, and repairs the regressions it finds
> on its own — bounded, so it can't run away.
>
> Nasiko is the control plane: it routes the fleet, governs agent-to-agent traffic,
> enforces least privilege, caps runaway chains, and traces every decision.
>
> The output isn't just generated code. It's a migration branch backed by an
> evidence trail showing what changed, what was validated, what failed, and what
> still needs human approval.

---

## If it breaks on stage

- **Play the recording.** Say "here's the run we recorded" and keep going. Don't debug live
- **Agent won't respond:** `nasiko ps`, then `nasiko logs <agent> -f`
- **Workflow hits a stale endpoint:** it pinned the agent URL at create time. Re-create it
- **MAF stuck at `pending`:** runs queued before the worker started are orphaned. Re-run

## Questions you will get

| Question | Answer |
|---|---|
| "How is this different from Copilot / AWS Transform?" | Those translate code. We migrate *behavior*, and prove parity against the legacy system |
| "Where does the 78% come from?" | Plain arithmetic over counted evidence — show `score.py`. Agents supply evidence, code does the maths |
| "What if the agents are wrong?" | Every finding cites file:line. The output is a reviewable branch, and readiness never claims done when it isn't |
| "Would this work on a 500k-line repo?" | Not today. Discovery is the bottleneck. That's chunking + incremental indexing — the architecture doesn't change |
| "Why Nasiko and not LangGraph?" | ACL, flow guards and cross-agent tracing. We'd have built all three by hand, badly |
