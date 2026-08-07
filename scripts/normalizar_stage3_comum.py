#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normaliza qualquer saida de Stage 3 para a interface comum da ablacao.

O objetivo e impedir que o Stage 4 receba definicoes autorais da LLM num braco
e exemplos por centroide no outro. As estatisticas e amostras sao reconstruidas
do mesmo modo, apenas a partir das atribuicoes e dos campos do Stage 2.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path


VERSION = "stage3-common-interface-v2"


def _hash_json(value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _sample_rank(ticket: dict) -> tuple[str, str]:
    """Amostra deterministica, independente de confianca ou centroide."""
    key = str(ticket.get("chave", "")).strip()
    digest = hashlib.sha256(f"{VERSION}\0{key}".encode("utf-8")).hexdigest()
    return digest, key


def _stats_for_cluster(cluster_id: int, members: list[dict]) -> OrderedDict:
    ranked = sorted(members, key=_sample_rank)
    samples = []
    seen = set()
    for item in ranked:
        intent = _text(item.get("intencao"))
        normalized = " ".join(intent.casefold().split())
        if intent and normalized not in seen:
            seen.add(normalized)
            samples.append(intent)
        if len(samples) >= 12:
            break
    themes = [
        value for value, _ in Counter(
            _text(item.get("tema")) for item in members
        ).most_common(12) if value
    ]
    return OrderedDict([
        ("cluster_id", cluster_id),
        ("total", len(members)),
        ("keywords", themes),
        ("sample_intencoes", samples),
        (
            "distribuicao_tipos_pedido",
            dict(Counter(
                _text(item.get("tipo_pedido")) for item in members
            ).most_common()),
        ),
    ])


def _stats_for_outlier(outlier_id: str, members: list[dict]) -> OrderedDict:
    base = _stats_for_cluster(-1, members)
    return OrderedDict([
        ("outlier_id", outlier_id),
        ("nome", "Residual tecnico da descoberta"),
        (
            "descricao",
            "Chamados sem pertencimento seguro a um grupo natural neste braco.",
        ),
        (
            "tratamento_esperado",
            "Revisar no mecanismo comum de reconciliacao do portfolio.",
        ),
        ("motivo", "Residual produzido pelo motor de descoberta."),
        ("tipo_registro", "agrupador_tecnico_residual"),
        ("publicavel_no_portfolio", False),
        ("total", base["total"]),
        ("percentual", 0.0),
        ("keywords", base["keywords"]),
        ("sample_intencoes", base["sample_intencoes"]),
        (
            "distribuicao_tipos_pedido",
            base["distribuicao_tipos_pedido"],
        ),
    ])


def normalizar(path: Path) -> dict:
    current_path = path / "03_clusters.json"
    raw_path = path / "03_clusters_raw.json"
    if not current_path.exists():
        raise RuntimeError(f"arquivo ausente: {current_path}")
    source = json.loads(current_path.read_text(encoding="utf-8-sig"))
    tickets = source.get("tickets")
    if not isinstance(tickets, list) or not tickets:
        raise RuntimeError("03_clusters.json sem tickets")
    if (
        source.get("metadata", {}).get("common_interface_version") == VERSION
        and raw_path.exists()
    ):
        return {
            "arquivo": str(current_path),
            "raw": str(raw_path),
            "n": len(tickets),
            "k": int(source.get("optimal_k", 0) or 0),
            "outliers": sum(
                int(item.get("total", 0) or 0)
                for item in source.get("outlier_stats", [])
            ),
            "common_interface_fingerprint": source.get("metadata", {}).get(
                "common_interface_fingerprint"
            ),
            "status": "already_normalized",
        }
    keys = [str(item.get("chave", "")).strip() for item in tickets]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise RuntimeError("tickets do Stage 3 tem chaves vazias ou duplicadas")

    # Preserva a saida original uma unica vez para auditoria.
    if not raw_path.exists():
        raw_path.write_text(
            json.dumps(source, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    groups: dict[int, list[dict]] = defaultdict(list)
    outliers: dict[str, list[dict]] = defaultdict(list)
    normalized_tickets = []
    for item in tickets:
        row = OrderedDict([
            ("chave", str(item.get("chave", "")).strip()),
            ("intencao", item.get("intencao", "")),
            ("tema", item.get("tema", "")),
            ("tipo_pedido", item.get("tipo_pedido", "")),
            ("cluster_id", item.get("cluster_id")),
            ("outlier_id", item.get("outlier_id")),
            ("status_agrupamento", item.get("status_agrupamento", "")),
        ])
        cluster_id = row["cluster_id"]
        if cluster_id is None or int(cluster_id) < 0:
            outlier_id = str(row.get("outlier_id") or "outlier_residual")
            row["cluster_id"] = None
            row["outlier_id"] = outlier_id
            row["status_agrupamento"] = "outlier_revisao"
            outliers[outlier_id].append(row)
        else:
            row["cluster_id"] = int(cluster_id)
            row["outlier_id"] = None
            row["status_agrupamento"] = "grupo_natural"
            groups[int(cluster_id)].append(row)
        normalized_tickets.append(row)

    # IDs brutos sao arbitrarios. Ordena os grupos pela assinatura invariavel
    # dos membros antes de remapear para 0..K-1. Assim uma mera permutacao de
    # labels nao altera a ordem em que o Stage 4 processa a mesma particao.
    group_signatures = {
        old: hashlib.sha256(
            "\0".join(
                sorted(str(row["chave"]) for row in members)
            ).encode("utf-8")
        ).hexdigest()
        for old, members in groups.items()
    }
    old_ids = sorted(groups, key=lambda old: group_signatures[old])
    remap = {old: new for new, old in enumerate(old_ids)}
    if any(old != new for old, new in remap.items()):
        groups = {
            remap[old]: members for old, members in groups.items()
        }
        for row in normalized_tickets:
            if row["cluster_id"] is not None:
                row["cluster_id"] = remap[int(row["cluster_id"])]

    stats = [
        _stats_for_cluster(cluster_id, groups[cluster_id])
        for cluster_id in sorted(groups)
    ]
    total = len(normalized_tickets)
    outlier_stats = []
    for outlier_id in sorted(outliers):
        stat = _stats_for_outlier(outlier_id, outliers[outlier_id])
        stat["percentual"] = round(stat["total"] / max(total, 1) * 100, 2)
        outlier_stats.append(stat)

    raw_fingerprint = _hash_json(source)
    assignment_payload = [
        (row["chave"], row["cluster_id"], row["outlier_id"])
        for row in normalized_tickets
    ]
    interface_fingerprint = _hash_json({
        "version": VERSION,
        "raw_fingerprint": raw_fingerprint,
        "assignments": assignment_payload,
        "sampling": "sha256(version+chave), 12 intencoes unicas",
    })
    metadata = OrderedDict(source.get("metadata") or {})
    metadata.update(OrderedDict([
        ("raw_stage3_fingerprint", raw_fingerprint),
        ("common_interface_version", VERSION),
        ("common_interface_fingerprint", interface_fingerprint),
        ("definitions_stripped", True),
        (
            "legacy_fields_removed",
            ["contexto", "tipo_atual", "distribuicao_categorias_atuais"],
        ),
        ("sample_policy", "sha256(version+chave), 12 intencoes unicas"),
        (
            "cluster_id_policy",
            "0..K-1 por sha256 das chaves ordenadas dos membros",
        ),
        ("clustering_fingerprint", interface_fingerprint),
    ]))
    output = OrderedDict([
        ("optimal_k", len(groups)),
        ("metodo", source.get("metodo", "")),
        ("metadata", metadata),
        ("cluster_stats", stats),
        ("outlier_stats", outlier_stats),
        ("tickets", normalized_tickets),
        ("_definicoes", []),
        ("_definicoes_outliers", []),
    ])
    current_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return {
        "arquivo": str(current_path),
        "raw": str(raw_path),
        "n": total,
        "k": len(groups),
        "outliers": sum(len(items) for items in outliers.values()),
        "common_interface_fingerprint": interface_fingerprint,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pipeline-data",
        required=True,
        help="pasta que contem 03_clusters.json",
    )
    args = parser.parse_args()
    result = normalizar(Path(args.pipeline_data).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
