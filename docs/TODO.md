# Build checklist

Status as of **2026-09-20 14:35 IST**. Measurements in
[09-findings.md](09-findings.md); reasoning in [07-build-plan.md](07-build-plan.md).

```
Deadline  2026-09-20 16:30 IST
```

---

## Phase 0 · Foundation ✅ done 13:35

- [x] `.gitignore` covering `.env` and `*resources.yaml`
- [x] Docs committed and pushed
- [x] `legacy/acme-orders/` — 21-file Flask + MySQL + Celery demo app
- [x] All three traps planted **and verified** (`legacy/verify_traps.py`, 3/3)
- [x] `fixtures/expected_behavior.json` — 8 behavioural cases
- [x] `scoring/score.py` — deterministic readiness, no LLM

## Phase 1 · Agents ✅ done 13:45

- [x] `agents/roles.py` — five roles from one definition
- [x] `agents/build.py` — generates five deployable agent dirs
- [x] Tool subsets per role (discovery 6, assessment 5, planning 4, execution 9, validation 7)
- [x] All five images built — **32s for the first, 4.5s for the other four**
- [x] `run/fleet.py` — local A2A harness
- [x] Fallback gate never needed: took the Python template instead of the Rust fork

## Phase 2 · Spine ✅ done 13:59

- [x] `run/spine.py` — discovery → assessment → planning, ~110s
- [x] Discovery found all 3 traps and 8 rules
- [x] Planning recommended Tier 1, justified by the **aim** not repo size
- [x] `run/tiers.py` — tier cards with costs
- [x] `ask_expecting()` — verifies artifacts actually landed

## Phase 3 · Approval + repair ✅ done 14:05

- [x] `run/approve.py` — approval grants the write capability
- [x] Denial verified as `OSError errno 30, read-only file system`
- [x] `run/execute.py` — migrated 17 files, both traps preserved
- [x] `run/validate.py` — repair loop over A2A, bounded at 3
- [x] 10 regressions found → repaired → clean in 1 attempt
- [x] `reject_hollow()` — refuses a false all-clear
- [x] `run/parity.py` — **10/10 cases match**, independent of the agents

## Phase 4 · Nasiko deployment ✅ done 14:25

- [x] `run/deploy.py` — all 5 agents deployed and **running** on Nasiko
- [x] `run/maf.py` — spine as a MAF workflow, ran successfully (225,575 tokens)
- [x] Agents pinned per step (routing put all 3 on validation — see findings)
- [ ] Shared artifact store so deployed steps can pass JSON — **known gap**

## Phase 5 · Evidence and freeze — remaining

- [x] `run/demo.sh` — the whole demo in one command
- [x] [09-findings.md](09-findings.md) — measured results, including failures
- [ ] Screenshot the trace from the Observability dashboard
- [ ] Rehearse the denied → approved sequence (beat 4) twice
- [ ] **Screen-record one full successful run as the fallback**
- [ ] Rehearse the 2-minute pitch out loud

> Stop building at 16:10 regardless of what is unfinished.

---

## Run it

```bash
./run/demo.sh              # whole thing, pausing between beats
./run/demo.sh --fast       # no pauses
./run/demo.sh --reset      # clean workspace first
```

Individually:

```bash
python3 legacy/verify_traps.py      # the traps are real
python3 run/fleet.py up             # start 5 agents, all read-only
python3 run/spine.py                # discovery -> assessment -> planning
python3 run/tiers.py                # the three costed options
python3 run/execute.py --force      # refused: no write grant
python3 run/approve.py --tier 1     # grant it
python3 run/execute.py              # same command, now works
python3 run/validate.py --repair    # find regressions, fix, re-check
python3 run/parity.py               # independent proof
python3 run/deploy.py --list        # what is running on Nasiko
```

---

## The three traps

If you break one while debugging, fix it before moving on. **T3 must survive to
demo time** — it is the database trap the parity story rests on.

| | What | Caught by |
|---|---|---|
| **T1** | VIP discount + the `pass` that stops coupons stacking | Discovery ✅ |
| **T2** | `OrderService` → `InventoryService`, invisible from the API layer | Discovery ✅ |
| **T3** | NULL ordering differs MySQL vs PostgreSQL | Discovery ✅, fixed by Execution ✅ |

## Branches

| Branch | For | State |
|---|---|---|
| `main` | Integrated | ✅ |
| `docs/architecture-and-plan` | The docs | ✅ merged |
| `feat/legacy-demo-repo` | Phase 0 | ✅ merged |
| `feat/agent-fleet` | Phases 1–2 | ✅ merged |
| `feat/approval-and-repair` | Phase 3 | ✅ merged |
| `feat/nasiko-deployment` | Phase 4 | in progress |
