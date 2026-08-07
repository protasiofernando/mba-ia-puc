#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 6 estrito: classifica cada resumo em uma categoria fechada do portfolio.

A LLM escolhe um category_id. O Python deriva nome e grupo do portfolio. Saidas
invalidas sao tentadas novamente e, se persistirem, ficam pendentes. Nao existe
fallback para a primeira categoria.
"""
import hashlib
import json
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from projeto import pipeline_data_dir, load_projeto_meta
from llm_client import get_client, LLMError

PD = pipeline_data_dir()
OUT = PD / "06_classificados.json"
STAGE6_VERSION = "closed-category-id-v3"


def _hash_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _category_id(group: str, name: str) -> str:
    import unicodedata
    value = unicodedata.normalize("NFKD", name or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = "".join(ch if ch.isalnum() else "_" for ch in value.casefold())
    slug = "_".join(part for part in value.split("_") if part)[:36] or "categoria"
    digest = hashlib.sha256(f"{group}\0{name}".encode("utf-8")).hexdigest()[:8]
    return f"{slug}_{digest}"


def carregar_portfolio():
    data = json.load(open(PD / "05_portfolio_recommendation.json", encoding="utf-8"))
    portfolio = data["recomendacao"]["portfolio_otimizado"]
    by_id = {}
    lines = []
    normalized = []
    for item in portfolio:
        name = str(item["nome"]).strip()
        group = str(item["grupo"]).strip()
        category_id = str(item.get("id") or _category_id(group, name)).strip()
        if not category_id or category_id in by_id:
            raise RuntimeError(f"category_id ausente ou duplicado: {category_id}")
        record = {
            "id": category_id,
            "nome": name,
            "grupo": group,
            "descricao": str(item.get("descricao", "")).strip(),
        }
        by_id[category_id] = record
        normalized.append(record)
        lines.append(
            f"- category_id={category_id} | grupo={group} | chamado={name} | "
            f"descricao={record['descricao']}"
        )
    if not by_id:
        raise RuntimeError("portfolio_otimizado vazio")
    fingerprint = str(
        data.get("metadata", {}).get("portfolio_fingerprint", "")
    ).strip() or _hash_json(normalized)
    return "\n".join(lines), by_id, fingerprint


SYSTEM = """Voce e analista de triagem do portal {portal_nome}. Classifique UM
chamado em EXATAMENTE UMA opcao do portfolio fechado abaixo.

PORTFOLIO:
{portfolio}

Regras:
- Retorne category_id copiando exatamente um ID do portfolio.
- segunda_opcao_id pode ser null; se preenchida, deve ser outro ID exato.
- Nao invente IDs, nomes ou categorias.
- Escolha pela intencao do chamado. A categoria antiga do Jira nao e fornecida
  para nao induzir a decisao.
- ambiguidade deve ser true quando duas opcoes forem plausiveis ou faltarem
  informacoes para decidir com seguranca.
- Nao use travessao.

