#!/usr/bin/env python3
"""Valida a identidade exata do Stage 2 antes de iniciar a comparação."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    args = parser.parse_args()

    base = Path(args.base).resolve()
    config_path = base / "experimento_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    input_config = config.get("input") or {}
    source = base / str(input_config.get("source_relpath", ""))
    expected_sha = str(input_config.get("expected_sha256", "")).lower()
    expected_count = int(input_config.get("expected_count", 0))
    required_fields = list(input_config.get("required_fields") or [])
    generation = input_config.get("stage2_generation") or {}

    if not source.is_file():
        raise SystemExit(f"ERRO: insumo congelado ausente: {source}")
    if len(expected_sha) != 64 or expected_count <= 0 or not required_fields:
        raise SystemExit(
            "ERRO: identidade esperada do insumo não foi pré-registrada"
        )
    if generation:
        stage2_code = base / "provenance" / "stage2_code" / "run_stage2_llm.py"
        llm_client = base / "common" / "scripts" / "llm_client.py"
        provenance_checks = {
            "stage2_contract_version": (
                generation.get("contract_version") == "intent-blind-v2"
            ),
            "stage2_model": (
                generation.get("model")
                == config.get("models", {}).get("reasoning")
            ),
            "stage2_code": (
                stage2_code.is_file()
                and _sha256(stage2_code)
                == generation.get("stage2_script_sha256")
            ),
            "llm_client": (
                llm_client.is_file()
                and _sha256(llm_client)
                == generation.get("llm_client_sha256")
            ),
            "model_digest": (
                len(str(generation.get("model_digest", ""))) == 64
            ),
            "temperature": (
                float(generation.get("temperature", -1)) == 0.0
            ),
        }
        failed = [
            name for name, passed in provenance_checks.items() if not passed
        ]
        if failed:
            raise SystemExit(
                "ERRO: proveniência do Stage 2 diverge: "
                + ", ".join(failed)
            )

    actual_sha = _sha256(source)
    if actual_sha != expected_sha:
        raise SystemExit(
            "ERRO: SHA-256 do Stage 2 difere do pré-registrado: "
            f"esperado={expected_sha} obtido={actual_sha}"
        )

    rows = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or len(rows) != expected_count:
        raise SystemExit(
            "ERRO: cardinalidade do Stage 2 difere da pré-registrada: "
            f"esperado={expected_count} obtido="
            f"{len(rows) if isinstance(rows, list) else 'não-lista'}"
        )

    keys = [str(row.get("chave", "")).strip() for row in rows]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise SystemExit("ERRO: Stage 2 contém chaves vazias ou duplicadas")

    invalid = [
        index
        for index, row in enumerate(rows)
        if not isinstance(row, dict)
        or any(field not in row for field in required_fields)
    ]
    if invalid:
        raise SystemExit(
            "ERRO: Stage 2 não satisfaz o schema mínimo nas linhas: "
            + ", ".join(map(str, invalid[:10]))
        )

    print(json.dumps({
        "status": "PASS",
        "arquivo": str(source),
        "sha256": actual_sha,
        "n": len(rows),
        "required_fields": required_fields,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
