#!/usr/bin/env python3
"""Registra somente metadados agregados do novo Stage 2 da comparação v6."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


REQUIRED_FIELDS = ("chave", "intencao", "tema", "tipo_pedido")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pipeline-data", required=True)
    parser.add_argument("--scope-manifest", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--ollama-tags", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    pipeline_data = Path(args.pipeline_data).resolve()
    scope_manifest_path = Path(args.scope_manifest).resolve()
    project_root = Path(args.project_root).resolve()
    ollama_tags_path = Path(args.ollama_tags).resolve()
    out = Path(args.out).resolve()
    tickets_path = pipeline_data / "01_tickets.json"
    summaries_path = pipeline_data / "02_summaries.json"
    if not tickets_path.is_file() or not summaries_path.is_file():
        raise SystemExit("ERRO: 01_tickets.json ou 02_summaries.json ausente")

    scope_manifest = _load(scope_manifest_path)
    ollama_tags = _load(ollama_tags_path)
    model_candidates = [
        item for item in (ollama_tags.get("models") or [])
        if str(item.get("name", "")) == args.model
        or (
            ":" not in args.model
            and str(item.get("name", "")) == f"{args.model}:latest"
        )
    ]
    if len(model_candidates) != 1:
        raise SystemExit(
            "ERRO: modelo Stage 2 não foi identificado univocamente "
            "no snapshot Ollama"
        )
    model_digest = str(model_candidates[0].get("digest", "")).strip()
    if len(model_digest) != 64:
        raise SystemExit("ERRO: digest completo do modelo Stage 2 ausente")
    expected_count = int(scope_manifest["totals"]["rows_after"])
    tickets = _load(tickets_path)
    summaries = _load(summaries_path)
    if not isinstance(tickets, list) or not isinstance(summaries, list):
        raise SystemExit("ERRO: Stage 1 ou Stage 2 não é uma lista JSON")
    if len(tickets) != expected_count or len(summaries) != expected_count:
        raise SystemExit(
            "ERRO: cardinalidade Stage 1/2 divergente: "
            f"esperado={expected_count} stage1={len(tickets)} "
            f"stage2={len(summaries)}"
        )

    ticket_keys = [str(row.get("chave", "")).strip() for row in tickets]
    summary_keys = [str(row.get("chave", "")).strip() for row in summaries]
    if ticket_keys != summary_keys:
        raise SystemExit("ERRO: lista/ordem de chaves difere entre Stage 1 e 2")
    if any(not key for key in summary_keys):
        raise SystemExit("ERRO: chave vazia no Stage 2")
    if len(summary_keys) != len(set(summary_keys)):
        raise SystemExit("ERRO: chave duplicada no Stage 2")
    invalid = [
        index for index, row in enumerate(summaries)
        if not isinstance(row, dict)
        or any(field not in row for field in REQUIRED_FIELDS)
    ]
    if invalid:
        raise SystemExit(
            "ERRO: Stage 2 viola schema mínimo nas linhas: "
            + ", ".join(map(str, invalid[:10]))
        )

    manifest = {
        "schema_version": "stage2-comparison-input-manifest-v1",
        "experiment_generation": "v6",
        "scope_method": "deterministic_structured_request_type_prefilter",
        "llm_used_for_scope": False,
        "scope_manifest_sha256": _sha256(scope_manifest_path),
        "stage1_sha256": _sha256(tickets_path),
        "stage2_sha256": _sha256(summaries_path),
        "stage2_contract_version": "intent-blind-v2",
        "stage2_model": args.model,
        "stage2_model_digest": model_digest,
        "stage2_temperature": 0.0,
        "stage2_script_sha256": _sha256(
            project_root / "scripts" / "run_stage2_llm.py"
        ),
        "llm_client_sha256": _sha256(
            project_root / "scripts" / "llm_client.py"
        ),
        "config_portfolio_sha256": _sha256(
            project_root / "configuracao" / "config_portfolio.json"
        ),
        "projeto_sha256": _sha256(
            project_root / "configuracao" / "projeto.json"
        ),
        "stage1_count": len(tickets),
        "stage2_count": len(summaries),
        "required_fields": list(REQUIRED_FIELDS),
        "unique_keys": len(set(summary_keys)),
        "contains_ticket_keys": False,
        "contains_ticket_text": False,
        "checkpoint_policy": (
            "isolated_v6_directory; reuse_only_when_per_ticket_source_hash_matches"
        ),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": "PASS",
        "manifest": str(out),
        **manifest,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
