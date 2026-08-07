#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Congela e verifica o ambiente comum usado pelos jobs da comparação."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


VERSION = "comparison-environment-lock-v1"


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _model_digests(tags_path: Path, expected: dict[str, str]) -> dict:
    tags = _load(tags_path).get("models") or []
    output = {}
    for role, name in expected.items():
        matches = [
            row for row in tags
            if (
                str(row.get("name") or row.get("model") or "") == name
                or (
                    ":" not in name
                    and str(row.get("name") or row.get("model") or "")
                    == f"{name}:latest"
                )
            )
        ]
        digest = (
            str(matches[0].get("digest") or "").strip()
            if len(matches) == 1 else ""
        )
        if not digest:
            raise RuntimeError(
                f"modelo esperado ausente ou sem digest exato: {role}={name}"
            )
        output[role] = {
            "name": name,
            "resolved_name": str(
                matches[0].get("name") or matches[0].get("model") or ""
            ),
            "digest": digest,
        }
    if (
        output["reasoning"]["digest"]
        == output["structured_json"]["digest"]
    ):
        raise RuntimeError(
            "modelos reasoning e structured_json devem ter digests distintos"
        )
    return output


def _snapshot(base: Path, metrics: Path) -> dict:
    config = _load(base / "experimento_config.json")
    expected_models = config.get("models") or {}
    required_roles = {"reasoning", "structured_json", "embedding"}
    if set(expected_models) != required_roles:
        raise RuntimeError(
            "experimento_config.models deve declarar reasoning, "
            "structured_json e embedding"
        )
    required_files = {
        "ollama": metrics / "_environment_ollama_tags.json",
        "ollama_version": metrics / "_environment_ollama_version.json",
        "python": metrics / "_environment_python.txt",
        "pip": metrics / "_environment_pip_freeze.txt",
        "numpy": metrics / "_environment_numpy_config.txt",
        "code": metrics / "_environment_code_sha256.txt",
        "gpu": metrics / "_environment_gpu_name.txt",
        "gpu_identity": metrics / "_environment_gpu_identity.txt",
        "cpu": metrics / "_environment_lscpu.txt",
        "package": base / "MANIFESTO_PACOTE.json",
    }
    missing = [
        name for name, path in required_files.items() if not path.is_file()
    ]
    if missing:
        raise RuntimeError(
            "arquivos de ambiente ausentes: " + ", ".join(missing)
        )
    gpu_name = required_files["gpu"].read_text(
        encoding="utf-8", errors="replace"
    ).strip()
    if not gpu_name:
        raise RuntimeError("nome da GPU vazio")
    lscpu_lines = required_files["cpu"].read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()
    cpu_model = next(
        (
            line.split(":", 1)[1].strip()
            for line in lscpu_lines
            if line.casefold().startswith("model name:")
        ),
        "",
    )
    if not cpu_model:
        raise RuntimeError("modelo de CPU ausente no lscpu")
    ollama_version = _load(
        required_files["ollama_version"]
    ).get("version")
    if not str(ollama_version or "").strip():
        raise RuntimeError("versao do Ollama ausente")
    gpu_identity = required_files["gpu_identity"].read_text(
        encoding="utf-8", errors="replace"
    ).strip()
    if not gpu_identity:
        raise RuntimeError("identidade completa da GPU ausente")
    python_version = required_files["python"].read_text(
        encoding="utf-8", errors="replace"
    ).strip()
    if not python_version:
        raise RuntimeError("versao do Python ausente")
    return {
        "version": VERSION,
        "models": _model_digests(
            required_files["ollama"],
            expected_models,
        ),
        "ollama_version": ollama_version,
        "gpu_name": gpu_name,
        "gpu_identity": gpu_identity,
        "cpu_model": cpu_model,
        "python": python_version,
        "pip_freeze_sha256": _sha(required_files["pip"]),
        "numpy_blas_config_sha256": _sha(required_files["numpy"]),
        "code_provenance_sha256": _sha(required_files["code"]),
        "package_manifest_sha256": _sha(required_files["package"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", required=True)
    parser.add_argument("--metrics-dir", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--mode", choices=("freeze", "verify"), required=True)
    args = parser.parse_args()

    base = Path(args.base).resolve()
    metrics = Path(args.metrics_dir).resolve()
    lock_path = base / "AMBIENTE_CONGELADO.json"
    snapshot = _snapshot(base, metrics)
    result = {
        "version": VERSION,
        "run_id": args.run_id,
        "mode": args.mode,
        "snapshot": snapshot,
        "status": "PASS",
    }
    if args.mode == "freeze":
        if lock_path.exists() and _load(lock_path) != snapshot:
            raise SystemExit(
                "ERRO: ambiente congelado existente diverge da rodada atual; "
                "use um diretorio novo"
            )
        lock_path.write_text(
            json.dumps(snapshot, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    else:
        if not lock_path.exists():
            raise SystemExit(
                "ERRO: AMBIENTE_CONGELADO.json ausente; rode primeiro job_00"
            )
        expected = _load(lock_path)
        if expected != snapshot:
            result["status"] = "FAIL"
            result["expected"] = expected
            (metrics / "_environment_verification.json").write_text(
                json.dumps(result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            raise SystemExit(
                "ERRO: codigo, modelo, dependencias ou GPU divergem do "
                "ambiente congelado no job_00"
            )
    (metrics / "_environment_verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
