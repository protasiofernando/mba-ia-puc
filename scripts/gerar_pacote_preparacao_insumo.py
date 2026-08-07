#!/usr/bin/env python3
"""Gera pacote code-only para regenerar o insumo Stages 1-2 no HPC.

Os três CSVs filtrados são deliberadamente excluídos e devem ser enviados por
SFTP diretamente para data/ no workspace institucional.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


DEFAULT_NAME = "mba-ia-puc_preparacao_insumo.zip"

FILES = [
    "scripts/hpc/job_pipeline.sh",
    "estudo_comparativo/hpc/job_preparar_insumo.sh",
    "requirements.txt",
    "configuracao/projeto.json",
    "configuracao/config_portfolio.json",
    "configuracao/contexto_catalogo.md",
    "scripts/projeto.py",
    "scripts/data_loader.py",
    "scripts/validar_pre_hpc.py",
    "scripts/validar_filtro_sala_sigilo_v6.py",
    "scripts/extract.py",
    "scripts/llm_client.py",
    "scripts/run_stage2_llm.py",
    "scripts/registrar_stage2_comparacao_v6.py",
    "estudo_comparativo/filtro_sala_sigilo_manifest_v6.json",
]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = (
        Path(args.out).resolve()
        if args.out
        else root / "_hpc" / "pacote" / DEFAULT_NAME
    )
    out.parent.mkdir(parents=True, exist_ok=True)

    payloads: dict[str, bytes] = {}
    for relative in FILES:
        path = root / relative
        if not path.is_file():
            raise RuntimeError(f"arquivo obrigatório ausente: {path}")
        data = path.read_bytes()
        if path.suffix == ".sh":
            data = data.replace(b"\r\n", b"\n")
        payloads[relative.replace("\\", "/")] = data

    instructions = """# PREPARAÇÃO STAGE 1-2 — v6

Este ZIP não contém CSV nem saída por chamado.

1. Extraia em um diretório remoto novo.
2. Envie separadamente os três CSVs filtrados para `data/`.
3. Valide: `python scripts/validar_filtro_sala_sigilo_v6.py`.
4. Submeta: `qsub estudo_comparativo/hpc/job_preparar_insumo.sh`.
5. Após sucesso, baixe somente o arquivo agregado
   `estudo_comparativo/preparacao_insumo/MANIFESTO_STAGE2_V6.json`.

Não copie o Stage 2 antigo da v5 e não envie o relatório privado de filtragem.
"""
    payloads["LEIA_ME_STAGE12_V6.md"] = instructions.encode("utf-8")
    manifest = {
        "package_version": "stage12-v6-code-only-v1",
        "privacy": {
            "contains_csv": False,
            "contains_ticket_level_data": False,
            "contains_env": False,
        },
        "expected_csv_destination": "data/",
        "files": {
            name: {"sha256": _sha(data), "bytes": len(data)}
            for name, data in sorted(payloads.items())
        },
    }
    payloads["MANIFESTO_PACOTE_STAGE12.json"] = (
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    with zipfile.ZipFile(
        out,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as archive:
        for name, data in sorted(payloads.items()):
            info = zipfile.ZipInfo(name)
            info.date_time = (2026, 7, 27, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)

    print(json.dumps({
        "status": "PASS",
        "arquivo": str(out),
        "sha256": _sha(out.read_bytes()),
        "bytes": out.stat().st_size,
        "n_arquivos": len(payloads),
        "contains_csv": False,
        "contains_ticket_level_data": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
