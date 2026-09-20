# 9. Findings — what we measured

Written after building it, on 2026-09-20. Everything here is a measurement or a
quotation from a real run, not a projection. Where something did not work, it
says so.

---

## It works

| Claim | Evidence |
|---|---|
| Discovery finds undocumented rules | 8 rules recovered, each with file:line, matching the hand-written fixture |
| It finds the load-bearing empty branch | *"the `pass` at pricing.py:29 is load-bearing"* |
| It finds the database trap | *"relying on MySQL NULL-first behavior — a migration to PostgreSQL would break this"* |
| Recommendation follows the aim, not repo size | Recommended Tier 1, citing *"a small team of 4 people"* and *"without a redesign"* |
| The plan predicts where it will break | *"BEH-006 ordering must be preserved with NULLS FIRST on products.quantity"* — before any code was written |
| Approval is a capability, not a flag | Pre-approval write fails as `OSError errno 30, read-only file system` |
| The repair loop closes | Validation found 10 regressions → Execution → re-validated clean, 1 attempt, 213s |
| Behaviour is genuinely preserved | 10/10 parity cases match, running both implementations side by side |
| The score is honest | 60%, "DO NOT MERGE YET", because the migration has no tests |

The migrated code kept both traps: the empty branch survived *with a comment
citing the legacy line*, and the nullable `ORDER BY` became
`ORDER BY quantity ASC NULLS FIRST`.

**Timings** (qwen3-coder-next via Bedrock): discovery 58-82s, assessment 11-29s,
planning 19-33s, execution 44-76s, validation 42s. Full local pipeline 6-12
minutes depending on how many repair cycles it takes.

### Run-to-run variance is real, and the system stays honest across it

Two clean runs of the same pipeline produced materially different migrations:

| | run A | run B |
|---|---|---|
| Files migrated | 17 | 9 |
| Regressions found | 10 | 3, then 2, then 6, then 4 |
| Repair outcome | clean after 1 attempt | **stopped by the flow guard at 3** |
| Readiness | 60% | 52% |
| Parity on migrated pricing | 10/10 | **10/10** |

Run B is the more interesting one. The repair loop did not converge — the
regression count went *up* between attempts — and the cap stopped it:

```
FLOW GUARD — stopped after 3 attempts, 4 regression(s) remain
ESCALATED TO HUMAN REVIEW
```

Two things to take from that. The system did not claim success it had not
earned: readiness dropped to 52% and said DO NOT MERGE YET. And the pricing it
*did* migrate was still behaviourally perfect, 10/10 against the legacy
implementation, including the undocumented coupon rule. Partial work,
honestly reported, with the good part verifiable.

This is also the flow guard demo, unstaged. It was not reproducible on demand
during the build; it happened because the migration genuinely failed to
converge.

---

## What did not work

### Semantic routing could not tell the fleet apart

Steps were first created with no `agent_id` so Nasiko's router would pick one
per step. It put **all three on the validation agent**.

This is not a Nasiko bug. Routing discriminates on agent descriptions, and five
agents that all describe themselves as migration specialists are genuinely hard
to separate by embedding similarity. The signal that distinguishes them —
*Discovery reads, Execution writes, Validation checks* — is a small part of
descriptions that are otherwise nearly identical.

**What we did:** the spine pins its agents. Routing is for a user who asks a
question and does not know which agent owns it; a pipeline whose steps are known
in advance should name the agent for each step.

**What would fix it:** descriptions written to contrast rather than to describe,
and ideally a routing hint per step.

### Deployed agents cannot share artifacts

The MAF run on Nasiko succeeded — 3 steps, 225,575 tokens — but **step 3
returned placeholder content**: *"due to missing input artifacts
(assessment.json, behavior_contract.json)"*.

Each deployed agent runs in its own container with its own filesystem. Discovery
wrote its artifacts inside its own container, where Planning cannot see them.
Nasiko's `writable` volume is documented as persistent and *private per agent*,
so it does not close this gap.

Locally the fleet shares one mounted workspace, which is why the same three
steps work end to end there.

**This is the main gap between the local harness and the deployed fleet, and it
is architectural, not a bug.** Options, none of them done yet:

- a shared object store (the stack already runs rustfs) that the artifact tools
  read and write instead of local disk
