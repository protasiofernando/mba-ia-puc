import hashlib
import json
import unittest
from pathlib import Path

from scripts.gerar_base_sintetica import generate


ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "resultados_publicaveis"
PUBLIC = RESULTS / "estudo_comparativo"


class PublicResultsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(
            (RESULTS / "MANIFESTO_RESULTADOS.json").read_text(encoding="utf-8-sig")
        )

    def test_promoted_files_match_manifest(self):
        self.assertEqual(len(self.manifest["files"]), 11)
        for relative, expected in self.manifest["files"].items():
            path = PUBLIC / relative
            data = path.read_bytes()
            self.assertEqual(len(data), expected["bytes"], relative)
            self.assertEqual(hashlib.sha256(data).hexdigest(), expected["sha256"], relative)

    def test_final_validation_is_complete_and_successful(self):
        validation = json.loads(
            (PUBLIC / "avaliacao" / "VALIDACAO_RESULTS.json").read_text(
                encoding="utf-8-sig"
            )
        )
        self.assertEqual(validation["status"], "PASS")
        self.assertEqual(validation["failures"], 0)
        self.assertEqual(len(validation["checks"]), 302)
        self.assertTrue(all(row["status"] == "PASS" for row in validation["checks"]))

    def test_public_manifest_declares_no_sensitive_content(self):
        self.assertTrue(all(value is False for value in self.manifest["privacy"].values()))
        self.assertEqual(self.manifest["source_job90"], "2234.HPCGPU")

    def test_synthetic_demo_is_public_only_and_deterministic(self):
        first = generate(80, 42)
        second = generate(80, 42)
        self.assertEqual(first, second)
        self.assertEqual(len(first), 80)
        self.assertEqual(len({row[1] for row in first}), 80)
        self.assertEqual(len({row[8] for row in first}), 8)
        self.assertTrue(all("Sala de Sigilo" not in row[8] for row in first))
        self.assertTrue(all("inteiramente fictício" in row[7] for row in first))


if __name__ == "__main__":
    unittest.main()
