#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Valida de modo independente o ZIP code-only da comparacao robusta."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import zipfile
from pathlib import Path, PurePosixPath


EXPECTED_PACKAGE_VERSION = "mba-ia-puc-comparison-v6-rev4"
EXPECTED_STAGE5_PIPELINE = "stage5-operational-reconciliation-v6.1"
EXPECTED_STAGE5_MAPPING = "closed-destination-stage4-evidence-v3"
MANIFEST_NAME = "MANIFESTO_PACOTE.json"
REQUIRED_FILES = {
    MANIFEST_NAME,
    "common/scripts/run_stage5_llm.py",
    "common/scripts/validar_portfolio.py",
    "hpc/job_00_referencia.sh",
    "hpc/job_10_m1_legado_llama.sh",
    "hpc/job_20_m2_nativo.sh",
    "hpc/job_30_ablacao.sh",
    "hpc/job_90_avaliacao.sh",
    "hpc/job_lib.sh",
    "source/LEIA-ME.txt",
}
FORBIDDEN_EXACT = {
    "source/02_summaries.json",
    "pipeline_data/01_tickets.json",
    "pipeline_data/02_summaries.json",
}
FORBIDDEN_SUFFIXES = {
    ".csv",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".xlsx",
    ".xls",
    ".zip",
    ".gz",
}
RUNTIME_PREFIXES = (
    "logs/",
    "resultados/",
    "avaliacao/",
    "referencia/checkpoints/",
    "metodo1_legado_llama/pipeline_data/",
    "runs/",
)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _literal_string_constant(source: bytes, filename: str, name: str) -> str:
    tree = ast.parse(
        source.decode("utf-8-sig"),
        filename=filename,
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
            f"{filename}: constante literal unica {name} ausente ou invalida"
        )
    return values[0]


