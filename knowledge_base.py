#!/usr/bin/env python3
"""
Banco de dados SQLite — base de dados operacional do dashboard.

Tabela principal: chamados (dados brutos, um registro por chamado).
Todas as métricas são calculadas ao vivo via SQL — sem tabelas agregadas
que ficam obsoletas.

Critério de "resolvido": data_resolucao preenchida (não nula, não vazia).
Isso é mais confiável do que checar o nome do status, que pode variar.
"""

import json
import sqlite3
import pandas as pd
from pathlib import Path

SUMMARIES_PATH = Path(__file__).parent / "pipeline_data" / "02_summaries.json"

from data_loader import load_jira_data

DB_PATH = Path(__file__).parent / "knowledge_base.db"

# Valores que representam "sem data" no CSV do Jira
_SEM_DATA = {"", "nan", "None", "NaT", "NaN"}

# Padrões que indicam fechamento SEM resolução real (cancelamento, duplicata, etc.)
# Verificação case-insensitive por substring — não depende do nome exato do status.
# A taxa de resolução exclui esses casos; eles aparecem no breakdown de situações.
_PADROES_NAO_RESOLVIDO = [
    "cancel", "recus", "rejeit", "duplic", "inválid", "invalid",
    "descart", "abandon", "withdraw", "void",
]


def _e_finalizado(data_resolucao) -> bool:
    """Ticket foi fechado de qualquer forma (tem data de resolução)."""
    if data_resolucao is None:
        return False
    return str(data_resolucao).strip() not in _SEM_DATA


def _e_resolvido(data_resolucao, situacao) -> bool:
    """
    Ticket foi resolvido com solução real.
    Critério: tem data de resolução E o status não indica cancelamento.
    Os padrões são checados por substring case-insensitive para não depender
    do nome exato do status no Jira, que pode variar.
    """
    if not _e_finalizado(data_resolucao):
        return False
    sit = str(situacao or "").lower()
    return not any(p in sit for p in _PADROES_NAO_RESOLVIDO)


def _str(row, col) -> str | None:
    """Retorna string limpa ou None — trata NaN, 'nan', vazio."""
    v = row.get(col)
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    return None if s.lower() in ('nan', 'none', 'nat', 'nat', '') else s


def _date_iso(row, col) -> str | None:
    """Retorna data no formato ISO (YYYY-MM-DD HH:MM) para SQLite strftime funcionar."""
    # Tenta usar a coluna _dt já parseada pelo data_loader
    dt_col = col.replace('Criado', 'Criado_dt').replace('Resolvido', 'Resolvido_dt')
    dt = row.get(dt_col)
    if dt is not None and not (isinstance(dt, float) and pd.isna(dt)):
        try:
            return pd.Timestamp(dt).strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass
    # Fallback: tenta parsear o campo raw
    raw = _str(row, col)
    if not raw:
        return None
    try:
        return pd.to_datetime(raw, dayfirst=True).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return raw


