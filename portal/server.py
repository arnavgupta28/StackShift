#!/usr/bin/env python3
"""StackShift portal — trigger the pipeline and watch it run.

    python3 portal/server.py            then open http://localhost:7700

Standard library only, deliberately: the portal has to start instantly on any
machine that can already run the pipeline, with nothing to install.

It does not reimplement any pipeline logic. Every stage shells out to the same
run/*.py script you would run by hand, so the portal and the terminal cannot
drift apart. What the portal adds is a place to watch it, a way to upload
context documents, and one button per stage.
"""

import html
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKSPACE = os.path.join(ROOT, ".runs", "demo", "workspace")
ARTIFACTS = os.path.join(WORKSPACE, ".stackshift")
CONTEXT = os.path.join(WORKSPACE, "context")
MIGRATED = os.path.join(WORKSPACE, "migrated")
PORT = int(os.environ.get("PORT", "7700"))

# Every stage is the exact command a person would type. The portal is a remote
# control, not a second implementation.
STAGES = {
    "fleet":    {"label": "Start fleet",  "cmd": ["python3", "run/fleet.py", "up"]},
    "spine":    {"label": "Discover, assess, plan",
                 "cmd": ["python3", "run/spine.py"]},
    "execute":  {"label": "Execute migration", "cmd": ["python3", "run/execute.py"]},
    "execute_denied": {"label": "Execute WITHOUT approval",
                       "cmd": ["python3", "run/execute.py", "--force"]},
    "validate": {"label": "Validate and repair",
                 "cmd": ["python3", "run/validate.py", "--repair", "--max-attempts", "3"]},
    "parity":   {"label": "Independent parity check",
                 "cmd": ["python3", "run/parity.py"]},
    "reset":    {"label": "Reset workspace",
                 "cmd": ["bash", "-c",
                         "rm -rf .runs/demo && mkdir -p .runs/demo/workspace/migrated "
                         ".runs/demo/workspace/.stackshift .runs/demo/workspace/context "
                         "&& cp -r legacy/acme-orders .runs/demo/workspace/legacy "
                         "&& cp fixtures/expected_behavior.json .runs/demo/workspace/"]},
}

# Which artifact proves a pipeline step finished. Drives the tracker.
STEPS = [
    ("discovery",  "Discovery",  "behavior_contract.json"),
    ("assessment", "Assessment", "assessment.json"),
    ("planning",   "Planning",   "migration_plan.json"),
    ("approval",   "Approval",   "approval.json"),
    ("execution",  "Execution",  "execution_report.json"),
    ("validation", "Validation", "validation_report.json"),
]

# Optional context sources the portal knows how to recognise, and what each
# unlocks. Mirrors docs/03-inputs-and-context.md.
CONTEXT_KINDS = [
    ("openapi",  r"(openapi|swagger)", "API compatibility provable, not inferred"),
    ("schema",   r"(schema|\.sql$)",   "Ground truth for the data model"),
    ("tests",    r"(test|spec)",       "A baseline to preserve"),
    ("docs",     r"(\.md$|readme|adr|doc)", "Architecture notes to confirm or contradict"),
    ("tickets",  r"(jira|ticket|issue|linear)", "Known bugs and work already planned"),
    ("traffic",  r"(traffic|access|\.log$|apm)", "Real payloads become test fixtures"),
]


class Runner:
    """Runs one stage at a time and keeps its output for the UI to poll."""

    def __init__(self):
        self.lock = threading.Lock()
        self.lines = []
        self.stage = None
        self.started = None
        self.finished = None
        self.code = None
        self.proc = None

    def busy(self):
        return self.stage is not None and self.finished is None

    def start(self, key):
        with self.lock:
            if self.busy():
                return False, "%s is already running" % self.stage
            if key not in STAGES:
                return False, "unknown stage %r" % key
            self.lines = []
            self.stage = key
            self.started = time.time()
            self.finished = None
            self.code = None
        threading.Thread(target=self._run, args=(key,), daemon=True).start()
        return True, None

    def _run(self, key):
        cmd = STAGES[key]["cmd"]
        self._emit("$ %s" % " ".join(cmd))
        try:
            self.proc = subprocess.Popen(
                cmd, cwd=ROOT, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, text=True, bufsize=1,
            )
            for line in self.proc.stdout:
                self._emit(line.rstrip("\n"))
            self.proc.wait()
            code = self.proc.returncode
        except Exception as exc:
            self._emit("portal error: %s" % exc)
            code = -1
        with self.lock:
            self.code = code
            self.finished = time.time()
            self.proc = None
        self._emit("")
        self._emit("[%s finished, exit %s]" % (key, code))

    def _emit(self, text):
        with self.lock:
            self.lines.append(text)

    def stop(self):
        proc = self.proc
        if proc:
            proc.terminate()
            return True
        return False

    def snapshot(self, since=0):
        with self.lock:
            return {
                "stage": self.stage,
                "running": self.busy(),
                "code": self.code,
                "elapsed": int((self.finished or time.time()) - self.started)
                           if self.started else 0,
                "lines": self.lines[since:],
                "total": len(self.lines),
            }


