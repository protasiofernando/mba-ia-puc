#!/usr/bin/env python3
"""
Triagem Inteligente de Chamados — DTI FGV
Dashboard Flask com 6 abas: Dashboard, Categorias, Simulação, Análise IA,
Histórico e Grupos Naturais.
"""

import json
import os
import re
import sqlite3
from dotenv import load_dotenv
load_dotenv()
from datetime import datetime
from pathlib import Path

import requests as _requests
from flask import Flask, jsonify, render_template, request

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False

BASE_DIR      = Path(__file__).parent
DB_PATH       = BASE_DIR / "knowledge_base.db"
PIPELINE_DATA = BASE_DIR / "pipeline_data"
P_RESULT      = PIPELINE_DATA / "05_portfolio_recommendation.json"
P_FINAL       = PIPELINE_DATA / "07_portfolio_final.json"
P_FINAL_CLASS = PIPELINE_DATA / "07_classificados_final.json"
P_LABELS      = PIPELINE_DATA / "04_labels.json"
CONFIG_PATH   = BASE_DIR / "config_portfolio.json"

# Ollama para simulação LLM local — configurável via variável de ambiente
OLLAMA_URL   = os.getenv("OLLAMA_URL",   "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma4:26b-q8")

# Azure OpenAI — configurar via .env ou variáveis de ambiente
AZURE_OPENAI_API_KEY    = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_ENDPOINT   = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")


def _load_json(path: Path):
    """Carrega JSON aceitando UTF-8 com ou sem BOM."""
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _carregar_categorias_obrigatorias() -> list:
    """Lê as categorias obrigatórias do config_portfolio.json."""
    if not CONFIG_PATH.exists():
        return []
    cfg = _load_json(CONFIG_PATH)
    return cfg.get("categorias_obrigatorias", [])


def _mesclar_portfolio(portfolio_llm: list) -> list:
    """
    Mescla o portfólio gerado pelo LLM com as categorias obrigatórias.
    - Categorias obrigatórias são adicionadas se ainda não existirem.
    - "Não encontrou o que procurava?" sempre vai para o final.
    """
    obrigatorias = _carregar_categorias_obrigatorias()
    nomes_llm = {c.get("nome", "").strip().lower() for c in portfolio_llm}

    catch_all = None
    extras = []
    for cat in obrigatorias:
        nome = cat.get("nome", "").strip()
        if "não encontrou" in nome.lower():
            # Só adiciona se o LLM não incluiu uma categoria equivalente
            if not any("não encontrou" in n for n in nomes_llm):
                catch_all = cat
        elif nome.lower() not in nomes_llm:
            extras.append(cat)

    resultado = list(portfolio_llm) + extras
    if catch_all:
        resultado.append(catch_all)
    return resultado


def _ordenar_portfolio(portfolio: list) -> list:
    """Ordena categorias por volume, mantendo catch-all/encaminhamentos ao final."""
    def _ordem(c):
        nome = c.get("nome", "").lower()
        return (bool(c.get("encaminhamento")), "não encontrou" in nome, -c.get("volume_estimado", 0))

    portfolio.sort(key=_ordem)
    return portfolio


def _portfolio_final_curado(data: dict) -> list:
    """Normaliza o portfolio definido pela curadoria humana (Stage 7) para o formato da UI."""
    port = [dict(c) for c in data.get("portfolio_final", []) if isinstance(c, dict)]
    for c in port:
        c["volume_estimado"] = c.get("volume", c.get("volume_estimado", 0))
        c["percentual_volume"] = c.get("percentual_portfolio", c.get("percentual_volume"))
    return _ordenar_portfolio(port)


def _diagnostico_curadoria_stage7(data: dict, portfolio: list) -> str:
    """Diagnostico deterministico baseado no portfolio final curado, sem depender do Stage 5."""
    meta = data.get("metadata", {}) if isinstance(data, dict) else {}
    total = meta.get("total_classificados") or sum(c.get("volume_estimado", 0) for c in portfolio)
    categorias = [c for c in portfolio if not c.get("encaminhamento")]
    principais = [c for c in categorias if c.get("volume_estimado", 0) > 0][:3]
    diretrizes = data.get("diretrizes", []) if isinstance(data, dict) else []
    fora = data.get("fora_do_catalogo", []) if isinstance(data, dict) else []

    partes = [
        f"A analise considera a curadoria final da area: {len(categorias)} categorias definidas para {total} chamados reclassificados."
    ]

    if principais:
        total_top = sum(c.get("volume_estimado", 0) for c in principais)
        pct_top = round(total_top * 100 / total, 1) if total else 0
        nomes = ", ".join(f"{c.get('nome')} ({c.get('volume_estimado', 0)})" for c in principais)
        partes.append(
            f"A demanda se concentra principalmente em {nomes}, que somam {pct_top}% do historico classificado."
        )

    catch_all = next((c for c in portfolio if "não encontrou" in c.get("nome", "").lower()), None)
    if catch_all and catch_all.get("volume_estimado", 0):
        partes.append(
            f"A categoria '{catch_all.get('nome')}' permanece como rota de excecao para {catch_all.get('volume_estimado')} chamados que nao se encaixam diretamente no catalogo final."
        )

    if diretrizes:
        partes.append(
            f"As {len(diretrizes)} diretrizes de curadoria foram usadas para orientar a separacao entre ambientes, software/licencas, nuvem, HPC, PGD e casos fora do catalogo."
        )
    if fora:
        partes.append(
            f"Os temas marcados como fora do catalogo foram preservados como encaminhamento, evitando criar categorias que a area nao decidiu manter."
        )

    return " ".join(partes)

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _db_tem_chamados() -> bool:
    """Retorna True quando knowledge_base.db existe e possui a tabela chamados."""
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


