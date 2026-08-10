#!/usr/bin/env python3
"""
Dashboard de Triagem de Chamados - painel próprio deste projeto.

4 abas: Tipos de Chamado Sugeridos, Indicadores, Prévia do Portal e Histórico.
Lê os artefatos do pipeline (../pipeline_data/*.json) e o banco local em
runtime/knowledge_base.db
do próprio projeto - os caminhos são resolvidos por scripts/projeto.py a partir da
localização deste arquivo, sem variável de ambiente.

A análise (etapas 1-7 do pipeline) é produzida pelos scripts do projeto com
modelos locais via Ollama. Este painel exibe os artefatos gerados e oferece uma
simulação ao vivo opcional via Ollama local ou Azure OpenAI.

  # a partir da pasta do projeto:
  python dashboard/app.py            # http://localhost:5000
"""

import json
import os
import re
import sys
import sqlite3
from dotenv import load_dotenv
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))  # <projeto>/scripts
from projeto import (
    projeto_dir,
    config_path as _cfg_path,
    contexto_catalogo_path as _contexto_catalogo_path,
    db_path as _db_path,
    feedback_path as _feedback_path,
    load_projeto_meta,
)
from llm_client import LLMClient, LLMError

# Carrega o .env do PRÓPRIO projeto (independe do diretório de onde o app é iniciado).
load_dotenv(projeto_dir() / ".env")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

PROJ_DIR      = projeto_dir()
PROJ_META     = load_projeto_meta()
PROJ_NOME     = PROJ_META.get("nome", PROJ_DIR.name)
PROJ_PORTAL_NOME = (
    PROJ_META.get("portal_nome")
    or PROJ_META.get("portal")
    or PROJ_META.get("nome")
    or PROJ_DIR.name
)
DB_PATH       = _db_path()
PIPELINE_DATA = PROJ_DIR / "pipeline_data"
P_RESULT      = PIPELINE_DATA / "05_portfolio_recommendation.json"
P_FINAL       = PIPELINE_DATA / "07_portfolio_final.json"
P_FINAL_CLASS = PIPELINE_DATA / "07_classificados_final.json"
P_FEEDBACK    = _feedback_path()
P_CLASS       = PIPELINE_DATA / "06_classificados.json"
P_QUALITY     = PIPELINE_DATA / "06_quality_report.json"
P_LABELS      = PIPELINE_DATA / "04_labels.json"
P_DIAG_EXEC   = PIPELINE_DATA / "diagnostico_executivo.json"
CONFIG_PATH   = _cfg_path()
CONTEXTO_CATALOGO_PATH = _contexto_catalogo_path()
CATEGORIA_NAO_ANALISAVEL = "Não categorizado"