RUNNER = Runner()


def read_json(name):
    path = os.path.join(ARTIFACTS, name)
    if not os.path.isfile(path):
        return None
    try:
        with open(path) as fh:
            return json.load(fh)
    except ValueError:
        return None


def mount_mode(container="ss-execution"):
    try:
        proc = subprocess.run(
            ["docker", "inspect", "-f",
             '{{range .Mounts}}{{if eq .Destination "/workspace"}}{{.RW}}{{end}}{{end}}',
             container], capture_output=True, text=True, timeout=10)
        if proc.returncode != 0:
            return "not running"
        return "read-write" if proc.stdout.strip() == "true" else "read-only"
    except Exception:
        return "unknown"


def context_files():
    if not os.path.isdir(CONTEXT):
        return []
    out = []
    for name in sorted(os.listdir(CONTEXT)):
        path = os.path.join(CONTEXT, name)
        if not os.path.isfile(path):
            continue
        low = name.lower()
        kind = next((k for k, pattern, _ in CONTEXT_KINDS
                     if re.search(pattern, low)), "other")
        out.append({"name": name, "size": os.path.getsize(path), "kind": kind})
    return out


DEFAULT_REPO = "https://github.com/pragnyamehar-create/legacy-acme-orders"


def repo_status():
    legacy_dir = os.path.join(WORKSPACE, "legacy")
    info = read_json("repo_info.json") or {}
    linked = os.path.isdir(legacy_dir) and any(os.scandir(legacy_dir)) if os.path.isdir(legacy_dir) else False
    files_count = 0
    if linked:
        for dirpath, dirs, files in os.walk(legacy_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "__pycache__"]
            files_count += len([f for f in files if not f.startswith(".") and not f.endswith(".pyc")])

    url = info.get("url")
    if not url and linked:
        try:
            res = subprocess.run(["git", "-C", legacy_dir, "config", "--get", "remote.origin.url"],
                                 capture_output=True, text=True, timeout=5)
            if res.returncode == 0 and res.stdout.strip():
                url = res.stdout.strip()
        except Exception:
            pass
    if not url:
        url = DEFAULT_REPO

    name = info.get("name")
    if not name and url:
        name = url.rstrip("/").split("/")[-1].replace(".git", "")
    elif not name:
        name = "acme-orders"

    return {
        "url": url,
        "name": name,
        "linked": linked,
        "files_count": files_count,
        "source": info.get("source", "github" if info.get("url") else "local"),
    }


def setup_repo(url=None):
    legacy_dir = os.path.join(WORKSPACE, "legacy")
    os.makedirs(WORKSPACE, exist_ok=True)
    os.makedirs(ARTIFACTS, exist_ok=True)
    os.makedirs(CONTEXT, exist_ok=True)
    os.makedirs(MIGRATED, exist_ok=True)

    RUNNER._emit("--- Setting up source repository ---")
    if url and url.strip():
        url = url.strip()
        RUNNER._emit(f"$ git clone {url} {os.path.relpath(legacy_dir, ROOT)}")
        if os.path.isdir(legacy_dir):
            shutil.rmtree(legacy_dir, ignore_errors=True)
        proc = subprocess.run(["git", "clone", "--depth", "1", url, legacy_dir],
                              capture_output=True, text=True, timeout=60)
        if proc.returncode != 0:
            err_msg = (proc.stderr or proc.stdout).strip()
            RUNNER._emit(f"git clone error: {err_msg}")
            return False, err_msg
        source = "github"
        RUNNER._emit("Repository cloned successfully.")
    else:
        url = DEFAULT_REPO
        source = "local"
        RUNNER._emit("Using default local repository (legacy/acme-orders)...")
        if os.path.isdir(legacy_dir):
            shutil.rmtree(legacy_dir, ignore_errors=True)
        local_src = os.path.join(ROOT, "legacy", "acme-orders")
        shutil.copytree(local_src, legacy_dir)
        RUNNER._emit("Local repository staged.")

    # Ensure expected_behavior.json exists in WORKSPACE
    ws_fixture = os.path.join(WORKSPACE, "expected_behavior.json")
    if not os.path.isfile(ws_fixture):
        repo_fixture = os.path.join(legacy_dir, "fixtures", "expected_behavior.json")
        root_fixture = os.path.join(ROOT, "fixtures", "expected_behavior.json")
        src_fix = repo_fixture if os.path.isfile(repo_fixture) else root_fixture
        if os.path.isfile(src_fix):
            shutil.copy(src_fix, ws_fixture)
            RUNNER._emit("Loaded expected_behavior.json fixture.")

    # Copy context docs if available in the repo
    repo_context = os.path.join(legacy_dir, "context")
    if os.path.isdir(repo_context):
        for item in os.listdir(repo_context):
            src_item = os.path.join(repo_context, item)
            dst_item = os.path.join(CONTEXT, item)
            if os.path.isfile(src_item) and not os.path.exists(dst_item):
                shutil.copy(src_item, dst_item)
                RUNNER._emit(f"Imported context doc: {item}")

    name = url.rstrip("/").split("/")[-1].replace(".git", "")
    info = {
        "url": url,
        "name": name,
        "source": source,
        "linked_at": time.time(),
    }
    with open(os.path.join(ARTIFACTS, "repo_info.json"), "w") as fh:
        json.dump(info, fh, indent=2)

    RUNNER._emit(f"Source repository active: {name}")
    return True, None