def calcular_metricas_interacoes() -> dict | None:
    """
    % de chamados com descrição suficiente vs insuficiente.
    Usa descricao_insuficiente (LLM) quando disponível; fallback para qtd_interacoes.
    """
    if not _db_tem_chamados():
        return None
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*)                                                           AS total,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'nao'                   THEN 1
                    WHEN descricao_insuficiente IS NULL
                         AND qtd_interacoes <= 1                          THEN 1
                END)                                                               AS diretos,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'sim'                   THEN 1
                    WHEN descricao_insuficiente IS NULL
                         AND qtd_interacoes > 1                           THEN 1
                END)                                                               AS insuficientes,
                COUNT(CASE WHEN descricao_insuficiente IN ('sim','nao') THEN 1 END) AS enriquecidos
            FROM chamados
            WHERE tipo_solicitacao IS NOT NULL
        """)
        row = cur.fetchone()
        conn.close()
        if not row or row["total"] == 0:
            return None
        return {
            "pct_diretos":      round(row["diretos"]       / row["total"] * 100, 1),
            "pct_multiplas":    round(row["insuficientes"] / row["total"] * 100, 1),
            "fonte":            "llm" if row["enriquecidos"] > 0 else "qtd_interacoes",
            "pct_enriquecidos": round(row["enriquecidos"]  / row["total"] * 100, 1),
        }
    except Exception:
        return None


def tabela_interacoes_por_categoria() -> list:
    """
    Estatísticas por categoria: volume, descrição suficiente/insuficiente, tempos médios.
    Usa descricao_insuficiente (LLM) quando disponível; fallback para qtd_interacoes.
    """
    if not _db_tem_chamados():
        return []
    try:
        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            SELECT
                tipo_solicitacao                                                             AS categoria,
                COUNT(*)                                                                     AS total,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'nao'                            THEN 1
                    WHEN descricao_insuficiente IS NULL AND qtd_interacoes <= 1    THEN 1
                END)                                                                         AS diretos,
                COUNT(CASE
                    WHEN descricao_insuficiente = 'sim'                            THEN 1
                    WHEN descricao_insuficiente IS NULL AND qtd_interacoes > 1     THEN 1
                END)                                                                         AS multiplos,
                ROUND(AVG(CASE
                    WHEN (descricao_insuficiente = 'nao'
                          OR (descricao_insuficiente IS NULL AND qtd_interacoes <= 1))
                         AND tempo_total_horas > 0
                    THEN tempo_total_horas END), 1)                                          AS t_medio_direto,
                ROUND(AVG(CASE
                    WHEN (descricao_insuficiente = 'sim'
                          OR (descricao_insuficiente IS NULL AND qtd_interacoes > 1))
                         AND tempo_total_horas > 0
                    THEN tempo_total_horas END), 1)                                          AS t_medio_multiplo
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
# Normalização de linguagem
# ---------------------------------------------------------------------------

def _normalizar_texto(texto: str) -> str:
    """Substitui termos coloquiais por linguagem formal e corrige nomes amplos."""
    if not texto:
        return texto
    subs = [
        (r"\bvai[\s\-]e[\s\-]vem\b",    "múltiplas interações"),
        (r"\bVai[\s\-]e[\s\-]Vem\b",    "Múltiplas Interações"),
        (r"\bvaievem\b",                 "múltiplas interações"),
        (r"\bMatlab/Qualtrics\b",        "softwares acadêmicos específicos"),
        (r"\bMatlab\b",                  "softwares acadêmicos"),
        (r"\bQualtrics\b",               "softwares acadêmicos"),
        (r"\bAWS/Azure\b",               "AWS, Azure e Google Cloud Platform"),
        (r"\bAWS e Azure\b",             "AWS, Azure e Google Cloud Platform"),
        (r"\bCloud AWS/Azure\b",         "Cloud (AWS, Azure e Google Cloud Platform)"),
    ]
    for pattern, replacement in subs:
        texto = re.sub(pattern, replacement, texto, flags=re.IGNORECASE)
    return texto


def _norm(obj):
    """Aplica normalização recursivamente em strings de um objeto."""
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
    return render_template("index.html")


# ---------------------------------------------------------------------------
# Helpers de filtro
# ---------------------------------------------------------------------------

def _where_mes(mes: str) -> tuple:
    """Retorna cláusula WHERE e parâmetros para filtrar por mês (YYYY-MM)."""
    if mes:
        return "WHERE strftime('%Y-%m', data_criacao) = ?", (mes,)
    return "", ()


def _and_mes(mes: str) -> tuple:
    """Versão AND para quando já existe um WHERE."""
    if mes:
        return "AND strftime('%Y-%m', data_criacao) = ?", (mes,)
    return "", ()


# ---------------------------------------------------------------------------
# API: Meses disponíveis (para o filtro)
# ---------------------------------------------------------------------------

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
# API: Dashboard
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
            "total_chamados":          0,
            "total_categorias":        0,
            "taxa_resolucao":          "N/A",
            "backlog":                 0,
            "finalizados":             0,
            "taxa_reabertura":         "0.0%",
            "distribuicao_categorias": [],
            "distribuicao_situacoes":  [],
            "tempo_por_categoria":     [],
            "tendencia_mensal":        [],
            "top_analistas":           [],
            "top_solicitantes":        [],
            "por_departamento":        [],
            "ia_resumo":               ia_resumo,
        })

    conn = get_db()
    cur = conn.cursor()

    # KPIs principais — calculados ao vivo, sem depender da tabela categorias
    cur.execute(f"SELECT COUNT(*) as c FROM chamados {w}", wp)
    total = cur.fetchone()["c"]

    cur.execute(f"SELECT COUNT(DISTINCT tipo_solicitacao) as c FROM chamados {w}", wp)
    cats = cur.fetchone()["c"]

    # Taxa de resolução real: tem data de resolução E status não indica cancelamento
    cur.execute(f"SELECT ROUND(SUM(resolvido)*100.0/COUNT(*),1) as taxa FROM chamados {w}", wp)
    taxa = cur.fetchone()["taxa"]

    # Finalizados (resolvidos + cancelados com data de fechamento)
    cur.execute(f"SELECT SUM(finalizado) as c FROM chamados {w}", wp)
    finalizados = cur.fetchone()["c"] or 0

    # Backlog: chamados ainda abertos (sem data de resolução)
    cur.execute(f"""
        SELECT COUNT(*) as c FROM chamados
        WHERE finalizado = 0 {a}
    """, ap)
    backlog = cur.fetchone()["c"]

    # Distribuição por categoria (top 8)
    cur.execute(f"""
        SELECT tipo_solicitacao, COUNT(*) as total
        FROM chamados
        WHERE tipo_solicitacao IS NOT NULL {a}
        GROUP BY tipo_solicitacao ORDER BY total DESC LIMIT 8
    """, ap)
    dist = [{"nome": r["tipo_solicitacao"], "total": r["total"]} for r in cur.fetchall()]

    # Situações — dinâmico com distinção resolvido/cancelado/aberto
    cur.execute(f"""
        SELECT situacao,
               COUNT(*) as total,
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

    # Tempo médio por categoria — calculado ao vivo
    cur.execute(f"""
        SELECT tipo_solicitacao as nome,
               ROUND(AVG(tempo_total_horas), 1) as tempo
        FROM chamados
        WHERE tipo_solicitacao IS NOT NULL AND tempo_total_horas > 0 {a}
        GROUP BY tipo_solicitacao ORDER BY tempo DESC LIMIT 8
    """, ap)
    tempos = [{"nome": r["nome"][:40], "tempo": r["tempo"]} for r in cur.fetchall()]

    # Tendência mensal
    cur.execute(f"""
        SELECT strftime('%Y-%m', data_criacao) as mes, COUNT(*) as total
        FROM chamados
        WHERE data_criacao IS NOT NULL {a}
        GROUP BY mes ORDER BY mes
    """, ap)
    tendencia = [{"mes": r["mes"], "total": r["total"]} for r in cur.fetchall()]

    # Top 10 analistas
    cur.execute(f"""
        SELECT responsavel, COUNT(*) as total
        FROM chamados
        WHERE responsavel IS NOT NULL AND responsavel != '' {a}
        GROUP BY responsavel ORDER BY total DESC LIMIT 10
    """, ap)
    analistas = [{"nome": r["responsavel"], "total": r["total"]} for r in cur.fetchall()]

    # Top 10 solicitantes
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

    # Volume por departamento
    cur.execute(f"""
        SELECT dpto_solicitante, COUNT(*) as total
        FROM chamados
        WHERE dpto_solicitante IS NOT NULL AND dpto_solicitante != '' {a}
        GROUP BY dpto_solicitante ORDER BY total DESC LIMIT 10
    """, ap)
    departamentos = [{"nome": r["dpto_solicitante"], "total": r["total"]} for r in cur.fetchall()]

    # Taxa de reabertura
    cur.execute(f"SELECT COUNT(*) as c FROM chamados {w or 'WHERE'} {'AND' if w else ''} chamado_reaberto = 1"
                .replace("WHERE AND", "WHERE"), wp)
    reabertos = cur.fetchone()["c"]
    taxa_reabertura = round(reabertos / total * 100, 1) if total else 0

    conn.close()

    ia_resumo = None
    portfolio = _portfolio_ativo()
    if portfolio:
        ia_resumo = {
            "categorias_recomendadas": len(portfolio),
        }

    return jsonify({
        "total_chamados":          total,
        "total_categorias":        cats,
        "taxa_resolucao":          f"{taxa:.1f}%" if taxa else "N/A",
        "backlog":                 backlog,
        "finalizados":             finalizados,
        "taxa_reabertura":         f"{taxa_reabertura:.1f}%",
        "distribuicao_categorias": dist,
        "distribuicao_situacoes":  situacoes,
        "tempo_por_categoria":     tempos,
        "tendencia_mensal":        tendencia,
        "top_analistas":           analistas,
        "top_solicitantes":        solicitantes,
        "por_departamento":        departamentos,
        "ia_resumo":               ia_resumo,
    })