def _load_json(path: Path):
    """Carrega JSON aceitando UTF-8 com ou sem BOM."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _volumes_reais_por_categoria() -> tuple[dict, dict]:
    """Volumes REAIS por tipo de chamado (Stage 6): (por_id, por_nome).

    Prefere o `06_quality_report.json` — agregado, VERSIONÁVEL e sem dados por
    chamado, o que mantém os cards corretos também num clone do repositório. Cai
    no `06_classificados.json` (local, com PII, fora do git) quando o quality
    report não existe. Vazio quando nenhum está disponível (ex.: método 1 legado,
    cujo portfólio final já traz volumes reais do 07)."""
    if P_QUALITY.exists():
        cats = (_load_json(P_QUALITY) or {}).get("categorias", {}) or {}
        por_nome = {str(k).strip(): int(v) for k, v in cats.items() if str(k).strip()}
        return {}, por_nome
    if P_CLASS.exists():
        por_id: dict[str, int] = {}
        por_nome: dict[str, int] = {}
        for r in _load_json(P_CLASS):
            cid = (r.get("categoria_id") or "").strip()
            nome = (r.get("categoria_nova") or "").strip()
            if cid:
                por_id[cid] = por_id.get(cid, 0) + 1
            if nome:
                por_nome[nome] = por_nome.get(nome, 0) + 1
        return por_id, por_nome
    return {}, {}


def _aplicar_volumes_reais(rec: dict) -> None:
    """Substitui, in-place, os volumes ESTIMADOS do portfólio (Stage 5) pelos
    volumes REAIS da classificação (Stage 6), para que cards, grupos, KPIs e a
    consolidação reflitam a base de fato. Sem efeito quando não há 06_classificados."""
    por_id, por_nome = _volumes_reais_por_categoria()
    if not (por_id or por_nome):
        return
    total_real = sum(por_nome.values()) or 0
    for item in rec.get("portfolio_otimizado", []):
        real = por_id.get(item.get("id"))
        if real is None:
            real = por_nome.get((item.get("nome") or "").strip(), 0)
        item["volume_estimado"] = real
        item["percentual_volume"] = round(real * 100 / total_real, 1) if total_real else 0


def _diag_overlay() -> dict:
    """Curadoria executiva opcional (pipeline_data/diagnostico_executivo.json):
    sobrepõe `analise_geral` / `impacto_estimado` / `acoes_prioritarias` no Painel
    Executivo quando a saída bruta do Stage 5 é procedural demais para
    apresentação. Ausente => usa a análise da própria LLM (caso do método 1)."""
    if not P_DIAG_EXEC.exists():
        return {}
    try:
        return _load_json(P_DIAG_EXEC) or {}
    except Exception:
        return {}


def _carregar_categorias_obrigatorias() -> list:
    if not CONFIG_PATH.exists():
        return []
    cfg = _load_json(CONFIG_PATH)
    return cfg.get("categorias_obrigatorias", [])


def _mesclar_portfolio(portfolio_llm: list) -> list:
    obrigatorias = _carregar_categorias_obrigatorias()
    nomes_llm = {c.get("nome", "").strip().lower() for c in portfolio_llm}

    extras = []
    for cat in obrigatorias:
        cat = dict(cat)
        nome = cat.get("nome", "").strip()
        if not cat.get("grupo"):
            cat["grupo"] = "Outros"
        if nome.lower() not in nomes_llm:
            extras.append(cat)

    return list(portfolio_llm) + extras


def _ordenar_portfolio(portfolio: list) -> list:
    def _ordem(c):
        return (bool(c.get("encaminhamento")), -c.get("volume_estimado", 0))
    portfolio.sort(key=_ordem)
    return portfolio


def _portfolio_final_curado(data: dict) -> list:
    port = [dict(c) for c in data.get("portfolio_final", []) if isinstance(c, dict)]
    for c in port:
        if not c.get("grupo"):
            c["grupo"] = "Outros"
        # Um Stage 7 recem-congelado pode existir antes da projecao automatica
        # por chamado. Nesse caso o volume e desconhecido (null), nao um motivo
        # para esconder o portfolio curado ou voltar ao candidato do Stage 5.
        c["volume_estimado"] = c.get("volume", c.get("volume_estimado", 0)) or 0
        c["percentual_volume"] = c.get("percentual_portfolio", c.get("percentual_volume"))
    return _ordenar_portfolio(port)


def _dados_curadoria() -> dict | None:
    """Retorna a decisao adotada, materializada ou diretamente do feedback."""
    if P_FINAL.exists():
        return _load_json(P_FINAL)
    if P_FEEDBACK.exists():
        return _load_json(P_FEEDBACK)
    return None


def _origens_por_categoria_classificada(path: Path) -> dict[str, set[str]]:
    """Mapeia categoria final -> categorias atuais a partir do 07/06 classificado."""
    if not path.exists():
        return {}
    origens: dict[str, set[str]] = {}
    for row in _load_json(path):
        nova = (row.get("categoria_nova") or "").strip()
        atual = (row.get("tipo_atual") or "").strip()
        if not nova or not atual or atual == CATEGORIA_NAO_ANALISAVEL:
            continue
        origens.setdefault(nova, set()).add(atual)
    return origens


def _resumo_grupos_portfolio(portfolio: list) -> list[dict]:
    grupos = {}
    ordem = []
    for item in portfolio:
        grupo = item.get("grupo") or "Outros"
        if grupo not in grupos:
            grupos[grupo] = {"nome": grupo, "classificacoes": 0, "chamados": 0}
            ordem.append(grupo)
        grupos[grupo]["classificacoes"] += 1
        grupos[grupo]["chamados"] += item.get("volume_estimado") or item.get("volume") or 0
    return sorted((grupos[g] for g in ordem), key=lambda g: (-g["chamados"], g["nome"]))


def _plural(n: int, singular: str, plural: str) -> str:
    return singular if n == 1 else plural


def _mapa_grupos_catalogo_atual() -> dict[str, str]:
    """Lê contexto_catalogo.md e mapeia classificação atual -> agrupador atual."""
    if not CONTEXTO_CATALOGO_PATH.exists():
        return {}

    mapa = {}
    grupo_atual = None
    texto = CONTEXTO_CATALOGO_PATH.read_text(encoding="utf-8-sig")
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha.startswith("## Grupo:"):
            grupo_atual = linha.split(":", 1)[1].strip()
            continue
        if linha.startswith("## Sem grupo definido"):
            grupo_atual = "Sem grupo definido"
            continue
        if not grupo_atual or not linha.startswith("|"):
            continue
        if linha.startswith("|---") or linha.lower().startswith("| crt "):
            continue
        celulas = [c.strip() for c in linha.strip("|").split("|")]
        if not celulas or not celulas[0]:
            continue
        nomes = [n.strip() for n in re.split(r"\s*/\s*", celulas[0]) if n.strip()]
        for nome in nomes:
            mapa.setdefault(nome, grupo_atual)
    return mapa


def _grupos_atuais_com_volume(categorias_atuais: dict) -> list[dict]:
    mapa_grupos = _mapa_grupos_catalogo_atual()
    grupos = {}
    for nome, volume in sorted(categorias_atuais.items(), key=lambda item: item[1], reverse=True):
        grupo = mapa_grupos.get(nome, "Sem grupo definido")
        if grupo not in grupos:
            grupos[grupo] = {"nome": grupo, "total": 0, "classificacoes": []}
        grupos[grupo]["total"] += volume
        grupos[grupo]["classificacoes"].append({"nome": nome, "volume": volume})

    total = sum(g["total"] for g in grupos.values()) or 1
    for grupo in grupos.values():
        for item in grupo["classificacoes"]:
            item["percentual"] = round(item["volume"] * 100 / total, 1)
    return sorted(grupos.values(), key=lambda g: (-g["total"], g["nome"]))


def _consolidacao_catalogo(
    rec: dict,
    categorias_atuais: dict | None = None,
    portfolio_override: list | None = None,
    origens_por_categoria: dict[str, set[str]] | None = None,
) -> list:
    """Visão organizacional 'novo -> atuais': cada chamado proposto e as
    classificações atuais que ele consolida, organizado por agrupador lógico.

    Fonte primária: `substitui_categorias_atuais` de cada chamado do portfólio
    otimizado (o mapeamento lógico curado pela análise). Para não deixar nenhuma
    categoria atual de fora, faz um fallback pelo `mapeamento_atual_vs_natural`
    (grupo natural dominante -> chamado que nasceu desse grupo).

    `categorias_atuais` (volume por categoria) fica na raiz do 05, não em `rec`;
    o chamador passa esse dicionário para ordenar as origens por volume.
    """
    if not isinstance(rec, dict):
        return []
    portfolio = portfolio_override if portfolio_override is not None else rec.get("portfolio_otimizado", []) or []
    if not portfolio:
        return []

    mapeamento = rec.get("mapeamento_atual_vs_natural", []) or []
    # Volume por categoria atual: usa o dicionário da raiz e, como reforço,
    # completa com volume_atual do mapeamento (para ordenar origens por volume).
    vol_atual = dict(categorias_atuais or {})
    for m in mapeamento:
        cat = m.get("categoria_atual")
        if cat and cat not in vol_atual and m.get("volume_atual") is not None:
            vol_atual[cat] = m.get("volume_atual")

    # chamado novo -> info (grupo, volume, categorias atuais que ele substitui)
    por_chamado = {}
    # grupo natural -> nome do chamado novo que nasceu dele
    chamado_por_grupo_natural = {}
    chamado_por_id = {}
    for cat in portfolio:
        nome = cat.get("nome", "")
        if not nome:
            continue
        category_id = str(cat.get("id", "")).strip()
        if category_id:
            chamado_por_id[category_id] = nome
        origens_classificadas = sorted((origens_por_categoria or {}).get(nome, set()))
        por_chamado[nome] = {
            "novo": nome,
            "grupo": cat.get("grupo") or "Outros",
            "volume": cat.get("volume_estimado") or cat.get("volume") or 0,
            "origens": origens_classificadas or list(cat.get("substitui_categorias_atuais", []) or []),
        }
        for gn in cat.get("baseado_nos_grupos", []) or []:
            chamado_por_grupo_natural.setdefault(gn, nome)

    # Cobertura: encaixa categorias atuais ainda não citadas em nenhum chamado.
    cobertas = {c for info in por_chamado.values() for c in info["origens"]}
    for m in mapeamento:
        cat_atual = m.get("categoria_atual")
        if not cat_atual or cat_atual in cobertas:
            continue
        alvo = chamado_por_id.get(str(m.get("destino_id", "")).strip())
        if not alvo:
            observed = m.get("grupos_naturais_observados", []) or []
            for relation in observed:
                if not isinstance(relation, dict):
                    continue
                alvo = chamado_por_grupo_natural.get(relation.get("nome"))
                if alvo:
                    break
        if not alvo:
            alvo = chamado_por_grupo_natural.get(
                m.get("grupo_natural_correspondente")
            )
        if alvo and alvo in por_chamado:
            por_chamado[alvo]["origens"].append(cat_atual)
            cobertas.add(cat_atual)

    # Ordena as categorias de origem de cada chamado por volume atual (desc).
    for info in por_chamado.values():
        info["origens"] = sorted(
            set(info["origens"]), key=lambda c: (-vol_atual.get(c, 0), c)
        )

    # Agrupa por agrupador lógico, preservando a ordem de grupos_otimizados.
    ordem_grupos = [g.get("nome") for g in rec.get("grupos_otimizados", []) if g.get("nome")]
    grupos, ordem = {}, []
    for info in por_chamado.values():
        g = info["grupo"]
        if g not in grupos:
            grupos[g] = []
            ordem.append(g)
        grupos[g].append(info)

    def _ordem_grupo(g):
        return ordem_grupos.index(g) if g in ordem_grupos else len(ordem_grupos) + ordem.index(g)

    # O volume exibido AQUI e o ANTIGO (soma dos tipos atuais consolidados), nao o
    # volume por conteudo do Stage 7. Sao leituras distintas em paineis separados:
    # migracao curada aqui, distribuicao por conteudo no Painel Executivo.
    def _vol_antigo(info):
        return sum(vol_atual.get(o, 0) for o in info["origens"])

    resultado = []
    for g in sorted(ordem, key=_ordem_grupo):
        chamados = sorted(grupos[g], key=lambda c: (-_vol_antigo(c), c["novo"]))
        resultado.append({
            "grupo": g,
            "volume": sum(_vol_antigo(c) for c in chamados),
            "chamados": [
                {
                    "novo": c["novo"],
                    "volume": _vol_antigo(c),
                    "origens": [
                        {"nome": o, "volume": vol_atual.get(o, 0)}
                        for o in c["origens"]
                    ],
                    "n_origens": len(c["origens"]),
                }
                for c in chamados
            ],
        })
    return resultado


def _pct_br(parte: float, total: float, clamp: bool = False) -> str:
    """Percentual em formato pt-BR (vírgula decimal), sem travessão."""
    if not total:
        return "0"
    valor = round(parte * 100 / total, 1)
    if clamp:
        valor = max(0, min(100, valor))
    return str(valor).replace(".", ",")


def _diagnostico_executivo(
    meta: dict,
    portfolio: list,
    total_tickets: int,
    usando_curadoria: bool,
    metricas: dict | None = None,
    categorias_atuais: dict | None = None,
    rec: dict | None = None,
):
    """Diagnóstico executivo (Painel Executivo): retorna dict estruturado com
    lead + KPIs de insight + ações prioritárias.

    O lead e as ações vêm da ANÁLISE REAL da LLM (Stage 5: `analise_geral`,
    `impacto_estimado`, `acoes_prioritarias`) quando disponível — é a leitura do
    "como era → como ficou / por que faz sentido" já produzida no pipeline. Os
    KPIs impacto (redução de vai-e-vem, tempo) vêm do `impacto_estimado` quando
    numéricos; os demais KPIs são a LEITURA dos dados (concentração, redundância,
    resolução direta, ruído externo). Sem travessão. Cai em heurísticas só quando
    o artefato não trouxer o campo correspondente.
    """
    total = total_tickets or meta.get("total_tickets", 0) or sum(
        item.get("volume_estimado") or item.get("volume") or 0 for item in portfolio
    )
    atuais = meta.get("n_categorias_atuais") or len(categorias_atuais or {}) or len(meta.get("categorias_atuais", {})) or 0
    grupos = _resumo_grupos_portfolio(portfolio)
    n_grupos = len(grupos)
    n_classificacoes = len(portfolio)

    reducao = atuais - n_classificacoes if (atuais and atuais > n_classificacoes) else 0
    reducao_pct = _pct_br(reducao, atuais)

    enc_grupo = next((g for g in grupos if "encaminh" in g["nome"].lower()), None)
    enc_vol = enc_grupo["chamados"] if enc_grupo else 0

    # --- Conteúdo REAL da LLM (Stage 5), quando presente no artefato ---
    rec = rec or {}
    analise = (rec.get("analise_geral") or "").strip()
    impacto = rec.get("impacto_estimado") if isinstance(rec.get("impacto_estimado"), dict) else {}
    justificativa = (impacto.get("justificativa") or "").strip()

    if analise:
        # Narrativa executiva "como era → como ficou" produzida pela LLM no pipeline.
        lead = analise
        if justificativa and justificativa.lower() not in analise.lower():
            lead = f"{analise} {justificativa}"
        lead_destaque = ""  # texto da LLM é livre; sem realce fixo
    else:
        lead = "O ganho está na organização do catálogo, não no volume de chamados."
        lead_destaque = "organização do catálogo"

    kpis = []
    # KPIs de impacto vindos do artefato (LLM ou curadoria executiva). Só entram
    # quando o valor é numérico/percentual; rótulo e cor por chave conhecida.
    _tem_num = lambda v: bool(re.search(r"\d", str(v or "")))
    _IMPACTO_META = (
        ("reducao_vaievem", "redução estimada de idas e vindas", "green"),
        ("melhoria_tempo_resolucao", "melhoria estimada no tempo de resolução", "blue"),
        ("cobertura", "cobertura (chamados classificados)", "green"),
        ("catch_all", "em categoria genérica (catch-all)", "green"),
        ("revisao", "sinalizados para revisão humana", "orange"),
    )
    for chave, label, cor in _IMPACTO_META:
        val = impacto.get(chave)
        if _tem_num(val):
            kpis.append({"valor": str(val).strip(), "label": label, "cor": cor})
    # KPIs de LEITURA dos dados (concentração, redundância, resolução direta, ruído externo).
    top2_vol = (grupos[0]["chamados"] + grupos[1]["chamados"]) if n_grupos >= 2 else 0
    # So exibe concentracao quando ha volume por categoria (curadoria sem Stage 7 fica em 0).
    if total and top2_vol > 0:
        top2_pct = _pct_br(top2_vol, total, clamp=True)
        kpis.append({"valor": f"{top2_pct}%", "label": "dos chamados em 2 grupos", "cor": "blue"})
    if reducao:
        kpis.append({"valor": f"{reducao_pct}%", "label": "tipos de chamado redundantes", "cor": "orange"})
    if metricas and metricas.get("pct_diretos") is not None:
        pct_diretos_num = float(metricas.get("pct_diretos") or 0)
        pct_diretos = str(round(pct_diretos_num, 1)).replace(".", ",")
        cor = "green" if pct_diretos_num >= 70 else "orange" if pct_diretos_num >= 40 else "gray"
        kpis.append({"valor": f"{pct_diretos}%", "label": "resolvidos em 1 interação", "cor": cor})
    if enc_vol:
        kpis.append({"valor": str(enc_vol), "label": "chamados de ruído externo", "cor": "gray"})

    # Ações: prioriza as ações prioritárias REAIS da LLM; senão, cai nas heurísticas.
    acoes = []
    for a in (rec.get("acoes_prioritarias") or []):
        if isinstance(a, dict):
            s = (a.get("acao") or a.get("descricao") or a.get("titulo") or "").strip()
        else:
            s = str(a).strip()
        if s:
            acoes.append(s)
    if not acoes:
        if total and n_grupos >= 2:
            acoes.append(
                "Comece pelos 2 maiores grupos: cobrem a maior fatia do volume com o "
                "menor esforço de implantação."
            )
        if metricas and metricas.get("pct_multiplas"):
            pct_multiplas = str(metricas.get("pct_multiplas")).replace(".", ",")
            acoes.append(
                f"Padronize campos obrigatórios: ataca os {pct_multiplas}% que exigem "
                "idas e vindas e puxam o tempo médio."
            )
        if not acoes:
            acoes.append(
                "Consolide o catálogo em grupos de chamados para reduzir a ambiguidade na triagem."
            )

    return {"lead": lead, "lead_destaque": lead_destaque, "kpis": kpis, "acoes": acoes}


def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _db_tem_chamados() -> bool:
    if not DB_PATH.exists():
        return False
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'chamados'")
        return cur.fetchone() is not None
    except sqlite3.Error:
        return False
    finally:
        if conn is not None:
            conn.close()


def calcular_metricas_interacoes():
    if not _db_tem_chamados():
        return None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'nao'                THEN 1
                    WHEN descricao_insuficiente IS NULL AND qtd_interacoes <= 1 THEN 1
                END) AS diretos,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'sim'                THEN 1
                    WHEN descricao_insuficiente IS NULL AND qtd_interacoes > 1  THEN 1
                END) AS insuficientes,
                COUNT(CASE WHEN descricao_insuficiente IN ('sim','nao') THEN 1 END) AS enriquecidos
            FROM chamados
            WHERE tipo_solicitacao IS NOT NULL
        """)
        row = cur.fetchone()
        conn.close()
        if not row or row["total"] == 0:
            return None
        return {
            "pct_diretos":      round(row["diretos"] / row["total"] * 100, 1),
            "pct_multiplas":    round(row["insuficientes"] / row["total"] * 100, 1),
            "fonte":            "llm" if row["enriquecidos"] > 0 else "qtd_interacoes",
            "pct_enriquecidos": round(row["enriquecidos"] / row["total"] * 100, 1),
        }
    except Exception:
        return None


