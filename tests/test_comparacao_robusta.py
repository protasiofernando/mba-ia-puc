import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DECISION_DIR = ROOT / "formacao_portfolio" / "decisao_curada"
sys.path.insert(0, str(ROOT / "scripts"))

from avaliar_comparacao_robusta import (
    _cost_comparison,
    _grid_sensitivity,
    _integrated_conclusion,
    _partition_metrics,
    _strategic_protection,
)
from classificar_referencia_consenso import (
    _normalize_vote,
    _summary_payload as reference_summary_payload,
)
from discovery_contract import opaque_roundtrip_id
from llm_client import LLMError
from normalizar_stage3_comum import normalizar
from run_stage3_llm import _opaque_working_summaries
from run_stage5_llm import _normalize_closed_destination
from run_stage5_llm import (
    CATEGORY_MAPPING_VERSION as STAGE5_MAPPING_PRODUCER,
)
from run_stage5_llm import PIPELINE_VERSION as STAGE5_PIPELINE_PRODUCER
from validar_portfolio import (
    CATEGORY_MAPPING_VERSION as STAGE5_MAPPING_VALIDATOR,
)
from validar_portfolio import (
    STAGE5_PIPELINE_VERSION as STAGE5_PIPELINE_VALIDATOR,
)
from gerar_pacote_comparacao_robusta import _validate_cross_contracts
from validar_comparacao_robusta import _portfolio_shared_view


