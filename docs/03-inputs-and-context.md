# 3. Inputs and context

**One input is required: the repo. Everything else is optional and makes the
migration better.**

The repo tells you what the code *does*. It doesn't tell you what the org *knows* —
which endpoints actually get traffic, which module is already being rewritten,
which bug everyone works around, why that weird branch in `pricing.py` exists.

That knowledge sits in Jira, in Confluence, in the OpenAPI spec, in the runbook,
in last month's incident. Every one of those we can link in makes the plan less of
a guess.

---

## Two audiences, two shapes

Worth separating, because they want different things from the same product.

| | **Developer** | **Organization** |
|---|---|---|
| Scope | One repo | A portfolio of repos |
| Question | "Get me off Flask" | "What's our Python 2 exposure, and what'll it cost?" |
| Wants | Speed, CLI, a branch to review | Standards, budget caps, an audit trail |
| Approval | Themselves | Architect approves what a dev proposes |
| Input style | CLI flags, a form | `stackshift.json` in the repo, run by CI |
| Success | Tests pass, PR merged | Compliance closed, cost predicted correctly |

The design serves both by making every input **optional, declarative and
machine-readable** — a dev types three flags, an org commits a JSON file.

---

## Tier 0 — required

### The repository

```
github.com/acme/acme-orders @ main
```

The only hard requirement. Everything else degrades gracefully.

### The aim — free text, and this matters more than it looks

```
"Python 3.8 goes EOL in March and we fail the security audit.
 Need off it without a redesign — the team is 4 people."
```

Most tools throw this away. We don't, because it answers questions the code
can't:

- *"without a redesign"* → recommend **Tier 1**, not Tier 2
- *"team is 4 people"* → **rule Tier 3 out**. Four people should not run nine services
- *"March"* → prefer incremental phases that ship, over a big-bang rewrite
- *"security audit"* → dependency CVEs are in scope; performance isn't

The aim drives the **recommended** tier. Without it we'd recommend by repo size,
which is the wrong variable.

---

## Tier 1 — optional context, in order of value

Each row says what it unlocks. This is the ranking to build in.

| Source | What it unlocks | Value |
|---|---|---|
| **OpenAPI / Swagger spec** | Contract tests become *provable* instead of inferred. The single highest-value input after the repo | ⭐⭐⭐ |
| **Production logs / traffic sample** | Real payloads become behavior-test fixtures. Tests with real inputs beat tests with invented ones | ⭐⭐⭐ |
| **APM / observability** (Datadog, Grafana) | Which endpoints are actually *used*. "37 endpoints, 9 get zero traffic — don't migrate those" | ⭐⭐⭐ |
| **Jira / Linear** | Known bugs, tech-debt backlog, what's already being rewritten. Stops us migrating a module that's being deleted next sprint | ⭐⭐ |
| **DB schema dump / migrations dir** | Ground truth for the data model, including constraints the ORM hides | ⭐⭐ |
| **Existing tests + CI config** | A baseline to preserve, plus the real target runtime and Python version | ⭐⭐ |
| **Confluence / Notion / `docs/`** | Architecture docs, ADRs, runbooks. Gives Discovery a prior to confirm or contradict | ⭐⭐ |
| **Incident history / postmortems** | Where it breaks *in practice* — exactly where to be careful | ⭐⭐ |
| **CODEOWNERS / team map** | Who owns what. Decides whether a service split is even viable | ⭐ |
| **IaC (Terraform, Helm)** | Target environment constraints. No point emitting Postgres 16 if the org runs 13 | ⭐ |
| **Compliance context** (PCI, HIPAA, SOC2) | Changes what's allowed: where data lives, what gets logged, what needs an audit trail | ⭐ |

### The three that change the answer most

**OpenAPI spec** — without it, "did the API stay compatible?" is inferred from
reading route decorators. With it, it's a checked contract. API compatibility
confidence goes from ~70% to ~95%.

**APM traffic data** — the best migration is the one you don't do. If 9 of 37
endpoints have had zero calls in 90 days, the honest plan is *delete them*, and
that's a cheaper, faster, lower-risk migration. No amount of code-reading gets
you this.