def tabela_interacoes_por_categoria() -> list:
    if not _db_tem_chamados():
        return []
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT
                tipo_solicitacao AS categoria,
                COUNT(*) AS total,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'nao'                         THEN 1
                    WHEN descricao_insuficiente IS NULL AND qtd_interacoes <= 1 THEN 1
                END) AS diretos,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'sim'                         THEN 1
                    WHEN descricao_insuficiente IS NULL AND qtd_interacoes > 1  THEN 1
                END) AS multiplos,
                ROUND(AVG(qtd_interacoes), 2) AS media_interacoes,
                ROUND(AVG(CASE WHEN tempo_total_horas > 0 THEN tempo_total_horas END), 1) AS tempo_medio_horas,
                ROUND(SUM(resolvido) * 100.0 / COUNT(*), 1) AS taxa_resolucao,
                ROUND(AVG(CASE
                    WHEN (descricao_insuficiente = 'nao'
                          OR (descricao_insuficiente IS NULL AND qtd_interacoes <= 1))
                         AND tempo_total_horas > 0
                    THEN tempo_total_horas END), 1) AS t_medio_direto,
                ROUND(AVG(CASE
                    WHEN (descricao_insuficiente = 'sim'
                          OR (descricao_insuficiente IS NULL AND qtd_interacoes > 1))
                         AND tempo_total_horas > 0
                    THEN tempo_total_horas END), 1) AS t_medio_multiplo
            FROM chamados
            WHERE tipo_solicitacao IS NOT NULL
            GROUP BY tipo_solicitacao
            ORDER BY total DESC
        """)
        rows = cur.fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Normalização de linguagem (deixa a saída consistente na UI)
# ---------------------------------------------------------------------------

def _normalizar_texto(texto: str) -> str:
    if not texto:
        return texto
    subs = [
        (r"\bvai[\s\-]e[\s\-]vem\b", "múltiplas interações"),
        (r"\bVai[\s\-]e[\s\-]Vem\b", "Múltiplas Interações"),
        (r"\bvaievem\b",             "múltiplas interações"),
    ]
    for pattern, replacement in subs:
        texto = re.sub(pattern, replacement, texto, flags=re.IGNORECASE)
    return texto


def _norm(obj):
    if isinstance(obj, str):
        return _normalizar_texto(obj)
    if isinstance(obj, list):
        return [_norm(i) for i in obj]
    if isinstance(obj, dict):
        return {k: _norm(v) for k, v in obj.items()}
    return obj


# ---------------------------------------------------------------------------
# Páginas
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template(
        "index.html",
        projeto_nome=PROJ_NOME,
        portal_nome=PROJ_PORTAL_NOME,
    )


# ---------------------------------------------------------------------------
# Helpers de filtro
# ---------------------------------------------------------------------------

def _where_mes(mes: str) -> tuple:
    if mes:
        return "WHERE strftime('%Y-%m', data_criacao) = ?", (mes,)
    return "", ()


def _and_mes(mes: str) -> tuple:
    if mes:
        return "AND strftime('%Y-%m', data_criacao) = ?", (mes,)
    return "", ()


def _where_categoria_util(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return (
        f"{prefix}tipo_solicitacao IS NOT NULL "
        f"AND {prefix}tipo_solicitacao != '' "
        f"AND {prefix}tipo_solicitacao != '{CATEGORIA_NAO_ANALISAVEL}'"
    )


@app.route("/api/projeto")
def get_projeto():
    """Metadados do projeto ativo (para título/rodapé da UI)."""
    return jsonify({
        "nome": PROJ_PORTAL_NOME,
        "projeto_nome": PROJ_NOME,
        "portal_nome": PROJ_PORTAL_NOME,
        "portal": PROJ_META.get("portal", ""),
        "descricao": PROJ_META.get("descricao", ""),
    })


@app.route("/api/meses")
def get_meses():
    if not _db_tem_chamados():
        return jsonify([])
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT strftime('%Y-%m', data_criacao) AS mes
        FROM chamados
        WHERE data_criacao IS NOT NULL
        ORDER BY mes DESC
    """)
    meses = [r["mes"] for r in cur.fetchall() if r["mes"]]
    conn.close()
    return jsonify(meses)


