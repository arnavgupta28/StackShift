# 5. Where we use Nasiko

The objective is not "we used Nasiko somewhere". It's that **every Nasiko
capability does real work that the project would be worse without** — and that
each one has a moment on screen.

A capability we only *describe* doesn't count. Each row below has a demo beat.

---

## The map

| # | Nasiko capability | Where StackShift uses it | How we prove it live |
|---|---|---|---|
| 1 | **A2A proxy** | Validation hands regressions to Execution | Trace shows the hop — two agents, one conversation |
| 2 | **Routing** | Start a session with no agent picked; router chooses | Ask "what business rules does this repo have?" → Discovery is selected, unprompted |
| 3 | **MAF workflows** | The Discovery → Assessment → Planning spine | One `context_id`, one trace, three agents |
| 4 | **ACL** | Only Execution can write, and only after approval | Run Execution pre-approval → **denied**. Approve → succeeds |
| 5 | **Flow guards** | Caps the repair loop | Attempt 4 killed by the control plane, on camera |
| 6 | **Observability** | End-to-end migration trace | One trace spanning all 5 agents |
| 7 | **TokenOps / FinOps** | The cost numbers on the tier cards | `nasiko observe stats` → real tokens, real dollars |
| 8 | **Secrets** | Bedrock credentials live in Nasiko, not agent code | Grep the agent source — no keys in it |
| 9 | **Deployment runtime** | 5 agents, independent lifecycles | `nasiko ps` → five agents, five containers |
| 10 | **GitHub integration** | Pulling the legacy repo in | Repo connected from the dashboard |

---

## The four that actually carry the pitch

Anyone can deploy five agents. These four are what make it Nasiko-native.

### ACL — approval is a permission, not a promise

The strongest 20 seconds in the demo:

```
$ stackshift run --tier 2          # before approving
  ✗ Execution agent: write denied by control plane
    grant: none

[ click Approve in the portal ]

$ stackshift run --tier 2
  ✓ Execution agent: writing to migration/fastapi-orders
```

Same command, twice, 20 seconds apart. Nothing changed in our code. What changed
was a grant in Nasiko.

> **Line to use:** "The approval button doesn't set a flag the agent could ignore.
> It grants a permission the agent doesn't otherwise have."

### Flow guards — autonomous, but it can't run away

The repair loop is an LLM deciding to call another LLM. That's exactly the shape
that burns $400 overnight.

```
  attempt 1  Validation → Execution   fixed, still failing
  attempt 2  Validation → Execution   fixed, still failing
  attempt 3  Validation → Execution   fixed, still failing
  attempt 4  ✗ FLOW GUARD — max depth 6 exceeded, chain terminated

  → escalated to human review
```

Set the caps low and let this happen **on purpose**.

> **Line to use:** "We built a system that reasons, delegates, repairs and
> re-validates on its own — and the control plane stops it running away. We
> didn't write that stop. It came with Nasiko."

### Observability — the evidence trail is the product

Don't show "migration complete". Show the trace.

```
  MIGRATION #1042

        Router
          │
      Discovery
          │
      Assessment
          │
       Planning
          │
     ⏸ APPROVAL (human, 41s)
          │
      Execution ⇄ Validation  (3 repair cycles)
          │
       Readiness 78%

  Agents 5 · A2A calls 19 · 4m12s · 512k tokens · $1.14 · repairs 3
```

Every span is a decision you can click into. For a migration — where the question
is always "why did it do *that*?" — the trace isn't telemetry, it's the deliverable.

### Routing — the fleet is real

With one agent, routing is a curiosity. With five specialists it's the point:
the user asks a question and doesn't have to know which agent owns it.

---

## Honest notes

Say these if asked. Getting caught overstating is worse than the gap itself.

- **MAF can't loop.** `MafDefinition { steps: Vec<MafStep> }` and a flat `for` in
  `executor.rs` — strictly linear. Our repair loop is A2A, not MAF. This is a
  design consequence we worked *with*, and it's why flow guards apply at all.
- **Nasiko's HITL crate isn't wired in.** `hitl/` has types and a migration but
  nothing imports it. We built the approval gate ourselves. See
  [04-approval-portal.md](04-approval-portal.md).
- **MAF re-plans on every run** — ~8 LLM calls per 3 steps. That's why the spine
  is 3 steps, not 8.
- **MAF pins agent endpoints at create time.** Redeploy an agent and the workflow
  silently points at a stale URL. Re-create the workflow after any redeploy.

---

## Tiers → capabilities

Worth noting that the tier choice changes which Nasiko features get exercised:

| | Tier 1 | Tier 2 | Tier 3 |
|---|---|---|---|
| A2A repair loop | rare | yes | constant |
| Flow guard fan-out cap | — | — | **load-bearing** (per-service fan-out) |
| Cost tracking matters | a little | yes | **a lot** ($4+) |

Tier 3 is where the control plane stops being nice-to-have. If the demo has room,
run Tier 3 once just to show the fan-out being capped.
