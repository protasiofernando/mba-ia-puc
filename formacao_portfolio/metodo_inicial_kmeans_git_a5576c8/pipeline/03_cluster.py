#!/usr/bin/env python3
"""
Stage 3 — Clustering semantico das intencoes com embeddings bge-m3.

Usa embeddings do modelo bge-m3 via Ollama para agrupar tickets por similaridade
semantica. O numero otimo de clusters e encontrado via silhouette score (K de 5 a 25).
Keywords de cada grupo sao extraidas dos campos 'tema' gerados pelo LLM no Stage 2
(frases de 2-3 palavras com significado semantico real, sem TF-IDF).

Entrada:  pipeline_data/02_summaries.json
Saida:    pipeline_data/03_clusters.json
Tempo estimado: ~15-20 minutos (embeddings bge-m3 via Ollama)
"""

import os
import sys
import json
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from collections import Counter

import numpy as np
import requests as _requests
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import normalize

sys.path.insert(0, str(Path(__file__).parent.parent))

PIPELINE_DATA = Path(__file__).parent.parent / "pipeline_data"
INPUT_FILE    = PIPELINE_DATA / "02_summaries.json"
OUTPUT_FILE   = PIPELINE_DATA / "03_clusters.json"

OLLAMA_URL    = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL   = "bge-m3"
# bge-m3 é leve, mas o runner de embeddings do Ollama devolve 500 esporádico sob
# concorrência alta. 2 workers equilibram velocidade e estabilidade. Configurável.
EMBED_WORKERS = int(os.getenv("EMBED_WORKERS", "2"))
# Acima desta fração de falhas, aborta — indica problema sistêmico, não 500 esporádico.
MAX_EMBED_FAIL_RATE = 0.15

K_MIN = 5
K_MAX = 25