def get_connection(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path or DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path=None):
    """Cria ou migra o schema do banco."""
    conn = get_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chamados (
            id                INTEGER PRIMARY KEY,
            chave             TEXT UNIQUE NOT NULL,
            titulo            TEXT,
            descricao         TEXT,
            situacao          TEXT,
            responsavel       TEXT,
            solicitante       TEXT,
            dpto_solicitante  TEXT,
            grupo_responsavel TEXT,
            chamado_reaberto  INTEGER DEFAULT 0,
            data_criacao      TEXT,
            data_resolucao    TEXT,
            finalizado        INTEGER DEFAULT 0,
            resolvido         INTEGER DEFAULT 0,
            tempo_total_horas      REAL,
            qtd_interacoes         INTEGER,
            tipo_solicitacao       TEXT,
            comentarios            TEXT,
            descricao_insuficiente TEXT
        )
    """)

    # Migração: adiciona colunas novas se o banco já existia sem elas
    colunas_existentes = {r[1] for r in cur.execute("PRAGMA table_info(chamados)")}
    novas = {
        "dpto_solicitante":       "TEXT",
        "grupo_responsavel":      "TEXT",
        "chamado_reaberto":       "INTEGER DEFAULT 0",
        "finalizado":             "INTEGER DEFAULT 0",
        "resolvido":              "INTEGER DEFAULT 0",
        "descricao_insuficiente": "TEXT",
    }
    for col, tipo in novas.items():
        if col not in colunas_existentes:
            cur.execute(f"ALTER TABLE chamados ADD COLUMN {col} {tipo}")
            print(f"[DB] Coluna adicionada: {col}")

    conn.commit()
    conn.close()


def load_chamados(db_path=None):
    """Lê os CSVs do Jira e popula (ou atualiza) a tabela chamados."""
    init_db(db_path)

    df = load_jira_data()
    conn = get_connection(db_path)
    cur = conn.cursor()

    inseridos = atualizados = 0
    for _, row in df.iterrows():
        data_res    = _date_iso(row, "Resolvido")
        situacao    = _str(row, "Situação") or ""
        reaberto_raw = (_str(row, "Chamado reaberto") or "").lower()
        reaberto    = 1 if reaberto_raw in ("sim", "yes", "true", "1") else 0
        finalizado  = 1 if _e_finalizado(data_res) else 0
        resolvido   = 1 if _e_resolvido(data_res, situacao) else 0

        descricao = _str(row, "Descrição")
        comentarios = _str(row, "comentarios_usuarios")

        valores = (
            row["Chave do item"],
            (_str(row, "Resumo") or "")[:500],
            descricao[:2000] if descricao else None,
            situacao or None,
            _str(row, "Responsável"),
            _str(row, "Solicitante"),
            _str(row, "Campo personalizado (Dpto solicitante)") or _str(row, "Dpto solicitante"),
            _str(row, "Grupo Responsável"),
            reaberto,
            _date_iso(row, "Criado"),
            data_res,
            finalizado,
            resolvido,
            float(row.get("Tempo total conclusão") or 0),
            int(row.get("qtd_interacoes") or 0),
            _str(row, "Customer Request Type"),
            comentarios[:2000] if comentarios else None,
        )

        try:
            cur.execute("""
                INSERT INTO chamados (
                    chave, titulo, descricao, situacao, responsavel, solicitante,
                    dpto_solicitante, grupo_responsavel, chamado_reaberto,
                    data_criacao, data_resolucao, finalizado, resolvido,
                    tempo_total_horas, qtd_interacoes, tipo_solicitacao, comentarios
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, valores)
            inseridos += 1
        except sqlite3.IntegrityError:
            # Atualiza campos que podem ter mudado
            cur.execute("""
                UPDATE chamados SET
                    situacao=?, responsavel=?, dpto_solicitante=?, grupo_responsavel=?,
                    chamado_reaberto=?, data_resolucao=?, finalizado=?, resolvido=?,
                    tempo_total_horas=?, qtd_interacoes=?
                WHERE chave=?
            """, (
                valores[3], valores[4], valores[6], valores[7],
                valores[8], valores[10], valores[11], valores[12],
                valores[13], valores[14],
                valores[0],
            ))
            atualizados += 1

    conn.commit()
    conn.close()
    print(f"[DB] {inseridos} inseridos, {atualizados} atualizados.")


def enriquecer_com_summaries(db_path=None) -> int:
    """
    Lê pipeline_data/02_summaries.json e atualiza o campo descricao_insuficiente
    em cada chamado. Deve ser chamado após load_chamados() e após o Stage 2 rodar.
    """
    if not SUMMARIES_PATH.exists():
        print("[DB] 02_summaries.json não encontrado — enriquecimento ignorado.")
        return 0

    with open(SUMMARIES_PATH, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    conn = get_connection(db_path)
    cur  = conn.cursor()
    atualizados = 0
    for s in summaries:
        chave = s.get("chave")
        valor = s.get("descricao_insuficiente")
        if chave and valor in ("sim", "nao"):
            cur.execute(
                "UPDATE chamados SET descricao_insuficiente = ? WHERE chave = ?",
                (valor, chave),
            )
            if cur.rowcount > 0:
                atualizados += 1

    conn.commit()
    conn.close()
    print(f"[DB] {atualizados} chamados enriquecidos com descricao_insuficiente.")
    return atualizados


if __name__ == "__main__":
    load_chamados()
    enriquecer_com_summaries()
    print("[DB] Banco atualizado com sucesso.")
