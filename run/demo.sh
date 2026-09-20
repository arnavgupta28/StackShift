#!/usr/bin/env bash
# The full StackShift demo, in order, with pauses between beats.
#
#   ./run/demo.sh            step through it, pausing between beats
#   ./run/demo.sh --fast     no pauses
#   ./run/demo.sh --reset    wipe the run workspace and start clean
#
# Beats 1-6 match docs/08-demo-script.md.

set -u
cd "$(dirname "$0")/.."

FAST=0
for arg in "$@"; do
  case "$arg" in
    --fast) FAST=1 ;;
    --reset)
      rm -rf .runs/demo
      mkdir -p .runs/demo/workspace/migrated
      cp -r legacy/acme-orders .runs/demo/workspace/legacy
      cp fixtures/expected_behavior.json .runs/demo/workspace/
      echo "  workspace reset"
      ;;
  esac
done

beat() {
  echo
  echo "=================================================================="
  echo "  $1"
  echo "=================================================================="
  if [ "$FAST" -eq 0 ]; then
    printf '  [enter to run] '
    read -r _
  fi
}

beat "0 · The traps are real (no agents involved)"
python3 legacy/verify_traps.py || exit 1

beat "1 · Start the fleet — every agent read-only"
python3 run/fleet.py up || exit 1

beat "2 · Discovery, Assessment, Planning — nothing can write source"
python3 run/spine.py || exit 1

beat "3 · Three costed options for a human to choose from"
python3 run/tiers.py || exit 1

beat "4a · Execution BEFORE approval — refused by the kernel"
python3 run/execute.py --force
echo
echo "  ^ 0 files. Not a prompt declining: errno 30, read-only file system."

beat "4b · Approve — which grants the capability"
python3 run/approve.py --tier 1 || exit 1
python3 run/approve.py --status

beat "4c · Same command again"
python3 run/execute.py || exit 1

beat "5 · Validation finds regressions and hands them back over A2A"
python3 run/validate.py --repair --max-attempts 3 || exit 1

beat "6 · Independent parity — both implementations actually run"
python3 run/parity.py

beat "7 · Readiness, computed not claimed"
python3 scoring/score.py .runs/demo/workspace/.stackshift/validation_report.json

echo
echo "=================================================================="
echo "  Artifacts:  .runs/demo/workspace/.stackshift/"
echo "  Migrated:   .runs/demo/workspace/migrated/"
echo "  Deployed:   python3 run/deploy.py --list"
echo "=================================================================="
echo
