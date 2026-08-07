#!/usr/bin/env python3
"""Audita no Git a execucao historica que precedeu a comparacao robusta."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
MANIFEST = ROOT / "formacao_portfolio" / "MANIFESTO_ORIGEM.json"


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return result.stdout


def _show_json(commit: str, path: str):
    return json.loads(_git("show", f"{commit}:{path}"))


def main() -> int:
    try:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
        historical = manifest["historical_formation"]
        commit = historical["git_commit_evidence"]
        _git("cat-file", "-e", f"{commit}^{{commit}}")
        audited = historical["audited_artifacts_in_commit"]
        for record in audited.values():
            actual_blob = _git("rev-parse", f"{commit}:{record['path']}").strip()
            if actual_blob != record["git_blob_sha1"]:
                raise RuntimeError(
                    f"blob divergente em {record['path']}: "
                    f"esperado={record['git_blob_sha1']} obtido={actual_blob}"
                )

        candidate = _show_json(commit, audited["automatic_candidate"]["path"])
        metadata = candidate["metadata"]
        portfolio = candidate["recomendacao"]["portfolio_otimizado"]
        checks = {
            "total_tickets": metadata["total_tickets"],
            "current_catalog_categories": metadata["n_categorias_atuais"],
            "natural_groups": metadata["n_grupos_naturais"],
            "suggested_portfolio_items": len(portfolio),
        }
        for key, actual in checks.items():
            expected = audited["automatic_candidate"][key]
            if actual != expected:
                raise RuntimeError(
                    f"metadado historico divergente {key}: "
                    f"esperado={expected} obtido={actual}"
                )

        stage7 = _show_json(commit, audited["materialized_stage7"]["path"])
        if stage7["metadata"]["total_classificados"] != audited[
            "materialized_stage7"
        ]["total_classified"]:
            raise RuntimeError("total historico do Stage 7 divergente")
        if len(stage7["portfolio_final"]) != audited["materialized_stage7"][
            "initial_curated_categories"
        ]:
            raise RuntimeError("numero de categorias da primeira curadoria diverge")

        stage3_code = _git("show", f"{commit}:pipeline/03_cluster.py")
        stage7_code = _git("show", f"{commit}:pipeline/07_finalize_portfolio.py")
        for marker in ("bge-m3", "KMeans", "silhouette_score"):
            if marker not in stage3_code:
                raise RuntimeError(f"marcador estatistico ausente: {marker}")
        for marker in ("feedback_portfolio.json", "07_portfolio_final.json"):
            if marker not in stage7_code:
                raise RuntimeError(f"marcador de curadoria ausente: {marker}")

        print(json.dumps({
            "status": "PASS",
            "commit": commit,
            "candidate": checks,
            "stage7_total_classified": stage7["metadata"]["total_classificados"],
            "initial_curated_categories": len(stage7["portfolio_final"]),
            "interpretation": (
                "candidato estatistico e primeira curadoria comprovados; "
                "portfolio final atual e refinamento posterior"
            ),
        }, ensure_ascii=False, indent=2))
        return 0
    except (
        OSError,
        KeyError,
        TypeError,
        ValueError,
        RuntimeError,
        subprocess.CalledProcessError,
    ) as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
