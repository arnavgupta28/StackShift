# StackShift

**Legacy in. Migration plan, code, tests and evidence out.**

Point it at a legacy repo. A fleet of five specialist agents works out what the
code actually does — including the business rules nobody wrote down — shows you
three costed ways to modernise it, waits for you to pick one, then does the work
and proves it didn't break anything.

[Nasiko](https://github.com/Nasiko-Labs/nasiko) is the control plane: it runs
the fleet, governs agent-to-agent traffic, enforces least privilege, bounds the
repair loop, and traces every decision.

---

## Why this isn't "ask an LLM to rewrite my code"

Migration is not a translation problem. Before you can rewrite a line you have
to know what the system *does*, what depends on what, and how you would prove
the new one behaves like the old one.

The demo repo has three bugs planted in it. All three are the kind a
syntactically perfect rewrite destroys silently:

```python
if coupon and coupon in COUPONS:
    if discount > 0:
        pass          # <- load-bearing. Tidy this up and pricing changes.
    else:
        discount = subtotal * COUPONS[coupon]
```

```sql
ORDER BY quantity ASC     -- MySQL sorts NULLs first, PostgreSQL sorts them last
```

Discovery found both, unprompted, and said of the first:
*"the `pass` at pricing.py:29 is load-bearing"*.

The migrated code kept them — the empty branch survived with a comment citing
the legacy line, and the query became `ORDER BY quantity ASC NULLS FIRST`.

---

## Try it

Requires the Nasiko stack running locally (`docker compose up -d` in `../nasiko`).

```bash
./run/demo.sh            # the whole thing, pausing between beats
./run/demo.sh --fast     # no pauses
```

The beat worth watching:

```
$ python3 run/execute.py --force
  0 files written — OSError errno 30, read-only file system

$ python3 run/approve.py --tier 1
  granting Execution write access ...

$ python3 run/execute.py
  17 files written to migrated/
```

Same command, twice. Nothing changed in our code. Approval granted a capability
the agent did not otherwise have — locally a mount flag, on Nasiko an ACL grant.
Until you click, no agent in the fleet can write to your repo.

---

## The fleet

| Agent | Job | Tools | Writes source |
|---|---|---|---|
| Discovery | What exists, and what rules are undocumented | 6 | no |
| Assessment | Complexity, risk, schema incompatibilities | 5 | no |
| Planning | Dependencies, phases, three costed tiers | 4 | no |
| Execution | Writes the migrated code | 9 | **yes, after approval** |
| Validation | Tests it, reports regressions | 7 | no |

Validation can run tests but cannot edit code. That is why a repair has to cross
an agent boundary — and why that hop shows up in the trace.

---

## Layout

```
docs/          the design, start at docs/README.md
legacy/        the demo app, with three planted traps
agents/        roles.py defines all five; build.py generates them
run/           the harness: fleet, spine, approve, execute, validate, deploy
scoring/       deterministic readiness score, no LLM
fixtures/      the behavioural baseline
```

## Docs

- [The problem and the 7 diff points](docs/01-problem-and-diff.md)
- [Architecture](docs/02-architecture.md)
- [Inputs and context](docs/03-inputs-and-context.md) — repo, aim, Jira, OpenAPI, `stackshift.json`
- [The approval portal and tiers](docs/04-approval-portal.md)
- [Developer experience](docs/05-developer-experience.md)
- [Where we use Nasiko](docs/06-nasiko-map.md)
- [Findings — what we measured, including what failed](docs/09-findings.md)
- [Build checklist and how to run each part](docs/TODO.md)

## Status

Hackathon build. The local pipeline works end to end; all five agents are
deployed and running on Nasiko. Known gaps — deployed agents can't share
artifacts, per-agent cost isn't attributed, no web portal — are written up
honestly in [docs/09-findings.md](docs/09-findings.md).