def completeness():
    """What context is linked, and what the missing pieces would buy.

    Shown rather than hidden, because 'you can proceed at 40%' plus a concrete
    reason to link the rest is better UX than silently doing worse.
    """
    repo = repo_status()
    have = {f["kind"] for f in context_files()}
    rows = [{"kind": kind, "linked": kind in have, "unlocks": unlocks}
            for kind, _, unlocks in CONTEXT_KINDS]
    rows.insert(0, {
        "kind": "repository",
        "linked": repo["linked"],
        "unlocks": f"{repo['name']} ({repo['files_count']} files)" if repo["linked"] else "Required"
    })
    linked = sum(1 for r in rows if r["linked"])
    return {"rows": rows, "linked": linked, "total": len(rows),
            "percent": int(100 * linked / len(rows))}


def migrated_files():
    if not os.path.isdir(MIGRATED):
        return []
    out = []
    for dirpath, dirs, files in os.walk(MIGRATED):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in files:
            if name.endswith(".pyc"):
                continue
            full = os.path.join(dirpath, name)
            out.append(os.path.relpath(full, MIGRATED))
    return sorted(out)


def readiness():
    report = read_json("validation_report.json")
    if not report:
        return None
    sys.path.insert(0, os.path.join(ROOT, "scoring"))
    try:
        import score  # noqa: E402
        return score.compute(report.get("evidence", report))
    except Exception:
        return None


