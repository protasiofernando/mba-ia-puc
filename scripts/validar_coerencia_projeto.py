#!/usr/bin/env python3
"""Audita a coerência entre história, código, alvos e resultados do projeto.

O gate é somente leitura. Ele não executa modelos, não acessa os CSVs privados,
não cria pacote e não faz qualquer operação Git.
"""

from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
STAGE2_SHA = "e4fb8e41c910f8f2ed6151d8e69515ae8fd1b01f1310d47fa680d4403fd54ff1"
EXECUTED_FEEDBACK_SHA = "7ffa42771809063994c2f37417306f264debbab137930a859520371bb6235f47"
CANONICAL_FEEDBACK_SHA = "0c18066c95f3e68a3825b0a566cc1b8568b532e032566e4aa5d7b6b39d2cd409"
REFERENCE_SHA = "5539b14497c851d3abc8a8356ef86a92318e811ee558c71bac3d53f5d0ca0d8b"
EXPECTED_RUNS = {
    "m1_legacy_llama",
    "m2_native",
    "kmeans_common_seed42",
    "llm_common_seed42",
    "kmeans_common_seed31415",
    "llm_common_seed31415",
    "kmeans_common_seed27182",
    "llm_common_seed27182",
}


def _json(relative: str):
    return json.loads((ROOT / relative).read_text(encoding="utf-8-sig"))