# ---------------------------------------------------------------------------
# API: Categorias
# ---------------------------------------------------------------------------

@app.route("/api/categorias")
def get_categorias():
    """
    Categorias com métricas calculadas dos dados brutos (tabela chamados).

    Métricas:
    - total_chamados: contagem de tickets por categoria
    - tempo_medio_horas: média de (Resolvido - Criado) em horas por ticket
    - media_interacoes: média de comentários por ticket (qtd_interacoes)
    - taxa_resolucao: % de tickets com situacao = 'Resolvido'
    - total_perguntas: qtd de perguntas orientativas cadastradas para a categoria
    """
    if not _db_tem_chamados():
        return jsonify([])

    conn = get_db()
    cur = conn.cursor()

    # Métricas calculadas ao vivo dos dados brutos
    cur.execute("""
        SELECT
            tipo_solicitacao                                          AS nome,
            COUNT(*)                                                  AS total_chamados,
            ROUND(AVG(tempo_total_horas), 1)                         AS tempo_medio_horas,
            ROUND(AVG(qtd_interacoes), 2)                            AS media_interacoes,
            ROUND(SUM(resolvido) * 100.0 / COUNT(*), 1)              AS taxa_resolucao
        FROM chamados
        WHERE tipo_solicitacao IS NOT NULL
          AND tipo_solicitacao != ''
        GROUP BY tipo_solicitacao
        ORDER BY total_chamados DESC
    """)
    cats = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Mapeamento: de categoria antiga → categoria ativa (Stage 7 se houver; senão Stage 6/5)
    mapeamento = {}
    classificados_path = _classificados_ativo_path()
    if classificados_path.exists():
        from collections import Counter, defaultdict
        por_atual = defaultdict(Counter)
        for item in _load_json(classificados_path):
            cat_atual = item.get("tipo_atual") or "Não categorizado"
            nova_cat = item.get("categoria_nova") or "Não encontrou o que procurava?"
            por_atual[cat_atual][nova_cat] += 1

        fonte = "curadoria final (Stage 7)" if _fonte_classificacao_ativa() == "stage7" else "classificação automática (Stage 6)"
        for cat_atual, cont in por_atual.items():
            nome_novo, qtd = cont.most_common(1)[0]
            total_cat = sum(cont.values()) or 1
            mapeamento[cat_atual] = {
                "nova_categoria": nome_novo,
                "aderencia":      f"{round(qtd * 100 / total_cat, 1)}%",
                "observacao":     f"Mapeamento por maioria com base na {fonte}.",
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
                        "aderencia":      prioridade,
                        "observacao":     nova_cat.get("descricao", ""),
                    }

    for cat in cats:
        cat["mapeamento_novo"] = mapeamento.get(cat["nome"], {
            "nova_categoria": "A definir",
            "aderencia":      "indefinida",
            "observacao":     "Não mapeada explicitamente pelo modelo.",
        })

    return jsonify(cats)


