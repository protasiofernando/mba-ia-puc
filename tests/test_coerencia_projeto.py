import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from validar_coerencia_projeto import audit_project
from verificar_publicacao_novo_repo import _reject_duplicate_json_keys


class ProjectCoherenceTest(unittest.TestCase):
    def test_story_code_targets_and_results_are_coherent(self):
        report = audit_project()
        failures = [
            row for row in report["details"] if row.get("status") == "FAIL"
        ]
        self.assertEqual(failures, [], failures)
        self.assertEqual(report["status"], "PASS")
        self.assertGreaterEqual(report["checks"], 40)
        self.assertFalse(report["git_operation_performed"])
        with self.assertRaisesRegex(ValueError, "chave JSON duplicada"):
            json.loads(
                '{"manifest_sha256_inside_zip":"a",'
                '"manifest_sha256_inside_zip":"b"}',
                object_pairs_hook=_reject_duplicate_json_keys,
            )

        # A narrativa pública promete simulação local ou Azure. Este teste de
        # contrato prova o caminho local sem chamar rede nem carregar tickets.
        import dashboard.app as dashboard_app

        class FakeLLMClient:
            def __init__(self, provider_override=None):
                self.provider = provider_override
                self.model = "modelo-teste"
                self.model_label = "ollama:modelo-teste"
                self.timeout = 5

            def chat_json(self, *_args, **_kwargs):
                return {
                    "titulo_sugerido": "Acesso a servidor acadêmico",
                    "texto_sugerido": "Preciso acessar o SERVIDOR_ACADEMICO.",
                    "grupo": "Infraestrutura Computacional",
                    "categoria": "Servidores Acadêmicos Compartilhados",
                    "justificativa": "O pedido trata de acesso ao servidor.",
                    "confianca": "alta",
                    "informacoes_faltantes": ["SERVIDOR_ACADEMICO"],
                }

        env = {
            "DASHBOARD_LLM_PROVIDER": "ollama",
            "OLLAMA_MODEL": "modelo-teste",
        }
        with patch.dict(os.environ, env, clear=False), patch.object(
            dashboard_app, "LLMClient", FakeLLMClient
        ):
            client = dashboard_app.app.test_client()
            status = client.get("/api/llm-status")
            self.assertEqual(status.status_code, 200)
            self.assertTrue(status.get_json()["local"])

            response = client.post(
                "/api/simular", json={"descricao": "Preciso acessar um servidor."}
            )
            payload = response.get_json()
            self.assertEqual(response.status_code, 200, payload)
            self.assertEqual(payload["motor"]["provedor"], "ollama")
            self.assertTrue(payload["motor"]["local"])
            self.assertEqual(payload["categoria"], "Servidores Acadêmicos Compartilhados")

        azure_env = {
            "DASHBOARD_LLM_PROVIDER": "",
            "OLLAMA_MODEL": "",
            "AZURE_OPENAI_API_KEY": "chave-teste",
            "AZURE_OPENAI_ENDPOINT": "https://exemplo.openai.azure.com",
            "AZURE_OPENAI_DEPLOYMENT": "deployment-teste",
        }
        with patch.dict(os.environ, azure_env, clear=False):
            status = dashboard_app.app.test_client().get("/api/llm-status")
            status_payload = status.get_json()
            self.assertEqual(status.status_code, 200)
            self.assertEqual(status_payload["provedor"], "azure")
            self.assertEqual(status_payload["modelo"], "deployment-teste")
            self.assertFalse(status_payload["local"])


if __name__ == "__main__":
    unittest.main()
