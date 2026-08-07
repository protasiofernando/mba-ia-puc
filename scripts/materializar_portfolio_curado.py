#!/usr/bin/env python3
"""Valida e materializa a decisao humana registrada no Stage 7.

Este modulo separa tres objetos que nao devem ser confundidos:

1. ``05_portfolio_recommendation.json``: candidato automatico;
2. ``formacao_portfolio/decisao_curada/feedback_portfolio.json``: decisao
   operacional curada pela area;
3. ``formacao_portfolio/decisao_curada/portfolio_referencia.json``: projecao
   analitica congelada dessa decisao.

O script nao inventa nem altera categorias. Por padrao, apenas valida a
equivalencia entre a decisao e o espelho que foi usado no estudo. Com
``--write-operational`` ele gera o agregado publicavel do Stage 7. Volumes so
sao preenchidos quando uma classificacao automatica por chamado e fornecida.

Os arquivos congelados do experimento nunca sao sobrescritos por este script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DECISION_DIR = ROOT / "formacao_portfolio" / "decisao_curada"
DEFAULT_FEEDBACK = DECISION_DIR / "feedback_portfolio.json"
DEFAULT_REFERENCE = DECISION_DIR / "portfolio_referencia.json"
DEFAULT_CONTRACT = ROOT / "formacao_portfolio" / "contrato_curadoria.json"
DEFAULT_OUTPUT = ROOT / "pipeline_data" / "07_portfolio_final.json"
DEFAULT_CLASSIFICATIONS = ROOT / "pipeline_data" / "07_classificados_final.json"


class CurationError(RuntimeError):
    """Contrato da curadoria invalido ou inconsistente."""


def _load(path: Path):
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_value = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return "_".join(
        part
        for part in "".join(
            char if char.isalnum() else "_" for char in ascii_value.casefold()
        ).split("_")
        if part
    )


def _feedback_categories(feedback: dict) -> list[dict]:
    rows = feedback.get("portfolio_final")
    if not isinstance(rows, list) or not rows:
        raise CurationError("feedback_portfolio.json nao possui portfolio_final")
    if not all(isinstance(row, dict) for row in rows):
        raise CurationError("portfolio_final deve conter somente objetos")
    return rows


def validate_feedback(feedback: dict, contract: dict) -> None:
    categories = _feedback_categories(feedback)
    required = {
        "id",
        "nome",
        "grupo",
        "descricao",
        "quando_usar",
        "informacoes_obrigatorias",
    }
    ids: set[str] = set()
    names: set[str] = set()
    for index, category in enumerate(categories):
        missing = sorted(required - set(category))
        if missing:
            raise CurationError(
                f"portfolio_final[{index}] sem campos obrigatorios: {missing}"
            )
        category_id = str(category["id"]).strip()
        name = str(category["nome"]).strip()
        if not category_id or category_id in ids:
            raise CurationError(f"id vazio ou duplicado: {category_id!r}")
        if not name or name.casefold() in names:
            raise CurationError(f"nome vazio ou duplicado: {name!r}")
        ids.add(category_id)
        names.add(name.casefold())
        fields = category.get("informacoes_obrigatorias")
        if not isinstance(fields, list) or not all(
            isinstance(field, str) and field.strip() for field in fields
        ):
            raise CurationError(
                f"informacoes_obrigatorias invalidas em {category_id}"
            )

    fixed_ids = set(contract.get("fixed_outside_analysis", []))
    if not fixed_ids:
        raise CurationError("contrato sem fixed_outside_analysis")
    missing_fixed = sorted(fixed_ids - ids)
    if missing_fixed:
        raise CurationError(f"itens fixos ausentes da curadoria: {missing_fixed}")
    for category in categories:
        if category["id"] in fixed_ids:
            if not category.get("fora_da_analise") or not category.get("imutavel"):
                raise CurationError(
                    f"item fixo {category['id']} deve ser imutavel e fora da analise"
                )


def build_reference(feedback: dict, contract: dict) -> dict:
    """Constroi a projecao analitica sem usar resultados dos metodos."""
    validate_feedback(feedback, contract)
    categories = _feedback_categories(feedback)
    group_ids = contract["group_ids"]
    analysis = contract["category_analysis"]
    fixed_ids = set(contract["fixed_outside_analysis"])

    analytical = []
    fixed = []
    seen_groups: list[str] = []
    for source in categories:
        item = dict(source)
        category_id = item["id"]
        group_name = item.pop("grupo")
        group_id = group_ids.get(group_name) or _slug(group_name)
        if category_id in fixed_ids:
            fixed_item = {
                "id": category_id,
                "nome": item["nome"],
                "grupo_id": group_id,
                "descricao": item["descricao"],
                "quando_usar": item["quando_usar"],
                "responsavel": item.get("responsavel"),
                "visivel_no_portal_dti_pesquisa": bool(
                    item.get("visivel_no_portal_dti_pesquisa")
                ),
                "encaminhamento": bool(item.get("encaminhamento")),
                "imutavel": bool(item.get("imutavel")),
                "participa_descoberta": False,
                "participa_otimizacao": False,
                "participa_metricas": False,
                "participa_ranking": False,
                "informacoes_obrigatorias": item["informacoes_obrigatorias"],
                "gestao_do_formulario": item.get("gestao_do_formulario"),
                "nota": contract["fixed_item_note"],
            }
            fixed.append({k: v for k, v in fixed_item.items() if v is not None})
            continue

        if group_id not in seen_groups:
            seen_groups.append(group_id)
        rule = analysis.get(category_id)
        if not isinstance(rule, dict):
            raise CurationError(
                f"contrato sem regra analitica para a categoria {category_id}"
            )
        analytical_item = {
            "id": category_id,
            "nome": item["nome"],
            "grupo_id": group_id,
            "descricao": item["descricao"],
            "quando_usar": item["quando_usar"],
            "informacoes_obrigatorias": item["informacoes_obrigatorias"],
            **rule,
        }
        if "nota_campos" in item:
            analytical_item["nota_campos"] = item["nota_campos"]
        analytical.append(analytical_item)

    group_names = {value: key for key, value in group_ids.items()}
    ordered_group_ids = contract.get("group_order", seen_groups)
    groups = [
        {"id": group_id, "nome": group_names.get(group_id, group_id)}
        for group_id in ordered_group_ids
        if group_id in seen_groups
    ]
    return {
        "schema_version": contract["reference_schema_version"],
        "metadata": contract["reference_metadata"],
        "grupos_analiticos": groups,
        "categorias_analiticas": analytical,
        "itens_fixos_fora_analise": fixed,
    }


def semantic_view(reference: dict) -> dict:
    """Campos que definem o alvo; ignora apenas ordem de chaves/formatacao."""
    return {
        "schema_version": reference.get("schema_version"),
        "metadata": reference.get("metadata"),
        "grupos_analiticos": reference.get("grupos_analiticos"),
        "categorias_analiticas": reference.get("categorias_analiticas"),
        "itens_fixos_fora_analise": reference.get("itens_fixos_fora_analise"),
    }


def build_operational(
    feedback: dict,
    classifications: list[dict] | None = None,
) -> dict:
    categories = [dict(row) for row in _feedback_categories(feedback)]
    counts: Counter[str] = Counter()
    if classifications is not None:
        if not isinstance(classifications, list):
            raise CurationError("classificacoes do Stage 7 devem ser uma lista")
        valid_ids = {row["id"] for row in categories}
        for row in classifications:
            category_id = str(row.get("categoria_id", "")).strip()
            if category_id not in valid_ids:
                raise CurationError(
                    f"classificacao aponta para categoria inexistente: {category_id!r}"
                )
            counts[category_id] += 1

    analytical_ids = {
        row["id"] for row in categories if not row.get("fora_da_analise")
    }
    analytical_base = sum(counts[category_id] for category_id in analytical_ids)
    for category in categories:
        if classifications is None:
            category["volume"] = None
            category["percentual_portfolio"] = None
        else:
            count = counts[category["id"]]
            category["volume"] = count
            category["percentual_portfolio"] = (
                None
                if category.get("fora_da_analise")
                else round(100 * count / analytical_base, 1)
                if analytical_base
                else 0.0
            )

    return {
        "schema_version": "portfolio-operacional-curado-v1",
        "metadata": {
            "decision_source": "feedback_portfolio.json",
            "human_curated": True,
            "automatic_candidate_source": "pipeline_data/05_portfolio_recommendation.json",
            "classification_source": (
                "pipeline_data/07_classificados_final.json"
                if classifications is not None
                else None
            ),
            "classification_status": (
                "complete" if classifications is not None else "not_materialized"
            ),
            "total_classificados": (
                len(classifications) if classifications is not None else None
            ),
            "base_portfolio": (
                analytical_base if classifications is not None else None
            ),
        },
        "portfolio_final": categories,
        "diretrizes": feedback.get("diretrizes", []),
        "fora_do_catalogo": feedback.get("fora_do_catalogo", []),
        "encaminhamentos": feedback.get("encaminhamentos", []),
    }


def validate_reference(feedback: dict, contract: dict, reference: dict) -> None:
    generated = build_reference(feedback, contract)
    if semantic_view(generated) != semantic_view(reference):
        raise CurationError(
            "portfolio_referencia.json diverge da projecao deterministica da curadoria"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feedback", type=Path, default=DEFAULT_FEEDBACK)
    parser.add_argument("--reference", type=Path, default=DEFAULT_REFERENCE)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--write-operational", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--classifications", type=Path)
    args = parser.parse_args(argv)

    try:
        feedback = _load(args.feedback)
        contract = _load(args.contract)
        reference = _load(args.reference)
        validate_reference(feedback, contract, reference)
        classifications = None
        if args.classifications:
            classifications = _load(args.classifications)
        elif DEFAULT_CLASSIFICATIONS.is_file():
            classifications = _load(DEFAULT_CLASSIFICATIONS)
        if args.write_operational:
            _write(args.output, build_operational(feedback, classifications))
        result = {
            "status": "PASS",
            "feedback": str(args.feedback),
            "feedback_sha256": _sha(args.feedback),
            "reference": str(args.reference),
            "reference_sha256": _sha(args.reference),
            "analytical_categories": len(reference["categorias_analiticas"]),
            "fixed_outside_analysis": len(reference["itens_fixos_fora_analise"]),
            "operational_written": bool(args.write_operational),
            "classification_used": classifications is not None,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, CurationError) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
