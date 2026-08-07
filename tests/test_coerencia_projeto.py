import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from validar_coerencia_projeto import audit_project


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


if __name__ == "__main__":
    unittest.main()
