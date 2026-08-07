#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 3 estatistico para a ablacao controlada da comparacao.

Este script usa exatamente os mesmos campos semanticos expostos ao Stage 3 LLM
(`intencao`, `tema` e `tipo_pedido`), gera embeddings bge-m3 e escolhe K pelo
maximo global de silhueta numa faixa pre-registrada. Ele produz o mesmo contrato
basico de ``03_clusters.json`` consumido pelos Stages 4-6 atuais.

Nao e o Metodo 1 nativo. O legado continua preservado em ``metodo_estatistico``.
Este e o braco K-means da ablacao onde apenas o motor de descoberta muda.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter, OrderedDict
from pathlib import Path

import numpy as np
import requests
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

sys.path.insert(0, str(Path(__file__).parent))
from llm_client import _log_metrics
from projeto import pipeline_data_dir
from discovery_contract import (
    DISCOVERY_CONTRACT_VERSION,
    DISCOVERY_FIELDS,
    discovery_payload,
)


PD = pipeline_data_dir()
OUT = PD / "03_clusters.json"
VERSION = "kmeans-bge-m3-common-fields-v1"
OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434"),
).rstrip("/")
EMBED_MODEL = os.getenv("EMBED_MODEL", "bge-m3").strip() or "bge-m3"
EMBED_BATCH_SIZE = max(1, int(os.getenv("EMBED_BATCH_SIZE", "32")))
EMBED_RETRIES = max(1, int(os.getenv("EMBED_RETRIES", "5")))
K_MIN = max(2, int(os.getenv("K_MIN", "4")))
K_MAX = max(K_MIN, int(os.getenv("K_MAX", "30")))
FORCE_K = int(os.getenv("FORCE_K", "0"))
N_INIT = max(1, int(os.getenv("KMEANS_N_INIT", "20")))
MAX_ITER = max(100, int(os.getenv("KMEANS_MAX_ITER", "500")))
SEED = int(os.getenv("KMEANS_RANDOM_SEED", os.getenv("STAGE3_RANDOM_SEED", "42")))
# 0 = todos os chamados. Para n~1.500, a silhueta completa e barata e evita
# relatar n total enquanto a metrica usa uma amostra escondida.
SILHOUETTE_SAMPLE = max(0, int(os.getenv("SILHOUETTE_SAMPLE", "0")))


