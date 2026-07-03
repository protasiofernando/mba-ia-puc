"""
Extração e tratamento dos dados exportados do Jira.

Lê os CSVs exportados do Jira (separador ^, UTF-8), aplica limpeza
de texto, consolida comentários e exporta um XLSX consolidado.

Por padrão descobre automaticamente todos os CSVs cujo nome começa com
Extracao_Jira, sem depender de anos fixos.
na pasta atual. Para passar arquivos explicitamente:

    python extracao/extrair_jira.py \
        --csvs "Extracao_Jira_2024.csv" "Extracao_Jira_2025.csv" "Extracao_Jira_2026.csv" \
        --saida "Extracao_Jira.xlsx"

Saída:
    Extracao_Jira.xlsx  (padrão na pasta atual)
"""

import re
import argparse
from pathlib import Path

import numpy as np
import pandas as pd

# ── Configuração padrão ────────────────────────────────────────────────────────

DEFAULT_OUTPUT = "Extracao_Jira.xlsx"

CSV_SEP      = "^"
CSV_ENCODING = "utf-8"
DATE_FMT     = "%d/%m/%Y %H:%M"
DATE_FMT_SEC = "%d/%m/%Y %H:%M:%S"

WANTED_COLS = [
    "Resumo",
    "Chave do item",
    "ID do item",
    "Situação",
    "Responsável",
    "Solicitante",
    "Criado",
    "Resolvido",
    "Descrição",
    "Anexos",
    "Chamado reaberto",
    "Confidencialidade",
    "Customer Request Type",
    "Dpto solicitante",
    "Grupo da Requisição",
    "Motivo",
    "SLA Datas_TTS",
    "SLA Duração_TTS",
    "SLA Resumo_TTS",
    "SLA Visão Geral_TTS",
    "SLA_TTS",
    "Tempo de Resolução",
    "Tipo da Requisição",
    "Grupo Responsável",
]

# ── Regex ─────────────────────────────────────────────────────────────────────

_comment_re   = re.compile(r"^Comentário(\.\d+)?$")
_invisiveis   = re.compile(r"[​-‍﻿⁠]")
_nbsp         = re.compile(r" ")
_servidor     = re.compile(r"\b(?:[A-Za-z]{9}\d{4}|[A-Za-z]{5}\d[A-Za-z]{3}\d{4})\b")
_email        = re.compile(r"\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b")
_illegal_xls  = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")


# ── Funções auxiliares ────────────────────────────────────────────────────────

def simplificar_campos(df: pd.DataFrame) -> pd.DataFrame:
    """Campo personalizado (Motivo) → Motivo"""
    novos = []
    for col in df.columns.astype(str):
        m = re.match(r"Campo personalizado \((.*?)\)(\.\d+)?$", col)
        novos.append((m.group(1).strip("[]") + (m.group(2) or "")) if m else col)
    df.columns = novos
    return df


def _order(col: str) -> int:
    m = re.match(r"^Comentário(?:\.(\d+))?$", col)
    return int(m.group(1)) if m and m.group(1) else 0


def comment_cols(df: pd.DataFrame) -> list:
    return sorted([c for c in df.columns if _comment_re.match(str(c))], key=_order)


def expand(df_cols, base: str) -> list:
    pat = re.compile(rf"^{re.escape(base)}(?:\.\d+)?$")
    return [c for c in df_cols if pat.match(str(c))]


def limpar_texto(series: pd.Series) -> pd.Series:
    s = series.copy()
    mask = s.notna()
    t = s[mask].astype(str)
    t = t.str.replace(r"\r\n?", "\n", regex=True).str.replace(r"\f", "\n", regex=True)
    t = t.str.replace(_invisiveis, "", regex=True).str.replace(_nbsp, " ", regex=True)
    t = t.str.replace(
        r"^(\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2};[^;]+;)", r"\1\n", regex=True
    )
    t = t.str.replace(r";(?:public|internal);;|\{\*\}|\*", "", regex=True)
    t = t.str.replace(_servidor, "servidor_exemplo", regex=True)
    t = t.str.replace(_email, "email_exemplo", regex=True)
    t = t.str.replace(r"\n[ \t]*\n+", "\n", regex=True)
    t = t.str.replace(r"[ \t]{2,}", " ", regex=True).str.strip()
    s[mask] = t
    return s


def sanitize_excel(df: pd.DataFrame) -> pd.DataFrame:
    for c in df.select_dtypes(include=["object", "string"]).columns:
        mask = df[c].notna()
        df.loc[mask, c] = df.loc[mask, c].astype(str).map(
            lambda v: _illegal_xls.sub("", v)
        )
    return df


# ── Etapas principais ─────────────────────────────────────────────────────────

def carregar_csvs(arquivos: list, sep: str, encoding: str) -> pd.DataFrame:
    dfs = []
    for f in arquivos:
        p = Path(f)
        if not p.exists():
            print(f"[AVISO] Arquivo não encontrado, ignorado: {p}")
            continue
        dfs.append(pd.read_csv(p, sep=sep, encoding=encoding))
    if not dfs:
        raise FileNotFoundError("Nenhum arquivo CSV encontrado.")
    df = pd.concat(dfs, ignore_index=True)
    print(f"[OK] Carregados {len(df)} registros de {len(dfs)} arquivo(s)")
    return df


