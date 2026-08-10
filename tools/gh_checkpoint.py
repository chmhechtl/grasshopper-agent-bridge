#!/usr/bin/env python3
"""Versioned checkpoints for the Grasshopper canvas, via the GH_MCP bridge + git.

Saves the live document to its own file, commits it, and can roll back to any
earlier commit — the canvas reloads from the restored file, so a bad edit costs
one command instead of an evening.

    gh_checkpoint.py save "Papier verdrahtet"   # save + commit
    gh_checkpoint.py list                       # show checkpoints
    gh_checkpoint.py restore <ref>              # roll back and reload
    gh_checkpoint.py restore <ref> --keep       # roll back, keep working copy staged

A checkpoint is a plain git commit of the .gh file. Nothing proprietary, no
sidecar format: `git log` and `git show` work as usual.
"""
import json
import socket
import subprocess
import sys
from pathlib import Path

HOST, PORT = "localhost", 8080


def send(command_type, params=None, timeout=180):
    payload = json.dumps({"type": command_type, "parameters": params or {}})
    sock = socket.socket()
    sock.settimeout(timeout)
    sock.connect((HOST, PORT))
    sock.sendall((payload + "\n").encode())
    chunks = b""
    while True:
        chunk = sock.recv(8192)
        if not chunk:
            break
        chunks += chunk
        if chunks.endswith(b"\n"):
            break
    sock.close()
    response = json.loads(chunks.decode("utf-8-sig").strip())
    if not response.get("success"):
        raise RuntimeError(f"{command_type}: {response.get('error')}")
    return response["data"]


def git(repo, *args, check=True):
    done = subprocess.run(["git", "-C", str(repo), *args],
                          capture_output=True, text=True)
    if check and done.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {done.stderr.strip()}")
    return done.stdout.strip()


def document_file():
    """Path of the live document, plus the git repo that tracks it."""
    info = send("get_document_info")
    path = info.get("path")
    if not path:
        raise SystemExit("The document has no path yet — save it once with Cmd+S.")
    path = Path(path)
    repo = Path(git(path.parent, "rev-parse", "--show-toplevel"))
    return path, repo


def cmd_save(message):
    path, repo = document_file()
    saved = send("save_document", {"path": str(path)})
    relative = path.relative_to(repo)

    git(repo, "add", "--", str(relative))
    if not git(repo, "diff", "--cached", "--name-only"):
        print(f"No change since the last checkpoint ({saved['objectCount']} objects).")
        return

    errors = send("get_errors")
    note = f"Checkpoint: {message}\n\nObjects: {saved['objectCount']}, messages: {errors['count']}"
    for component in errors["components"][:8]:
        for entry in component["messages"]:
            note += f"\n  [{component['nickname'] or component['name']}] {entry['level']}: {entry['message']}"
    note += "\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>"

    git(repo, "commit", "-q", "-m", note)
    print(f"Checkpoint {git(repo, 'rev-parse', '--short', 'HEAD')}: {message}")
    print(f"  {saved['objectCount']} objects, {errors['count']} messages")


def cmd_list():
    path, repo = document_file()
    relative = path.relative_to(repo)
    log = git(repo, "log", "--format=%h  %ad  %s", "--date=format:%Y-%m-%d %H:%M",
              "--", str(relative))
    print(log or "No checkpoints yet.")


def cmd_restore(ref, keep):
    path, repo = document_file()
    relative = path.relative_to(repo)

    if git(repo, "status", "--porcelain", "--", str(relative)):
        raise SystemExit("The file has unsaved changes — run 'save' first, or discard them.")

    subject = git(repo, "log", "-1", "--format=%s", ref)
    git(repo, "checkout", ref, "--", str(relative))
    loaded = send("load_document", {"path": str(path)})
    print(f"Back on {ref} ({subject}) — {loaded['objectCount']} objects loaded.")

    if not keep:
        git(repo, "commit", "-q", "-m",
            f"Back on {ref}\n\nCo-Authored-By: Claude Fable 5 <noreply@anthropic.com>")
        print(f"Recorded as a new commit: {git(repo, 'rev-parse', '--short', 'HEAD')}")
    else:
        print("The restore is staged, not committed.")


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    action = sys.argv[1]

    if action == "save":
        cmd_save(" ".join(sys.argv[2:]) or "Work in progress")
    elif action == "list":
        cmd_list()
    elif action == "restore":
        if len(sys.argv) < 3:
            raise SystemExit("restore needs a commit (see 'list').")
        cmd_restore(sys.argv[2], "--keep" in sys.argv)
    else:
        raise SystemExit(__doc__)


if __name__ == "__main__":
    main()
