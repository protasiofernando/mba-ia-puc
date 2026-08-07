import base64
import hashlib
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import materializar_portfolio_curado as materializer
import run_stage7_curadoria as stage7


class PortfolioFormationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.feedback = json.loads(
            (
                ROOT
                / "formacao_portfolio"
                / "decisao_curada"
                / "feedback_portfolio.json"
            ).read_text(encoding="utf-8-sig")
        )
        cls.reference = json.loads(
            (
                ROOT
                / "formacao_portfolio"
                / "decisao_curada"
                / "portfolio_referencia.json"
            ).read_text(encoding="utf-8-sig")
        )
        cls.contract = json.loads(
            (ROOT / "formacao_portfolio" / "contrato_curadoria.json").read_text(
                encoding="utf-8-sig"
            )
        )

    def test_frozen_files_still_match_executed_manifest(self):
        manifest = json.loads(
            (
                ROOT
                / "resultados_publicaveis"
                / "estudo_comparativo"
                / "MANIFESTO_PACOTE.json"
            ).read_text(encoding="utf-8-sig")
        )
        decision_dir = ROOT / "formacao_portfolio" / "decisao_curada"
        actual_reference = hashlib.sha256(
            (decision_dir / "portfolio_referencia.json").read_bytes()
        ).hexdigest()
        self.assertEqual(
            actual_reference,
            manifest["files"]["portfolio_referencia.json"]["sha256"],
        )
        encoded = (
            ROOT
            / "estudo_comparativo"
            / "proveniencia_execucao"
            / "feedback_portfolio_executado.json.b64"
        ).read_text(encoding="ascii")
        executed_feedback = base64.b64decode(encoded.strip(), validate=True)
        self.assertEqual(
            hashlib.sha256(executed_feedback).hexdigest(),
            manifest["files"]["feedback_portfolio.json"]["sha256"],
        )

    def test_feedback_deterministically_projects_to_frozen_reference(self):
        materializer.validate_reference(
            self.feedback,
            self.contract,
            self.reference,
        )
        rebuilt = materializer.build_reference(self.feedback, self.contract)
        self.assertEqual(
            materializer.semantic_view(rebuilt),
            materializer.semantic_view(self.reference),
        )

    def test_sala_is_visible_but_never_analytical(self):
        analytical = {
            row["id"] for row in self.reference["categorias_analiticas"]
        }
        self.assertNotIn("sala_sigilo", analytical)
        sala = self.reference["itens_fixos_fora_analise"]
        self.assertEqual([row["id"] for row in sala], ["sala_sigilo"])
        self.assertTrue(sala[0]["visivel_no_portal_dti_pesquisa"])
        for field in (
            "participa_descoberta",
            "participa_otimizacao",
            "participa_metricas",
            "participa_ranking",
        ):
            self.assertFalse(sala[0][field])

    def test_operational_definition_is_human_curated_without_ticket_labels(self):
        result = materializer.build_operational(self.feedback)
        self.assertTrue(result["metadata"]["human_curated"])
        self.assertEqual(result["metadata"]["classification_status"], "not_materialized")
        self.assertIsNone(result["metadata"]["total_classificados"])
        self.assertEqual(len(result["portfolio_final"]), 9)

    def test_published_stage7_aggregate_is_complete_and_ticket_free(self):
        aggregate = json.loads(
            (ROOT / "pipeline_data" / "07_portfolio_final.json").read_text(
                encoding="utf-8-sig"
            )
        )
        metadata = aggregate["metadata"]
        self.assertEqual(metadata["classification_status"], "complete")
        self.assertEqual(metadata["total_classificados"], 1456)
        self.assertEqual(metadata["base_portfolio"], 1456)

        categories = aggregate["portfolio_final"]
        self.assertEqual(
            {row["id"] for row in categories},
            {row["id"] for row in self.feedback["portfolio_final"]},
        )
        analytical = [row for row in categories if not row.get("fora_da_analise")]
        self.assertEqual(sum(row["volume"] for row in analytical), 1456)
        sala = next(row for row in categories if row["id"] == "sala_sigilo")
        self.assertEqual(sala["volume"], 0)
        self.assertTrue(sala["fora_da_analise"])
        self.assertNotIn("classificacoes", aggregate)

    def test_stage7_closed_portfolio_excludes_sala(self):
        _, by_id, _ = stage7._portfolio(self.feedback)
        self.assertEqual(len(by_id), 8)
        self.assertNotIn("sala_sigilo", by_id)
        response = {
            "categoria_id": "hpc_gpu",
            "segunda_opcao_id": None,
            "justificativa": "Demanda de processamento intensivo.",
            "confianca": "alta",
            "ambiguidade": False,
        }
        normalized = stage7._normalize(response, by_id)
        self.assertEqual(normalized["categoria_id"], "hpc_gpu")
        self.assertFalse(normalized["revisao_recomendada"])

    def test_formation_and_stage7_runners_exist(self):
        paths = [
            ROOT / "formacao_portfolio" / "hpc" / "job_formar_candidato_estatistico.sh",
            ROOT / "scripts" / "materializar_portfolio_curado.py",
            ROOT / "scripts" / "verificar_origem_formacao.py",
            ROOT / "scripts" / "run_stage7_curadoria.py",
            ROOT / "scripts" / "hpc" / "job_stage7_curadoria.sh",
        ]
        for path in paths:
            self.assertTrue(path.is_file(), path)

    def test_historical_snapshot_matches_its_manifest(self):
        snapshot = ROOT / "formacao_portfolio" / "metodo_inicial_kmeans_git_a5576c8"
        manifest = json.loads(
            (snapshot / "MANIFESTO_SNAPSHOT.json").read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(manifest["files"]), 23)
        for relative, expected in manifest["files"].items():
            data = (snapshot / relative).read_bytes()
            self.assertEqual(len(data), expected["bytes"], relative)
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"], relative)


if __name__ == "__main__":
    unittest.main()
