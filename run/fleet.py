#!/usr/bin/env python3
"""Run the StackShift agent fleet locally over A2A.

This is the local harness. It talks to each agent exactly the way Nasiko's
proxy does — same JSONRPC, same A2A-Version header — so behaviour here matches
behaviour once the fleet is deployed to the control plane.

    python3 run/fleet.py up                    start all five agents
    python3 run/fleet.py down                  stop them
    python3 run/fleet.py ask discovery "..."   send one agent a task
    python3 run/fleet.py status                what is running

The workspace is mounted into every agent, so artifacts written by one agent
are readable by the next. That shared workspace is how the fleet passes
structured findings between steps without relying on chat summaries.
"""

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.join(ROOT, ".runs", "demo", "workspace")

# Port per role. Execution deliberately last: it is the only one that writes.
AGENTS = {
    "discovery": 10010,
    "assessment": 10011,
    "planning": 10012,
    "execution": 10013,
    "validation": 10014,
}

A2A_HEADERS = {
    "Content-Type": "application/json",
    # a2a-sdk 1.1.0 defaults a missing header to protocol 0.3 and then rejects
    # the call. The header is not optional.
    "A2A-Version": "1.0",
}


def _env_from_nasiko():
    """Read the LLM credentials from the running Nasiko stack's .env."""
    env_path = os.path.join(os.path.dirname(ROOT), "nasiko", ".env")
    wanted = ("OPENAI_API_KEY", "OPENAI_BASE_URL", "OPENAI_MODEL")
    found = {}
    if os.path.isfile(env_path):
        with open(env_path) as fh:
            for line in fh:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, val = line.partition("=")
                    if key in wanted:
                        found[key] = val
    for key in wanted:
        if key in os.environ:
            found[key] = os.environ[key]
    missing = [k for k in wanted if k not in found]
    if missing:
        sys.exit("missing LLM config: %s" % ", ".join(missing))
    return found


def up():
    env = _env_from_nasiko()
    os.makedirs(WORKSPACE, exist_ok=True)
    print()
    for name, port in AGENTS.items():
        container = "ss-%s" % name
        subprocess.run(["docker", "rm", "-f", container],
                       capture_output=True, check=False)
        cmd = ["docker", "run", "-d", "--name", container,
               "-p", "%d:8000" % port,
               "-v", "%s:/workspace" % WORKSPACE]
        for key, val in env.items():
            cmd += ["-e", "%s=%s" % (key, val)]
        cmd.append("stackshift-%s:latest" % name)
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            print("  FAILED %-12s %s" % (name, proc.stderr.strip()[:90]))
        else:
            print("  started %-12s :%d" % (name, port))
    print()
    _wait_ready()


def _wait_ready(timeout=60):
    deadline = time.time() + timeout
    pending = dict(AGENTS)
    while pending and time.time() < deadline:
        for name, port in list(pending.items()):
            try:
                url = "http://localhost:%d/.well-known/agent-card.json" % port
                with urllib.request.urlopen(url, timeout=3) as resp:
                    card = json.load(resp)
                print("  ready   %-12s %s" % (name, card.get("name", "?")))
                del pending[name]
            except Exception:
                pass
        if pending:
            time.sleep(2)
    print()
    if pending:
        print("  NOT READY: %s" % ", ".join(pending))
        return False
    print("  fleet up (%d agents)\n" % len(AGENTS))
    return True


def down():
    for name in AGENTS:
        subprocess.run(["docker", "rm", "-f", "ss-%s" % name],
                       capture_output=True, check=False)
    print("\n  fleet down\n")


def status():
    print()
    for name, port in AGENTS.items():
        try:
            url = "http://localhost:%d/.well-known/agent-card.json" % port
            with urllib.request.urlopen(url, timeout=3) as resp:
                json.load(resp)
            state = "up"
        except Exception:
            state = "down"
        print("  %-12s :%-6d %s" % (name, port, state))
    print()


def ask(agent, prompt, timeout=900):
    """Send one task to one agent. Returns its final text."""
    if agent not in AGENTS:
        sys.exit("unknown agent %r; choose from %s" % (agent, ", ".join(AGENTS)))
    payload = {
        "jsonrpc": "2.0", "id": "1", "method": "SendMessage",
        "params": {"message": {
            "role": "ROLE_USER",
            "parts": [{"text": prompt}],
            "messageId": "m-%d" % int(time.time()),
        }},
    }
    req = urllib.request.Request(
        "http://localhost:%d/" % AGENTS[agent],
        data=json.dumps(payload).encode(), headers=A2A_HEADERS,
    )
    started = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.load(resp)
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc), "seconds": time.time() - started}

    if "error" in body:
        return {"ok": False, "error": body["error"], "seconds": time.time() - started}

    texts = []

    def walk(node):
        if isinstance(node, dict):
            if "text" in node and isinstance(node["text"], str):
                texts.append(node["text"])
            for val in node.values():
                walk(val)
        elif isinstance(node, list):
            for val in node:
                walk(val)

    walk(body.get("result", {}).get("task", {}).get("artifacts", []))
    return {
        "ok": True,
        "text": texts[-1] if texts else "",
        "seconds": round(time.time() - started, 1),
    }


def artifacts():
    path = os.path.join(WORKSPACE, ".stackshift")
    if not os.path.isdir(path):
        return []
    return sorted(os.listdir(path))


def ask_expecting(agent, prompt, expect, attempts=2):
    """Ask, then verify the named artifacts actually landed on disk.

    Models reliably describe the JSON they would write instead of calling
    write_artifact. The prompt says not to; this makes it not matter. If an
    expected artifact is missing we say exactly which one and ask again, rather
    than discovering the gap in a later agent that cannot recover from it.
    """
    result = None
    for attempt in range(1, attempts + 1):
        result = ask(agent, prompt)
        if not result["ok"]:
            return result
        missing = [name for name in expect
                   if not os.path.isfile(os.path.join(WORKSPACE, ".stackshift", name))]
        result["missing"] = missing
        result["attempts"] = attempt
        if not missing:
            return result
        if attempt < attempts:
            print("    [%s] %s not written, asking again"
                  % (agent, ", ".join(missing)))
            prompt = (
                "You did not call write_artifact, so nothing was delivered. "
                "Your analysis is not lost — repeat it now as a write_artifact "
                "call for each of: %s. Content must be valid JSON. Do nothing "
                "else." % ", ".join(missing)
            )
    return result


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    cmd = args[0]
    if cmd == "up":
        up()
    elif cmd == "down":
        down()
    elif cmd == "status":
        status()
    elif cmd == "ask":
        if len(args) < 3:
            sys.exit("usage: fleet.py ask <agent> <prompt>")
        result = ask(args[1], " ".join(args[2:]))
        if not result["ok"]:
            print("\n  ERROR: %s\n" % result["error"])
            return 1
        print("\n%s\n" % result["text"])
        print("  (%ss, artifacts: %s)\n"
              % (result["seconds"], ", ".join(artifacts()) or "none"))
    else:
        print(__doc__)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
