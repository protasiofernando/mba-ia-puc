#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Guardas de linhagem e justica do experimento de comparacao."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path


VERSION = "comparison-validator-v2"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows06(path: Path) -> list:
    data = _load(path)
    if isinstance(data, list):
        return data
    for name in ("classificados", "classificacoes"):
        if isinstance(data.get(name), list):
            return data[name]
    return []


def _telemetry_stage_coverage(path: Path) -> dict[str, bool]:
    labels = set()
    if path.exists():
        with path.open(
            "r", encoding="utf-8", errors="replace", newline=""
        ) as handle:
            for row in csv.DictReader(handle):
                try:
                    status = int(row.get("status") or 0)
                except ValueError:
                    continue
                if status == 0:
                    labels.add(
                        str(row.get("stage") or "")
                        .casefold()
                        .replace("_", "")
                    )
    return {
        f"stage{stage}": any(
            label.startswith(f"stage{stage}") for label in labels
        )
        for stage in range(3, 7)
    }


def _call_telemetry_stage_coverage(path: Path) -> dict[str, bool]:
    covered = {f"stage{stage}": False for stage in range(3, 7)}
    if not path.exists():
        return covered
    for line in path.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            row = json.loads(line)
        except (TypeError, json.JSONDecodeError):
            continue
        label = str(row.get("stage") or "").casefold().replace("_", "")
        valid = (
            bool(str(row.get("model") or "").strip())
            and bool(str(row.get("kind") or "").strip())
            and isinstance(row.get("elapsed_s"), (int, float))
            and float(row["elapsed_s"]) >= 0
        )
        if not valid:
            continue
        for stage in covered:
            if label.startswith(stage):
                covered[stage] = True
    return covered


