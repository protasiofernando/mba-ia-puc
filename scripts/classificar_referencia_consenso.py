#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Constroi a referência automática sobre uma máscara determinística congelada.

A máscara é obrigatoriamente produzida antes deste script, a partir da exclusão
estruturada dos request types de Sala de Sigilo antes do Stage 1. Nenhuma LLM
decide escopo. Aqui, os chamados já validados no escopo são projetados no
portfolio operacional curado ex post.

  Dois modelos distintos votam; casos incertos recebem retestes correlacionados.
  A referencia estrita exige acordo inicial entre as duas familias. A referencia
  de cobertura pode usar maioria de estabilidade ou chair automatico, permitindo
  analise de sensibilidade sem rotulacao manual.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import sys
import threading
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from sklearn.metrics import cohen_kappa_score

sys.path.insert(0, str(Path(__file__).parent))
from llm_client import LLMClient, LLMError
from discovery_contract import (
    ROUNDTRIP_IDENTIFIER_POLICY,
    opaque_roundtrip_id,
)


VERSION = "automatic-consensus-reference-v4"
CONFIDENCE = {"alta", "media", "baixa"}


def _hash_json(value) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def _summary_payload(item: dict) -> OrderedDict:
    def values(field: str) -> list[str]:
        raw = item.get(field)
        source = raw if isinstance(raw, list) else ([raw] if raw else [])
        return [str(value).strip() for value in source if str(value).strip()][:5]

    return OrderedDict([
        (
            "registro_id",
            opaque_roundtrip_id(str(item.get("chave", "")).strip()),
        ),
        ("intencao", str(item.get("intencao", "")).strip()),
        ("tema", str(item.get("tema", "")).strip()),
        ("tipo_pedido", str(item.get("tipo_pedido", "")).strip()),
        ("contexto", str(item.get("contexto", "")).strip()),
        ("info_fornecidas", values("info_fornecidas")),
        ("info_faltantes", values("info_faltantes")),
    ])


def _model_digest(model: str) -> str:
    base = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/")
    try:
        response = requests.get(f"{base}/api/tags", timeout=20)
        response.raise_for_status()
        matches = []
        for item in response.json().get("models", []):
            name = str(item.get("name", ""))
            if name == model or (
                ":" not in model and name == f"{model}:latest"
            ):
                matches.append(item)
        chosen = matches[0] if len(matches) == 1 else {}
        return str(chosen.get("digest", "")).strip()
    except Exception:
        return ""


