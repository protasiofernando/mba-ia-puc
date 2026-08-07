#!/usr/bin/env python3
"""
Stage 3 - Clustering semantico das intencoes com embeddings bge-m3.

Usa embeddings do modelo bge-m3 via Ollama para agrupar tickets por similaridade
semantica. O numero de clusters e escolhido pela silhueta, mas com selecao por
pico local e faixa ampliada (ver CORRECAO METODOLOGICA abaixo). Keywords de cada
grupo sao extraidas dos campos 'tema' gerados pelo LLM no Stage 2.

Entrada:  pipeline_data/02_summaries.json
Saida:    pipeline_data/03_clusters.json

CORRECOES METODOLOGICAS (metodo 1 corrigido, comparacao com o metodo atual):

1. Descarte silencioso de embeddings. Antes, um embedding que falhasse era
   removido do clustering e sumia do artefato, sem rastro. Agora a tolerancia e
   estrita, os retries sao maiores, e qualquer ticket sem embedding NAO e
   descartado: ele fica no artefato com cluster_id = -1 e embedding_falhou = true,
   listado em metadata.tickets_sem_embedding. Assim a cobertura e completa e
   auditavel, no espirito do metodo atual (sem descarte em silencio).

2. K de borda por silhueta. Antes, testava K de 5 a 25 e pegava o maximo global,
   que caiu na borda (K=23, sem cotovelo, com duplicatas semanticas). Agora a
   faixa e ampliada e configuravel, a escolha prefere um pico local interior (nao
   de borda), avisa quando o otimo cai na borda e aceita override consciente por
   FORCE_K. A curva completa e o criterio de escolha ficam no artefato.
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
sys.path.insert(0, str(Path(__file__).parent))
from llm_client import _log_metrics  # telemetria de custo (metrica 7): loga embeddings

PIPELINE_DATA = Path(__file__).parent.parent / "pipeline_data"
INPUT_FILE    = PIPELINE_DATA / "02_summaries.json"
OUTPUT_FILE   = PIPELINE_DATA / "03_clusters.json"

OLLAMA_URL    = os.getenv("OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL   = "bge-m3"
# bge-m3 e leve, mas o runner de embeddings do Ollama devolve 500 esporadico sob
# concorrencia alta. 2 workers equilibram velocidade e estabilidade. Configuravel.
EMBED_WORKERS = int(os.getenv("EMBED_WORKERS", "2"))
# CORRECAO 1: tolerancia estrita. Com mais retries, a falha residual deve ser ~0.
# Acima desta fracao, aborta (indica problema sistematico do runner de embeddings).
MAX_EMBED_FAIL_RATE = float(os.getenv("MAX_EMBED_FAIL_RATE", "0.02"))
EMBED_RETRIES = int(os.getenv("EMBED_RETRIES", "5"))

# CORRECAO 2: faixa ampliada e configuravel para o otimo nao ficar preso a borda.
K_MIN = int(os.getenv("K_MIN", "4"))
K_MAX = int(os.getenv("K_MAX", "30"))
# Override consciente do numero de clusters (0 = desligado, usa a selecao por silhueta).
FORCE_K = int(os.getenv("FORCE_K", "0"))


def get_embedding(text: str, retries: int = EMBED_RETRIES) -> list:
    """Chama Ollama /api/embeddings para obter o vetor semantico do texto.

    Com retry e backoff: sob concorrencia o endpoint pode devolver um 500
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
            resp = r.json()
            _log_metrics(
                {"model": EMBED_MODEL,
                 "prompt_eval_count": resp.get("prompt_eval_count"),
                 "total_duration": resp.get("total_duration")},
                r.elapsed.total_seconds(),
                kind="embedding",
            )
            return resp["embedding"]
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

    CORRECAO 1 (sem descarte silencioso): tickets cujo embedding falha apos os
    retries NAO somem. Sao devolvidos separadamente (failed_summaries) para serem
    marcados e mantidos no artefato com cluster_id = -1. So aborta se a fracao de
    falhas passar de MAX_EMBED_FAIL_RATE (problema sistematico do runner).

    Retorna (X, kept_summaries, failed_summaries) alinhados: X tem uma linha por
    kept_summary; failed_summaries carrega os que nao puderam ser vetorizados.
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
            return idx, None  # registrado como falha, o ticket NAO sera descartado

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
    fail_idx = [i for i in range(total) if result[i] is None]
    n_fail   = len(fail_idx)
    if n_fail:
        frac = n_fail / total
        chaves = [str(summaries[i].get("chave") or summaries[i].get("key") or i) for i in fail_idx]
        print(f"[Stage 3] AVISO: {n_fail}/{total} embeddings falharam ({frac:.1%}). "
              f"Mantidos com cluster_id=-1 (nao descartados). Chaves: {', '.join(chaves)}")
        if frac > MAX_EMBED_FAIL_RATE:
            print(f"[Stage 3] ERRO: taxa de falha de embeddings alta demais ({frac:.1%}, "
                  f"limite {MAX_EMBED_FAIL_RATE:.0%}). Abortando, verifique o ollama.log.")
            sys.exit(2)

    kept_summaries   = [summaries[i] for i in ok_idx]
    failed_summaries = [summaries[i] for i in fail_idx]
    X = normalize(np.array([result[i] for i in ok_idx], dtype=np.float32))
    print(f"[Stage 3] Embeddings concluidos: {len(ok_idx)}/{total} validos "
          f"em {(time.time()-start)/60:.1f}min")
    # Normaliza para que distancia euclidiana equivalha a similaridade coseno
    return X, kept_summaries, failed_summaries