# ---------------------------------------------------------------------------
# API: Indicadores
# ---------------------------------------------------------------------------

@app.route("/api/dashboard")
def dashboard():
    mes = request.args.get("mes", "")
    w, wp = _where_mes(mes)
    a, ap = _and_mes(mes)

    if not _db_tem_chamados():
        ia_resumo = None
        portfolio = _portfolio_ativo()
        if portfolio:
            ia_resumo = {"categorias_recomendadas": len(portfolio)}
        return jsonify({
            "total_chamados": 0, "total_categorias": 0, "taxa_resolucao": "N/A",
            "backlog": 0, "finalizados": 0, "taxa_reabertura": "0.0%",
            "distribuicao_categorias": [], "distribuicao_situacoes": [],
            "tempo_por_categoria": [], "tendencia_mensal": [], "top_analistas": [],
            "top_solicitantes": [], "por_departamento": [], "ia_resumo": ia_resumo,
        })

    conn = get_db()
    cur = conn.cursor()

    cur.execute(f"SELECT COUNT(*) as c FROM chamados {w}", wp)
    total = cur.fetchone()["c"]

    cur.execute(f"""
        SELECT COUNT(DISTINCT tipo_solicitacao) as c
        FROM chamados
        WHERE {_where_categoria_util()} {a}
    """, ap)
    cats = cur.fetchone()["c"]

    cur.execute(f"SELECT ROUND(SUM(resolvido)*100.0/COUNT(*),1) as taxa FROM chamados {w}", wp)
    taxa = cur.fetchone()["taxa"]

    cur.execute(f"SELECT SUM(finalizado) as c FROM chamados {w}", wp)
    finalizados = cur.fetchone()["c"] or 0

    cur.execute(f"SELECT COUNT(*) as c FROM chamados WHERE finalizado = 0 {a}", ap)
    backlog = cur.fetchone()["c"]

    cur.execute(f"""
        SELECT tipo_solicitacao, COUNT(*) as total
        FROM chamados
        WHERE {_where_categoria_util()} {a}
        GROUP BY tipo_solicitacao ORDER BY total DESC LIMIT 8
    """, ap)
    dist = [{"nome": r["tipo_solicitacao"], "total": r["total"]} for r in cur.fetchall()]

    cur.execute(f"""
        SELECT situacao, COUNT(*) as total,
               SUM(resolvido) as resolvidos,
               SUM(finalizado - resolvido) as cancelados
        FROM chamados
        WHERE situacao IS NOT NULL {a}
        GROUP BY situacao ORDER BY total DESC
    """, ap)
    situacoes = [
        {"nome": r["situacao"], "total": r["total"],
         "resolvidos": r["resolvidos"] or 0, "cancelados": r["cancelados"] or 0}
        for r in cur.fetchall()
    ]

    cur.execute(f"""
        SELECT tipo_solicitacao as nome, ROUND(AVG(tempo_total_horas), 1) as tempo
        FROM chamados
        WHERE {_where_categoria_util()} AND tempo_total_horas > 0 {a}
        GROUP BY tipo_solicitacao ORDER BY tempo DESC LIMIT 8
    """, ap)
    tempos = [{"nome": r["nome"][:40], "tempo": r["tempo"]} for r in cur.fetchall()]

    cur.execute(f"""
        SELECT strftime('%Y-%m', data_criacao) as mes, COUNT(*) as total
        FROM chamados
        WHERE data_criacao IS NOT NULL {a}
        GROUP BY mes ORDER BY mes
    """, ap)
    tendencia = [{"mes": r["mes"], "total": r["total"]} for r in cur.fetchall()]

    cur.execute(f"""
        SELECT responsavel, COUNT(*) as total
        FROM chamados
        WHERE responsavel IS NOT NULL AND responsavel != '' {a}
        GROUP BY responsavel ORDER BY total DESC LIMIT 10
    """, ap)
    analistas = [{"nome": r["responsavel"], "total": r["total"]} for r in cur.fetchall()]

    cur.execute(f"""
        SELECT c.solicitante, COUNT(*) as total,
            (SELECT c2.dpto_solicitante FROM chamados c2
             WHERE c2.solicitante = c.solicitante AND c2.dpto_solicitante IS NOT NULL AND c2.dpto_solicitante != ''
             GROUP BY c2.dpto_solicitante ORDER BY COUNT(*) DESC LIMIT 1) as dpto
        FROM chamados c
        WHERE c.solicitante IS NOT NULL AND c.solicitante != '' {a}
        GROUP BY c.solicitante ORDER BY total DESC LIMIT 10
    """, ap)
    solicitantes = [{"nome": r["solicitante"], "dpto": r["dpto"] or "", "total": r["total"]} for r in cur.fetchall()]

    cur.execute(f"""
        SELECT dpto_solicitante, COUNT(*) as total
        FROM chamados
        WHERE dpto_solicitante IS NOT NULL AND dpto_solicitante != '' {a}
        GROUP BY dpto_solicitante ORDER BY total DESC LIMIT 10
    """, ap)
    departamentos = [{"nome": r["dpto_solicitante"], "total": r["total"]} for r in cur.fetchall()]

    cur.execute(f"SELECT COUNT(*) as c FROM chamados {w or 'WHERE'} {'AND' if w else ''} chamado_reaberto = 1"
                .replace("WHERE AND", "WHERE"), wp)
    reabertos = cur.fetchone()["c"]
    taxa_reabertura = round(reabertos / total * 100, 1) if total else 0

    conn.close()

    ia_resumo = None
    portfolio = _portfolio_ativo()
    if portfolio:
        ia_resumo = {"categorias_recomendadas": len(portfolio)}

    return jsonify({
        "total_chamados": total,
        "total_categorias": cats,
        "taxa_resolucao": f"{taxa:.1f}%" if taxa is not None else "N/A",
        "backlog": backlog,
        "finalizados": finalizados,
        "taxa_reabertura": f"{taxa_reabertura:.1f}%",
        "distribuicao_categorias": dist,
        "distribuicao_situacoes": situacoes,
        "tempo_por_categoria": tempos,
        "tendencia_mensal": tendencia,
        "top_analistas": analistas,
        "top_solicitantes": solicitantes,
        "por_departamento": departamentos,
        "ia_resumo": ia_resumo,
    })


