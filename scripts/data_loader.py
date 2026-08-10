#!/usr/bin/env python3
"""
Utilitário central de carregamento dos CSVs do portal (Jira Service Management).

Descobre automaticamente os CSVs na pasta de dados do projeto ativo e os combina,
derivando as colunas calculadas que o restante do projeto espera:
  - Tempo total conclusão  (horas entre Criado e Resolvido)
  - qtd_interacoes         (quantidade de colunas Comentário preenchidas)
  - comentarios_usuarios   (texto concatenado de todos os Comentários)

Na arquitetura vigente, a descoberta não exige
nomes começando com "Extracao_Jira" - carrega o padrão definido em
configuracao/projeto.json
("csv_glob", padrão "*.csv"). Isso acomoda exports como "sdgov_720d_v2.csv".

A pasta de dados é <projeto>/data (resolvida por scripts/projeto.py), ou
JIRA_DATA_DIR quando definida.
"""

import sys
import pandas as pd
from pathlib import Path
from typing import Union, List

sys.path.insert(0, str(Path(__file__).parent))
from projeto import data_dir, csv_glob


def _discover_csvs(directory: Path, pattern: str) -> list:
    """Retorna todos os CSVs da pasta que casam com o padrão, ordenados."""
    if not directory.exists():
        return []
    return sorted(
        p for p in directory.glob(pattern)
        if p.is_file() and p.suffix.lower() == ".csv"
    )


def load_jira_data(csv_paths: Union[str, List[str], None] = None) -> pd.DataFrame:
    """
    Lê um ou mais CSVs do portal (separador ^), combina e deriva colunas.

    Quando csv_paths é None, descobre automaticamente os CSVs em data_dir()
    usando o padrão csv_glob() do projeto.
    """
    if csv_paths is None:
        directory = data_dir()
        pattern = csv_glob()
        csv_paths = _discover_csvs(directory, pattern)
        if not csv_paths:
            raise FileNotFoundError(
                f"Nenhum CSV ('{pattern}') encontrado em: {directory}\n"
                "Verifique a pasta data/ do projeto (ou a variável JIRA_DATA_DIR)."
            )
    elif isinstance(csv_paths, (str, Path)):
        csv_paths = [csv_paths]

    dfs = []
    for path in csv_paths:
        p = Path(path)
        if not p.exists():
            print(f"[AVISO] Arquivo não encontrado, ignorado: {p}")
            continue
        df = pd.read_csv(p, sep='^', encoding='utf-8', low_memory=False, dtype=str)
        print(f"   {p.name}: {len(df)} linhas")
        dfs.append(df)

    if not dfs:
        raise FileNotFoundError(
            "Nenhum arquivo CSV encontrado. Verifique os caminhos:\n"
            + "\n".join(str(p) for p in csv_paths)
        )

    df = pd.concat(dfs, ignore_index=True)

    if 'Chave do item' not in df.columns:
        raise ValueError("Coluna obrigatória ausente nos CSVs: 'Chave do item'")
    for col in ('Criado', 'Resolvido'):
        if col not in df.columns:
            df[col] = None

    # Remove duplicados pela chave do item
    antes = len(df)
    df = df.drop_duplicates(subset=['Chave do item'])
    if len(df) < antes:
        print(f"   {antes - len(df)} duplicados removidos")

    print(f"[OK] {len(df)} chamados carregados no total")

    # --- Colunas derivadas ---

    # Tempo total conclusão (horas)
    df['Criado_dt'] = pd.to_datetime(df['Criado'], dayfirst=True, errors='coerce')
    df['Resolvido_dt'] = pd.to_datetime(df['Resolvido'], dayfirst=True, errors='coerce')
    df['Tempo total conclusão'] = (
        (df['Resolvido_dt'] - df['Criado_dt']).dt.total_seconds() / 3600
    ).fillna(0).clip(lower=0)

    # Quantidade de interações = nº de colunas "Comentário" preenchidas
    comentario_cols = [c for c in df.columns
                       if c.strip() == 'Comentário' or c.strip().startswith('Comentário.')]
    if comentario_cols:
        df['qtd_interacoes'] = df[comentario_cols].notna().sum(axis=1).astype(int)
    elif 'qtd_interacoes' in df.columns:
        df['qtd_interacoes'] = pd.to_numeric(df['qtd_interacoes'], errors='coerce').fillna(0).astype(int)
    else:
        df['qtd_interacoes'] = 0

    # Texto concatenado dos comentários
    def _concat_comentarios(row):
        partes = [str(v).strip() for v in row if pd.notna(v) and str(v).strip() not in ('', 'nan')]
        return ' | '.join(partes) if partes else None

    if comentario_cols:
        df['comentarios_usuarios'] = df[comentario_cols].apply(_concat_comentarios, axis=1)
    elif 'comentarios_usuarios' not in df.columns:
        df['comentarios_usuarios'] = None

    # Garante que Customer Request Type exista
    if 'Customer Request Type' not in df.columns:
        df['Customer Request Type'] = 'Não categorizado'
    df['Customer Request Type'] = df['Customer Request Type'].fillna('Não categorizado')

    return df
