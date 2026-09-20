# 4. Developer experience

The test: **would a developer use this twice?**

Most code-gen tools fail that test because they produce a large diff with no
explanation and no way to check it. Here's how we avoid that.

---

## The whole journey

```
 1. point it at a repo          ~10 sec
 2. watch discovery             ~90 sec   ← already useful, nothing written yet
 3. pick a tier                 your call  ← costs shown up front
 4. review the plan             ~2 min     ← we flag where it'll go wrong
 5. approve                     1 click    ← this is what grants write access
 6. watch it work               live trace
 7. read the readiness report   computed, not claimed
 8. review the branch           normal git diff, normal PR
```

Steps 1–4 are read-only. A developer can run discovery on a repo out of pure
curiosity and get a list of undocumented business rules for free.

---

## Five DX principles

### 1. Nothing happens to your code without a click

No "and then it opened a PR". The approval gate is real, and it's enforced by
permissions rather than by good intentions.

### 2. Show the price before the work

Every tier shows tokens, dollars, runtime and risk **before** you commit. A dev
who is 20 minutes from a demo picks Tier 1. A dev with a week picks Tier 3. Both
are correct; only they know which.

### 3. Stream findings, don't spin

```
  ▸ found: VIP discount rule, undocumented        pricing.py:47
  ▸ found: OrderService → InventoryService        orders.py:112
  ▸ warn:  no test coverage on payments/          payments/
```

Every line names a file. A progress bar tells you nothing; this tells you what
it learned.

### 4. Every claim is clickable

The readiness report is not a summary, it's an index. "3 behavior mismatches"
expands to the three rules, each with the legacy file:line it came from, the
input that broke it, and the two different outputs.

### 5. Output is a normal git branch

Not a ZIP. Not a chat window. A branch you review with `git diff` and the same
eyes you'd use on a colleague's PR.

```bash
git checkout migration/fastapi-orders
git diff main --stat
pytest
```

If the developer's existing habits work on our output, we've done our job.

---

## What the output actually contains

```
migration/fastapi-orders
├── src/                      the migrated code
├── tests/
│   ├── contract/             one test per API endpoint
│   └── behavior/             one test per discovered business rule  ← the good part
├── Dockerfile
├── docker-compose.yml
└── MIGRATION.md              what changed, what was validated, what failed
```

`tests/behavior/` is the differentiator. Each test traces back to a rule Discovery
found in the legacy code:

```python
def test_vip_discount_above_5000():
    """Legacy rule: services/pricing.py:47
    VIP customers receive 15% discount on orders above ₹5,000."""
    assert price(customer=VIP, total=7200) == 6120
```

The docstring cites the legacy source. A reviewer can check the rule was real.

---

## Failure UX — the part most tools get wrong

Things will fail. What matters is what the developer sees when they do.

| What happens | What we show |
|---|---|
| Behavior regression found | The rule, the input, legacy output vs new output, side by side |
| Repair loop hits the cap | "Stopped after 3 attempts — needs a human" + what it tried each time |
| An agent errors | Which agent, which step, the trace link, what the previous steps produced |
| Migration only partly works | Partial branch + honest readiness score. Never "✓ complete" |

**We never claim success we can't evidence.** A 61% readiness score with three
named blockers is more useful than a green checkmark that's lying.

### The behavior diff is the money shot

```
  TEST 127 · VIP discount with coupon
  ─────────────────────────────────────
  input      customer=VIP  total=₹7200  coupon=SAVE10

  LEGACY     discount 15%   coupon rejected   final ₹6120
  MIGRATED   discount 15%   coupon ACCEPTED   final ₹5508
                            ^^^^^^^^^^^^^^^

  ❌ REGRESSION — legacy rejects coupons stacked on VIP discount
     source: services/pricing.py:52
     → sent to Execution for repair (attempt 1 of 3)
```

That single screen is the strongest argument for the whole project. No syntax
checker finds this. No test suite that didn't exist finds this. Show it.

---

## CLI, for developers who won't use a web UI

```bash
stackshift scan   github.com/acme/acme-orders     # discovery only, read-only
stackshift plan   --to fastapi+postgres           # prints the 3 tiers
stackshift run    --tier 2 --approve              # explicit approval flag
stackshift status                                 # live progress
stackshift report                                 # the readiness card
```

`--approve` is required and has no default. You cannot accidentally run a
migration by forgetting a flag.
