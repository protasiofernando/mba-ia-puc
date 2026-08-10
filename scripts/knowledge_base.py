#!/usr/bin/env python3
"""
Banco de dados SQLite - base operacional do dashboard do projeto ativo.

Tabela principal: chamados (dados brutos, um registro por chamado).
Todas as métricas são calculadas ao vivo via SQL - sem tabelas agregadas
que ficam obsoletas.

O banco é gravado em <projeto>/dashboard/runtime/knowledge_base.db e lê os CSVs
de <projeto>/data
(ou JIRA_DATA_DIR). Rode uma vez após configurar o projeto, a partir da pasta do
projeto:

  python scripts/knowledge_base.py
"""

import sys
import json
import re
import sqlite3
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from data_loader import load_jira_data
from projeto import db_path, pipeline_data_dir

# Valores que representam "sem data" no CSV
_SEM_DATA = {"", "nan", "None", "NaT", "NaN"}

# Padrões que indicam fechamento SEM resolução real (cancelamento, duplicata, etc.)
_PADROES_NAO_RESOLVIDO = [
    "cancel", "recus", "rejeit", "duplic", "inválid", "invalid",
    "descart", "abandon", "withdraw", "void",
]


def _tem_situacao_terminal_sem_resolucao(situacao) -> bool:
    sit = str(situacao or "").lower()
    return any(p in sit for p in _PADROES_NAO_RESOLVIDO)


def _e_finalizado(data_resolucao, situacao) -> bool:
    if data_resolucao is not None and str(data_resolucao).strip() not in _SEM_DATA:
        return True
    return _tem_situacao_terminal_sem_resolucao(situacao)


def _e_resolvido(data_resolucao, situacao) -> bool:
    if data_resolucao is None or str(data_resolucao).strip() in _SEM_DATA:
        return False
    sit = str(situacao or "").lower()
    return not any(p in sit for p in _PADROES_NAO_RESOLVIDO)


def _str(row, col):
    v = row.get(col)
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    s = str(v).strip()
    return None if s.lower() in ('nan', 'none', 'nat', '') else s


def _date_iso(row, col):
    dt_col = col.replace('Criado', 'Criado_dt').replace('Resolvido', 'Resolvido_dt')
    dt = row.get(dt_col)
    if dt is not None and not (isinstance(dt, float) and pd.isna(dt)):
        try:
            return pd.Timestamp(dt).strftime('%Y-%m-%d %H:%M')
        except Exception:
            pass
    raw = _str(row, col)
    if not raw:
        return None
    try:
        return pd.to_datetime(raw, dayfirst=True).strftime('%Y-%m-%d %H:%M')
    except Exception:
        return raw


def _dpto_solicitante(row):
    """Extrai area/departamento do solicitante quando o export do Jira traz esse dado."""
    for col in (
        "Campo personalizado (Dpto solicitante)",
        "Dpto solicitante",
        "Campo personalizado (Departamento)",
        "Campo personalizado (Organizações)",
    ):
        valor = _str(row, col)
        if valor:
            return valor

    info_usuario = _str(row, "Campo personalizado (Informações do usuário)")
    if info_usuario:
        match = re.search(r"(?:^|;)\s*Depto:\s*([^;]+)", info_usuario, flags=re.IGNORECASE)
        if match:
            return match.group(1).strip()

    return _str(row, "Campo personalizado ([SD Unidade])")


def get_connection(db=None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db or db_path()))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db=None):
    conn = get_connection(db)
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


def load_chamados(db=None):
    init_db(db)
    df = load_jira_data()
    conn = get_connection(db)
    cur = conn.cursor()

    inseridos = atualizados = 0
    for _, row in df.iterrows():
        data_res     = _date_iso(row, "Resolvido")
        situacao     = _str(row, "Situação") or ""
        reaberto_raw = (_str(row, "Chamado reaberto") or "").lower()
        reaberto     = 1 if reaberto_raw in ("sim", "yes", "true", "1") else 0
        finalizado   = 1 if _e_finalizado(data_res, situacao) else 0
        resolvido    = 1 if _e_resolvido(data_res, situacao) else 0

        descricao   = _str(row, "Descrição")
        comentarios = _str(row, "comentarios_usuarios")

        valores = (
            row["Chave do item"],
            (_str(row, "Resumo") or "")[:500],
            descricao[:2000] if descricao else None,
            situacao or None,
            _str(row, "Responsável"),
            _str(row, "Solicitante"),
            _dpto_solicitante(row),
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


def enriquecer_com_summaries(db=None) -> int:
    """
    Lê pipeline_data/02_summaries.json (produzido pelo LLM local no Stage 2) e
    atualiza descricao_insuficiente em cada chamado. Rodar após o Stage 2.
    """
    summaries_path = pipeline_data_dir() / "02_summaries.json"
    if not summaries_path.exists():
        print("[DB] 02_summaries.json não encontrado - enriquecimento ignorado.")
        return 0

    with open(summaries_path, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    conn = get_connection(db)
    cur = conn.cursor()
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