Responda SOMENTE JSON:
{
  "category_id": "id exato escolhido",
  "segunda_opcao_id": "outro id exato ou null",
  "justificativa": "1 ou 2 frases",
  "confianca": "alta|media|baixa",
  "ambiguidade": true
}"""


def montar_user(item: dict, correction: str = "") -> str:
    message = (
        f"intencao: {item.get('intencao', '')}\n"
        f"tema: {item.get('tema', '')}\n"
        f"tipo_pedido: {item.get('tipo_pedido', '')}\n"
        f"contexto: {item.get('contexto', '')}\n"
        f"info_fornecidas: {', '.join(item.get('info_fornecidas', []))}"
    )
    if correction:
        message += (
            "\n\nA resposta anterior foi invalida: "
            + correction
            + "\nResponda novamente usando somente IDs existentes no portfolio."
        )
    return message


def _input_hash(item: dict, portfolio_fingerprint: str) -> str:
    payload = {
        "version": STAGE6_VERSION,
        "portfolio_fingerprint": portfolio_fingerprint,
        "intencao": item.get("intencao", ""),
        "tema": item.get("tema", ""),
        "tipo_pedido": item.get("tipo_pedido", ""),
        "contexto": item.get("contexto", ""),
        "info_fornecidas": item.get("info_fornecidas", []),
    }
    return _hash_json(payload)


def carregar_ckpt(path: Path, expected_hashes: dict[str, str]) -> dict:
    found = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            key = row["chave"]
            if row.get("_input_hash") == expected_hashes.get(key):
                found[key] = row
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return found


def _normalize_response(response: dict, by_id: dict[str, dict]) -> dict:
    if not isinstance(response, dict):
        raise ValueError("resposta nao e objeto")
    category_id = str(response.get("category_id", "")).strip()
    if category_id not in by_id:
        raise ValueError(f"category_id inexistente: {category_id or '(vazio)'}")

    second = response.get("segunda_opcao_id")
    second = str(second).strip() if second is not None else ""
    # A 2a opcao e OPCIONAL (o prompt permite null). Se a LLM devolver uma 2a
    # opcao invalida (fora do portfolio ou igual a primaria), descarta-se apenas
    # a 2a opcao e marca-se revisao; a classificacao primaria valida e mantida,
    # em vez de falhar o chamado inteiro por um campo secundario.
    segunda_opcao_descartada = False
    if second and (second not in by_id or second == category_id):
        second = ""
        segunda_opcao_descartada = True
    if "confianca" not in response:
        raise ValueError("confianca ausente")
    confidence = str(response.get("confianca", "")).strip().lower()
    if confidence not in {"alta", "media", "baixa"}:
        raise ValueError(f"confianca invalida: {confidence}")

    if not isinstance(response.get("ambiguidade"), bool):
        raise ValueError("ambiguidade deve ser booleano true ou false")
    ambiguous = response["ambiguidade"]
    justification = str(response.get("justificativa", "")).strip()
    if not justification:
        raise ValueError("justificativa ausente ou vazia")
    chosen = by_id[category_id]
    second_item = by_id.get(second)
    review = confidence == "baixa" or ambiguous or segunda_opcao_descartada
    return {
        "categoria_id": category_id,
        "grupo_novo": chosen["grupo"],
        "categoria_nova": chosen["nome"],
        "segunda_opcao_id": second or None,
        "segunda_categoria": second_item["nome"] if second_item else None,
        "segunda_opcao_descartada": segunda_opcao_descartada,
        "justificativa": justification[:500],
        "confianca": confidence,
        "ambiguidade": ambiguous,
        "revisao_recomendada": review,
    }


def main():
    summaries = json.load(open(PD / "02_summaries.json", encoding="utf-8"))
    try:
        portfolio_text, by_id, portfolio_fingerprint = carregar_portfolio()
    except (KeyError, TypeError, ValueError, RuntimeError) as exc:
        raise SystemExit(f"ERRO: portfolio invalido para Stage 6: {exc}") from exc

    meta = load_projeto_meta()
    portal_name = meta.get("portal_nome") or meta.get("nome") or "portal de atendimento"
    system = (
        SYSTEM.replace("{portal_nome}", portal_name)
        .replace("{portfolio}", portfolio_text)
    )
    client = get_client()
    workers = int(os.getenv("PIPELINE_WORKERS", "8"))
    safe = client.model_label.replace(":", "_").replace("/", "_")
    checkpoint = PD / (
        f"_ckpt_stage6__{safe}__p{portfolio_fingerprint[:12]}.jsonl"
    )
    input_hashes = {
        item["chave"]: _input_hash(item, portfolio_fingerprint) for item in summaries
    }
    found = carregar_ckpt(checkpoint, input_hashes)
    pending = [item for item in summaries if item["chave"] not in found]
    print(
        f"[Stage 6/{client.model_label}] total={len(summaries)} "
        f"feitos={len(found)} pendentes={len(pending)} workers={workers}"
    )
    print(f"[Stage 6] checkpoint: {checkpoint.name}")

    lock = threading.Lock()
    handle = open(checkpoint, "a", encoding="utf-8")
    counters = {"ok": 0, "erro": 0, "revisao": 0, "retries_semanticos": 0}

    def process(item):
        last_error = ""
        for attempt in range(1, 4):
            try:
                response = client.chat_json(
                    system,
                    montar_user(item, last_error),
                    max_tokens=350,
                    timeout=900,
                )
                normalized = _normalize_response(response, by_id)
                record = {
                    "chave": item["chave"],
                    **normalized,
                    "intencao": item.get("intencao", ""),
                    "tipo_atual": item.get("tipo_atual", ""),
                    "modelo_decisor": client.model_label,
                    "_input_hash": input_hashes[item["chave"]],
                }
                with lock:
                    handle.write(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                    handle.flush()
                    counters["ok"] += 1
                    counters["retries_semanticos"] += attempt - 1
                    if record["revisao_recomendada"]:
                        counters["revisao"] += 1
                    if (counters["ok"] + counters["erro"]) % 100 == 0:
                        print(
                            f"   ... {counters['ok']} ok, {counters['erro']} erro, "
                            f"{counters['revisao']} para revisao"
                        )
                return True
            except ValueError as exc:
                last_error = str(exc)
            except LLMError as exc:
                last_error = str(exc)

        with lock:
            counters["erro"] += 1
        print(f"   [ERRO] {item['chave']}: resposta invalida apos 3 tentativas: {last_error}")
        return False

    if pending:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, item) for item in pending]
            for _ in as_completed(futures):
                pass
    handle.close()

    found = carregar_ckpt(checkpoint, input_hashes)
    missing = [item["chave"] for item in summaries if item["chave"] not in found]
    output = [
        {
            key: value
            for key, value in found[item["chave"]].items()
            if not key.startswith("_")
        }
        for item in summaries if item["chave"] in found
    ]
    print(
        f"[Stage 6] resolvidos={len(output)} faltando={len(missing)} "
        f"revisao_recomendada={sum(1 for row in output if row.get('revisao_recomendada'))} "
        f"retries_semanticos={counters['retries_semanticos']}"
    )
    if missing:
        print(f"[Stage 6] AINDA FALTAM {len(missing)}. Ex.: {missing[:5]}")
        print("[Stage 6] 06_classificados.json NAO foi gravado.")
        raise SystemExit(2)

    json.dump(output, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[Stage 6] OK: {OUT} ({len(output)} registros) via {client.model_label}")


if __name__ == "__main__":
    main()