# ---------------------------------------------------------------------------
# API: Classificação Sugerida
# ---------------------------------------------------------------------------

@app.route("/api/categorias")
def get_categorias():
    if not _db_tem_chamados():
        return jsonify([])

    conn = get_db()
    cur = conn.cursor()
    cur.execute(f"""
        SELECT
            tipo_solicitacao AS nome,
            COUNT(*) AS total_chamados,
            ROUND(AVG(CASE WHEN tempo_total_horas > 0 THEN tempo_total_horas END), 1) AS tempo_medio_horas,
            ROUND(AVG(qtd_interacoes), 2) AS media_interacoes,
            ROUND(SUM(resolvido) * 100.0 / COUNT(*), 1) AS taxa_resolucao
        FROM chamados
        WHERE {_where_categoria_util()}
        GROUP BY tipo_solicitacao
        ORDER BY total_chamados DESC
    """)
    cats = [dict(r) for r in cur.fetchall()]
    conn.close()

    mapeamento = {}
    classificados_path = _classificados_ativo_path()
    if classificados_path.exists():
        from collections import Counter, defaultdict
        por_atual = defaultdict(Counter)
        for item in _load_json(classificados_path):
            cat_atual = item.get("tipo_atual") or "Não categorizado"
            nova_cat = item.get("categoria_nova") or "Sem classificação"
            por_atual[cat_atual][nova_cat] += 1

        fonte = "curadoria final (Stage 7)" if _fonte_classificacao_ativa() == "stage7" else "classificação automática (Stage 6)"
        for cat_atual, cont in por_atual.items():
            nome_novo, qtd = cont.most_common(1)[0]
            total_cat = sum(cont.values()) or 1
            mapeamento[cat_atual] = {
                "nova_categoria": nome_novo,
                "aderencia": f"{round(qtd * 100 / total_cat, 1)}%",
                "observacao": f"Mapeamento por maioria com base na {fonte}.",
            }
    elif P_RESULT.exists():
        rec_data = _load_json(P_RESULT)
        portfolio = rec_data.get("recomendacao", {}).get("portfolio_otimizado", [])
        for nova_cat in portfolio:
            nome_novo = nova_cat.get("nome", "")
            prioridade = nova_cat.get("prioridade_implementacao", "media")
            for cat_antiga in nova_cat.get("substitui_categorias_atuais", []):
                if cat_antiga:
                    mapeamento[cat_antiga] = {
                        "nova_categoria": nome_novo,
                        "aderencia": prioridade,
                        "observacao": nova_cat.get("descricao", ""),
                    }

    for cat in cats:
        cat["mapeamento_novo"] = mapeamento.get(cat["nome"], {
            "nova_categoria": "A definir",
            "aderencia": "indefinida",
            "observacao": "Não mapeada explicitamente pelo modelo.",
        })

    return jsonify(cats)