- passing artifacts through the MAF message chain — but MAF summarises each
  step's reply with an LLM call before passing it on, so structured data does
  not survive intact
- one agent with role-switching, which gives up the per-agent authority
  boundary that is the point of the design

### Context documents are announced, not provably read

Uploading an OpenAPI spec and an architecture note took context completeness
from 14% to 42%, and the spine reported *"context: 2 document(s) supplied by the
user"*. But no artifact from that run cites `context/` anywhere, so we told the
agents the documents existed and cannot show they opened them.

What would fix it: require Discovery to record which context files it read in
`system_map.json`, and reject the artifact if an uploaded OpenAPI spec is not
among them — the same treatment `reject_hollow()` gives an empty report.

### The tier recommendation is not stable across runs

Same aim ("no redesign", "team of 4"), two runs, two answers: Tier 1 the first
time, **Tier 2 the second**. Tier 1 is the better reading of that aim.

The recommendation is one model call over a long context, so it varies. If the
recommendation matters — and the whole point of the tiers is that it does —
it should be computed from the plan's own numbers rather than asked for, the
way `score.py` computes readiness. That is the same mistake in both places, and
we only fixed it in one.

### Per-agent cost attribution reads zero

`/api/observability/finops/dashboard` shows 5 agents and 1.10 container hours
but `total_cost: 0.0` and zero tokens per agent, while the MAF execution
records 225,575 tokens. Token counts are being captured at the orchestration
level and not attributed per agent — most likely because the Bedrock-hosted
qwen model is not in the pricing registry.

**Do not show the FinOps dashboard as a cost demo.** Show the MAF execution's
token count, which is real.

---

## Things that bit us, recorded so they don't again

**The agent described its JSON instead of writing it.** Assessment produced a
correct analysis and printed it in chat. The next agent reads artifacts from
disk and never sees the reply — and MAF replaces the reply with an LLM summary
anyway, so anything left in chat is destroyed. Fixed in the role preamble and,
more reliably, by `ask_expecting()` verifying the file exists.

**Asking it to "just write the artifact now" produced a hollow file.** The
retry got back a correctly-shaped validation report with every count zero and
no regressions — which renders as a perfect migration. A clean bill of health
backed by no measurement is the worst output this system can produce. The retry
now re-sends the whole task, and `reject_hollow()` refuses a report claiming 0
rules checked against a contract with 8. The second attempt found 8/8 rules and
10 regressions.

**The model wrote a Python expression into JSON** — `"expected": {"discount":
subtotal * Decimal('0.15')}`. `write_artifact` now parses `.json` payloads
before saving and hands back the parse error, so the agent repairs it while it
still has the context.

**`score.py` crashed on `null`.** Agents emit `"statements_total": null` for
things they did not measure, and `dict.get(key, 0)` returns `None` for that,
not `0`.

**Nasiko API details:** `version_tag` must be semver (`v1` is rejected);
responses are wrapped as `{data, message, status_code}` with paginated lists
adding another `{data, total}` inside; `data={}` is a legitimate empty POST body
and `if data` silently downgrades the request to a GET, returning 405.

**a2a-sdk 1.1.0 needs an `A2A-Version: 1.0` header.** Without it the server
assumes protocol 0.3 and rejects the call. The method name is `SendMessage`, not
`message/send`.

---

## The build decision that saved the day

The plan was to fork Nasiko's Rust `agents/coding`, which already has file
tools. We used the Python `agents/openai` template instead and wrote the tools.

Installing dependencies *before* copying source makes the pip layer shared
across all five images:

```
first agent    32s
other four     4.5s  total
```

The Rust crate pulls `a2a-rs` from git and would have cost minutes per agent,
for five agents differing only in a prompt and a tool list. The 14:30 fallback
gate in the build plan was never needed because we took the fallback first.

---

## Honest status

| | |
|---|---|
| Local pipeline, end to end | **works** |
| Fleet deployed on Nasiko | **works** — 5 agents running |
| MAF spine on Nasiko | runs; step 3 degrades without shared artifacts |
| Approval gate | **works**, kernel-enforced locally |
| Repair loop | **works**, bounded |
| Flow guard stopping a runaway | **observed** — run B hit the 3-attempt cap and escalated |
| Per-agent cost | not attributed |
| Web portal | not built — CLI only |
| Tier 3 execution | priced, not executed |