@app.route("/api/mapeamento-detalhado")
def get_mapeamento_detalhado():
    """
    Retorna a distribuição detalhada: para cada categoria atual,
    quantos tickets iriam para cada nova categoria do portfólio otimizado.

    Prioridade de fonte:
    1. Stage 7 (07_classificados_final.json), se existir — curadoria final reclassificada
    2. Stage 6 (06_classificados.json) — classificação per-ticket automática via LLM
    3. Stage 3/4 (03_clusters + 04_labels) — mapeamento estatístico por cluster
    """
    from collections import defaultdict

    breakdown = defaultdict(int)
    fonte = "nenhum"

    classificados_path = _classificados_ativo_path()
    clusters_path      = PIPELINE_DATA / "03_clusters.json"

    if classificados_path.exists():
        # Fonte preferencial: classificação per-ticket ativa (Stage 7 se houver; senão Stage 6)
        classificados = _load_json(classificados_path)
        for item in classificados:
            cat_atual = item.get("tipo_atual") or "Não categorizado"
            nova_cat  = item.get("categoria_nova") or "Não encontrou o que procurava?"
            breakdown[(cat_atual, nova_cat)] += 1
        fonte = _fonte_classificacao_ativa()

    elif P_LABELS.exists() and P_RESULT.exists() and clusters_path.exists():
        # Fallback: mapeamento estatístico via clusters
        labels = _load_json(P_LABELS)
        result = _load_json(P_RESULT)
        portfolio = _mesclar_portfolio(result.get("recomendacao", {}).get("portfolio_otimizado", []))
        cluster_to_nova = {}
        for nova in portfolio:
            for grupo in nova.get("baseado_nos_grupos", []):
                if grupo:
                    cluster_to_nova[grupo] = nova["nome"]
        c_data = _load_json(clusters_path)
        id_to_nome = {c["cluster_id"]: c["nome"] for c in labels.get("clusters", [])}
        for ticket in c_data.get("tickets", []):
            cid      = ticket.get("cluster_id")
            cluster_nome = id_to_nome.get(cid, "")
            nova     = cluster_to_nova.get(cluster_nome, "Não encontrou o que procurava?")
            cat_atual = ticket.get("tipo_atual") or "Não categorizado"
            breakdown[(cat_atual, nova)] += 1
        fonte = "stage3"

    if not breakdown:
        return jsonify([])

    # Estatísticas por categoria atual do banco
    stats = {}
    if _db_tem_chamados():
        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT tipo_solicitacao AS nome,
                   COUNT(*) AS total_chamados,
                   ROUND(AVG(tempo_total_horas), 1) AS tempo_medio_horas,
                   ROUND(AVG(qtd_interacoes), 2) AS media_interacoes,
                   ROUND(SUM(resolvido) * 100.0 / COUNT(*), 1) AS taxa_resolucao
            FROM chamados
            WHERE tipo_solicitacao IS NOT NULL AND tipo_solicitacao != ''
            GROUP BY tipo_solicitacao
        """)
        stats = {r["nome"]: dict(r) for r in cur.fetchall()}
        conn.close()

    rows = []
    for (cat_atual, nova_cat), chamados in sorted(breakdown.items(), key=lambda x: -x[1]):
        s = stats.get(cat_atual, {})
        rows.append({
            "categoria_atual":   cat_atual,
            "nova_categoria":    nova_cat,
            "chamados":          chamados,
            "total_categoria":   s.get("total_chamados", 0),
            "tempo_medio_horas": s.get("tempo_medio_horas"),
            "media_interacoes":  s.get("media_interacoes"),
            "taxa_resolucao":    s.get("taxa_resolucao"),
            "fonte":             fonte,
        })

    return jsonify(rows)


@app.route("/api/historico")
def get_historico():
    """
    Retorna tickets paginados com a categoria atribuída pelo pipeline LLM.
    Fonte preferencial: Stage 7 curado, depois Stage 6 automático, depois Stage 3.
    Se nenhum artefato de pipeline estiver disponível localmente, categoria_llm fica vazia.
    """
    page   = int(request.args.get("page", 1))
    limit  = int(request.args.get("limit", 50))
    busca  = request.args.get("q", "").strip().lower()
    offset = (page - 1) * limit

    if not _db_tem_chamados():
        return jsonify({
            "total":              0,
            "page":               page,
            "limit":              limit,
            "tickets":            [],
            "tem_dados_pipeline": False,
            "fonte":              "nenhum",
        })

    # Constrói mapa chave → categoria ativa (Stage 7/6) ou grupo natural (Stage 3)
    cluster_map: dict = {}
    classificados_path = _classificados_ativo_path()
    clusters_path      = PIPELINE_DATA / "03_clusters.json"

    if classificados_path.exists():
        # Preferência: classificação direta no portfólio ativo (Stage 7 se houver; senão Stage 6)
        for item in _load_json(classificados_path):
            chave = item.get("chave")
            cat   = item.get("categoria_nova")
            conf  = item.get("confianca")
            if chave and cat:
                cluster_map[chave] = {"categoria": cat, "confianca": conf}
    elif clusters_path.exists() and P_LABELS.exists():
        # Fallback: Stage 3 — grupos naturais por cluster
        c_data = _load_json(clusters_path)
        labels = _load_json(P_LABELS)
        id_to_nome = {c["cluster_id"]: c["nome"] for c in labels.get("clusters", [])}
        for ticket in c_data.get("tickets", []):
            chave = ticket.get("chave")
            cid   = ticket.get("cluster_id")
            if chave and cid is not None:
                cluster_map[chave] = {"categoria": id_to_nome.get(cid, "—"), "confianca": None}

    conn = get_db()
    cur  = conn.cursor()

    where  = "WHERE 1=1"
    params: list = []
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
        t["confianca_llm"] = info["confianca"] if info else None

    return jsonify({
        "total":              total,
        "page":               page,
        "limit":              limit,
        "tickets":            tickets,
        "tem_dados_pipeline": bool(cluster_map),
        "fonte":              _fonte_classificacao_ativa() if classificados_path.exists() else ("stage3" if clusters_path.exists() else "nenhum"),
    })


@app.route("/api/portfolio-novo")
def get_portfolio_novo():
    """Portfólio ativo para a tela de categorias.

    Se o Stage 7 existir, retorna a curadoria final da área. Caso contrário,
    retorna o portfólio recomendado automaticamente pelo Stage 5/6.
    """
    if P_FINAL.exists():
        return jsonify(_norm(_portfolio_final_curado(_load_json(P_FINAL))))

    portfolio_llm = []
    if P_RESULT.exists():
        data = _load_json(P_RESULT)
        portfolio_llm = data.get("recomendacao", {}).get("portfolio_otimizado", [])

    portfolio = _mesclar_portfolio(portfolio_llm)

    # Volume real por categoria a partir da classificação do Stage 6
    classificados_path = _classificados_ativo_path()
    if classificados_path.exists():
        from collections import Counter
        cont = Counter((item.get("categoria_nova") or "").strip()
                       for item in _load_json(classificados_path))
        enc_nomes = {c.get("nome", "").strip() for c in portfolio if c.get("encaminhamento")}
        base = sum(n for nome, n in cont.items() if nome not in enc_nomes) or 1
        for cat in portfolio:
            real = cont.get(cat.get("nome", "").strip(), 0)
            cat["volume_estimado"]   = real
            cat["percentual_volume"] = None if cat.get("encaminhamento") else round(real / base * 100, 1)

    # Ordena: categorias do portfólio por volume desc, catch-all e encaminhamentos no fim
    def _ordem(c):
        nome = c.get("nome", "").lower()
        return (bool(c.get("encaminhamento")), "não encontrou" in nome, -c.get("volume_estimado", 0))
    portfolio.sort(key=_ordem)

    return jsonify(_norm(portfolio))


@app.route("/api/portfolio-final")
def get_portfolio_final():
    """Portfólio DEFINIDO pela área (curadoria humana, Stage 7).

    Vazio se o Stage 7 ainda não rodou — o bloco "Portfólio Definido" fica oculto.
    Os volumes já vêm calculados pelo Stage 7 (07_portfolio_final.json).
    """
    if not P_FINAL.exists():
        return jsonify([])
    data = _load_json(P_FINAL)
    return jsonify(_norm(_portfolio_final_curado(data)))


def _portfolio_ativo() -> list:
    """Portfólio para a simulação: o DEFINIDO (Stage 7) se existir, senão o recomendado (Stage 5)."""
    if P_FINAL.exists():
        return _portfolio_final_curado(_load_json(P_FINAL))
    if P_RESULT.exists():
        d = _load_json(P_RESULT)
        return _mesclar_portfolio(d.get("recomendacao", {}).get("portfolio_otimizado", []))
    return []


def _classificados_ativo_path():
    """Classificação para o dashboard: a DEFINIDA (Stage 7, 07_classificados_final.json)
    se existir, senão a recomendada (Stage 6, 06_classificados.json)."""
    return P_FINAL_CLASS if P_FINAL.exists() and P_FINAL_CLASS.exists() else (PIPELINE_DATA / "06_classificados.json")


def _fonte_classificacao_ativa() -> str:
    """Nome da fonte da classificação ativa exibida no dashboard."""
    return "stage7" if P_FINAL.exists() and P_FINAL_CLASS.exists() else "stage6"


# ---------------------------------------------------------------------------
# API: Simulação LLM
# ---------------------------------------------------------------------------

@app.route("/api/simular-llm", methods=["POST"])
def simular_llm():
    """Classifica um chamado usando o LLM (Ollama) com o portfólio otimizado como contexto."""
    data      = request.json or {}
    descricao = data.get("descricao", "").strip()

    if not descricao:
        return jsonify({"erro": "Informe a descrição do chamado."}), 400

    # Verifica se Ollama está disponível
    try:
        _requests.get(f"{OLLAMA_URL}/api/version", timeout=3)
    except Exception:
        return jsonify({"erro": "Ollama indisponível. Verifique se está rodando no nó GPU."}), 503

    # Carrega categorias do portfólio ativo (DEFINIDO no Stage 7 se existir, senão o recomendado)
    categorias = []
    portfolio = _portfolio_ativo()
    for cat in portfolio:
        categorias.append({
            "nome":         cat.get("nome", ""),
            "descricao":    cat.get("descricao", ""),
            "quando_usar":  cat.get("quando_usar", ""),
        })

    cats_texto = "\n".join(
        f"- {c['nome']}: {c['descricao']}"
        for c in categorias if c["nome"]
    )

    # Carrega contexto de infraestrutura do config
    infra_ctx = ""
    if CONFIG_PATH.exists():
        cfg = _load_json(CONFIG_PATH)
        infra_ctx = cfg.get("infra_context", {}).get("texto_contexto", "")

    infra_bloco_local = ("Contexto da infraestrutura DTI:\n" + infra_ctx + "\n") if infra_ctx else ""

    prompt = f"""Você é um analista de triagem de chamados da DTI FGV. Classifique o chamado abaixo em uma das categorias disponíveis.

