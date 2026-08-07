#!/usr/bin/env python3
"""Valida integridade, linhagem e sinais de qualidade dos Stages 5 e 6."""
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

from projeto import config_path, pipeline_data_dir


DECISOES_OUTLIER = {
    "incorporar_portfolio",
    "fundir_em_chamado",
    "manter_revisao",
    "desconsiderar_portfolio",
}
STAGE5_PIPELINE_VERSION = "stage5-operational-reconciliation-v6.1"
CATEGORY_MAPPING_VERSION = "closed-destination-stage4-evidence-v3"
STATUS_RECONCILIACAO = {
    "manter_separado",
    "fundir",
    "dividir_para_revisao",
    "obrigatorio",
}
CRITERIOS_RECONCILIACAO = {
    "mesmo_objetivo_usuario",
    "mesmo_servico_sistema",
    "mesmo_tratamento",
    "mesmo_fluxo_responsavel",
    "mesmos_dados_aprovacoes",
    "mesmos_sla_seguranca",
}
PERFIL_OPERACIONAL = {
    "objetivo_usuario",
    "servico_sistema_alvo",
    "acao_tratamento",
    "fluxo_responsavel",
    "dados_aprovacoes",
    "requisitos_seguranca",
}


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().split())


def _mandatory_names() -> list[str]:
    if not config_path().exists():
        return []
    config = _load_json(config_path())
    output = []
    for item in config.get("categorias_obrigatorias", []):
        name = item.get("nome", "") if isinstance(item, dict) else item
        name = str(name).strip()
        if name:
            output.append(name)
    return output


