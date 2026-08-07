#!/usr/bin/env python3
"""Stage 7 operacional: aplica automaticamente o portfolio humano congelado.

A intervencao humana acontece no nivel do catalogo, em
``formacao_portfolio/decisao_curada/feedback_portfolio.json``. Nao ha rotulacao manual por chamado. Este script
projeta os resumos do Stage 2 nas categorias fechadas da decisao curada, com
LLM local, IDs exatos, checkpoint vinculado ao conteudo e cobertura completa.

Entradas:
  formacao_portfolio/decisao_curada/feedback_portfolio.json
  formacao_portfolio/decisao_curada/portfolio_referencia.json
  pipeline_data/02_summaries.json

Saidas:
  pipeline_data/07_classificados_final.json  (privada, por chamado)
  pipeline_data/07_portfolio_final.json      (agregada, publicavel)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_client import LLMError, get_client
from materializar_portfolio_curado import (
    DEFAULT_CONTRACT,
    DEFAULT_FEEDBACK,
    DEFAULT_OUTPUT,
    DEFAULT_REFERENCE,
    _load,
    _write,
    build_operational,
    validate_reference,
)
from projeto import load_projeto_meta, pipeline_data_dir


PD = pipeline_data_dir()
INPUT = PD / "02_summaries.json"
OUTPUT = PD / "07_classificados_final.json"
STAGE7_VERSION = "closed-curated-portfolio-v1"


SYSTEM = """Voce e analista de triagem do portal {portal}. Classifique UM
chamado em EXATAMENTE UMA categoria do portfolio operacional curado.

PORTFOLIO FECHADO:
{portfolio}

Regras:
- copie categoria_id exatamente de uma opcao acima;
- use somente intencao, tema, tipo do pedido, contexto e informacoes fornecidas;
- a categoria historica do Jira nao e fornecida;
- Sala de Sigilo nao e opcao: seus registros foram excluidos antes do Stage 1;
- ambiguidade=true quando duas opcoes forem plausiveis ou faltarem dados;
- nao invente IDs ou categorias.