@app.route("/api/mapeamento-detalhado")
def get_mapeamento_detalhado():
    from collections import defaultdict
    breakdown = defaultdict(int)
    fonte = "nenhum"

    classificados_path = _classificados_ativo_path()
    clusters_path = PIPELINE_DATA / "03_clusters.json"

    if classificados_path.exists():
        for item in _load_json(classificados_path):
            cat_atual = item.get("tipo_atual") or "Não categorizado"
            nova_cat = item.get("categoria_nova") or "Sem classificação"
            grupo_novo = item.get("grupo_novo") or ""
            breakdown[(cat_atual, nova_cat, grupo_novo)] += 1
        fonte = _fonte_classificacao_ativa()
    elif P_LABELS.exists() and P_RESULT.exists() and clusters_path.exists():
        labels = _load_json(P_LABELS)
        result = _load_json(P_RESULT)
        portfolio = _mesclar_portfolio(result.get("recomendacao", {}).get("portfolio_otimizado", []))
        cluster_to_nova = {}
        outlier_to_nova = {}
        grupo_por_nova = {}
        for nova in portfolio:
            grupo_por_nova[nova.get("nome", "")] = nova.get("grupo", "")
            for grupo in nova.get("baseado_nos_grupos", []):
                if grupo:
                    cluster_to_nova[grupo] = nova["nome"]
            for outlier_id in nova.get("baseado_nos_outliers", []):
                if outlier_id:
                    outlier_to_nova[outlier_id] = nova["nome"]
        c_data = _load_json(clusters_path)
        id_to_nome = {c["cluster_id"]: c["nome"] for c in labels.get("clusters", [])}
        for ticket in c_data.get("tickets", []):
            cid = ticket.get("cluster_id")
            cluster_nome = id_to_nome.get(cid, "")
            nova = cluster_to_nova.get(cluster_nome)
            if not nova:
                nova = outlier_to_nova.get(
                    ticket.get("outlier_id"), "Sem classificação"
                )
            grupo_novo = grupo_por_nova.get(nova, "")
            cat_atual = ticket.get("tipo_atual") or "Não categorizado"
            breakdown[(cat_atual, nova, grupo_novo)] += 1
        fonte = "stage3"

    if not breakdown:
        return jsonify([])

    stats = {}
    if _db_tem_chamados():
        conn = get_db()
        cur = conn.cursor()
        cur.execute(f"""
            SELECT tipo_solicitacao AS nome,
                   COUNT(*) AS total_chamados,
                   ROUND(AVG(CASE WHEN tempo_total_horas > 0 THEN tempo_total_horas END), 1) AS tempo_medio_horas,
                   ROUND(AVG(qtd_interacoes), 2) AS media_interacoes,
                   ROUND(SUM(resolvido) * 100.0 / COUNT(*), 1) AS taxa_resolucao
            FROM chamados
            WHERE {_where_categoria_util()}
            GROUP BY tipo_solicitacao
        """)
        stats = {r["nome"]: dict(r) for r in cur.fetchall()}
        conn.close()

    rows = []
    for (cat_atual, nova_cat, grupo_novo), chamados in sorted(breakdown.items(), key=lambda x: -x[1]):
        s = stats.get(cat_atual, {})
        rows.append({
            "categoria_atual": cat_atual,
            "nova_categoria": nova_cat,
            "grupo_novo": grupo_novo,
            "chamados": chamados,
            "total_categoria": s.get("total_chamados", 0),
            "tempo_medio_horas": s.get("tempo_medio_horas"),
            "media_interacoes": s.get("media_interacoes"),
            "taxa_resolucao": s.get("taxa_resolucao"),
            "fonte": fonte,
        })
    return jsonify(rows)


@app.route("/api/historico")
def get_historico():
    page = int(request.args.get("page", 1))
    limit = int(request.args.get("limit", 50))
    busca = request.args.get("q", "").strip().lower()
    offset = (page - 1) * limit

    if not _db_tem_chamados():
        return jsonify({
            "total": 0, "page": page, "limit": limit, "tickets": [],
            "tem_dados_pipeline": False, "fonte": "nenhum",
        })

    cluster_map = {}
    classificados_path = _classificados_ativo_path()
    clusters_path = PIPELINE_DATA / "03_clusters.json"
    grupo_por_categoria = {}
    try:
        grupo_por_categoria = {
            c.get("nome"): c.get("grupo")
            for c in _portfolio_ativo()
            if c.get("nome")
        }
    except Exception:
        grupo_por_categoria = {}

    if classificados_path.exists():
        for item in _load_json(classificados_path):
            chave = item.get("chave")
            cat = item.get("categoria_nova")
            grupo = item.get("grupo_novo") or grupo_por_categoria.get(cat)
            conf = item.get("confianca")
            if chave and cat:
                cluster_map[chave] = {"categoria": cat, "grupo": grupo, "confianca": conf}
    elif clusters_path.exists() and P_LABELS.exists():
        c_data = _load_json(clusters_path)
        labels = _load_json(P_LABELS)
        id_to_nome = {c["cluster_id"]: c["nome"] for c in labels.get("clusters", [])}
        for ticket in c_data.get("tickets", []):
            chave = ticket.get("chave")
            cid = ticket.get("cluster_id")
            if chave and cid is not None:
                cluster_map[chave] = {"categoria": id_to_nome.get(cid, "-"), "confianca": None}

    conn = get_db()
    cur = conn.cursor()
    where = "WHERE 1=1"
    params = []
    if busca:
        where += " AND (LOWER(titulo) LIKE ? OR LOWER(chave) LIKE ?)"
        params += [f"%{busca}%", f"%{busca}%"]

    cur.execute(f"SELECT COUNT(*) as c FROM chamados {where}", params)
    total = cur.fetchone()["c"]

    cur.execute(f"""
        SELECT chave, titulo, descricao, tipo_solicitacao, situacao
        FROM chamados {where}
        ORDER BY data_criacao DESC
        LIMIT ? OFFSET ?
    """, params + [limit, offset])
    tickets = [dict(r) for r in cur.fetchall()]
    conn.close()

    for t in tickets:
        info = cluster_map.get(t["chave"])
        t["categoria_llm"] = info["categoria"] if info else None
        t["grupo_llm"] = info.get("grupo") if info else None
        t["confianca_llm"] = info["confianca"] if info else None

    return jsonify({
        "total": total, "page": page, "limit": limit, "tickets": tickets,
        "tem_dados_pipeline": bool(cluster_map),
        "fonte": _fonte_classificacao_ativa() if classificados_path.exists() else ("stage3" if clusters_path.exists() else "nenhum"),
    })