**Jira** — twice useful. It stops wasted work ("don't migrate `reporting/`, it's
being replaced"), and it lets us **link migration phases to existing tickets** so
the plan lands in a backlog the team already uses instead of a PDF nobody reads.

---

## Context completeness — show the gap, don't hide it

Rather than silently doing worse with less, we show what's missing and what it
would buy:

```
  CONTEXT COMPLETENESS  ████████░░░░░░░░  42%

  ✓ Repository              connected
  ✓ docs/ folder            8 files indexed
  ✓ CI config               .github/workflows/ci.yml
  ✗ OpenAPI spec            → would raise API confidence 70% → 95%
  ✗ Jira                    → would flag modules already being rewritten
  ✗ Production traffic      → would identify unused endpoints (est. 9 of 37)

  You can proceed at 42%. Linking the OpenAPI spec is the biggest single win.
```

Two reasons this is good DX:

1. **Never blocks.** You can always run with just a repo
2. **Makes the ask concrete.** "Link Jira" is annoying; "linking Jira stops you
   migrating a module that's being deleted" is persuasive

Confidence numbers in the readiness report are **capped by context completeness** —
we won't claim 95% API compatibility when we never saw a contract.

---

## The JSON input — configuration as code

Everything the UI collects is really just this file. Devs can skip the UI entirely;
orgs commit it and run it from CI.

```json
{
  "$schema": "https://stackshift.dev/schema/v1.json",
  "version": "1",

  "source": {
    "repo": "github.com/acme/acme-orders",
    "branch": "main",
    "scope": ["src/orders/**", "src/pricing/**"],
    "exclude": ["**/vendor/**", "**/migrations/**"]
  },

  "aim": "Python 3.8 EOL in March, failing security audit. No redesign, 4-person team.",

  "target": {
    "framework": "fastapi",
    "database": "postgresql",
    "workers":   "async",
    "packaging": "docker",
    "tests":     "contract+behavior"
  },

  "constraints": {
    "preserve_api_behavior": true,
    "allow_breaking_changes": false,
    "python_version": "3.12",
    "max_cost_usd": 2.50,
    "max_runtime_minutes": 15
  },

  "context": {
    "openapi":    { "path": "docs/openapi.yaml" },
    "docs":       { "path": "docs/**/*.md" },
    "schema":     { "path": "db/schema.sql" },
    "jira":       { "connector": "jira",       "project": "ORD", "optional": true },
    "confluence": { "connector": "confluence", "space": "ENG",   "optional": true },
    "traffic":    { "path": "data/access-log-sample.jsonl",       "optional": true }
  },

  "approval": {
    "required": true,
    "tier": null,
    "approvers": ["@acme/architects"]
  },

  "guardrails": {
    "allowed_targets": ["fastapi", "litestar"],
    "forbidden": ["microservices"],
    "require_behavior_tests": true
  }
}
```

### Why JSON matters more than the UI

- **Repeatable** — same input, same migration. A UI form isn't reproducible
- **Reviewable** — it's a PR. Your architect reviews the *migration config* before
  anything runs
- **CI-runnable** — `stackshift run --config stackshift.json` in a pipeline
- **Portfolio-scale** — 40 repos, 40 files, one dashboard. This is the org story
- **Diffable** — "what changed between the plan we approved and the one that ran?"

### `guardrails` is the org block

The bit that turns a developer tool into something a platform team will adopt:

- `allowed_targets` — only stacks the org actually supports
- `forbidden` — "no microservices without architecture review"
- `require_behavior_tests` — can't skip validation to go faster
- `max_cost_usd` — a hard ceiling; the run aborts rather than overspending

A developer can propose anything. Guardrails decide what's approvable.

---

## How context reaches the agents — and why that's a Nasiko story

Jira and Confluence are **real Nasiko connectors** (`server/src/seed.rs`), reachable
through the MCP gateway over OAuth. So the wiring is:

```
  Discovery agent
        │
        ▼
  Nasiko MCP Gateway  ──►  Jira      (OAuth, read-only scope)
        │                  Confluence
        │                  GitHub
        ▼
  permission-filtered tool surface
```

Three consequences worth saying out loud:

1. **No credentials in agent code.** The agent calls a tool; Nasiko holds the token.
   Grep the agent source — there's nothing to leak
2. **Read-only by scope.** Discovery gets Jira *read*. It cannot comment on your
   tickets or move your cards. That's the ACL, not a prompt
3. **Adding a source doesn't mean rebuilding agents.** Connect it in Nasiko, and
   the tool appears in the agent's filtered surface

> **Line for the pitch:** "Every one of these sources needs a token. Not one of
> them is in our code. Nasiko's MCP gateway holds them and hands agents a
> permission-filtered tool surface — Discovery can read Jira, it cannot write to it."

### Redaction, before anyone asks

Production logs and tickets contain customer data.

- Traffic samples are **redacted and sampled** before becoming fixtures — shapes
  and edge cases, not real people
- Ticket bodies are summarized to findings; raw text isn't retained
- What we send to the model is listed in the run's evidence trail, so "what did
  you send to an LLM?" has an actual answer

---

## Today's build

Be clear about what's real this afternoon — see [07-build-plan.md](07-build-plan.md).

| Input | Today |
|---|---|
| Repo | ✅ |
| Aim (free text) | ✅ — feeds the tier recommendation |
| `docs/` folder | ✅ — plain file reads |
| `stackshift.json` | ✅ — this *is* the input mechanism; the UI is post-hackathon |
| OpenAPI spec | ⚠️ if the demo repo has one |
| Jira / Confluence | ❌ **architecture only** — connectors exist, OAuth setup doesn't fit today. Show the wiring on a slide, don't fake a connection |
| Traffic / APM | ❌ post-hackathon |
| Guardrails enforcement | ⚠️ `max_cost_usd` maps to a Nasiko flow guard token cap — that part is real |

**Don't demo a Jira connection you haven't wired.** Say "connectors exist in
Nasiko, here's the design" — that's a credible roadmap. A faked integration that a
judge probes is a bad thirty seconds.