def _validate_stage5(base: Path, errors: list[str], warnings: list[str]):
    p05 = base / "05_portfolio_recommendation.json"
    p04 = base / "04_labels.json"
    if not p05.exists():
        errors.append(f"arquivo nao encontrado: {p05}")
        return None, None, None

    data = _load_json(p05)
    metadata = data.get("metadata", {})
    recommendation = data.get("recomendacao", {})
    portfolio = recommendation.get("portfolio_otimizado", [])
    groups = recommendation.get("grupos_otimizados", [])
    revision = recommendation.get("revisao_contexto_catalogo")
    outliers = data.get("outliers_stage3", [])
    outlier_evaluation = recommendation.get("avaliacao_outliers_stage3", [])

    if metadata.get("pipeline_version") != STAGE5_PIPELINE_VERSION:
        errors.append(
            "Stage 5 nao foi gerado pelo pipeline vigente "
            f"{STAGE5_PIPELINE_VERSION}."
        )
    if metadata.get("category_mapping_version") != CATEGORY_MAPPING_VERSION:
        errors.append(
            "Stage 5 nao usa o contrato vigente de mapeamento deterministico "
            f"{CATEGORY_MAPPING_VERSION}."
        )
    if not metadata.get("portfolio_fingerprint"):
        errors.append("Stage 5 sem metadata.portfolio_fingerprint.")
    if not isinstance(revision, dict) or revision.get("contexto_lido") is not True:
        errors.append("revisao_contexto_catalogo.contexto_lido deve ser true.")
    elif not revision.get("agrupadores_atuais_considerados"):
        errors.append("revisao do catalogo nao lista agrupadores atuais considerados.")

    if not isinstance(portfolio, list) or not portfolio:
        errors.append("portfolio_otimizado deve conter chamados.")
        portfolio = portfolio if isinstance(portfolio, list) else []
    if not isinstance(groups, list) or not groups:
        errors.append("grupos_otimizados esta vazio ou invalido.")
        groups = groups if isinstance(groups, list) else []

    names_seen = {}
    ids_seen = {}
    items_by_group: dict[str, list[str]] = defaultdict(list)
    category_owners: dict[str, list[str]] = defaultdict(list)
    natural_owners: dict[str, list[str]] = defaultdict(list)
    outlier_owners: dict[str, list[str]] = defaultdict(list)
    for item in portfolio:
        if not isinstance(item, dict):
            errors.append("portfolio_otimizado contem item nao objeto.")
            continue
        name = str(item.get("nome", "")).strip()
        group = str(item.get("grupo", "")).strip()
        category_id = str(item.get("id", "")).strip()
        if not name:
            errors.append("item do portfolio sem nome.")
            continue
        if not group:
            errors.append(f"item '{name}' sem grupo.")
        if not category_id:
            errors.append(f"item '{name}' sem id.")
        profile = item.get("perfil_operacional")
        if not isinstance(profile, dict):
            errors.append(f"item '{name}' sem perfil_operacional.")
        else:
            missing_profile = sorted(
                field for field in PERFIL_OPERACIONAL
                if not str(profile.get(field, "")).strip()
            )
            if missing_profile:
                errors.append(
                    f"item '{name}' com perfil_operacional incompleto: "
                    + ", ".join(missing_profile)
                )
        status = str(item.get("status_reconciliacao", "")).strip()
        if status not in STATUS_RECONCILIACAO:
            errors.append(
                f"item '{name}' com status_reconciliacao invalido: "
                f"{status or '(vazio)'}."
            )
        if not str(item.get("justificativa_reconciliacao", "")).strip():
            errors.append(f"item '{name}' sem justificativa_reconciliacao.")
        normalized = _norm(name)
        if normalized in names_seen:
            errors.append(f"chamado duplicado: '{names_seen[normalized]}' e '{name}'.")
        names_seen[normalized] = name
        if category_id in ids_seen:
            errors.append(f"category_id duplicado: {category_id}.")
        ids_seen[category_id] = name
        items_by_group[group].append(name)
        for category in item.get("substitui_categorias_atuais", []) or []:
            category_owners[str(category)].append(name)
        for natural in item.get("baseado_nos_grupos", []) or []:
            natural_owners[str(natural)].append(name)
        for outlier_id in item.get("baseado_nos_outliers", []) or []:
            outlier_owners[str(outlier_id)].append(name)

    declared_groups = {}
    for group in groups:
        if not isinstance(group, dict):
            errors.append("grupos_otimizados contem item nao objeto.")
            continue
        name = str(group.get("nome", "")).strip()
        if not name:
            errors.append("grupo otimizado sem nome.")
            continue
        if name in declared_groups:
            errors.append(f"grupo otimizado duplicado: {name}.")
        declared_groups[name] = group

    if set(items_by_group) != set(declared_groups):
        missing = sorted(set(items_by_group) - set(declared_groups))
        extra = sorted(set(declared_groups) - set(items_by_group))
        if missing:
            errors.append("grupos usados mas nao declarados: " + ", ".join(missing))
        if extra:
            errors.append("grupos declarados sem itens: " + ", ".join(extra))
    for group, names in items_by_group.items():
        declared = declared_groups.get(group, {}).get("chamados", []) or []
        if len(declared) != len(names) or set(declared) != set(names):
            errors.append(f"lista de chamados divergente no grupo '{group}'.")

    current_categories = data.get("categorias_atuais", {})
    if not isinstance(current_categories, dict):
        errors.append("categorias_atuais deve ser um objeto.")
        current_categories = {}
    unknown_categories = sorted(set(category_owners) - set(current_categories))
    missing_categories = sorted(set(current_categories) - set(category_owners))
    duplicate_categories = {
        category: owners for category, owners in category_owners.items() if len(owners) != 1
    }
    if unknown_categories:
        errors.append("categorias atuais inventadas: " + ", ".join(unknown_categories[:12]))
    if missing_categories:
        errors.append("categorias atuais sem mapeamento: " + ", ".join(missing_categories[:12]))
    if duplicate_categories:
        errors.append(
            "categorias atuais com mais de um destino: "
            + "; ".join(
                f"{category} -> {', '.join(owners)}"
                for category, owners in list(duplicate_categories.items())[:8]
            )
        )

    natural_names = {
        str(item.get("nome", "")).strip()
        for item in data.get("grupos_naturais", [])
        if isinstance(item, dict) and item.get("nome")
    }
    unknown_naturals = sorted(set(natural_owners) - natural_names)
    missing_naturals = sorted(natural_names - set(natural_owners))
    duplicate_naturals = {
        natural: owners
        for natural, owners in natural_owners.items()
        if len(owners) != 1
    }
    if unknown_naturals:
        errors.append("grupos naturais inventados: " + ", ".join(unknown_naturals))
    if missing_naturals:
        errors.append("grupos naturais sem cobertura: " + ", ".join(missing_naturals))
    if duplicate_naturals:
        errors.append(
            "grupos naturais com mais de um destino: "
            + "; ".join(
                f"{natural} -> {', '.join(owners)}"
                for natural, owners in list(duplicate_naturals.items())[:8]
            )
        )

    for item in portfolio:
        if not isinstance(item, dict):
            continue
        name = str(item.get("nome", "")).strip()
        status = str(item.get("status_reconciliacao", "")).strip()
        owner_count = len(item.get("baseado_nos_grupos", []) or [])
        if status == "fundir" and owner_count < 2:
            errors.append(
                f"item fundido '{name}' deve cobrir ao menos dois grupos naturais."
            )
        elif status in {"manter_separado", "dividir_para_revisao"} and owner_count != 1:
            errors.append(
                f"item '{name}' com status {status} deve cobrir um grupo natural."
            )
        elif status == "obrigatorio" and owner_count:
            errors.append(
                f"item obrigatorio '{name}' nao pode ter grupo natural associado."
            )

    reconciliation = recommendation.get("reconciliacao_grupos_naturais")
    if not isinstance(reconciliation, list):
        errors.append("reconciliacao_grupos_naturais deve ser uma lista.")
        reconciliation = []
    reconciled = {}
    portfolio_by_id = {
        str(item.get("id", "")): item
        for item in portfolio if isinstance(item, dict)
    }
    for item in reconciliation:
        if not isinstance(item, dict):
            errors.append("reconciliacao_grupos_naturais contem item nao objeto.")
            continue
        natural = str(item.get("grupo_natural", "")).strip()
        if not natural or natural in reconciled:
            errors.append(
                "reconciliacao com grupo natural ausente ou repetido: "
                + (natural or "(vazio)")
            )
            continue
        decision_llm = str(item.get("decisao_llm", "")).strip()
        final_decision = str(item.get("decisao_final", "")).strip()
        destination = str(item.get("destino_id", "")).strip()
        if decision_llm not in STATUS_RECONCILIACAO - {"obrigatorio"}:
            errors.append(f"decisao_llm invalida para grupo natural '{natural}'.")
        if final_decision not in STATUS_RECONCILIACAO - {"obrigatorio"}:
            errors.append(f"decisao_final invalida para grupo natural '{natural}'.")
        target = portfolio_by_id.get(destination)
        if target is None:
            errors.append(
                f"reconciliacao de '{natural}' usa destino inexistente: {destination}."
            )
        else:
            if item.get("destino_nome") != target.get("nome"):
                errors.append(
                    f"reconciliacao de '{natural}' tem nome de destino divergente."
                )
            if final_decision != target.get("status_reconciliacao"):
                errors.append(
                    f"reconciliacao de '{natural}' diverge do status do destino."
                )
            if natural not in (target.get("baseado_nos_grupos", []) or []):
                errors.append(
                    f"reconciliacao de '{natural}' nao confere com a linhagem."
                )
        criteria = item.get("criterios")
        if not isinstance(criteria, dict) or set(criteria) != CRITERIOS_RECONCILIACAO:
            errors.append(f"criterios de reconciliacao invalidos para '{natural}'.")
        elif any(not isinstance(value, bool) for value in criteria.values()):
            errors.append(
                f"criterios de reconciliacao nao booleanos para '{natural}'."
            )
        if not str(item.get("justificativa", "")).strip():
            errors.append(f"reconciliacao de '{natural}' sem justificativa.")
        reconciled[natural] = item
    if set(reconciled) != natural_names:
        missing = sorted(natural_names - set(reconciled))
        unknown = sorted(set(reconciled) - natural_names)
        errors.append(
            "cobertura da reconciliacao divergente: "
            f"faltando={len(missing)} extras={len(unknown)}."
        )
    if metadata.get("n_request_types_reconciliados") != len(portfolio):
        errors.append(
            "metadata.n_request_types_reconciliados diverge do portfolio."
        )
    split_count = sum(
        isinstance(item, dict)
        and item.get("status_reconciliacao") == "dividir_para_revisao"
        for item in portfolio
    )
    if metadata.get("n_grupos_para_divisao") != split_count:
        errors.append("metadata.n_grupos_para_divisao diverge do portfolio.")

    if not isinstance(outliers, list):
        errors.append("outliers_stage3 deve ser uma lista.")
        outliers = []
    outlier_ids = []
    for outlier in outliers:
        if not isinstance(outlier, dict):
            errors.append("outliers_stage3 contem item nao objeto.")
            continue
        outlier_id = str(outlier.get("outlier_id", "")).strip()
        if not outlier_id:
            errors.append("outliers_stage3 contem item sem outlier_id.")
            continue
        outlier_ids.append(outlier_id)
    duplicated_source_outliers = [
        outlier_id for outlier_id, total in Counter(outlier_ids).items() if total > 1
    ]
    if duplicated_source_outliers:
        errors.append(
            "outlier_id duplicado na fonte do Stage 5: "
            + ", ".join(duplicated_source_outliers)
        )
    expected_outliers = set(outlier_ids)
    unknown_outlier_links = sorted(set(outlier_owners) - expected_outliers)
    duplicated_outlier_links = {
        outlier_id: owners
        for outlier_id, owners in outlier_owners.items()
        if len(owners) > 1
    }
    if unknown_outlier_links:
        errors.append(
            "portfolio referencia candidatos raros inexistentes: "
            + ", ".join(unknown_outlier_links)
        )
    if duplicated_outlier_links:
        errors.append(
            "candidatos raros vinculados a mais de um chamado: "
            + "; ".join(
                f"{outlier_id} -> {', '.join(owners)}"
                for outlier_id, owners in duplicated_outlier_links.items()
            )
        )

    if not isinstance(outlier_evaluation, list):
        errors.append("avaliacao_outliers_stage3 deve ser uma lista.")
        outlier_evaluation = []
    evaluated = {}
    for item in outlier_evaluation:
        if not isinstance(item, dict):
            errors.append("avaliacao_outliers_stage3 contem item nao objeto.")
            continue
        outlier_id = str(item.get("outlier_id", "")).strip()
        if not outlier_id or outlier_id in evaluated:
            errors.append(
                f"avaliacao tem outlier_id ausente ou repetido: {outlier_id or '(vazio)'}"
            )
            continue
        decision = str(item.get("decisao", "")).strip()
        destination = str(item.get("destino_portfolio", "") or "").strip() or None
        reason = str(item.get("justificativa", "")).strip()
        if decision not in DECISOES_OUTLIER:
            errors.append(f"decisao invalida para {outlier_id}: {decision}")
        if not reason:
            errors.append(f"avaliacao do candidato raro {outlier_id} sem justificativa.")
        linked = outlier_owners.get(outlier_id, [])
        if decision in {"incorporar_portfolio", "fundir_em_chamado"}:
            if destination not in names_seen.values():
                errors.append(
                    f"{outlier_id} aponta para destino_portfolio inexistente: {destination}"
                )
            if linked != [destination]:
                errors.append(
                    f"{outlier_id} nao esta vinculado somente ao destino {destination}."
                )
        elif decision in DECISOES_OUTLIER and (destination is not None or linked):
            errors.append(
                f"{outlier_id} com decisao {decision} nao pode ter destino no portfolio."
            )
        evaluated[outlier_id] = item
    missing_outlier_evaluation = sorted(expected_outliers - set(evaluated))
    unknown_outlier_evaluation = sorted(set(evaluated) - expected_outliers)
    if missing_outlier_evaluation:
        errors.append(
            "candidatos raros sem avaliacao: " + ", ".join(missing_outlier_evaluation)
        )
    if unknown_outlier_evaluation:
        errors.append(
            "avaliacao contem candidatos raros inexistentes: "
            + ", ".join(unknown_outlier_evaluation)
        )
    if metadata.get("n_outliers_stage3") != len(outlier_ids):
        errors.append("metadata.n_outliers_stage3 diverge de outliers_stage3.")

    missing_mandatory = [
        name for name in _mandatory_names() if _norm(name) not in names_seen
    ]
    if missing_mandatory:
        errors.append("categorias obrigatorias ausentes: " + ", ".join(missing_mandatory))

    mapping = recommendation.get("mapeamento_atual_vs_natural", [])
    mapped = []
    mapping_by_category = {}
    for item in mapping:
        if not isinstance(item, dict):
            errors.append("mapeamento_atual_vs_natural contem item nao objeto.")
            continue
        category = str(item.get("categoria_atual", "")).strip()
        mapped.append(category)
        if category and category not in mapping_by_category:
            mapping_by_category[category] = item
    if Counter(mapped) != Counter(current_categories.keys()):
        errors.append("mapeamento_atual_vs_natural nao cobre exatamente categorias_atuais.")
    else:
        public_naturals = [
            item for item in data.get("grupos_naturais", [])
            if isinstance(item, dict)
        ]
        for category in current_categories:
            item = mapping_by_category[category]
            destination_id = str(item.get("destino_id", "")).strip()
            destination_name = str(item.get("destino_portfolio", "")).strip()
            if destination_id not in ids_seen:
                errors.append(
                    f"mapeamento de {category} usa destino_id inexistente: "
                    f"{destination_id or '(vazio)'}."
                )
            else:
                expected_name = ids_seen[destination_id]
                if destination_name != expected_name:
                    errors.append(
                        f"mapeamento de {category} tem destino_portfolio divergente."
                    )
                if category_owners.get(category) != [expected_name]:
                    errors.append(
                        f"mapeamento de {category} diverge da linhagem do portfolio."
                    )

            expected_evidence = []
            for natural in public_naturals:
                name = str(natural.get("nome", "")).strip()
                distribution = natural.get("distribuicao_categorias_atuais", {})
                if not name or not isinstance(distribution, dict):
                    continue
                volume = int(distribution.get(category, 0) or 0)
                if volume > 0:
                    expected_evidence.append({"nome": name, "volume": volume})
            expected_evidence.sort(
                key=lambda row: (-row["volume"], _norm(row["nome"]))
            )

            observed = item.get("grupos_naturais_observados")
            actual_evidence = []
            if not isinstance(observed, list):
                errors.append(
                    f"mapeamento de {category} sem grupos_naturais_observados."
                )
                continue
            for relation in observed:
                if not isinstance(relation, dict):
                    errors.append(
                        f"mapeamento de {category} contem evidencia nao objeto."
                    )
                    continue
                name = str(relation.get("nome", "")).strip()
                try:
                    volume = int(relation.get("volume", 0))
                except (TypeError, ValueError):
                    volume = -1
                if not name or volume <= 0:
                    errors.append(
                        f"mapeamento de {category} contem evidencia invalida."
                    )
                    continue
                actual_evidence.append({"nome": name, "volume": volume})
            if actual_evidence != expected_evidence:
                errors.append(
                    f"grupos_naturais_observados de {category} divergem do Stage 4."
                )

    if p04.exists():
        labels = _load_json(p04)
        stage4_fingerprint = str(
            labels.get("metadata", {}).get("stage4_fingerprint", "")
        ).strip()
        if stage4_fingerprint and metadata.get("stage4_fingerprint") != stage4_fingerprint:
            errors.append("Stage 5 nao corresponde ao fingerprint do Stage 4 atual.")
    else:
        warnings.append("04_labels.json ausente; linhagem do Stage 5 nao foi conferida.")

    p03 = base / "03_clusters.json"
    if p03.exists():
        stage3 = _load_json(p03)
        stage3_outlier_ids = {
            str(item.get("outlier_id", "")).strip()
            for item in stage3.get("outlier_stats", [])
            if isinstance(item, dict) and str(item.get("outlier_id", "")).strip()
        }
        if stage3_outlier_ids != expected_outliers:
            errors.append("outliers_stage3 nao correspondem ao 03_clusters.json atual.")
    else:
        warnings.append("03_clusters.json ausente; candidatos raros nao foram conferidos.")

    return data, portfolio, ids_seen