def processar_comentarios(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()
    cols = comment_cols(df)
    if not cols:
        df["comentarios_usuarios"] = ""
        df["qtd_interacoes"] = 1
        return df

    s = df[cols].stack(dropna=True).astype(str)
    autor = s.str.extract(
        r"^\s*\d{2}/\d{2}/\d{4}\s+\d{2}:\d{2}\s*;\s*([^;\s]+)", expand=False
    ).str.lower()
    s_humano = s[autor.notna() & autor.ne("automato")]

    n = s_humano.groupby(level=0).cumcount() + 1
    humano_wide = s_humano.copy()
    humano_wide.index = pd.MultiIndex.from_arrays(
        [humano_wide.index.get_level_values(0), n], names=["row_id", "n"]
    )
    humano_wide = humano_wide.unstack("n")
    humano_wide.columns = [
        "Comentário" if i == 1 else f"Comentário.{i-1}" for i in humano_wide.columns
    ]
    for c in humano_wide.columns:
        humano_wide[c] = limpar_texto(humano_wide[c])

    df = df.drop(columns=cols).join(humano_wide)
    final = comment_cols(df)

    df["comentarios_usuarios"] = (
        df[final]
        .apply(lambda r: "\n\n".join(x for x in r.dropna().astype(str) if x.strip()), axis=1)
        .fillna("")
    )
    df["qtd_interacoes"] = df[final].notna().sum(axis=1) + 1

    cols_ord = df.columns.tolist()
    cols_ord.remove("qtd_interacoes")
    cols_ord.insert(cols_ord.index("comentarios_usuarios"), "qtd_interacoes")
    print(f"[OK] Comentários humanos processados: {len(final)} colunas")
    return df[cols_ord]


def selecionar_colunas(df: pd.DataFrame, wanted: list) -> pd.DataFrame:
    df = df.copy()
    df.columns = df.columns.astype(str).str.strip()

    keep = []
    for base in wanted:
        keep.extend(expand(df.columns, base))
    keep.extend(expand(df.columns, "Comentário"))
    for c in ["qtd_interacoes", "comentarios_usuarios"]:
        if c in df.columns:
            keep.append(c)
    for base in ["Descrição", "Resumo"]:
        keep.extend(expand(df.columns, base))

    seen = set()
    keep = [c for c in keep if not (c in seen or seen.add(c))]
    df = df[[c for c in keep if c in df.columns]]

    # Limpeza de texto
    texto_cols = (
        [c for c in df.columns if re.match(r"^(Descrição|Resumo|Comentário)(\.\d+)?$", str(c))]
        + (["comentarios_usuarios"] if "comentarios_usuarios" in df.columns else [])
    )
    seen2 = set()
    for c in [x for x in texto_cols if not (x in seen2 or seen2.add(x))]:
        df[c] = limpar_texto(df[c])

    # Tempo total de conclusão
    if {"Criado", "Resolvido"}.issubset(df.columns):
        def parse_dt(col):
            dt = pd.to_datetime(df[col], format=DATE_FMT, errors="coerce")
            mask = dt.isna() & df[col].notna()
            dt[mask] = pd.to_datetime(df.loc[mask, col], format=DATE_FMT_SEC, errors="coerce")
            return dt

        tempo = ((parse_dt("Resolvido") - parse_dt("Criado")).dt.total_seconds() / 3600).round(2)
        pos = df.columns.get_loc("Criado") + 1
        df.insert(pos, "Tempo total conclusão", tempo)

    print(f"[OK] DataFrame final: {df.shape[0]} linhas × {df.shape[1]} colunas")
    return sanitize_excel(df)


# ── Entry point ───────────────────────────────────────────────────────────────

def _discover_csvs() -> list:
    """Descobre todos os Extracao_Jira*.csv na pasta atual, ordenados."""
    return sorted(
        p for p in Path(".").iterdir()
        if p.is_file()
        and p.suffix.lower() == ".csv"
        and p.stem.lower().startswith("extracao_jira")
    )


def main():
    parser = argparse.ArgumentParser(description="Extrai e trata dados do Jira")
    parser.add_argument(
        "--csvs", nargs="+", default=None,
        metavar="CSV",
        help="Caminhos dos CSVs do Jira. Se omitido, descobre automaticamente "
             "todos os Extracao_Jira*.csv na pasta atual.",
    )
    parser.add_argument("--saida", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    if args.csvs:
        arquivos = args.csvs
    else:
        arquivos = _discover_csvs()
        if not arquivos:
            parser.error(
                "Nenhum arquivo Extracao_Jira*.csv encontrado na pasta atual. "
                "Use --csvs para especificar os arquivos."
            )
        print(f"[INFO] Arquivos encontrados: {[str(p) for p in arquivos]}")

    df = carregar_csvs(arquivos, CSV_SEP, CSV_ENCODING)
    df = simplificar_campos(df)
    df = processar_comentarios(df)
    df = selecionar_colunas(df, WANTED_COLS)

    df.to_excel(args.saida, index=False)
    print(f"[OK] Exportado: {args.saida}")


if __name__ == "__main__":
    main()