def validate_package(path: Path) -> dict:
    path = path.resolve()
    errors: list[str] = []
    with zipfile.ZipFile(path) as archive:
        corrupt = archive.testzip()
        if corrupt:
            errors.append(f"entrada corrompida: {corrupt}")
        infos = archive.infolist()
        names = [info.filename for info in infos]
        name_set = set(names)
        if len(names) != len(name_set):
            errors.append("nomes duplicados no ZIP")
        missing = sorted(REQUIRED_FILES - name_set)
        if missing:
            errors.append("arquivos obrigatorios ausentes: " + ", ".join(missing))
        for name in names:
            pure = PurePosixPath(name)
            if (
                pure.is_absolute()
                or ".." in pure.parts
                or "\\" in name
                or name.startswith("/")
            ):
                errors.append(f"caminho inseguro: {name}")
            lower = name.casefold()
            if name in FORBIDDEN_EXACT:
                errors.append(f"dado proibido no pacote: {name}")
            if any(lower.endswith(suffix) for suffix in FORBIDDEN_SUFFIXES):
                errors.append(f"extensao proibida no pacote: {name}")
            if (
                "_ckpt" in lower
                or "_metrics" in lower
                or lower.endswith(".env")
                or "/.env" in lower
                or "ollama_serve.log" in lower
            ):
                errors.append(f"artefato de execucao ou segredo potencial: {name}")
            if lower.startswith("source/") and name not in {
                "source/.gitkeep",
                "source/LEIA-ME.txt",
            }:
                errors.append(f"source contem arquivo nao autorizado: {name}")
            if lower.startswith(RUNTIME_PREFIXES) and not lower.endswith(
                "/.gitkeep"
            ):
                errors.append(f"output de runtime presente: {name}")

        if MANIFEST_NAME not in name_set:
            raise RuntimeError("; ".join(errors))
        manifest = json.loads(
            archive.read(MANIFEST_NAME).decode("utf-8-sig")
        )
        if manifest.get("package_version") != EXPECTED_PACKAGE_VERSION:
            errors.append(
                "package_version divergente: "
                + str(manifest.get("package_version"))
            )
        if manifest.get("name") != path.name:
            errors.append(
                f"nome do manifesto diverge do ZIP: {manifest.get('name')}"
            )
        privacy = manifest.get("privacy") or {}
        if privacy != {
            "contains_ticket_level_data": False,
            "contains_csv": False,
            "contains_env": False,
            "contains_checkpoints": False,
        }:
            errors.append("declaracao de privacidade ausente ou divergente")
        declared = manifest.get("files") or {}
        if set(declared) != name_set - {MANIFEST_NAME}:
            errors.append("conjunto de arquivos diverge do manifesto")
        for name, expected in declared.items():
            payload = archive.read(name)
            if _sha(payload) != expected.get("sha256"):
                errors.append(f"SHA divergente: {name}")
            if len(payload) != expected.get("bytes"):
                errors.append(f"tamanho divergente: {name}")

        for info in infos:
            name = info.filename
            payload = archive.read(name)
            if name.endswith(".py"):
                try:
                    ast.parse(
                        payload.decode("utf-8-sig"),
                        filename=name,
                    )
                except (SyntaxError, UnicodeDecodeError) as exc:
                    errors.append(f"Python invalido em {name}: {exc}")
            elif name.endswith(".json"):
                try:
                    json.loads(payload.decode("utf-8-sig"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    errors.append(f"JSON invalido em {name}: {exc}")
            elif name.endswith(".sh"):
                if not payload.startswith(b"#!/bin/bash\n"):
                    errors.append(f"shell sem shebang LF esperado: {name}")
                if b"\r\n" in payload:
                    errors.append(f"shell contem CRLF: {name}")

        producer_name = "common/scripts/run_stage5_llm.py"
        validator_name = "common/scripts/validar_portfolio.py"
        producer = archive.read(producer_name)
        validator = archive.read(validator_name)
        pipeline_producer = _literal_string_constant(
            producer,
            producer_name,
            "PIPELINE_VERSION",
        )
        pipeline_validator = _literal_string_constant(
            validator,
            validator_name,
            "STAGE5_PIPELINE_VERSION",
        )
        mapping_producer = _literal_string_constant(
            producer,
            producer_name,
            "CATEGORY_MAPPING_VERSION",
        )
        mapping_validator = _literal_string_constant(
            validator,
            validator_name,
            "CATEGORY_MAPPING_VERSION",
        )
        if {
            pipeline_producer,
            pipeline_validator,
        } != {EXPECTED_STAGE5_PIPELINE}:
            errors.append(
                "contrato pipeline Stage 5 divergente no ZIP: "
                f"{pipeline_producer} x {pipeline_validator}"
            )
        if {
            mapping_producer,
            mapping_validator,
        } != {EXPECTED_STAGE5_MAPPING}:
            errors.append(
                "contrato de mapeamento Stage 5 divergente no ZIP: "
                f"{mapping_producer} x {mapping_validator}"
            )
        preflight = (manifest.get("preflight") or {}).get(
            "cross_contracts"
        ) or {}
        if (
            preflight.get("stage5_pipeline_version")
            != EXPECTED_STAGE5_PIPELINE
            or preflight.get("stage5_category_mapping_version")
            != EXPECTED_STAGE5_MAPPING
            or preflight.get("producer_validator_equal") is not True
        ):
            errors.append("preflight de contratos ausente ou divergente")

        method_names = [
            name
            for name in names
            if (
                name.startswith("metodo1_legado_llama/pipeline/")
                or re.fullmatch(
                    r"common/scripts/run_stage[3-6]_[^/]+\.py",
                    name,
                )
                or name
                == "common/scripts/normalizar_stage3_comum.py"
            )
        ]
        for name in method_names:
            lowered = archive.read(name).lower()
            if any(
                term in lowered
                for term in (
                    b"sala de sigilo",
                    b"sala_sigilo",
                    b"sala sigilo",
                )
            ):
                errors.append(
                    f"item fora de escopo aparece no codigo do metodo: {name}"
                )

    if errors:
        raise RuntimeError("\n".join(f"- {error}" for error in errors))
    return {
        "status": "PASS",
        "arquivo": str(path),
        "sha256": _sha(path.read_bytes()),
        "bytes": path.stat().st_size,
        "zip_entries": len(names),
        "manifest_files": len(declared),
        "package_version": EXPECTED_PACKAGE_VERSION,
        "stage5_pipeline_version": EXPECTED_STAGE5_PIPELINE,
        "stage5_category_mapping_version": EXPECTED_STAGE5_MAPPING,
        "privacy_gate": "PASS",
        "syntax_gate": "PASS",
        "manifest_gate": "PASS",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("zip_path")
    args = parser.parse_args()
    print(
        json.dumps(
            validate_package(Path(args.zip_path)),
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