def _validate_stage6(
    base: Path,
    portfolio: list[dict],
    errors: list[str],
    warnings: list[str],
):
    p06 = base / "06_classificados.json"
    p02 = base / "02_summaries.json"
    if not p06.exists():
        errors.append(f"arquivo nao encontrado: {p06}")
        return

    rows = _load_json(p06)
    if not isinstance(rows, list):
        errors.append("06_classificados.json deve ser uma lista.")
        return

    by_name = {item.get("nome"): item for item in portfolio}
    by_id = {item.get("id"): item for item in portfolio}
    keys = []
    category_counts = Counter()
    confidence_counts = Counter()
    review_count = 0
    for row in rows:
        if not isinstance(row, dict):
            errors.append("06_classificados contem item nao objeto.")
            continue
        key = str(row.get("chave", "")).strip()
        keys.append(key)
        name = row.get("categoria_nova")
        category_id = row.get("categoria_id")
        group = row.get("grupo_novo")
        expected = by_name.get(name)
        if expected is None:
            errors.append(f"classificacao {key} usa categoria inexistente: {name}")
            continue
        if category_id != expected.get("id"):
            errors.append(
                f"classificacao {key} tem categoria_id '{category_id}', "
                f"esperado '{expected.get('id')}'."
            )
        if group != expected.get("grupo"):
            errors.append(
                f"classificacao {key} tem grupo '{group}', "
                f"esperado '{expected.get('grupo')}'."
            )
        if category_id not in by_id:
            errors.append(f"classificacao {key} usa category_id inexistente: {category_id}")
        confidence = row.get("confianca")
        if confidence not in {"alta", "media", "baixa"}:
            errors.append(f"classificacao {key} tem confianca invalida: {confidence}")
        ambiguity = row.get("ambiguidade")
        if not isinstance(ambiguity, bool):
            errors.append(f"classificacao {key} tem ambiguidade nao booleana.")
        review = row.get("revisao_recomendada")
        if not isinstance(review, bool):
            errors.append(f"classificacao {key} tem revisao_recomendada nao booleana.")
        elif isinstance(ambiguity, bool) and review != (
            confidence == "baixa" or ambiguity
        ):
            errors.append(
                f"classificacao {key} tem revisao_recomendada incoerente com "
                "confianca/ambiguidade."
            )
        second_id = row.get("segunda_opcao_id")
        second_name = row.get("segunda_categoria")
        if second_id:
            second = by_id.get(second_id)
            if second is None:
                errors.append(
                    f"classificacao {key} usa segunda_opcao_id inexistente: {second_id}"
                )
            elif second_id == category_id:
                errors.append(f"classificacao {key} repete o ID na segunda opcao.")
            elif second_name != second.get("nome"):
                errors.append(
                    f"classificacao {key} tem segunda_categoria divergente do ID."
                )
        elif second_name:
            errors.append(
                f"classificacao {key} tem segunda_categoria sem segunda_opcao_id."
            )
        if row.get("fallback_aplicado"):
            errors.append(f"classificacao {key} registra fallback proibido.")
        category_counts[name] += 1
        confidence_counts[confidence] += 1
        review_count += review is True

    duplicate_keys = [key for key, total in Counter(keys).items() if key and total > 1]
    if duplicate_keys:
        errors.append("chaves duplicadas no Stage 6: " + ", ".join(duplicate_keys[:12]))
    if any(not key for key in keys):
        errors.append("Stage 6 contem registro sem chave.")

    if p02.exists():
        summaries = _load_json(p02)
        expected_keys = [str(item.get("chave", "")).strip() for item in summaries]
        missing = sorted(set(expected_keys) - set(keys))
        extra = sorted(set(keys) - set(expected_keys))
        if len(rows) != len(expected_keys) or missing or extra:
            errors.append(
                f"cobertura Stage 6 divergente: esperado={len(expected_keys)} "
                f"obtido={len(rows)} faltando={len(missing)} extras={len(extra)}."
            )
    else:
        warnings.append("02_summaries.json ausente; cobertura por chamado nao foi conferida.")

    total = len(rows)
    max_category = category_counts.most_common(1)
    if max_category and total and max_category[0][1] / total > 0.70:
        warnings.append(
            f"categoria '{max_category[0][0]}' concentra "
            f"{max_category[0][1] / total * 100:.1f}% das classificacoes."
        )
    if total and review_count / total > 0.30:
        warnings.append(
            f"{review_count / total * 100:.1f}% das classificacoes pedem revisao."
        )

    report = {
        "total_classificados": total,
        "categorias": dict(category_counts.most_common()),
        "confianca": dict(confidence_counts),
        "revisao_recomendada": review_count,
        "percentual_revisao": round(review_count / max(total, 1) * 100, 2),
        "avisos": warnings,
    }
    with open(base / "06_quality_report.json", "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(
        f"06_classificados: {total} registros, "
        f"{review_count} para revisao, {len(category_counts)} categorias usadas."
    )


def validate(stage5_only: bool = False) -> int:
    base = pipeline_data_dir()
    errors: list[str] = []
    warnings: list[str] = []
    _, portfolio, _ = _validate_stage5(base, errors, warnings)
    if not stage5_only and portfolio is not None:
        _validate_stage6(base, portfolio, errors, warnings)
    elif stage5_only:
        warnings.append("validacao restrita ao Stage 5 por opcao --stage5-only.")

    for warning in warnings:
        print(f"AVISO: {warning}")
    if errors:
        print("ERROS:")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        f"Portfolio OK: {len(portfolio or [])} chamados em "
        f"{len({item.get('grupo') for item in (portfolio or [])})} grupos logicos."
    )
    return 0


if __name__ == "__main__":
    sys.exit(validate(stage5_only="--stage5-only" in sys.argv[1:]))
