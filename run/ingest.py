#!/usr/bin/env python3
"""Load a legacy repository into the run workspace.

    python3 run/ingest.py https://github.com/pragnyamehar-create/legacy-acme-orders
    python3 run/ingest.py --local legacy/acme-orders

Clones the repo, then wires up whatever it happens to carry:

  stackshift.json   its `aim` becomes the aim the Planning agent reasons about,
                    so the recommendation follows the repo owner's stated
                    constraints rather than a default baked into our harness
  context/          copied to the workspace's context folder, so an OpenAPI
                    spec or architecture note the repo already ships is treated
                    the same as one a user drags into the portal

Everything is optional. A bare repo with none of it still runs.
"""

import json
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.join(ROOT, ".runs", "demo", "workspace")
LEGACY = os.path.join(WORKSPACE, "legacy")
CONTEXT = os.path.join(WORKSPACE, "context")
AIM_FILE = os.path.join(WORKSPACE, ".stackshift", "aim.txt")


def fresh_workspace():
    shutil.rmtree(os.path.join(ROOT, ".runs", "demo"), ignore_errors=True)
    for path in (LEGACY, CONTEXT, os.path.join(WORKSPACE, "migrated"),
                 os.path.join(WORKSPACE, ".stackshift")):
        os.makedirs(path, exist_ok=True)
    fixture = os.path.join(ROOT, "fixtures", "expected_behavior.json")
    if os.path.isfile(fixture):
        shutil.copy(fixture, WORKSPACE)


def clone(url, dest):
    proc = subprocess.run(
        ["git", "clone", "--depth", "1", url, dest],
        capture_output=True, text=True, timeout=300,
        env=dict(os.environ, GIT_TERMINAL_PROMPT="0"),
    )
    if proc.returncode != 0:
        sys.exit("clone failed: %s" % (proc.stderr.strip()[:300]))


def adopt(source_name):
    """Pull the repo's own config and context into the workspace."""
    notes = []

    # Record where this came from BEFORE dropping .git. The portal reads
    # repo_info.json; without it, a lookup of remote.origin.url walks up out of
    # the deleted legacy/.git and reports StackShift's own origin instead.
    info = {
        "url": source_name,
        "name": source_name.rstrip("/").split("/")[-1].replace(".git", ""),
        "source": "local" if source_name.startswith(("legacy/", "./", "/")) else "github",
    }
    os.makedirs(os.path.join(WORKSPACE, ".stackshift"), exist_ok=True)
    with open(os.path.join(WORKSPACE, ".stackshift", "repo_info.json"), "w") as fh:
        json.dump(info, fh, indent=2)

    # Its git history is not part of what we analyse, and it confuses the
    # agents' file listings.
    shutil.rmtree(os.path.join(LEGACY, ".git"), ignore_errors=True)

    config_path = os.path.join(LEGACY, "stackshift.json")
    aim = None
    if os.path.isfile(config_path):
        try:
            with open(config_path) as fh:
                config = json.load(fh)
            aim = config.get("aim")
            notes.append("stackshift.json: %s -> %s" % (
                (config.get("source") or {}).get("framework", "?"),
                (config.get("target") or {}).get("framework", "?")))
        except ValueError:
            notes.append("stackshift.json present but not valid JSON — ignored")

    if aim:
        os.makedirs(os.path.dirname(AIM_FILE), exist_ok=True)
        with open(AIM_FILE, "w") as fh:
            fh.write(aim)
        notes.append("aim taken from the repo")

    repo_context = os.path.join(LEGACY, "context")
    if os.path.isdir(repo_context):
        for name in sorted(os.listdir(repo_context)):
            src = os.path.join(repo_context, name)
            if os.path.isfile(src):
                shutil.copy(src, os.path.join(CONTEXT, name))
        notes.append("%d context document(s) adopted"
                     % len(os.listdir(repo_context)))

    return notes, aim


def summarise():
    counts = {}
    for dirpath, dirs, files in os.walk(LEGACY):
        dirs[:] = [d for d in dirs if d not in (".git", "__pycache__")]
        for name in files:
            counts[os.path.splitext(name)[1] or "(none)"] = \
                counts.get(os.path.splitext(name)[1] or "(none)", 0) + 1
    return counts


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1

    fresh_workspace()

    if args[0] == "--local":
        src = os.path.join(ROOT, args[1])
        if not os.path.isdir(src):
            sys.exit("no such directory: %s" % src)
        shutil.rmtree(LEGACY, ignore_errors=True)
        shutil.copytree(src, LEGACY)
        origin = os.path.relpath(src, ROOT)
    else:
        origin = args[0]
        shutil.rmtree(LEGACY, ignore_errors=True)
        print("\n  cloning %s ..." % origin)
        clone(origin, LEGACY)

    notes, aim = adopt(origin)
    counts = summarise()

    print()
    print("  INGESTED  %s" % origin)
    print("  " + "-" * 60)
    total = sum(counts.values())
    print("  %d files: %s" % (total, ", ".join(
        "%s×%d" % (k, v) for k, v in sorted(counts.items(), key=lambda x: -x[1])[:8])))
    for note in notes:
        print("  + %s" % note)
    if aim:
        print()
        print("  AIM (from the repo, drives the tier recommendation):")
        for line in [aim[i:i + 66] for i in range(0, len(aim), 66)]:
            print("    %s" % line)
    print()
    print("  Next:  python3 run/spine.py     (or stage 2 in the portal)")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