@app.route("/api/portfolio-novo")
def get_portfolio_novo():
    curadoria = _dados_curadoria()
    if curadoria is not None:
        return jsonify(_norm(_portfolio_final_curado(curadoria)))

    portfolio_llm = []
    if P_RESULT.exists():
        data = _load_json(P_RESULT)
        portfolio_llm = data.get("recomendacao", {}).get("portfolio_otimizado", [])

    portfolio = _mesclar_portfolio(portfolio_llm)

    classificados_path = _classificados_ativo_path()
    if classificados_path.exists():
        from collections import Counter
        cont = Counter((item.get("categoria_nova") or "").strip()
                       for item in _load_json(classificados_path))
        enc_nomes = {c.get("nome", "").strip() for c in portfolio if c.get("encaminhamento")}
        base = sum(n for nome, n in cont.items() if nome not in enc_nomes) or 1
        for cat in portfolio:
            real = cont.get(cat.get("nome", "").strip(), 0)
            cat["volume_estimado"] = real
            cat["percentual_volume"] = None if cat.get("encaminhamento") else round(real / base * 100, 1)

    def _ordem(c):
        return (bool(c.get("encaminhamento")), -c.get("volume_estimado", 0))
    portfolio.sort(key=_ordem)

    return jsonify(_norm(portfolio))


@app.route("/api/portfolio-final")
def get_portfolio_final():
    data = _dados_curadoria()
    if data is None:
        return jsonify([])
    return jsonify(_norm(_portfolio_final_curado(data)))


def _portfolio_ativo() -> list:
    curadoria = _dados_curadoria()
    if curadoria is not None:
        return _portfolio_final_curado(curadoria)
    if P_RESULT.exists():
        d = _load_json(P_RESULT)
        return _mesclar_portfolio(d.get("recomendacao", {}).get("portfolio_otimizado", []))
    return []


def _classificados_ativo_path():
    return P_FINAL_CLASS if P_FINAL.exists() and P_FINAL_CLASS.exists() else (PIPELINE_DATA / "06_classificados.json")


def _fonte_classificacao_ativa() -> str:
    return "stage7" if P_FINAL.exists() and P_FINAL_CLASS.exists() else "stage6"


# ---------------------------------------------------------------------------
# Simulação ao vivo - monta o prompt e faz o parse do JSON de resposta
# ---------------------------------------------------------------------------

def _categorias_para_prompt():
    """Retorna (texto_categorias, portfolio, infra_ctx) para o prompt de simulação."""
    portfolio = _portfolio_ativo()
    cats_texto = "\n".join(
        f"- {c.get('grupo','Outros')} > {c.get('nome','')}: {c.get('descricao','')} | Usar quando: {c.get('quando_usar','')}"
        for c in portfolio if c.get("nome")
    )
    infra_ctx = ""
    if CONFIG_PATH.exists():
        cfg = _load_json(CONFIG_PATH)
        infra_ctx = cfg.get("infra_context", {}).get("texto_contexto", "")
    return cats_texto, portfolio, infra_ctx


_INSTRUCAO_SIM = (
    "Responda SOMENTE com JSON válido. Campos: "
    "titulo_sugerido (título conciso em até 10 palavras), "
    "texto_sugerido (texto completo do chamado em primeira pessoa, 3-5 frases, direto e "
    "objetivo - inclua TODOS os dados necessários já como placeholders em "
    "MAIUSCULAS_COM_UNDERSCORE, ex: NOME_PORTAL, NOME_USUARIO, ID_OBJETO_BDGC, NOME_FILA; "
    "NÃO use frases como 'posso informar se necessário' ou 'caso necessário'; o texto deve "
    "conter tudo que o atendente precisa para resolver sem solicitar informações adicionais), "
    "grupo (nome exato do grupo do item escolhido), "
    "categoria (nome exato de um dos chamados/request types acima), justificativa (1-2 frases), "
    "confianca (alta, media ou baixa), informacoes_faltantes (lista de campos ausentes)."
)


def _enriquecer_resultado(resultado: dict, portfolio: list) -> dict:
    """Anexa informações obrigatórias, SLA e complexidade da categoria escolhida."""
    nome_cat = resultado.get("categoria", "")
    for cat in portfolio:
        if cat.get("nome", "").strip().lower() == nome_cat.strip().lower():
            resultado["grupo"] = resultado.get("grupo") or cat.get("grupo", "")
            resultado["informacoes_necessarias"] = (
                cat.get("informacoes_obrigatorias") or cat.get("informacoes_necessarias", [])
            )
            resultado["sla_sugerido"] = cat.get("sla_sugerido", "")
            resultado["complexidade"] = cat.get("complexidade", "")
            break
    return resultado


# ---------------------------------------------------------------------------
# API: simulação com Ollama local ou Azure OpenAI
# ---------------------------------------------------------------------------

_DASHBOARD_LLM_PROVIDERS = {"ollama", "azure"}


def _dashboard_llm_status(provider_override: str | None = None) -> dict:
    """Descreve o motor configurado sem realizar chamada de rede.

    Na seleção automática, o Ollama tem precedência para manter o texto do
    chamado dentro da infraestrutura. O Azure é usado como fallback quando
    estiver configurado.
    """
    requested = (
        provider_override
        or os.getenv("DASHBOARD_LLM_PROVIDER", "")
        or ""
    ).strip().lower()
    if requested and requested not in _DASHBOARD_LLM_PROVIDERS:
        return {
            "disponivel": False,
            "provedor": requested,
            "modelo": None,
            "local": False,
            "erro": "DASHBOARD_LLM_PROVIDER deve ser ollama ou azure.",
        }

    ollama_model = os.getenv("OLLAMA_MODEL", "").strip()
    azure_ready = bool(
        os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        and os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
    )
    provider = requested or ("ollama" if ollama_model else ("azure" if azure_ready else ""))
    if provider == "ollama":
        return {
            "disponivel": bool(ollama_model),
            "provedor": "ollama",
            "modelo": ollama_model or None,
            "local": True,
        }
    if provider == "azure":
        return {
            "disponivel": azure_ready,
            "provedor": "azure",
            "modelo": os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1"),
            "local": False,
        }
    return {
        "disponivel": False,
        "provedor": None,
        "modelo": None,
        "local": False,
    }


def _simular_com_llm(provider_override: str | None = None):
    status = _dashboard_llm_status(provider_override)
    if not status["disponivel"]:
        detalhe = status.get("erro") or (
            "Motor de simulação não configurado. Defina OLLAMA_MODEL para uso "
            "local ou as credenciais AZURE_OPENAI_* no .env."
        )
        return jsonify({"erro": detalhe}), 503

    data = request.get_json(silent=True) or {}
    descricao = data.get("descricao", "").strip()
    if not descricao:
        return jsonify({"erro": "Informe a descrição do chamado."}), 400

    cats_texto, portfolio, infra_ctx = _categorias_para_prompt()
    infra_bloco = ("Contexto do portal:\n" + infra_ctx) if infra_ctx else ""
    system_msg = (
        f"Você é um analista de triagem de chamados do portal {PROJ_PORTAL_NOME}. "
        "Classifique chamados nos chamados/request types do portfólio, preservando o grupo lógico.\n\n"
        f"{infra_bloco}\n\nPORTFÓLIO DISPONÍVEL (grupo > chamado):\n{cats_texto}\n\n{_INSTRUCAO_SIM}"
    )
    user_msg = f"Descrição do chamado:\n{descricao}"

    try:
        client = LLMClient(provider_override=status["provedor"])
        timeout = int(os.getenv("DASHBOARD_LLM_TIMEOUT", str(client.timeout)))
        resultado = client.chat_json(
            system_msg,
            user_msg,
            temperature=0.1,
            max_tokens=700,
            max_retries=2,
            timeout=timeout,
        )
        resultado["motor"] = {
            "provedor": client.provider,
            "modelo": client.model_label.split(":", 1)[-1],
            "local": client.provider == "ollama",
        }
        return jsonify(_norm(_enriquecer_resultado(resultado, portfolio)))
    except (LLMError, OSError, TypeError, ValueError) as exc:
        return jsonify({"erro": f"Erro no motor de simulação: {str(exc)}"}), 502


