#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera uma base demonstrativa inteiramente artificial para o dashboard.

O gerador usa somente o catálogo agregado e publicável de
``pipeline_data/07_portfolio_final.json``. Não lê chamados, resumos, durações,
categorias antigas ou qualquer outro artefato privado. Os textos, pessoas,
datas, tempos e interações são criados por regras pseudoaleatórias
determinísticas e não representam casos reais.

A saída conserva apenas o schema de importação do Jira esperado pelo projeto e
permanece ignorada pelo Git, conforme a política de publicação code-only.

Uso:
    python scripts/gerar_base_sintetica.py
    python scripts/gerar_base_sintetica.py --amostra 400 --seed 42
    python scripts/gerar_base_sintetica.py --saida C:/temp/demo.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from projeto import projeto_dir

    ROOT = projeto_dir()
except Exception:
    ROOT = Path(__file__).resolve().parent.parent

PORTFOLIO_PATH = ROOT / "pipeline_data" / "07_portfolio_final.json"
DEFAULT_OUTPUT = ROOT / "data_exemplo" / "dti-pesquisa__sintetica.csv"

COLS = [
    "Resumo",
    "Chave do item",
    "Situação",
    "Responsável",
    "Solicitante",
    "Criado",
    "Resolvido",
    "Descrição",
    "Customer Request Type",
    "Comentário",
    "Comentário.1",
    "Comentário.2",
    "Comentário.3",
]

_PII_PATTERNS = {
    "email": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    "url": re.compile(r"https?://\S+", re.IGNORECASE),
    "ipv4": re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
}

_TITLE_PATTERNS = (
    "Exemplo sintético — {nome}",
    "Demonstração de atendimento — {nome}",
    "Cenário fictício para {nome}",
    "Teste do fluxo — {nome}",
)

_ACTION_PATTERNS = (
    "validar o encaminhamento e os campos obrigatórios",
    "demonstrar o carregamento no painel local",
    "testar a classificação sem utilizar dados institucionais",
    "exercitar o fluxo de atendimento em ambiente de demonstração",
)

_COMPLEXITY_HOURS = {
    "baixa": 18.0,
    "média": 42.0,
    "media": 42.0,
    "alta": 72.0,
}


def _load_public_services(path: Path) -> list[dict]:
    """Carrega apenas serviços analíticos do agregado público."""
    with path.open("r", encoding="utf-8-sig") as handle:
        payload = json.load(handle)

    services = [
        item
        for item in payload.get("portfolio_final", [])
        if not item.get("fora_da_analise") and int(item.get("volume") or 0) > 0
    ]
    if not services:
        raise ValueError(f"Nenhum serviço analítico encontrado em {path}")
    return services


def _service_sequence(services: list[dict], size: int, rng: random.Random) -> list[dict]:
    """Garante todas as categorias e completa a amostra por pesos agregados."""
    if size < len(services):
        raise ValueError(
            f"--amostra deve ser pelo menos {len(services)} para representar "
            "todas as categorias analíticas"
        )

    sequence = list(services)
    remaining = size - len(sequence)
    if remaining:
        weights = [float(item.get("volume") or 1) for item in services]
        sequence.extend(rng.choices(services, weights=weights, k=remaining))
    rng.shuffle(sequence)
    return sequence


def _format_date(value: datetime) -> str:
    return value.strftime("%d/%m/%Y %H:%M")


def _duration_hours(service: dict, interactions: int, rng: random.Random) -> float:
    """Cria duração fictícia; nenhuma distribuição privada é reutilizada."""
    baseline = _COMPLEXITY_HOURS.get(str(service.get("complexidade", "")).lower(), 36.0)
    interaction_factor = 1.0 if interactions <= 1 else 1.8 + (interactions - 2) * 0.45
    noise = rng.lognormvariate(0.0, 0.55)
    return round(min(720.0, max(0.5, baseline * interaction_factor * noise)), 2)


def _make_description(service: dict, index: int, rng: random.Random) -> str:
    action = rng.choice(_ACTION_PATTERNS)
    public_scope = str(service.get("quando_usar") or service.get("descricao") or "").strip()
    return (
        "Chamado inteiramente fictício, criado automaticamente para demonstração. "
        f"O cenário {index:04d} serve para {action}. "
        f"Escopo público usado como referência: {public_scope}"
    )


def _make_row(index: int, service: dict, rng: random.Random) -> list[str]:
    created_start = datetime(2024, 1, 1, 8, 0)
    created = created_start + timedelta(
        days=rng.randint(0, 910),
        minutes=rng.randint(0, 12 * 60),
    )
    interactions = rng.choices((0, 1, 2, 3, 4), weights=(12, 28, 30, 20, 10), k=1)[0]
    is_resolved = rng.random() < 0.92
    if is_resolved:
        resolved = created + timedelta(hours=_duration_hours(service, interactions, rng))
        resolved_text = _format_date(resolved)
        status = rng.choice(("Resolvido", "Fechado"))
    else:
        resolved_text = ""
        status = "Em andamento"

    name = str(service["nome"])
    title = rng.choice(_TITLE_PATTERNS).format(nome=name)
    description = _make_description(service, index, rng)
    comments = [
        f"Interação sintética {number}: acompanhamento fictício do cenário {index:04d}."
        for number in range(1, interactions + 1)
    ]
    comments.extend([""] * (4 - len(comments)))

    return [
        title,
        f"SYN-{index:04d}",
        status,
        f"Atendente Fictício {rng.randint(1, 12):02d}",
        f"Solicitante Fictício {rng.randint(1, 120):03d}",
        _format_date(created),
        resolved_text,
        description,
        name,
        *comments,
    ]


def _validate(rows: list[list[str]]) -> None:
    """Falha antes da gravação se o contrato sintético for violado."""
    keys = [row[1] for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("Chaves sintéticas duplicadas")
    if not all(re.fullmatch(r"SYN-\d{4,}", key) for key in keys):
        raise ValueError("Chave fora do padrão sintético")
    if any("Sala de Sigilo" in row[8] for row in rows):
        raise ValueError("Sala de Sigilo não pode integrar a base analítica")

    text = "\n".join(" ".join((row[0], row[7], *row[9:])) for row in rows)
    detected = [name for name, pattern in _PII_PATTERNS.items() if pattern.search(text)]
    if detected:
        raise ValueError(f"Padrões proibidos detectados: {', '.join(detected)}")


def generate(size: int, seed: int) -> list[list[str]]:
    rng = random.Random(seed)
    services = _load_public_services(PORTFOLIO_PATH)
    sequence = _service_sequence(services, size, rng)
    rows = [_make_row(index, service, rng) for index, service in enumerate(sequence, 1)]
    _validate(rows)
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Gera CSV demonstrativo totalmente artificial para o dashboard."
    )
    parser.add_argument(
        "--amostra",
        type=int,
        default=240,
        help="Quantidade de chamados fictícios (padrão: 240; mínimo: 8).",
    )
    parser.add_argument("--seed", type=int, default=42, help="Seed determinística.")
    parser.add_argument(
        "--saida",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Caminho do CSV gerado (padrão: data_exemplo/dti-pesquisa__sintetica.csv).",
    )
    args = parser.parse_args()

    rows = generate(args.amostra, args.seed)
    output = args.saida.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="^")
        writer.writerow(COLS)
        writer.writerows(rows)

    categories = len({row[8] for row in rows})
    print(f"[sintetica] OK: {len(rows)} chamados artificiais, {categories} categorias")
    print(f"[sintetica] saída local: {output}")
    print("[sintetica] nenhum artefato privado foi lido")


if __name__ == "__main__":
    main()