def _text(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def _sha(relative: str) -> str:
    return hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()


def _decision_view(value):
    """Remove metadados editoriais que não entram na projeção analítica."""
    enrichment = {"justificativa_consolidacao", "substitui_categorias_atuais"}
    if isinstance(value, dict):
        return {
            key: _decision_view(item)
            for key, item in value.items()
            if not key.startswith("_") and key not in enrichment
        }
    if isinstance(value, list):
        return [_decision_view(item) for item in value]
    return value


class Audit:
    def __init__(self) -> None:
        self.checks: list[dict[str, str]] = []
        self.warnings: list[str] = []

    def check(self, name: str, condition: bool, detail: str = "") -> None:
        self.checks.append(
            {"check": name, "status": "PASS" if condition else "FAIL", "detail": detail}
        )

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def report(self) -> dict:
        failures = [row for row in self.checks if row["status"] == "FAIL"]
        return {
            "status": "PASS" if not failures else "FAIL",
            "checks": len(self.checks),
            "failures": len(failures),
            "warnings": self.warnings,
            "details": self.checks,
            "git_operation_performed": False,
        }


def _check_scope(audit: Audit) -> None:
    scope = _json("estudo_comparativo/filtro_sala_sigilo_manifest_v6.json")
    totals = scope.get("totals", {})
    audit.check("scope.rows_before", totals.get("rows_before") == 1584)
    audit.check("scope.rows_removed", totals.get("rows_removed_before_stage1") == 128)
    audit.check("scope.rows_after", totals.get("rows_after") == 1456)
    audit.check(
        "scope.arithmetic",
        totals.get("rows_before", 0) - totals.get("rows_removed_before_stage1", 0)
        == totals.get("rows_after"),
    )
    audit.check(
        "scope.deterministic_structured_field",
        scope.get("decision_field") == "Customer Request Type"
        and scope.get("matching_policy") == "exact_trimmed_case_sensitive"
        and "Nenhum texto livre" in scope.get("scope_rule", ""),
    )
    audit.check(
        "scope.public_manifest_has_no_ticket_content",
        scope.get("privacy", {}).get("contains_ticket_keys") is False
        and scope.get("privacy", {}).get("contains_ticket_text") is False,
    )
    legacy_label = "Solicitação de Acesso a Bases de Dados"
    context = _text("configuracao/contexto_catalogo.md")
    readme = _text("README.md")
    feedback = _json("formacao_portfolio/decisao_curada/feedback_portfolio.json")
    access_service = next(
        (
            row
            for row in feedback.get("portfolio_final", [])
            if row.get("id") == "acesso_bases_dados"
        ),
        {},
    )
    audit.check(
        "scope.semantic_exclusion_documented",
        legacy_label in scope.get("excluded_request_types", [])
        and f"| {legacy_label} | 128 |" in context
        and "outros seis rótulos da lista de exclusão tiveram zero ocorrências" in readme
        and "rótulo legado" in readme
        and "Não confundir com o request type antigo de mesmo nome"
        in access_service.get("justificativa_consolidacao", ""),
    )

    config = _json("estudo_comparativo/experimento_config.json")
    source = config.get("input", {})
    audit.check("input.stage2_count", source.get("expected_count") == 1456)
    audit.check("input.stage2_sha", source.get("expected_sha256") == STAGE2_SHA)
    audit.check(
        "input.scope_matches_manifest",
        source.get("rows_before_scope_filter") == 1584
        and source.get("rows_removed_before_stage1") == 128
        and source.get("llm_used_for_scope") is False,
    )
    generation = source.get("stage2_generation", {})
    audit.check(
        "input.stage2_generation_frozen",
        generation.get("contract_version") == "intent-blind-v2"
        and generation.get("model") == "llama3.3:70b"
        and generation.get("temperature") == 0.0,
    )


def _check_target_and_history(audit: Audit) -> None:
    feedback_path = "formacao_portfolio/decisao_curada/feedback_portfolio.json"
    reference_path = "formacao_portfolio/decisao_curada/portfolio_referencia.json"
    feedback = _json(feedback_path)
    reference = _json(reference_path)
    executed_feedback_bytes = base64.b64decode(
        (
            ROOT
            / "estudo_comparativo/proveniencia_execucao/feedback_portfolio_executado.json.b64"
        )
        .read_text(encoding="ascii")
        .strip(),
        validate=True,
    )
    executed_feedback = json.loads(executed_feedback_bytes.decode("utf-8-sig"))
    origin = _json("formacao_portfolio/MANIFESTO_ORIGEM.json")
    contract = _json("formacao_portfolio/contrato_curadoria.json")

    feedback_ids = [row.get("id") for row in feedback.get("portfolio_final", [])]
    analytic_ids = [row.get("id") for row in reference.get("categorias_analiticas", [])]
    fixed_ids = [row.get("id") for row in reference.get("itens_fixos_fora_analise", [])]
    audit.check(
        "target.nine_visible_unique_items",
        len(feedback_ids) == 9 and len(set(feedback_ids)) == 9,
    )
    audit.check(
        "target.canonical_metadata_is_clean",
        feedback.get("_papel") == "fonte_canonica_da_decisao_operacional"
        and "_fonte_canonica" not in feedback
        and not any(
            marker in feedback.get("_comentario", "").lower()
            for marker in ("hotfix", "rev2", "v2")
        ),
    )
    audit.check(
        "target.eight_analytic_plus_sala",
        len(analytic_ids) == 8
        and set(analytic_ids) == set(feedback_ids) - {"sala_sigilo"}
        and fixed_ids == ["sala_sigilo"],
    )
    sala = next(
        (row for row in feedback.get("portfolio_final", []) if row.get("id") == "sala_sigilo"),
        {},
    )
    audit.check(
        "target.sala_visible_fixed_outside_analysis",
        sala.get("visivel_no_portal_dti_pesquisa") is True
        and sala.get("imutavel") is True
        and sala.get("fora_da_analise") is True
        and contract.get("fixed_outside_analysis") == ["sala_sigilo"],
    )
    frozen = origin.get("frozen_experiment_inputs", {})
    canonical = origin.get("canonical_decision_document", {})
    audit.check(
        "target.frozen_hashes",
        _sha(feedback_path) == CANONICAL_FEEDBACK_SHA
        == canonical.get("sha256")
        and hashlib.sha256(executed_feedback_bytes).hexdigest()
        == EXECUTED_FEEDBACK_SHA
        == frozen.get("executed_feedback_portfolio_sha256")
        and _sha(reference_path) == REFERENCE_SHA == frozen.get("portfolio_referencia_sha256")
        and frozen.get("stage2_sha256") == STAGE2_SHA,
    )
    audit.check(
        "target.canonical_enrichment_is_analytically_neutral",
        _decision_view(feedback) == _decision_view(executed_feedback)
        and canonical.get("projects_to_frozen_reference") is True
        and canonical.get("changes_job90_result") is False
        and set(canonical.get("post_execution_enrichment_fields", []))
        == {"justificativa_consolidacao", "substitui_categorias_atuais"},
    )
    audit.check(
        "target.precedes_comparison",
        origin.get("curation", {}).get("human_decision_frozen_before_comparison") is True
        and origin.get("comparison", {}).get("starts_after_target_freeze") is True,
    )
    audit.check(
        "target.not_independent_ground_truth",
        "endogenous" in origin.get("methodological_limit", "").lower()
        and "not an independent ground truth" in origin.get("methodological_limit", "").lower(),
    )

    stage7_current = _json("pipeline_data/07_portfolio_final.json")
    stage7_rows = stage7_current.get("portfolio_final", [])
    stage7_analytical = [
        row for row in stage7_rows if not row.get("fora_da_analise")
    ]
    stage7_sala = next(
        (row for row in stage7_rows if row.get("id") == "sala_sigilo"),
        {},
    )
    audit.check(
        "stage7.current_aggregate_complete",
        stage7_current.get("metadata", {}).get("classification_status") == "complete"
        and stage7_current.get("metadata", {}).get("total_classificados") == 1456
        and stage7_current.get("metadata", {}).get("base_portfolio") == 1456
        and sum(int(row.get("volume") or 0) for row in stage7_analytical) == 1456,
    )
    audit.check(
        "stage7.current_scope_and_catalog",
        {row.get("id") for row in stage7_rows} == set(feedback_ids)
        and stage7_sala.get("fora_da_analise") is True
        and stage7_sala.get("volume") == 0,
    )

    snapshot_root = ROOT / "formacao_portfolio" / "metodo_inicial_kmeans_git_a5576c8"
    snapshot_manifest = _json(
        "formacao_portfolio/metodo_inicial_kmeans_git_a5576c8/MANIFESTO_SNAPSHOT.json"
    )
    manifest_ok = len(snapshot_manifest.get("files", {})) == 23
    for relative, expected in snapshot_manifest.get("files", {}).items():
        path = snapshot_root / relative
        manifest_ok = (
            manifest_ok
            and path.is_file()
            and path.stat().st_size == expected.get("bytes")
            and hashlib.sha256(path.read_bytes()).hexdigest() == expected.get("sha256")
        )
    audit.check("history.snapshot_23_files_exact", manifest_ok)

    candidate = _json(
        "formacao_portfolio/metodo_inicial_kmeans_git_a5576c8/"
        "pipeline_data/05_portfolio_recommendation.json"
    )
    historical_feedback = _json(
        "formacao_portfolio/metodo_inicial_kmeans_git_a5576c8/feedback_portfolio.json"
    )
    stage7 = _json(
        "formacao_portfolio/metodo_inicial_kmeans_git_a5576c8/"
        "pipeline_data/07_portfolio_final.json"
    )
    audit.check(
        "history.automatic_candidate",
        candidate.get("metadata", {}).get("total_tickets") == 1575
        and len(candidate.get("grupos_naturais", [])) == 23
        and len(candidate.get("recomendacao", {}).get("portfolio_otimizado", [])) == 10,
    )
    audit.check(
        "history.human_curation_then_stage7",
        len(historical_feedback.get("portfolio_final", [])) == 7
        and len(stage7.get("portfolio_final", [])) == 7
        and stage7.get("metadata", {}).get("total_classificados") == 1583,
    )


def _ordered(text: str, markers: list[str]) -> bool:
    positions = [text.find(marker) for marker in markers]
    return all(position >= 0 for position in positions) and positions == sorted(positions)


def _check_flow(audit: Audit) -> None:
    formation = _text("formacao_portfolio/hpc/job_formar_candidato_estatistico.sh")
    audit.check(
        "flow.formation_stages_3_to_6",
        _ordered(
            formation,
            [
                "run_stage 3",
                "run_stage 4",
                "run_stage 5",
                "run_stage 6",
                "CANDIDATO_AUTOMATICO=",
                "PROXIMO_PASSO=curadoria humana",
            ],
        ),
    )
    audit.check(
        "flow.formation_does_not_materialize_decision",
        "materializar_portfolio_curado.py" not in formation
        and "run_stage7_curadoria.py" not in formation,
    )

    stage7 = _text("scripts/hpc/job_stage7_curadoria.sh")
    audit.check(
        "flow.stage7_validates_classifies_materializes",
        _ordered(
            stage7,
            [
                "python scripts/materializar_portfolio_curado.py\n",
                "python scripts/run_stage7_curadoria.py",
                "python scripts/materializar_portfolio_curado.py \\",
            ],
        ),
    )

    job00 = _text("estudo_comparativo/hpc/job_00_referencia.sh")
    audit.check(
        "flow.job00_scope_reference_common_inputs_setup",
        _ordered(
            job00,
            [
                'run_step "deterministic_scope"',
                'run_step "reference_consensus"',
                'run_step "prepare_common_inputs"',
                'run_step "validate_setup"',
            ],
        ),
    )
    job90 = _text("estudo_comparativo/hpc/job_90_avaliacao.sh")
    audit.check(
        "flow.job90_validate_audit_evaluate_publish",
        _ordered(
            job90,
            [
                'run_step "validate_results"',
                'run_step "audit_form_fields"',
                'run_step "evaluate_methods"',
                'run_step "validate_final_report"',
                'tar -czf "$PUBLIC"',
            ],
        ),
    )

    config = _json("estudo_comparativo/experimento_config.json")
    runs = {config.get("native_m1", {}).get("id")}
    runs.update(row.get("id") for row in config.get("runs", []))
    audit.check("flow.eight_declared_arms", runs == EXPECTED_RUNS)
    audit.check(
        "flow.three_paired_seeds",
        {
            (row.get("discovery"), row.get("seed"))
            for row in config.get("runs", [])
            if row.get("family", "").startswith("ablation")
        }
        == {
            ("kmeans", 42),
            ("llm", 42),
            ("kmeans", 31415),
            ("llm", 31415),
            ("kmeans", 27182),
            ("llm", 27182),
        },
    )


def _check_results(audit: Audit) -> None:
    public_manifest = _json("resultados_publicaveis/MANIFESTO_RESULTADOS.json")
    validation = _json(
        "resultados_publicaveis/estudo_comparativo/avaliacao/VALIDACAO_RESULTS.json"
    )
    metrics = _json(
        "resultados_publicaveis/estudo_comparativo/avaliacao/"
        "RESULTADO_COMPARACAO_ROBUSTA.metrics.json"
    )
    audit.check(
        "results.job90_success",
        public_manifest.get("source_job90") == "2234.HPCGPU"
        and public_manifest.get("validation_status") == "PASS"
        and public_manifest.get("validation_checks") == 302
        and public_manifest.get("validation_failures") == 0,
    )
    audit.check(
        "results.302_checks_pass",
        validation.get("status") == "PASS"
        and validation.get("failures") == 0
        and len(validation.get("checks", [])) == 302
        and all(row.get("status") == "PASS" for row in validation.get("checks", [])),
    )
    scope = metrics.get("scope", {})
    audit.check(
        "results.scope_matches_protocol",
        scope.get("n_total_before_filter") == 1584
        and scope.get("n_sala_removed_upstream") == 128
        and scope.get("n_analiticos") == 1456
        and scope.get("llm_used_for_scope") is False,
    )
    audit.check("results.all_eight_runs", set(metrics.get("runs", {})) == EXPECTED_RUNS)
    integrated = metrics.get("integrated_conclusion", {})
    audit.check(
        "results.no_forced_global_winner",
        integrated.get("code") == "resultado_global_nao_unico"
        and integrated.get("adherence_direction_convergent") is False
        and integrated.get("portfolio_decision") == "portfolio_curado_permanece_adotado",
    )
    audit.check(
        "results.cost_separate_and_statistical",
        integrated.get("cost_synthesis_code") == "custo_convergente_estatistico"
        and integrated.get("cost_evidence_convergent") is True,
    )
    audit.check("results.no_warnings", metrics.get("warnings") == [])


def _check_code_provenance(audit: Audit) -> None:
    package = _json("resultados_publicaveis/estudo_comparativo/MANIFESTO_PACOTE.json")
    package_files = package.get("files", {})
    mapping: dict[str, str] = {}
    common = [
        "auditar_campos_portfolio.py",
        "avaliar_comparacao_robusta.py",
        "classificar_referencia_consenso.py",
        "discovery_contract.py",
        "llm_client.py",
        "normalizar_stage3_comum.py",
        "preparar_escopo_deterministico_v6.py",
        "preparar_execucoes_comparacao.py",
        "projeto.py",
        "run_stage3_kmeans_fair.py",
        "run_stage3_llm.py",
        "run_stage4_llm.py",
        "run_stage5_llm.py",
        "run_stage6_llm.py",
        "validar_ambiente_comparacao.py",
        "validar_artefato_retomada.py",
        "validar_comparacao_robusta.py",
        "validar_insumo_comparacao.py",
        "validar_pacote_comparacao.py",
        "validar_portfolio.py",
    ]
    for name in common:
        mapping[f"common/scripts/{name}"] = f"scripts/{name}"
    for name in (
        "job_00_referencia.sh",
        "job_10_m1_legado_llama.sh",
        "job_20_m2_nativo.sh",
        "job_30_ablacao.sh",
        "job_90_avaliacao.sh",
        "job_lib.sh",
    ):
        mapping[f"hpc/{name}"] = f"estudo_comparativo/hpc/{name}"
    for name in (
        "__init__.py",
        "llm_client.py",
        "03_cluster.py",
        "04_label_clusters.py",
        "05_compare_portfolio.py",
        "06_classify_portfolio.py",
    ):
        mapping[f"metodo1_legado_llama/pipeline/{name}"] = (
            f"metodo_estatistico/pipeline/{name}"
        )
    mapping.update(
        {
            "decision_rules_v1.json": "estudo_comparativo/decision_rules_v1.json",
            "experimento_config.json": "estudo_comparativo/experimento_config.json",
            "filtro_sala_sigilo_manifest_v6.json": (
                "estudo_comparativo/filtro_sala_sigilo_manifest_v6.json"
            ),
            "portfolio_referencia.json": (
                "formacao_portfolio/decisao_curada/portfolio_referencia.json"
            ),
        }
    )
    allowed_migrations = {
        "common/scripts/projeto.py",
        "common/scripts/run_stage3_kmeans_fair.py",
    }
    exact = []
    divergent = []
    missing = []
    for packaged, local in mapping.items():
        expected = package_files.get(packaged, {}).get("sha256")
        path = ROOT / local
        if not expected or not path.is_file():
            missing.append(f"{packaged}->{local}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            exact.append(packaged)
        else:
            divergent.append(packaged)
    archive = base64.b64decode(
        (
            ROOT
            / "estudo_comparativo/proveniencia_execucao/feedback_portfolio_executado.json.b64"
        )
        .read_text(encoding="ascii")
        .strip(),
        validate=True,
    )
    archived_feedback_exact = (
        hashlib.sha256(archive).hexdigest()
        == package_files.get("feedback_portfolio.json", {}).get("sha256")
    )
    audit.check(
        "provenance.executed_feedback_preserved",
        archived_feedback_exact,
    )
    audit.check("provenance.mapped_critical_files_present", not missing, "; ".join(missing))
    audit.check(
        "provenance.only_documented_path_migrations_differ",
        set(divergent) == allowed_migrations,
        ", ".join(divergent),
    )
    audit.check(
        "provenance.executed_computation_core_preserved",
        len(exact) == len(mapping) - len(allowed_migrations)
        and archived_feedback_exact,
        f"{len(exact) + int(archived_feedback_exact)}/{len(mapping) + 1} "
        "mapeados byte a byte",
    )
    fair = _text("scripts/run_stage3_kmeans_fair.py")
    project = _text("scripts/projeto.py")
    audit.check(
        "provenance.fair_kmeans_difference_is_docstring_path",
        "metodo_estatistico" in fair and "legado_metodo1" not in fair,
    )
    audit.check(
        "provenance.project_helper_matches_new_layout",
        '"configuracao" / "config_portfolio.json"' in project
        and '"formacao_portfolio"' in project
        and '"dashboard" / "runtime" / "knowledge_base.db"' in project,
    )


def _check_narrative(audit: Audit) -> None:
    readme = _text("README.md")
    flow = _text("docs/FLUXO_COMPLETO_MBA.md")
    formation = _text("formacao_portfolio/README.md")
    pipeline_note = _text("pipeline_data/README.md")
    unsupported = ["| 468 | 29,5% |", "| 435 | 27,5% |", "despenca para **1,3%**"]
    audit.check(
        "narrative.no_unsupported_curated_volumes",
        not any(marker in readme for marker in unsupported),
    )
    audit.check(
        "narrative.canonical_chronology",
        "candidato estatístico" in formation.lower()
        and "só depois" in formation.lower()
        and "alvo endógeno" in formation.lower()
        and "não houve rotulagem humana por chamado" in flow.lower(),
    )
    audit.check(
        "narrative.pipeline_aggregates_are_qualified",
        "execução" in pipeline_note
        and "arquitetura agêntica" in pipeline_note
        and "1.456 chamados" in pipeline_note
        and "não são os placares do estudo comparativo" in pipeline_note
        and "projeção automática" in pipeline_note
        and "retrospectiva" in pipeline_note,
    )
    publication_note = _text("docs/00_LEIA_PRIMEIRO_IA.md").lower()
    audit.check(
        "narrative.git_publication_recorded",
        "protasiofernando/mba-ia-puc" in publication_note
        and "único commit-raiz" in publication_note
        and "não possui histórico anterior" in publication_note
        and "branch de arquivo ou tag" in publication_note,
    )


def audit_project() -> dict:
    audit = Audit()
    try:
        _check_scope(audit)
        _check_target_and_history(audit)
        _check_flow(audit)
        _check_results(audit)
        _check_code_provenance(audit)
        _check_narrative(audit)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        audit.check("audit.completed_without_exception", False, repr(exc))
    else:
        audit.check("audit.completed_without_exception", True)
    return audit.report()


def main() -> int:
    report = audit_project()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
