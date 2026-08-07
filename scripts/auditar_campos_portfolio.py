#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audita automaticamente os campos do portfolio contra o historico sumarizado.

As listas ``info_fornecidas`` e ``info_faltantes`` do Stage 2 sao frases
semanticas, nao um formulario estruturado. O script usa bge-m3 para alinhar cada
frase aos campos curados e agrega presenca/ausencia por servico. O relatorio nao
publica texto nem chave de chamado.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

import numpy as np
import requests
from sklearn.preprocessing import normalize


VERSION = "portfolio-field-audit-bge-v2"
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
).rstrip("/")
MODEL = os.getenv("FIELD_AUDIT_EMBED_MODEL", "bge-m3")


def _norm(value: str) -> str:
    return " ".join(str(value or "").casefold().strip().split())


def _hash_json(value) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_digest() -> str:
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=20)
        response.raise_for_status()
        for row in response.json().get("models", []):
            name = str(row.get("name") or row.get("model") or "")
            if name == MODEL or (
                ":" not in MODEL and name == f"{MODEL}:latest"
            ):
                return str(row.get("digest") or "").strip()
    except Exception:
        return ""
    return ""


def _request(texts: list[str], retries: int = 5) -> list[list[float]]:
    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(
                f"{OLLAMA_URL}/api/embed",
                json={"model": MODEL, "input": texts, "truncate": False},
                timeout=600,
            )
            response.raise_for_status()
            vectors = response.json().get("embeddings")
            if not isinstance(vectors, list) or len(vectors) != len(texts):
                raise RuntimeError("quantidade de embeddings inesperada")
            return vectors
        except Exception as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(f"falha ao gerar embeddings: {last_error}")


def _embeddings(
    texts: list[str],
    cache_dir: Path,
    model_digest: str,
) -> np.ndarray:
    fingerprint = _hash_json({
        "version": VERSION,
        "model": MODEL,
        "model_digest": model_digest,
        "texts": texts,
    })
    cache = cache_dir / f"_field_embeddings__{fingerprint[:16]}.npy"
    if cache.exists():
        matrix = np.load(cache, allow_pickle=False)
        if matrix.shape[0] == len(texts):
            return normalize(matrix.astype(np.float32))
    vectors = []
    for start in range(0, len(texts), 64):
        vectors.extend(_request(texts[start:start + 64]))
    matrix = normalize(np.asarray(vectors, dtype=np.float32))
    cache_dir.mkdir(parents=True, exist_ok=True)
    np.save(cache, matrix, allow_pickle=False)
    return matrix