{infra_bloco_local}
CATEGORIAS DISPONÍVEIS:
{cats_texto}

CHAMADO:
{descricao}

Responda SOMENTE com JSON. Os campos são: titulo_sugerido (título conciso em até 10 palavras), texto_sugerido (texto completo do chamado em primeira pessoa, 3-5 frases, direto e objetivo — inclua TODOS os dados necessários já como placeholders em MAIUSCULAS_COM_UNDERSCORE, ex: VERSAO_PYTHON, NOME_VENV, NOME_BIBLIOTECA, VERSAO_BIBLIOTECA, NOME_SERVIDOR; se o chamado envolver linguagem de programação (Python, R, Julia, etc.), biblioteca ou framework, o texto DEVE especificar a versão — use placeholder VERSAO_X se o usuário pode escolher, ou escreva "versão mais recente disponível" se não há preferência indicada; NÃO use frases como "posso informar se necessário", "aguardo orientações" ou "caso necessário"; o texto deve conter tudo que o atendente precisa para resolver o chamado sem solicitar informações adicionais), categoria (nome exato de uma das categorias acima), justificativa (1-2 frases), confianca (alta, media ou baixa), informacoes_faltantes (lista de campos ausentes).

JSON:
{{"""

    try:
        # /api/chat + think:false: o endpoint de chat aplica o template do modelo
        # e think:false desliga o modo de raciocínio (modelos como o gemma4:26b-q8
        # senão devolvem content vazio). Ver docs/NOTAS_TECNICAS.md.
        resp = _requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={"model": OLLAMA_MODEL,
                  "messages": [{"role": "user", "content": prompt}],
                  "stream": False, "think": False, "format": "json",
                  "options": {"temperature": 0.1, "num_predict": -1, "num_ctx": 16384}},
            timeout=180,
        )
        resp.raise_for_status()
        texto = resp.json().get("message", {}).get("content", "")

        # Extrai JSON da resposta — múltiplas estratégias de extração
        texto_limpo = re.sub(r"```json\s*", "", texto)
        texto_limpo = re.sub(r"```\s*", "", texto_limpo)

        resultado = None
        # Tenta encontrar o bloco JSON do primeiro { ao último }
        inicio = texto_limpo.find("{")
        fim = texto_limpo.rfind("}")
        if inicio != -1 and fim != -1 and fim > inicio:
            try:
                resultado = json.loads(texto_limpo[inicio:fim+1])
            except json.JSONDecodeError:
                pass

        # Fallback: regex greedy
        if resultado is None:
            match = re.search(r"\{.*\}", texto_limpo, re.DOTALL)
            if match:
                try:
                    resultado = json.loads(match.group())
                except json.JSONDecodeError:
                    pass

        if resultado is None:
            return jsonify({"erro": "LLM não retornou JSON válido.", "resposta_raw": texto[:500]}), 500

        # Enriquece com campos obrigatórios da categoria escolhida
        nome_cat = resultado.get("categoria", "")
        for cat in portfolio:
            if cat.get("nome", "").strip().lower() == nome_cat.strip().lower():
                resultado["informacoes_necessarias"] = (
                    cat.get("informacoes_obrigatorias") or
                    cat.get("informacoes_necessarias", [])
                )
                resultado["sla_sugerido"] = cat.get("sla_sugerido", "")
                resultado["complexidade"] = cat.get("complexidade", "")
                break

        return jsonify(_norm(resultado))

    except Exception as e:
        return jsonify({"erro": f"Erro ao chamar o LLM: {str(e)}"}), 500


@app.route("/api/ollama-status")
def ollama_status():
    """Verifica se o Ollama está disponível para simulação LLM local."""
    try:
        _requests.get(f"{OLLAMA_URL}/api/version", timeout=3)
        return jsonify({"disponivel": True, "url": OLLAMA_URL, "modelo": OLLAMA_MODEL})
    except Exception:
        return jsonify({"disponivel": False, "url": OLLAMA_URL})


@app.route("/api/openai-status")
def openai_status():
    """Verifica se a chave Azure OpenAI está configurada."""
    configurado = bool(AZURE_OPENAI_API_KEY and AZURE_OPENAI_ENDPOINT)
    return jsonify({
        "disponivel": configurado,
        "modelo":     AZURE_OPENAI_DEPLOYMENT if configurado else None,
    })


@app.route("/api/simular-openai", methods=["POST"])
def simular_openai():
    """Classifica um chamado usando a Azure OpenAI com o portfólio otimizado como contexto."""
    if not AZURE_OPENAI_API_KEY or not AZURE_OPENAI_ENDPOINT:
        return jsonify({"erro": "Azure OpenAI não configurada. Verifique o arquivo .env e reinicie o servidor."}), 503

    data      = request.json or {}
    descricao = data.get("descricao", "").strip()

    if not descricao:
        return jsonify({"erro": "Informe a descrição do chamado."}), 400

    # Carrega categorias do portfólio ativo (DEFINIDO no Stage 7 se existir, senão o recomendado)
    portfolio  = _portfolio_ativo()
    categorias = []
    for cat in portfolio:
        categorias.append({
            "nome":        cat.get("nome", ""),
            "descricao":   cat.get("descricao", ""),
            "quando_usar": cat.get("quando_usar", ""),
        })

    cats_texto = "\n".join(
        f"- {c['nome']}: {c['descricao']} | Usar quando: {c['quando_usar']}"
        for c in categorias if c["nome"]
    )

    infra_ctx = ""
    if CONFIG_PATH.exists():
        cfg = _load_json(CONFIG_PATH)
        infra_ctx = cfg.get("infra_context", {}).get("texto_contexto", "")

    infra_bloco = ("Contexto da infraestrutura DTI:\n" + infra_ctx) if infra_ctx else ""
    system_msg = f"""Você é um analista de triagem de chamados da DTI FGV. Classifique chamados de suporte técnico nas categorias do portfólio otimizado.

{infra_bloco}

CATEGORIAS DISPONÍVEIS:
{cats_texto}

Responda SOMENTE com JSON válido: titulo_sugerido (título conciso em até 10 palavras), texto_sugerido (texto completo do chamado em primeira pessoa, 3-5 frases, direto e objetivo — inclua TODOS os dados necessários já como placeholders em MAIUSCULAS_COM_UNDERSCORE, ex: VERSAO_PYTHON, NOME_VENV, NOME_BIBLIOTECA, VERSAO_BIBLIOTECA, NOME_SERVIDOR; se o chamado envolver linguagem de programação (Python, R, Julia, etc.), biblioteca ou framework, o texto DEVE especificar a versão — use placeholder VERSAO_X se o usuário pode escolher, ou escreva "versão mais recente disponível" se não há preferência indicada; NÃO use frases como "posso informar se necessário", "aguardo orientações" ou "caso necessário"; o texto deve conter tudo que o atendente precisa para resolver o chamado sem solicitar informações adicionais), categoria (nome exato de uma das categorias acima), justificativa (1-2 frases), confianca (alta, media ou baixa), informacoes_faltantes (lista de campos ausentes)."""

    user_msg = f"Descrição do chamado:\n{descricao}"

    try:
        azure_url = (
            f"{AZURE_OPENAI_ENDPOINT}/openai/deployments/{AZURE_OPENAI_DEPLOYMENT}"
            f"/chat/completions?api-version={AZURE_OPENAI_API_VERSION}"
        )
        resp = _requests.post(
            azure_url,
            headers={
                "api-key":        AZURE_OPENAI_API_KEY,
                "Content-Type":   "application/json",
            },
            json={
                "messages":        [
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_msg},
                ],
                "temperature":     0.1,
                "max_tokens":      700,
                "response_format": {"type": "json_object"},
            },
            timeout=30,
        )
        resp.raise_for_status()
        resultado = json.loads(resp.json()["choices"][0]["message"]["content"])

        # Enriquece com campos obrigatórios da categoria escolhida
        nome_cat = resultado.get("categoria", "")
        for cat in portfolio:
            if cat.get("nome", "").strip().lower() == nome_cat.strip().lower():
                resultado["informacoes_necessarias"] = (
                    cat.get("informacoes_obrigatorias") or
                    cat.get("informacoes_necessarias", [])
                )
                resultado["sla_sugerido"] = cat.get("sla_sugerido", "")
                resultado["complexidade"] = cat.get("complexidade", "")
                break

        return jsonify(_norm(resultado))

    except Exception as e:
        return jsonify({"erro": f"Erro ao chamar OpenAI: {str(e)}"}), 500


# ---------------------------------------------------------------------------
# API: Análise IA
# ---------------------------------------------------------------------------

@app.route("/api/analise-resumo")
def get_analise_resumo():
    if not P_RESULT.exists() and not P_FINAL.exists():
        return jsonify({"erro": "Resultados do pipeline não encontrados."}), 404

    d = _load_json(P_RESULT) if P_RESULT.exists() else {}

    rec  = d.get("recomendacao", {})
    meta = d.get("metadata", {})

    usando_curadoria = P_FINAL.exists()
    if usando_curadoria:
        final_data = _load_json(P_FINAL)
        portfolio_final = _portfolio_final_curado(final_data)
        analise_geral = _diagnostico_curadoria_stage7(final_data, portfolio_final)
        total_tickets = final_data.get("metadata", {}).get("total_classificados", meta.get("total_tickets", 0))
        problemas = []
        mapeamento = []
        acoes = []
    else:
        portfolio_llm = sorted(
            rec.get("portfolio_otimizado", []),
            key=lambda x: x.get("volume_estimado", 0), reverse=True
        )
        portfolio_final = _mesclar_portfolio(portfolio_llm)
        analise_geral = rec.get("analise_geral", "")
        total_tickets = meta.get("total_tickets", 0)
        problemas = rec.get("problemas_encontrados", [])
        mapeamento = rec.get("mapeamento_atual_vs_natural", [])
        acoes = rec.get("acoes_prioritarias", [])

    return jsonify(_norm({
        "total_tickets":           total_tickets,
        "categorias_atuais":       meta.get("n_categorias_atuais", 0),
        "grupos_naturais":         meta.get("n_grupos_naturais", 0),
        "categorias_recomendadas": len(portfolio_final),
        "usando_curadoria":        usando_curadoria,
        "fonte_portfolio":         "stage7" if usando_curadoria else "stage5",
        "analise_geral":           analise_geral,
        "problemas":               problemas,
        "portfolio_otimizado":     portfolio_final,
        "mapeamento":              mapeamento,
        "acoes":                   acoes,
        "categorias_atuais_volume":  d.get("categorias_atuais", {}),
        "metricas_interacoes":       calcular_metricas_interacoes(),
    }))


@app.route("/api/analise-clusters")
def get_analise_clusters():
    if not P_LABELS.exists():
        return jsonify({"erro": "04_labels.json não encontrado."}), 404
    data = _load_json(P_LABELS)
    clusters = sorted(data.get("clusters", []), key=lambda x: x.get("total_tickets", 0), reverse=True)
    return jsonify(_norm({
        "total_clusters": data.get("optimal_k", 0),
        "total_tickets":  data.get("total_tickets", 0),
        "clusters":       clusters,
    }))


@app.route("/api/interacoes-categorias")
def get_interacoes_categorias():
    """Tabela de interações por categoria: volume, resolução direta, múltiplas, tempos médios."""
    return jsonify(tabela_interacoes_por_categoria())


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("")
    print("  Triagem Inteligente de Chamados — DTI FGV")
    print("  http://localhost:5000")
    print("")
    app.run(debug=False, host="0.0.0.0", port=5000)