def _gpu_telemetry_stage_coverage(
    gpu_path: Path,
    time_path: Path,
) -> dict[str, bool]:
    covered = {f"stage{stage}": False for stage in range(3, 7)}
    if not gpu_path.exists() or not time_path.exists():
        return covered
    windows = []
    with time_path.open(
        "r", encoding="utf-8", errors="replace", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            label = str(row.get("stage") or "").casefold().replace("_", "")
            stage = next(
                (
                    name for name in covered
                    if label.startswith(name)
                ),
                None,
            )
            if stage is None:
                continue
            try:
                status = int(row.get("status") or 0)
                start = float(row.get("inicio_epoch") or "")
                finish = float(row.get("fim_epoch") or "")
            except (TypeError, ValueError):
                continue
            if status == 0 and finish >= start:
                windows.append((stage, start, finish))
    if not windows:
        return covered
    with gpu_path.open(
        "r", encoding="utf-8", errors="replace", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            try:
                epoch = float(row.get("epoch") or "")
                float(row.get("gpu_util_pct") or "")
                float(row.get("mem_used_mib") or "")
                float(row.get("mem_total_mib") or "")
                float(row.get("power_w") or "")
            except (TypeError, ValueError):
                continue
            for stage, start, finish in windows:
                if start <= epoch <= finish:
                    covered[stage] = True
    return covered


def _portfolio_shared_view(target: dict, feedback: dict) -> dict:
    analytic_rows = list(target.get("categorias_analiticas") or [])
    fixed_rows = list(target.get("itens_fixos_fora_analise") or [])
    target_rows = analytic_rows + fixed_rows
    feedback_rows = list(feedback.get("portfolio_final") or [])
    group_names = {
        str(row.get("id")): row.get("nome")
        for row in (target.get("grupos_analiticos") or [])
    }
    analytic_ids = {str(row.get("id")) for row in analytic_rows}
    fields = (
        "id",
        "nome",
        "descricao",
        "quando_usar",
        "informacoes_obrigatorias",
        "nota_campos",
    )

    def normalize_target(rows: list[dict]) -> dict:
        output = {}
        for row in rows:
            row_id = str(row.get("id"))
            item = {
                field: row.get(field)
                for field in fields
                if field in row
            }
            if row_id in analytic_ids:
                item["grupo"] = group_names.get(str(row.get("grupo_id")))
            output[row_id] = item
        return output

    def normalize_feedback(rows: list[dict]) -> dict:
        output = {}
        for row in rows:
            row_id = str(row.get("id"))
            item = {
                field: row.get(field)
                for field in fields
                if field in row
            }
            if row_id in analytic_ids:
                item["grupo"] = row.get("grupo")
            output[row_id] = item
        return output

    return {
        "target": normalize_target(target_rows),
        "feedback": normalize_feedback(feedback_rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument(
        "--phase",
        choices=("setup", "results"),
        default="setup",
    )
    parser.add_argument(
        "--require-final-report",
        action="store_true",
        help=(
            "No phase results, exige o relatório agregado e aplica todos os "
            "gates finais. Use somente depois do avaliador."
        ),
    )
    args = parser.parse_args()
    if args.require_final_report and args.phase != "results":
        parser.error("--require-final-report exige --phase results")
    base = Path(args.base).resolve()
    config = _load(base / "experimento_config.json")
    target = _load(base / "portfolio_referencia.json")
    feedback = _load(base / "feedback_portfolio.json")
    scope = _load(base / "referencia" / "01_scope_mask.json")
    manifest = _load(base / "manifesto_insumo_comum.json")
    analytic_path = base / "referencia" / "02_summaries_escopo.json"
    analytic = _load(analytic_path)
    analytic_keys = [str(row.get("chave", "")) for row in analytic]
    included = scope.get("incluidos") or []
    checks = []

    def check(name: str, condition: bool, detail: str = ""):
        checks.append({
            "check": name,
            "status": "PASS" if condition else "FAIL",
            "detail": detail,
        })

    package_manifest_path = base / "MANIFESTO_PACOTE.json"
    check("package_manifest_exists", package_manifest_path.exists())
    if package_manifest_path.exists():
        package_manifest = _load(package_manifest_path)
        for relative, expected in (
            package_manifest.get("files") or {}
        ).items():
            packaged_path = base / relative
            check(
                f"package_file:{relative}",
                packaged_path.is_file()
                and _sha(packaged_path) == expected.get("sha256"),
            )

    fixed = target.get("itens_fixos_fora_analise") or []
    portfolio_views = _portfolio_shared_view(target, feedback)
    check(
        "comparison_target_matches_operational_feedback",
        portfolio_views["target"] == portfolio_views["feedback"],
    )
    sala = next((row for row in fixed if row.get("id") == "sala_sigilo"), {})
    check("sala_exists_as_fixed_item", bool(sala))
    check("sala_immutable", sala.get("imutavel") is True)
    check("sala_not_in_discovery", sala.get("participa_descoberta") is False)
    check("sala_not_in_metrics", sala.get("participa_metricas") is False)
    check("sala_visible_in_portal", sala.get("visivel_no_portal_dti_pesquisa") is True)
    check("scope_matches_filtered_input", analytic_keys == included)
    check(
        "analytic_sha_matches_manifest",
        _sha(analytic_path) == manifest.get("analytic_input_sha256"),
    )
    reference_path = base / "referencia" / "06_referencia_consenso.json"
    reference = _load(reference_path)
    reference_metadata = reference.get("metadata") or {}
    check(
        "reference_matches_analytic_sha",
        reference_metadata.get("analytic_source_fingerprint")
        == _sha(analytic_path),
    )
    check(
        "reference_matches_scope",
        reference_metadata.get("scope_fingerprint")
        == scope.get("metadata", {}).get("scope_fingerprint"),
    )
    check(
        "reference_matches_portfolio",
        reference_metadata.get("portfolio_fingerprint")
        == _sha(base / "portfolio_referencia.json"),
    )
    check(
        "reference_models_receive_only_opaque_ids",
        reference_metadata.get("jira_key_exposed_to_reference_models")
        is False
        and reference_metadata.get("roundtrip_identifier_policy")
        == "sha256-domain-separated-128-v1"
        and scope.get("metadata", {}).get(
            "jira_key_exposed_to_reference_models"
        )
        is False
        and scope.get("metadata", {}).get("roundtrip_identifier_policy")
        == "sha256-domain-separated-128-v1",
    )
    check(
        "reference_models_match_config",
        reference_metadata.get("modelos", {}).get("a")
        == config.get("models", {}).get("reasoning")
        and reference_metadata.get("modelos", {}).get("b")
        == config.get("models", {}).get("structured_json"),
    )
    rules = _load(base / "decision_rules_v1.json")
    protected_target_ids = {
        str(row.get("id"))
        for row in (target.get("categorias_analiticas") or [])
        if row.get("protecao_decisao") is True
    }
    check(
        "strategic_guard_matches_target_flags",
        set(rules.get("strategic_service_ids") or [])
        == protected_target_ids,
    )
    check(
        "reference_and_strategic_gates_preregistered",
        (rules.get("reference_robustness") or {}).get("primary_view")
        == "consensus_full"
        and int(rules.get("minimum_strategic_service_support", 0)) == 5
        and sorted(
            float(value)
            for value in (
                rules.get("descriptive_margin_sensitivity") or []
            )
        )
        == [0.02, 0.05],
    )
    scope_rules = rules.get("scope_mask") or {}
    scope_metadata = scope.get("metadata") or {}
    check(
        "scope_is_deterministic_and_preregistered",
        scope_metadata.get("scope_method")
        == "deterministic_structured_request_type_prefilter"
        and scope_metadata.get("llm_used_for_scope") is False
        and scope_metadata.get("free_text_used_for_scope") is False
        and scope_rules.get("policy")
        == "deterministic_structured_request_type_prefilter_before_stage1"
        and scope_rules.get("llm_used_for_scope") is False
        and scope_rules.get("free_text_used_for_scope") is False,
    )
    check(
        "scope_has_no_second_filter_inside_analysis",
        not (scope.get("exclusoes") or [])
        and not (scope.get("indeterminados") or [])
        and int(scope_metadata.get("n_incluidos", -1)) == len(analytic_keys)
        and int(scope_metadata.get("n_sala_sigilo", -1)) == 0
        and int(scope_metadata.get("n_indeterminados", -1)) == 0
        and int(scope_rules.get("analysis_exclusions", -1)) == 0
        and int(scope_rules.get("analysis_indeterminate", -1)) == 0,
    )
    filter_manifest_path = base / str(scope_rules.get("manifest", ""))
    filter_manifest = (
        _load(filter_manifest_path) if filter_manifest_path.is_file() else {}
    )
    check(
        "upstream_scope_manifest_matches_preregistration",
        filter_manifest_path.is_file()
        and scope_metadata.get("filter_manifest_fingerprint")
        == _sha(filter_manifest_path)
        and int(filter_manifest.get("totals", {}).get("rows_before", -1))
        == int(scope_rules.get("rows_before", -2))
        and int(
            filter_manifest.get("totals", {}).get(
                "rows_removed_before_stage1", -1
            )
        )
        == int(scope_rules.get("rows_removed_before_stage1", -2))
        and int(filter_manifest.get("totals", {}).get("rows_after", -1))
        == int(scope_rules.get("rows_after", -2))
        and int(scope_metadata.get("n_sala_removed_upstream_before_stage1", -1))
        == int(scope_rules.get("rows_removed_before_stage1", -2)),
    )
    check(
        "raw_source_matches_scope",
        scope.get("metadata", {}).get("source_fingerprint")
        == _sha(base / config["input"]["source_relpath"]),
    )
    check(
        "analytic_input_is_byte_identical_to_prefiltered_stage2",
        _sha(analytic_path)
        == _sha(base / config["input"]["source_relpath"]),
    )
    raw_source_path = base / config["input"]["source_relpath"]
    raw_source = _load(raw_source_path)
    raw_required_fields = config["input"].get("required_fields") or []
    check(
        "raw_source_matches_preregistered_identity",
        _sha(raw_source_path)
        == str(config["input"].get("expected_sha256", "")).lower()
        and isinstance(raw_source, list)
        and len(raw_source) == int(config["input"].get("expected_count", 0))
        and all(
            isinstance(row, dict)
            and all(field in row for field in raw_required_fields)
            for row in raw_source
        ),
    )
    check(
        "manifest_matches_reference",
        manifest.get("reference_fingerprint")
        == reference_metadata.get("reference_fingerprint"),
    )
    check(
        "no_empty_or_duplicate_keys",
        all(analytic_keys) and len(analytic_keys) == len(set(analytic_keys)),
    )
    excluded = {
        str(row.get("chave", ""))
        for row in (scope.get("exclusoes") or []) + (scope.get("indeterminados") or [])
    }
    check("excluded_keys_absent_from_analytic_input", not (excluded & set(analytic_keys)))

    # O pacote de comparacao tem uma copia sanitizada do contexto. A unica
    # mencao permitida a Sala fica no alvo/ref, nunca nos prompts dos metodos.
    common_config = base / "common" / "config_portfolio.json"
    common_catalog = base / "common" / "contexto_catalogo.md"
    if common_config.exists():
        text = common_config.read_text(encoding="utf-8-sig").casefold()
        check("common_config_has_no_sala", "sala de sigilo" not in text)
    else:
        check("common_config_exists", False)
    if common_catalog.exists():
        text = common_catalog.read_text(encoding="utf-8-sig").casefold()
        check("common_catalog_has_no_sala", "sala de sigilo" not in text)
    else:
        check("common_catalog_exists", False)
    legacy_root = Path(config["native_m1"]["pipeline_data"]).parent
    legacy_config = base / legacy_root / "config_portfolio.json"
    if legacy_config.exists():
        text = legacy_config.read_text(encoding="utf-8-sig").casefold()
        check("legacy_config_has_no_sala", "sala de sigilo" not in text)
    else:
        check("legacy_config_exists", False)
    method_code_paths = [
        base / "common" / "scripts" / name
        for name in (
            "run_stage3_llm.py",
            "run_stage3_kmeans_fair.py",
            "normalizar_stage3_comum.py",
            "run_stage4_llm.py",
            "run_stage5_llm.py",
            "run_stage6_llm.py",
        )
    ] + list((base / legacy_root / "pipeline").glob("*.py"))
    forbidden_scope_terms = (
        "sala de sigilo",
        "sala_sigilo",
        "sala sigilo",
    )
    for path in method_code_paths:
        text = (
            path.read_text(encoding="utf-8-sig").casefold()
            if path.exists() else ""
        )
        check(
            f"method_code_has_no_sala:{path.relative_to(base)}",
            path.exists()
            and not any(term in text for term in forbidden_scope_terms),
        )

    environment_lock = base / "AMBIENTE_CONGELADO.json"
    check("environment_lock_exists", environment_lock.exists())
    frozen_environment = _load(environment_lock) if environment_lock.exists() else {}
    pip_freeze_copy = base / "requirements_frozen_hpc.txt"
    numpy_config_copy = base / "NUMPY_BLAS_CONFIG_HPC.txt"
    check(
        "published_pip_freeze_matches_environment",
        pip_freeze_copy.exists()
        and _sha(pip_freeze_copy)
        == frozen_environment.get("pip_freeze_sha256"),
    )
    check(
        "published_numpy_blas_matches_environment",
        numpy_config_copy.exists()
        and _sha(numpy_config_copy)
        == frozen_environment.get("numpy_blas_config_sha256"),
    )
    check(
        "reference_model_digests_match_frozen",
        reference_metadata.get("model_digests", {}).get("a")
        == frozen_environment.get("models", {})
        .get("reasoning", {})
        .get("digest")
        and reference_metadata.get("model_digests", {}).get("b")
        == frozen_environment.get("models", {})
        .get("structured_json", {})
        .get("digest"),
    )

    destinations = []
    if config.get("native_m1"):
        destinations.append(config["native_m1"])
    destinations.extend(config.get("runs") or [])
    required_results = set(config.get("comparisons", {}).get("operational", []))
    required_results.update(
        config.get("comparisons", {}).get("fair_ablation_primary", [])
    )
    for repeat_ids in (
        config.get("comparisons", {})
        .get("fair_ablation_repeats", {})
        .values()
    ):
        required_results.update(repeat_ids)
    common_source_fingerprints = {"llm": [], "kmeans": []}
    expected_models = config.get("models") or {}
    for run in destinations:
        run_id = str(run["id"])
        pd = base / run["pipeline_data"]
        input_path = pd / "02_summaries.json"
        check(f"{run_id}:input_exists", input_path.exists())
        if not input_path.exists():
            continue
        check(
            f"{run_id}:same_input_hash",
            _sha(input_path) == manifest.get("analytic_input_sha256"),
        )
        rows = _load(input_path)
        keys = [str(row.get("chave", "")) for row in rows]
        check(f"{run_id}:same_key_order", keys == analytic_keys)
        check(f"{run_id}:excluded_keys_absent", not (excluded & set(keys)))

        if args.phase != "results":
            continue
        stage3_path = pd / "03_clusters.json"
        stage4_path = pd / "04_labels.json"
        stage5_path = pd / "05_portfolio_recommendation.json"
        stage6_path = pd / "06_classificados.json"
        output_paths = (stage3_path, stage4_path, stage5_path, stage6_path)
        if (
            run_id not in required_results
            and not any(path.exists() for path in output_paths)
        ):
            checks.append({
                "check": f"{run_id}:optional_repeat",
                "status": "PASS",
                "detail": "replica opcional ainda nao executada",
            })
            continue
        environment_path = pd / "_environment_verification.json"
        check(f"{run_id}:environment_verified", environment_path.exists())
        if environment_path.exists():
            environment = _load(environment_path)
            check(
                f"{run_id}:environment_matches_frozen",
                environment.get("status") == "PASS"
                and environment.get("mode") == "verify"
                and environment.get("run_id") == run_id
                and environment.get("snapshot") == frozen_environment,
            )
        telemetry_coverage = _telemetry_stage_coverage(
            pd / "_metrics_tempo.csv"
        )
        check(
            f"{run_id}:telemetry_stages_3_6",
            all(telemetry_coverage.values()),
            json.dumps(telemetry_coverage, ensure_ascii=False),
        )
        call_coverage = _call_telemetry_stage_coverage(
            pd / "_metrics_tokens.jsonl"
        )
        gpu_coverage = _gpu_telemetry_stage_coverage(
            pd / "_metrics_gpu.csv",
            pd / "_metrics_tempo.csv",
        )
        check(
            f"{run_id}:telemetry_calls_stages_3_6",
            all(call_coverage.values()),
            json.dumps(call_coverage, ensure_ascii=False),
        )
        check(
            f"{run_id}:telemetry_gpu_samples_each_stage_3_6",
            all(gpu_coverage.values()),
            json.dumps(gpu_coverage, ensure_ascii=False),
        )
        check(f"{run_id}:stage3_exists", stage3_path.exists())
        check(f"{run_id}:stage4_exists", stage4_path.exists())
        check(f"{run_id}:stage5_exists", stage5_path.exists())
        check(f"{run_id}:stage6_exists", stage6_path.exists())
        if not all(path.exists() for path in output_paths):
            continue
        stage3 = _load(stage3_path)
        stage3_keys = [
            str(row.get("chave", "")) for row in stage3.get("tickets") or []
        ]
        stage6_rows = _rows06(stage6_path)
        stage6_keys = [str(row.get("chave", "")) for row in stage6_rows]
        check(
            f"{run_id}:stage3_complete",
            len(stage3_keys) == len(set(stage3_keys)) == len(analytic_keys)
            and set(stage3_keys) == set(analytic_keys),
        )
        check(
            f"{run_id}:stage6_complete",
            len(stage6_keys) == len(set(stage6_keys)) == len(analytic_keys)
            and set(stage6_keys) == set(analytic_keys),
        )
        check(
            f"{run_id}:stage6_no_pending",
            all(
                (row.get("categoria_id") or row.get("categoria_nova"))
                and not row.get("_pendente")
                for row in stage6_rows
            ),
        )
        raw = stage3
        if run.get("common_interface"):
            metadata = stage3.get("metadata") or {}
            check(
                f"{run_id}:common_interface",
                metadata.get("common_interface_version")
                == "stage3-common-interface-v2",
            )
            check(
                f"{run_id}:definitions_stripped",
                stage3.get("_definicoes") == []
                and metadata.get("definitions_stripped") is True,
            )
            raw_path = pd / "03_clusters_raw.json"
            check(f"{run_id}:raw_stage3_exists", raw_path.exists())
            raw = _load(raw_path) if raw_path.exists() else {}
            check(
                f"{run_id}:legacy_fields_removed",
                all(
                    "tipo_atual" not in row and "contexto" not in row
                    for row in stage3.get("tickets") or []
                )
                and all(
                    "distribuicao_categorias_atuais" not in row
                    for row in stage3.get("cluster_stats") or []
                ),
            )
        raw_metadata = raw.get("metadata") or {}
        if "seed" in run:
            check(
                f"{run_id}:declared_seed_matches_output",
                int(raw_metadata.get("random_seed", -1))
                == int(run["seed"]),
            )
        discovery = run.get("discovery")
        if discovery == "kmeans":
            fields = raw_metadata.get("campos_embedding")
            selection = raw_metadata.get("k_selection") or {}
            check(
                f"{run_id}:common_discovery_fields",
                fields == ["intencao", "tema", "tipo_pedido"],
            )
            check(
                f"{run_id}:embedding_model",
                raw_metadata.get("embedding_model")
                == expected_models.get("embedding"),
            )
            check(
                f"{run_id}:embedding_digest",
                raw_metadata.get("embedding_model_digest")
                == frozen_environment.get("models", {})
                .get("embedding", {})
                .get("digest"),
            )
            check(
                f"{run_id}:kmeans_preregistered_parameters",
                selection.get("forcado") is False
                and selection.get("faixa_pre_registrada") == [4, 30]
                and int(selection.get("n_init", 0)) == 20
                and int(selection.get("max_iter", 0)) == 500
                and int(selection.get("silhueta_n", 0)) == len(analytic_keys)
                and selection.get("usa_amostra") is False
                and int(raw_metadata.get("embedding_batch_size", 0)) == 32
                and int(raw_metadata.get("embedding_retries", 0)) == 5,
            )
        elif discovery == "llm":
            def _bare(m):
                return m[7:] if isinstance(m, str) and m.startswith("ollama:") else m
            check(
                f"{run_id}:llm_discovery_model",
                _bare(raw_metadata.get("discovery_model"))
                == _bare(expected_models.get("reasoning")),
            )
            check(
                f"{run_id}:llm_json_model",
                _bare(raw_metadata.get("json_model"))
                == _bare(expected_models.get("structured_json")),
            )
            check(
                f"{run_id}:common_discovery_contract",
                raw_metadata.get("discovery_contract_version")
                == "discovery-common-fields-v2"
                and raw_metadata.get("discovery_fields")
                == ["intencao", "tema", "tipo_pedido"],
            )
            check(
                f"{run_id}:jira_key_not_exposed_to_llm",
                raw_metadata.get("jira_key_exposed_to_llm") is False
                and raw_metadata.get("roundtrip_identifier_policy")
                == "sha256-domain-separated-128-v1",
            )
        elif discovery == "kmeans_legacy":
            check(
                f"{run_id}:legacy_embedding_model",
                stage3.get("embedding_model")
                == expected_models.get("embedding"),
            )
        if run.get("common_interface") and discovery in common_source_fingerprints:
            common_source_fingerprints[discovery].append(
                raw_metadata.get("source_fingerprint")
            )

    if args.phase == "results":
        for discovery, fingerprints in common_source_fingerprints.items():
            nonempty = [value for value in fingerprints if value]
            check(
                f"common_{discovery}:source_fingerprint_stable",
                len(nonempty) == len(fingerprints)
                and len(set(nonempty)) <= 1,
            )
        final_report_path = (
            base
            / "avaliacao"
            / "RESULTADO_COMPARACAO_ROBUSTA.metrics.json"
        )
        check(
            "final_report_exists_when_required",
            final_report_path.exists() or not args.require_final_report,
        )
        if final_report_path.exists():
            final_report = _load(final_report_path)
            fair = final_report.get("fair_ablation_conclusion") or {}
            strategic_grid = (
                fair.get("strategic_service_protection_grid") or {}
            )
            check(
                "final_report_has_all_three_replicates",
                fair.get("three_replicates_complete") is True,
            )
            check(
                "final_report_has_complete_seed_reference_layer_cube",
                fair.get("seed_reference_layer_cube_complete") is True,
            )
            check(
                "final_report_strategic_grid_has_all_cells",
                strategic_grid.get("evaluated_cells") == 12
                and strategic_grid.get(
                    "expected_cells_for_strong_claim"
                )
                == 12,
            )
            check(
                "final_report_is_not_provisional_for_missing_replicates",
                fair.get("strength")
                != "provisoria_sem_tres_replicas",
            )

    failures = [row for row in checks if row["status"] == "FAIL"]
    report = {
        "version": VERSION,
        "phase": args.phase,
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": len(failures),
    }
    out = base / "avaliacao" / f"VALIDACAO_{args.phase.upper()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
