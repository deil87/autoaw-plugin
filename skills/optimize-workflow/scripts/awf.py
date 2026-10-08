#!/usr/bin/env python3
"""Offline helpers for building an .awf file. Stdlib only; nothing leaves the machine.

Run every command FROM THE REPO ROOT: anchors and source.files are repo-relative.

    awf.py validate <file.awf>        the server's checks, plus anchors vs. the files on disk
    awf.py hash <file> [<file> ...]   source.files entries (path + sha256)
    awf.py find <file> <text>         line numbers where <text> occurs, for anchors
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import awf_envelope  # noqa: E402  — vendored copy of the server's validator


def cmd_validate(path: str) -> int:
    try:
        doc = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR cannot read {path}: {exc}")
        return 2
    errors, warnings = awf_envelope.validate(doc)
    errors += _check_against_disk(doc)
    for e in errors:
        print(f"ERROR   {e}")
    for w in warnings:
        print(f"WARNING {w}")
    if not errors:
        rows = len((doc.get("eval") or {}).get("rows") or [])
        agents = [a.get("id") for a in doc["workflow"]["agents"]]
        print(f"OK  {len(agents)} agents {agents}, {len(doc.get('tunable') or [])} tunable paths, {rows} eval rows")
    return 1 if errors else 0


def _check_against_disk(doc: dict) -> list[str]:
    """What only the client's machine can check: do the anchors point at real lines?

    The server never sees the source, so a typo like line_start: 700 passes there
    and surfaces only when the result is applied to a line that does not exist.
    """
    errs: list[str] = []
    hashed = {f.get("path"): f.get("sha256") for f in (doc.get("source") or {}).get("files") or []
              if isinstance(f, dict)}
    for path, sha in hashed.items():
        p = Path(path or "")
        if not p.is_file():
            errs.append(f"source.files: {path!r} not found (run from the repo root)")
        elif sha and hashlib.sha256(p.read_bytes()).hexdigest() != sha:
            errs.append(f"source.files: {path!r} changed since it was hashed — re-hash and re-check its anchors")
    for key, a in (doc.get("anchors") or {}).items():
        if not isinstance(a, dict) or not isinstance(a.get("file"), str):
            continue
        p = Path(a["file"])
        if not p.is_file():
            errs.append(f"anchor {key!r}: {a['file']!r} not found (run from the repo root)")
            continue
        n = len(p.read_text(encoding="utf-8").splitlines())
        end = a.get("line_end", a.get("line_start"))
        if isinstance(end, int) and end > n:
            errs.append(f"anchor {key!r}: line {end} is past the end of {a['file']} ({n} lines)")
        if a["file"] not in hashed:
            errs.append(f"anchor {key!r}: {a['file']!r} is not listed in source.files")
    return errs


def cmd_hash(paths: list[str]) -> int:
    out = []
    root = Path.cwd().resolve()
    for p in paths:
        full = Path(p).resolve()
        try:
            rel = full.relative_to(root)
        except ValueError:
            print(f"ERROR {p} is outside the current directory — run from the repo root")
            return 1
        out.append({"path": rel.as_posix(), "sha256": hashlib.sha256(full.read_bytes()).hexdigest()})
    print(json.dumps(out, indent=2))
    return 0


def cmd_find(path: str, text: str) -> int:
    hits = [i for i, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1)
            if text in line]
    if not hits:
        print(f"not found in {path}: {text!r}")
        return 1
    for i in hits:
        print(f"{path}:{i}")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 2 and argv[0] == "validate":
        return cmd_validate(argv[1])
    if len(argv) >= 2 and argv[0] == "hash":
        return cmd_hash(argv[1:])
    if len(argv) >= 3 and argv[0] == "find":
        return cmd_find(argv[1], argv[2])
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
