#!/usr/bin/env python3
"""
Stage 5 — Comparacao de portfolio e recomendacao otimizada.

Envia ao LLM:
  - As categorias atuais do Jira com volumes reais
  - Os N grupos naturais descobertos pelo pipeline

O modelo compara os dois e gera:
  - Analise das diferencas
  - Problemas encontrados (lacunas, sobreposicoes, fragmentacoes)
  - Portfolio otimizado sugerido
  - Acoes prioritarias
  - Estimativa de impacto (reducao de vai-e-vem, melhoria de SLA)

Entrada:  pipeline_data/04_labels.json
           pipeline_data/03_clusters.json (para metadados de tickets)
Saida:    pipeline_data/05_portfolio_recommendation.json (sem amostras de texto de chamados)
Tempo estimado: ~2-3 minutos (uma unica chamada LLM longa)
"""

import sys
import json
import unicodedata
from pathlib import Path
from collections import Counter

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.llm_client import generate_json, is_available, OLLAMA_URL

PIPELINE_DATA = Path(__file__).parent.parent / "pipeline_data"
CONFIG_PATH   = Path(__file__).parent.parent / "config_portfolio.json"
INPUT_LABELS = PIPELINE_DATA / "04_labels.json"
INPUT_CLUSTERS = PIPELINE_DATA / "03_clusters.json"
OUTPUT_FILE = PIPELINE_DATA / "05_portfolio_recommendation.json"

PUBLIC_CLUSTER_FIELDS = [
    "cluster_id",
    "nome",
    "descricao",
    "quando_usar",
    "informacoes_necessarias",
    "sla_sugerido",
    "complexidade",
    "volume_percentual",
    "total_tickets",
    "distribuicao_categorias_atuais",
    "rotulo_gerado_por_fallback",
]

