#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Valida entradas obrigatorias antes de enviar/rodar no HPC.

Este script existe para impedir rodadas baseadas em contexto inferido. Para o
pipeline LLM funcionar, o usuario deve fornecer:
- CSVs em data/ com nomes padronizados: <slug>__YYYY-MM__YYYY-MM.csv
- contexto_catalogo.md real, vindo da area/sistema, nao inferido pelo agente
- config_portfolio.json preenchido com contexto do portal
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from projeto import (
    config_path,
    contexto_catalogo_path,
    data_dir,
    projeto_meta_path,
)


SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def load_json(path: Path) -> dict:
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except Exception as exc:
        raise ValueError(f"nao foi possivel ler JSON {path.name}: {exc}") from exc


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except Exception as exc:
        raise ValueError(f"nao foi possivel ler {path.name}: {exc}") from exc


def validate() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    projeto_path = projeto_meta_path()
    if not projeto_path.exists():
        errors.append("projeto.json ausente.")
        projeto = {}
    else:
        try:
            projeto = load_json(projeto_path)
        except ValueError as exc:
            errors.append(str(exc))
            projeto = {}

    slug = str(projeto.get("slug", "")).strip()
    if not slug:
        errors.append("projeto.json sem slug.")
    elif not SLUG_RE.match(slug):
        errors.append("slug invalido. Use apenas minusculas, numeros e hifen, ex.: banco-dados.")

    portal_nome = str(projeto.get("portal_nome") or projeto.get("nome") or "").strip()
    if not portal_nome or portal_nome.lower().startswith("nome "):
        errors.append("projeto.json deve ter nome/portal_nome real.")

    # CSVs
    ddir = data_dir()
    csvs = sorted(p for p in ddir.glob("*.csv") if p.is_file()) if ddir.exists() else []
    if not csvs:
        errors.append(f"nenhum CSV encontrado em {ddir}.")
    elif slug:
        expected = re.compile(rf"^{re.escape(slug)}__(\d{{4}}-\d{{2}})__(\d{{4}}-\d{{2}})\.csv$")
        for csv in csvs:
            m = expected.match(csv.name)
            if not m:
                errors.append(
                    f"CSV fora do padrao: {csv.name}. Use {slug}__YYYY-MM__YYYY-MM.csv."
                )
                continue
            inicio, fim = m.groups()
            if inicio > fim:
                errors.append(f"CSV com periodo invertido: {csv.name}.")
    csv_glob = str(projeto.get("csv_glob", "")).strip()
    if slug and csv_glob != f"{slug}__*.csv":
        errors.append(f"csv_glob deve ser \"{slug}__*.csv\" para este projeto.")

    # contexto_catalogo.md
    catalogo_path = contexto_catalogo_path()
    if not catalogo_path.exists():
        errors.append("contexto_catalogo.md ausente. Forneca o catalogo real antes do HPC.")
    else:
        try:
            catalogo = read_text(catalogo_path)
            lower = catalogo.lower()
            proibidos = [
                "<nome",
                "<slug",
                "<para que serve",
                "preencha uma tabela",
                "foram inferidos",
                "inferidos a partir",
                "valide/ajuste conforme",
                "as 44 categorias abaixo",
                "substituir pelo catalogo real",
                "pendente: catalogo real",
                "catalogo real ausente",
            ]
            if len(catalogo.strip()) < 500:
                errors.append("contexto_catalogo.md parece curto demais para ser o catalogo real.")
            if any(token in lower for token in proibidos):
                errors.append(
                    "contexto_catalogo.md contem placeholder ou texto inferido. "
                    "Substitua pelo catalogo real fornecido pela area/sistema."
                )
            if "grupo" not in lower or ("chamado" not in lower and "request type" not in lower):
                warnings.append(
                    "contexto_catalogo.md nao menciona claramente grupos e chamados/request types."
                )
        except ValueError as exc:
            errors.append(str(exc))

    # config_portfolio.json
    cpath = config_path()
    if not cpath.exists():
        errors.append("config_portfolio.json ausente.")
    else:
        try:
            cfg = load_json(cpath)
            texto = str(cfg.get("infra_context", {}).get("texto_contexto", "")).strip()
            if len(texto) < 300 or "DESCREVA AQUI" in texto.upper():
                errors.append("config_portfolio.json precisa de infra_context.texto_contexto real.")
        except ValueError as exc:
            errors.append(str(exc))

    for warning in warnings:
        print(f"AVISO: {warning}")
    if errors:
        print("ERROS DE PRE-HPC:")
        for err in errors:
            print(f"- {err}")
        return 1

    print(f"Pre-HPC OK: {len(csvs)} CSV(s) padronizado(s), catalogo real presente.")
    return 0


if __name__ == "__main__":
    sys.exit(validate())
