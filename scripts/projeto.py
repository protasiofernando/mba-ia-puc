#!/usr/bin/env python3
"""
Resolução das pastas do projeto - auto-relativa.

Cada portal é um projeto AUTOCONTIDO e independente. Este arquivo mora em
<projeto>/scripts/projeto.py, então a raiz do projeto é sempre a pasta que
contém scripts/, dashboard/, data/, configuracao/ etc. - descoberta a
partir da localização deste arquivo, sem depender de variável de ambiente.

Estrutura esperada dentro da raiz do projeto:
  scripts/              este código (extract, data_loader, knowledge_base, ...)
  dashboard/            app Flask (painel próprio do projeto)
  data/                 CSV(s) exportado(s) do portal
  pipeline_data/        saídas das etapas (01..07)
  configuracao/         metadados, contexto e catálogo institucional
  formacao_portfolio/decisao_curada/  decisão e espelho analítico
  dashboard/runtime/    banco local gerado do dashboard
"""

import os
import json
from pathlib import Path


def projeto_dir() -> Path:
    """Raiz do projeto (pasta que contém scripts/). Auto-relativa a este arquivo."""
    return Path(__file__).resolve().parent.parent


def load_projeto_meta() -> dict:
    """Lê projeto.json (metadados do projeto). Retorna {} se não existir."""
    p = projeto_meta_path()
    if p.exists():
        with open(p, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    return {}


def data_dir() -> Path:
    """Pasta com os CSVs. JIRA_DATA_DIR sobrepõe (aponta para outra pasta)."""
    override = os.getenv("JIRA_DATA_DIR", "").strip()
    return Path(override).resolve() if override else projeto_dir() / "data"


def pipeline_data_dir() -> Path:
    """Pasta de saídas do pipeline (criada se não existir).

    PIPELINE_DATA_DIR permite executar réplicas experimentais com o mesmo
    código, mantendo checkpoints e artefatos isolados. Sem a variável, o
    comportamento operacional permanece inalterado.
    """
    override = os.getenv("PIPELINE_DATA_DIR", "").strip()
    d = Path(override).resolve() if override else projeto_dir() / "pipeline_data"
    d.mkdir(parents=True, exist_ok=True)
    return d


def config_path() -> Path:
    override = os.getenv("PORTFOLIO_CONFIG_PATH", "").strip()
    return (
        Path(override).resolve()
        if override
        else projeto_dir() / "configuracao" / "config_portfolio.json"
    )


def contexto_catalogo_path() -> Path:
    override = os.getenv("CATALOG_CONTEXT_PATH", "").strip()
    return (
        Path(override).resolve()
        if override
        else projeto_dir() / "configuracao" / "contexto_catalogo.md"
    )


def projeto_meta_path() -> Path:
    return projeto_dir() / "configuracao" / "projeto.json"


def feedback_path() -> Path:
    return (
        projeto_dir()
        / "formacao_portfolio"
        / "decisao_curada"
        / "feedback_portfolio.json"
    )


def portfolio_referencia_path() -> Path:
    return (
        projeto_dir()
        / "formacao_portfolio"
        / "decisao_curada"
        / "portfolio_referencia.json"
    )


def db_path() -> Path:
    return projeto_dir() / "dashboard" / "runtime" / "knowledge_base.db"


def csv_glob() -> str:
    """Padrão de nome dos CSVs a carregar (projeto.json > 'csv_glob'; padrão '*.csv')."""
    return (load_projeto_meta().get("csv_glob") or "*.csv").strip()