def get_embedding(text: str, retries: int = 3) -> list:
    """Chama Ollama /api/embeddings para obter o vetor semantico do texto.

    Com retry: sob concorrencia (varios workers) o endpoint pode devolver um 500
    transitorio. Sem retry, um unico 500 derrubaria todo o Stage 3.
    """
    payload = {"model": EMBED_MODEL, "prompt": text or "(vazio)"}
    last_error = None
    for attempt in range(retries):
        try:
            r = _requests.post(
                f"{OLLAMA_URL}/api/embeddings",
                json=payload,
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["embedding"]
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Embedding falhou apos {retries} tentativas: {last_error}")


def build_text(summary: dict) -> str:
    """Combina intencao, tema, tipo e contexto para gerar o texto a vetorizar."""
    def _s(v):
        if isinstance(v, list):
            return " ".join(str(x) for x in v)
        return str(v) if v else ""

    parts = [
        _s(summary.get("intencao", "")),
        _s(summary.get("tema", "")),
        _s(summary.get("tipo_pedido", "")),
        _s(summary.get("contexto", "")),
    ]
    return " ".join(p for p in parts if p and p != "indefinido")


def get_all_embeddings(summaries: list):
    """Gera embeddings para todos os tickets em paralelo.

    Tolerante a falha: um embedding que falhe após os retries é ignorado (o ticket
    é descartado do clustering) em vez de derrubar todo o Stage 3 — perder alguns
    chamados em ~1583 não afeta os grupos. Aborta apenas se a fração de falhas
    passar de MAX_EMBED_FAIL_RATE (indicaria problema sistêmico).

    Retorna (X, summaries_validos) já alinhados — os summaries cujo embedding falhou
    são removidos para manter os índices consistentes com as linhas de X.
    """
    texts  = [build_text(s) for s in summaries]
    total  = len(texts)
    result = [None] * total
    counter = [0]
    lock   = threading.Lock()
    start  = time.time()

    def embed_one(args):
        idx, text = args
        try:
            return idx, get_embedding(text)
        except Exception:
            return idx, None  # falha graciosa — ticket sera descartado

    print(f"[Stage 3] Gerando {total} embeddings com {EMBED_MODEL} (workers={EMBED_WORKERS})...")
    with ThreadPoolExecutor(max_workers=EMBED_WORKERS) as executor:
        futures = {executor.submit(embed_one, (i, t)): i for i, t in enumerate(texts)}
        for future in as_completed(futures):
            idx, emb = future.result()
            result[idx] = emb
            with lock:
                counter[0] += 1
                if counter[0] % 100 == 0:
                    elapsed = time.time() - start
                    eta_min = elapsed / counter[0] * (total - counter[0]) / 60
                    print(f"  {counter[0]}/{total} ({elapsed/60:.1f}min, ~{eta_min:.0f}min restantes)")

    ok_idx   = [i for i in range(total) if result[i] is not None]
    n_fail   = total - len(ok_idx)
    if n_fail:
        frac = n_fail / total
        print(f"[Stage 3] AVISO: {n_fail}/{total} embeddings falharam ({frac:.1%}) — tickets ignorados.")
        if frac > MAX_EMBED_FAIL_RATE:
            print(f"[Stage 3] ERRO: taxa de falha de embeddings alta demais ({frac:.1%}, "
                  f"limite {MAX_EMBED_FAIL_RATE:.0%}). Abortando — verifique o ollama.log.")
            sys.exit(2)

    kept_summaries = [summaries[i] for i in ok_idx]
    X = normalize(np.array([result[i] for i in ok_idx], dtype=np.float32))
    print(f"[Stage 3] Embeddings concluidos: {len(ok_idx)}/{total} validos "
          f"em {(time.time()-start)/60:.1f}min")
    # Normaliza para que distancia euclidiana equivalha a similaridade coseno
    return X, kept_summaries


def find_optimal_k(X, k_min: int, k_max: int) -> tuple:
    """Testa valores de K e retorna o K com melhor silhouette score."""
    scores = {}
    sample = min(500, X.shape[0])
    print(f"[Stage 3] Testando K de {k_min} a {k_max}...")
    for k in range(k_min, k_max + 1):
        km     = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        labels = km.fit_predict(X)
        score  = silhouette_score(X, labels, sample_size=sample, random_state=42)
        scores[k] = round(float(score), 4)
        print(f"  K={k:2d}: silhouette={score:.4f}")
    optimal_k = max(scores, key=scores.get)
    return optimal_k, scores


def extract_keywords(summaries: list, labels: np.ndarray, optimal_k: int) -> dict:
    """
    Extrai keywords por cluster a partir dos campos 'tema' gerados pelo LLM no Stage 2.
    Cada 'tema' é uma frase de 2-3 palavras com significado semântico real — muito mais
    representativa do que termos isolados extraídos por TF-IDF sobre o corpus completo.
    """
    cluster_keywords = {}
    for cid in range(optimal_k):
        members = [s for s, l in zip(summaries, labels) if l == cid]
        if not members:
            cluster_keywords[cid] = []
            continue

        tema_counter: Counter = Counter()
        for s in members:
            tema = s.get("tema", "")
            if tema and tema.strip().lower() not in ("indefinido", "nan", "none", ""):
                tema_counter[tema.strip().lower()] += 1

        cluster_keywords[cid] = [t for t, _ in tema_counter.most_common(12)]
    return cluster_keywords


def main():
    # Verifica Ollama e modelo
    try:
        r = _requests.get(f"{OLLAMA_URL}/api/version", timeout=5)
        r.raise_for_status()
    except Exception:
        print(f"[Stage 3] ERRO: Ollama nao esta rodando em {OLLAMA_URL}")
        sys.exit(1)

    # Verifica se bge-m3 está disponível
    try:
        r = _requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        modelos = [m["name"] for m in r.json().get("models", [])]
        if not any(EMBED_MODEL in m for m in modelos):
            print(f"[Stage 3] AVISO: modelo {EMBED_MODEL} nao encontrado. Baixando...")
            _requests.post(f"{OLLAMA_URL}/api/pull",
                          json={"name": EMBED_MODEL, "stream": False}, timeout=600)
            print(f"[Stage 3] {EMBED_MODEL} baixado.")
    except Exception as e:
        print(f"[Stage 3] AVISO: nao foi possivel verificar modelos: {e}")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        summaries = json.load(f)
    print(f"[Stage 3] {len(summaries)} summaries para clusterizar")

    # Embeddings semanticos — summaries é filtrado para os tickets cujo embedding deu certo
    X, summaries = get_all_embeddings(summaries)
    print(f"[Stage 3] Dimensao dos embeddings: {X.shape[1]}")

    # K otimo via silhouette
    optimal_k, silhouette_scores = find_optimal_k(X, K_MIN, K_MAX)
    print(f"[Stage 3] K otimo: {optimal_k} (silhouette={silhouette_scores[optimal_k]:.4f})")

    # Clustering final
    km     = KMeans(n_clusters=optimal_k, random_state=42, n_init=15, max_iter=300)
    labels = km.fit_predict(X)

    # Keywords por cluster
    cluster_keywords = extract_keywords(summaries, labels, optimal_k)

    # Atribui cluster_id a cada ticket
    for i, summary in enumerate(summaries):
        summary["cluster_id"] = int(labels[i])

    # Estatisticas por cluster
    cluster_stats = []
    for cid in range(optimal_k):
        members    = [s for s in summaries if s["cluster_id"] == cid]
        member_idx = [i for i, s in enumerate(summaries) if s["cluster_id"] == cid]
        centroid   = km.cluster_centers_[cid]
        dists      = np.linalg.norm(X[member_idx] - centroid, axis=1)
        closest    = [member_idx[j] for j in dists.argsort()[:10]]
        cat_dist   = Counter(s.get("tipo_atual", "") for s in members)
        tipo_dist  = Counter(s.get("tipo_pedido", "") for s in members)

        cluster_stats.append({
            "cluster_id":                     cid,
            "total":                          len(members),
            "keywords":                       cluster_keywords[cid],
            "sample_intencoes":               [summaries[j]["intencao"] for j in closest],
            "distribuicao_categorias_atuais": dict(cat_dist.most_common(6)),
            "distribuicao_tipos_pedido":      dict(tipo_dist.most_common()),
        })

    cluster_stats.sort(key=lambda x: x["total"], reverse=True)

    output = {
        "optimal_k":         optimal_k,
        "embedding_model":   EMBED_MODEL,
        "silhouette_scores": {str(k): v for k, v in silhouette_scores.items()},
        "cluster_stats":     cluster_stats,
        "tickets":           summaries,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[Stage 3] {optimal_k} clusters encontrados")
    print(f"[Stage 3] Top 5 clusters:")
    for stat in cluster_stats[:5]:
        kws = ", ".join(stat["keywords"][:4])
        print(f"  Cluster {stat['cluster_id']}: {stat['total']} tickets | {kws}")
    print(f"[Stage 3] Salvo em: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
