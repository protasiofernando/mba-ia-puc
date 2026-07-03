#!/usr/bin/env python3
"""
Utilitário central de carregamento dos CSVs do Jira.
Descobre automaticamente todos os arquivos Extracao_Jira*.csv no diretório
de dados e os combina, derivando as colunas calculadas que o restante do
projeto espera:
  - Tempo total conclusão  (horas entre Criado e Resolvido)
  - qtd_interacoes         (quantidade de colunas Comentário preenchidas)
  - comentarios_usuarios   (texto concatenado de todos os Comentários)

O diretório de dados pode ser sobrescrito via variável de ambiente:
  JIRA_DATA_DIR=/caminho/para/pasta/com/csvs
"""

import os as _os
import pandas as pd
from pathlib import Path
from typing import Union, List

_DATA_DIR = Path(_os.getenv("JIRA_DATA_DIR", str(Path(__file__).parent / "data")))


def _discover_csvs(data_dir: Path) -> list:
    """
    Retorna todos os CSVs de extração do Jira, ordenados.

    O ano não faz parte da regra de negócio: qualquer arquivo CSV cujo nome
    comece com Extracao_Jira é carregado, por exemplo:
      - Extracao_Jira_2024.csv
      - Extracao_Jira_2026.csv
      - Extracao_Jira_periodo_teste.csv
    """
    if not data_dir.exists():
        return []
    return sorted(
        p for p in data_dir.iterdir()
        if p.is_file()
        and p.suffix.lower() == ".csv"
        and p.stem.lower().startswith("extracao_jira")
    )


def load_jira_data(csv_paths: Union[str, List[str], None] = None) -> pd.DataFrame:
    """
    Lê um ou mais CSVs do Jira (separador ^), combina e deriva colunas.

    Parâmetros
    ----------
    csv_paths : str | list[str] | None
        Caminho(s) para os arquivos CSV. Quando None, descobre automaticamente
        todos os Extracao_Jira*.csv em JIRA_DATA_DIR.

    Retorna
    -------
    pd.DataFrame com todas as colunas originais mais as derivadas.
    """
    if csv_paths is None:
        csv_paths = _discover_csvs(_DATA_DIR)
        if not csv_paths:
            raise FileNotFoundError(
                f"Nenhum arquivo Extracao_Jira*.csv encontrado em: {_DATA_DIR}\n"
                "Defina JIRA_DATA_DIR para apontar para o diretório correto."
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
