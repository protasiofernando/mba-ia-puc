#!/usr/bin/env python3
"""Gate local para preparar e manter a publicação integral do repositório.

O script não cria commit, não altera remotes e não envia arquivos. Ele valida
o conteúdo que o Git incluiria e as branches/tags locais alcançáveis. Assim, um
artefato proibido não fica invisível ao gate apenas por estar fora da ``main``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

from validar_coerencia_projeto import audit_project


ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "formacao_portfolio" / "metodo_inicial_kmeans_git_a5576c8"
SNAPSHOT_MANIFEST = SNAPSHOT / "MANIFESTO_SNAPSHOT.json"
PUBLIC_ROOT = ROOT / "resultados_publicaveis" / "estudo_comparativo"
PUBLIC_MANIFEST = ROOT / "resultados_publicaveis" / "MANIFESTO_RESULTADOS.json"

ESSENTIAL = (
    "README.md",
    "AGENTS.md",
    "formacao_portfolio/decisao_curada/feedback_portfolio.json",
    "formacao_portfolio/decisao_curada/portfolio_referencia.json",
    "configuracao/config_portfolio.json",
    "configuracao/contexto_catalogo.md",
    "configuracao/projeto.json",
    "docs/00_LEIA_PRIMEIRO_IA.md",
    "docs/MANUAL_DO_PROJETO.md",
    "docs/FLUXO_COMPLETO_MBA.md",
    "docs/RESULTADOS_COMPARACAO.md",
    "docs/ESTADO_COMPARACAO_ROBUSTA.json",
    "docs/PUBLICACAO_NOVO_REPOSITORIO.md",
    "docs/AUDITORIA_COERENCIA_PROJETO.md",
    "formacao_portfolio/README.md",
    "formacao_portfolio/MANIFESTO_ORIGEM.json",
    "formacao_portfolio/contrato_curadoria.json",
    "formacao_portfolio/metodo_inicial_kmeans_git_a5576c8/MANIFESTO_SNAPSHOT.json",
    "metodo_estatistico/pipeline/03_cluster.py",
    "pipeline_data/README.md",
    "pipeline_data/07_portfolio_final.json",
    "scripts/validar_coerencia_projeto.py",
    "estudo_comparativo/PROTOCOLO_METODOLOGICO.md",
    "estudo_comparativo/proveniencia_execucao/feedback_portfolio_executado.json.b64",
    "estudo_comparativo/proveniencia_execucao/README.md",
    "resultados_publicaveis/MANIFESTO_RESULTADOS.json",
    "resultados_publicaveis/estudo_comparativo/avaliacao/VALIDACAO_RESULTS.json",
)

FORBIDDEN_SUFFIXES = (
    ".csv",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".jsonl",
    ".zip",
    ".tar",
    ".tar.gz",
    ".tgz",
    ".7z",
    ".rar",
    ".env",
)
FORBIDDEN_NAMES = {
    "01_tickets.json",
    "02_summaries.json",
    "03_clusters.json",
    "06_classificados.json",
    "07_classificados_final.json",
}
FORBIDDEN_PARTS = {"_hpc", "_envio_hpc", "_hpc_res", "_retorno_hpc", "data"}
MARKDOWN_LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
ALLOWED_HISTORICAL_FILES = {
    ("refs/tags/formacao-a5576c8", "data_exemplo/Extracao_Jira_exemplo.csv")
}
EXPECTED_HISTORICAL_BLOBS = {
    (
        "refs/tags/formacao-a5576c8",
        "data_exemplo/Extracao_Jira_exemplo.csv",
    ): "fbf61012ff699be34ae2dc93656057446b7d164b"
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _reject_duplicate_json_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"chave JSON duplicada: {key}")
        result[key] = value
    return result


def _json(path: Path):
    return json.loads(
        path.read_text(encoding="utf-8-sig"),
        object_pairs_hook=_reject_duplicate_json_keys,
    )


def _git_publishable_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return sorted(
        (ROOT / line.strip()).resolve()
        for line in result.stdout.splitlines()
        if line.strip() and (ROOT / line.strip()).is_file()
    )


def _verify_manifest(root: Path, manifest_path: Path, failures: list[str]) -> int:
    manifest = _json(manifest_path)
    count = 0
    for relative, expected in manifest.get("files", {}).items():
        path = root / relative
        count += 1
        if not path.is_file():
            failures.append(f"manifesto: ausente {path.relative_to(ROOT)}")
            continue
        actual_bytes = path.stat().st_size
        if actual_bytes != expected["bytes"]:
            failures.append(
                f"manifesto: bytes divergentes em {path.relative_to(ROOT)} "
                f"({actual_bytes} != {expected['bytes']})"
            )
        actual_sha = _sha256(path)
        if actual_sha != expected["sha256"]:
            failures.append(f"manifesto: SHA-256 divergente em {path.relative_to(ROOT)}")
    return count


def _verify_markdown_links(files: list[Path], failures: list[str]) -> int:
    checked = 0
    for path in files:
        if path.suffix.lower() != ".md" or SNAPSHOT in path.parents:
            continue
        checked += 1
        text = path.read_text(encoding="utf-8-sig")
        for raw_target in MARKDOWN_LINK.findall(text):
            target = raw_target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            resolved = (path.parent / target).resolve()
            try:
                resolved.relative_to(ROOT.resolve())
            except ValueError:
                failures.append(f"link sai do repositório: {path.relative_to(ROOT)} -> {target}")
                continue
            if not resolved.exists():
                failures.append(f"link quebrado: {path.relative_to(ROOT)} -> {target}")
    return checked


def _verify_relative_publication_path(
    relative: Path | PurePosixPath,
    failures: list[str],
    context: str = "publicação",
) -> None:
    relative_posix = relative.as_posix()
    if (context, relative_posix) in ALLOWED_HISTORICAL_FILES:
        return
    lowered = relative_posix.lower()
    parts = {part.lower() for part in relative.parts}
    suffix_forbidden = any(lowered.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES)
    if suffix_forbidden and relative.name != ".env.example":
        failures.append(f"{context}: extensão proibida {relative_posix}")
    if relative.name.lower() in FORBIDDEN_NAMES:
        failures.append(f"{context}: artefato por chamado proibido {relative_posix}")
    if parts & FORBIDDEN_PARTS:
        failures.append(f"{context}: diretório sensível proibido {relative_posix}")
    if "checkpoint" in relative.name.lower():
        failures.append(f"{context}: checkpoint proibido {relative_posix}")


def _verify_publication_set(files: list[Path], failures: list[str]) -> None:
    for path in files:
        _verify_relative_publication_path(path.relative_to(ROOT), failures)


def _verify_git_refs(failures: list[str]) -> tuple[int, int]:
    refs_proc = subprocess.run(
        [
            "git",
            "for-each-ref",
            "--format=%(refname)",
            "refs/heads",
            "refs/tags",
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    refs = [line.strip() for line in refs_proc.stdout.splitlines() if line.strip()]
    files_checked = 0
    for ref in refs:
        tree_proc = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", ref],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        for raw in tree_proc.stdout.splitlines():
            if not raw.strip():
                continue
            files_checked += 1
            _verify_relative_publication_path(
                PurePosixPath(raw.strip()), failures, context=ref
            )

    historical_ref = "refs/tags/formacao-a5576c8"
    if historical_ref in refs:
        note_proc = subprocess.run(
            ["git", "show", f"{historical_ref}:data_exemplo/README.md"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        note = note_proc.stdout.lower()
        if "15 chamados fictícios" not in note or "nenhum dado real" not in note:
            failures.append(
                "tag de formação: exceção CSV não declarada como sintética e sem dado real"
            )
        for (ref, path), expected_blob in EXPECTED_HISTORICAL_BLOBS.items():
            blob_proc = subprocess.run(
                ["git", "rev-parse", f"{ref}:{path}"],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            if blob_proc.stdout.strip() != expected_blob:
                failures.append(
                    f"tag de formação: conteúdo sintético inesperado em {path}"
                )
    return len(refs), files_checked


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--full",
        action="store_true",
        help="também executa a suíte pytest sem criar cache",
    )
    args = parser.parse_args()
    failures: list[str] = []

    for relative in ESSENTIAL:
        if not (ROOT / relative).is_file():
            failures.append(f"estrutura: ausente {relative}")

    publishable = _git_publishable_files()
    _verify_publication_set(publishable, failures)
    git_refs_checked, git_ref_files_checked = _verify_git_refs(failures)

    json_checked = 0
    for path in publishable:
        if path.suffix.lower() != ".json":
            continue
        json_checked += 1
        try:
            _json(path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            failures.append(f"JSON inválido: {path.relative_to(ROOT)}: {exc}")

    snapshot_files = _verify_manifest(SNAPSHOT, SNAPSHOT_MANIFEST, failures)
    public_files = _verify_manifest(PUBLIC_ROOT, PUBLIC_MANIFEST, failures)

    snapshot_manifest = _json(SNAPSHOT_MANIFEST)
    if snapshot_manifest.get("commit") != "a5576c83d47e9eda7e6087b59e57bac65c04e1b4":
        failures.append("snapshot: commit histórico inesperado")

    result_manifest = _json(PUBLIC_MANIFEST)
    if result_manifest.get("source_job90") != "2234.HPCGPU":
        failures.append("resultados: Job 90 inesperado")
    if result_manifest.get("validation_status") != "PASS":
        failures.append("resultados: manifesto não está PASS")
    if result_manifest.get("validation_checks") != 302:
        failures.append("resultados: quantidade de checks diferente de 302")
    if result_manifest.get("validation_failures") != 0:
        failures.append("resultados: manifesto registra falhas")
    if not all(value is False for value in result_manifest.get("privacy", {}).values()):
        failures.append("resultados: gate de privacidade não está integralmente falso")

    validation = _json(PUBLIC_ROOT / "avaliacao" / "VALIDACAO_RESULTS.json")
    if validation.get("status") != "PASS" or validation.get("failures") != 0:
        failures.append("resultados: VALIDACAO_RESULTS não está PASS/zero")
    if len(validation.get("checks", [])) != 302:
        failures.append("resultados: VALIDACAO_RESULTS não contém 302 checks")
    if any(check.get("status") != "PASS" for check in validation.get("checks", [])):
        failures.append("resultados: há check final diferente de PASS")

    package = _json(PUBLIC_ROOT / "MANIFESTO_PACOTE.json")
    decision_dir = ROOT / "formacao_portfolio" / "decisao_curada"
    expected_reference = package.get("files", {}).get(
        "portfolio_referencia.json", {}
    ).get("sha256")
    if (
        not expected_reference
        or _sha256(decision_dir / "portfolio_referencia.json")
        != expected_reference
    ):
        failures.append("alvo congelado: portfolio_referencia.json diverge do pacote")
    executed_feedback = base64.b64decode(
        (
            ROOT
            / "estudo_comparativo"
            / "proveniencia_execucao"
            / "feedback_portfolio_executado.json.b64"
        )
        .read_text(encoding="ascii")
        .strip(),
        validate=True,
    )
    expected_feedback = package.get("files", {}).get(
        "feedback_portfolio.json", {}
    ).get("sha256")
    if (
        not expected_feedback
        or hashlib.sha256(executed_feedback).hexdigest() != expected_feedback
    ):
        failures.append("alvo congelado: feedback executado não foi preservado")

    coherence = audit_project()
    if coherence.get("status") != "PASS":
        for row in coherence.get("details", []):
            if row.get("status") == "FAIL":
                failures.append(
                    f"coerência: {row.get('check')}: {row.get('detail', '')}"
                )

    markdown_checked = _verify_markdown_links(publishable, failures)

    tests = "SKIPPED"
    if args.full:
        test_env = os.environ.copy()
        test_env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
            cwd=ROOT,
            env=test_env,
        )
        tests = "PASS" if proc.returncode == 0 else "FAIL"
        if proc.returncode != 0:
            failures.append("testes: pytest falhou")

    status = "PASS" if not failures else "FAIL"
    report = {
        "status": status,
        "publishable_files_checked": len(publishable),
        "git_refs_checked": git_refs_checked,
        "git_ref_files_checked": git_ref_files_checked,
        "historical_synthetic_csv_exceptions": len(ALLOWED_HISTORICAL_FILES),
        "json_checked": json_checked,
        "markdown_checked": markdown_checked,
        "historical_snapshot_files_checked": snapshot_files,
        "public_result_files_checked": public_files,
        "final_result_checks": len(validation.get("checks", [])),
        "coherence_checks": coherence.get("checks", 0),
        "pytest": tests,
        "git_upload_performed": False,
        "failures": failures,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
