#!/usr/bin/env python3
"""Valida, sem LLM, o universo filtrado que alimentará a comparação v6."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from projeto import data_dir, projeto_dir


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manifest",
        default=str(
            projeto_dir()
            / "estudo_comparativo"
            / "filtro_sala_sigilo_manifest_v6.json"
        ),
    )
    args = parser.parse_args()

    manifest_path = Path(args.manifest).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if manifest.get("schema_version") != "deterministic-request-type-exclusion-v1":
        raise SystemExit("ERRO: schema do manifesto de escopo não reconhecido")

    request_type_field = str(manifest["decision_field"])
    key_field = str(manifest["key_field"])
    excluded = set(manifest["excluded_request_types"])
    expected_files = manifest["files"]
    expected_names = [str(item["name"]) for item in expected_files]
    actual_files = sorted(data_dir().glob("dti-pesquisa__*.csv"))
    actual_names = [path.name for path in actual_files]
    if actual_names != sorted(expected_names):
        raise SystemExit(
            "ERRO: conjunto de CSVs difere do manifesto: "
            f"esperado={sorted(expected_names)} obtido={actual_names}"
        )

    all_keys: list[str] = []
    result_files = []
    for expected in expected_files:
        path = data_dir() / str(expected["name"])
        actual_sha = _sha256(path)
        if actual_sha != str(expected["sha256_after"]):
            raise SystemExit(
                f"ERRO: hash do CSV filtrado diverge em {path.name}: "
                f"esperado={expected['sha256_after']} obtido={actual_sha}"
            )
        frame = pd.read_csv(
            path,
            sep="^",
            encoding="utf-8",
            dtype=str,
            keep_default_na=False,
            low_memory=False,
        )
        missing = [
            field for field in (request_type_field, key_field)
            if field not in frame.columns
        ]
        if missing:
            raise SystemExit(
                f"ERRO: colunas ausentes em {path.name}: {', '.join(missing)}"
            )
        if len(frame) != int(expected["rows_after"]):
            raise SystemExit(
                f"ERRO: cardinalidade divergente em {path.name}: "
                f"esperado={expected['rows_after']} obtido={len(frame)}"
            )
        request_types = frame[request_type_field].astype(str).str.strip()
        residual = sorted(set(request_types) & excluded)
        if residual:
            raise SystemExit(
                f"ERRO: request type excluído ainda existe em {path.name}: "
                + "; ".join(residual)
            )
        keys = frame[key_field].astype(str).str.strip().tolist()
        if any(not key for key in keys):
            raise SystemExit(f"ERRO: chave vazia em {path.name}")
        all_keys.extend(keys)
        result_files.append({
            "name": path.name,
            "rows": len(frame),
            "sha256": actual_sha,
            "excluded_request_types_remaining": 0,
        })

    expected_after = int(manifest["totals"]["rows_after"])
    if len(all_keys) != expected_after:
        raise SystemExit(
            "ERRO: total pós-filtro divergente: "
            f"esperado={expected_after} obtido={len(all_keys)}"
        )
    if len(all_keys) != len(set(all_keys)):
        raise SystemExit("ERRO: há chaves duplicadas entre os CSVs filtrados")

    print(json.dumps({
        "status": "PASS",
        "scope_method": "deterministic_structured_request_type_prefilter",
        "manifest": str(manifest_path),
        "manifest_sha256": _sha256(manifest_path),
        "rows_before": int(manifest["totals"]["rows_before"]),
        "rows_removed_before_stage1": int(
            manifest["totals"]["rows_removed_before_stage1"]
        ),
        "rows_after": len(all_keys),
        "unique_keys": len(set(all_keys)),
        "files": result_files,
        "llm_used_for_scope": False,
        "free_text_used_for_scope": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