def _load_legacy_stage5():
    path = ROOT / "metodo_estatistico" / "pipeline" / "05_compare_portfolio.py"
    spec = importlib.util.spec_from_file_location("legacy_stage5", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ComparisonUnitTests(unittest.TestCase):
    def test_final_package_build_and_independent_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / (
                "mba-ia-puc_comparacao_teste.zip"
            )
            build = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "gerar_pacote_comparacao_robusta.py"
                    ),
                    "--stage2-manifest",
                    str(
                        ROOT
                        / "tests"
                        / "fixtures"
                        / "MANIFESTO_STAGE2_V6.json"
                    ),
                    "--out",
                    str(out),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                build.returncode,
                0,
                build.stderr + build.stdout,
            )
            audit = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "validar_pacote_comparacao.py"
                    ),
                    str(out),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                audit.returncode,
                0,
                audit.stderr + audit.stdout,
            )
            result = json.loads(audit.stdout)
            self.assertEqual(result["status"], "PASS")
            self.assertEqual(result["privacy_gate"], "PASS")
            self.assertEqual(
                result["stage5_category_mapping_version"],
                "closed-destination-stage4-evidence-v3",
            )

    def test_stage5_producer_and_validator_contracts_are_identical(self):
        self.assertEqual(
            STAGE5_PIPELINE_PRODUCER,
            "stage5-operational-reconciliation-v6.1",
        )
        self.assertEqual(
            STAGE5_MAPPING_PRODUCER,
            "closed-destination-stage4-evidence-v3",
        )
        self.assertEqual(
            STAGE5_PIPELINE_PRODUCER,
            STAGE5_PIPELINE_VALIDATOR,
        )
        self.assertEqual(
            STAGE5_MAPPING_PRODUCER,
            STAGE5_MAPPING_VALIDATOR,
        )

    def test_package_preflight_rejects_stage5_contract_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scripts = root / "scripts"
            scripts.mkdir()
            (scripts / "run_stage5_llm.py").write_text(
                'PIPELINE_VERSION = "stage5-operational-reconciliation-v6.1"\n'
                'CATEGORY_MAPPING_VERSION = '
                '"closed-destination-stage4-evidence-v3"\n',
                encoding="utf-8",
            )
            (scripts / "validar_portfolio.py").write_text(
                'STAGE5_PIPELINE_VERSION = '
                '"stage5-operational-reconciliation-v6.1"\n'
                'CATEGORY_MAPPING_VERSION = '
                '"closed-destination-stage4-evidence-v2"\n',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                "contrato de mapeamento Stage 5 divergente",
            ):
                _validate_cross_contracts(root)

    def test_package_preflight_accepts_release_contracts(self):
        result = _validate_cross_contracts(ROOT)
        self.assertTrue(result["producer_validator_equal"])
        self.assertEqual(
            result["stage5_category_mapping_version"],
            "closed-destination-stage4-evidence-v3",
        )

    def test_stage5_closed_destination_accepts_unique_digest_identity(self):
        portfolio = {
            "teste_e_projeto_4c2cd10d": {"nome": "Teste e Projeto"},
            "ambiente_pesquisa_a1b2c3d4": {"nome": "Ambiente de Pesquisa"},
        }
        self.assertEqual(
            _normalize_closed_destination(
                "test_e_projeto_4c2cd10d",
                portfolio,
            ),
            "teste_e_projeto_4c2cd10d",
        )

    def test_stage5_closed_destination_rejects_ambiguous_digest(self):
        portfolio = {
            "categoria_a_4c2cd10d": {"nome": "Categoria A"},
            "categoria_b_4c2cd10d": {"nome": "Categoria B"},
        }
        with self.assertRaisesRegex(LLMError, "destino_id inexistente"):
            _normalize_closed_destination(
                "categoria_qualquer_4c2cd10d",
                portfolio,
            )

    def test_stage5_closed_destination_rejects_changed_digest(self):
        portfolio = {
            "teste_e_projeto_4c2cd10d": {"nome": "Teste e Projeto"},
        }
        with self.assertRaisesRegex(LLMError, "destino_id inexistente"):
            _normalize_closed_destination(
                "test_e_projeto_deadbeef",
                portfolio,
            )

    def test_stage5_closed_destination_keeps_exact_and_wrapped_contracts(self):
        portfolio = {
            "teste_e_projeto_4c2cd10d": {"nome": "Teste e Projeto"},
        }
        self.assertEqual(
            _normalize_closed_destination(
                "teste_e_projeto_4c2cd10d",
                portfolio,
            ),
            "teste_e_projeto_4c2cd10d",
        )
        self.assertEqual(
            _normalize_closed_destination(
                "destino_id=teste_e_projeto_4c2cd10d",
                portfolio,
            ),
            "teste_e_projeto_4c2cd10d",
        )

    def test_active_reference_code_cannot_classify_scope_with_llm(self):
        source = (
            ROOT / "scripts" / "classificar_referencia_consenso.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("SCOPE_SYSTEM", source)
        self.assertNotIn('phase="scope"', source)
        self.assertIn("--scope-mask", source)
        self.assertIn(
            "deterministic_structured_request_type_prefilter",
            source,
        )

    def test_deterministic_scope_includes_prefiltered_stage2_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            summaries = base / "02_summaries.json"
            rows = [
                {
                    "chave": "T-1",
                    "intencao": "usar hpc",
                    "tema": "hpc",
                    "tipo_pedido": "solicitacao",
                },
                {
                    "chave": "T-2",
                    "intencao": "criar vm",
                    "tema": "vm",
                    "tipo_pedido": "solicitacao",
                },
            ]
            summaries.write_text(
                json.dumps(rows, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            manifest = base / "filter_manifest.json"
            manifest.write_text(
                json.dumps({
                    "decision_field": "Customer Request Type",
                    "matching_policy": "exact_trimmed_case_sensitive",
                    "totals": {
                        "rows_before": 3,
                        "rows_removed_before_stage1": 1,
                        "rows_after": 2,
                    },
                }),
                encoding="utf-8",
            )
            out = base / "referencia"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(
                        ROOT
                        / "scripts"
                        / "preparar_escopo_deterministico_v6.py"
                    ),
                    "--summaries",
                    str(summaries),
                    "--filter-manifest",
                    str(manifest),
                    "--out-dir",
                    str(out),
                ],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                completed.returncode,
                0,
                completed.stderr + completed.stdout,
            )
            scope = json.loads(
                (out / "01_scope_mask.json").read_text(encoding="utf-8")
            )
            self.assertEqual(scope["incluidos"], ["T-1", "T-2"])
            self.assertEqual(scope["exclusoes"], [])
            self.assertEqual(scope["indeterminados"], [])
            self.assertFalse(scope["metadata"]["llm_used_for_scope"])
            self.assertEqual(
                (out / "02_summaries_escopo.json").read_bytes(),
                summaries.read_bytes(),
            )

    def test_no_historical_renderer_and_final_gate_is_explicit(self):
        evaluator = (
            ROOT / "scripts" / "avaliar_comparacao_robusta.py"
        ).read_text(encoding="utf-8")
        job90 = (
            ROOT / "estudo_comparativo" / "hpc" / "job_90_avaliacao.sh"
        ).read_text(encoding="utf-8")
        self.assertNotIn("_render_markdown_v1_historical", evaluator)
        self.assertIn("--require-final-report", job90)

    def test_frozen_input_validator_rejects_wrong_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            source = base / "source" / "02_summaries.json"
            source.parent.mkdir()
            rows = [
                {
                    "chave": "A-1",
                    "intencao": "usar hpc",
                    "tema": "hpc",
                    "tipo_pedido": "solicitacao",
                },
                {
                    "chave": "A-2",
                    "intencao": "criar vm",
                    "tema": "vm",
                    "tipo_pedido": "solicitacao",
                },
            ]
            source.write_text(
                json.dumps(rows, ensure_ascii=False),
                encoding="utf-8",
            )
            expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()
            (base / "experimento_config.json").write_text(
                json.dumps({
                    "input": {
                        "source_relpath": "source/02_summaries.json",
                        "expected_sha256": expected_sha,
                        "expected_count": 2,
                        "required_fields": [
                            "chave",
                            "intencao",
                            "tema",
                            "tipo_pedido",
                        ],
                    }
                }),
                encoding="utf-8",
            )
            command = [
                sys.executable,
                str(ROOT / "scripts" / "validar_insumo_comparacao.py"),
                "--base",
                str(base),
            ]
            valid = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(valid.returncode, 0, valid.stderr + valid.stdout)
            rows[0]["tema"] = "alterado"
            source.write_text(json.dumps(rows), encoding="utf-8")
            invalid = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertNotEqual(invalid.returncode, 0)

    def test_bcubed_and_macro_best_match(self):
        predicted = {f"k{i}": f"p{i}" for i in range(4)}
        reference = {
            "k0": "a",
            "k1": "a",
            "k2": "b",
            "k3": "b",
        }
        target = {"a": {"nome": "A"}, "b": {"nome": "B"}}
        result = _partition_metrics(
            predicted,
            reference,
            {"a", "b"},
            target,
            {"minimum_n": 1, "minimum_row_share": 0, "minimum_column_share": 0},
        )
        self.assertAlmostEqual(result["bcubed_precision"], 1.0)
        self.assertAlmostEqual(result["bcubed_recall"], 0.5)
        self.assertAlmostEqual(result["bcubed_f1"], 2 / 3, places=5)
        self.assertAlmostEqual(
            result["macro_best_match_f1_services"], 2 / 3, places=5
        )

    def test_vote_validation_rejects_string_boolean(self):
        with self.assertRaises(LLMError):
            _normalize_vote(
                {
                    "decision_id": "a",
                    "second_option_id": None,
                    "confidence": "alta",
                    "ambiguity": "false",
                    "justification": "x",
                },
                {"a", "b"},
            )

    def test_vote_validation_accepts_reversible_id_prefix(self):
        vote = _normalize_vote(
            {
                "decision_id": "id=servidores_academicos",
                "second_option_id": "id:hpc_gpu",
                "confidence": "alta",
                "ambiguity": False,
                "justification": "servico principal identificado",
            },
            {"servidores_academicos", "hpc_gpu"},
        )
        self.assertEqual(vote["decision_id"], "servidores_academicos")
        self.assertEqual(vote["second_option_id"], "hpc_gpu")

    def test_llm_roundtrip_identifier_is_opaque_and_reversible_locally(self):
        first = opaque_roundtrip_id("TICKET-SINTETICO-0001")
        second = opaque_roundtrip_id("TICKET-SINTETICO-0001")
        self.assertEqual(first, second)
        self.assertNotIn("1234", first)
        working, original_by_opaque = _opaque_working_summaries([
            {
                "chave": "TICKET-SINTETICO-0001",
                "intencao": "solicitar recurso",
                "tema": "hpc",
                "tipo_pedido": "solicitacao",
            }
        ])
        self.assertEqual(working[0]["chave"], first)
        self.assertEqual(original_by_opaque[first], "TICKET-SINTETICO-0001")
        reference_payload = reference_summary_payload({
            "chave": "TICKET-SINTETICO-0001",
            "intencao": "solicitar recurso",
        })
        self.assertNotIn("chave", reference_payload)
        self.assertEqual(reference_payload["registro_id"], first)

    def test_grid_sensitivity_decomposes_each_dimension(self):
        def item(direction):
            return {
                "direction": direction,
                "difference_llm_minus_kmeans": 0.1,
            }

        seed_only = {
            "1": {"v": {"l": item("llm")}},
            "2": {"v": {"l": item("kmeans")}},
        }
        self.assertTrue(_grid_sensitivity(seed_only)["seed_sensitive"])
        self.assertFalse(
            _grid_sensitivity(seed_only)["reference_sensitive"]
        )
        self.assertFalse(_grid_sensitivity(seed_only)["layer_sensitive"])

        reference_only = {
            "1": {
                "a": {"l": item("llm")},
                "b": {"l": item("kmeans")},
            }
        }
        self.assertTrue(
            _grid_sensitivity(reference_only)["reference_sensitive"]
        )
        self.assertFalse(_grid_sensitivity(reference_only)["seed_sensitive"])

        layer_only = {
            "1": {
                "v": {
                    "discovery": item("llm"),
                    "final": item("equivalent"),
                }
            }
        }
        self.assertTrue(_grid_sensitivity(layer_only)["layer_sensitive"])
        self.assertFalse(
            _grid_sensitivity(layer_only)["reference_sensitive"]
        )

    def test_strategic_guard_rejects_material_service_loss(self):
        left = {
            "per_reference": {
                "hpc_gpu": {"best_match_f1": 0.9, "support": 10},
            }
        }
        right = {
            "per_reference": {
                "hpc_gpu": {"best_match_f1": 0.7, "support": 10},
            }
        }
        guard = _strategic_protection(
            left,
            right,
            "right",
            "left",
            "right",
            {
                "maximum_strategic_service_loss": 0.1,
                "strategic_service_ids": ["hpc_gpu"],
            },
        )
        self.assertFalse(guard["passed"])
        no_support = _strategic_protection(
            {"per_reference": {}},
            {"per_reference": {}},
            None,
            "left",
            "right",
            {
                "minimum_strategic_service_support": 5,
                "strategic_service_ids": ["hpc_gpu"],
            },
        )
        self.assertFalse(no_support["passed"])
        self.assertEqual(no_support["unevaluable_services"], ["hpc_gpu"])

    def test_stage3_normalizer_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            raw = {
                "optimal_k": 2,
                "metodo": "teste",
                "metadata": {"clustering_fingerprint": "old"},
                "cluster_stats": [],
                "outlier_stats": [],
                "tickets": [
                    {
                        "chave": "A",
                        "intencao": "um",
                        "tema": "x",
                        "tipo_pedido": "solicitacao",
                        "contexto": "c",
                        "tipo_atual": "old",
                        "cluster_id": 4,
                    },
                    {
                        "chave": "B",
                        "intencao": "dois",
                        "tema": "y",
                        "tipo_pedido": "incidente",
                        "contexto": "c",
                        "tipo_atual": "old",
                        "cluster_id": 8,
                    },
                ],
                "_definicoes": [{"cluster_id": 4, "nome": "vazamento"}],
            }
            (folder / "03_clusters.json").write_text(
                json.dumps(raw), encoding="utf-8"
            )
            first = normalizar(folder)
            first_bytes = (folder / "03_clusters.json").read_bytes()
            second = normalizar(folder)
            second_bytes = (folder / "03_clusters.json").read_bytes()
            self.assertEqual(first_bytes, second_bytes)
            self.assertEqual(second["status"], "already_normalized")
            output = json.loads(first_bytes)
            self.assertEqual(output["_definicoes"], [])
            self.assertEqual(
                [row["cluster_id"] for row in output["tickets"]], [0, 1]
            )
            self.assertEqual(first["k"], 2)

    def test_stage3_normalizer_is_label_permutation_invariant(self):
        base_tickets = [
            {"chave": "A", "intencao": "a", "tema": "x", "tipo_pedido": "s"},
            {"chave": "B", "intencao": "b", "tema": "x", "tipo_pedido": "s"},
            {"chave": "C", "intencao": "c", "tema": "y", "tipo_pedido": "i"},
            {"chave": "D", "intencao": "d", "tema": "y", "tipo_pedido": "i"},
        ]
        outputs = []
        with tempfile.TemporaryDirectory() as tmp:
            for folder_name, labels in (
                ("one", [8, 8, 4, 4]),
                ("two", [1, 1, 9, 9]),
            ):
                folder = Path(tmp) / folder_name
                folder.mkdir()
                tickets = [
                    {**row, "cluster_id": label, "outlier_id": None}
                    for row, label in zip(base_tickets, labels)
                ]
                (folder / "03_clusters.json").write_text(
                    json.dumps({"tickets": tickets, "metadata": {}}),
                    encoding="utf-8",
                )
                normalizar(folder)
                data = json.loads(
                    (folder / "03_clusters.json").read_text(encoding="utf-8")
                )
                outputs.append({
                    row["chave"]: row["cluster_id"] for row in data["tickets"]
                })
        self.assertEqual(outputs[0], outputs[1])

    def test_cost_requires_complete_stages_and_material_gap(self):
        def result(seconds, available=True):
            return {
                "cost": {
                    "wall_seconds_stages_3_6": seconds,
                    "wall_seconds_stages_3_6_available": available,
                }
            }

        rules = {"cost_tiebreaker": {"minimum_relative_difference": 0.1}}
        comparison = _cost_comparison(
            {"a": result(100), "b": result(95)},
            ["a"],
            ["b"],
            "left",
            "right",
            rules,
        )
        self.assertEqual(comparison["winner"], "equivalent")
        unavailable = _cost_comparison(
            {"a": result(100), "b": result(1, available=False)},
            ["a"],
            ["b"],
            "left",
            "right",
            rules,
        )
        self.assertIsNone(unavailable["winner"])

    def test_operational_feedback_matches_comparison_target(self):
        target = json.loads(
            (DECISION_DIR / "portfolio_referencia.json").read_text(encoding="utf-8")
        )
        feedback = json.loads(
            (DECISION_DIR / "feedback_portfolio.json").read_text(encoding="utf-8")
        )
        views = _portfolio_shared_view(target, feedback)
        self.assertEqual(views["target"], views["feedback"])
        changed = json.loads(json.dumps(feedback))
        changed["portfolio_final"][0]["grupo"] = "Grupo incorreto"
        changed_views = _portfolio_shared_view(target, changed)
        self.assertNotEqual(
            changed_views["target"],
            changed_views["feedback"],
        )

    def test_legacy_stage5_validates_after_mandatory_merge(self):
        stage5 = _load_legacy_stage5()
        recommendation = {
            "portfolio_otimizado": [
                {"nome": "Categoria A"},
                {"nome": "Categoria B"},
            ]
        }
        mandatory = [{"nome": "Nao encontrou o que procurava?"}]
        normalized, diagnostic = (
            stage5._normalize_and_merge_recommendation(
                recommendation,
                mandatory,
            )
        )
        self.assertIsNotNone(normalized)
        self.assertEqual(diagnostic["valid_items_before_merge"], 2)
        self.assertEqual(diagnostic["valid_items_after_merge"], 3)
        self.assertEqual(
            [item["nome"] for item in normalized["portfolio_otimizado"]],
            [
                "Categoria A",
                "Categoria B",
                "Nao encontrou o que procurava?",
            ],
        )

    def test_legacy_stage5_rejects_small_portfolio_cleanly(self):
        stage5 = _load_legacy_stage5()
        normalized, diagnostic = (
            stage5._normalize_and_merge_recommendation(
                {"portfolio_otimizado": [{"nome": "Categoria A"}]},
                [{"nome": "Nao encontrou o que procurava?"}],
            )
        )
        self.assertIsNone(normalized)
        self.assertEqual(
            diagnostic["reason"],
            "portfolio_too_small_after_mandatory_merge",
        )

    def test_integrated_cost_evidence_never_disappears(self):
        operational = {
            "code": "operacional_equivalentes_m1_mais_eficiente",
            "strength": "descritiva_condicional_a_uma_execucao",
            "reference_sensitive": False,
            "layer_sensitive": False,
            "quality_winner": None,
            "cost_winner": "m1",
        }
        fair = {
            "code": "equivalentes_llm_mais_eficiente",
            "strength": "forte",
            "quality_winner": None,
            "cost_winner": "llm",
        }
        result = _integrated_conclusion(operational, fair)
        self.assertTrue(result["cost_evidence_available"])
        self.assertFalse(result["cost_evidence_convergent"])
        self.assertEqual(
            result["cost_synthesis_code"],
            "custos_divergentes_entre_estimandos",
        )
        fair["cost_winner"] = None
        unavailable = _integrated_conclusion(operational, fair)
        self.assertFalse(unavailable["cost_evidence_available"])
        self.assertEqual(
            unavailable["cost_synthesis_code"],
            "custo_incompleto_entre_estimandos",
        )


class ComparisonEndToEndTest(unittest.TestCase):
    def test_evaluator_generates_conclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            shutil.copy2(
                ROOT / "estudo_comparativo" / "experimento_config.json",
                base / "experimento_config.json",
            )
            rules = json.loads(
                (ROOT / "estudo_comparativo" / "decision_rules_v1.json").read_text(
                    encoding="utf-8"
                )
            )
            rules["bootstrap"]["replicates"] = 30
            (base / "decision_rules_v1.json").write_text(
                json.dumps(rules), encoding="utf-8"
            )
            shutil.copy2(
                DECISION_DIR / "portfolio_referencia.json",
                base / "portfolio_referencia.json",
            )
            shutil.copy2(
                DECISION_DIR / "feedback_portfolio.json",
                base / "feedback_portfolio.json",
            )
            shutil.copy2(
                ROOT / "estudo_comparativo" / "PROTOCOLO_METODOLOGICO.md",
                base / "PROTOCOLO_METODOLOGICO.md",
            )
            (base / "MANIFESTO_PACOTE.json").write_text(
                json.dumps({"files": {}}),
                encoding="utf-8",
            )
            portfolio = json.loads(
                (base / "portfolio_referencia.json").read_text(encoding="utf-8")
            )
            services = [
                row["id"]
                for row in portfolio["categorias_analiticas"]
                if row.get("papel_analise") != "catch_all"
            ]
            group_by_service = {
                row["id"]: row["grupo_id"]
                for row in portfolio["categorias_analiticas"]
            }
            keys = [f"T-{index:03d}" for index in range(70)]
            refs = {key: services[index % len(services)] for index, key in enumerate(keys)}
            summaries = [
                {
                    "chave": key,
                    "intencao": "teste",
                    "tema": "tema",
                    "tipo_pedido": "solicitacao",
                    "contexto": "ctx",
                    "info_fornecidas": [],
                    "info_faltantes": [],
                }
                for key in keys
            ]
            reference_dir = base / "referencia"
            reference_dir.mkdir()
            analytic_path = reference_dir / "02_summaries_escopo.json"
            analytic_path.write_text(json.dumps(summaries), encoding="utf-8")
            scope = {
                "metadata": {
                    "n_total": 72,
                    "n_sala_sigilo": 2,
                    "n_indeterminados": 0,
                    "scope_fingerprint": "scope",
                    "source_fingerprint": "raw",
                },
                "incluidos": keys,
                "exclusoes": [{"chave": "S-1"}, {"chave": "S-2"}],
                "indeterminados": [],
            }
            (reference_dir / "01_scope_mask.json").write_text(
                json.dumps(scope), encoding="utf-8"
            )
            classifications = [
                {
                    "chave": key,
                    "categoria_estrita_id": refs[key],
                    "categoria_cobertura_id": refs[key],
                    "categoria_ref_id": refs[key],
                    "categoria_ref": refs[key],
                    "grupo_ref_id": group_by_service[refs[key]],
                    "status_consenso": "initial_agreement",
                    "modelo_a_id": refs[key],
                    "modelo_b_id": refs[key],
                }
                for key in keys
            ]
            (reference_dir / "06_referencia_consenso.json").write_text(
                json.dumps(
                    {
                        "metadata": {"n_escopo": len(keys)},
                        "classificacoes": classifications,
                    }
                ),
                encoding="utf-8",
            )
            (reference_dir / "06_referencia_quality.json").write_text(
                json.dumps({"n_consenso_estrito": len(keys)}),
                encoding="utf-8",
            )
            input_hash = __import__("hashlib").sha256(
                analytic_path.read_bytes()
            ).hexdigest()
            (base / "manifesto_insumo_comum.json").write_text(
                json.dumps(
                    {
                        "analytic_input_sha256": input_hash,
                        "n_analiticos": len(keys),
                    }
                ),
                encoding="utf-8",
            )
            config = json.loads(
                (base / "experimento_config.json").read_text(encoding="utf-8")
            )
            runs = [config["native_m1"]] + config["runs"]
            required = set(config["comparisons"]["operational"])
            required.update(config["comparisons"]["fair_ablation_primary"])
            for run in runs:
                if run["id"] not in required:
                    continue
                pd = base / run["pipeline_data"]
                pd.mkdir(parents=True, exist_ok=True)
                (pd / "02_summaries.json").write_bytes(analytic_path.read_bytes())
                is_llm = run["id"] in {"m2_native", "llm_common_seed42"}
                stage3_tickets = []
                stage6 = []
                for index, key in enumerate(keys):
                    if is_llm:
                        leaf = refs[key]
                        cluster = services.index(refs[key])
                    else:
                        leaf = f"coarse_{index % 2}"
                        cluster = index % 2
                    stage3_tickets.append(
                        {
                            "chave": key,
                            "cluster_id": cluster,
                            "outlier_id": None,
                        }
                    )
                    stage6.append(
                        {
                            "chave": key,
                            "categoria_id": leaf,
                            "categoria_nova": leaf,
                            "grupo_novo": group_by_service.get(
                                refs[key], "coarse_group"
                            ) if is_llm else "coarse_group",
                            "confianca": "alta",
                            "ambiguidade": False,
                        }
                    )
                (pd / "03_clusters.json").write_text(
                    json.dumps({"tickets": stage3_tickets}),
                    encoding="utf-8",
                )
                (pd / "06_classificados.json").write_text(
                    json.dumps(stage6), encoding="utf-8"
                )
            command = [
                sys.executable,
                str(ROOT / "scripts" / "avaliar_comparacao_robusta.py"),
                "--base",
                str(base),
            ]
            completed = subprocess.run(
                command,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            report = json.loads(
                (
                    base
                    / "avaliacao"
                    / "RESULTADO_COMPARACAO_ROBUSTA.metrics.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(report["conclusion"]["quality_winner"], "llm")
            self.assertEqual(
                set(report["conclusion"]["bootstrap_by_reference_view"]),
                {
                    "consensus_strict",
                    "consensus_full",
                    "model_a",
                    "model_b",
                },
            )
            self.assertEqual(
                report["operational_comparison"]["quality_winner"],
                "m2",
            )
            self.assertIn("integrated_conclusion", report)
            markdown = (
                base / "avaliacao" / "RESULTADO_COMPARACAO_ROBUSTA.md"
            ).read_text(encoding="utf-8")
            self.assertIn("Benchmark das arquiteturas downstream", markdown)
            self.assertIn("Ablação justa", markdown)
            self.assertIn("Estabilidade alvo-independente", markdown)
            self.assertIn("Síntese de custo", markdown)
            self.assertIn("Células cuja direção difere", markdown)
            self.assertTrue(
                (base / "avaliacao" / "ledger_sanitizado.csv").exists()
            )


if __name__ == "__main__":
    unittest.main()
