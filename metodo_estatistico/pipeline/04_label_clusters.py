#!/usr/bin/env python3
"""
Stage 4 — Rotulacao dos clusters pelo LLM.

Para cada cluster, envia as intencoes mais representativas ao modelo e pede:
  - nome da categoria (maximo 5 palavras)
  - descricao do que cobre
  - criterio de quando usar
  - informacoes que DEVEM ser coletadas ao abrir chamado desse tipo
  - SLA sugerido e complexidade

Entrada:  pipeline_data/03_clusters.json
Saida:    pipeline_data/04_labels.json (sem amostras de texto de chamados)
Tempo estimado: ~30 segundos por cluster * N clusters
"""

import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.llm_client import generate_json, is_available, OLLAMA_URL

PIPELINE_DATA = Path(__file__).parent.parent / "pipeline_data"
CONFIG_PATH   = Path(__file__).parent.parent / "config_portfolio.json"
INPUT_FILE    = PIPELINE_DATA / "03_clusters.json"
OUTPUT_FILE   = PIPELINE_DATA / "04_labels.json"


def _load_context() -> tuple[str, str]:
    """Retorna (infra_context, categorias_obrigatorias_texto)."""
    if not CONFIG_PATH.exists():
        return "", ""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    infra = cfg.get("infra_context", {}).get("texto_contexto", "")
    obrig = cfg.get("categorias_obrigatorias", [])
    obrig_texto = "\n".join(
        f"- {c['nome']}: {c.get('descricao', '')} | Informacoes obrigatorias: {', '.join(c.get('informacoes_obrigatorias', []))}"
        for c in obrig
    )
    return infra, obrig_texto


PROMPT = """{infra_context}

=== CATEGORIAS FIXAS (ja existem no portfolio — NAO recriar, apenas referenciar se o grupo se encaixar) ===
{categorias_obrigatorias}

=== GRUPO DE CHAMADOS A ROTULAR ===
Voce e um especialista em gestao de servicos de TI (ITSM) da FGV.
Analisando {n} chamados agrupados automaticamente por similaridade semantica:

Keywords do grupo: {keywords}

Pedidos reais dos usuarios (extraidos por IA):
{intencoes}

Categorias do Jira que caem neste grupo: {cats_atuais}

Com base no contexto de infraestrutura acima e nos pedidos reais dos usuarios, defina esta categoria de servico.
Use as informacoes obrigatorias descritas no contexto de infraestrutura para preencher o campo informacoes_necessarias — nao invente campos genericos, use os que fazem sentido para este tipo de demanda.
Responda APENAS com JSON valido:
{{
  "nome": "nome da categoria (maximo 5 palavras, em portugues, SEM repetir palavras, titulo claro orientado ao usuario)",
  "descricao": "o que esta categoria cobre — 1 a 2 frases objetivas",
  "quando_usar": "criterio claro e direto de quando um chamado pertence a esta categoria",
  "informacoes_necessarias": [
    "informacao especifica que o usuario DEVE fornecer ao abrir este chamado",
    "segunda informacao obrigatoria",
    "terceira informacao obrigatoria",
    "quarta informacao (se aplicavel ao tipo de servico)"
  ],
  "sla_sugerido": "prazo tipico de resolucao (ex: 4h, 1 dia util, 3 dias uteis)",
  "complexidade": "baixa|media|alta",
  "volume_percentual": 0.0
}}"""


_infra_context, _cats_obrigatorias = _load_context()


def label_cluster(stat: dict, total_tickets: int) -> dict:
    intencoes_text = "\n".join(f"- {i}" for i in stat["sample_intencoes"])
    cats_atuais = ", ".join(
        f"{cat} ({n})" for cat, n in stat["distribuicao_categorias_atuais"].items()
    )

    prompt = PROMPT.format(
        infra_context=_infra_context,
        categorias_obrigatorias=_cats_obrigatorias,
        n=len(stat["sample_intencoes"]),
        keywords=", ".join(stat["keywords"][:8]),
        intencoes=intencoes_text,
        cats_atuais=cats_atuais or "nao mapeado",
    )

    try:
        result = generate_json(prompt, temperature=0.15, max_tokens=2048, timeout=180, num_ctx=8192)
        result["rotulo_gerado_por_fallback"] = False
    except Exception as e:
        # Fallback: deduplica keywords e usa as 3 primeiras únicas
        seen: set = set()
        kws_unique = []
        for kw in stat["keywords"]:
            if kw not in seen:
                seen.add(kw)
                kws_unique.append(kw)
            if len(kws_unique) == 3:
                break
        result = {
            "nome": " ".join(kws_unique).title() if kws_unique else f"Grupo {stat['cluster_id']}",
            "descricao": "Rotulo nao gerado pelo modelo.",
            "quando_usar": "",
            "informacoes_necessarias": [],
            "sla_sugerido": "1 dia util",
            "complexidade": "media",
            "rotulo_gerado_por_fallback": True,
        }
        print(f"[Stage 4] AVISO: fallback usado no cluster {stat['cluster_id']}: {e}")

    result["cluster_id"] = stat["cluster_id"]
    result["total_tickets"] = stat["total"]
    result["volume_percentual"] = round(stat["total"] / total_tickets * 100, 1)
    result["distribuicao_categorias_atuais"] = stat["distribuicao_categorias_atuais"]
    return result


def main():
    if not is_available():
        print(f"[Stage 4] ERRO: Ollama nao esta rodando em {OLLAMA_URL}")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    cluster_stats = data["cluster_stats"]
    total_tickets = sum(s["total"] for s in cluster_stats)

    print(f"[Stage 4] Rotulando {len(cluster_stats)} clusters ({total_tickets} tickets no total)...")

    labels = []
    for i, stat in enumerate(cluster_stats):
        print(f"[Stage 4] Cluster {stat['cluster_id']} ({stat['total']} tickets) [{i+1}/{len(cluster_stats)}]...")
        start = time.time()
        label = label_cluster(stat, total_tickets)
        elapsed = time.time() - start
        print(f"  -> \"{label.get('nome', '?')}\" ({elapsed:.1f}s)")
        labels.append(label)

    output = {
        "optimal_k": data["optimal_k"],
        "total_tickets": total_tickets,
        "clusters": labels,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[Stage 4] {len(labels)} clusters rotulados")
    print("[Stage 4] Grupos identificados (por volume):")
    for label in sorted(labels, key=lambda x: x["total_tickets"], reverse=True):
        print(f"  {label['total_tickets']:4d} tickets ({label['volume_percentual']:5.1f}%) | {label['nome']}")
    print(f"[Stage 4] Salvo em: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
