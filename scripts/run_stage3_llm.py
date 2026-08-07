#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Stage 3: descoberta hierarquica de grupos pela LLM a partir das intencoes.

Todas as intencoes sao lidas em lotes. A LLM propoe grupos locais orientados ao
tratamento da demanda, consolida esses grupos numa taxonomia global e, por fim,
atribui cada chamado a um ID fechado. Categoria antiga e contexto inferido nao
entram nos prompts de descoberta ou atribuicao.
"""
import hashlib
import json
import math
import os
import random
import re
import sys
import threading
import unicodedata
from collections import Counter, defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from llm_client import LLMClient, LLMError, get_client
from projeto import pipeline_data_dir
from discovery_contract import (
    DISCOVERY_CONTRACT_VERSION,
    DISCOVERY_FIELDS,
    ROUNDTRIP_IDENTIFIER_POLICY,
    discovery_payload,
    opaque_roundtrip_id,
)

PD = pipeline_data_dir()
OUT = PD / "03_clusters.json"
DISCOVERY_VERSION = "llm-hierarchical-intent-v3"
REDISCOVERY_VERSION = "llm-recursive-outliers-v5.1"
PIPELINE_VERSION = "llm-semantic-unbounded-v5.3"
OUTLIER_BUCKET_ID = "outlier_residual"


LOCAL_SYSTEM = """Voce e especialista senior em triagem de servicos. Analise UM
lote de intencoes de chamados e descubra grupos naturais LOCAIS com base no
tratamento necessario para atender a demanda.

O mais importante e separar intencoes que exigem fluxos, autorizacoes,
informacoes ou equipes diferentes, mesmo quando usam palavras ou objetos
tecnicos parecidos. Nao agrupe apenas por proximidade lexical.

Servicos ou sistemas operacionalmente independentes devem permanecer em grupos
naturais distintos nesta descoberta. Por exemplo, acesso ao Sistema X nao deve
ser misturado com acesso ao Sistema Y quando nao compartilham o mesmo servico,
equipe, autorizacao, formulario e fluxo de atendimento. Isso nao significa que
o catalogo final tera grupos logicos separados: no Stage 5, request types
distintos podem compartilhar um mesmo agrupador logico de apresentacao.

Nesta etapa, NAO classifique cada chave. Defina somente os grupos locais do
lote. A atribuicao de cada chamado sera feita em outra chamada, com IDs
fechados.

Responda SOMENTE JSON:
{
  "grupos": [
    {
      "local_id": "g1",
      "nome": "nome provisorio curto",
      "descricao": "o que as intencoes deste grupo pedem",
      "tratamento_esperado": "como a demanda e tratada e por que difere das proximas",
      "criterios_inclusao": ["criterio objetivo"],
      "criterios_exclusao": ["demanda parecida que deve ficar fora"]
    }
  ]
}

Regras:
- defina de 4 a 12 grupos locais, salvo lote muito homogeneo;
- nao liste chaves nesta etapa;
- nao crie grupo generico de diversos, outros ou avulsos;
- diferencie incidente, solicitacao, acesso, execucao, restauracao, consulta e
  outras intencoes quando o tratamento for diferente;
- nao use travessao nos textos."""


LOCAL_ASSIGN_SYSTEM = """Voce e analista senior de triagem. Classifique UMA
intencao em exatamente um destino local fechado do lote.

DESTINOS LOCAIS:
{groups}

Escolha pelo tratamento necessario, nao apenas por palavras parecidas. Se a
intencao nao couber com seguranca em nenhum grupo local, marque como avulso.
Avulso nao e erro e nao e categoria generica; e preservacao individual para a
consolidacao global.

Responda SOMENTE JSON:
{
  "destino_tipo": "grupo|avulso",
  "local_id": "g1 ou null",
  "nome_provisorio": "preencher se avulso",
  "tratamento_esperado": "preencher se avulso",
  "motivo": "criterio de escolha ou motivo do avulso"
}

Regras:
- use somente local_id existente quando destino_tipo=grupo;
- se destino_tipo=avulso, local_id deve ser null e os demais campos devem
  explicar a demanda individual;
- nao invente chaves;
- nao use travessao nos textos."""


GLOBAL_DECISION_SYSTEM = """Voce e arquiteto senior de catalogo de servicos.
Leia as unidades semanticas recebidas e proponha uma taxonomia consolidada.

Voce deve definir somente os grupos de destino. NAO relacione unidades de
origem, nao cite IDs, nao conte cobertura e nao classifique cada unidade. O
Python fara essas atribuicoes uma por vez em uma etapa separada.

Use somente blocos neste formato:

[GRUPO]
NOME: nome curto e unico
DESCRICAO: intencao atendida
TRATAMENTO: acao e fluxo que caracterizam o grupo
INCLUI: criterio 1 | criterio 2
EXCLUI: fronteira 1 | fronteira 2
[/GRUPO]

Regras:
- funda conceitos somente quando exigirem essencialmente o mesmo tratamento;
- preserve separados fluxos, autorizacoes, equipes e sistemas independentes;
- nao crie grupo generico de diversos, outros ou avulsos;
- nao cite IDs nem nomes de variaveis da entrada;
- nao escreva nada fora dos blocos;
- nao use travessao nos textos."""


GLOBAL_JSON_SYSTEM = """Voce e compilador JSON estrito. Converta o plano
semantico recebido em JSON, sem decidir pertencimento de unidades de origem.

Responda SOMENTE JSON:
{
  "grupos": [
    {
      "nome": "nome curto e unico",
      "descricao": "intencao atendida",
      "tratamento_esperado": "acao e fluxo do grupo",
      "criterios_inclusao": ["criterio objetivo"],
      "criterios_exclusao": ["fronteira objetiva"]
    }
  ]
}

Regras:
- nao inclua IDs, chaves ou listas de unidades de origem;
- nao acrescente grupos ausentes do plano;
- nao crie grupo generico de diversos, outros ou avulsos;
- nao use travessao nos textos.

Exemplo de entrada:
[GRUPO]
NOME: Restauracao de Banco
DESCRICAO: Recuperar base ou dados a partir de copia valida.
TRATAMENTO: Validar backup, janela e ponto antes da execucao.
INCLUI: restaurar base | recuperar dados
EXCLUI: criar base vazia | liberar acesso
[/GRUPO]

Exemplo de saida:
{
  "grupos": [
    {
      "nome": "Restauracao de Banco",
      "descricao": "Recuperar base ou dados a partir de copia valida.",
      "tratamento_esperado": "Validar backup, janela e ponto antes da execucao.",
      "criterios_inclusao": ["restaurar base", "recuperar dados"],
      "criterios_exclusao": ["criar base vazia", "liberar acesso"]
    }
  ]
}"""


GLOBAL_ASSIGN_SYSTEM = """Voce e analista senior de arquitetura de servicos.
Classifique UMA unidade semantica em um grupo fechado da taxonomia proposta.

GRUPOS DE DESTINO:
{groups}

Responda SOMENTE JSON:
{
  "destino_tipo": "grupo|manter_separado",
  "destino_id": "g1 ou null",
  "justificativa": "comparacao objetiva de tratamento"
}

Escolha grupo somente quando o tratamento, fluxo, autorizacao e fronteira do
servico forem compativeis. Use manter_separado quando nenhum grupo representar
a unidade com seguranca. Use somente um destino_id listado e nao use travessao
nos textos."""


ASSIGN_SYSTEM = """Voce e analista senior de triagem. Classifique UMA intencao
em exatamente um destino da taxonomia fechada abaixo.

DESTINOS:
{groups}

Escolha pelo tratamento necessario, nao apenas por palavras parecidas. Respeite
os criterios de inclusao e exclusao. A categoria antiga do Jira e o contexto
inferido nao sao fornecidos. Use outlier somente quando nenhum grupo representar
com seguranca o tratamento pedido; isso nao e fallback generico.

Responda SOMENTE JSON:
{
  "destino_tipo": "grupo|outlier",
  "destino_id": "0 ou null",
  "confianca": "alta|media|baixa",
  "ambiguidade": false,
  "justificativa": "diferenca de tratamento que sustenta a escolha"
}

Quando destino_tipo=outlier, destino_id deve ser null. Nao invente IDs e nao use
travessao nos textos."""


OUTLIER_SUMMARY_SYSTEM = """Voce e analista senior de catalogo. Leia as
intencoes residuais que nao encontraram grupo natural e produza um resumo
consolidado. Nao classifique chamados, nao liste chaves e nao tente criar IDs.

Responda SOMENTE JSON:
{
  "descricao": "explicacao objetiva do que o conjunto residual representa",
  "principais_demandas": ["demanda recorrente ou representativa"],
  "tratamento_esperado": "como esses casos devem ser revisados",
  "motivo": "por que o conjunto nao forma um grupo natural coerente"
}

