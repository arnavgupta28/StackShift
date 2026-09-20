# 1. The problem, and why this is different

## The problem

A company has a 10-year-old customer service app:

- Python Flask, MySQL, Celery, Redis, Jinja templates
- 50+ modules, 37 API endpoints, 28 tables
- Almost no documentation
- The people who wrote it left

They want FastAPI, PostgreSQL, Docker, real tests.

## Why the obvious approach fails

```
Developer ──► "rewrite this in FastAPI" ──► LLM ──► new code ──► hope
```

This fails because **migration is not a translation problem**. Before you can
rewrite a line you have to answer:

- What does this system actually do?
- Which business rules are hidden in the code and written down nowhere?
- What calls what? What breaks if I touch this?
- Which parts can move independently?
- How do I *prove* the new one behaves like the old one?

An LLM handed a file can translate syntax. It cannot answer those questions,
and it will not tell you it didn't.

---

## The 7 diff points

These are the things to say out loud in the pitch. Each one has a demo moment.

### D1 — Behavior first, not syntax first

We don't migrate *lines*, we migrate *rules*.

Discovery reads this:

```python
if customer.vip and order.total > 5000:
    apply_discount(15)
```

and writes down:

> **Rule:** VIP customers get 15% off orders above ₹5,000.
> Source: `services/pricing.py:47`. Documented nowhere.

That list of rules becomes the contract the new code is tested against.

**Why it matters:** a syntactically perfect rewrite that drops this rule is a
production incident. Ours catches it because it was looking for it.

### D2 — Evidence, not vibes

Every claim traces to a file and a line. The final output is not "done" — it's a
report saying what changed, what was validated, what failed, and what a human
still has to look at.

**Why it matters:** you can hand this to a reviewer. "The AI said it's fine"
is not reviewable.

### D3 — You choose the destination, and you see the price first

Three tiers, each with real numbers attached: files touched, agents invoked,
token cost, runtime, risk. Plus a custom option.

**Why it matters:** "modernize my app" isn't one job. The right answer depends on
budget and appetite for risk — and that's the customer's call, not the AI's.
See [04-approval-portal.md](04-approval-portal.md).

### D4 — Read-only until you say go

Discovery, Assessment and Planning **cannot write to your repo**. Not by
instruction — by permission. They hold no write grant.

Approving a plan is what flips the grant on for the Execution agent.

**Why it matters:** "the agent promised not to touch anything" is not a control.
This is.

### D5 — Autonomous, but bounded

When Validation finds a regression it sends it back to Execution to fix, and
re-tests. That's a loop, and loops with LLMs in them can run forever and burn
money.

Nasiko's flow guards cap depth, fan-out, tokens and wall-clock. Attempt 4 gets
killed by the control plane, not by a prompt asking it nicely to stop.

**Why it matters:** this is the difference between a demo and something you'd
let near a real repo.

### D6 — The score is arithmetic, not an opinion

Readiness is computed by plain code from counted evidence:

```
readiness = f(failed_contract_tests,
              failed_behavior_tests,
              schema_incompatibilities,
              unresolved_dependencies)
```

The agents supply the evidence. A script does the maths.

**Why it matters:** when a judge asks "why 78%?", you show the formula. If an
LLM invented the number you have nothing.

### D7 — Specialists with different authority, not one big agent

Five agents, each with a different tool set and different permissions.
Validation can *run* tests but cannot *edit* code — which is precisely why it has
to hand the fix back to Execution, and why that hop shows up in the trace.

**Why it matters:** it makes the multi-agent design load-bearing instead of
decorative. Most "multi-agent" demos are one agent called five times.

---

## What we are deliberately NOT building

Naming these keeps them a decision rather than an oversight.

| Not building | Why |
|---|---|
| Upload ZIP → LLM → download ZIP | Doesn't need agents, doesn't need Nasiko, proves nothing |
| Five agents that each "analyze" with no dependency between them | Fake collaboration. Agents must depend on and constrain each other |
| Migrating a Java monolith into 20 microservices | Too big to finish or to demo |
| Booting the legacy app to diff live behavior | Costs hours; we assert parity from a fixture instead |
| Fully autonomous, no human | The whole point of D3/D4 is that a human decides |
