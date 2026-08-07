#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera o ZIP code-only da comparacao robusta para o HPC.

O pacote nunca inclui CSV, 02_summaries, outputs por chamado, checkpoints,
metricas de rodadas anteriores, banco ou .env.
"""

from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import subprocess
import zipfile
from pathlib import Path


PACKAGE_VERSION = "mba-ia-puc-comparison-v6-rev4"
# O identificador interno acima ficou congelado no protocolo executado. O nome
# externo abaixo identifica a revisão final efetivamente executada.
DEFAULT_NAME = "mba-ia-puc_rev6_20260803.zip"

COMMON_SCRIPTS = [
    "llm_client.py",
    "projeto.py",
    "discovery_contract.py",
    "run_stage3_llm.py",
    "run_stage3_kmeans_fair.py",
    "normalizar_stage3_comum.py",
    "run_stage4_llm.py",
    "run_stage5_llm.py",
    "run_stage6_llm.py",
    "validar_portfolio.py",
    "classificar_referencia_consenso.py",
    "preparar_escopo_deterministico_v6.py",
    "preparar_execucoes_comparacao.py",
    "avaliar_comparacao_robusta.py",
    "auditar_campos_portfolio.py",
    "validar_comparacao_robusta.py",
    "validar_ambiente_comparacao.py",
    "validar_insumo_comparacao.py",
    "validar_artefato_retomada.py",
    "validar_pacote_comparacao.py",
]

LEGACY_PIPELINE = [
    "__init__.py",
    "llm_client.py",
    "03_cluster.py",
    "04_label_clusters.py",
    "05_compare_portfolio.py",
    "06_classify_portfolio.py",
]

COMPARISON_FILES = [
    "decision_rules_v1.json",
    "experimento_config.json",
    "filtro_sala_sigilo_manifest_v6.json",
    "PROTOCOLO_METODOLOGICO.md",
    "DOSSIE_AUDITORIA.md",
    "README.md",
    "requirements_comparacao.txt",
    "RUNBOOK_HPC.md",
    "hpc/job_00_referencia.sh",
    "hpc/job_10_m1_legado_llama.sh",
    "hpc/job_20_m2_nativo.sh",
    "hpc/job_30_ablacao.sh",
    "hpc/job_90_avaliacao.sh",
    "hpc/job_lib.sh",
    "source/LEIA-ME.txt",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")


def _literal_string_constant(path: Path, name: str) -> str:
    """Le uma constante string de modulo sem importar codigo operacional."""
    tree = ast.parse(
        path.read_text(encoding="utf-8-sig"),
        filename=str(path),
    )
    values = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [
                target.id
                for target in node.targets
                if isinstance(target, ast.Name)
            ]
            if name in targets and isinstance(node.value, ast.Constant):
                values.append(node.value.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and isinstance(node.value, ast.Constant)
        ):
            values.append(node.value.value)
    if len(values) != 1 or not isinstance(values[0], str):
        raise RuntimeError(
            f"constante literal unica {name} ausente ou invalida em {path}"
        )
    return values[0]


def _validate_cross_contracts(root: Path) -> dict[str, str]:
    """Impede empacotar produtor e validador com contratos divergentes."""
    producer = root / "scripts" / "run_stage5_llm.py"
    validator = root / "scripts" / "validar_portfolio.py"
    values = {
        "stage5_pipeline_producer": _literal_string_constant(
            producer,
            "PIPELINE_VERSION",
        ),
        "stage5_pipeline_validator": _literal_string_constant(
            validator,
            "STAGE5_PIPELINE_VERSION",
        ),
        "stage5_mapping_producer": _literal_string_constant(
            producer,
            "CATEGORY_MAPPING_VERSION",
        ),
        "stage5_mapping_validator": _literal_string_constant(
            validator,
            "CATEGORY_MAPPING_VERSION",
        ),
    }
    expected = {
        "stage5_pipeline": "stage5-operational-reconciliation-v6.1",
        "stage5_mapping": "closed-destination-stage4-evidence-v3",
    }
    if (
        values["stage5_pipeline_producer"]
        != values["stage5_pipeline_validator"]
        or values["stage5_pipeline_producer"] != expected["stage5_pipeline"]
    ):
        raise RuntimeError(
            "contrato Stage 5 divergente entre produtor, validador e "
            f"release: {values}"
        )
    if (
        values["stage5_mapping_producer"]
        != values["stage5_mapping_validator"]
        or values["stage5_mapping_producer"] != expected["stage5_mapping"]
    ):
        raise RuntimeError(
            "contrato de mapeamento Stage 5 divergente entre produtor, "
            f"validador e release: {values}"
        )
    return {
        "stage5_pipeline_version": expected["stage5_pipeline"],
        "stage5_category_mapping_version": expected["stage5_mapping"],
        "producer_validator_equal": True,
    }


def _sanitized_config(path: Path, keep_mandatory: bool) -> bytes:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    text = str(data.get("infra_context", {}).get("texto_contexto", ""))
    marker = "\n8. SALA DE SIGILO"
    if marker not in text:
        raise RuntimeError(
            f"nao foi possivel localizar a secao 8 de Sala em {path}"
        )
    clean = text.split(marker, 1)[0].rstrip()
    if "SALA DE SIGILO" in clean.upper():
        raise RuntimeError(f"mencao residual a Sala no contexto sanitizado: {path}")
    data["infra_context"]["texto_contexto"] = clean
    data["_comparison_scope"] = {
        "version": PACKAGE_VERSION,
        "fixed_item_removed_from_method_prompts": "sala_sigilo",
        "tickets_removed_before_stage3": True,
    }
    if not keep_mandatory:
        data["categorias_obrigatorias"] = []
    return _json_bytes(data)


def _git_info(root: Path) -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
        dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip())
        return {"commit": commit, "worktree_dirty": dirty}
    except Exception:
        return {"commit": None, "worktree_dirty": None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--out",
        default=None,
        help="ZIP de saida; padrao _hpc/pacote/<nome versionado>",
    )
    parser.add_argument(
        "--stage2-manifest",
        required=True,
        help=(
            "MANIFESTO_STAGE2_V6.json agregado, baixado do HPC após a "
            "regeneração dos Stages 1-2"
        ),
    )
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    contract_preflight = _validate_cross_contracts(root)
    out = (
        Path(args.out).resolve()
        if args.out
        else root / "_hpc" / "pacote" / DEFAULT_NAME
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    files: dict[str, bytes] = {}
    stage2_manifest_path = Path(args.stage2_manifest).resolve()
    stage2_manifest = json.loads(
        stage2_manifest_path.read_text(encoding="utf-8-sig")
    )
    if (
        stage2_manifest.get("schema_version")
        != "stage2-comparison-input-manifest-v1"
        or stage2_manifest.get("experiment_generation") != "v6"
        or stage2_manifest.get("scope_method")
        != "deterministic_structured_request_type_prefilter"
        or stage2_manifest.get("llm_used_for_scope") is not False
        or int(stage2_manifest.get("stage2_count", 0)) != 1456
        or stage2_manifest.get("stage2_contract_version") != "intent-blind-v2"
        or stage2_manifest.get("stage2_model") != "llama3.3:70b"
    ):
        raise RuntimeError("manifesto do Stage 2 não satisfaz o contrato v6")
    stage2_sha = str(stage2_manifest.get("stage2_sha256", "")).lower()
    if len(stage2_sha) != 64 or any(ch not in "0123456789abcdef" for ch in stage2_sha):
        raise RuntimeError("SHA-256 do Stage 2 ausente ou inválido")
    stage2_model_digest = str(
        stage2_manifest.get("stage2_model_digest", "")
    ).lower()
    if (
        len(stage2_model_digest) != 64
        or any(ch not in "0123456789abcdef" for ch in stage2_model_digest)
    ):
        raise RuntimeError("digest Ollama do modelo Stage 2 ausente ou inválido")

    def add_bytes(archive_name: str, data: bytes) -> None:
        name = archive_name.replace("\\", "/").lstrip("/")
        if name in files:
            raise RuntimeError(f"arquivo duplicado no pacote: {name}")
        files[name] = data

    def add_file(source: Path, archive_name: str) -> None:
        data = source.read_bytes()
        if source.suffix == ".sh":
            data = data.replace(b"\r\n", b"\n")
        add_bytes(archive_name, data)

    comparison_dir = root / "estudo_comparativo"
    filter_manifest_path = (
        comparison_dir / "filtro_sala_sigilo_manifest_v6.json"
    )
    if (
        stage2_manifest.get("scope_manifest_sha256")
        != _sha(filter_manifest_path.read_bytes())
    ):
        raise RuntimeError(
            "manifesto do Stage 2 foi gerado com outro manifesto de escopo"
        )
    experiment_config = json.loads(
        (comparison_dir / "experimento_config.json").read_text(
            encoding="utf-8-sig"
        )
    )
    if int(experiment_config["input"]["expected_count"]) != 1456:
        raise RuntimeError("cardinalidade v6 inconsistente no experimento")
    experiment_config["input"]["expected_sha256"] = stage2_sha
    experiment_config["input"]["stage2_generation"] = {
        "contract_version": stage2_manifest["stage2_contract_version"],
        "model": stage2_manifest["stage2_model"],
        "model_digest": stage2_model_digest,
        "temperature": stage2_manifest["stage2_temperature"],
        "stage2_script_sha256": stage2_manifest[
            "stage2_script_sha256"
        ],
        "llm_client_sha256": stage2_manifest["llm_client_sha256"],
        "config_portfolio_sha256": stage2_manifest[
            "config_portfolio_sha256"
        ],
    }

    # Lista positiva: nunca empacotar por varredura diretórios que podem passar
    # a conter resultados, logs, checkpoints ou dados por chamado.
    for relative in COMPARISON_FILES:
        source = comparison_dir / relative
        if not source.is_file():
            raise RuntimeError(f"arquivo obrigatorio ausente: {source}")
        if relative == "experimento_config.json":
            add_bytes(relative, _json_bytes(experiment_config))
        else:
            add_file(source, relative)
    add_file(
        root / "docs" / "APENDICE_TECNICO.md",
        "APENDICE_TECNICO.md",
    )

    decision_dir = root / "formacao_portfolio" / "decisao_curada"
    config_dir = root / "configuracao"
    add_file(decision_dir / "portfolio_referencia.json", "portfolio_referencia.json")
    add_file(decision_dir / "feedback_portfolio.json", "feedback_portfolio.json")
    add_file(config_dir / "projeto.json", "common/projeto.json")
    add_file(config_dir / "contexto_catalogo.md", "common/contexto_catalogo.md")
    add_bytes(
        "common/config_portfolio.json",
        _sanitized_config(config_dir / "config_portfolio.json", keep_mandatory=False),
    )
    for name in COMMON_SCRIPTS:
        add_file(root / "scripts" / name, f"common/scripts/{name}")
    add_file(
        root / "scripts" / "run_stage2_llm.py",
        "provenance/stage2_code/run_stage2_llm.py",
    )

    add_file(
        root / "metodo_estatistico" / "README.md",
        "metodo1_legado_llama/README.md",
    )
    add_bytes(
        "metodo1_legado_llama/config_portfolio.json",
        _sanitized_config(
            root / "metodo_estatistico" / "config_portfolio.json",
            keep_mandatory=True,
        ),
    )
    for name in LEGACY_PIPELINE:
        add_file(
            root / "metodo_estatistico" / "pipeline" / name,
            f"metodo1_legado_llama/pipeline/{name}",
        )

    method_code = [
        name for name in files
        if (
            name.startswith("metodo1_legado_llama/pipeline/")
            or name in {
                "common/scripts/run_stage3_llm.py",
                "common/scripts/run_stage3_kmeans_fair.py",
                "common/scripts/normalizar_stage3_comum.py",
                "common/scripts/run_stage4_llm.py",
                "common/scripts/run_stage5_llm.py",
                "common/scripts/run_stage6_llm.py",
            }
        )
    ]
    forbidden_scope_terms = (
        b"sala de sigilo",
        b"sala_sigilo",
        b"sala sigilo",
    )
    for name in method_code:
        lowered = files[name].lower()
        if any(term in lowered for term in forbidden_scope_terms):
            raise RuntimeError(
                "mencao a item fora de escopo no codigo entregue ao metodo: "
                + name
            )

    config = experiment_config
    empty_paths = [
        "source/.gitkeep",
        "referencia/checkpoints/.gitkeep",
        "avaliacao/.gitkeep",
        "resultados/.gitkeep",
        "logs/.gitkeep",
        "metodo1_legado_llama/pipeline_data/.gitkeep",
    ]
    for run in config.get("runs", []):
        empty_paths.append(
            f"{str(run['pipeline_data']).rstrip('/')}/.gitkeep"
        )
    for name in empty_paths:
        if name not in files:
            add_bytes(name, b"")

    manifest = {
        "package_version": PACKAGE_VERSION,
        "name": out.name,
        "git": _git_info(root),
        "preflight": {
            "cross_contracts": contract_preflight,
        },
        "privacy": {
            "contains_ticket_level_data": False,
            "contains_csv": False,
            "contains_env": False,
            "contains_checkpoints": False,
        },
        "files": {
            name: {"sha256": _sha(data), "bytes": len(data)}
            for name, data in sorted(files.items())
        },
    }
    add_bytes("MANIFESTO_PACOTE.json", _json_bytes(manifest))

    with zipfile.ZipFile(
        out,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name, data in sorted(files.items()):
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 7, 30, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            # rw-r--r-- para arquivos; executavel sera aplicado pelo runbook.
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)

    print(json.dumps({
        "arquivo": str(out),
        "sha256": _sha(out.read_bytes()),
        "bytes": out.stat().st_size,
        "n_arquivos": len(files),
        "ticket_level_data": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
