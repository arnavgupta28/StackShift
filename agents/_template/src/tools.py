"""Workspace tools for the StackShift agent fleet.

Every tool lives here, but no agent gets all of them. Each role's agent.py
imports only the tools its job needs — see roles.py. That subset IS the
least-privilege boundary: an agent cannot call a tool it was never given, no
matter what the model decides it wants to do.

Two separate write surfaces, deliberately:

  .stackshift/   artifact directory. Every agent may write here. This is where
                 findings, plans and reports go.
  the repo       source code. Only the Execution agent may write here, and only
                 after a human has approved a plan.

So "read-only" means read-only *on your code*. An agent that reports its
findings is still read-only in the sense that matters.
"""

import fnmatch
import json
import os
import subprocess

from agents import function_tool

WORKSPACE = os.environ.get("WORKSPACE_DIR", "/workspace")
ARTIFACTS = os.path.join(WORKSPACE, ".stackshift")

MAX_READ_BYTES = 200_000
MAX_OUTPUT_CHARS = 20_000
COMMAND_TIMEOUT = 120

SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".stackshift"}


def _resolve(path, *, root=WORKSPACE):
    """Resolve path inside root, refusing anything that escapes it."""
    full = os.path.realpath(os.path.join(root, path))
    if not full.startswith(os.path.realpath(root)):
        raise ValueError("path escapes the workspace: %s" % path)
    return full


def _truncate(text, limit=MAX_OUTPUT_CHARS):
    if len(text) <= limit:
        return text
    return text[:limit] + "\n... [truncated, %d chars omitted]" % (len(text) - limit)


# --------------------------------------------------------------------------
# READ — granted to every role
# --------------------------------------------------------------------------

@function_tool
def read_file(path: str) -> str:
    """Read a file from the workspace. Returns the contents with line numbers."""
    try:
        full = _resolve(path)
        if not os.path.isfile(full):
            return "No such file: %s" % path
        if os.path.getsize(full) > MAX_READ_BYTES:
            return "File too large: %s" % path
        with open(full, encoding="utf-8", errors="replace") as fh:
            lines = fh.read().split("\n")
        return _truncate("\n".join("%4d\t%s" % (i, l) for i, l in enumerate(lines, 1)))
    except Exception as exc:
        return "Error reading %s: %s" % (path, exc)


@function_tool
def list_directory(path: str = ".") -> str:
    """List files and directories at a path in the workspace."""
    try:
        full = _resolve(path)
        if not os.path.isdir(full):
            return "Not a directory: %s" % path
        out = []
        for name in sorted(os.listdir(full)):
            if name in SKIP_DIRS:
                continue
            target = os.path.join(full, name)
            out.append("%s/" % name if os.path.isdir(target) else name)
        return "\n".join(out) if out else "(empty)"
    except Exception as exc:
        return "Error listing %s: %s" % (path, exc)


@function_tool
def glob_files(pattern: str) -> str:
    """Find files matching a glob pattern, e.g. '**/*.py'. Searches recursively."""
    try:
        matches = []
        base = os.path.realpath(WORKSPACE)
        for root, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in files:
                rel = os.path.relpath(os.path.join(root, name), base)
                if fnmatch.fnmatch(rel, pattern) or fnmatch.fnmatch(name, pattern):
                    matches.append(rel)
        matches.sort()
        return "\n".join(matches[:300]) if matches else "No files match %s" % pattern
    except Exception as exc:
        return "Error globbing %s: %s" % (pattern, exc)


@function_tool
def search_code(pattern: str, path: str = ".") -> str:
    """Search file contents for a regular expression. Returns file:line matches."""
    try:
        full = _resolve(path)
        proc = subprocess.run(
            ["grep", "-rn", "-E", pattern, full],
            capture_output=True, text=True, timeout=30,
        )
        base = os.path.realpath(WORKSPACE) + "/"
        hits = [l.replace(base, "") for l in proc.stdout.split("\n")
                if l and not any("/%s/" % d in l for d in SKIP_DIRS)]
        return _truncate("\n".join(hits[:200])) if hits else "No matches for %s" % pattern
    except Exception as exc:
        return "Error searching: %s" % exc


# --------------------------------------------------------------------------
# ARTIFACTS — granted to every role. Cannot touch source code.
# --------------------------------------------------------------------------

def _strip_fences(text):
    """Drop a markdown code fence if the model wrapped the payload in one."""
    body = text.strip()
    if not body.startswith("```"):
        return text
    lines = body.split("\n")
    if lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines[1:])