def main() -> None:
    global MODEL
    parser = argparse.ArgumentParser()
    parser.add_argument("--summaries", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--portfolio", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--model", default="bge-m3")
    parser.add_argument("--environment-lock")
    parser.add_argument(
        "--threshold",
        type=float,
        default=float(os.getenv("FIELD_MATCH_THRESHOLD", "0.55")),
    )
    args = parser.parse_args()
    MODEL = str(args.model).strip()
    if not MODEL:
        raise SystemExit("ERRO: modelo de embedding vazio")
    summaries_path = Path(args.summaries).resolve()
    reference_path = Path(args.reference).resolve()
    portfolio_path = Path(args.portfolio).resolve()
    summaries = json.loads(summaries_path.read_text(encoding="utf-8-sig"))
    reference = json.loads(reference_path.read_text(encoding="utf-8-sig"))
    portfolio = json.loads(portfolio_path.read_text(encoding="utf-8-sig"))
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if not isinstance(summaries, list) or not summaries:
        raise SystemExit("ERRO: summaries vazio ou invalido")
    reference_rows = reference.get("classificacoes")
    category_rows = portfolio.get("categorias_analiticas")
    if not isinstance(reference_rows, list) or not reference_rows:
        raise SystemExit("ERRO: referencia sem classificacoes")
    if not isinstance(category_rows, list) or not category_rows:
        raise SystemExit("ERRO: portfolio sem categorias analiticas")

    def unique_map(rows: list[dict], label: str) -> dict:
        output = {}
        for row in rows:
            key = str(row.get("chave", "")).strip()
            if not key or key in output:
                raise SystemExit(
                    f"ERRO: {label} com chave vazia ou duplicada: {key}"
                )
            output[key] = row
        return output

    summary_by_key = unique_map(summaries, "summaries")
    reference_row_by_key = unique_map(reference_rows, "referencia")
    if set(reference_row_by_key) != set(summary_by_key):
        raise SystemExit("ERRO: referencia e summaries tem universos diferentes")
    categories = {}
    for item in category_rows:
        category_id = str(item.get("id", "")).strip()
        if not category_id or category_id in categories:
            raise SystemExit(
                f"ERRO: categoria vazia ou duplicada: {category_id}"
            )
        categories[category_id] = item
    reference_views = OrderedDict([
        (
            "consensus_strict",
            {
                key: row.get("categoria_estrita_id")
                for key, row in reference_row_by_key.items()
            },
        ),
        (
            "consensus_full",
            {
                key: row.get("categoria_cobertura_id")
                for key, row in reference_row_by_key.items()
            },
        ),
        (
            "model_a",
            {
                key: row.get("modelo_a_id")
                for key, row in reference_row_by_key.items()
            },
        ),
        (
            "model_b",
            {
                key: row.get("modelo_b_id")
                for key, row in reference_row_by_key.items()
            },
        ),
    ])
    for view_name, assignments in reference_views.items():
        unknown = {
            str(value) for value in assignments.values()
            if value is not None and str(value) not in categories
        }
        if unknown:
            raise SystemExit(
                f"ERRO: categorias desconhecidas em {view_name}: "
                + ", ".join(sorted(unknown))
            )

    model_digest = _model_digest()
    if not model_digest:
        raise SystemExit(
            f"ERRO: nao foi possivel registrar o digest exato de {MODEL}"
        )
    if args.environment_lock:
        lock_path = Path(args.environment_lock).resolve()
        lock = json.loads(lock_path.read_text(encoding="utf-8-sig"))
        expected = (lock.get("models") or {}).get("embedding") or {}
        if (
            expected.get("name") != MODEL
            or expected.get("digest") != model_digest
        ):
            raise SystemExit(
                "ERRO: modelo/digest da auditoria de campos diverge do "
                "ambiente congelado"
            )

    phrases = set()
    ticket_phrases = {}
    for key, row in summary_by_key.items():
        provided = {
            _norm(value) for value in (row.get("info_fornecidas") or [])
            if _norm(value)
        }
        missing = {
            _norm(value) for value in (row.get("info_faltantes") or [])
            if _norm(value)
        }
        ticket_phrases[key] = {"provided": provided, "missing": missing}
        phrases.update(provided)
        phrases.update(missing)
    field_records = []
    for category_id, category in categories.items():
        for index, field in enumerate(
            category.get("informacoes_obrigatorias") or [], start=1
        ):
            field_records.append({
                "category_id": category_id,
                "field_id": f"{category_id}__f{index}",
                "text": str(field),
            })
    phrase_list = sorted(phrases)
    texts = phrase_list + [row["text"] for row in field_records]
    matrix = _embeddings(texts, out_dir, model_digest)
    phrase_vectors = matrix[:len(phrase_list)]
    field_vectors = matrix[len(phrase_list):]
    phrase_index = {phrase: index for index, phrase in enumerate(phrase_list)}
    fields_by_category = defaultdict(list)
    for index, record in enumerate(field_records):
        record = dict(record)
        record["vector_index"] = index
        fields_by_category[record["category_id"]].append(record)

    thresholds = sorted(set([
        round(max(0.0, args.threshold - 0.05), 2),
        round(args.threshold, 2),
        round(min(1.0, args.threshold + 0.05), 2),
    ]))
    reports_by_view = OrderedDict()
    for view_name, reference_by_key in reference_views.items():
        reports = {}
        for threshold in thresholds:
            category_output = OrderedDict()
            for category_id, category in categories.items():
                keys = [
                    key for key, assigned in reference_by_key.items()
                    if assigned == category_id
                ]
                fields = fields_by_category[category_id]
                field_counts = {
                    record["field_id"]: {
                        "campo": record["text"],
                        "tickets_com_evidencia_fornecida": 0,
                        "tickets_com_evidencia_faltante": 0,
                        "tickets_com_evidencia_contraditoria": 0,
                    }
                    for record in fields
                }
                unmatched_provided = 0
                unmatched_missing = 0
                for key in keys:
                    matched = {"provided": set(), "missing": set()}
                    for kind in ("provided", "missing"):
                        for phrase in ticket_phrases[key][kind]:
                            if not fields:
                                if kind == "provided":
                                    unmatched_provided += 1
                                else:
                                    unmatched_missing += 1
                                continue
                            pvec = phrase_vectors[phrase_index[phrase]]
                            similarities = [
                                float(np.dot(
                                    pvec,
                                    field_vectors[field["vector_index"]],
                                ))
                                for field in fields
                            ]
                            best = int(np.argmax(similarities))
                            if similarities[best] >= threshold:
                                matched[kind].add(
                                    fields[best]["field_id"]
                                )
                            elif kind == "provided":
                                unmatched_provided += 1
                            else:
                                unmatched_missing += 1
                    for field_id in matched["provided"]:
                        field_counts[field_id][
                            "tickets_com_evidencia_fornecida"
                        ] += 1
                    for field_id in matched["missing"]:
                        field_counts[field_id][
                            "tickets_com_evidencia_faltante"
                        ] += 1
                    for field_id in (
                        matched["provided"] & matched["missing"]
                    ):
                        field_counts[field_id][
                            "tickets_com_evidencia_contraditoria"
                        ] += 1
                field_list = []
                for record in fields:
                    item = field_counts[record["field_id"]]
                    denominator = max(len(keys), 1)
                    item["taxa_fornecida"] = round(
                        item["tickets_com_evidencia_fornecida"]
                        / denominator,
                        6,
                    )
                    item["taxa_faltante"] = round(
                        item["tickets_com_evidencia_faltante"]
                        / denominator,
                        6,
                    )
                    item["taxa_contraditoria"] = round(
                        item["tickets_com_evidencia_contraditoria"]
                        / denominator,
                        6,
                    )
                    field_list.append(item)
                category_output[category_id] = {
                    "nome": category.get("nome"),
                    "n_tickets": len(keys),
                    "campos": field_list,
                    "ocorrencias_sem_alinhamento": {
                        "fornecidas": unmatched_provided,
                        "faltantes": unmatched_missing,
                    },
                }
            reports[str(threshold)] = category_output
        reports_by_view[view_name] = reports

    principal_view = "consensus_strict"
    threshold_key = str(round(args.threshold, 2))
    selected = reports_by_view[principal_view][threshold_key]
    output = OrderedDict([
        ("version", VERSION),
        (
            "natureza",
            "auditoria_automatica_agregada_dos_campos_curados",
        ),
        ("embedding_model", MODEL),
        ("embedding_model_digest", model_digest),
        (
            "environment_lock_sha256",
            _sha_file(Path(args.environment_lock).resolve())
            if args.environment_lock else None,
        ),
        ("input_sha256", {
            "summaries": _sha_file(summaries_path),
            "reference": _sha_file(reference_path),
            "portfolio": _sha_file(portfolio_path),
        }),
        ("reference_view_principal", principal_view),
        (
            "reference_view_coverage",
            {
                view: sum(value is not None for value in assignments.values())
                / max(len(assignments), 1)
                for view, assignments in reference_views.items()
            },
        ),
        ("threshold_principal", round(args.threshold, 2)),
        ("thresholds_sensibilidade", thresholds),
        (
            "nota",
            "info_fornecidas e info_faltantes foram produzidas no Stage 2 por "
            "LLM. As taxas sao evidencia de apoio, nao validacao humana.",
        ),
        ("resultados_por_view_e_threshold", reports_by_view),
    ])
    json_path = out_dir / "RESULTADO_CAMPOS_PORTFOLIO.metrics.json"
    json_path.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# Informações que o usuário deve fornecer",
        "",
        "Os campos abaixo são a decisão operacional curada. As taxas mostram, "
        "como apoio, quantas demandas históricas continham evidência de que o "
        "campo já havia sido fornecido ou estava faltando. O alinhamento foi "
        f"automático com `{MODEL}` (limiar principal {args.threshold:.2f}).",
        "",
    ]
    for category_id, category in selected.items():
        lines.extend([
            f"## {category['nome']}",
            "",
            f"Base histórica no serviço: {category['n_tickets']} chamados.",
            "",
            "| Informação obrigatória | Evidência fornecida | Evidência faltante |",
            "|---|---:|---:|",
        ])
        for field in category["campos"]:
            lines.append(
                f"| {field['campo']} | {field['taxa_fornecida']:.1%} | "
                f"{field['taxa_faltante']:.1%} |"
            )
        lines.append("")
    lines = [
        "# Informações que o usuário deve fornecer",
        "",
        "Os campos abaixo são a decisão operacional curada. As taxas mostram, "
        "como apoio, quantas demandas históricas continham evidência de que o "
        "campo já havia sido fornecido ou estava faltando. O alinhamento foi "
        f"automático com `{MODEL}` (limiar principal {args.threshold:.2f}).",
        "",
        "A coluna principal usa somente o acordo inicial limpo entre Llama e "
        "Qwen. A faixa repete o cálculo nas quatro visões da referência. Uma "
        "contradição significa que o Stage 2 associou ao mesmo campo evidências "
        "de informação fornecida e faltante no mesmo chamado; isso é ruído "
        "potencial da extração, não um julgamento do usuário.",
        "",
    ]
    for category_id, category in selected.items():
        lines.extend([
            f"## {category['nome']}",
            "",
            f"Base histórica estrita no serviço: "
            f"{category['n_tickets']} chamados.",
            "",
            "| Informação obrigatória | Fornecida (estrita) | Faixa 4 visões | "
            "Faltante (estrita) | Faixa 4 visões | Contradição |",
            "|---|---:|---:|---:|---:|---:|",
        ])
        for field_index, field in enumerate(category["campos"]):
            sensitivity_fields = [
                reports_by_view[view][threshold_key][category_id][
                    "campos"
                ][field_index]
                for view in reference_views
            ]
            provided_values = [
                item["taxa_fornecida"] for item in sensitivity_fields
            ]
            missing_values = [
                item["taxa_faltante"] for item in sensitivity_fields
            ]
            lines.append(
                f"| {field['campo']} | {field['taxa_fornecida']:.1%} | "
                f"{min(provided_values):.1%}–{max(provided_values):.1%} | "
                f"{field['taxa_faltante']:.1%} | "
                f"{min(missing_values):.1%}–{max(missing_values):.1%} | "
                f"{field['taxa_contraditoria']:.1%} |"
            )
        lines.append("")
    md_path = out_dir / "RESULTADO_CAMPOS_PORTFOLIO.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[campos] {md_path}")
    print(f"[campos] {json_path}")


if __name__ == "__main__":
    main()