def find_optimal_k(X, k_min: int, k_max: int, force_k: int = 0) -> tuple:
    """Escolhe K pela silhueta, mas sem o artefato de borda.

    CORRECAO 2: em vez do maximo global (que caia na borda K=23), prefere um pico
    local interior da curva de silhueta. Se nao houver pico interior (curva
    monotona), usa o maximo global e sinaliza que caiu na borda. FORCE_K permite
    override consciente. Devolve tambem o diagnostico da escolha.
    """
    scores = {}
    sample = min(500, X.shape[0])
    k_top  = min(k_max, X.shape[0] - 1)
    print(f"[Stage 3] Testando K de {k_min} a {k_top}...")
    for k in range(k_min, k_top + 1):
        km     = KMeans(n_clusters=k, random_state=42, n_init=10, max_iter=300)
        labels = km.fit_predict(X)
        score  = silhouette_score(X, labels, sample_size=sample, random_state=42)
        scores[k] = round(float(score), 4)
        print(f"  K={k:2d}: silhueta={score:.4f}")

    ks = sorted(scores)
    if force_k and force_k in scores:
        chosen, motivo = force_k, "forcado_por_FORCE_K"
    else:
        peaks = [
            k for i, k in enumerate(ks)
            if (i == 0 or scores[k] >= scores[ks[i - 1]])
            and (i == len(ks) - 1 or scores[k] >= scores[ks[i + 1]])
        ]
        interior = [k for k in peaks if ks[0] < k < ks[-1]]
        if interior:
            chosen, motivo = max(interior, key=lambda k: scores[k]), "pico_local_interior"
        else:
            chosen, motivo = max(scores, key=scores.get), "maximo_global_sem_pico_interior"

    na_borda = chosen in (ks[0], ks[-1])
    if na_borda:
        print(f"[Stage 3] AVISO: K escolhido ({chosen}) esta na borda da faixa testada "
              f"[{ks[0]},{ks[-1]}]. Ausencia de cotovelo claro. Considere FORCE_K ou "
              f"revisar a curva de silhueta em metadata.selecao_k.")
    top = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:5]
    diagnostico = {
        "motivo": motivo,
        "na_borda": na_borda,
        "faixa_testada": [ks[0], ks[-1]],
        "top5_por_silhueta": [{"k": k, "silhueta": v} for k, v in top],
    }
    return chosen, scores, diagnostico


