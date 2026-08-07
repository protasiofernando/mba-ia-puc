#!/usr/bin/env python3
"""Verifica hashes locais e, quando possivel, blobs do commit de origem."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
SNAPSHOT = HERE / "metodo_inicial_kmeans_git_a5576c8"
MANIFEST = SNAPSHOT / "MANIFESTO_SNAPSHOT.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    failures = []
    git_checked = 0
    for relative, expected in manifest["files"].items():
        path = SNAPSHOT / relative
        if not path.is_file():
            failures.append(f"AUSENTE: {relative}")
            continue
        data = path.read_bytes()
        if len(data) != expected["bytes"]:
            failures.append(
                f"BYTES: {relative}: esperado={expected['bytes']} obtido={len(data)}"
            )
        actual = sha256(data)
        if actual != expected["sha256"]:
            failures.append(
                f"SHA256: {relative}: esperado={expected['sha256']} obtido={actual}"
            )
        try:
            blob = subprocess.run(
                ["git", "show", f"{manifest['commit']}:{relative}"],
                cwd=HERE.parent,
                check=True,
                capture_output=True,
            ).stdout
            git_checked += 1
            if data != blob:
                failures.append(f"GIT_BLOB: {relative} diverge do commit")
        except (FileNotFoundError, subprocess.CalledProcessError):
            pass

    status = "PASS" if not failures else "FAIL"
    print(json.dumps({
        "status": status,
        "snapshot": str(SNAPSHOT),
        "commit": manifest["commit"],
        "files": len(manifest["files"]),
        "git_blobs_checked": git_checked,
        "failures": failures,
    }, ensure_ascii=False, indent=2))
    return 0 if not failures else 2


if __name__ == "__main__":
    raise SystemExit(main())
