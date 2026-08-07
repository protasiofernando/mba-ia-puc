#!/usr/bin/env python3
"""Gate do Stage 2 usado para formar um candidato de portfolio."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "estudo_comparativo" / "experimento_config.json",
    )
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8-sig"))
    expected = config["input"]
    raw = args.input.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    rows = json.loads(raw.decode("utf-8-sig"))
    required = set(expected["required_fields"])
    if actual_sha != expected["expected_sha256"]:
        raise SystemExit(
            "ERRO: SHA do Stage 2 divergente: "
            f"esperado={expected['expected_sha256']} obtido={actual_sha}"
        )
    if not isinstance(rows, list) or len(rows) != expected["expected_count"]:
        raise SystemExit(
            f"ERRO: cardinalidade divergente: esperado={expected['expected_count']} "
            f"obtido={len(rows) if isinstance(rows, list) else 'nao-lista'}"
        )
    keys = []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or not required.issubset(row):
            raise SystemExit(f"ERRO: registro {index} viola o contrato do Stage 2")
        keys.append(str(row.get("chave", "")).strip())
    if not all(keys) or len(keys) != len(set(keys)):
        raise SystemExit("ERRO: chaves vazias ou duplicadas")
    print(json.dumps({
        "status": "PASS",
        "arquivo": str(args.input.resolve()),
        "sha256": actual_sha,
        "n": len(rows),
        "scope": (
            "128 registros do request type legado do fluxo de dados "
            "confidenciais/Sala removidos antes do Stage 1"
        ),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