def extract_keywords(summaries: list, labels: np.ndarray, optimal_k: int) -> dict:
    """
    Extrai keywords por cluster a partir dos campos 'tema' gerados pelo LLM no Stage 2.
    Cada 'tema' e uma frase de 2-3 palavras com significado semantico real, muito mais
    representativa do que termos isolados extraidos por TF-IDF sobre o corpus completo.
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

    # Verifica se bge-m3 esta disponivel
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

    # Embeddings semanticos. kept = vetorizados; failed = sem embedding (mantidos).
    X, kept_summaries, failed_summaries = get_all_embeddings(summaries)
    print(f"[Stage 3] Dimensao dos embeddings: {X.shape[1]}")

    # K via silhueta com selecao por pico local (ver CORRECAO 2)
    optimal_k, silhouette_scores, selecao_k = find_optimal_k(X, K_MIN, K_MAX, FORCE_K)
    print(f"[Stage 3] K escolhido: {optimal_k} (silhueta={silhouette_scores[optimal_k]:.4f}, "
          f"motivo={selecao_k['motivo']})")

    # Clustering final
    km     = KMeans(n_clusters=optimal_k, random_state=42, n_init=15, max_iter=300)
    labels = km.fit_predict(X)

    # Keywords por cluster
    cluster_keywords = extract_keywords(kept_summaries, labels, optimal_k)

    # Atribui cluster_id a cada ticket vetorizado
    for i, summary in enumerate(kept_summaries):
        summary["cluster_id"] = int(labels[i])

    # CORRECAO 1: tickets sem embedding entram no artefato como residual tecnico,
    # visiveis e contaveis, nunca descartados em silencio.
    for s in failed_summaries:
        s["cluster_id"] = -1
        s["embedding_falhou"] = True

    # Estatisticas por cluster
    cluster_stats = []
    for cid in range(optimal_k):
        members    = [s for s in kept_summaries if s["cluster_id"] == cid]
        member_idx = [i for i, s in enumerate(kept_summaries) if s["cluster_id"] == cid]
        centroid   = km.cluster_centers_[cid]
        dists      = np.linalg.norm(X[member_idx] - centroid, axis=1)
        closest    = [member_idx[j] for j in dists.argsort()[:10]]
        cat_dist   = Counter(s.get("tipo_atual", "") for s in members)
        tipo_dist  = Counter(s.get("tipo_pedido", "") for s in members)

        cluster_stats.append({
            "cluster_id":                     cid,
            "total":                          len(members),
            "keywords":                       cluster_keywords[cid],
            "sample_intencoes":               [kept_summaries[j]["intencao"] for j in closest],
            "distribuicao_categorias_atuais": dict(cat_dist.most_common(6)),
            "distribuicao_tipos_pedido":      dict(tipo_dist.most_common()),
        })

    cluster_stats.sort(key=lambda x: x["total"], reverse=True)

    # Residual tecnico explicito para os sem embedding (nao entra no K-means)
    if failed_summaries:
        cluster_stats.append({
            "cluster_id":                     -1,
            "total":                          len(failed_summaries),
            "keywords":                       ["falha tecnica de embedding"],
            "sample_intencoes":               [s.get("intencao", "") for s in failed_summaries[:10]],
            "distribuicao_categorias_atuais": dict(Counter(s.get("tipo_atual", "") for s in failed_summaries).most_common(6)),
            "distribuicao_tipos_pedido":      dict(Counter(s.get("tipo_pedido", "") for s in failed_summaries).most_common()),
            "residual_tecnico":               True,
        })

    tickets_sem_embedding = [
        str(s.get("chave") or s.get("key") or "") for s in failed_summaries
    ]

    output = {
        "optimal_k":             optimal_k,
        "embedding_model":       EMBED_MODEL,
        "selecao_k":             selecao_k,
        "silhouette_scores":     {str(k): v for k, v in silhouette_scores.items()},
        "total_summaries":       len(summaries),
        "total_clusterizados":   len(kept_summaries),
        "tickets_sem_embedding": tickets_sem_embedding,
        "cluster_stats":         cluster_stats,
        "tickets":               kept_summaries + failed_summaries,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[Stage 3] {optimal_k} clusters + {'1 residual tecnico' if failed_summaries else 'sem residual'}")
    print(f"[Stage 3] cobertura: {len(kept_summaries)} clusterizados + "
          f"{len(failed_summaries)} sem embedding = {len(summaries)} (sem descarte)")
    print(f"[Stage 3] Top 5 clusters:")
    for stat in cluster_stats[:5]:
        kws = ", ".join(stat["keywords"][:4])
        print(f"  Cluster {stat['cluster_id']}: {stat['total']} tickets | {kws}")
    print(f"[Stage 3] Salvo em: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