def state():
    plan = read_json("migration_plan.json")
    approval = read_json("approval.json")
    validation = read_json("validation_report.json")

    steps = []
    for key, label, artifact in STEPS:
        done = os.path.isfile(os.path.join(ARTIFACTS, artifact))
        steps.append({"key": key, "label": label, "done": done,
                      "artifact": artifact})

    tiers = []
    if plan:
        sys.path.insert(0, os.path.join(ROOT, "run"))
        try:
            import tiers as tiers_mod  # noqa: E402
            normalised = tiers_mod.normalise(dict(plan))
            for t in normalised.get("tiers", []):
                est = tiers_mod.estimate(t)
                tiers.append({
                    "id": t.get("id"), "name": t.get("name"),
                    "summary": t.get("summary"), "risk": t.get("risk"),
                    "recommended": t.get("recommended"),
                    "pick_this_if": t.get("pick_this_if"),
                    "estimate": est,
                })
        except Exception:
            pass

    return {
        "repo": repo_status(),
        "steps": steps,
        "tiers": tiers,
        "recommended_tier": (plan or {}).get("recommended_tier"),
        "recommendation_reason": (plan or {}).get("recommendation_reason"),
        "strategy": (plan or {}).get("strategy"),
        "approval": approval,
        "grant": mount_mode(),
        "context": context_files(),
        "completeness": completeness(),
        "migrated": migrated_files(),
        "regressions": (validation or {}).get("regressions") or [],
        "rules": len((read_json("behavior_contract.json") or {}).get("rules") or []),
        "readiness": readiness(),
        "runner": RUNNER.snapshot(since=10 ** 9),
        "nasiko": os.environ.get("NASIKO_URL", "http://localhost:8080"),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body, ctype="application/json"):
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?")[0]
        query = dict(p.split("=", 1) for p in self.path.split("?")[1].split("&")
                     if "=" in p) if "?" in self.path else {}

        if path in ("/", "/index.html"):
            page = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
            with open(page, "rb") as fh:
                return self._send(200, fh.read(), "text/html; charset=utf-8")

        if path == "/api/state":
            return self._send(200, state())

        if path == "/api/log":
            return self._send(200, RUNNER.snapshot(since=int(query.get("since", 0))))

        if path == "/api/artifact":
            name = query.get("name", "")
            data = read_json(name)
            if data is None:
                return self._send(404, {"error": "no artifact %s" % name})
            return self._send(200, data)

        if path == "/api/file":
            rel = query.get("path", "")
            full = os.path.realpath(os.path.join(MIGRATED, rel))
            if not full.startswith(os.path.realpath(MIGRATED)) or not os.path.isfile(full):
                return self._send(404, "not found", "text/plain")
            with open(full, encoding="utf-8", errors="replace") as fh:
                return self._send(200, fh.read(), "text/plain; charset=utf-8")

        return self._send(404, {"error": "not found"})

    def do_POST(self):
        path = self.path.split("?")[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""

        if path == "/api/repo/clone":
            body = json.loads(raw or b"{}")
            url = body.get("url")
            ok, err = setup_repo(url)
            if not ok:
                return self._send(400, {"ok": False, "error": err})
            return self._send(200, {"ok": True, "repo": repo_status()})

        if path == "/api/run":
            body = json.loads(raw or b"{}")
            ok, err = RUNNER.start(body.get("stage"))
            return self._send(200 if ok else 409, {"ok": ok, "error": err})

        if path == "/api/stop":
            return self._send(200, {"ok": RUNNER.stop()})

        if path == "/api/approve":
            body = json.loads(raw or b"{}")
            tier = body.get("tier")
            proc = subprocess.run(
                ["python3", "run/approve.py", "--tier", str(tier)],
                cwd=ROOT, capture_output=True, text=True, timeout=180)
            return self._send(200, {"ok": proc.returncode == 0,
                                    "output": proc.stdout + proc.stderr})

        if path == "/api/revoke":
            proc = subprocess.run(["python3", "run/approve.py", "--revoke"],
                                  cwd=ROOT, capture_output=True, text=True, timeout=180)
            return self._send(200, {"ok": proc.returncode == 0,
                                    "output": proc.stdout + proc.stderr})

        if path == "/api/upload":
            return self._upload(raw)

        if path == "/api/context/clear":
            shutil.rmtree(CONTEXT, ignore_errors=True)
            os.makedirs(CONTEXT, exist_ok=True)
            return self._send(200, {"ok": True})

        return self._send(404, {"error": "not found"})

    def _upload(self, raw):
        """Accept multipart uploads of context documents.

        Parsed by hand because cgi.FieldStorage is gone in 3.13+ and the point
        of this portal is that it needs nothing installed.
        """
        ctype = self.headers.get("Content-Type", "")
        if "boundary=" not in ctype:
            return self._send(400, {"error": "expected multipart/form-data"})
        boundary = ctype.split("boundary=")[1].strip().strip('"').encode()

        os.makedirs(CONTEXT, exist_ok=True)
        saved = []
        for part in raw.split(b"--" + boundary):
            if b"\r\n\r\n" not in part:
                continue
            head, _, body = part.partition(b"\r\n\r\n")
            match = re.search(br'filename="([^"]*)"', head)
            if not match or not match.group(1):
                continue
            name = os.path.basename(match.group(1).decode("utf-8", "replace"))
            body = body.rstrip(b"\r\n").rstrip(b"--")
            if not name or not body:
                continue
            # Flatten any path the browser sent; a folder upload arrives as
            # many files whose names contain directories.
            name = name.replace("/", "_")
            with open(os.path.join(CONTEXT, name), "wb") as fh:
                fh.write(body)
            saved.append({"name": name, "size": len(body)})
        return self._send(200, {"ok": True, "saved": saved})


def main():
    os.makedirs(CONTEXT, exist_ok=True)
    os.makedirs(ARTIFACTS, exist_ok=True)
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print()
    print("  StackShift portal   http://localhost:%d" % PORT)
    print("  Nasiko dashboard    %s" % os.environ.get("NASIKO_URL",
                                                      "http://localhost:8080"))
    print("  workspace           %s" % os.path.relpath(WORKSPACE, ROOT))
    print()
    print("  ctrl-c to stop")
    print()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  stopped\n")


if __name__ == "__main__":
    main()