PROMPT = """Voce e um consultor senior de ITSM (IT Service Management) especializado em gestao de portfolio de servicos de TI universitarios.

{infra_context}

=== CONTEXTO E OBJETIVO ===
A DTI da FGV atende pesquisadores e docentes de diferentes unidades academicas.
O portfolio atual foi construido ao longo do tempo de forma incremental, resultando em categorias muito especificas e granulares que dificultam a triagem e nao refletem como os usuarios percebem e descrevem seus proprios problemas no momento da abertura.
O objetivo desta analise e propor um portfolio consolidado, com categorias mais amplas e coesas, baseado em como a demanda se organiza naturalmente — e nao nas divisoes tecnicas internas da equipe de TI.
O criterio central de qualidade e: o proprio usuario deve conseguir identificar a categoria correta sem orientacao, e ao abrir o chamado ja fornecer as informacoes necessarias para o atendimento sem idas e vindas.

=== PORTFOLIO ATUAL (base: {total} chamados reais) ===
{categorias_atuais}

=== GRUPOS NATURAIS IDENTIFICADOS POR IA ===
(Descobertos por analise semantica dos chamados, sem pre-conceitos sobre o portfolio atual)
{grupos_naturais}

=== CATEGORIAS FIXAS (JA DECIDIDAS — ja fazem parte do portfolio final) ===
{categorias_obrigatorias}

Estas categorias ja estao definidas e VAO existir no portfolio final exatamente com estes nomes. Trate-as como dadas: NAO as recrie, NAO as renomeie e NAO crie categorias novas que se sobreponham a elas. As marcadas como [ENCAMINHAMENTO] cobrem demanda de outra equipe — mesmo assim ocupam seu espaco e devem ser consideradas ao desenhar as demais.

=== SUA TAREFA ===
Com base nos grupos naturais descobertos (que refletem como a demanda se organiza de fato), e considerando as categorias FIXAS como ja existentes, proponha as categorias COMPLEMENTARES que faltam para cobrir o restante da demanda. O portfolio_otimizado final = categorias fixas + categorias novas que voce criar. Ele deve:
- Cobrir toda a demanda dos grupos naturais que ainda NAO esta coberta pelas categorias fixas
- COMPLEMENTAR as fixas, nunca duplicar: se uma demanda ja cabe numa categoria fixa (ex: um incidente tecnico, um pedido de Sala de Sigilo), nao crie outra categoria para ela
- Consolidar demandas sobrepostas ou relacionadas em grupos coesos
- Usar nomes claros e orientados ao usuario, nao a nomenclatura tecnica interna
- Definir campos obrigatorios precisos por categoria para eliminar o ciclo de perguntas de esclarecimento
- Cada grupo natural deve ser coberto por exatamente UMA categoria (fixa ou nova), sem fragmentacao nem duplicacao
IMPORTANTE: As categorias fixas DEVEM aparecer no portfolio_otimizado com os nomes exatos fornecidos. As categorias novas devem COMPLEMENTAR as fixas, nunca se sobrepor a elas.

Responda APENAS com JSON valido, sem texto adicional:
{{
  "analise_geral": "paragrafos resumindo as principais descobertas da comparacao entre portfolio atual e grupos naturais",

  "problemas_encontrados": [
    {{
      "tipo": "sobreposicao|lacuna|fragmentacao|nomenclatura|volume_desproporcional",
      "severidade": "alta|media|baixa",
      "descricao": "descricao concreta do problema identificado",
      "categorias_envolvidas": ["lista de categorias afetadas"]
    }}
  ],

  "mapeamento_atual_vs_natural": [
    {{
      "categoria_atual": "nome da categoria atual",
      "volume_atual": 0,
      "grupo_natural_correspondente": "nome do grupo natural mais proximo ou null",
      "aderencia": "boa|parcial|baixa|sem_correspondencia",
      "observacao": "comentario sobre a relacao"
    }}
  ],

  "portfolio_otimizado": [
    {{
      "nome": "nome da categoria otimizada (maximo 5 palavras)",
      "descricao": "o que cobre em 1-2 frases",
      "volume_estimado": 0,
      "percentual_volume": 0.0,
      "substitui_categorias_atuais": ["categorias atuais que esta nova categoria substitui"],
      "baseado_nos_grupos": ["grupos naturais que embasam esta categoria"],
      "informacoes_obrigatorias": ["campos que DEVEM ser preenchidos ao abrir"],
      "sla_sugerido": "prazo de resolucao tipico",
      "complexidade": "baixa|media|alta",
      "prioridade_implementacao": "alta|media|baixa"
    }}
  ],

  "acoes_prioritarias": [
    {{
      "acao": "descricao da acao concreta",
      "impacto": "descricao do impacto esperado",
      "prazo": "imediato|curto_prazo|medio_prazo"
    }}
  ],

  "impacto_estimado": {{
    "reducao_vaievem": "estimativa de reducao % de chamados com multiplas interacoes",
    "melhoria_tempo_resolucao": "estimativa de melhoria no tempo medio de resolucao",
    "justificativa": "por que essas melhorias sao esperadas com o portfolio otimizado"
  }}
}}"""


def _norm_nome(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().split())


def _merge_obrigatorias(portfolio_llm: list, cats_obrigatorias: list) -> list:
    """Garante que toda categoria obrigatoria esteja no portfolio_otimizado, com a
    definicao exata do config (nome, descricao, quando_usar, campos, flags como
    'obrigatoria' e 'encaminhamento').

    - Mantem as categorias livres geradas pelo LLM.
    - Obrigatoria ja presente (mesmo nome, ignorando acento/caixa): sobreposta pela
      definicao canonica do config.
    - Obrigatoria ausente: adicionada.
    - O catch-all ("Nao encontrou...") vai sempre para o fim.

    Torna o 05 autossuficiente — nao depende do LLM ter incluido as obrigatorias —
    e consistente com o Stage 6 e o dashboard (que aplicam a mesma regra de merge).
    """
    resultado = [c for c in portfolio_llm if isinstance(c, dict)]
    catch_all = None
    for ob in cats_obrigatorias:
        n = _norm_nome(ob.get("nome", ""))
        if "nao encontrou" in n:
            catch_all = ob
            continue
        # Casa por nome exato OU por prefixo: se a LLM anexou rótulo/descrição ao nome
        # (ex: "Sala de Sigilo... [ENCAMINHAMENTO ...]"), ainda reconhece e substitui
        # pela definição limpa do config — evita categoria duplicada/poluída.
        idx = next((i for i, c in enumerate(resultado)
                    if _norm_nome(c.get("nome", "")) == n
                    or _norm_nome(c.get("nome", "")).startswith(n)), None)
        if idx is not None:
            resultado[idx] = dict(ob)
        else:
            resultado.append(dict(ob))

    # Remove catch-all equivalentes e deduplica por nome normalizado
    visto, dedup = set(), []
    for c in resultado:
        nn = _norm_nome(c.get("nome", ""))
        if "encontrou" in nn or nn in visto:
            continue
        visto.add(nn)
        dedup.append(c)
    if catch_all:
        dedup.append(dict(catch_all))
    return dedup