def _hash_json(value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _field(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def _intent_payload(item: dict) -> OrderedDict:
    return discovery_payload(item)


def _embedding_text(item: dict) -> str:
    payload = _intent_payload(item)
    parts = [
        f"intencao: {payload['intencao']}",
        f"tema: {payload['tema']}",
        f"tipo_pedido: {payload['tipo_pedido']}",
    ]
    return "\n".join(parts)


def _model_digest() -> str:
    try:
        response = requests.get(f"{OLLAMA_URL}/api/tags", timeout=20)
        response.raise_for_status()
        for item in response.json().get("models", []):
            name = str(item.get("name", ""))
            if name == EMBED_MODEL or (
                ":" not in EMBED_MODEL
                and name == f"{EMBED_MODEL}:latest"
            ):
                return str(item.get("digest", "")).strip()
    except Exception:
        pass
    return ""


def _request_with_retry(url: str, payload: dict, timeout: int = 300) -> dict:
    last_error = None
    for attempt in range(EMBED_RETRIES):
        started = time.time()
        try:
            response = requests.post(url, json=payload, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            usage = {
                "usage": {
                    "prompt_tokens": data.get("prompt_eval_count"),
                    "completion_tokens": 0,
                    "total_tokens": data.get("prompt_eval_count"),
                }
            }
            _log_metrics(
                f"ollama:{EMBED_MODEL}",
                "embedding",
                usage,
                time.time() - started,
            )
            return data
        except Exception as exc:
            last_error = exc
            if attempt < EMBED_RETRIES - 1:
                time.sleep(min(20, 2 ** attempt))
    raise RuntimeError(
        f"embedding falhou apos {EMBED_RETRIES} tentativas: {last_error}"
    )


def _embed_batch(texts: list[str]) -> list[list[float]]:
    """Usa /api/embed em lote; faz fallback para /api/embeddings por item."""
    try:
        data = _request_with_retry(
            f"{OLLAMA_URL}/api/embed",
            {"model": EMBED_MODEL, "input": texts, "truncate": False},
            timeout=600,
        )
        embeddings = data.get("embeddings")
        if isinstance(embeddings, list) and len(embeddings) == len(texts):
            return embeddings
        raise RuntimeError("/api/embed retornou quantidade inesperada")
    except Exception as batch_error:
        print(
            f"[Stage 3 K-means] lote /api/embed indisponivel ({batch_error}); "
            "usando /api/embeddings por item."
        )
        output = []
        for text in texts:
            data = _request_with_retry(
                f"{OLLAMA_URL}/api/embeddings",
                {"model": EMBED_MODEL, "prompt": text or "(vazio)"},
                timeout=180,
            )
            embedding = data.get("embedding")
            if not isinstance(embedding, list) or not embedding:
                raise RuntimeError("/api/embeddings retornou vetor vazio")
            output.append(embedding)
        return output


def _load_or_create_embeddings(
    summaries: list[dict],
) -> tuple[np.ndarray, str, str]:
    texts = [_embedding_text(item) for item in summaries]
    model_digest = _model_digest()
    input_fingerprint = _hash_json({
        "version": VERSION,
        "model": EMBED_MODEL,
        "model_digest": model_digest,
        "contract_version": DISCOVERY_CONTRACT_VERSION,
        "fields": list(DISCOVERY_FIELDS),
        "texts": texts,
    })
    matrix_path = PD / f"_stage3_embeddings__{input_fingerprint[:16]}.npy"
    manifest_path = PD / f"_stage3_embeddings__{input_fingerprint[:16]}.json"
    if matrix_path.exists() and manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            matrix = np.load(matrix_path, allow_pickle=False)
            if (
                manifest.get("input_fingerprint") == input_fingerprint
                and matrix.ndim == 2
                and matrix.shape[0] == len(summaries)
            ):
                print(
                    f"[Stage 3 K-means] embeddings em cache: "
                    f"{matrix.shape[0]}x{matrix.shape[1]}"
                )
                return normalize(matrix.astype(np.float32)), input_fingerprint, model_digest
        except Exception:
            pass

    chunks = []
    total = len(texts)
    started = time.time()
    for start in range(0, total, EMBED_BATCH_SIZE):
        batch = texts[start:start + EMBED_BATCH_SIZE]
        chunks.extend(_embed_batch(batch))
        done = min(total, start + len(batch))
        if done % 100 < len(batch) or done == total:
            print(
                f"[Stage 3 K-means] embeddings {done}/{total} "
                f"({(time.time() - started) / 60:.1f} min)"
            )
    matrix = np.asarray(chunks, dtype=np.float32)
    if matrix.ndim != 2 or matrix.shape[0] != total or not np.isfinite(matrix).all():
        raise RuntimeError(
            f"matriz de embeddings invalida: shape={getattr(matrix, 'shape', None)}"
        )
    matrix = normalize(matrix)
    np.save(matrix_path, matrix, allow_pickle=False)
    manifest_path.write_text(
        json.dumps({
            "version": VERSION,
            "input_fingerprint": input_fingerprint,
            "model": EMBED_MODEL,
            "model_digest": model_digest,
            "n": total,
            "dim": int(matrix.shape[1]),
            "contract_version": DISCOVERY_CONTRACT_VERSION,
            "fields": list(DISCOVERY_FIELDS),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return matrix, input_fingerprint, model_digest


def _select_k(matrix: np.ndarray):
    n = matrix.shape[0]
    upper = min(K_MAX, n - 1)
    if K_MIN > upper:
        raise RuntimeError(f"poucos registros ({n}) para testar K a partir de {K_MIN}")
    candidates = list(range(K_MIN, upper + 1))
    if FORCE_K:
        if FORCE_K not in candidates:
            raise RuntimeError(
                f"FORCE_K={FORCE_K} fora da faixa valida [{K_MIN}, {upper}]"
            )
        candidates = [FORCE_K]

    scores = OrderedDict()
    fits = {}
    sample_size = (
        min(SILHOUETTE_SAMPLE, n)
        if SILHOUETTE_SAMPLE and SILHOUETTE_SAMPLE < n
        else None
    )
    print(
        f"[Stage 3 K-means] K={candidates[0]}..{candidates[-1]}, "
        f"n_init={N_INIT}, silhueta_n={sample_size or n}, seed={SEED}"
    )
    for k in candidates:
        model = KMeans(
            n_clusters=k,
            random_state=SEED,
            n_init=N_INIT,
            max_iter=MAX_ITER,
            algorithm="lloyd",
        )
        labels = model.fit_predict(matrix)
        score = silhouette_score(
            matrix,
            labels,
            metric="euclidean",
            sample_size=sample_size,
            random_state=SEED if sample_size else None,
        )
        scores[str(k)] = {
            "silhueta": round(float(score), 6),
            "inercia": round(float(model.inertia_), 6),
        }
        fits[k] = (model, labels)
        print(f"  K={k:2d}: silhueta={score:.6f} inercia={model.inertia_:.2f}")

    # Regra pre-registrada e nao adaptativa ao alvo: maior silhueta; empate no
    # sexto decimal favorece o menor K (portfolio mais parcimonioso).
    chosen = sorted(
        fits,
        key=lambda k: (-scores[str(k)]["silhueta"], k),
    )[0]
    diagnostics = OrderedDict([
        ("criterio", "maximo_global_silhueta; empate_no_6o_decimal_menor_k"),
        ("forcado", bool(FORCE_K)),
        ("faixa_pre_registrada", [K_MIN, K_MAX]),
        ("faixa_efetiva", [min(fits), max(fits)]),
        ("na_borda", chosen in {min(fits), max(fits)}),
        ("n_init", N_INIT),
        ("max_iter", MAX_ITER),
        ("silhueta_n", sample_size or n),
        ("usa_amostra", bool(sample_size)),
    ])
    return chosen, fits[chosen][0], fits[chosen][1], scores, diagnostics


def _stats(
    summaries: list[dict],
    matrix: np.ndarray,
    labels: np.ndarray,
    model: KMeans,
    k: int,
) -> list[OrderedDict]:
    output = []
    for cluster_id in range(k):
        member_idx = np.flatnonzero(labels == cluster_id)
        distances = np.linalg.norm(
            matrix[member_idx] - model.cluster_centers_[cluster_id],
            axis=1,
        )
        representative_idx = [
            int(member_idx[pos]) for pos in np.argsort(distances)[:12]
        ]
        members = [summaries[int(idx)] for idx in member_idx]
        themes = [
            value for value, _ in Counter(
                _field(item.get("tema")) for item in members
            ).most_common(12) if value
        ]
        output.append(OrderedDict([
            ("cluster_id", cluster_id),
            ("total", len(members)),
            ("keywords", themes),
            (
                "sample_intencoes",
                [_field(summaries[idx].get("intencao")) for idx in representative_idx],
            ),
            (
                "distribuicao_categorias_atuais",
                dict(Counter(
                    _field(item.get("tipo_atual")) for item in members
                ).most_common()),
            ),
            (
                "distribuicao_tipos_pedido",
                dict(Counter(
                    _field(item.get("tipo_pedido")) for item in members
                ).most_common()),
            ),
            ("distancia_media_centroide", round(float(distances.mean()), 6)),
        ]))
    output.sort(key=lambda row: (-row["total"], row["cluster_id"]))
    return output


def main() -> None:
    input_path = PD / "02_summaries.json"
    if not input_path.exists():
        raise SystemExit(f"ERRO: entrada ausente: {input_path}")
    summaries = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(summaries, list) or not summaries:
        raise SystemExit("ERRO: 02_summaries.json vazio ou invalido.")
    keys = [str(item.get("chave", "")).strip() for item in summaries]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise SystemExit("ERRO: chaves vazias ou duplicadas no Stage 2.")

    print(
        f"[Stage 3 K-means] n={len(summaries)} campos="
        "intencao+tema+tipo_pedido (contexto e tipo_atual excluidos)"
    )
    matrix, embedding_fingerprint, model_digest = _load_or_create_embeddings(
        summaries
    )
    chosen, model, labels, scores, diagnostics = _select_k(matrix)
    cluster_stats = _stats(summaries, matrix, labels, model, chosen)

    tickets = []
    for item, label in zip(summaries, labels):
        tickets.append(OrderedDict([
            ("chave", str(item["chave"])),
            ("intencao", item.get("intencao", "")),
            ("tema", item.get("tema", "")),
            ("tipo_pedido", item.get("tipo_pedido", "")),
            ("contexto", item.get("contexto", "")),
            ("tipo_atual", item.get("tipo_atual", "")),
            ("cluster_id", int(label)),
            ("outlier_id", None),
            ("status_agrupamento", "grupo_natural"),
            ("confianca_cluster", None),
            ("ambiguidade_cluster", False),
            (
                "justificativa_cluster",
                "Atribuicao pelo menor deslocamento no espaco normalizado bge-m3.",
            ),
        ]))

    source_fingerprint = _hash_json([_intent_payload(item) for item in summaries])
    clustering_fingerprint = _hash_json({
        "version": VERSION,
        "embedding_fingerprint": embedding_fingerprint,
        "seed": SEED,
        "k": chosen,
        "assignments": [(row["chave"], row["cluster_id"]) for row in tickets],
    })
    output = OrderedDict([
        ("optimal_k", chosen),
        (
            "metodo",
            "K-means sobre bge-m3 nos campos comuns intencao, tema e tipo_pedido",
        ),
        ("metadata", OrderedDict([
            ("pipeline_version", VERSION),
            ("source_fingerprint", source_fingerprint),
            ("embedding_model", EMBED_MODEL),
            ("embedding_model_digest", model_digest),
            ("embedding_batch_size", EMBED_BATCH_SIZE),
            ("embedding_retries", EMBED_RETRIES),
            ("embedding_fingerprint", embedding_fingerprint),
            ("discovery_contract_version", DISCOVERY_CONTRACT_VERSION),
            ("campos_embedding", list(DISCOVERY_FIELDS)),
            ("random_seed", SEED),
            ("k_selection", diagnostics),
            ("silhouette_scores", scores),
            ("clustering_fingerprint", clustering_fingerprint),
            ("total_tickets", len(tickets)),
        ])),
        ("cluster_stats", cluster_stats),
        ("outlier_stats", []),
        ("tickets", tickets),
        # O normalizador comum remove definicoes dos dois bracos antes do Stage 4.
        ("_definicoes", []),
        ("_definicoes_outliers", []),
    ])
    OUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(
        f"[Stage 3 K-means] OK: k={chosen}, "
        f"silhueta={scores[str(chosen)]['silhueta']}, arquivo={OUT}"
    )


if __name__ == "__main__":
    main()