Responda SOMENTE JSON:
{{
  "categoria_id": "id exato",
  "segunda_opcao_id": "outro id exato ou null",
  "justificativa": "1 ou 2 frases",
  "confianca": "alta|media|baixa",
  "ambiguidade": true
}}"""


def _hash_json(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _portfolio(feedback: dict) -> tuple[str, dict[str, dict], str]:
    rows = [
        row
        for row in feedback.get("portfolio_final", [])
        if isinstance(row, dict) and not row.get("fora_da_analise")
    ]
    by_id: dict[str, dict] = {}
    lines = []
    for row in rows:
        category_id = str(row.get("id", "")).strip()
        if not category_id or category_id in by_id:
            raise RuntimeError(f"categoria analitica ausente ou duplicada: {category_id!r}")
        normalized = {
            "id": category_id,
            "nome": str(row.get("nome", "")).strip(),
            "grupo": str(row.get("grupo", "")).strip(),
            "descricao": str(row.get("descricao", "")).strip(),
            "quando_usar": str(row.get("quando_usar", "")).strip(),
        }
        by_id[category_id] = normalized
        lines.append(
            f"- categoria_id={category_id} | grupo={normalized['grupo']} | "
            f"nome={normalized['nome']} | descricao={normalized['descricao']} | "
            f"usar quando={normalized['quando_usar']}"
        )
    if not by_id:
        raise RuntimeError("portfolio curado sem categorias analiticas")
    fingerprint = _hash_json({
        "stage7_version": STAGE7_VERSION,
        "categories": list(by_id.values()),
        "diretrizes": feedback.get("diretrizes", []),
        "fora_do_catalogo": feedback.get("fora_do_catalogo", []),
    })
    return "\n".join(lines), by_id, fingerprint


def _user(item: dict, correction: str = "") -> str:
    supplied = item.get("info_fornecidas", [])
    if isinstance(supplied, list):
        supplied = ", ".join(str(value) for value in supplied)
    text = (
        f"intencao: {item.get('intencao', '')}\n"
        f"tema: {item.get('tema', '')}\n"
        f"tipo_pedido: {item.get('tipo_pedido', '')}\n"
        f"contexto: {item.get('contexto', '')}\n"
        f"info_fornecidas: {supplied or ''}"
    )
    if correction:
        text += (
            "\n\nA resposta anterior foi invalida: "
            + correction
            + "\nTente novamente copiando somente IDs do portfolio."
        )
    return text


def _normalize(response: dict, by_id: dict[str, dict]) -> dict:
    if not isinstance(response, dict):
        raise ValueError("resposta nao e objeto")
    category_id = str(response.get("categoria_id", "")).strip()
    if category_id not in by_id:
        raise ValueError(f"categoria_id inexistente: {category_id or '(vazio)'}")
    second = response.get("segunda_opcao_id")
    second = str(second).strip() if second is not None else ""
    second_discarded = bool(second and (second not in by_id or second == category_id))
    if second_discarded:
        second = ""
    confidence = str(response.get("confianca", "")).strip().lower()
    if confidence not in {"alta", "media", "baixa"}:
        raise ValueError(f"confianca invalida: {confidence!r}")
    ambiguous = response.get("ambiguidade")
    if not isinstance(ambiguous, bool):
        raise ValueError("ambiguidade deve ser booleana")
    justification = str(response.get("justificativa", "")).strip()
    if not justification:
        raise ValueError("justificativa ausente")
    chosen = by_id[category_id]
    alternative = by_id.get(second)
    return {
        "categoria_id": category_id,
        "grupo_novo": chosen["grupo"],
        "categoria_nova": chosen["nome"],
        "segunda_opcao_id": second or None,
        "segunda_categoria": alternative["nome"] if alternative else None,
        "segunda_opcao_descartada": second_discarded,
        "justificativa": justification[:500],
        "confianca": confidence,
        "ambiguidade": ambiguous,
        "revisao_recomendada": (
            confidence == "baixa" or ambiguous or second_discarded
        ),
    }


def _input_hash(item: dict, portfolio_fingerprint: str) -> str:
    return _hash_json({
        "version": STAGE7_VERSION,
        "portfolio_fingerprint": portfolio_fingerprint,
        "intencao": item.get("intencao", ""),
        "tema": item.get("tema", ""),
        "tipo_pedido": item.get("tipo_pedido", ""),
        "contexto": item.get("contexto", ""),
        "info_fornecidas": item.get("info_fornecidas", []),
    })


def _load_checkpoint(path: Path, hashes: dict[str, str]) -> dict[str, dict]:
    found: dict[str, dict] = {}
    if not path.is_file():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            key = row["chave"]
            if row.get("_input_hash") == hashes.get(key):
                found[key] = row
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return found


def main() -> int:
    if not INPUT.is_file():
        print(f"ERRO: insumo ausente: {INPUT}", file=sys.stderr)
        return 2
    feedback = _load(DEFAULT_FEEDBACK)
    contract = _load(DEFAULT_CONTRACT)
    reference = _load(DEFAULT_REFERENCE)
    validate_reference(feedback, contract, reference)
    portfolio_text, by_id, fingerprint = _portfolio(feedback)

    summaries = _load(INPUT)
    if not isinstance(summaries, list) or not summaries:
        print("ERRO: Stage 2 vazio ou invalido", file=sys.stderr)
        return 2
    keys = [str(item.get("chave", "")).strip() for item in summaries]
    if not all(keys) or len(keys) != len(set(keys)):
        print("ERRO: chaves do Stage 2 ausentes ou duplicadas", file=sys.stderr)
        return 2

    client = get_client()
    portal = load_projeto_meta().get("portal_nome") or "portal de atendimento"
    system = SYSTEM.replace("{portal}", portal).replace("{portfolio}", portfolio_text)
    workers = int(os.getenv("PIPELINE_WORKERS", "2"))
    safe_model = client.model_label.replace(":", "_").replace("/", "_")
    checkpoint = PD / f"_ckpt_stage7__{safe_model}__p{fingerprint[:12]}.jsonl"
    hashes = {
        item["chave"]: _input_hash(item, fingerprint) for item in summaries
    }
    found = _load_checkpoint(checkpoint, hashes)
    pending = [item for item in summaries if item["chave"] not in found]
    print(
        f"[Stage 7/{client.model_label}] total={len(summaries)} "
        f"feitos={len(found)} pendentes={len(pending)} workers={workers}"
    )
    print(f"[Stage 7] checkpoint: {checkpoint.name}")

    lock = threading.Lock()
    handle = checkpoint.open("a", encoding="utf-8")
    counters = {"ok": 0, "erro": 0, "revisao": 0, "retries": 0}

    def process(item: dict) -> bool:
        last_error = ""
        for attempt in range(1, 4):
            try:
                response = client.chat_json(
                    system,
                    _user(item, last_error),
                    temperature=0.0,
                    max_tokens=350,
                    timeout=900,
                )
                normalized = _normalize(response, by_id)
                record = {
                    "chave": item["chave"],
                    **normalized,
                    "intencao": item.get("intencao", ""),
                    "tipo_atual": item.get("tipo_atual", ""),
                    "modelo_decisor": client.model_label,
                    "_input_hash": hashes[item["chave"]],
                }
                with lock:
                    handle.write(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                    handle.flush()
                    counters["ok"] += 1
                    counters["retries"] += attempt - 1
                    if record["revisao_recomendada"]:
                        counters["revisao"] += 1
                    if counters["ok"] % 100 == 0:
                        print(
                            f"   ... {counters['ok']} ok, {counters['erro']} erro, "
                            f"{counters['revisao']} para revisao"
                        )
                return True
            except (ValueError, LLMError) as exc:
                last_error = str(exc)
        with lock:
            counters["erro"] += 1
        print(f"[Stage 7] ERRO {item['chave']}: {last_error}")
        return False

    if pending:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, item) for item in pending]
            for _ in as_completed(futures):
                pass
    handle.close()

    found = _load_checkpoint(checkpoint, hashes)
    missing = [item["chave"] for item in summaries if item["chave"] not in found]
    if missing:
        print(f"ERRO: Stage 7 incompleto; faltam {len(missing)} registros", file=sys.stderr)
        return 2
    output = [
        {
            key: value
            for key, value in found[item["chave"]].items()
            if not key.startswith("_")
        }
        for item in summaries
    ]
    _write(OUTPUT, output)
    _write(DEFAULT_OUTPUT, build_operational(feedback, output))
    print(
        f"[Stage 7] PASS: {len(output)} classificados automaticamente; "
        f"{sum(1 for row in output if row['revisao_recomendada'])} para revisao"
    )
    print(f"[Stage 7] privado: {OUTPUT}")
    print(f"[Stage 7] agregado: {DEFAULT_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
