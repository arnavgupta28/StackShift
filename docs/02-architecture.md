# 2. Architecture

## The shape

Two layers. We build the top one; Nasiko **is** the bottom one.

```
┌──────────────────────────────────────────────────────────────┐
│  STACKSHIFT PORTAL          (we build)                        │
│  repo input · tier cards · approval gate · readiness report   │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  AGENTIC LAYER             (we build — 5 agents)              │
│                                                               │
│   Discovery → Assessment → Planning ⏸ APPROVAL ⏸             │
│                                       │                       │
│                                  Execution ⇄ Validation       │
└───────────────────────────┬──────────────────────────────────┘
                            │
┌───────────────────────────▼──────────────────────────────────┐
│  CONTROL PLANE             (Nasiko — off the shelf)           │
│  routing · A2A proxy · ACL · flow guards · traces · cost      │
└──────────────────────────────────────────────────────────────┘
```

This maps 1:1 onto the BlueCloud reference architecture in
[`assets/agentic_migration_framework.png`](../assets/agentic_migration_framework.png):

| Reference architecture | Ours |
|---|---|
| Migration Command Center | StackShift portal + Nasiko dashboard |
| Agent Orchestrator | Nasiko router + MAF workflows |
| Config Management & Policy Engine | Nasiko ACL + flow guards + secrets |
| Discovery / Assessment / Planning / Execution / Validation Agents | same five names |

> **Say this on stage:** "This is a known reference architecture. The control plane
> is normally the part you'd spend six months building. We got it off the shelf."

> **Careful:** the reference diagram is about *data* migration (Oracle, warehouses).
> Ours migrates *code*. Don't promise database migration you aren't doing.

---

## The five agents

Each is a fork of Nasiko's `agents/coding`, which already ships a ReAct loop and
file tools. The fork changes two things: the **system prompt** (its job) and the
**tool list** (its authority).

| Agent | Job | Tools | Can write? |
|---|---|---|---|
| **Discovery** | Inventory the repo. Extract undocumented business rules. | `read_file` `list_directory` `glob` | ❌ |
| **Assessment** | Score complexity and risk per module. Profile the data model. | `read_file` `list_directory` | ❌ |
| **Planning** | Dependency graph, impact ranking, phased strategy, the 3 tiers. | `read_file` `list_directory` | ❌ |
| **Execution** | Write the new code on a migration branch. | `read_file` `edit_file` `list_directory` `glob` `run_command` | ✅ *after approval* |
| **Validation** | Run tests. Compare behavior to the contract. Report regressions. | `read_file` `run_command` `list_directory` | ❌ |

Two deliberate design choices:

- **Validation cannot edit.** It has to hand findings back to Execution. That hop
  is the multi-agent story, and it's visible in the trace.
- **Execution holds no write grant until approval.** The approval click is what
  grants it. See [04-approval-portal.md](04-approval-portal.md).

---

## How they're wired

### The spine — a straight line (MAF)

```
Discovery ──► Assessment ──► Planning
```

Runs as a Nasiko MAF workflow. One `context_id`, so the whole thing is one trace.

### The repair loop — NOT MAF

```
Execution ⇄ Validation     (direct A2A calls)
```

**This is the single most important technical correction in the design.**

Nasiko's MAF is strictly linear. In `orchestrator/src/maf/types.rs`:

```rust
pub struct MafDefinition {
    pub steps: Vec<MafStep>,   // a list. that's it.
}
```

and `executor.rs` is a flat `for` over those steps. No branching, no conditionals,
no back-edge. **You cannot express a repair loop as a MAF workflow.**

So the loop runs as direct agent-to-agent calls instead. This turns out to be
better, because flow guards only apply to A2A hops — which means the loop is
genuinely bounded by the control plane:

```
NASIKO_FLOW_MAX_DEPTH=6      NASIKO_FLOW_MAX_FAN_OUT=8
NASIKO_FLOW_MAX_TOKENS=...   NASIKO_FLOW_TIMEOUT_SECS=600
```

Attempt 4 hits the cap and Nasiko kills the chain. **Demo that on purpose.**

---

## Data passed between agents

Agents exchange JSON files in the workspace, not prose. Prose is where multi-agent
systems quietly lose information.

```
system_map.json         Discovery  → what exists: modules, endpoints, tables, deps
behavior_contract.json  Discovery  → the rules, each with file:line evidence
assessment.json         Assessment → per-module complexity + risk scores
migration_plan.json     Planning   → the 3 tiers, phases, files touched, estimates
validation_report.json  Validation → pass/fail per rule, per contract, per test
readiness.json          score.py   → the final number (computed, not generated)
```

Why files and not chat: MAF summarizes each step's output with an LLM call before
passing it on (see `executor.rs`). Anything you need to survive intact must be
written to disk, not left in the message.

---

## Why 5 agents and not 8

The original vision had 8+ (separate Behavior, Dependency, DB, Worker, Config,
Root Cause agents). Each agent is a container build and a deploy. Folded down:

- Behavior Archaeologist → **Discovery**'s prompt
- Dependency & Impact → **Planning**'s prompt
- DB / Worker / Config specialists → **Execution** handles all three
- Root Cause → **Validation** emits the diagnosis with the failure

The five names also match the reference architecture, which makes the slide easier.
