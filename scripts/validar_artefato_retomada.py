#!/usr/bin/env python3
"""Valida um output existente antes de um job retomado pular a etapa."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _keys(rows: list[dict]) -> list[str]:
    return [str(row.get("chave") or row.get("key") or "").strip() for row in rows]


def _stage6_rows(data) -> list[dict]:
    if isinstance(data, list):
        return data
    for field in ("classificados", "classificacoes"):
        if isinstance(data.get(field), list):
            return data[field]
    return []


def _fail(message: str) -> None:
    raise SystemExit("ERRO: artefato de retomada invalido: " + message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    output_path = Path(args.output).resolve()
    pd = output_path.parent
    input_path = pd / "02_summaries.json"
    if not input_path.is_file():
        _fail(f"insumo ausente: {input_path}")
    source = _load(input_path)
    if not isinstance(source, list) or not source:
        _fail("02_summaries vazio ou invalido")
    source_keys = _keys(source)
    if (
        any(not key for key in source_keys)
        or len(source_keys) != len(set(source_keys))
    ):
        _fail("02_summaries possui chave vazia ou duplicada")

    data = _load(output_path)
    name = output_path.name
    if name == "03_clusters.json":
        rows = data.get("tickets") or []
        keys = _keys(rows)
        if (
            len(keys) != len(set(keys))
            or len(keys) != len(source_keys)
            or set(keys) != set(source_keys)
        ):
            _fail("Stage 3 nao cobre exatamente o universo do Stage 2")
        if not isinstance(data.get("cluster_stats"), list):
            _fail("Stage 3 sem cluster_stats")

    elif name == "04_labels.json":
        stage3_path = pd / "03_clusters.json"
        if not stage3_path.is_file():
            _fail("Stage 4 existe sem Stage 3")
        stage3 = _load(stage3_path)
        if int(data.get("total_tickets") or 0) != len(source_keys):
            _fail("total_tickets do Stage 4 diverge do Stage 2")
        clusters = data.get("clusters")
        if not isinstance(clusters, list) or not clusters:
            _fail("Stage 4 sem clusters rotulados")
        upstream = (stage3.get("metadata") or {}).get(
            "clustering_fingerprint"
        )
        recorded = (data.get("metadata") or {}).get(
            "clustering_fingerprint"
        )
        if upstream and recorded != upstream:
            _fail("fingerprint Stage 3 -> Stage 4 diverge")
        stage3_ids = {
            str(row.get("cluster_id"))
            for row in (stage3.get("cluster_stats") or [])
        }
        stage4_ids = {
            str(row.get("cluster_id")) for row in clusters
        }
        if stage3_ids and stage4_ids != stage3_ids:
            _fail("IDs de cluster do Stage 4 divergem do Stage 3")

    elif name == "05_portfolio_recommendation.json":
        stage4_path = pd / "04_labels.json"
        if not stage4_path.is_file():
            _fail("Stage 5 existe sem Stage 4")
        stage4 = _load(stage4_path)
        metadata = data.get("metadata") or {}
        if int(metadata.get("total_tickets") or 0) != len(source_keys):
            _fail("total_tickets do Stage 5 diverge do Stage 2")
        upstream = (stage4.get("metadata") or {}).get(
            "stage4_fingerprint"
        )
        recorded = metadata.get("stage4_fingerprint")
        if upstream and recorded != upstream:
            _fail("fingerprint Stage 4 -> Stage 5 diverge")
        if not isinstance(data.get("recomendacao"), dict):
            _fail("Stage 5 sem recomendacao")

    elif name == "06_classificados.json":
        if not (pd / "05_portfolio_recommendation.json").is_file():
            _fail("Stage 6 existe sem Stage 5")
        rows = _stage6_rows(data)
        keys = _keys(rows)
        if (
            len(keys) != len(set(keys))
            or len(keys) != len(source_keys)
            or set(keys) != set(source_keys)
        ):
            _fail("Stage 6 nao cobre exatamente o universo do Stage 2")
        if any(
            not (row.get("categoria_id") or row.get("categoria_nova"))
            or row.get("_pendente")
            for row in rows
        ):
            _fail("Stage 6 possui categoria vazia ou pendente")
    else:
        _fail(f"output nao reconhecido: {name}")

    print(f"[retomada] PASS: {output_path}")


if __name__ == "__main__":
    main()
