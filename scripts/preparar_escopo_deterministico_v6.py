#!/usr/bin/env python3
"""Materializa a máscara v6: todo o Stage 2 já filtrado entra na análise."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from discovery_contract import ROUNDTRIP_IDENTIFIER_POLICY


VERSION = "deterministic-prefiltered-scope-v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _hash_json(value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summaries", required=True)
    parser.add_argument("--filter-manifest", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    summaries_path = Path(args.summaries).resolve()
    filter_manifest_path = Path(args.filter_manifest).resolve()
    out_dir = Path(args.out_dir).resolve()
    rows = json.loads(summaries_path.read_text(encoding="utf-8-sig"))
    manifest = json.loads(
        filter_manifest_path.read_text(encoding="utf-8-sig")
    )
    if not isinstance(rows, list) or not rows:
        raise SystemExit("ERRO: Stage 2 vazio ou inválido")
    expected = int(manifest["totals"]["rows_after"])
    if len(rows) != expected:
        raise SystemExit(
            "ERRO: Stage 2 não tem a cardinalidade pós-filtro: "
            f"esperado={expected} obtido={len(rows)}"
        )
    keys = [str(row.get("chave", "")).strip() for row in rows]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise SystemExit("ERRO: Stage 2 contém chaves vazias ou duplicadas")

    source_fingerprint = _sha256(summaries_path)
    scope_fingerprint = _hash_json({
        "version": VERSION,
        "source_fingerprint": source_fingerprint,
        "included_keys": keys,
        "excluded_in_analysis": [],
        "indeterminate_in_analysis": [],
    })
    scope = {
        "metadata": {
            "version": VERSION,
            "scope_method": (
                "deterministic_structured_request_type_prefilter"
            ),
            "source_fingerprint": source_fingerprint,
            "filter_manifest_fingerprint": _sha256(filter_manifest_path),
            "scope_fingerprint": scope_fingerprint,
            "roundtrip_identifier_policy": ROUNDTRIP_IDENTIFIER_POLICY,
            "jira_key_exposed_to_reference_models": False,
            "llm_used_for_scope": False,
            "free_text_used_for_scope": False,
            "decision_field_upstream": manifest["decision_field"],
            "matching_policy_upstream": manifest["matching_policy"],
            "n_total": len(rows),
            "n_incluidos": len(rows),
            "n_sala_sigilo": 0,
            "n_indeterminados": 0,
            "n_sala_removed_upstream_before_stage1": int(
                manifest["totals"]["rows_removed_before_stage1"]
            ),
            "n_before_upstream_filter": int(
                manifest["totals"]["rows_before"]
            ),
            "scope_decision_timing": "before_stage1",
        },
        "incluidos": keys,
        "exclusoes": [],
        "indeterminados": [],
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    mask_path = out_dir / "01_scope_mask.json"
    mask_path.write_text(
        json.dumps(scope, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    analytic_path = out_dir / "02_summaries_escopo.json"
    analytic_path.write_bytes(summaries_path.read_bytes())
    if _sha256(analytic_path) != source_fingerprint:
        raise SystemExit("ERRO: cópia byte a byte do Stage 2 falhou")
    print(json.dumps({
        "status": "PASS",
        "scope_method": scope["metadata"]["scope_method"],
        "llm_used_for_scope": False,
        "n_incluidos": len(keys),
        "n_excluidos_na_analise": 0,
        "n_removidos_upstream": (
            scope["metadata"]["n_sala_removed_upstream_before_stage1"]
        ),
        "source_sha256": source_fingerprint,
        "scope_fingerprint": scope_fingerprint,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