def main():
    if not is_available():
        print(f"[Stage 5] ERRO: Ollama nao esta rodando em {OLLAMA_URL}")
        sys.exit(1)

    with open(INPUT_LABELS, "r", encoding="utf-8") as f:
        labels_data = json.load(f)

    with open(INPUT_CLUSTERS, "r", encoding="utf-8") as f:
        clusters_data = json.load(f)

    tickets = clusters_data["tickets"]
    total = len(tickets)

    # -- Categorias atuais com volumes reais
    cat_counter = Counter(t.get("tipo_atual", "") for t in tickets)
    categorias_atuais = [
        c for c in sorted(cat_counter, key=cat_counter.get, reverse=True)
        if c and c != "Nao categorizado"
    ]

    categorias_atuais_text = "\n".join(
        f"  {i+1:2d}. {cat} — {cat_counter[cat]} chamados ({cat_counter[cat]/total*100:.1f}%)"
        for i, cat in enumerate(categorias_atuais)
    )

    # -- Grupos naturais
    clusters = labels_data["clusters"]
    clusters_sorted = sorted(clusters, key=lambda x: x["total_tickets"], reverse=True)

    grupos_text = "\n".join(
        f"  {i+1:2d}. [{c['total_tickets']} chamados | {c['volume_percentual']:.1f}%] "
        f"{c['nome']} — {c['descricao']}"
        for i, c in enumerate(clusters_sorted)
    )

    # -- Config: categorias obrigatórias + contexto de infraestrutura
    cats_obrigatorias = []
    infra_context_text = ""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        cats_obrigatorias = cfg.get("categorias_obrigatorias", [])
        infra_context_text = cfg.get("infra_context", {}).get("texto_contexto", "")

    def _fmt_obrigatoria(c: dict) -> str:
        # O nome fica ISOLADO antes do ':' — nenhum rótulo colado a ele, senão a LLM
        # copia o rótulo para dentro do nome da categoria. Notas vão depois da descrição.
        nome   = c.get("nome", "")
        desc   = c.get("descricao", "")
        quando = c.get("quando_usar", "")
        linha  = f"  - {nome}: {desc}"
        if quando:
            linha += f" Usar quando: {quando}."
        if c.get("encaminhamento"):
            linha += " (NOTA: categoria de ENCAMINHAMENTO — demanda atendida por OUTRA equipe; mantenha exatamente este nome, sem variações.)"
        return linha

    obrigatorias_text = "\n".join(
        _fmt_obrigatoria(c) for c in cats_obrigatorias
    ) if cats_obrigatorias else "  (nenhuma definida)"

    n_atual = len(categorias_atuais)
    n_natural = len(clusters)

    print(f"[Stage 5] Comparando {n_atual} categorias atuais vs {n_natural} grupos naturais...")
    print(f"[Stage 5] Categorias obrigatorias: {len(cats_obrigatorias)}")
    print(f"[Stage 5] Base: {total} chamados")
    print("[Stage 5] Gerando recomendacao de portfolio (pode levar 2-5 minutos)...")

    prompt = PROMPT.format(
        infra_context=infra_context_text,
        n_atual=n_atual,
        total=total,
        categorias_atuais=categorias_atuais_text,
        n_natural=n_natural,
        grupos_naturais=grupos_text,
        categorias_obrigatorias=obrigatorias_text,
    )

    recomendacao = None
    for tentativa in range(1, 4):
        try:
            recomendacao = generate_json(
                prompt, temperature=0.2, max_tokens=16384, timeout=600, num_ctx=32768
            )
        except Exception as e:
            print(f"[Stage 5] Tentativa {tentativa}/3 — erro: {e}")
            if tentativa == 3:
                recomendacao = {
                    "falha_geracao": True,
                    "analise_geral": "Falha na geracao da recomendacao.",
                }
            continue

        # Normaliza chaves alternativas que o LLM pode ter usado
        if "portfolio_otimizado" not in recomendacao:
            for alt in ["portfolio_proposto", "portfolio", "categorias_otimizadas", "novo_portfolio"]:
                if alt in recomendacao:
                    val = recomendacao.pop(alt)
                    if isinstance(val, dict):
                        val = [
                            {"nome": k, **(v if isinstance(v, dict) else {"descricao": str(v)})}
                            for k, v in val.items()
                        ]
                    recomendacao["portfolio_otimizado"] = val
                    print(f"[Stage 5] AVISO: LLM usou '{alt}' — corrigido para 'portfolio_otimizado'")
                    break

        portfolio = recomendacao.get("portfolio_otimizado", [])
        cats_validas = [c for c in portfolio if isinstance(c, dict)]
        if len(cats_validas) >= 3:
            print(f"[Stage 5] OK: {len(cats_validas)} categorias validas (tentativa {tentativa})")
            break
        else:
            print(f"[Stage 5] Tentativa {tentativa}/3 — portfolio_otimizado insuficiente ({len(cats_validas)} itens), retentando...")
            recomendacao = None

    # Garante as categorias obrigatorias no portfolio de forma deterministica —
    # o 05 ja nasce completo e consistente com o Stage 6 e o dashboard.
    if isinstance(recomendacao, dict) and isinstance(recomendacao.get("portfolio_otimizado"), list):
        antes = len(recomendacao["portfolio_otimizado"])
        recomendacao["portfolio_otimizado"] = _merge_obrigatorias(
            recomendacao["portfolio_otimizado"], cats_obrigatorias
        )
        depois = len(recomendacao["portfolio_otimizado"])
        if depois != antes:
            print(f"[Stage 5] Categorias obrigatorias mescladas: {antes} -> {depois} no portfolio final")

    output = {
        "metadata": {
            "total_tickets": total,
            "n_categorias_atuais": n_atual,
            "n_grupos_naturais": n_natural,
        },
        "categorias_atuais": {cat: cat_counter[cat] for cat in categorias_atuais},
        "grupos_naturais": [
            {k: c[k] for k in PUBLIC_CLUSTER_FIELDS if k in c}
            for c in clusters_sorted
        ],
        "recomendacao": recomendacao,
    }

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[Stage 5] Recomendacao gerada!")

    if "portfolio_otimizado" in recomendacao:
        portfolio = recomendacao["portfolio_otimizado"]
        cats_dict = [c for c in portfolio if isinstance(c, dict)]
        print(f"\n=== PORTFOLIO OTIMIZADO SUGERIDO ({len(portfolio)} categorias) ===")
        for cat in sorted(cats_dict, key=lambda x: x.get("volume_estimado", 0), reverse=True):
            print(f"  {int(cat.get('volume_estimado', 0)):4d} tickets | {cat.get('nome', '?')}")
        if len(cats_dict) < len(portfolio):
            print(f"  [AVISO] {len(portfolio) - len(cats_dict)} itens com formato inesperado ignorados")

    if "acoes_prioritarias" in recomendacao:
        print(f"\n=== ACOES PRIORITARIAS ===")
        for acao in recomendacao["acoes_prioritarias"][:5]:
            if isinstance(acao, dict):
                print(f"  [{acao.get('prazo','?')}] {acao.get('acao','?')}")
            else:
                print(f"  - {acao}")

    print(f"\n[Stage 5] Salvo em: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