@function_tool
def write_artifact(name: str, content: str) -> str:
    """Write a findings/plan/report artifact (JSON or text) to the artifact store.

    Use this to record structured output such as system_map.json or
    behavior_contract.json. This CANNOT write to source code.

    A .json artifact is parsed before it is saved. If it is not valid JSON the
    write is rejected and the parse error is returned, so fix it and call again.
    """
    try:
        content = _strip_fences(content)

        # Downstream agents parse these artifacts. Catching malformed JSON at
        # the point of writing lets the agent repair it while it still has the
        # context; a parse failure three steps later is unrecoverable.
        if name.endswith(".json"):
            try:
                json.loads(content)
            except ValueError as exc:
                return (
                    "REJECTED: %s is not valid JSON (%s). Every value must be a "
                    "JSON literal -- a quoted string, number, boolean, null, "
                    "object or array. Expressions such as "
                    "subtotal * Decimal('0.15') are not valid; write the "
                    "computed value, or describe it as a quoted string. "
                    "Fix it and call write_artifact again." % (name, exc)
                )

        os.makedirs(ARTIFACTS, exist_ok=True)
        full = _resolve(name, root=ARTIFACTS)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
        return "Wrote .stackshift/%s (%d bytes)" % (name, len(content))
    except Exception as exc:
        return "Error writing artifact %s: %s" % (name, exc)


@function_tool
def read_artifact(name: str) -> str:
    """Read an artifact written by an earlier agent in the migration."""
    try:
        full = _resolve(name, root=ARTIFACTS)
        if not os.path.isfile(full):
            available = os.listdir(ARTIFACTS) if os.path.isdir(ARTIFACTS) else []
            return "No artifact %s. Available: %s" % (name, ", ".join(available) or "none")
        with open(full, encoding="utf-8", errors="replace") as fh:
            return _truncate(fh.read())
    except Exception as exc:
        return "Error reading artifact %s: %s" % (name, exc)


# --------------------------------------------------------------------------
# SOURCE WRITE — Execution agent only, and only after human approval
# --------------------------------------------------------------------------

@function_tool
def write_source(path: str, content: str) -> str:
    """Create or overwrite a source file in the migration output directory."""
    try:
        full = _resolve(path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(content)
        return "Wrote %s (%d bytes)" % (path, len(content))
    except Exception as exc:
        return "Error writing %s: %s" % (path, exc)


@function_tool
def edit_source(path: str, search: str, replace: str) -> str:
    """Replace an exact string in a source file. `search` must appear exactly once."""
    try:
        full = _resolve(path)
        if not os.path.isfile(full):
            return "No such file: %s" % path
        with open(full, encoding="utf-8") as fh:
            body = fh.read()
        count = body.count(search)
        if count == 0:
            return "Search string not found in %s" % path
        if count > 1:
            return "Search string appears %d times in %s; make it unique" % (count, path)
        with open(full, "w", encoding="utf-8") as fh:
            fh.write(body.replace(search, replace))
        return "Edited %s" % path
    except Exception as exc:
        return "Error editing %s: %s" % (path, exc)


# --------------------------------------------------------------------------
# EXECUTE — Execution and Validation only
# --------------------------------------------------------------------------

@function_tool
def run_command(command: str) -> str:
    """Run a shell command in the workspace, e.g. 'python -m pytest -q'."""
    try:
        proc = subprocess.run(
            command, shell=True, cwd=WORKSPACE,
            capture_output=True, text=True, timeout=COMMAND_TIMEOUT,
        )
        parts = ["$ %s" % command, "exit=%d" % proc.returncode]
        if proc.stdout:
            parts.append(proc.stdout)
        if proc.stderr:
            parts.append("stderr:\n%s" % proc.stderr)
        return _truncate("\n".join(parts))
    except subprocess.TimeoutExpired:
        return "Command timed out after %ds: %s" % (COMMAND_TIMEOUT, command)
    except Exception as exc:
        return "Error running command: %s" % exc


# Name -> tool, for roles.py to select from.
REGISTRY = {
    "read_file": read_file,
    "list_directory": list_directory,
    "glob_files": glob_files,
    "search_code": search_code,
    "write_artifact": write_artifact,
    "read_artifact": read_artifact,
    "write_source": write_source,
    "edit_source": edit_source,
    "run_command": run_command,
}