def _load_portfolio(path: Path) -> tuple[list[dict], dict, dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    analytic = data.get("categorias_analiticas")
    fixed = data.get("itens_fixos_fora_analise")
    if not isinstance(analytic, list) or not analytic:
        raise RuntimeError("portfolio sem categorias_analiticas")
    if not isinstance(fixed, list):
        raise RuntimeError("portfolio sem itens_fixos_fora_analise")
    by_id = {}
    for category in analytic:
        category_id = str(category.get("id", "")).strip()
        if not category_id or category_id in by_id:
            raise RuntimeError(f"id analitico ausente ou duplicado: {category_id}")
        by_id[category_id] = category
    sala = next(
        (
            item for item in fixed
            if str(item.get("id", "")).strip() == "sala_sigilo"
        ),
        None,
    )
    if not sala:
        raise RuntimeError("item fixo sala_sigilo ausente")
    return analytic, by_id, sala


def _reference_system(categories: list[dict], variant: str) -> str:
    ordered = list(categories)
    if variant == "reverse":
        ordered.reverse()
    elif variant == "rotate" and ordered:
        ordered = ordered[2:] + ordered[:2]
    lines = []
    for item in ordered:
        lines.append(
            f"- id={item['id']} | grupo={item.get('grupo_id', '')} | "
            f"nome={item.get('nome', '')} | quando_usar={item.get('quando_usar', '')}"
        )
    return """Voce projeta UM chamado no portfolio operacional curado e fechado
abaixo. Este e um instrumento de avaliacao; nao altere nem invente categorias.

PORTFOLIO ANALITICO:
{categories}

Regras:
- retorne exatamente um id listado;
- escolha pela intencao e pelo servico ou ambiente afetado;
- acesso, incidente, manutencao, backup e restauracao classificam pelo servico;
- HPC, VM individual, servidor compartilhado e nuvem sao distintos;
- use o catch-all apenas quando nenhum servico analitico servir;
- a categoria antiga do Jira nao e fornecida.

Responda SOMENTE JSON:
{{
  "decision_id": "id exato",
  "second_option_id": "outro id exato ou null",
  "confidence": "alta|media|baixa",
  "ambiguity": false,
  "justification": "criterio objetivo em ate duas frases"
}}""".format(categories="\n".join(lines))


def _clean_decision_id(value) -> str:
    """Normaliza apenas variacoes sintaticas reversiveis do ID canonico."""
    text = str(value or "").strip().strip("`'\"")
    lowered = text.lower()
    for prefix in ("id=", "id:"):
        if lowered.startswith(prefix):
            text = text[len(prefix):].strip().strip("`'\"")
            lowered = text.lower()
    return text


def _normalize_vote(raw: dict, allowed: set[str]) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("resposta nao e objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("resultado nao e objeto")
    decision = _clean_decision_id(body.get("decision_id"))
    if decision not in allowed:
        raise LLMError(f"decision_id invalido: {decision or '(vazio)'}")
    second = body.get("second_option_id")
    if second is not None:
        second = _clean_decision_id(second)
        if not second:
            second = None
    if second is not None and (second not in allowed or second == decision):
        raise LLMError(f"second_option_id invalido: {second}")
    confidence = str(body.get("confidence", "")).strip().lower()
    if confidence not in CONFIDENCE:
        raise LLMError(f"confidence invalida: {confidence or '(vazio)'}")
    ambiguity = body.get("ambiguity")
    if not isinstance(ambiguity, bool):
        raise LLMError("ambiguity deve ser booleano")
    justification = str(body.get("justification", "")).strip()
    if not justification:
        raise LLMError("justification ausente")
    return OrderedDict([
        ("decision_id", decision),
        ("second_option_id", second),
        ("confidence", confidence),
        ("ambiguity", ambiguity),
        ("justification", justification[:500]),
    ])


def _checkpoint_load(path: Path, expected: dict[str, str]) -> dict[str, dict]:
    output = {}
    if not path.exists():
        return output
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            key = str(row.get("chave", ""))
            if key and row.get("_input_hash") == expected.get(key):
                output[key] = row
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return output


def _run_pass(
    *,
    rows: list[dict],
    phase: str,
    pass_id: str,
    model: str,
    model_digest: str,
    system: str,
    allowed: set[str],
    checkpoint_dir: Path,
    workers: int,
) -> dict[str, dict]:
    prompt_fingerprint = _hash_json({
        "version": VERSION,
        "phase": phase,
        "pass_id": pass_id,
        "system": system,
        "allowed": sorted(allowed),
    })
    input_hashes = {}
    for item in rows:
        payload = _summary_payload(item)
        key = str(item.get("chave", "")).strip()
        input_hashes[key] = _hash_json({
            "version": VERSION,
            "phase": phase,
            "pass_id": pass_id,
            "model": model,
            "model_digest": model_digest,
            "prompt_fingerprint": prompt_fingerprint,
            "payload": payload,
        })
    path = checkpoint_dir / (
        f"{phase}__{pass_id}__{_safe(model)}__"
        f"p{prompt_fingerprint[:12]}.jsonl"
    )
    found = _checkpoint_load(path, input_hashes)
    pending = [
        item for item in rows
        if str(item.get("chave", "")).strip() not in found
    ]
    print(
        f"[referencia/{phase}/{pass_id}/{model}] total={len(rows)} "
        f"feitos={len(found)} pendentes={len(pending)} workers={workers}"
    )
    if not pending:
        return found

    client = LLMClient(provider_override="ollama", model_override=model)
    lock = threading.Lock()
    errors = []

    def classify(item: dict) -> dict:
        payload = _summary_payload(item)
        key = str(item.get("chave", "")).strip()
        last_error = ""
        user_base = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        for attempt in range(1, 5):
            user = user_base
            if attempt > 1:
                user += (
                    "\n\nA resposta anterior foi invalida: "
                    + last_error
                    + "\nResponda novamente com um ID exato e todos os campos."
                )
            try:
                vote = _normalize_vote(
                    client.chat_json(
                        system,
                        user,
                        temperature=0.0,
                        max_tokens=500,
                        max_retries=4,
                        timeout=900,
                    ),
                    allowed,
                )
                return {
                    "chave": key,
                    **vote,
                    "_input_hash": input_hashes[key],
                    "_model": model,
                    "_model_digest": model_digest,
                    "_phase": phase,
                    "_pass_id": pass_id,
                }
            except LLMError as exc:
                last_error = str(exc)
        raise LLMError(f"{key}: voto invalido apos retries: {last_error}")

    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = {executor.submit(classify, item): item for item in pending}
            for future in as_completed(futures):
                item = futures[future]
                try:
                    record = future.result()
                except Exception as exc:
                    errors.append(str(exc))
                    print(f"[referencia] ERRO {item.get('chave')}: {exc}")
                    continue
                with lock:
                    handle.write(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                    handle.flush()
                found[record["chave"]] = record
    if errors or len(found) != len(rows):
        raise RuntimeError(
            f"passagem {phase}/{pass_id}/{model} incompleta; "
            "reexecute para retomar"
        )
    return found


def _needs_revote(a: dict, b: dict) -> bool:
    return (
        a["decision_id"] != b["decision_id"]
        or a["confidence"] == "baixa"
        or b["confidence"] == "baixa"
        or bool(a["ambiguity"])
        or bool(b["ambiguity"])
    )


def _majority(votes: list[dict], minimum: int) -> tuple[str | None, int]:
    counts = Counter(vote["decision_id"] for vote in votes)
    if not counts:
        return None, 0
    decision, total = counts.most_common(1)[0]
    tied = sum(1 for value in counts.values() if value == total) > 1
    if tied or total < minimum:
        return None, total
    return decision, total


def _confidence_from_votes(votes: list[dict], decision: str) -> str:
    relevant = [vote for vote in votes if vote["decision_id"] == decision]
    if relevant and all(vote["confidence"] == "alta" for vote in relevant):
        return "alta"
    if any(vote["confidence"] == "baixa" for vote in relevant):
        return "baixa"
    return "media"


def _kappa(left: list[str], right: list[str]) -> float | None:
    value = float(cohen_kappa_score(left, right))
    return round(value, 6) if math.isfinite(value) else None


def _write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summaries", required=True)
    parser.add_argument("--portfolio", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument(
        "--scope-mask",
        required=True,
        help="01_scope_mask.json determinístico produzido antes desta etapa",
    )
    parser.add_argument(
        "--model-a",
        default=os.getenv("REFERENCE_MODEL_A", "llama3.3:70b"),
    )
    parser.add_argument(
        "--model-b",
        default=os.getenv(
            "REFERENCE_MODEL_B",
            "qwen3:30b-a3b-instruct-2507-q4_K_M",
        ),
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=int(os.getenv("REFERENCE_WORKERS", "2")),
    )
    args = parser.parse_args()

    summaries_path = Path(args.summaries).resolve()
    portfolio_path = Path(args.portfolio).resolve()
    out_dir = Path(args.out_dir).resolve()
    checkpoint_dir = out_dir / "checkpoints"
    rows = json.loads(summaries_path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or not rows:
        raise SystemExit("ERRO: summaries vazio ou invalido")
    keys = [str(item.get("chave", "")).strip() for item in rows]
    if any(not key for key in keys) or len(keys) != len(set(keys)):
        raise SystemExit("ERRO: chaves vazias ou duplicadas nos summaries")
    for item, key in zip(rows, keys):
        item["chave"] = key
    categories, category_by_id, _sala = _load_portfolio(portfolio_path)

    models = {"a": args.model_a, "b": args.model_b}
    digests = {name: _model_digest(model) for name, model in models.items()}
    missing_digests = [
        models[name] for name, digest in digests.items() if not digest
    ]
    if missing_digests:
        raise SystemExit(
            "ERRO: nao foi possivel registrar o digest Ollama de: "
            + ", ".join(missing_digests)
        )
    if models["a"] == models["b"] or digests["a"] == digests["b"]:
        raise SystemExit(
            "ERRO: os dois classificadores da referencia devem ter nomes e "
            "digests Ollama distintos"
        )
    source_fingerprint = _sha256_file(summaries_path)
    portfolio_fingerprint = _sha256_file(portfolio_path)

    # A máscara v6 é uma evidência produzida por regra determinística antes
    # desta execução. Este script recusa qualquer exclusão/indeterminação
    # adicional e nunca chama modelos para decidir o universo.
    scope_mask_path = Path(args.scope_mask).resolve()
    scope_output = json.loads(
        scope_mask_path.read_text(encoding="utf-8-sig")
    )
    scope_metadata = scope_output.get("metadata") or {}
    included_keys = scope_output.get("incluidos") or []
    exclusions = scope_output.get("exclusoes") or []
    indeterminate = scope_output.get("indeterminados") or []
    if (
        scope_metadata.get("scope_method")
        != "deterministic_structured_request_type_prefilter"
        or scope_metadata.get("llm_used_for_scope") is not False
        or scope_metadata.get("free_text_used_for_scope") is not False
    ):
        raise SystemExit("ERRO: máscara não é o escopo determinístico v6")
    if scope_metadata.get("source_fingerprint") != source_fingerprint:
        raise SystemExit("ERRO: máscara não pertence ao Stage 2 informado")
    if included_keys != keys or exclusions or indeterminate:
        raise SystemExit(
            "ERRO: máscara v6 deve incluir exatamente todo o Stage 2 "
            "pré-filtrado, na mesma ordem"
        )
    scope_fingerprint = str(scope_metadata.get("scope_fingerprint", ""))
    if len(scope_fingerprint) != 64:
        raise SystemExit("ERRO: fingerprint de escopo ausente ou inválido")
    analytic_rows = rows
    analytic_path = out_dir / "02_summaries_escopo.json"
    analytic_path.parent.mkdir(parents=True, exist_ok=True)
    analytic_path.write_bytes(summaries_path.read_bytes())
    analytic_source_fingerprint = _sha256_file(analytic_path)

    # Referência analítica.
    allowed = set(category_by_id)
    ref_a = _run_pass(
        rows=analytic_rows,
        phase="reference",
        pass_id="a1",
        model=models["a"],
        model_digest=digests["a"],
        system=_reference_system(categories, "normal"),
        allowed=allowed,
        checkpoint_dir=checkpoint_dir,
        workers=args.workers,
    )
    ref_b = _run_pass(
        rows=analytic_rows,
        phase="reference",
        pass_id="b1",
        model=models["b"],
        model_digest=digests["b"],
        system=_reference_system(categories, "reverse"),
        allowed=allowed,
        checkpoint_dir=checkpoint_dir,
        workers=args.workers,
    )
    ref_revote_rows = [
        item for item in analytic_rows
        if _needs_revote(
            ref_a[str(item["chave"])],
            ref_b[str(item["chave"])],
        )
    ]
    ref_a2 = _run_pass(
        rows=ref_revote_rows,
        phase="reference",
        pass_id="a2",
        model=models["a"],
        model_digest=digests["a"],
        system=_reference_system(categories, "rotate")
        + "\nEste e um reteste de estabilidade do mesmo modelo; reavalie do zero.",
        allowed=allowed,
        checkpoint_dir=checkpoint_dir,
        workers=args.workers,
    )
    ref_b2 = _run_pass(
        rows=ref_revote_rows,
        phase="reference",
        pass_id="b2",
        model=models["b"],
        model_digest=digests["b"],
        system=_reference_system(categories, "normal")
        + "\nEste e um reteste de estabilidade do mesmo modelo; reavalie do zero.",
        allowed=allowed,
        checkpoint_dir=checkpoint_dir,
        workers=args.workers,
    )

    preliminary = {}
    chair_rows_by_model = {"a": [], "b": []}
    row_by_key = {str(item["chave"]): item for item in analytic_rows}
    for key in included_keys:
        votes = [ref_a[key], ref_b[key]]
        initial_strict = (
            votes[0]["decision_id"]
            if (
                votes[0]["decision_id"] == votes[1]["decision_id"]
                and not votes[0]["ambiguity"]
                and not votes[1]["ambiguity"]
                and votes[0]["confidence"] != "baixa"
                and votes[1]["confidence"] != "baixa"
            )
            else None
        )
        if key in ref_a2:
            votes.extend([ref_a2[key], ref_b2[key]])
            coverage_candidate, strength = _majority(votes, 3)
            status = (
                "stability_majority_3_of_4"
                if coverage_candidate
                else "no_stability_majority"
            )
        else:
            coverage_candidate = votes[0]["decision_id"]
            strength = 2
            status = "initial_cross_model_agreement"
        preliminary[key] = {
            "votes": votes,
            "strict": initial_strict,
            "coverage_candidate": coverage_candidate,
            "strength": strength,
            "status": status,
        }
        if coverage_candidate is None:
            chair_name = "a" if int(hashlib.sha256(key.encode()).hexdigest(), 16) % 2 == 0 else "b"
            chair_rows_by_model[chair_name].append(row_by_key[key])

    chair_votes = {}
    for name in ("a", "b"):
        if not chair_rows_by_model[name]:
            continue
        chair_votes.update(_run_pass(
            rows=chair_rows_by_model[name],
            phase="reference",
            pass_id=f"chair_{name}",
            model=models[name],
            model_digest=digests[name],
            system=_reference_system(categories, "rotate")
            + "\nVoce e o desempate automatico final. Decida do zero.",
            allowed=allowed,
            checkpoint_dir=checkpoint_dir,
            workers=args.workers,
        ))

    classifications = []
    for key in included_keys:
        info = preliminary[key]
        strict_id = info["strict"]
        coverage_id = info["coverage_candidate"]
        status = info["status"]
        votes = list(info["votes"])
        if coverage_id is None:
            chair = chair_votes[key]
            votes.append(chair)
            coverage_id = chair["decision_id"]
            status = "automatic_chair_tiebreak"
        category = category_by_id[coverage_id]
        classifications.append(OrderedDict([
            ("chave", key),
            ("categoria_estrita_id", strict_id),
            ("categoria_cobertura_id", coverage_id),
            ("categoria_ref_id", coverage_id),
            ("categoria_ref", category["nome"]),
            ("grupo_ref_id", category.get("grupo_id")),
            ("status_consenso", status),
            ("forca_maioria", info["strength"]),
            ("confianca_consenso", _confidence_from_votes(votes, coverage_id)),
            ("modelo_a_id", ref_a[key]["decision_id"]),
            ("modelo_b_id", ref_b[key]["decision_id"]),
            ("votos", [
                {
                    "modelo": vote["_model"],
                    "passagem": vote["_pass_id"],
                    "decision_id": vote["decision_id"],
                    "confidence": vote["confidence"],
                    "ambiguity": vote["ambiguity"],
                }
                for vote in votes
            ]),
        ]))

    strict_count = sum(row["categoria_estrita_id"] is not None for row in classifications)
    initial_agreement = sum(
        row["status_consenso"] == "initial_cross_model_agreement"
        for row in classifications
    )
    reference_fingerprint = _hash_json([
        (
            row["chave"],
            row["categoria_estrita_id"],
            row["categoria_cobertura_id"],
            row["status_consenso"],
        )
        for row in classifications
    ])
    reference_output = OrderedDict([
        ("metadata", OrderedDict([
            ("version", VERSION),
            ("natureza", "projecao_automatica_no_alvo_operacional_curado_ex_post"),
            ("source_fingerprint", source_fingerprint),
            ("analytic_source_fingerprint", analytic_source_fingerprint),
            ("portfolio_fingerprint", portfolio_fingerprint),
            ("scope_fingerprint", scope_fingerprint),
            (
                "scope_method",
                "deterministic_structured_request_type_prefilter",
            ),
            ("llm_used_for_scope", False),
            ("reference_fingerprint", reference_fingerprint),
            ("modelos", models),
            ("model_digests", digests),
            ("roundtrip_identifier_policy", ROUNDTRIP_IDENTIFIER_POLICY),
            ("jira_key_exposed_to_reference_models", False),
            ("n_escopo", len(classifications)),
            ("n_consenso_estrito", strict_count),
            ("n_sem_consenso_estrito", len(classifications) - strict_count),
            (
                "consenso_estrito_pct",
                round(strict_count / max(len(classifications), 1) * 100, 4),
            ),
            (
                "acordo_inicial_pct",
                round(initial_agreement / max(len(classifications), 1) * 100, 4),
            ),
        ])),
        ("classificacoes", classifications),
    ])
    _write_json(out_dir / "06_referencia_consenso.json", reference_output)

    quality = OrderedDict([
        ("version", VERSION),
        ("natureza", "qualidade_agregada_da_referencia_automatica"),
        ("source_fingerprint", source_fingerprint),
        ("analytic_source_fingerprint", analytic_source_fingerprint),
        ("portfolio_fingerprint", portfolio_fingerprint),
        ("scope_fingerprint", scope_fingerprint),
        (
            "scope_method",
            "deterministic_structured_request_type_prefilter",
        ),
        ("llm_used_for_scope", False),
        ("reference_fingerprint", reference_fingerprint),
        ("n_total", len(rows)),
        ("n_sala_sigilo_excluidos", len(exclusions)),
        (
            "n_sala_acordo_entre_familias",
            sum(
                row["status_consenso"] == "sala_cross_model_agreement"
                for row in exclusions
            ),
        ),
        (
            "n_sala_quarentena_contestada",
            sum(
                row["status_consenso"]
                == "possible_sala_quarantine_contested"
                for row in exclusions
            ),
        ),
        ("n_escopo_indeterminado_excluidos", len(indeterminate)),
        ("n_analiticos", len(classifications)),
        ("n_consenso_estrito", strict_count),
        ("n_sem_consenso_estrito", len(classifications) - strict_count),
        (
            "n_desempate_automatico",
            sum(
                row["status_consenso"] == "automatic_chair_tiebreak"
                for row in classifications
            ),
        ),
        (
            "n_maioria_estabilidade_3_de_4",
            sum(
                row["status_consenso"] == "stability_majority_3_of_4"
                for row in classifications
            ),
        ),
        (
            "acordo_inicial_modelos_pct",
            round(
                sum(ref_a[key]["decision_id"] == ref_b[key]["decision_id"] for key in included_keys)
                / max(len(included_keys), 1)
                * 100,
                4,
            ),
        ),
        (
            "cohen_kappa_modelos_referencia",
            _kappa(
                [ref_a[key]["decision_id"] for key in included_keys],
                [ref_b[key]["decision_id"] for key in included_keys],
            ),
        ),
        (
            "cohen_kappa_modelos_escopo",
            None,
        ),
        (
            "distribuicao_cobertura",
            dict(Counter(
                row["categoria_cobertura_id"] for row in classifications
            ).most_common()),
        ),
        (
            "distribuicao_estrita",
            dict(Counter(
                row["categoria_estrita_id"] for row in classifications
                if row["categoria_estrita_id"] is not None
            ).most_common()),
        ),
    ])
    _write_json(out_dir / "06_referencia_quality.json", quality)
    print(json.dumps(quality, ensure_ascii=False, indent=2))
    print(f"[referencia] summaries analiticos: {analytic_path}")
    print(f"[referencia] referencia: {out_dir / '06_referencia_consenso.json'}")


if __name__ == "__main__":
    main()
