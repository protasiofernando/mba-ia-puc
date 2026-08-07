#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Distribui o mesmo 02 filtrado, byte a byte, para todas as execucoes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


VERSION = "prepare-comparison-inputs-v1"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base",
        required=True,
        help="raiz extraida do pacote comparacao_robusta",
    )
    parser.add_argument(
        "--config",
        default="experimento_config.json",
        help="caminho relativo a --base",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="reservado; entradas divergentes exigem novo experiment_id/diretorio",
    )
    args = parser.parse_args()
    if args.force:
        raise SystemExit(
            "ERRO: --force foi desabilitado para proteger a linhagem. "
            "Use um novo experiment_id e um diretorio remoto vazio."
        )
    base = Path(args.base).resolve()
    config_path = (base / args.config).resolve()
    config = _load(config_path)
    source = base / "referencia" / "02_summaries_escopo.json"
    scope_path = base / "referencia" / "01_scope_mask.json"
    reference_path = base / "referencia" / "06_referencia_consenso.json"
    portfolio_path = base / "portfolio_referencia.json"
    if not source.exists() or not scope_path.exists() or not reference_path.exists():
        raise SystemExit(
            "ERRO: rode primeiro hpc/job_00_referencia.sh; mascara, referencia "
            "ou 02 filtrado ausente"
        )
    rows = _load(source)
    scope = _load(scope_path)
    reference = _load(reference_path)
    keys = [str(item.get("chave", "")).strip() for item in rows]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise SystemExit("ERRO: 02 filtrado tem chaves vazias ou duplicadas")
    included = scope.get("incluidos") or []
    if keys != included:
        raise SystemExit(
            "ERRO: ordem/lista de chaves do 02 filtrado difere da mascara de escopo"
        )
    excluded = {
        str(item.get("chave", ""))
        for item in (scope.get("exclusoes") or []) + (scope.get("indeterminados") or [])
    }
    if excluded & set(keys):
        raise SystemExit("ERRO: chave excluida reapareceu no 02 filtrado")
    source_hash = _sha(source)
    reference_metadata = reference.get("metadata") or {}
    scope_metadata = scope.get("metadata") or {}
    lineage_checks = {
        "reference_analytic_hash": (
            reference_metadata.get("analytic_source_fingerprint") == source_hash
        ),
        "reference_raw_hash": (
            reference_metadata.get("source_fingerprint")
            == scope_metadata.get("source_fingerprint")
        ),
        "reference_scope_hash": (
            reference_metadata.get("scope_fingerprint")
            == scope_metadata.get("scope_fingerprint")
        ),
        "reference_portfolio_hash": (
            reference_metadata.get("portfolio_fingerprint")
            == _sha(portfolio_path)
        ),
    }
    failed_lineage = [
        name for name, passed in lineage_checks.items() if not passed
    ]
    if failed_lineage:
        raise SystemExit(
            "ERRO: linhagem da referencia quebrada: "
            + ", ".join(failed_lineage)
        )

    destinations = []
    native_m1 = config.get("native_m1")
    if native_m1:
        destinations.append(
            (str(native_m1["id"]), base / native_m1["pipeline_data"])
        )
    for run in config.get("runs", []):
        destinations.append(
            (str(run["id"]), base / run["pipeline_data"])
        )
    if not destinations:
        raise SystemExit("ERRO: config sem destinos")

    source_bytes = source.read_bytes()
    output = []
    for run_id, pipeline_data in destinations:
        pipeline_data = pipeline_data.resolve()
        try:
            pipeline_data.relative_to(base)
        except ValueError as exc:
            raise SystemExit(
                f"ERRO: destino fora da raiz do experimento: {pipeline_data}"
            ) from exc
        pipeline_data.mkdir(parents=True, exist_ok=True)
        target = pipeline_data / "02_summaries.json"
        if target.exists() and _sha(target) != source_hash:
            raise SystemExit(
                f"ERRO: {target} existe com hash diferente; crie um novo "
                "diretorio/experiment_id"
            )
        target.write_bytes(source_bytes)
        target_rows = _load(target)
        target_keys = [str(item.get("chave", "")).strip() for item in target_rows]
        if target_keys != keys:
            raise SystemExit(f"ERRO: ordem de chaves alterada em {target}")
        output.append({
            "run_id": run_id,
            "arquivo": str(target.relative_to(base)).replace("\\", "/"),
            "sha256": _sha(target),
            "n": len(target_rows),
        })

    manifest = {
        "version": VERSION,
        "config_sha256": _sha(config_path),
        "portfolio_sha256": _sha(portfolio_path),
        "reference_sha256": _sha(reference_path),
        "reference_fingerprint": reference_metadata.get(
            "reference_fingerprint"
        ),
        "lineage_checks": lineage_checks,
        "scope_fingerprint": scope.get("metadata", {}).get("scope_fingerprint"),
        "raw_source_fingerprint": scope.get("metadata", {}).get(
            "source_fingerprint"
        ),
        "analytic_input_sha256": source_hash,
        "n_analiticos": len(rows),
        "n_sala_excluidos": len(scope.get("exclusoes") or []),
        "n_indeterminados_excluidos": len(scope.get("indeterminados") or []),
        "n_sala_removed_upstream_before_stage1": scope.get(
            "metadata", {}
        ).get("n_sala_removed_upstream_before_stage1"),
        "scope_method": scope.get("metadata", {}).get("scope_method"),
        "llm_used_for_scope": scope.get("metadata", {}).get(
            "llm_used_for_scope"
        ),
        "destinos": output,
    }
    manifest_path = base / "manifesto_insumo_comum.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