Regras:
- sintetize os temas principais sem afirmar que todos os casos sao iguais;
- use de 1 a 12 principais_demandas;
- nao inclua IDs, chaves, contagens inventadas ou dados pessoais;
- nao proponha Chamados avulsos como servico publicavel do catalogo;
- nao use travessao nos textos."""


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256(payload)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def _get_json_client(default_client):
    model = os.getenv("STAGE3_JSON_MODEL", "").strip()
    if not model:
        return default_client
    if getattr(default_client, "provider", "") == "ollama" and model == getattr(
        default_client, "model", ""
    ):
        return default_client
    return LLMClient(provider_override="ollama", model_override=model)


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _as_list(value, limit: int = 4, item_limit: int = 140) -> list[str]:
    source = value if isinstance(value, list) else ([value] if value else [])
    output = []
    for item in source:
        text = str(item).strip()
        if text:
            output.append(text[:item_limit])
        if len(output) >= limit:
            break
    return output


def _intent_payload(item: dict) -> OrderedDict:
    return discovery_payload(item)


def _opaque_working_summaries(
    summaries: list[dict],
) -> tuple[list[dict], dict[str, str]]:
    """Troca chaves Jira por IDs opacos durante todo o contato com a LLM."""
    working = []
    original_by_opaque = {}
    for source in summaries:
        original = str(source.get("chave", "")).strip()
        opaque = opaque_roundtrip_id(original)
        if opaque in original_by_opaque:
            raise ValueError("colisao de identificadores opacos")
        original_by_opaque[opaque] = original
        row = dict(source)
        row["chave"] = opaque
        working.append(row)
    return working, original_by_opaque


def _source_fingerprint(
    items: list[dict],
    version: str | None = None,
) -> str:
    return _hash_json({
        "version": version or PIPELINE_VERSION,
        "discovery_contract_version": DISCOVERY_CONTRACT_VERSION,
        "local_system": LOCAL_SYSTEM,
        "local_assign_system": LOCAL_ASSIGN_SYSTEM,
        "global_decision_system": GLOBAL_DECISION_SYSTEM,
        "global_json_system": GLOBAL_JSON_SYSTEM,
        "global_assign_system": GLOBAL_ASSIGN_SYSTEM,
        "assign_system": ASSIGN_SYSTEM,
        "items": [_intent_payload(item) for item in items],
    })


def _build_batches(items: list[dict], batch_size: int, seed: int) -> list[list[dict]]:
    ordered = sorted(items, key=lambda item: str(item.get("chave", "")))
    random.Random(seed).shuffle(ordered)
    batch_count = max(1, math.ceil(len(ordered) / batch_size))
    base_size, remainder = divmod(len(ordered), batch_count)
    sizes = [base_size + (1 if index < remainder else 0) for index in range(batch_count)]
    batches = []
    start = 0
    for size in sizes:
        batches.append(ordered[start:start + size])
        start += size
    return batches


def _batch_hash(batch: list[dict]) -> str:
    return _hash_json({
        "version": DISCOVERY_VERSION,
        "system": LOCAL_SYSTEM,
        "assign_system": LOCAL_ASSIGN_SYSTEM,
        "items": [_intent_payload(item) for item in batch],
    })


def _missing_as_outlier(item: dict) -> OrderedDict:
    intent = str(item.get("intencao", "")).strip()
    theme = str(item.get("tema", "")).strip()
    request_type = str(item.get("tipo_pedido", "")).strip()
    name = intent or theme or f"Demanda avulsa {item.get('chave', '')}"
    treatment_parts = []
    if request_type:
        treatment_parts.append(f"tipo do pedido: {request_type}")
    if theme:
        treatment_parts.append(f"tema: {theme}")
    treatment_parts.append("avaliar individualmente na consolidacao global")
    return OrderedDict([
        ("chave", str(item.get("chave", "")).strip()),
        ("nome_provisorio", name[:100]),
        ("tratamento_esperado", "; ".join(treatment_parts)[:280]),
        (
            "motivo",
            "Chave omitida pela LLM apos retries; preservada como avulso individual.",
        ),
    ])


def _normalize_local_groups(raw: dict) -> list[OrderedDict]:
    if not isinstance(raw, dict):
        raise LLMError("descoberta local nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("descoberta local sem objeto de resultado")
    raw_groups = body.get("grupos")
    if not isinstance(raw_groups, list):
        raise LLMError("grupos locais devem ser uma lista")

    groups = []
    group_ids = set()
    for index, source in enumerate(raw_groups):
        if not isinstance(source, dict):
            raise LLMError(f"grupo local {index} nao e objeto")
        local_id = str(
            source.get("local_id", source.get("grupo_id", source.get("id", "")))
        ).strip()
        name = str(source.get("nome", "")).strip()
        description = str(source.get("descricao", "")).strip()
        treatment = str(source.get("tratamento_esperado", "")).strip()
        if not local_id or local_id in group_ids:
            raise LLMError(f"local_id ausente ou duplicado: {local_id or '(vazio)'}")
        if not name or not description or not treatment:
            raise LLMError(f"grupo local {local_id} sem nome, descricao ou tratamento")
        group_ids.add(local_id)
        groups.append(OrderedDict([
            ("local_id", local_id),
            ("nome", name[:100]),
            ("descricao", description[:320]),
            ("tratamento_esperado", treatment[:280]),
            ("criterios_inclusao", _as_list(source.get("criterios_inclusao"))),
            ("criterios_exclusao", _as_list(source.get("criterios_exclusao"))),
        ]))
    if not groups:
        raise LLMError("descoberta local sem grupos")
    return groups


def _local_groups_text(groups: list[dict]) -> str:
    lines = []
    for group in groups:
        includes = "; ".join(group.get("criterios_inclusao", []))
        excludes = "; ".join(group.get("criterios_exclusao", []))
        lines.append(
            f"local_id={group['local_id']} | nome={group['nome']} | "
            f"descricao={group['descricao']} | tratamento={group['tratamento_esperado']} | "
            f"inclui={includes} | exclui={excludes}"
        )
    return "\n".join(lines)


def _normalize_local_assignment(raw: dict, valid_group_ids: set[str]) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("atribuicao local nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("atribuicao local sem objeto de resultado")

    destino_tipo = _norm(str(body.get("destino_tipo", "")).strip())
    local_id = body.get("local_id")
    local_id = None if local_id is None else str(local_id).strip()
    if not destino_tipo and local_id in valid_group_ids:
        destino_tipo = "grupo"
    if destino_tipo in {"grupo", "group"}:
        if local_id not in valid_group_ids:
            raise LLMError(f"local_id inexistente na atribuicao local: {local_id}")
        return OrderedDict([
            ("destino_tipo", "grupo"),
            ("local_id", local_id),
        ])
    if destino_tipo in {"avulso", "outlier"}:
        name = str(body.get("nome_provisorio", "")).strip()
        treatment = str(body.get("tratamento_esperado", "")).strip()
        reason = str(body.get("motivo", "")).strip()
        if not name or not treatment or not reason:
            raise LLMError("avulso local sem nome, tratamento ou motivo")
        return OrderedDict([
            ("destino_tipo", "avulso"),
            ("nome_provisorio", name[:100]),
            ("tratamento_esperado", treatment[:280]),
            ("motivo", reason[:320]),
        ])
    raise LLMError(f"destino_tipo local invalido: {destino_tipo or '(vazio)'}")


def _assign_item_locally(
    client,
    system: str,
    item: dict,
    valid_group_ids: set[str],
) -> OrderedDict:
    user_base = json.dumps(_intent_payload(item), ensure_ascii=False)
    last_error = "resposta nao processada"
    for attempt in range(1, 4):
        user = user_base
        if attempt > 1:
            user += (
                "\n\nA resposta anterior foi invalida: " + last_error
                + "\nUse somente um local_id existente ou marque como avulso."
            )
        try:
            return _normalize_local_assignment(
                client.chat_json(system, user, max_tokens=420, timeout=900),
                valid_group_ids,
            )
        except LLMError as exc:
            last_error = str(exc)

    fallback = _missing_as_outlier(item)
    fallback["motivo"] = (
        "A LLM nao conseguiu classificar a intencao em grupo local apos retries; "
        "preservada como avulso individual."
    )
    return OrderedDict([
        ("destino_tipo", "avulso"),
        ("nome_provisorio", fallback["nome_provisorio"]),
        ("tratamento_esperado", fallback["tratamento_esperado"]),
        ("motivo", fallback["motivo"]),
    ])


def _normalize_local(
    raw: dict,
    batch: list[dict],
    allow_missing_as_outliers: bool = False,
) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("descoberta local nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("descoberta local sem objeto de resultado")
    raw_groups = body.get("grupos")
    raw_assignments = body.get("atribuicoes")
    raw_outliers = body.get("avulsos")
    if not isinstance(raw_groups, list):
        raise LLMError("grupos locais devem ser uma lista")
    if raw_assignments is not None and not isinstance(raw_assignments, list):
        raise LLMError("atribuicoes locais devem ser uma lista quando informadas")
    if not isinstance(raw_outliers, list):
        raise LLMError("avulsos locais devem ser uma lista")

    groups = []
    group_ids = set()
    group_keys_by_id = {}
    for index, source in enumerate(raw_groups):
        if not isinstance(source, dict):
            raise LLMError(f"grupo local {index} nao e objeto")
        local_id = str(
            source.get("local_id", source.get("grupo_id", source.get("id", "")))
        ).strip()
        name = str(source.get("nome", "")).strip()
        description = str(source.get("descricao", "")).strip()
        treatment = str(source.get("tratamento_esperado", "")).strip()
        if not local_id or local_id in group_ids:
            raise LLMError(f"local_id ausente ou duplicado: {local_id or '(vazio)'}")
        if not name or not description or not treatment:
            raise LLMError(f"grupo local {local_id} sem nome, descricao ou tratamento")
        raw_group_keys = source.get("chaves", [])
        if raw_group_keys is None:
            raw_group_keys = []
        if not isinstance(raw_group_keys, list):
            raise LLMError(f"grupo local {local_id} tem chaves fora de lista")
        group_keys_by_id[local_id] = [
            str(key).strip() for key in raw_group_keys if str(key).strip()
        ]
        group_ids.add(local_id)
        groups.append(OrderedDict([
            ("local_id", local_id),
            ("nome", name[:100]),
            ("descricao", description[:320]),
            ("tratamento_esperado", treatment[:280]),
            ("criterios_inclusao", _as_list(source.get("criterios_inclusao"))),
            ("criterios_exclusao", _as_list(source.get("criterios_exclusao"))),
        ]))

    expected_keys = [str(item.get("chave", "")).strip() for item in batch]
    assignments_by_key = {}
    counts = Counter()
    if isinstance(raw_assignments, list):
        for source in raw_assignments:
            if not isinstance(source, dict):
                raise LLMError("atribuicoes locais contem item nao objeto")
            key = str(source.get("chave", "")).strip()
            local_id = str(
                source.get("local_id", source.get("grupo_id", ""))
            ).strip()
            if not key or key in assignments_by_key:
                raise LLMError(f"chave ausente ou duplicada na atribuicao local: {key}")
            if local_id not in group_ids:
                raise LLMError(f"atribuicao de {key} usa local_id inexistente: {local_id}")
            assignments_by_key[key] = local_id
            counts[local_id] += 1
    else:
        for local_id, keys in group_keys_by_id.items():
            for key in keys:
                if not key or key in assignments_by_key:
                    raise LLMError(f"chave ausente ou duplicada em grupos[].chaves: {key}")
                assignments_by_key[key] = local_id
                counts[local_id] += 1

    outliers_by_key = {}
    for source in raw_outliers:
        if not isinstance(source, dict):
            raise LLMError("avulsos locais contem item nao objeto")
        key = str(source.get("chave", "")).strip()
        name = str(source.get("nome_provisorio", "")).strip()
        treatment = str(source.get("tratamento_esperado", "")).strip()
        reason = str(source.get("motivo", "")).strip()
        if not key or key in outliers_by_key or key in assignments_by_key:
            raise LLMError(f"chave ausente, repetida ou sobreposta em avulsos: {key}")
        if not name or not treatment or not reason:
            raise LLMError(f"avulso {key} sem nome, tratamento ou motivo")
        outliers_by_key[key] = OrderedDict([
            ("chave", key),
            ("nome_provisorio", name[:100]),
            ("tratamento_esperado", treatment[:280]),
            ("motivo", reason[:320]),
        ])

    covered = set(assignments_by_key) | set(outliers_by_key)
    missing = sorted(set(expected_keys) - covered)
    unknown = sorted(covered - set(expected_keys))
    if missing and not unknown and allow_missing_as_outliers:
        max_ratio = float(os.getenv("STAGE3_MAX_AUTO_OUTLIER_MISSING_RATIO", "0.25"))
        ratio = len(missing) / max(len(expected_keys), 1)
        if ratio <= max_ratio:
            item_by_key = {str(item.get("chave", "")).strip(): item for item in batch}
            for key in missing:
                outliers_by_key[key] = _missing_as_outlier(item_by_key[key])
            covered = set(assignments_by_key) | set(outliers_by_key)
            missing = sorted(set(expected_keys) - covered)
    if missing or unknown or len(covered) != len(expected_keys):
        raise LLMError(
            f"cobertura local divergente: faltando={len(missing)} extras={len(unknown)}"
        )
    empty_groups = [local_id for local_id in group_ids if counts[local_id] == 0]
    if empty_groups:
        raise LLMError("grupos locais vazios: " + ", ".join(sorted(empty_groups)))

    assignments = [
        OrderedDict([("chave", key), ("local_id", assignments_by_key[key])])
        for key in expected_keys if key in assignments_by_key
    ]
    outliers = [outliers_by_key[key] for key in expected_keys if key in outliers_by_key]
    return OrderedDict([
        ("grupos", groups),
        ("atribuicoes", assignments),
        ("avulsos", outliers),
    ])


def _discovery_user(batch: list[dict], batch_index: int) -> str:
    return json.dumps({
        "lote": batch_index,
        "total_no_lote": len(batch),
        "intencoes": [_intent_payload(item) for item in batch],
    }, ensure_ascii=False, separators=(",", ":"))


def _discover_batch(
    client,
    batch: list[dict],
    batch_index: int,
    log_label: str = "Stage 3a",
) -> OrderedDict:
    base_user = _discovery_user(batch, batch_index)
    last_error = "resposta nao processada"
    groups = None
    for attempt in range(1, 4):
        user = base_user
        if attempt > 1:
            user += (
                "\n\nA tentativa anterior violou o contrato: " + last_error
                + "\nRegenere apenas a lista de grupos locais, sem classificar chaves."
            )
        try:
            raw = client.chat_json(
                LOCAL_SYSTEM,
                user,
                max_tokens=2400,
                timeout=1200,
            )
            groups = _normalize_local_groups(raw)
            break
        except LLMError as exc:
            last_error = str(exc)
            print(
                f"[{log_label}] lote {batch_index} grupos tentativa {attempt}/3 invalida: "
                f"{last_error}"
            )
    if groups is None:
        raise LLMError(
            f"lote {batch_index} sem grupos locais validos apos 3 tentativas: "
            f"{last_error}"
        )

    system = LOCAL_ASSIGN_SYSTEM.replace("{groups}", _local_groups_text(groups))
    valid_group_ids = {group["local_id"] for group in groups}
    assignments = []
    outliers = []
    used_group_ids = set()
    for position, item in enumerate(batch, start=1):
        key = str(item.get("chave", "")).strip()
        result = _assign_item_locally(client, system, item, valid_group_ids)
        if result["destino_tipo"] == "grupo":
            assignments.append(OrderedDict([
                ("chave", key),
                ("local_id", result["local_id"]),
            ]))
            used_group_ids.add(result["local_id"])
        else:
            outliers.append(OrderedDict([
                ("chave", key),
                ("nome_provisorio", result["nome_provisorio"]),
                ("tratamento_esperado", result["tratamento_esperado"]),
                ("motivo", result["motivo"]),
            ]))
        if position % 50 == 0 or position == len(batch):
            print(
                f"[{log_label}] lote {batch_index}: "
                f"{position}/{len(batch)} atribuicoes locais"
            )

    active_groups = [group for group in groups if group["local_id"] in used_group_ids]
    return _normalize_local({
        "grupos": active_groups,
        "atribuicoes": assignments,
        "avulsos": outliers,
    }, batch)


def _load_discovery_checkpoint(
    path: Path,
    expected_hashes: dict[int, str],
    model: str,
) -> dict[int, dict]:
    found = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            index = int(row["batch_index"])
            if (
                row.get("pipeline_version") == DISCOVERY_VERSION
                and row.get("model") == model
                and row.get("batch_hash") == expected_hashes.get(index)
                and isinstance(row.get("result"), dict)
            ):
                found[index] = row["result"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return found


def _make_local_records(
    discoveries: dict[int, dict],
    batches: list[list[dict]],
) -> list[dict]:
    records = []
    for batch_index, batch in enumerate(batches, start=1):
        result = discoveries[batch_index]
        item_by_key = {str(item["chave"]): item for item in batch}
        keys_by_group = defaultdict(list)
        for assignment in result["atribuicoes"]:
            keys_by_group[assignment["local_id"]].append(assignment["chave"])
        for group_index, group in enumerate(result["grupos"], start=1):
            record_id = f"b{batch_index:03d}_g{group_index:02d}"
            examples = []
            seen = set()
            for key in keys_by_group[group["local_id"]]:
                intent = str(item_by_key[key].get("intencao", "")).strip()
                normalized = _norm(intent)
                if intent and normalized not in seen:
                    seen.add(normalized)
                    examples.append(intent[:220])
                if len(examples) >= 2:
                    break
            records.append({
                "id": record_id,
                "tipo_unidade": "grupo_local",
                "nome": group["nome"],
                "descricao": group["descricao"],
                "tratamento_esperado": group["tratamento_esperado"],
                "criterios_inclusao": group["criterios_inclusao"],
                "criterios_exclusao": group["criterios_exclusao"],
                "volume": len(keys_by_group[group["local_id"]]),
                "exemplos": examples,
                "origens_base": [record_id],
                "chaves": list(keys_by_group[group["local_id"]]),
            })
        for outlier_index, outlier in enumerate(result["avulsos"], start=1):
            record_id = f"b{batch_index:03d}_o{outlier_index:03d}"
            item = item_by_key[outlier["chave"]]
            intent = str(item.get("intencao", "")).strip()
            records.append({
                "id": record_id,
                "tipo_unidade": "avulso_local",
                "nome": outlier["nome_provisorio"],
                "descricao": intent,
                "tratamento_esperado": outlier["tratamento_esperado"],
                "criterios_inclusao": [intent] if intent else [],
                "criterios_exclusao": [],
                "motivo": outlier["motivo"],
                "volume": 1,
                "exemplos": [intent] if intent else [],
                "origens_base": [record_id],
                "chaves": [outlier["chave"]],
            })
    return records


def _build_local_audit(
    discoveries: dict[int, dict],
    batches: list[list[dict]],
) -> OrderedDict:
    output = []
    for batch_index, batch in enumerate(batches, start=1):
        result = discoveries[batch_index]
        keys_by_group = defaultdict(list)
        for assignment in result["atribuicoes"]:
            keys_by_group[assignment["local_id"]].append(assignment["chave"])
        groups = []
        for group in result["grupos"]:
            keys = keys_by_group[group["local_id"]]
            groups.append(OrderedDict([
                ("local_id", group["local_id"]),
                ("nome", group["nome"]),
                ("descricao", group["descricao"]),
                ("tratamento_esperado", group["tratamento_esperado"]),
                ("criterios_inclusao", group["criterios_inclusao"]),
                ("criterios_exclusao", group["criterios_exclusao"]),
                ("total", len(keys)),
                ("chaves", keys),
            ]))
        output.append(OrderedDict([
            ("lote", batch_index),
            ("total_chamados", len(batch)),
            ("grupos", groups),
            ("avulsos", result["avulsos"]),
        ]))
    return OrderedDict([
        ("pipeline_version", PIPELINE_VERSION),
        ("discovery_version", DISCOVERY_VERSION),
        ("total_lotes", len(batches)),
        ("lotes", output),
    ])


def _compact_record(record: dict) -> OrderedDict:
    return OrderedDict([
        ("id", record["id"]),
        ("tipo", record.get("tipo_unidade", "grupo_local")),
        ("nome", record["nome"]),
        ("descricao", str(record.get("descricao", ""))[:240]),
        ("tratamento", str(record.get("tratamento_esperado", ""))[:220]),
        ("inclui", _as_list(record.get("criterios_inclusao"), 3, 100)),
        ("exclui", _as_list(record.get("criterios_exclusao"), 3, 100)),
        ("motivo", str(record.get("motivo", ""))[:180]),
        ("volume", int(record.get("volume", 0) or 0)),
        ("exemplos", _as_list(record.get("exemplos"), 2, 180)),
    ])


def _records_size(records: list[dict]) -> int:
    return len(json.dumps(
        [_compact_record(record) for record in records],
        ensure_ascii=False,
        separators=(",", ":"),
    ))


def _merge_max_records() -> int:
    return max(10, int(os.getenv("STAGE3_MERGE_MAX_RECORDS", "20")))


def _chunk_records(records: list[dict], char_budget: int) -> list[list[dict]]:
    chunks = []
    current = []
    current_size = 2
    max_records = _merge_max_records()
    for record in records:
        size = len(json.dumps(_compact_record(record), ensure_ascii=False)) + 1
        if current and (
            current_size + size > char_budget or len(current) >= max_records
        ):
            chunks.append(current)
            current = []
            current_size = 2
        current.append(record)
        current_size += size
    if current:
        chunks.append(current)
    if (
        len(chunks) > 1
        and len(chunks[-1]) < 3
        and len(chunks[-2]) + len(chunks[-1]) <= max_records
    ):
        chunks[-2].extend(chunks.pop())
    return chunks


def _initial_outlier_items(
    discoveries: dict[int, dict],
    batches: list[list[dict]],
) -> list[dict]:
    items = []
    for batch_index, batch in enumerate(batches, start=1):
        by_key = {str(item["chave"]): item for item in batch}
        for outlier in discoveries[batch_index]["avulsos"]:
            items.append(by_key[str(outlier["chave"])])
    return items


def _load_outlier_discovery_checkpoint(
    path: Path,
    round_index: int,
    expected_hashes: dict[int, str],
    model: str,
) -> dict[int, dict]:
    found = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            batch_index = int(row["batch_index"])
            if (
                int(row.get("round_index", -1)) == round_index
                and row.get("pipeline_version") == REDISCOVERY_VERSION
                and row.get("model") == model
                and row.get("batch_hash") == expected_hashes.get(batch_index)
                and isinstance(row.get("result"), dict)
            ):
                found[batch_index] = row["result"]
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return found


def _materialize_rediscovery_batch(
    result: dict,
    batch: list[dict],
    round_index: int,
    batch_index: int,
    min_support: int,
) -> tuple[list[dict], list[dict]]:
    by_key = {str(item["chave"]): item for item in batch}
    keys_by_group = defaultdict(list)
    for assignment in result["atribuicoes"]:
        keys_by_group[str(assignment["local_id"])].append(str(assignment["chave"]))

    accepted = []
    residual_keys = {str(item["chave"]) for item in batch}
    for group_index, group in enumerate(result["grupos"], start=1):
        keys = keys_by_group.get(str(group["local_id"]), [])
        if len(keys) < min_support:
            continue
        record_id = f"a_r{round_index:02d}_b{batch_index:03d}_g{group_index:02d}"
        examples = []
        seen = set()
        for key in keys:
            intent = str(by_key[key].get("intencao", "")).strip()
            normalized = _norm(intent)
            if intent and normalized not in seen:
                seen.add(normalized)
                examples.append(intent[:220])
            if len(examples) >= 3:
                break
        accepted.append({
            "id": record_id,
            "tipo_unidade": "grupo_reagrupado",
            "nome": group["nome"],
            "descricao": group["descricao"],
            "tratamento_esperado": group["tratamento_esperado"],
            "criterios_inclusao": group["criterios_inclusao"],
            "criterios_exclusao": group["criterios_exclusao"],
            "volume": len(keys),
            "exemplos": examples,
            "origens_base": [record_id],
            "chaves": list(keys),
        })
        residual_keys.difference_update(keys)

    residual = [item for item in batch if str(item["chave"]) in residual_keys]
    covered = {
        key for record in accepted for key in record.get("chaves", [])
    } | {str(item["chave"]) for item in residual}
    expected = {str(item["chave"]) for item in batch}
    if covered != expected:
        raise LLMError(
            "reagrupamento de avulsos perdeu cobertura: "
            f"faltando={len(expected - covered)} extras={len(covered - expected)}"
        )
    return accepted, residual


def _rediscover_outliers(
    client,
    initial_items: list[dict],
    batch_size: int,
    seed: int,
    source_fingerprint: str,
) -> tuple[list[dict], list[dict], list[dict]]:
    if not initial_items:
        return [], [], []

    safe_model = _safe_name(client.model_label)
    checkpoint = PD / (
        f"_ckpt_stage3_outlier_discovery__{safe_model}__"
        f"s{source_fingerprint[:12]}.jsonl"
    )
    max_rounds = max(1, int(os.getenv("STAGE3_OUTLIER_MAX_ROUNDS", "8")))
    min_support = max(
        2, int(os.getenv("STAGE3_OUTLIER_MIN_GROUP_SIZE", "2"))
    )
    workers = max(1, int(os.getenv("PIPELINE_WORKERS", "2")))
    residual = list(initial_items)
    all_groups = []
    audit = []
    no_progress_rounds = 0

    for round_index in range(1, max_rounds + 1):
        batches = _build_batches(
            residual,
            batch_size,
            seed + round_index * 1009,
        )
        expected_hashes = {
            index: _batch_hash(batch)
            for index, batch in enumerate(batches, start=1)
        }
        discoveries = _load_outlier_discovery_checkpoint(
            checkpoint,
            round_index,
            expected_hashes,
            client.model_label,
        )
        pending = [
            (index, batch)
            for index, batch in enumerate(batches, start=1)
            if index not in discoveries
        ]
        print(
            f"[Stage 3b.1/{client.model_label}] rodada={round_index} "
            f"avulsos={len(residual)} lotes={len(batches)} "
            f"feitos={len(discoveries)} pendentes={len(pending)}"
        )
        errors = []
        if pending:
            with open(checkpoint, "a", encoding="utf-8") as handle:
                with ThreadPoolExecutor(max_workers=workers) as executor:
                    futures = {
                        executor.submit(
                            _discover_batch,
                            client,
                            batch,
                            index,
                            f"Stage 3b.1/r{round_index}",
                        ): (index, batch)
                        for index, batch in pending
                    }
                    for future in as_completed(futures):
                        index, _ = futures[future]
                        try:
                            result = future.result()
                        except LLMError as exc:
                            errors.append(f"lote {index}: {exc}")
                            print(
                                f"[Stage 3b.1] ERRO rodada {round_index} "
                                f"lote {index}: {exc}"
                            )
                            continue
                        discoveries[index] = result
                        handle.write(json.dumps({
                            "pipeline_version": REDISCOVERY_VERSION,
                            "model": client.model_label,
                            "round_index": round_index,
                            "batch_index": index,
                            "batch_hash": expected_hashes[index],
                            "result": result,
                        }, ensure_ascii=False, separators=(",", ":")) + "\n")
                        handle.flush()
        if errors or len(discoveries) != len(batches):
            raise LLMError(
                "reagrupamento de avulsos incompleto; reexecute para retomar"
            )

        round_groups = []
        next_residual = []
        for batch_index, batch in enumerate(batches, start=1):
            groups, batch_residual = _materialize_rediscovery_batch(
                discoveries[batch_index],
                batch,
                round_index,
                batch_index,
                min_support,
            )
            round_groups.extend(groups)
            next_residual.extend(batch_residual)
        grouped_tickets = len(residual) - len(next_residual)
        audit.append(OrderedDict([
            ("rodada", round_index),
            ("entrada_avulsos", len(residual)),
            ("lotes", len(batches)),
            ("novos_grupos", len(round_groups)),
            ("chamados_agrupados", grouped_tickets),
            ("avulsos_restantes", len(next_residual)),
        ]))
        print(
            f"[Stage 3b.1] rodada {round_index}: "
            f"{len(round_groups)} novos grupos, "
            f"{grouped_tickets} chamados agrupados, "
            f"{len(next_residual)} avulsos restantes"
        )
        all_groups.extend(round_groups)
        residual = next_residual
        if not residual:
            break
        if grouped_tickets == 0:
            no_progress_rounds += 1
        else:
            no_progress_rounds = 0
        if len(residual) <= batch_size and grouped_tickets == 0:
            break
        if no_progress_rounds >= 2 and len(residual) > batch_size:
            print(
                f"[Stage 3b.1] rodada {round_index}: sem progresso; "
                "os avulsos serao reembaralhados em nova rodada."
            )
    else:
        print(
            f"[Stage 3b.1] limite de {max_rounds} rodadas atingido; "
            f"{len(residual)} chamados seguem para reconciliacao final."
        )
    return all_groups, residual, audit


def _proposal_input(records: list[dict]) -> list[OrderedDict]:
    return [OrderedDict([
        ("nome", record["nome"]),
        ("descricao", str(record.get("descricao", ""))[:260]),
        ("tratamento", str(record.get("tratamento_esperado", ""))[:240]),
        ("inclui", _as_list(record.get("criterios_inclusao"), 3, 100)),
        ("exclui", _as_list(record.get("criterios_exclusao"), 3, 100)),
        ("volume", int(record.get("volume", 0) or 0)),
        ("exemplos", _as_list(record.get("exemplos"), 2, 160)),
    ]) for record in records]


def _validate_group_plan(plan: str) -> str:
    if not isinstance(plan, str) or "[GRUPO]" not in plan:
        raise LLMError("plano global vazio ou fora do formato canonico")
    forbidden = re.search(r"(?im)^\s*(IDS?|CHAVES?|ORIGENS?)\s*:", plan)
    if forbidden:
        raise LLMError("plano global tentou declarar pertencimento de origens")
    if plan.count("[GRUPO]") != plan.count("[/GRUPO]"):
        raise LLMError("plano global contem bloco de grupo incompleto")
    return plan


def _normalize_group_proposals(
    raw: dict,
    expected_count: int | None = None,
) -> list[OrderedDict]:
    if not isinstance(raw, dict):
        raise LLMError("compilacao da taxonomia nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    raw_groups = body.get("grupos") if isinstance(body, dict) else None
    if not isinstance(raw_groups, list) or not raw_groups:
        raise LLMError("compilacao da taxonomia sem grupos")
    if expected_count is not None and len(raw_groups) != expected_count:
        raise LLMError(
            "compilacao alterou a quantidade de grupos do plano: "
            f"esperado={expected_count} recebido={len(raw_groups)}"
        )
    groups = []
    names = Counter()
    for index, source in enumerate(raw_groups, start=1):
        if not isinstance(source, dict):
            raise LLMError(f"grupo proposto {index} nao e objeto")
        name = str(source.get("nome", "")).strip()
        description = str(source.get("descricao", "")).strip()
        treatment = str(source.get("tratamento_esperado", "")).strip()
        if not name or not description or not treatment:
            raise LLMError(
                f"grupo proposto {index} sem nome, descricao ou tratamento"
            )
        normalized = _norm(name)
        names[normalized] += 1
        if names[normalized] > 1:
            adjusted = f"{name} ({names[normalized]})"
            print(
                f"[Stage 3b.2] AVISO: nome proposto duplicado ajustado: "
                f"{name} -> {adjusted}"
            )
            name = adjusted
        groups.append(OrderedDict([
            ("proposal_id", f"g{index}"),
            ("nome", name[:100]),
            ("descricao", description[:360]),
            ("tratamento_esperado", treatment[:320]),
            ("criterios_inclusao", _as_list(source.get("criterios_inclusao"))),
            ("criterios_exclusao", _as_list(source.get("criterios_exclusao"))),
        ]))
    return groups


def _proposal_groups_text(groups: list[dict]) -> str:
    return "\n".join(
        f"id={group['proposal_id']} | nome={group['nome']} | "
        f"descricao={group['descricao']} | "
        f"tratamento={group['tratamento_esperado']} | "
        f"inclui={'; '.join(group['criterios_inclusao'])} | "
        f"exclui={'; '.join(group['criterios_exclusao'])}"
        for group in groups
    )


def _normalize_group_destination(raw: dict, valid_ids: set[str]) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("atribuicao de unidade nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("atribuicao de unidade sem objeto de resultado")
    destination_type = _norm(str(body.get("destino_tipo", "")))
    destination_id = body.get("destino_id")
    destination_id = None if destination_id is None else str(destination_id).strip()
    justification = str(body.get("justificativa", "")).strip()
    if not justification:
        raise LLMError("atribuicao de unidade sem justificativa")
    if destination_type in {"grupo", "group"}:
        if destination_id not in valid_ids:
            raise LLMError(f"grupo proposto inexistente: {destination_id}")
        return OrderedDict([
            ("destino_tipo", "grupo"),
            ("destino_id", destination_id),
            ("justificativa", justification[:400]),
        ])
    if destination_type in {"manter separado", "manter_separado", "separado"}:
        return OrderedDict([
            ("destino_tipo", "manter_separado"),
            ("destino_id", None),
            ("justificativa", justification[:400]),
        ])
    raise LLMError(
        f"destino_tipo de unidade invalido: {destination_type or '(vazio)'}"
    )


def _assign_group_record(client, groups: list[dict], record: dict) -> OrderedDict:
    system = GLOBAL_ASSIGN_SYSTEM.replace("{groups}", _proposal_groups_text(groups))
    user_base = json.dumps(_proposal_input([record])[0], ensure_ascii=False)
    valid_ids = {group["proposal_id"] for group in groups}
    last_error = "resposta nao processada"
    for attempt in range(1, 4):
        user = user_base
        if attempt > 1:
            user += (
                "\n\nA resposta anterior foi invalida: " + last_error
                + "\nUse um grupo listado ou manter_separado."
            )
        try:
            return _normalize_group_destination(
                client.chat_json(system, user, max_tokens=360, timeout=900),
                valid_ids,
            )
        except LLMError as exc:
            last_error = str(exc)
    raise LLMError(
        f"unidade {record['id']} sem atribuicao valida apos 3 tentativas: "
        f"{last_error}"
    )


def _materialize_proposal_assignments(
    proposals: list[dict],
    records: list[dict],
    assignments: list[dict],
    prefix: str,
) -> list[dict]:
    if len(assignments) != len(records):
        raise LLMError(
            "quantidade de atribuicoes diverge das unidades de origem: "
            f"{len(assignments)} != {len(records)}"
        )
    by_proposal = defaultdict(list)
    separate = []
    for record, assignment in zip(records, assignments):
        if assignment["destino_tipo"] == "grupo":
            by_proposal[assignment["destino_id"]].append(record)
        else:
            separate.append(record)

    output = []
    output_index = 0
    for proposal in proposals:
        sources = by_proposal.get(proposal["proposal_id"], [])
        output_index += 1
        examples = []
        seen = set()
        for source in sources:
            for example in source.get("exemplos", []):
                normalized = _norm(example)
                if example and normalized not in seen:
                    seen.add(normalized)
                    examples.append(example)
                if len(examples) >= 3:
                    break
            if len(examples) >= 3:
                break
        output.append({
            "id": f"{prefix}_g{output_index:03d}",
            "tipo_unidade": "grupo_consolidado",
            "nome": proposal["nome"],
            "descricao": proposal["descricao"],
            "tratamento_esperado": proposal["tratamento_esperado"],
            "criterios_inclusao": proposal["criterios_inclusao"],
            "criterios_exclusao": proposal["criterios_exclusao"],
            "volume": sum(int(source.get("volume", 0) or 0) for source in sources),
            "exemplos": examples,
            "origens_base": sorted({
                origin
                for source in sources
                for origin in source.get("origens_base", [source["id"]])
            }),
            "chaves": sorted({
                key for source in sources for key in source.get("chaves", [])
            }),
        })
    for source in separate:
        output_index += 1
        preserved = dict(source)
        preserved["id"] = f"{prefix}_s{output_index:03d}"
        preserved["tipo_unidade"] = "grupo_preservado"
        output.append(preserved)
    return output


def _validate_merge_chunk_output(output: list[dict], records: list[dict]) -> None:
    if not isinstance(output, list) or not output:
        raise LLMError("checkpoint de consolidacao vazio ou invalido")
    expected_origins = Counter(
        origin
        for record in records
        for origin in record.get("origens_base", [record["id"]])
    )
    found_origins = Counter(
        origin
        for record in output
        for origin in record.get("origens_base", [])
    )
    expected_keys = Counter(
        str(key) for record in records for key in record.get("chaves", [])
    )
    found_keys = Counter(
        str(key) for record in output for key in record.get("chaves", [])
    )
    if found_origins != expected_origins:
        raise LLMError("checkpoint de consolidacao diverge nas origens")
    if found_keys != expected_keys:
        raise LLMError("checkpoint de consolidacao diverge nas chaves")
    for index, record in enumerate(output, start=1):
        if not all(str(record.get(field, "")).strip() for field in (
            "id", "nome", "descricao", "tratamento_esperado"
        )):
            raise LLMError(
                f"checkpoint de consolidacao tem grupo {index} incompleto"
            )


def _merge_chunk_fingerprint(
    client,
    json_client,
    records: list[dict],
    prefix: str,
    plan_max_tokens: int,
    json_max_tokens: int,
) -> str:
    return _hash_json({
        "pipeline_version": PIPELINE_VERSION,
        "model": client.model_label,
        "json_model": json_client.model_label,
        "prefix": prefix,
        "global_decision_system": GLOBAL_DECISION_SYSTEM,
        "global_json_system": GLOBAL_JSON_SYSTEM,
        "global_assign_system": GLOBAL_ASSIGN_SYSTEM,
        "group_count_policy": "semantic_no_numeric_limit",
        "plan_max_tokens": plan_max_tokens,
        "json_max_tokens": json_max_tokens,
        "records": records,
    })


def _load_merge_chunk_checkpoint(path: Path, fingerprint: str) -> list[dict] | None:
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            if (
                row.get("pipeline_version") == PIPELINE_VERSION
                and row.get("fingerprint") == fingerprint
                and isinstance(row.get("result"), list)
            ):
                return row["result"]
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return None


def _consolidate_group_chunk(
    client,
    json_client,
    records: list[dict],
    prefix: str,
) -> list[dict]:
    plan_max_tokens = max(
        3000, int(os.getenv("STAGE3_PLAN_MAX_TOKENS", "9000"))
    )
    json_max_tokens = max(
        3000, int(os.getenv("STAGE3_JSON_MAX_TOKENS", "9000"))
    )
    safe_model = _safe_name(client.model_label)
    safe_json_model = _safe_name(json_client.model_label)
    checkpoint = PD / (
        f"_ckpt_stage3_merge__{safe_model}__json_{safe_json_model}.jsonl"
    )
    fingerprint = _merge_chunk_fingerprint(
        client,
        json_client,
        records,
        prefix,
        plan_max_tokens,
        json_max_tokens,
    )
    cached = _load_merge_chunk_checkpoint(checkpoint, fingerprint)
    if cached is not None:
        _validate_merge_chunk_output(cached, records)
        print(
            f"[Stage 3b.2] {prefix}: cache reutilizado "
            f"({len(records)} unidades)"
        )
        return cached

    payload = json.dumps({
        "regra_de_cardinalidade": (
            "Nao existe minimo ou maximo de grupos naturais nesta etapa. Uma "
            "unidade que misture servicos distintos pode originar mais de um "
            "grupo natural, mas isso nao define a quantidade final de grupos "
            "logicos do catalogo."
        ),
        "unidades_sem_ids": _proposal_input(records),
    }, ensure_ascii=False, separators=(",", ":"))
    last_error = "resposta nao processada"
    for attempt in range(1, 4):
        user_payload = payload
        if attempt > 1:
            user_payload += (
                "\n\nCORRECAO OBRIGATORIA: a resposta anterior falhou por: "
                + last_error
                + ". Responda novamente com todos os blocos fechados e textos "
                "mais concisos, sem remover grupos semanticamente distintos."
            )
        try:
            plan = _validate_group_plan(client.chat_text(
                GLOBAL_DECISION_SYSTEM,
                user_payload,
                temperature=0.0,
                max_tokens=plan_max_tokens,
                timeout=1800,
            ))
            raw = json_client.chat_json(
                GLOBAL_JSON_SYSTEM,
                json.dumps({"plano_semantico": plan}, ensure_ascii=False),
                max_tokens=json_max_tokens,
                timeout=1800,
            )
            proposals = _normalize_group_proposals(
                raw,
                plan.count("[GRUPO]"),
            )
            assignments = []
            for position, record in enumerate(records, start=1):
                assignments.append(_assign_group_record(client, proposals, record))
                if position % 25 == 0 or position == len(records):
                    print(
                        f"[Stage 3b.2] {prefix}: {position}/{len(records)} "
                        "unidades reconciliadas"
                    )
            result = _materialize_proposal_assignments(
                proposals, records, assignments, prefix
            )
            _validate_merge_chunk_output(result, records)
            with open(checkpoint, "a", encoding="utf-8") as handle:
                handle.write(json.dumps({
                    "pipeline_version": PIPELINE_VERSION,
                    "fingerprint": fingerprint,
                    "prefix": prefix,
                    "model": client.model_label,
                    "json_model": json_client.model_label,
                    "result": result,
                }, ensure_ascii=False, separators=(",", ":")) + "\n")
                handle.flush()
            return result
        except LLMError as exc:
            last_error = str(exc)
            print(
                f"[Stage 3b.2] {prefix} tentativa {attempt}/3 invalida: "
                f"{last_error}"
            )
    raise LLMError(
        f"{prefix} sem taxonomia valida apos 3 tentativas: {last_error}"
    )


def _consolidate_taxonomy(
    client,
    json_client,
    local_records: list[dict],
    char_budget: int,
) -> tuple[list[dict], list[dict], list[dict]]:
    if not local_records:
        raise LLMError("nao ha grupos para consolidar")
    current = list(local_records)
    rounds = []
    round_index = 0
    no_progress = 0
    global_char_budget = max(
        char_budget,
        int(os.getenv("STAGE3_GLOBAL_CHAR_BUDGET", "60000")),
    )
    global_max_records = max(
        1,
        int(os.getenv("STAGE3_GLOBAL_MAX_RECORDS", "160")),
    )
    while (
        _records_size(current) > global_char_budget
        or len(current) > global_max_records
    ):
        round_index += 1
        if round_index > 6:
            raise LLMError("consolidacao excedeu seis rodadas intermediarias")
        if round_index > 1:
            random.Random(7300 + round_index).shuffle(current)
        chunks = _chunk_records(current, char_budget)
        if len(chunks) < 2:
            raise LLMError("nao foi possivel dividir grupos dentro do limite de contexto")
        next_records = []
        before = len(current)
        for chunk_index, chunk in enumerate(chunks, start=1):
            next_records.extend(_consolidate_group_chunk(
                client,
                json_client,
                chunk,
                f"r{round_index:02d}c{chunk_index:02d}",
            ))
        if len(next_records) >= before:
            no_progress += 1
        else:
            no_progress = 0
        rounds.append({
            "rodada": round_index,
            "entrada": before,
            "lotes": len(chunks),
            "saida": len(next_records),
            "reduziu": len(next_records) < before,
        })
        current = next_records
        if no_progress >= 2:
            raise LLMError(
                "duas rodadas intermediarias sem reducao suficiente para o "
                "contexto global"
            )

    final_records = _consolidate_group_chunk(
        client,
        json_client,
        current,
        "final",
    )
    rounds.append({
        "rodada": round_index + 1,
        "entrada": len(current),
        "lotes": 1,
        "saida": len(final_records),
        "grupos": len(final_records),
        "outliers": 0,
        "final": True,
    })
    definitions = []
    used_names = Counter()
    for cluster_id, record in enumerate(final_records):
        name = str(record["nome"]).strip()
        normalized = _norm(name)
        used_names[normalized] += 1
        if used_names[normalized] > 1:
            name = f"{name} ({used_names[normalized]})"
        definitions.append(OrderedDict([
            ("cluster_id", cluster_id),
            ("nome", name[:100]),
            ("descricao", record["descricao"]),
            ("criterio", record["tratamento_esperado"]),
            ("tratamento_esperado", record["tratamento_esperado"]),
            ("criterios_inclusao", record["criterios_inclusao"]),
            ("criterios_exclusao", record["criterios_exclusao"]),
            ("keywords", []),
            ("grupos_locais_origem", record["origens_base"]),
        ]))
    return definitions, [], rounds


def _taxonomy_text(
    definitions: list[dict],
    outliers: list[dict] | None = None,
) -> str:
    public_groups = [OrderedDict([
        ("cluster_id", item["cluster_id"]),
        ("nome", item["nome"]),
        ("descricao", item["descricao"]),
        ("tratamento_esperado", item["tratamento_esperado"]),
        ("criterios_inclusao", item["criterios_inclusao"]),
        ("criterios_exclusao", item["criterios_exclusao"]),
    ]) for item in definitions]
    return json.dumps(
        {"grupos": public_groups},
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _normalize_assignment(
    raw: dict,
    valid_group_ids: set[int],
    valid_outlier_ids: set[str] | None = None,
) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("atribuicao nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("atribuicao sem objeto de resultado")
    destination_type = str(body.get("destino_tipo", "")).strip().lower()
    destination_id = body.get("destino_id")
    if destination_type == "grupo":
        if isinstance(destination_id, bool):
            raise LLMError("destino_id de grupo booleano e invalido")
        try:
            cluster_id = int(destination_id)
        except (TypeError, ValueError) as exc:
            raise LLMError(f"destino_id de grupo invalido: {destination_id}") from exc
        if cluster_id not in valid_group_ids:
            raise LLMError(f"cluster_id inexistente: {cluster_id}")
        outlier_id = None
        status = "grupo_natural"
    elif destination_type == "outlier":
        if valid_outlier_ids:
            outlier_id = str(destination_id or "").strip()
            if outlier_id not in valid_outlier_ids:
                raise LLMError(f"outlier_id inexistente: {outlier_id or '(vazio)'}")
        else:
            if destination_id is not None and str(destination_id).strip() not in {
                "", "null"
            }:
                raise LLMError("destino_id de outlier deve ser null")
            outlier_id = None
        cluster_id = None
        status = "outlier_revisao"
    else:
        raise LLMError(f"destino_tipo invalido: {destination_type or '(vazio)'}")
    confidence = str(body.get("confianca", "")).strip().lower()
    if confidence not in {"alta", "media", "baixa"}:
        raise LLMError(f"confianca invalida ou ausente: {confidence}")
    ambiguity = body.get("ambiguidade")
    if not isinstance(ambiguity, bool):
        raise LLMError("ambiguidade deve ser booleano true ou false")
    justification = str(body.get("justificativa", "")).strip()
    if not justification:
        raise LLMError("justificativa ausente")
    return OrderedDict([
        ("cluster_id", cluster_id),
        ("outlier_id", outlier_id),
        ("status_agrupamento", status),
        ("confianca_cluster", confidence),
        ("ambiguidade_cluster", ambiguity),
        ("justificativa_cluster", justification[:500]),
    ])


def _assignment_hash(item: dict, taxonomy_fingerprint: str) -> str:
    return _hash_json({
        "version": PIPELINE_VERSION,
        "taxonomy_fingerprint": taxonomy_fingerprint,
        "intent": _intent_payload(item),
    })


def _load_assignment_checkpoint(path: Path, expected_hashes: dict[str, str]) -> dict:
    found = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            key = str(row["chave"])
            if row.get("_input_hash") == expected_hashes.get(key):
                found[key] = row
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return found


def _outlier_summary_payload(items: list[dict]) -> list[OrderedDict]:
    return [OrderedDict([
        ("intencao", str(item.get("intencao", "")).strip()),
        ("tema", str(item.get("tema", "")).strip()),
        ("tipo_pedido", str(item.get("tipo_pedido", "")).strip()),
    ]) for item in items]


def _normalize_outlier_summary(raw: dict) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("resumo dos chamados avulsos nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("resumo dos chamados avulsos sem objeto de resultado")
    description = str(body.get("descricao", "")).strip()
    treatment = str(body.get("tratamento_esperado", "")).strip()
    reason = str(body.get("motivo", "")).strip()
    demands = _as_list(body.get("principais_demandas"), 12, 180)
    if not description or not treatment or not reason or not demands:
        raise LLMError(
            "resumo dos chamados avulsos sem descricao, demandas, tratamento ou motivo"
        )
    return OrderedDict([
        ("descricao", description[:700]),
        ("principais_demandas", demands),
        ("tratamento_esperado", treatment[:500]),
        ("motivo", reason[:500]),
    ])


def _summarize_outlier_block(client, items: list[dict]) -> OrderedDict:
    user_base = json.dumps(
        {"intencoes_residuais": _outlier_summary_payload(items)},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    last_error = "resposta nao processada"
    for attempt in range(1, 4):
        user = user_base
        if attempt > 1:
            user += (
                "\n\nA resposta anterior foi invalida: " + last_error
                + "\nRegenere o resumo completo sem IDs ou chaves."
            )
        try:
            return _normalize_outlier_summary(
                client.chat_json(
                    OUTLIER_SUMMARY_SYSTEM,
                    user,
                    max_tokens=1600,
                    timeout=1200,
                )
            )
        except LLMError as exc:
            last_error = str(exc)
    raise LLMError(
        "resumo dos chamados avulsos invalido apos 3 tentativas: " + last_error
    )


def _summarize_final_outliers(
    client,
    residual_items: list[dict],
    taxonomy_fingerprint: str,
) -> list[OrderedDict]:
    if not residual_items:
        return []
    safe_model = _safe_name(client.model_label)
    input_fingerprint = _hash_json({
        "version": PIPELINE_VERSION,
        "taxonomy_fingerprint": taxonomy_fingerprint,
        "system": OUTLIER_SUMMARY_SYSTEM,
        "items": _outlier_summary_payload(residual_items),
    })
    cache = PD / (
        f"_ckpt_stage3_outlier_summary__{safe_model}__"
        f"i{input_fingerprint[:12]}.json"
    )
    if cache.exists():
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            if (
                cached.get("pipeline_version") == PIPELINE_VERSION
                and cached.get("input_fingerprint") == input_fingerprint
            ):
                summary = _normalize_outlier_summary(cached.get("summary"))
                print("[Stage 3c] resumo de Chamados avulsos em cache")
                return [_outlier_bucket_definition(summary)]
        except (OSError, ValueError, json.JSONDecodeError, LLMError):
            pass

    batch_size = max(
        20, int(os.getenv("STAGE3_OUTLIER_SUMMARY_BATCH_SIZE", "200"))
    )
    batches = _build_batches(residual_items, batch_size, 9107)
    partials = []
    for index, batch in enumerate(batches, start=1):
        partials.append(_summarize_outlier_block(client, batch))
        print(
            f"[Stage 3c] resumo de avulsos {index}/{len(batches)} concluido"
        )
    if len(partials) == 1:
        summary = partials[0]
    else:
        synthetic = [
            {
                "chave": f"resumo-{index}",
                "intencao": item["descricao"],
                "tema": "; ".join(item["principais_demandas"]),
                "tipo_pedido": item["tratamento_esperado"],
            }
            for index, item in enumerate(partials, start=1)
        ]
        summary = _summarize_outlier_block(client, synthetic)
    cache.write_text(json.dumps({
        "pipeline_version": PIPELINE_VERSION,
        "input_fingerprint": input_fingerprint,
        "summary": summary,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    return [_outlier_bucket_definition(summary)]


def _outlier_bucket_definition(summary: dict) -> OrderedDict:
    return OrderedDict([
        ("outlier_id", OUTLIER_BUCKET_ID),
        ("nome", "Chamados avulsos"),
        ("descricao", summary["descricao"]),
        ("principais_demandas", summary["principais_demandas"]),
        ("tratamento_esperado", summary["tratamento_esperado"]),
        ("motivo", summary["motivo"]),
        ("tipo_registro", "agrupador_tecnico_residual"),
        ("publicavel_no_portfolio", False),
        ("grupos_locais_origem", []),
    ])


def _assign_all(
    client,
    summaries: list[dict],
    definitions: list[dict],
    outlier_definitions: list[dict],
    taxonomy_fingerprint: str,
) -> tuple[list[dict], dict, list[dict]]:
    safe_model = _safe_name(client.model_label)
    checkpoint = PD / (
        f"_ckpt_stage3_assign__{safe_model}__t{taxonomy_fingerprint[:12]}.jsonl"
    )
    input_hashes = {
        str(item["chave"]): _assignment_hash(item, taxonomy_fingerprint)
        for item in summaries
    }
    found = _load_assignment_checkpoint(checkpoint, input_hashes)
    pending = [item for item in summaries if str(item["chave"]) not in found]
    workers = max(1, int(os.getenv("PIPELINE_WORKERS", "2")))
    system = ASSIGN_SYSTEM.replace(
        "{groups}", _taxonomy_text(definitions, outlier_definitions)
    )
    valid_group_ids = {int(item["cluster_id"]) for item in definitions}
    valid_outlier_ids = set()
    print(
        f"[Stage 3c/{client.model_label}] total={len(summaries)} "
        f"feitos={len(found)} pendentes={len(pending)} workers={workers}"
    )
    print(f"[Stage 3c] checkpoint: {checkpoint.name}")
    counters = {"ok": 0, "erro": 0, "retries_semanticos": 0}
    lock = threading.Lock()
    handle = open(checkpoint, "a", encoding="utf-8")

    def process(item: dict) -> bool:
        last_error = ""
        user_base = json.dumps(_intent_payload(item), ensure_ascii=False)
        for attempt in range(1, 4):
            user = user_base
            if attempt > 1:
                user += (
                    "\n\nA resposta anterior foi invalida: " + last_error
                    + "\nUse somente um destino existente e complete todos os campos."
                )
            try:
                raw = client.chat_json(system, user, max_tokens=420, timeout=900)
                normalized = _normalize_assignment(
                    raw, valid_group_ids, valid_outlier_ids
                )
                record = {
                    "chave": str(item["chave"]),
                    **normalized,
                    "_input_hash": input_hashes[str(item["chave"])],
                }
                with lock:
                    handle.write(
                        json.dumps(record, ensure_ascii=False, separators=(",", ":"))
                        + "\n"
                    )
                    handle.flush()
                    counters["ok"] += 1
                    counters["retries_semanticos"] += attempt - 1
                    if (counters["ok"] + counters["erro"]) % 100 == 0:
                        print(f"   ... {counters['ok']} atribuidos, {counters['erro']} erros")
                return True
            except LLMError as exc:
                last_error = str(exc)
        with lock:
            counters["erro"] += 1
        print(
            f"   [ERRO] {item['chave']}: atribuicao invalida apos 3 tentativas: "
            f"{last_error}"
        )
        return False

    if pending:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, item) for item in pending]
            for _ in as_completed(futures):
                pass
    handle.close()

    found = _load_assignment_checkpoint(checkpoint, input_hashes)
    missing = [str(item["chave"]) for item in summaries if str(item["chave"]) not in found]
    if missing:
        print(f"[Stage 3c] faltam {len(missing)} atribuicoes. Ex.: {missing[:5]}")
        raise LLMError("atribuicoes incompletas; reexecute para retomar")
    output = []
    residual_items = []
    for item in summaries:
        row = dict(found[str(item["chave"])])
        if row.get("cluster_id") is None:
            row["outlier_id"] = OUTLIER_BUCKET_ID
            residual_items.append(item)
        output.append(row)
    final_outlier_definitions = _summarize_final_outliers(
        client,
        residual_items,
        taxonomy_fingerprint,
    )
    counters["total"] = len(output)
    counters["ambiguos"] = sum(bool(row.get("ambiguidade_cluster")) for row in output)
    counters["confianca"] = dict(Counter(row.get("confianca_cluster") for row in output))
    counters["outliers"] = sum(row.get("outlier_id") is not None for row in output)
    return output, counters, final_outlier_definitions


def _build_output(
    summaries: list[dict],
    assignments: list[dict],
    definitions: list[dict],
    outlier_definitions: list[dict],
    metadata: dict,
) -> OrderedDict:
    assignment_by_key = {row["chave"]: row for row in assignments}
    tickets = []
    grouped = defaultdict(list)
    grouped_outliers = defaultdict(list)
    for item in summaries:
        key = str(item["chave"])
        assignment = assignment_by_key[key]
        ticket = OrderedDict([
            ("chave", key),
            ("intencao", item.get("intencao", "")),
            ("tema", item.get("tema", "")),
            ("tipo_pedido", item.get("tipo_pedido", "")),
            ("contexto", item.get("contexto", "")),
            ("tipo_atual", item.get("tipo_atual", "")),
            ("cluster_id", int(assignment["cluster_id"]) if assignment["cluster_id"] is not None else None),
            ("outlier_id", assignment.get("outlier_id")),
            ("status_agrupamento", assignment.get("status_agrupamento")),
            ("confianca_cluster", assignment.get("confianca_cluster")),
            ("ambiguidade_cluster", assignment.get("ambiguidade_cluster")),
            ("justificativa_cluster", assignment.get("justificativa_cluster", "")),
        ])
        tickets.append(ticket)
        if ticket["cluster_id"] is not None:
            grouped[int(ticket["cluster_id"])].append(ticket)
        else:
            grouped_outliers[str(ticket["outlier_id"])].append(ticket)

    definition_by_id = {int(item["cluster_id"]): item for item in definitions}
    stats = []
    for cluster_id in range(len(definitions)):
        group = grouped[cluster_id]
        confidence_order = {"alta": 0, "media": 1, "baixa": 2}
        ranked = sorted(group, key=lambda item: (
            bool(item.get("ambiguidade_cluster")),
            confidence_order.get(item.get("confianca_cluster"), 3),
            item["chave"],
        ))
        samples = []
        seen = set()
        for item in ranked:
            intent = str(item.get("intencao", "")).strip()
            normalized = _norm(intent)
            if intent and normalized not in seen:
                seen.add(normalized)
                samples.append(intent)
            if len(samples) >= 12:
                break
        themes = [
            value for value, _ in Counter(
                str(item.get("tema", "")).strip() for item in group
            ).most_common(12) if value
        ]
        definition_by_id[cluster_id]["keywords"] = themes
        stats.append(OrderedDict([
            ("cluster_id", cluster_id),
            ("total", len(group)),
            ("keywords", themes),
            ("sample_intencoes", samples),
            ("distribuicao_categorias_atuais", dict(Counter(
                item.get("tipo_atual", "") for item in group
            ).most_common())),
            ("distribuicao_tipos_pedido", dict(Counter(
                item.get("tipo_pedido", "") for item in group
            ).most_common())),
            ("distribuicao_confianca", dict(Counter(
                item.get("confianca_cluster", "") for item in group
            ).most_common())),
            ("ambiguos", sum(bool(item.get("ambiguidade_cluster")) for item in group)),
        ]))

    outlier_stats = []
    total_tickets = len(tickets)
    for definition in outlier_definitions:
        outlier_id = str(definition["outlier_id"])
        group = grouped_outliers[outlier_id]
        if not group:
            continue
        samples = []
        seen = set()
        for item in sorted(group, key=lambda row: row["chave"]):
            intent = str(item.get("intencao", "")).strip()
            normalized = _norm(intent)
            if intent and normalized not in seen:
                seen.add(normalized)
                samples.append(intent)
            if len(samples) >= 12:
                break
        themes = [
            value for value, _ in Counter(
                str(item.get("tema", "")).strip() for item in group
            ).most_common(12) if value
        ]
        outlier_stats.append(OrderedDict([
            ("outlier_id", outlier_id),
            ("nome", definition["nome"]),
            ("descricao", definition["descricao"]),
            ("principais_demandas", definition.get("principais_demandas", [])),
            ("tratamento_esperado", definition["tratamento_esperado"]),
            ("motivo", definition["motivo"]),
            ("tipo_registro", definition.get("tipo_registro")),
            (
                "publicavel_no_portfolio",
                bool(definition.get("publicavel_no_portfolio", False)),
            ),
            ("total", len(group)),
            ("percentual", round(len(group) / max(total_tickets, 1) * 100, 2)),
            ("keywords", themes),
            ("sample_intencoes", samples),
            ("distribuicao_tipos_pedido", dict(Counter(
                item.get("tipo_pedido", "") for item in group
            ).most_common())),
            ("distribuicao_confianca", dict(Counter(
                item.get("confianca_cluster", "") for item in group
            ).most_common())),
            ("ambiguos", sum(bool(item.get("ambiguidade_cluster")) for item in group)),
        ]))

    return OrderedDict([
        ("optimal_k", len(definitions)),
        (
            "metodo",
            "LLM hierarquica: lotes, reagrupamento iterativo de avulsos, "
            "taxonomia sem IDs de origem e atribuicao unitaria fechada",
        ),
        ("metadata", metadata),
        ("cluster_stats", stats),
        ("outlier_stats", outlier_stats),
        ("tickets", tickets),
        ("_definicoes", definitions),
        ("_definicoes_outliers", outlier_definitions),
    ])


def main():
    summaries_path = PD / "02_summaries.json"
    if not summaries_path.exists():
        raise SystemExit(f"ERRO: arquivo nao encontrado: {summaries_path}")
    with open(summaries_path, "r", encoding="utf-8-sig") as handle:
        summaries = json.load(handle)
    if not isinstance(summaries, list) or not summaries:
        raise SystemExit("ERRO: 02_summaries.json vazio ou invalido.")
    original_keys = [str(item.get("chave", "")).strip() for item in summaries]
    if (
        any(not key for key in original_keys)
        or len(set(original_keys)) != len(original_keys)
    ):
        raise SystemExit("ERRO: Stage 2 contem chaves vazias ou duplicadas.")
    try:
        summaries, original_by_opaque = _opaque_working_summaries(summaries)
    except ValueError as exc:
        raise SystemExit(f"ERRO: {exc}") from exc

    seed = int(os.getenv("STAGE3_RANDOM_SEED", "42"))
    batch_size = max(40, int(os.getenv("STAGE3_DISCOVERY_BATCH_SIZE", "200")))
    char_budget = max(8000, int(os.getenv("STAGE3_MERGE_CHAR_BUDGET", "12000")))
    source_fingerprint = _source_fingerprint(summaries)
    rediscovery_source_fingerprint = _source_fingerprint(
        summaries,
        REDISCOVERY_VERSION,
    )
    batches = _build_batches(summaries, batch_size, seed)
    if "--estimate-context" in sys.argv[1:]:
        sizes = [
            len(LOCAL_SYSTEM) + len(_discovery_user(batch, index))
            for index, batch in enumerate(batches, start=1)
        ]
        max_chars = max(sizes)
        optimistic = round(max_chars / 4)
        conservative = round(max_chars / 3)
        output_reserve = 7000
        configured = int(os.getenv("OLLAMA_CONTEXT_LENGTH", "32768"))
        print(f"Chamados: {len(summaries)}")
        print(f"Lotes: {len(batches)}")
        print(f"Maior lote: {max(len(batch) for batch in batches)} chamados")
        print(f"Maior prompt: {max_chars} caracteres")
        print(f"Entrada estimada: {optimistic} a {conservative} tokens")
        print(f"Reserva maxima de saida: {output_reserve} tokens")
        print(f"Contexto configurado: {configured} tokens")
        print(
            "Margem conservadora: "
            f"{configured - conservative - output_reserve} tokens"
        )
        return
    expected_hashes = {
        index: _batch_hash(batch) for index, batch in enumerate(batches, start=1)
    }
    client = get_client()
    json_client = _get_json_client(client)
    safe_model = _safe_name(client.model_label)
    discovery_checkpoint = PD / f"_ckpt_stage3_discovery__{safe_model}.jsonl"
    discoveries = _load_discovery_checkpoint(
        discovery_checkpoint, expected_hashes, client.model_label
    )
    pending = [
        (index, batch)
        for index, batch in enumerate(batches, start=1)
        if index not in discoveries
    ]
    workers = max(1, int(os.getenv("PIPELINE_WORKERS", "2")))
    print(
        f"[Stage 3a/{client.model_label}] chamados={len(summaries)} "
        f"lotes={len(batches)} feitos={len(discoveries)} pendentes={len(pending)} "
        f"tamanho_lote={batch_size} workers={workers}"
    )
    errors = []
    if pending:
        with open(discovery_checkpoint, "a", encoding="utf-8") as checkpoint:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                futures = {
                    executor.submit(_discover_batch, client, batch, index): (index, batch)
                    for index, batch in pending
                }
                for future in as_completed(futures):
                    index, _ = futures[future]
                    try:
                        result = future.result()
                    except LLMError as exc:
                        errors.append(f"lote {index}: {exc}")
                        print(f"[Stage 3a] ERRO lote {index}: {exc}")
                        continue
                    discoveries[index] = result
                    row = {
                        "pipeline_version": DISCOVERY_VERSION,
                        "model": client.model_label,
                        "batch_index": index,
                        "batch_hash": expected_hashes[index],
                        "result": result,
                    }
                    checkpoint.write(
                        json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
                    )
                    checkpoint.flush()
                    print(
                        f"   lote {index}/{len(batches)}: "
                        f"{len(result['grupos'])} grupos locais, "
                        f"{len(result['avulsos'])} avulsos"
                    )
    if errors or len(discoveries) != len(batches):
        print("[Stage 3a] descoberta incompleta; reexecute para retomar os lotes pendentes.")
        raise SystemExit(2)

    local_audit = _build_local_audit(discoveries, batches)
    with open(PD / "_stage3_grupos_lotes.json", "w", encoding="utf-8") as handle:
        json.dump(local_audit, handle, ensure_ascii=False, indent=2)

    local_records = _make_local_records(discoveries, batches)
    local_groups = [
        record for record in local_records
        if record.get("tipo_unidade") == "grupo_local"
    ]
    initial_outlier_items = _initial_outlier_items(discoveries, batches)
    local_group_count = len(local_groups)
    local_outlier_count = len(initial_outlier_items)
    try:
        rediscovered_groups, residual_items, outlier_rounds = _rediscover_outliers(
            client,
            initial_outlier_items,
            batch_size,
            seed,
            rediscovery_source_fingerprint,
        )
    except LLMError as exc:
        print(f"[Stage 3b.1] ERRO: {exc}")
        raise SystemExit(2) from exc
    outlier_audit = OrderedDict([
        ("pipeline_version", PIPELINE_VERSION),
        ("rediscovery_version", REDISCOVERY_VERSION),
        ("initial_outliers", local_outlier_count),
        ("rounds", outlier_rounds),
        ("rediscovered_groups", rediscovered_groups),
        ("residual_count", len(residual_items)),
        ("residual_keys", [str(item["chave"]) for item in residual_items]),
    ])
    with open(
        PD / "_stage3_reagrupamento_avulsos.json", "w", encoding="utf-8"
    ) as handle:
        json.dump(outlier_audit, handle, ensure_ascii=False, indent=2)

    group_pool = local_groups + rediscovered_groups
    local_fingerprint = _hash_json({
        "groups": group_pool,
        "residual_keys": [str(item["chave"]) for item in residual_items],
    })
    merge_max_records = _merge_max_records()
    taxonomy_input_fingerprint = _hash_json({
        "local_fingerprint": local_fingerprint,
        "global_decision_system": GLOBAL_DECISION_SYSTEM,
        "global_json_system": GLOBAL_JSON_SYSTEM,
        "global_assign_system": GLOBAL_ASSIGN_SYSTEM,
        "merge_model": client.model_label,
        "merge_json_model": json_client.model_label,
        "merge_char_budget": char_budget,
        "merge_max_records": merge_max_records,
        "global_char_budget": int(os.getenv("STAGE3_GLOBAL_CHAR_BUDGET", "60000")),
        "global_max_records": int(os.getenv("STAGE3_GLOBAL_MAX_RECORDS", "160")),
        "ownership_policy": "one_unit_per_call",
        "initial_outliers": local_outlier_count,
        "rediscovered_groups": len(rediscovered_groups),
        "residual_outliers": len(residual_items),
        "group_count_policy": "semantic_no_numeric_limit",
    })
    taxonomy_cache = PD / (
        f"_ckpt_stage3_taxonomy__{safe_model}__i{taxonomy_input_fingerprint[:12]}.json"
    )
    definitions = None
    outlier_definitions = None
    consolidation_rounds = []
    if taxonomy_cache.exists():
        try:
            cached = json.loads(taxonomy_cache.read_text(encoding="utf-8"))
            if (
                cached.get("pipeline_version") == PIPELINE_VERSION
                and cached.get("model") == client.model_label
                and cached.get("json_model", client.model_label) == json_client.model_label
                and cached.get("source_fingerprint") == source_fingerprint
                and cached.get("local_fingerprint") == local_fingerprint
                and cached.get("taxonomy_input_fingerprint")
                == taxonomy_input_fingerprint
                and isinstance(cached.get("definitions"), list)
                and isinstance(cached.get("outlier_definitions"), list)
            ):
                definitions = cached["definitions"]
                outlier_definitions = cached["outlier_definitions"]
                consolidation_rounds = cached.get("consolidation_rounds", [])
                print(
                    f"[Stage 3b.2] taxonomia em cache: "
                    f"{len(definitions)} grupos"
                )
        except (OSError, ValueError, json.JSONDecodeError):
            definitions = None
            outlier_definitions = None
    if definitions is None:
        print(
            f"[Stage 3b.2/{client.model_label}] consolidando {len(group_pool)} "
            f"grupos descobertos (orcamento_intermediario={char_budget}, "
            f"json={json_client.model_label})"
        )
        try:
            definitions, outlier_definitions, consolidation_rounds = _consolidate_taxonomy(
                client,
                json_client,
                group_pool,
                char_budget,
            )
        except LLMError as exc:
            print(f"[Stage 3b.2] ERRO: {exc}")
            raise SystemExit(2) from exc
        cache_payload = {
            "pipeline_version": PIPELINE_VERSION,
            "model": client.model_label,
            "json_model": json_client.model_label,
            "source_fingerprint": source_fingerprint,
            "local_fingerprint": local_fingerprint,
            "taxonomy_input_fingerprint": taxonomy_input_fingerprint,
            "consolidation_rounds": consolidation_rounds,
            "definitions": definitions,
            "outlier_definitions": outlier_definitions,
        }
        taxonomy_cache.write_text(
            json.dumps(cache_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(
            f"[Stage 3b.2] taxonomia global: {len(definitions)} grupos"
        )

    taxonomy_fingerprint = _hash_json({"grupos": definitions})
    try:
        assignments, assignment_report, outlier_definitions = _assign_all(
            client,
            summaries,
            definitions,
            [],
            taxonomy_fingerprint,
        )
    except LLMError as exc:
        print(f"[Stage 3c] ERRO: {exc}")
        print("[Stage 3] 03_clusters.json NAO foi gravado.")
        raise SystemExit(2) from exc

    clustering_fingerprint = _hash_json({
        "taxonomy_fingerprint": taxonomy_fingerprint,
        "assignments": [
            (row["chave"], row["cluster_id"], row.get("outlier_id"))
            for row in assignments
        ],
    })
    metadata = OrderedDict([
        ("pipeline_version", PIPELINE_VERSION),
        ("discovery_model", client.model_label),
        ("json_model", json_client.model_label),
        ("discovery_contract_version", DISCOVERY_CONTRACT_VERSION),
        ("discovery_fields", list(DISCOVERY_FIELDS)),
        ("roundtrip_identifier_policy", ROUNDTRIP_IDENTIFIER_POLICY),
        ("jira_key_exposed_to_llm", False),
        ("source_fingerprint", source_fingerprint),
        ("local_fingerprint", local_fingerprint),
        ("taxonomy_input_fingerprint", taxonomy_input_fingerprint),
        ("taxonomy_fingerprint", taxonomy_fingerprint),
        ("clustering_fingerprint", clustering_fingerprint),
        ("random_seed", seed),
        ("discovery_batch_size", batch_size),
        ("discovery_batches", len(batches)),
        ("merge_char_budget", char_budget),
        ("merge_max_records", merge_max_records),
        ("local_groups", local_group_count),
        ("local_outliers", local_outlier_count),
        ("outlier_rediscovery_rounds", outlier_rounds),
        ("rediscovered_groups", len(rediscovered_groups)),
        ("residual_outliers_before_final_assignment", len(residual_items)),
        ("consolidation_rounds", consolidation_rounds),
        ("global_groups", len(definitions)),
        ("global_outlier_candidates", len(outlier_definitions)),
        ("final_outlier_tickets", assignment_report["outliers"]),
        ("assignment_report", assignment_report),
    ])
    output = _build_output(
        summaries,
        assignments,
        definitions,
        outlier_definitions,
        metadata,
    )
    for ticket in output["tickets"]:
        opaque = str(ticket["chave"])
        if opaque not in original_by_opaque:
            raise SystemExit(
                "ERRO: Stage 3 produziu identificador tecnico desconhecido."
            )
        ticket["chave"] = original_by_opaque[opaque]
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
    with open(PD / "_stage3_discovery_report.json", "w", encoding="utf-8") as handle:
        json.dump(metadata, handle, ensure_ascii=False, indent=2)
    print(
        f"[Stage 3] OK: 03_clusters.json (k={len(definitions)}, "
        f"{len(summaries)} chamados, outliers={assignment_report['outliers']}, "
        f"ambiguos={assignment_report['ambiguos']})"
    )


if __name__ == "__main__":
    main()