@app.route("/api/llm-status")
def llm_status():
    return jsonify(_dashboard_llm_status())


@app.route("/api/simular", methods=["POST"])
def simular():
    return _simular_com_llm()


# Endpoints legados mantidos para clientes locais antigos; neles o provedor
# continua explicitamente fixado em Azure.
@app.route("/api/openai-status")
def openai_status():
    return jsonify(_dashboard_llm_status("azure"))


@app.route("/api/simular-openai", methods=["POST"])
def simular_openai():
    return _simular_com_llm("azure")


# ---------------------------------------------------------------------------
# API: resumo executivo e comparação de portfólio
# ---------------------------------------------------------------------------

@app.route("/api/analise-resumo")
def get_analise_resumo():
    if not P_RESULT.exists() and _dados_curadoria() is None:
        return jsonify({"erro": "Resultados do pipeline não encontrados."}), 404

    d = _load_json(P_RESULT) if P_RESULT.exists() else {}
    rec = d.get("recomendacao", {})
    meta = d.get("metadata", {})
    categorias_atuais = d.get("categorias_atuais", {})
    metricas = calcular_metricas_interacoes()

    final_data = _dados_curadoria()
    usando_curadoria = final_data is not None
    # Curadoria executiva (opcional) sobrepõe a análise bruta do Stage 5 no painel.
    rec_diag = {**rec, **_diag_overlay()}
    if usando_curadoria:
        portfolio_final = _portfolio_final_curado(final_data)
        # substitui_categorias_atuais vive no feedback curado (fonte canonica da
        # decisao); o 07_portfolio_final materializado nao o carrega. Enriquece aqui
        # para o mapa de migracao, sem tocar no artefato materializado.
        if P_FEEDBACK.exists():
            _fb_sub = {
                it.get("id"): it
                for it in _load_json(P_FEEDBACK).get("portfolio_final", [])
                if it.get("id")
            }
            for _it in portfolio_final:
                _src = _fb_sub.get(_it.get("id"))
                if _src is not None:
                    _it["substitui_categorias_atuais"] = _src.get("substitui_categorias_atuais", [])
                    if _src.get("justificativa_consolidacao"):
                        _it["justificativa_consolidacao"] = _src["justificativa_consolidacao"]
        total_tickets = (
            final_data.get("metadata", {}).get("total_classificados")
            or meta.get("total_tickets", 0)
        )
        diagnostico = _diagnostico_executivo(meta, portfolio_final, total_tickets, True, metricas, categorias_atuais, rec_diag)
        # Consolidacao = mapa de migracao CURADO (particao: cada tipo atual entra em
        # um unico tipo novo), vindo de substitui_categorias_atuais. NAO usa a
        # classificacao por chamado do Stage 7 (que repetiria o mesmo tipo atual em
        # varios tipos novos). A distribuicao por conteudo do Stage 7 fica no Painel
        # Executivo e nos volumes do portfolio.
        consolidacao = _consolidacao_catalogo(
            rec,
            categorias_atuais,
            portfolio_override=portfolio_final,
            origens_por_categoria=None,
        )
        problemas = []
        mapeamento = []
        acoes = []
    else:
        # Volumes REAIS (Stage 6) nos cards/grupos/KPI, no lugar dos estimados.
        _aplicar_volumes_reais(rec)
        portfolio_llm = sorted(
            rec.get("portfolio_otimizado", []),
            key=lambda x: x.get("volume_estimado", 0), reverse=True
        )
        portfolio_final = _mesclar_portfolio(portfolio_llm)
        total_tickets = meta.get("total_tickets", 0)
        diagnostico = _diagnostico_executivo(meta, portfolio_final, total_tickets, False, metricas, categorias_atuais, rec_diag)
        consolidacao = _consolidacao_catalogo(rec, categorias_atuais)
        problemas = rec.get("problemas_encontrados", [])
        mapeamento = rec.get("mapeamento_atual_vs_natural", [])
        acoes = rec.get("acoes_prioritarias", [])

    return jsonify(_norm({
        "total_tickets": total_tickets,
        "categorias_atuais": meta.get("n_categorias_atuais", 0) or len(categorias_atuais),
        "grupos_naturais": meta.get("n_grupos_naturais", 0),
        "grupos_logicos_total": len(_resumo_grupos_portfolio(portfolio_final)),
        "grupos_logicos": _resumo_grupos_portfolio(portfolio_final),
        "categorias_recomendadas": len(portfolio_final),
        "usando_curadoria": usando_curadoria,
        "fonte_portfolio": "stage7" if usando_curadoria else "stage5",
        "diagnostico": diagnostico,
        "problemas": problemas,
        "portfolio_otimizado": portfolio_final,
        "consolidacao": consolidacao,
        "mapeamento": mapeamento,
        "acoes": acoes,
        "categorias_atuais_volume": categorias_atuais,
        "grupos_atuais": _grupos_atuais_com_volume(categorias_atuais),
        "metricas_interacoes": metricas,
    }))


@app.route("/api/analise-clusters")
def get_analise_clusters():
    if not P_LABELS.exists():
        return jsonify({"erro": "04_labels.json não encontrado."}), 404
    data = _load_json(P_LABELS)
    clusters = sorted(data.get("clusters", []), key=lambda x: x.get("total_tickets", 0), reverse=True)
    return jsonify(_norm({
        "total_clusters": data.get("optimal_k", 0),
        "total_tickets": data.get("total_tickets", 0),
        "clusters": clusters,
    }))


@app.route("/api/interacoes-categorias")
def get_interacoes_categorias():
    return jsonify(tabela_interacoes_por_categoria())


@app.route("/health")
def health():
    return jsonify({
        "status": "ok",
        "projeto": PROJ_NOME,
        "portal_nome": PROJ_PORTAL_NOME,
        "timestamp": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    _porta = int(os.getenv("PORT", "5000"))
    _host = os.getenv("DASHBOARD_HOST", "127.0.0.1")
    print("")
    print(f"  Triagem Inteligente de Chamados - {PROJ_PORTAL_NOME}")
    print(f"  Projeto: {PROJ_DIR}")
    print(f"  http://{_host}:{_porta}")
    print("")
    app.run(debug=False, host=_host, port=_porta)
