# 10. Recording the demo

A run recorded once, that worked, beats a live run that might not. The pipeline
is non-deterministic — two identical runs produced a 17-file migration that
repaired cleanly and a 9-file one that hit the flow guard (see
[09-findings.md](09-findings.md)). Record it, then present the recording.

**Input repo:** `https://github.com/pragnyamehar-create/legacy-acme-orders`

**Total runtime:** 12–16 minutes, mostly waiting on agents. Budget 25 minutes
including retakes.

---

## Before you hit record

Run this checklist. Every item has bitten us at least once.

```bash
# 1. Nasiko is up
cd ../nasiko && docker compose ps          # 7/7, server healthy

# 2. Agents are deployed and running
cd ../StackShift && python3 run/deploy.py --list    # 5 running

# 3. Portal is up
python3 portal/server.py                   # leave it running

# 4. Fresh workspace from the real repo
python3 run/ingest.py https://github.com/pragnyamehar-create/legacy-acme-orders

# 5. Agents restarted against that workspace, all read-only
python3 run/fleet.py up                    # 5 agents, "workspace read-only"
```

Then, in the browser:

- Open `http://localhost:7700`
- Pick your theme — **dark reads better on a projector**, light reads better in
  a bright room
- Hard-refresh so the tracker shows all six nodes pending
- Zoom the browser to ~110–125%; the pipeline strip and the log are what people
  need to read
- **Close the `nasiko/.env` tab in your editor.** It has live credentials in it
- Silence notifications

Record the **browser window only**, not the whole screen — a full desktop
capture shows your editor, your dock, and whatever else is open.

---

## The run, beat by beat

Times are from measured runs. Say the line, click the button, wait.

### Beat 1 · The input — 30s

Show the GitHub repo in a tab first. Scroll `services/pricing.py` and
`repositories/order_repo.py` briefly.

> "A ten-year-old Flask and MySQL order service. Twenty-odd files, no real
> documentation, and the people who wrote it have left. We want FastAPI and
> Postgres."

Switch to the portal. The repo URL is already in the field.

**Click `Load repository`.** (~5s)

> "It clones the repo, and picks up two things it happens to ship: a
> `stackshift.json` saying what the team actually wants, and a context folder
> with an OpenAPI spec and architecture notes."

### Beat 2 · Discovery — 90s

**Click `2 · Discover → Assess → Plan`.**

While Discovery runs, talk over it — the log is scrolling and the first node is
pulsing:

> "Three agents, and not one of them can write to your code. They hold read
> tools only. Right now it's reading every service and repository file."

When the findings land, read one out:

> "It found a rule nobody wrote down — VIP customers get 15% off above ₹5,000.
> And this one: an empty `pass` branch that stops coupons stacking on that
> discount. It called it *load-bearing*. A rewrite that tidies that up silently
> changes your pricing.
>
> It also caught that the reorder query depends on MySQL sorting NULLs first,
> which PostgreSQL doesn't."

### Beat 3 · Three costed options — 45s

The tier cards appear on the right.

> "'Modernise my app' isn't one job. Refresh gets you off Flask for about forty
> cents. Restructure rebuilds the architecture. Re-architect splits it into
> services for four dollars and a lot more risk.
>
> Tokens, runtime and risk, before you commit. And the recommendation comes from
> the aim the repo declared — no redesign, four-person team — not from how big
> the codebase is."

### Beat 4 · Approval is a permission — 60s ⭐

**The most important 60 seconds. Rehearse this one twice before recording.**

**Click `3 · Execute without approval`.** Wait ~40s. It writes nothing.

> "Zero files. And look at the error: `read-only file system`. That isn't the
> agent politely declining — the workspace isn't mounted writable. It cannot
> write, whatever it decides it wants to do."

Point at the header chip: `execution: read-only`.

**Click `Approve Tier 1`.** The chip flips to `read-write` and goes green.

> "Approving restarts that one agent with a writable workspace. On Nasiko the
> same boundary is an ACL grant. Nothing changed in our code — a permission
> changed."

**Click `4 · Execute`.** (~60–90s)

> "Same operation. Now it works."

### Beat 5 · It checks its own work — 4–8 min

**Click `5 · Validate & repair`.**

This is the long one. Talk over the first minute, then let it run.

> "Validation reads the migrated code against the rules Discovery found. It can
> run tests and it cannot edit code — deliberately. So when it finds something,
> it has to hand it back to the Execution agent. That hand-off is an
> agent-to-agent call, and it's bounded: three attempts, then the control plane
> stops it."

Whichever way it goes, you have a story:

- **Repairs cleanly** → "found the regressions, fixed them, re-checked."
- **Hits the cap** → "it didn't converge, so the flow guard stopped it and
  escalated. That's the difference between a system that repairs itself and one
  that bills you all night."

### Beat 6 · Proof, not opinion — 60s

**Click `6 · Parity check`.**

> "This asks no agent anything. It imports the old pricing module and the new
> one, runs the same inputs through both, and compares. Ten out of ten,
> including the undocumented coupon rule."

Then point at the readiness score.

> "And it won't claim success it hasn't earned — sixty percent, do not merge
> yet, because there are no tests. That number is arithmetic over counted
> evidence, in a file you can read. No model produced it."

### Beat 7 · The control plane — 30s

Switch to `http://localhost:8080`.

> "All five agents run on Nasiko. Every hop is traced, the fleet is governed by
> it, and the repair loop is bounded by its flow guards."

Show **Agents** (5 running), then **Observability**.

**Do not open FinOps** — per-agent cost reads $0 on this build.

---

## Recording commands

I could not start the recording myself: macOS Screen Recording permission is not
granted to the process running these commands, and `screencapture -v` produces
no file.

**QuickTime** is the reliable route: File → New Screen Recording → select the
browser window → record.

**From the terminal**, once you have granted your terminal app Screen Recording
in System Settings → Privacy & Security:

```bash
# whole screen, ctrl-c to stop
screencapture -v ~/Desktop/stackshift-demo.mov

# pick a window interactively
screencapture -v -w ~/Desktop/stackshift-demo.mov
```

Check it produced a file — a blocked recording fails silently:

```bash
ls -lh ~/Desktop/stackshift-demo.mov
```

---

## If something breaks mid-take

| Symptom | Do this |
|---|---|
| A stage hangs | `Stop`, then re-click it. Agents are idempotent |
| Tracker looks stale | Hard-refresh; it polls every 5s when idle |
| Tiers don't appear | Planning didn't write its artifact. Re-run stage 2 |
| Approve does nothing | `docker ps` — `ss-execution` restarting takes ~5s |
| Everything is confused | `python3 run/ingest.py <url>` then `python3 run/fleet.py up`, start again |

**Do not debug on camera.** Stop the recording, fix it, start the take again.

---

## Cut it down

If you need a 3-minute version, record only **beats 2, 4 and 6**: the
undocumented rule, the denied-then-granted approval, and the parity proof. Those
three carry the argument on their own.
