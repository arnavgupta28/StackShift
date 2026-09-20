#!/usr/bin/env python3
"""Deploy the agent fleet to the Nasiko control plane.

    python3 run/deploy.py            deploy all five
    python3 run/deploy.py --list     show what is deployed
    python3 run/deploy.py --grant execution    redeploy with a writable workspace
    python3 run/deploy.py --revoke execution   redeploy read-only

Once deployed the fleet is routable, traced, and governed by Nasiko rather than
by this repo's local harness. The demo repo is baked into each image at
/workspace so a deployed agent has something real to read.

Nasiko's upload API takes a `writable` flag that decides whether the agent gets
a read-write volume at /workspace. That is the same boundary run/approve.py
enforces locally with a mount flag, except here the control plane owns it. So
approving a tier means redeploying the Execution agent with writable=true, and
until that happens its writes fail no matter what it decides to do.

Local harness (run/fleet.py) vs deployed fleet:
  local     full pipeline, shared artifact directory, fastest to iterate on
  deployed  routing, traces, cost, ACL -- the control-plane half of the story
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
NASIKO = os.path.join(os.path.dirname(ROOT), "nasiko")
BASE = os.environ.get("NASIKO_URL", "http://localhost:8080")
BUILD = os.path.join(ROOT, "agents", "build")
LEGACY = os.path.join(ROOT, "legacy", "acme-orders")

ORDER = ["discovery", "assessment", "planning", "execution", "validation"]


def _env_value(key):
    path = os.path.join(NASIKO, ".env")
    if os.path.isfile(path):
        with open(path) as fh:
            for line in fh:
                line = line.strip()
                if line.startswith(key + "="):
                    return line.partition("=")[2]
    return os.environ.get(key, "")


def _api(path, token=None, data=None, method=None, raw=None, ctype=None):
    url = BASE + path
    # `data={}` is a legitimate empty POST body; `if data` would treat it as
    # no body at all and silently downgrade the request to a GET.
    body = raw if raw is not None else (
        json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, method=method or ("POST" if body else "GET"))
    req.add_header("Content-Type", ctype or "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            text = resp.read().decode()
    except urllib.error.HTTPError as exc:
        # The server explains 4xx failures in the body; urllib raises before we
        # would otherwise see it.
        return {"error": "HTTP %s" % exc.code, "detail": exc.read().decode()[:400]}
    try:
        out = json.loads(text)
    except ValueError:
        return {"raw": text}
    # The server wraps payloads as {"data": ..., "message": ..., "status_code": ...}
    # and paginated lists add another {"data": [...], "total": N} inside that.
    # Unwrap both so callers see the object they actually asked for.
    ENVELOPE = {"data", "message", "status_code", "total", "success"}
    while (isinstance(out, dict) and "data" in out
           and not (set(out) - ENVELOPE)):
        out = out["data"]
    return out


def login():
    out = _api("/api/auth/login", data={
        "username": _env_value("ADMIN_USERNAME") or "admin",
        "password": _env_value("ADMIN_PASSWORD"),
    })
    token = out.get("token") or out.get("access_token")
    if not token:
        sys.exit("login failed: %s" % json.dumps(out)[:200])
    return token


def make_zip(role):
    """Zip one generated agent, with the demo repo baked in at legacy/.

    A deployed agent has no bind mount to the developer's machine, so the code
    it is meant to analyse has to travel with it.
    """
    src = os.path.join(BUILD, role)
    if not os.path.isdir(src):
        sys.exit("no build for %s — run: python3 agents/build.py" % role)

    staging = tempfile.mkdtemp(prefix="ss-%s-" % role)
    shutil.copytree(src, os.path.join(staging, "agent"))
    shutil.copytree(LEGACY, os.path.join(staging, "agent", "workspace", "legacy"))

    agent_dir = os.path.join(staging, "agent")
    # Bake the workspace into the image and point the tools at it.
    with open(os.path.join(agent_dir, "Dockerfile"), "a") as fh:
        fh.write("\nCOPY workspace/ /workspace/\n")
        fh.write("RUN mkdir -p /workspace/.stackshift /workspace/migrated\n")

    zip_path = os.path.join(staging, "%s.zip" % role)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for dirpath, _, files in os.walk(agent_dir):
            for name in files:
                full = os.path.join(dirpath, name)
                zf.write(full, os.path.relpath(full, agent_dir))
    return zip_path, staging


def _multipart(fields, filename, payload):
    boundary = "----stackshift%d" % os.getpid()
    out = b""
    for key, val in fields.items():
        out += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n"
                % (boundary, key, val)).encode()
    out += ("--%s\r\nContent-Disposition: form-data; name=\"source\"; "
            "filename=\"%s\"\r\nContent-Type: application/zip\r\n\r\n"
            % (boundary, filename)).encode()
    out += payload + ("\r\n--%s--\r\n" % boundary).encode()
    return out, "multipart/form-data; boundary=%s" % boundary


def deploy(role, token, writable=False):
    zip_path, staging = make_zip(role)
    try:
        with open(zip_path, "rb") as fh:
            payload = fh.read()
        fields = {
            "name": "stackshift-%s" % role,
            "version_tag": "1.0.0",
            "inbound_format": "openai",
            "ports": "8000",
            "writable": "true" if writable else "false",
            "env": json.dumps({
                "OPENAI_API_KEY": _env_value("OPENAI_API_KEY"),
                "OPENAI_BASE_URL": _env_value("OPENAI_BASE_URL"),
                "OPENAI_MODEL": _env_value("OPENAI_MODEL"),
                "WORKSPACE_DIR": "/workspace",
            }),
        }
        if writable:
            # Mount the writable volume somewhere that does NOT hide the baked
            # workspace, or the agent loses the code it is supposed to migrate.
            fields["writable_path"] = "/workspace/migrated"
        body, ctype = _multipart(fields, "%s.zip" % role, payload)
        out = _api("/api/agents/upload", token=token, raw=body, ctype=ctype)
        return out
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def list_agents(token):
    out = _api("/api/agents", token=token)
    items = out if isinstance(out, list) else (out.get("agents") or out.get("items") or [])
    print()
    print("  DEPLOYED ON NASIKO  (%s)" % BASE)
    print("  " + "-" * 58)
    if not items:
        print("  none")
    for a in items:
        print("  %-26s %-12s %s" % (a.get("name"), a.get("status") or "?",
                                    (a.get("id") or "")[:8]))
    print()
    return items


def main():
    args = sys.argv[1:]
    token = login()

    if "--list" in args:
        list_agents(token)
        return 0

    for flag, writable in (("--grant", True), ("--revoke", False)):
        if flag in args:
            role = args[args.index(flag) + 1]
            print("\n  %s workspace write for %s ..."
                  % ("granting" if writable else "revoking", role))
            out = deploy(role, token, writable=writable)
            print("  %s\n" % json.dumps(out)[:200])
            return 0

    print("\n  deploying %d agents to %s" % (len(ORDER), BASE))
    print("  " + "-" * 58)
    for role in ORDER:
        # Nothing is deployed writable. Approval is what changes that.
        out = deploy(role, token, writable=False)
        ident = out.get("id") or out.get("agent_id") or out.get("build_id") or ""
        # The server returns a human message on success too, so only `error`
        # means failure here.
        if out.get("error"):
            print("  FAILED  %-12s %s"
                  % (role, str(out.get("detail") or out["error"])[:70]))
        else:
            print("  queued  %-12s %s"
                  % (role, str(ident or out.get("message") or "")[:44]))
    print()
    print("  Builds run server-side. Watch: docker compose logs -f server")
    print("  Then:   python3 run/deploy.py --list")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
