#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 5 estrito: compara demanda natural e catalogo atual para recomendar o
portfolio. Normaliza formato, mas nunca inventa mapeamentos semanticos.

Uso: python scripts/run_stage5_llm.py [--force]
"""
import argparse
import hashlib
import json
import os
import re
import sys
import threading
import unicodedata
from collections import Counter, defaultdict, OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from projeto import config_path, contexto_catalogo_path, pipeline_data_dir, load_projeto_meta
from llm_client import LLMClient, LLMError, get_client

PD = pipeline_data_dir()
OUT = PD / "05_portfolio_recommendation.json"
PIPELINE_VERSION = "stage5-operational-reconciliation-v6.1"
RECONCILIATION_COMPILER_VERSION = "json-per-block-v1"
CATEGORY_MAPPING_VERSION = "closed-destination-stage4-evidence-v3"
ADERENCIAS = {"boa", "parcial", "baixa", "sem_correspondencia"}
COMPLEXIDADES = {"baixa", "media", "alta"}
PRAZOS = {"imediato", "curto_prazo", "medio_prazo"}
PRIORIDADES = {"alta", "media", "baixa"}
PROBLEMAS = {"sobreposicao", "lacuna", "fragmentacao", "nomenclatura", "volume_desproporcional"}
DECISOES_RECONCILIACAO = {
    "manter_separado",
    "fundir",
    "dividir_para_revisao",
}
CRITERIOS_RECONCILIACAO = (
    "mesmo_objetivo_usuario",
    "mesmo_servico_sistema",
    "mesmo_tratamento",
    "mesmo_fluxo_responsavel",
    "mesmos_dados_aprovacoes",
    "mesmos_sla_seguranca",
)
DECISOES_AUDITORIA_FUSAO = {"aprovar_fusao", "rejeitar_fusao"}
DECISOES_OUTLIER = {
    "incorporar_portfolio",
    "fundir_em_chamado",
    "manter_revisao",
    "desconsiderar_portfolio",
}

BASE_DECISION_SYSTEM = """Voce e consultor senior de ITSM. Desenhe somente a
estrutura-base do portfolio de servicos. Considere os grupos naturais, o
catalogo atual e as categorias obrigatorias, mas nao tente mapear todas as
categorias atuais nem avaliar candidatos raros nesta chamada.

Nao escreva JSON. Use somente o formato canonico abaixo:

[ANALISE]
RESUMO: sintese executiva curta
PRINCIPIO_REVISAO: criterio usado ao comparar demanda e catalogo
AGRUPADORES_ATUAIS: grupo atual 1 | grupo atual 2
DECISAO_REVISAO: decisao relevante sobre agrupamento
AJUSTE_REVISAO: ajuste recomendado
PROBLEMA: tipo | severidade | descricao
ACAO: acao | impacto | prazo
IMPACTO_REDUCAO: efeito esperado no vaivem
IMPACTO_TEMPO: efeito esperado no tempo de resolucao
IMPACTO_JUSTIFICATIVA: justificativa do impacto
[/ANALISE]

[CHAMADO]
NOME: nome orientado ao usuario
GRUPO: agrupador logico
DESCRICAO: o que o chamado atende
INFORMACOES: campo 1 | campo 2
SLA: prazo sugerido
COMPLEXIDADE: baixa|media|alta
PRIORIDADE: alta|media|baixa
[/CHAMADO]

Repita [CHAMADO] para cada request type proposto.

Regras:
- nao imponha quantidade minima, maxima ou meta de reducao;
- trate os agrupadores atuais do catalogo como referencia forte; em geral, a
  proposta nao deve criar mais grupos logicos do que o catalogo atual;
- diferencas entre servicos, sistemas ou fluxos devem virar chamados/request
  types distintos, mas podem compartilhar o mesmo grupo logico quando um
  formulario inteligente conseguir diferenciar alvo, perfil, ambiente,
  aprovacao ou demais informacoes necessarias;
- crie grupo logico novo somente quando nenhum agrupador atual representar bem
  uma familia operacional relevante; justifique esse caso em DECISAO_REVISAO;
- os blocos CHAMADO desta etapa sao apenas um rascunho analitico de direcoes;
  candidatos naturais e reconciliacao operacional serao executados
  separadamente, portanto nao afirme uma contagem final;
- cada chamado deve ter nome e grupo unicos e significado operacional claro;
- servicos ou sistemas independentes devem permanecer como chamados distintos;
- chamados de acesso a sistemas diferentes so podem ser fundidos quando os
  sistemas pertencem ao mesmo servico e compartilham equipe, autorizacao,
  formulario, informacoes obrigatorias e fluxo completo;
- chamados distintos podem compartilhar o mesmo GRUPO logico de apresentacao;
- preserve exatamente os nomes das categorias obrigatorias quando existirem;
- nao crie chamados genericos de diversos, outros ou nao categorizado;
- nao escreva listas de categorias atuais ou IDs de outliers nos chamados;
- nao escreva nada fora dos blocos;
- nao use travessao nos textos."""


BASE_JSON_SYSTEM = """Voce e compilador JSON estrito. Converta o plano
canonico recebido em JSON sem redesenhar o portfolio.

Responda SOMENTE JSON no formato:
{
  "recomendacao_base": {
    "analise_geral": "texto",
    "problemas_encontrados": [
      {"tipo": "lacuna", "severidade": "media", "descricao": "texto", "categorias_envolvidas": []}
    ],
    "revisao_contexto_catalogo": {
      "contexto_lido": true,
      "principio": "texto",
      "agrupadores_atuais_considerados": ["grupo atual"],
      "decisoes_de_agrupamento": ["decisao"],
      "ajustes_pos_revisao": ["ajuste"]
    },
    "portfolio_otimizado": [
      {
        "nome": "Solicitar Acesso",
        "grupo": "Identidade e Acesso",
        "descricao": "Conceder ou alterar acesso autorizado.",
        "substitui_categorias_atuais": [],
        "baseado_nos_grupos": [],
        "baseado_nos_outliers": [],
        "informacoes_obrigatorias": ["usuario", "perfil"],
        "sla_sugerido": "2 dias uteis",
        "complexidade": "media",
        "prioridade_implementacao": "alta"
      }
    ],
    "acoes_prioritarias": [
      {"acao": "texto", "impacto": "texto", "prazo": "curto_prazo"}
    ],
    "impacto_estimado": {
      "reducao_vaievem": "texto",
      "melhoria_tempo_resolucao": "texto",
      "justificativa": "texto"
    }
  }
}

Regras:
- copie nomes, grupos e significados do plano canonico;
- mantenha vazias as tres listas de linhagem de cada chamado;
- use somente enums mostrados no schema;
- preserve exatamente categorias obrigatorias citadas no plano;
- nao invente chamados ausentes no plano;
- nao use travessao nos textos."""


CATEGORY_MAPPING_SYSTEM = """Mapeie UMA categoria atual para exatamente um
category_id do portfolio fechado. Escolha pelo tratamento dominante observado,
nao apenas pelo nome. Os grupos naturais observados sao evidencias de apoio:
nao escolha, copie ou devolva seus nomes, pois o Python preserva essa relacao.

Responda SOMENTE JSON:
{
  "destino_id": "category_id exato",
  "aderencia": "boa|parcial|baixa|sem_correspondencia",
  "observacao": "justificativa curta"
}

Nao invente IDs, nao acrescente campos e nao use travessao."""


NATURAL_REQUEST_SYSTEM = """Transforme UM grupo natural ja validado em UM
request type orientado ao usuario. Nao funda este grupo com outro e nao
descarte seu significado. Escolha um agrupador logico de apresentacao entre os
grupos atuais quando houver aderencia; crie um agrupador logico novo somente
quando realmente necessario. A diferenca fina entre sistemas, ambientes,
perfis ou fluxos deve ficar no request type, na descricao e nas informacoes de
um formulario inteligente, nao necessariamente em um novo grupo logico.

Responda SOMENTE JSON:
{
  "nome": "nome exato do grupo natural recebido",
  "grupo": "agrupador logico",
  "descricao": "o que este chamado atende",
  "informacoes_obrigatorias": ["campo necessario"],
  "sla_sugerido": "prazo sugerido",
  "complexidade": "baixa|media|alta",
  "prioridade_implementacao": "alta|media|baixa",
  "perfil_operacional": {
    "objetivo_usuario": "resultado buscado pelo solicitante",
    "servico_sistema_alvo": "servico, sistema ou objeto atendido",
    "acao_tratamento": "acao executada pela equipe",
    "fluxo_responsavel": "fluxo e equipe responsavel, ou nao_informado",
    "dados_aprovacoes": "dados, formulario e aprovacoes, ou nao_informado",
    "requisitos_seguranca": "restricoes relevantes, ou nao_informado"
  }
}

Regras:
- gere exatamente um request type;
- preserve o nome exato informado em nome_obrigatorio;
- prefira agrupadores atuais e evite aumentar a quantidade total de grupos
  logicos do catalogo;
- nao use agrupador de atalhos ou acesso rapido;
- nao crie categoria generica de diversos, outros ou nao categorizado;
- sistemas e tratamentos independentes permanecem distintos;
- nao use travessao nos textos."""


RECONCILIATION_DECISION_SYSTEM = """Voce e arquiteto senior de catalogo de
servicos. Reconcile candidatos de request type descobertos pela demanda com o
catalogo existente e o contexto real da area.

Nao escreva JSON e nao liste IDs ou grupos naturais de origem. Produza somente
blocos canonicos completos:

[CHAMADO_FINAL]
NOME: nome orientado ao usuario
GRUPO: agrupador logico
DESCRICAO: escopo preciso do chamado
OBJETIVO_USUARIO: resultado buscado pelo solicitante
SERVICO_SISTEMA_ALVO: servico, sistema ou objeto atendido
ACAO_TRATAMENTO: acao executada pela equipe
FLUXO_RESPONSAVEL: fluxo e equipe responsavel, ou nao_informado
DADOS_APROVACOES: dados, formulario e aprovacoes, ou nao_informado
REQUISITOS_SEGURANCA: restricoes relevantes, ou nao_informado
INFORMACOES: campo 1 | campo 2
SLA: prazo sugerido
COMPLEXIDADE: baixa|media|alta
PRIORIDADE: alta|media|baixa
[/CHAMADO_FINAL]

Regras:
- nao existe quantidade minima, maxima ou meta de reducao;
- os agrupadores atuais do catalogo sao a referencia principal para grupos
  logicos finais; em geral, nao aumente a quantidade de grupos logicos;
- servicos, sistemas ou fluxos diferentes devem permanecer como request types
  distintos, mas podem compartilhar um mesmo grupo logico amplo quando isso
  melhorar a navegacao do usuario e o formulario puder diferenciar o caso;
- crie grupo logico novo apenas quando os agrupadores atuais nao comportarem uma
  familia operacional importante; explique essa decisao no bloco;
- mantenha separados candidatos com diferenca relevante de objetivo, servico
  ou sistema, acao, equipe, fluxo, autorizacao, formulario, dados obrigatorios,
  SLA ou seguranca;
- somente proponha um destino comum quando todo o tratamento operacional for
  compativel e o usuario puder escolher o mesmo formulario sem ambiguidade;
- acesso ao Sistema X e acesso ao Sistema Y permanecem separados quando os
  servicos ou fluxos forem independentes;
- incidente, solicitacao, consulta, criacao, alteracao, exclusao, backup e
  restauracao nao sao equivalentes apenas por tratarem o mesmo objeto;
- o catalogo atual e evidencia operacional, nao uma verdade a ser copiada;
- candidatos internamente mistos nao devem ser escondidos em um destino
  generico: a atribuicao posterior podera marca-los para divisao e revisao;
- nao crie chamados de outros, diversos, consulta generica ou resolucao
  generica de incidentes para absorver lacunas;
- preserve exatamente o nome de toda categoria obrigatoria;
- os blocos definem somente destinos possiveis. O pertencimento de cada grupo
  natural sera decidido depois, uma unidade por chamada;
- nao escreva nada fora dos blocos e nao use travessao nos textos."""


RECONCILIATION_JSON_SYSTEM = """Voce e compilador JSON estrito. Converta o
UNICO bloco CHAMADO_FINAL recebido em JSON sem fundir, dividir, renomear ou
criar blocos.

Responda SOMENTE JSON:
{
  "portfolio_reconciliado": [
    {
      "nome": "nome exato",
      "grupo": "grupo exato",
      "descricao": "descricao exata",
      "informacoes_obrigatorias": ["campo 1"],
      "sla_sugerido": "prazo",
      "complexidade": "baixa|media|alta",
      "prioridade_implementacao": "alta|media|baixa",
      "perfil_operacional": {
        "objetivo_usuario": "texto",
        "servico_sistema_alvo": "texto",
        "acao_tratamento": "texto",
        "fluxo_responsavel": "texto",
        "dados_aprovacoes": "texto",
        "requisitos_seguranca": "texto"
      }
    }
  ]
}

Mantenha exatamente um objeto para o unico bloco recebido. Nao inclua linhagem,
IDs de origem ou campos extras. Nao use travessao nos textos."""


RECONCILIATION_ASSIGN_SYSTEM = """Avalie UM candidato natural contra o
portfolio reconciliado fechado. A decisao deve considerar conjuntamente
objetivo do usuario, servico ou sistema, acao e tratamento, fluxo e equipe,
formulario, dados, aprovacoes, SLA e seguranca.

Responda SOMENTE JSON:
{
  "decisao": "manter_separado|fundir|dividir_para_revisao",
  "destino_id": "category_id exato ou null",
  "criterios": {
    "mesmo_objetivo_usuario": true,
    "mesmo_servico_sistema": true,
    "mesmo_tratamento": true,
    "mesmo_fluxo_responsavel": true,
    "mesmos_dados_aprovacoes": true,
    "mesmos_sla_seguranca": true
  },
  "justificativa": "motivo operacional objetivo"
}

Use manter_separado quando houver um destino proprio e distinto para o
candidato. Use fundir somente quando um destino puder atender este candidato e
outros equivalentes sem perder diferencas operacionais. Nessas duas decisoes,
todos os criterios devem ser true e destino_id deve existir.

Use dividir_para_revisao quando o candidato misturar objetivos, servicos,
sistemas ou fluxos independentes, ou quando nenhum destino for integralmente
compativel. Nesse caso destino_id deve ser null. Nunca escolha o destino mais
proximo e nunca invente IDs."""


MERGE_AUDIT_SYSTEM = """Audite UMA fusao proposta entre grupos naturais.
Compare conjuntamente todos os candidatos e o request type de destino. A fusao
so pode ser aprovada se todos os candidatos forem mutuamente compativeis em
objetivo do usuario, servico ou sistema, acao e tratamento, fluxo e equipe,
formulario, dados, aprovacoes, SLA e seguranca.

Responda SOMENTE JSON:
{
  "decisao": "aprovar_fusao|rejeitar_fusao",
  "criterios": {
    "mesmo_objetivo_usuario": true,
    "mesmo_servico_sistema": true,
    "mesmo_tratamento": true,
    "mesmo_fluxo_responsavel": true,
    "mesmos_dados_aprovacoes": true,
    "mesmos_sla_seguranca": true
  },
  "justificativa": "motivo operacional objetivo"
}

Qualquer criterio false exige rejeitar_fusao. Sistemas independentes,
incidentes e solicitacoes, ou formularios e aprovacoes
diferentes nao podem ser fundidos apenas por proximidade tematica. Nao proponha
outro destino e nao liste IDs."""


OUTLIER_MAPPING_SYSTEM = """Avalie UM candidato raro contra um portfolio
fechado. Escolha uma decisao valida. Somente incorporar_portfolio e
fundir_em_chamado recebem destino_id. Se nao houver chamado coerente, use
manter_revisao ou desconsiderar_portfolio sem destino.

Responda SOMENTE JSON:
{
  "decisao": "incorporar_portfolio|fundir_em_chamado|manter_revisao|desconsiderar_portfolio",
  "destino_id": "category_id exato ou null",
  "justificativa": "motivo objetivo"
}

Nao invente IDs e nao use travessao."""


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig") if path.exists() else ""


def _parse_args():
    parser = argparse.ArgumentParser(description="Executa o Stage 5 estrito.")
    parser.add_argument("--force", action="store_true", help="regenera o Stage 5")
    return parser.parse_args()


def _norm(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().split())


def _slug(text: str) -> str:
    value = unicodedata.normalize("NFKD", text or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = "".join(ch if ch.isalnum() else "_" for ch in value.casefold())
    return "_".join(part for part in value.split("_") if part)[:36] or "categoria"


def _category_id(group: str, name: str) -> str:
    digest = hashlib.sha256(f"{group}\0{name}".encode("utf-8")).hexdigest()[:8]
    return f"{_slug(name)}_{digest}"


def _hash_json(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _is_uncategorized(category: str) -> bool:
    value = _norm(category)
    return (
        not value
        or value in {"nan", "none", "(vazio)", "sem categoria"}
        or "nao categorizado" in value
    )


def _as_list(value, limit: int | None = None) -> list[str]:
    if isinstance(value, list):
        source = value
    elif value:
        source = [value]
    else:
        source = []
    output = [str(item).strip() for item in source if str(item).strip()]
    return output[:limit] if limit else output


def _one_of(value: str, allowed: set[str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in allowed else default


def _first_text(source: dict, *keys: str) -> str:
    for key in keys:
        value = source.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _public_cluster(label: dict) -> OrderedDict:
    return OrderedDict([
        ("cluster_id", label.get("cluster_id")),
        ("nome", label.get("nome")),
        ("descricao", label.get("descricao")),
        ("quando_usar", label.get("quando_usar")),
        ("informacoes_necessarias", label.get("informacoes_necessarias", [])),
        ("sla_sugerido", label.get("sla_sugerido")),
        ("complexidade", label.get("complexidade")),
        ("total_tickets", label.get("total_tickets")),
        ("volume_percentual", label.get("volume_percentual")),
        ("distribuicao_categorias_atuais", label.get("distribuicao_categorias_atuais", {})),
    ])


def _public_outlier(outlier: dict) -> OrderedDict:
    return OrderedDict([
        ("outlier_id", outlier.get("outlier_id")),
        ("nome", outlier.get("nome")),
        ("descricao", outlier.get("descricao")),
        ("principais_demandas", outlier.get("principais_demandas", [])),
        ("tratamento_esperado", outlier.get("tratamento_esperado")),
        ("motivo", outlier.get("motivo")),
        ("tipo_registro", outlier.get("tipo_registro")),
        (
            "publicavel_no_portfolio",
            bool(outlier.get("publicavel_no_portfolio", True)),
        ),
        ("total", int(outlier.get("total", 0) or 0)),
        ("percentual", outlier.get("percentual", 0)),
        ("keywords", outlier.get("keywords", [])),
        ("sample_intencoes", outlier.get("sample_intencoes", [])),
    ])


def _catalog_group_names(catalog: str) -> list[str]:
    names = []
    seen = set()
    for match in re.finditer(r"(?im)^##\s+Grupo:\s*(.+?)\s*$", catalog or ""):
        name = match.group(1).strip()
        normalized = _norm(name)
        if not name or normalized in seen or "acesso rapido" in normalized:
            continue
        seen.add(normalized)
        names.append(name)
    return names


def _catalog_items(catalog: str) -> list[OrderedDict]:
    items = []
    seen = set()
    current_group = ""
    for raw_line in (catalog or "").splitlines():
        heading = re.match(r"(?i)^##\s+Grupo:\s*(.+?)\s*$", raw_line.strip())
        if heading:
            current_group = heading.group(1).strip()
            continue
        if (
            not current_group
            or "acesso rapido" in _norm(current_group)
            or not raw_line.strip().startswith("|")
        ):
            continue
        columns = [part.strip() for part in raw_line.strip().strip("|").split("|", 1)]
        if len(columns) != 2:
            continue
        name, description = columns
        normalized = _norm(name)
        if (
            not name
            or normalized in {"crt", "chamado", "request type"}
            or set(name) <= {"-", ":"}
            or normalized in seen
        ):
            continue
        seen.add(normalized)
        items.append(OrderedDict([
            ("nome", name),
            ("grupo", current_group),
            ("descricao", description),
        ]))
    return items


def _normalize_operational_profile(raw) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("perfil_operacional deve ser um objeto")
    fields = OrderedDict([
        ("objetivo_usuario", "objetivo do usuario"),
        ("servico_sistema_alvo", "servico ou sistema alvo"),
        ("acao_tratamento", "acao ou tratamento"),
        ("fluxo_responsavel", "fluxo ou responsavel"),
        ("dados_aprovacoes", "dados ou aprovacoes"),
        ("requisitos_seguranca", "requisitos de seguranca"),
    ])
    output = OrderedDict()
    for field, label in fields.items():
        value = str(raw.get(field, "")).strip()
        if not value:
            raise LLMError(f"perfil_operacional sem {label}")
        output[field] = value[:700]
    return output


def _normalize_natural_request(raw: dict, label: dict) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("request type natural nao retornou objeto")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("request type natural sem objeto de resultado")
    natural_name = str(label.get("nome", "")).strip()
    if not natural_name:
        raise LLMError("grupo natural sem nome")
    source = dict(body)
    source["nome"] = natural_name
    if not str(source.get("descricao", "")).strip():
        source["descricao"] = label.get("descricao", "")
    if not source.get("informacoes_obrigatorias"):
        source["informacoes_obrigatorias"] = label.get(
            "informacoes_necessarias", []
        )
    if not str(source.get("sla_sugerido", "")).strip():
        source["sla_sugerido"] = label.get("sla_sugerido", "2 dias uteis")
    if not str(source.get("complexidade", "")).strip():
        source["complexidade"] = label.get("complexidade", "media")
    item = _item_base(source)
    if "acesso rapido" in _norm(item["grupo"]):
        raise LLMError("agrupador de acesso rapido nao e funcional")
    item["perfil_operacional"] = _normalize_operational_profile(
        body.get("perfil_operacional")
    )
    item["baseado_nos_grupos"] = []
    item["substitui_categorias_atuais"] = []
    item["baseado_nos_outliers"] = []
    return item


def _normalize_closed_destination(
    value,
    portfolio_by_id: dict[str, dict],
) -> str:
    destination = str(value or "").strip().strip("`\"'")
    if destination in portfolio_by_id:
        return destination
    wrapped = re.fullmatch(
        r"(?i)\s*(?:category_id|destino_id)\s*[:=]\s*([a-z0-9_-]+)\s*",
        destination,
    )
    if wrapped and wrapped.group(1) in portfolio_by_id:
        return wrapped.group(1)

    # O sufixo hexadecimal e parte deterministica do ID canonico, derivada de
    # SHA-256(grupo + NUL + nome). Modelos podem copiar esse identificador
    # fechado preservando o sufixo e alterar levemente apenas o slug legivel.
    # Aceitamos a recuperacao somente quando:
    #   1. a resposta ainda tem a forma <slug>_<digest de 8 hex>;
    #   2. o digest coincide exatamente;
    #   3. existe um unico ID canonico com esse digest.
    # Nao ha similaridade textual, distancia de edicao ou decisao semantica.
    digest_match = re.fullmatch(
        r"(?i)[a-z0-9][a-z0-9_-]*_([0-9a-f]{8})",
        destination,
    )
    if digest_match:
        suffix = "_" + digest_match.group(1).lower()
        candidates = [
            canonical_id
            for canonical_id in portfolio_by_id
            if canonical_id.lower().endswith(suffix)
        ]
        if len(candidates) == 1:
            canonical_id = candidates[0]
            print(
                "[Stage 5] destino_id normalizado por digest unico: "
                f"{destination} -> {canonical_id}"
            )
            return canonical_id
    raise LLMError(f"destino_id inexistente: {destination or '(vazio)'}")


def categorias_uteis(
    labels: list[dict],
    stage3_tickets: list[dict] | None = None,
) -> OrderedDict:
    counts = Counter()
    if stage3_tickets is not None:
        for ticket in stage3_tickets:
            category = str(ticket.get("tipo_atual", "")).strip()
            if not _is_uncategorized(category):
                counts[category] += 1
        return OrderedDict(counts.most_common())
    for label in labels:
        for category, total in label.get("distribuicao_categorias_atuais", {}).items():
            if not _is_uncategorized(category):
                counts[category] += int(total or 0)
    return OrderedDict(counts.most_common())


def _mandatory_names(config: dict) -> list[str]:
    output = []
    for item in config.get("categorias_obrigatorias", []):
        if isinstance(item, dict):
            name = str(item.get("nome", "")).strip()
        else:
            name = str(item).strip()
        if name:
            output.append(name)
    return output


def _item_base(raw_item: dict) -> OrderedDict:
    name = _first_text(raw_item, "nome", "chamado", "nome_chamado", "request_type", "servico")
    group = _first_text(raw_item, "grupo", "agrupador", "grupo_logico")
    if not name:
        raise LLMError("item de portfolio sem nome")
    if not group:
        raise LLMError(f"item de portfolio sem grupo: {name}")
    item = OrderedDict([
        ("id", _category_id(group, name)),
        ("nome", name[:120]),
        ("grupo", group[:120]),
        ("descricao", str(raw_item.get("descricao", "")).strip()[:900]),
        ("volume_estimado", 0),
        ("percentual_volume", 0.0),
        ("substitui_categorias_atuais", _as_list(raw_item.get("substitui_categorias_atuais"))),
        ("baseado_nos_grupos", _as_list(raw_item.get("baseado_nos_grupos"))),
        ("baseado_nos_outliers", _as_list(raw_item.get("baseado_nos_outliers"))),
        ("informacoes_obrigatorias", _as_list(raw_item.get("informacoes_obrigatorias"), 8)),
        ("sla_sugerido", str(raw_item.get("sla_sugerido", "2 dias uteis")).strip()[:80]),
        ("complexidade", _one_of(raw_item.get("complexidade"), COMPLEXIDADES, "media")),
        ("prioridade_implementacao", _one_of(
            raw_item.get("prioridade_implementacao"), PRIORIDADES, "media"
        )),
    ])
    if raw_item.get("perfil_operacional") is not None:
        item["perfil_operacional"] = _normalize_operational_profile(
            raw_item.get("perfil_operacional")
        )
    status = str(raw_item.get("status_reconciliacao", "")).strip()
    if status:
        if status not in DECISOES_RECONCILIACAO | {"obrigatorio"}:
            raise LLMError(f"status_reconciliacao invalido: {status}")
        item["status_reconciliacao"] = status
        item["justificativa_reconciliacao"] = str(
            raw_item.get("justificativa_reconciliacao", "")
        ).strip()[:1200]
    return item


def _normalize_portfolio(
    raw_portfolio,
    labels: list[dict],
    categories: OrderedDict,
    total_tickets: int,
    mandatory_names: list[str],
    outliers: list[dict],
) -> list[OrderedDict]:
    if not isinstance(raw_portfolio, list) or not raw_portfolio:
        raise LLMError("portfolio_otimizado deve conter objetos completos")

    natural_names = {str(item.get("nome", "")).strip() for item in labels if item.get("nome")}
    mandatory_normalized = {_norm(name) for name in mandatory_names}
    outlier_totals = {
        str(item.get("outlier_id", "")).strip(): int(item.get("total", 0) or 0)
        for item in outliers if str(item.get("outlier_id", "")).strip()
    }
    items: list[OrderedDict] = []
    seen_names: dict[str, str] = {}
    for index, raw_item in enumerate(raw_portfolio):
        if not isinstance(raw_item, dict):
            raise LLMError(f"portfolio_otimizado[{index}] nao e um objeto")
        item = _item_base(raw_item)
        if "perfil_operacional" not in item:
            raise LLMError(f"{item['nome']} nao possui perfil_operacional")
        if item.get("status_reconciliacao") not in (
            DECISOES_RECONCILIACAO | {"obrigatorio"}
        ):
            raise LLMError(
                f"{item['nome']} nao possui status_reconciliacao valido"
            )
        normalized_name = _norm(item["nome"])
        if normalized_name in seen_names:
            raise LLMError(
                f"chamado duplicado: {seen_names[normalized_name]} e {item['nome']}"
            )
        seen_names[normalized_name] = item["nome"]

        unknown_categories = [
            category for category in item["substitui_categorias_atuais"]
            if category not in categories
        ]
        if unknown_categories:
            raise LLMError(
                f"{item['nome']} referencia categorias atuais inexistentes: "
                + ", ".join(unknown_categories)
            )
        unknown_naturals = [
            natural for natural in item["baseado_nos_grupos"]
            if natural not in natural_names
        ]
        if unknown_naturals:
            raise LLMError(
                f"{item['nome']} referencia grupos naturais inexistentes: "
                + ", ".join(unknown_naturals)
            )
        unknown_outliers = [
            outlier_id for outlier_id in item["baseado_nos_outliers"]
            if outlier_id not in outlier_totals
        ]
        if unknown_outliers:
            raise LLMError(
                f"{item['nome']} referencia candidatos raros inexistentes: "
                + ", ".join(unknown_outliers)
            )
        if (
            not item["substitui_categorias_atuais"]
            and not item["baseado_nos_grupos"]
            and not item["baseado_nos_outliers"]
            and _norm(item["nome"]) not in mandatory_normalized
        ):
            raise LLMError(
                f"{item['nome']} nao tem demanda historica nem e categoria obrigatoria"
            )
        items.append(item)

    category_owners: dict[str, list[str]] = defaultdict(list)
    natural_owners: dict[str, list[str]] = defaultdict(list)
    outlier_owners: dict[str, list[str]] = defaultdict(list)
    for item in items:
        for category in item["substitui_categorias_atuais"]:
            category_owners[category].append(item["nome"])
        for natural in item["baseado_nos_grupos"]:
            natural_owners[natural].append(item["nome"])
        for outlier_id in item["baseado_nos_outliers"]:
            outlier_owners[outlier_id].append(item["nome"])

    missing_categories = [category for category in categories if not category_owners[category]]
    duplicate_categories = {
        category: owners for category, owners in category_owners.items() if len(owners) > 1
    }
    missing_naturals = [natural for natural in natural_names if not natural_owners[natural]]
    duplicate_naturals = {
        natural: owners for natural, owners in natural_owners.items()
        if len(owners) > 1
    }
    if missing_categories:
        raise LLMError(
            "categorias atuais sem mapeamento: " + ", ".join(missing_categories[:12])
        )
    if duplicate_categories:
        details = "; ".join(
            f"{category} -> {', '.join(owners)}"
            for category, owners in list(duplicate_categories.items())[:8]
        )
        raise LLMError("categorias atuais repetidas: " + details)
    if missing_naturals:
        raise LLMError("grupos naturais sem cobertura: " + ", ".join(sorted(missing_naturals)))
    if duplicate_naturals:
        details = "; ".join(
            f"{natural} -> {', '.join(owners)}"
            for natural, owners in list(duplicate_naturals.items())[:8]
        )
        raise LLMError("grupos naturais com mais de um destino: " + details)
    duplicated_outliers = {
        outlier_id: owners
        for outlier_id, owners in outlier_owners.items()
        if len(owners) > 1
    }
    if duplicated_outliers:
        details = "; ".join(
            f"{outlier_id} -> {', '.join(owners)}"
            for outlier_id, owners in duplicated_outliers.items()
        )
        raise LLMError("candidatos raros repetidos no portfolio: " + details)

    normalized_portfolio_names = {_norm(item["nome"]) for item in items}
    missing_mandatory = [
        name for name in mandatory_names if _norm(name) not in normalized_portfolio_names
    ]
    if missing_mandatory:
        raise LLMError(
            "categorias obrigatorias ausentes: " + ", ".join(missing_mandatory)
        )

    natural_totals = {
        item["nome"]: int(item.get("total_tickets", 0) or 0) for item in labels
    }
    for item in items:
        volume = sum(int(categories[category]) for category in item["substitui_categorias_atuais"])
        if not item["substitui_categorias_atuais"]:
            volume = sum(
                natural_totals.get(group, 0) for group in item["baseado_nos_grupos"]
            ) + sum(
                outlier_totals.get(outlier_id, 0)
                for outlier_id in item["baseado_nos_outliers"]
            )
        item["volume_estimado"] = int(volume)
        item["percentual_volume"] = round(volume / max(total_tickets, 1) * 100, 1)
    return items


def _normalize_outlier_evaluation(
    raw,
    outliers: list[dict],
    portfolio: list[OrderedDict],
) -> list[OrderedDict]:
    expected = {
        str(item.get("outlier_id", "")).strip()
        for item in outliers if str(item.get("outlier_id", "")).strip()
    }
    if not expected and raw in (None, []):
        return []
    if not isinstance(raw, list):
        raise LLMError("avaliacao_outliers_stage3 deve ser uma lista")

    portfolio_names = {item["nome"] for item in portfolio}
    owners: dict[str, list[str]] = defaultdict(list)
    for item in portfolio:
        for outlier_id in item["baseado_nos_outliers"]:
            owners[outlier_id].append(item["nome"])

    by_id = {}
    for index, source in enumerate(raw):
        if not isinstance(source, dict):
            raise LLMError(f"avaliacao_outliers_stage3[{index}] nao e objeto")
        outlier_id = str(source.get("outlier_id", "")).strip()
        if not outlier_id or outlier_id in by_id:
            raise LLMError(f"outlier_id ausente ou repetido: {outlier_id or '(vazio)'}")
        decision = str(source.get("decisao", "")).strip().lower()
        if decision not in DECISOES_OUTLIER:
            raise LLMError(f"decisao invalida para {outlier_id}: {decision}")
        destination = str(source.get("destino_portfolio", "") or "").strip() or None
        reason = str(source.get("justificativa", "")).strip()
        if not reason:
            raise LLMError(f"avaliacao do candidato raro {outlier_id} sem justificativa")
        linked = owners.get(outlier_id, [])
        if decision in {"incorporar_portfolio", "fundir_em_chamado"}:
            if destination not in portfolio_names:
                raise LLMError(
                    f"{outlier_id} exige destino_portfolio existente: {destination}"
                )
            if linked != [destination]:
                raise LLMError(
                    f"{outlier_id} deve estar vinculado somente a {destination}"
                )
        elif destination is not None or linked:
            raise LLMError(
                f"{outlier_id} com decisao {decision} nao pode ter destino no portfolio"
            )
        by_id[outlier_id] = OrderedDict([
            ("outlier_id", outlier_id),
            ("decisao", decision),
            ("destino_portfolio", destination),
            ("justificativa", reason[:700]),
        ])

    missing = sorted(expected - set(by_id))
    unknown = sorted(set(by_id) - expected)
    if missing or unknown:
        raise LLMError(
            "cobertura dos candidatos raros divergente: "
            f"faltando={len(missing)} extras={len(unknown)}"
        )
    return [by_id[outlier_id] for outlier_id in sorted(expected)]


def _normalize_groups(raw_groups, portfolio: list[OrderedDict], total_tickets: int):
    if not isinstance(raw_groups, list) or not raw_groups:
        raise LLMError("grupos_otimizados deve ser uma lista de objetos")

    raw_by_name = {}
    for index, raw in enumerate(raw_groups):
        if not isinstance(raw, dict):
            raise LLMError(f"grupos_otimizados[{index}] nao e um objeto")
        name = _first_text(raw, "nome", "grupo", "agrupador", "grupo_logico")
        if not name:
            raise LLMError(f"grupos_otimizados[{index}] sem nome")
        if name in raw_by_name:
            raise LLMError(f"grupo otimizado duplicado: {name}")
        raw_by_name[name] = raw

    portfolio_by_group: OrderedDict[str, list[OrderedDict]] = OrderedDict()
    for item in portfolio:
        portfolio_by_group.setdefault(item["grupo"], []).append(item)

    missing = [name for name in portfolio_by_group if name not in raw_by_name]
    extra = [name for name in raw_by_name if name not in portfolio_by_group]
    if missing:
        raise LLMError("grupos usados no portfolio mas nao declarados: " + ", ".join(missing))
    if extra:
        raise LLMError("grupos declarados sem chamados no portfolio: " + ", ".join(extra))

    output = []
    for group, items in portfolio_by_group.items():
        raw = raw_by_name[group]
        expected = [item["nome"] for item in items]
        declared = _as_list(raw.get("chamados"))
        if set(declared) != set(expected) or len(declared) != len(expected):
            raise LLMError(f"lista de chamados divergente no grupo {group}")
        volume = sum(int(item["volume_estimado"]) for item in items)
        output.append(OrderedDict([
            ("nome", group),
            ("descricao", str(raw.get("descricao", "")).strip()[:700]),
            ("volume_estimado", volume),
            ("percentual_volume", round(volume / max(total_tickets, 1) * 100, 1)),
            ("chamados", expected),
        ]))
    return output


def _category_natural_evidence(
    labels: list[dict],
    category: str,
) -> list[OrderedDict]:
    evidence = []
    for label in labels:
        name = str(label.get("nome", "")).strip()
        distribution = label.get("distribuicao_categorias_atuais", {})
        if not name or not isinstance(distribution, dict):
            continue
        volume = int(distribution.get(category, 0) or 0)
        if volume <= 0:
            continue
        evidence.append(OrderedDict([
            ("nome", name),
            ("volume", volume),
        ]))
    return sorted(
        evidence,
        key=lambda item: (-item["volume"], _norm(item["nome"])),
    )


def _normalize_mapping(
    raw,
    categories: OrderedDict,
    labels: list[dict],
    portfolio: list[OrderedDict],
):
    if not isinstance(raw, list):
        raise LLMError("mapeamento_atual_vs_natural deve ser uma lista")
    by_category = {}
    for item in raw:
        if not isinstance(item, dict):
            raise LLMError("mapeamento_atual_vs_natural contem item nao objeto")
        category = str(item.get("categoria_atual", "")).strip()
        if category:
            if category in by_category:
                raise LLMError(f"mapeamento duplicado para categoria atual: {category}")
            by_category[category] = item

    missing = [category for category in categories if category not in by_category]
    unknown = [category for category in by_category if category not in categories]
    if missing:
        raise LLMError("mapeamento sem categorias atuais: " + ", ".join(missing[:12]))
    if unknown:
        raise LLMError("mapeamento contem categorias desconhecidas: " + ", ".join(unknown[:12]))

    output = []
    portfolio_by_id = {item["id"]: item for item in portfolio}
    owner_by_category = {}
    for item in portfolio:
        for category in item["substitui_categorias_atuais"]:
            owner_by_category[category] = item
    for category, volume in categories.items():
        source = by_category[category]
        owner = owner_by_category.get(category)
        if owner is None:
            raise LLMError(f"mapeamento sem destino para categoria atual: {category}")
        destination = str(source.get("destino_id", "")).strip()
        if destination and destination not in portfolio_by_id:
            raise LLMError(
                f"mapeamento de {category} usa destino inexistente: {destination}"
            )
        if destination and destination != owner["id"]:
            raise LLMError(
                f"mapeamento de {category} diverge do portfolio montado"
            )
        output.append(OrderedDict([
            ("categoria_atual", category),
            ("volume_atual", int(volume)),
            ("destino_id", owner["id"]),
            ("destino_portfolio", owner["nome"]),
            (
                "grupos_naturais_observados",
                _category_natural_evidence(labels, category),
            ),
            ("aderencia", _one_of(source.get("aderencia"), ADERENCIAS, "parcial")),
            ("observacao", str(source.get("observacao", "")).strip()[:500]),
        ]))
    return output


def _normalize_reconciliation_report(
    raw,
    natural_names: set[str],
    portfolio: list[OrderedDict],
) -> list[OrderedDict]:
    if not isinstance(raw, list):
        raise LLMError("reconciliacao_grupos_naturais deve ser uma lista")
    portfolio_by_id = {item["id"]: item for item in portfolio}
    by_natural = {}
    for source in raw:
        if not isinstance(source, dict):
            raise LLMError("reconciliacao_grupos_naturais contem item nao objeto")
        natural_name = str(source.get("grupo_natural", "")).strip()
        if not natural_name or natural_name in by_natural:
            raise LLMError(
                "reconciliacao com grupo natural ausente ou repetido: "
                + (natural_name or "(vazio)")
            )
        decision_llm = str(source.get("decisao_llm", "")).strip()
        final_decision = str(source.get("decisao_final", "")).strip()
        if decision_llm not in DECISOES_RECONCILIACAO:
            raise LLMError(
                f"decisao_llm invalida na reconciliacao de {natural_name}"
            )
        if final_decision not in DECISOES_RECONCILIACAO:
            raise LLMError(
                f"decisao_final invalida na reconciliacao de {natural_name}"
            )
        destination = str(source.get("destino_id", "")).strip()
        if destination not in portfolio_by_id:
            raise LLMError(
                f"reconciliacao de {natural_name} usa destino inexistente"
            )
        item = portfolio_by_id[destination]
        if source.get("destino_nome") != item["nome"]:
            raise LLMError(
                f"reconciliacao de {natural_name} tem nome de destino divergente"
            )
        if final_decision != item.get("status_reconciliacao"):
            raise LLMError(
                f"reconciliacao de {natural_name} diverge do status do destino"
            )
        criteria_raw = source.get("criterios")
        if not isinstance(criteria_raw, dict):
            raise LLMError(
                f"reconciliacao de {natural_name} nao possui criterios"
            )
        criteria = OrderedDict()
        for field in CRITERIOS_RECONCILIACAO:
            value = criteria_raw.get(field)
            if not isinstance(value, bool):
                raise LLMError(
                    f"criterio {field} invalido para {natural_name}"
                )
            criteria[field] = value
        reason = str(source.get("justificativa", "")).strip()
        if not reason:
            raise LLMError(
                f"reconciliacao de {natural_name} sem justificativa"
            )
        by_natural[natural_name] = OrderedDict([
            ("grupo_natural", natural_name),
            ("decisao_llm", decision_llm),
            ("decisao_final", final_decision),
            ("destino_id", destination),
            ("destino_nome", item["nome"]),
            ("criterios", criteria),
            ("justificativa", reason[:1000]),
        ])

    missing = sorted(natural_names - set(by_natural))
    unknown = sorted(set(by_natural) - natural_names)
    if missing or unknown:
        raise LLMError(
            "cobertura da reconciliacao divergente: "
            f"faltando={len(missing)} extras={len(unknown)}"
        )
    return [by_natural[name] for name in sorted(natural_names)]


def _normalize_revision(raw):
    if not isinstance(raw, dict) or raw.get("contexto_lido") is not True:
        raise LLMError("revisao_contexto_catalogo.contexto_lido deve vir como true")
    considered = _as_list(raw.get("agrupadores_atuais_considerados"))
    if not considered:
        raise LLMError("revisao do catalogo nao lista agrupadores atuais considerados")
    return OrderedDict([
        ("contexto_lido", True),
        ("principio", str(raw.get("principio", "")).strip()),
        ("agrupadores_atuais_considerados", considered),
        ("decisoes_de_agrupamento", raw.get("decisoes_de_agrupamento", [])
         if isinstance(raw.get("decisoes_de_agrupamento"), list) else []),
        ("ajustes_pos_revisao", _as_list(raw.get("ajustes_pos_revisao"))),
    ])


def _normalize_problems(raw):
    output = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            output.append(OrderedDict([
                ("tipo", _one_of(item.get("tipo"), PROBLEMAS, "lacuna")),
                ("severidade", _one_of(item.get("severidade"), PRIORIDADES, "media")),
                ("descricao", str(item.get("descricao", "")).strip()[:700]),
                ("categorias_envolvidas", _as_list(item.get("categorias_envolvidas"))),
            ]))
    return output


def _normalize_actions(raw):
    output = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, dict):
            output.append(OrderedDict([
                ("acao", str(item.get("acao", "")).strip()[:300]),
                ("impacto", str(item.get("impacto", "")).strip()[:300]),
                ("prazo", _one_of(item.get("prazo"), PRAZOS, "curto_prazo")),
            ]))
    return output


def normalizar(
    raw: dict,
    labels: list[dict],
    categories: OrderedDict,
    total_tickets: int,
    mandatory_names: list[str] | None = None,
    outliers: list[dict] | None = None,
) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("Stage 5 nao retornou um objeto JSON")
    recommendation = raw.get("recomendacao", raw)
    if not isinstance(recommendation, dict):
        raise LLMError("Stage 5 retornou JSON sem objeto recomendacao")

    mandatory_names = mandatory_names or []
    outliers = outliers or []
    natural_names = {
        str(item.get("nome", "")).strip() for item in labels if item.get("nome")
    }
    portfolio = _normalize_portfolio(
        recommendation.get("portfolio_otimizado"),
        labels,
        categories,
        total_tickets,
        mandatory_names,
        outliers,
    )
    outlier_evaluation = _normalize_outlier_evaluation(
        recommendation.get("avaliacao_outliers_stage3"), outliers, portfolio
    )
    groups = _normalize_groups(
        recommendation.get("grupos_otimizados"), portfolio, total_tickets
    )
    mapping = _normalize_mapping(
        recommendation.get("mapeamento_atual_vs_natural"),
        categories,
        labels,
        portfolio,
    )
    reconciliation = _normalize_reconciliation_report(
        recommendation.get("reconciliacao_grupos_naturais"),
        natural_names,
        portfolio,
    )
    revision = _normalize_revision(recommendation.get("revisao_contexto_catalogo"))
    impact = recommendation.get("impacto_estimado")
    impact = impact if isinstance(impact, dict) else {}

    return OrderedDict([
        ("analise_geral", str(recommendation.get("analise_geral", "")).strip()),
        ("problemas_encontrados", _normalize_problems(
            recommendation.get("problemas_encontrados")
        )),
        ("mapeamento_atual_vs_natural", mapping),
        ("reconciliacao_grupos_naturais", reconciliation),
        ("revisao_contexto_catalogo", revision),
        ("grupos_otimizados", groups),
        ("portfolio_otimizado", portfolio),
        ("avaliacao_outliers_stage3", outlier_evaluation),
        ("acoes_prioritarias", _normalize_actions(
            recommendation.get("acoes_prioritarias")
        )),
        ("impacto_estimado", OrderedDict([
            ("reducao_vaievem", str(impact.get("reducao_vaievem", "")).strip()),
            ("melhoria_tempo_resolucao", str(
                impact.get("melhoria_tempo_resolucao", "")
            ).strip()),
            ("justificativa", str(impact.get("justificativa", "")).strip()),
        ])),
    ])


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value)


def _get_json_client(default_client):
    model = (
        os.getenv("STAGE5_JSON_MODEL", "").strip()
        or os.getenv("STAGE3_JSON_MODEL", "").strip()
    )
    if not model:
        return default_client
    if getattr(default_client, "provider", "") == "ollama" and model == getattr(
        default_client, "model", ""
    ):
        return default_client
    return LLMClient(provider_override="ollama", model_override=model)


def _base_payload(
    config: dict,
    catalog: str,
    labels: list[dict],
    categories: OrderedDict,
    total_tickets: int,
    portal_name: str,
) -> OrderedDict:
    catalog_groups = _catalog_group_names(catalog)
    return OrderedDict([
        ("objetivo", f"Desenhar a estrutura-base do portfolio do portal {portal_name}."),
        ("total_tickets", total_tickets),
        ("contexto_portal", config.get("infra_context", {}).get("texto_contexto", "")),
        ("categorias_obrigatorias", config.get("categorias_obrigatorias", [])),
        ("agrupadores_atuais", catalog_groups),
        ("quantidade_agrupadores_atuais", len(catalog_groups)),
        (
            "politica_agrupadores_logicos",
            "Use os agrupadores atuais como referencia forte. Em geral, nao "
            "crie mais grupos logicos do que ja existem; diferencie servicos "
            "em request types e formularios quando isso for suficiente.",
        ),
        ("catalogo_atual_grupos_chamados", catalog),
        ("categorias_atuais_agregadas", categories),
        ("grupos_naturais_stage4", [_public_cluster(item) for item in labels]),
        (
            "instrucao_de_escopo",
            "Nao mapeie categorias atuais nem candidatos raros nesta chamada.",
        ),
    ])


def _validate_base_plan(plan: str, mandatory_names: list[str]) -> None:
    if not isinstance(plan, str) or not plan.strip():
        raise LLMError("plano-base do Stage 5 vazio")
    if plan.count("[CHAMADO]") < 1:
        raise LLMError("plano-base deve conter pelo menos um bloco CHAMADO")
    normalized_plan = _norm(plan)
    missing = [name for name in mandatory_names if _norm(name) not in normalized_plan]
    if missing:
        raise LLMError(
            "plano-base omitiu categorias obrigatorias: " + ", ".join(missing)
        )


def _normalize_base(raw: dict, mandatory_names: list[str]) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("compilacao do portfolio-base nao retornou objeto JSON")
    recommendation = raw.get("recomendacao_base", raw)
    if not isinstance(recommendation, dict):
        raise LLMError("compilacao sem objeto recomendacao_base")
    raw_portfolio = recommendation.get("portfolio_otimizado")
    if not isinstance(raw_portfolio, list) or not raw_portfolio:
        raise LLMError("portfolio-base deve conter chamados")

    portfolio = []
    seen_names = set()
    for index, source in enumerate(raw_portfolio):
        if not isinstance(source, dict):
            raise LLMError(f"portfolio-base[{index}] nao e objeto")
        item = _item_base(source)
        normalized = _norm(item["nome"])
        if normalized in seen_names:
            raise LLMError(f"portfolio-base tem chamado duplicado: {item['nome']}")
        seen_names.add(normalized)
        item["substitui_categorias_atuais"] = []
        item["baseado_nos_grupos"] = []
        item["baseado_nos_outliers"] = []
        portfolio.append(item)

    missing_mandatory = [
        name for name in mandatory_names if _norm(name) not in seen_names
    ]
    if missing_mandatory:
        raise LLMError(
            "portfolio-base omitiu categorias obrigatorias: "
            + ", ".join(missing_mandatory)
        )

    impact = recommendation.get("impacto_estimado")
    impact = impact if isinstance(impact, dict) else {}
    return OrderedDict([
        ("analise_geral", str(recommendation.get("analise_geral", "")).strip()),
        (
            "problemas_encontrados",
            _normalize_problems(recommendation.get("problemas_encontrados")),
        ),
        (
            "revisao_contexto_catalogo",
            _normalize_revision(recommendation.get("revisao_contexto_catalogo")),
        ),
        ("portfolio_otimizado", portfolio),
        (
            "acoes_prioritarias",
            _normalize_actions(recommendation.get("acoes_prioritarias")),
        ),
        ("impacto_estimado", OrderedDict([
            ("reducao_vaievem", str(impact.get("reducao_vaievem", "")).strip()),
            (
                "melhoria_tempo_resolucao",
                str(impact.get("melhoria_tempo_resolucao", "")).strip(),
            ),
            ("justificativa", str(impact.get("justificativa", "")).strip()),
        ])),
    ])


def _build_base(
    client,
    json_client,
    payload: OrderedDict,
    mandatory_names: list[str],
) -> tuple[OrderedDict, str]:
    base_user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    last_error = "resposta nao processada"
    for semantic_attempt in range(1, 4):
        semantic_user = base_user
        if semantic_attempt > 1:
            semantic_user += (
                "\n\nO plano anterior foi invalido: " + last_error
                + "\nRefaca todos os blocos no formato canonico."
            )
        try:
            plan = client.chat_text(
                BASE_DECISION_SYSTEM,
                semantic_user,
                max_tokens=8000,
                timeout=1200,
            )
            _validate_base_plan(plan, mandatory_names)
        except LLMError as exc:
            last_error = str(exc)
            print(
                f"[Stage 5a] plano tentativa {semantic_attempt}/3 invalida: "
                f"{last_error}"
            )
            continue

        compiler_error = ""
        for compiler_attempt in range(1, 4):
            compiler_user = json.dumps({
                "categorias_obrigatorias": mandatory_names,
                "plano_canonico": plan,
                "erro_compilacao_anterior": compiler_error,
            }, ensure_ascii=False, separators=(",", ":"))
            try:
                raw = json_client.chat_json(
                    BASE_JSON_SYSTEM,
                    compiler_user,
                    max_tokens=10000,
                    timeout=1200,
                )
                return _normalize_base(raw, mandatory_names), plan
            except LLMError as exc:
                compiler_error = str(exc)
                print(
                    f"[Stage 5a] compilacao JSON tentativa "
                    f"{compiler_attempt}/3 invalida: {compiler_error}"
                )
        last_error = "compilacao JSON invalida: " + compiler_error
    raise LLMError("portfolio-base invalido apos retries: " + last_error)


def _reconciliation_candidate(item: dict, label: dict) -> OrderedDict:
    return OrderedDict([
        ("candidate_id", item["id"]),
        ("nome", item["nome"]),
        ("grupo_logico_sugerido", item["grupo"]),
        ("descricao", item["descricao"]),
        ("perfil_operacional", item["perfil_operacional"]),
        ("informacoes_obrigatorias", item["informacoes_obrigatorias"]),
        ("sla_sugerido", item["sla_sugerido"]),
        ("complexidade", item["complexidade"]),
        ("grupo_natural", _public_cluster(label)),
    ])


def _validate_reconciliation_plan(
    plan: str,
    mandatory_names: list[str],
) -> int:
    if not isinstance(plan, str) or not plan.strip():
        raise LLMError("plano de reconciliacao vazio")
    starts = plan.count("[CHAMADO_FINAL]")
    ends = plan.count("[/CHAMADO_FINAL]")
    if starts < 1 or starts != ends:
        raise LLMError(
            "plano de reconciliacao contem blocos CHAMADO_FINAL incompletos"
        )
    required_fields = (
        "NOME:",
        "GRUPO:",
        "DESCRICAO:",
        "OBJETIVO_USUARIO:",
        "SERVICO_SISTEMA_ALVO:",
        "ACAO_TRATAMENTO:",
        "FLUXO_RESPONSAVEL:",
        "DADOS_APROVACOES:",
        "REQUISITOS_SEGURANCA:",
        "INFORMACOES:",
        "SLA:",
        "COMPLEXIDADE:",
        "PRIORIDADE:",
    )
    blocks = re.findall(
        r"\[CHAMADO_FINAL\](.*?)\[/CHAMADO_FINAL\]",
        plan,
        flags=re.DOTALL,
    )
    if len(blocks) != starts:
        raise LLMError("nao foi possivel ler todos os blocos CHAMADO_FINAL")
    for index, block in enumerate(blocks, start=1):
        missing = [field for field in required_fields if field not in block]
        if missing:
            raise LLMError(
                f"bloco CHAMADO_FINAL {index} incompleto: "
                + ", ".join(missing)
            )
    normalized_plan = _norm(plan)
    missing_mandatory = [
        name for name in mandatory_names if _norm(name) not in normalized_plan
    ]
    if missing_mandatory:
        raise LLMError(
            "plano reconciliado omitiu categorias obrigatorias: "
            + ", ".join(missing_mandatory)
        )
    return starts


def _reconciliation_plan_blocks(plan: str) -> list[str]:
    blocks = re.findall(
        r"\[CHAMADO_FINAL\](.*?)\[/CHAMADO_FINAL\]",
        plan,
        flags=re.DOTALL,
    )
    return [
        "[CHAMADO_FINAL]\n"
        + block.strip()
        + "\n[/CHAMADO_FINAL]"
        for block in blocks
    ]


def _normalize_reconciled_portfolio(
    raw: dict,
    mandatory_names: list[str],
    expected_count: int,
) -> list[OrderedDict]:
    if not isinstance(raw, dict):
        raise LLMError("compilacao da reconciliacao nao retornou objeto JSON")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("compilacao da reconciliacao sem objeto de resultado")
    sources = body.get("portfolio_reconciliado")
    if not isinstance(sources, list) or not sources:
        raise LLMError("portfolio_reconciliado deve ser uma lista nao vazia")
    if len(sources) != expected_count:
        raise LLMError(
            "compilacao alterou a quantidade de blocos: "
            f"esperado={expected_count} obtido={len(sources)}"
        )

    output = []
    seen_names = {}
    seen_ids = set()
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise LLMError(f"portfolio_reconciliado[{index}] nao e objeto")
        item = _item_base(source)
        if not item["descricao"]:
            raise LLMError(f"chamado reconciliado sem descricao: {item['nome']}")
        if "perfil_operacional" not in item:
            raise LLMError(
                f"chamado reconciliado sem perfil_operacional: {item['nome']}"
            )
        normalized = _norm(item["nome"])
        if normalized in seen_names:
            raise LLMError(
                f"chamado reconciliado duplicado: "
                f"{seen_names[normalized]} e {item['nome']}"
            )
        if item["id"] in seen_ids:
            raise LLMError(f"category_id reconciliado duplicado: {item['id']}")
        seen_names[normalized] = item["nome"]
        seen_ids.add(item["id"])
        item["substitui_categorias_atuais"] = []
        item["baseado_nos_grupos"] = []
        item["baseado_nos_outliers"] = []
        output.append(item)

    missing_mandatory = [
        name for name in mandatory_names if _norm(name) not in seen_names
    ]
    if missing_mandatory:
        raise LLMError(
            "portfolio reconciliado omitiu categorias obrigatorias: "
            + ", ".join(missing_mandatory)
        )
    return output


def _build_reconciliation_plan(
    client,
    payload: OrderedDict,
    mandatory_names: list[str],
) -> str:
    base_user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    last_error = "resposta nao processada"
    plan_tokens = max(
        3000, int(os.getenv("STAGE5_RECONCILE_PLAN_MAX_TOKENS", "10000"))
    )
    for semantic_attempt in range(1, 4):
        semantic_user = base_user
        if semantic_attempt > 1:
            semantic_user += (
                "\n\nO plano anterior foi invalido: " + last_error
                + "\nRefaca todos os blocos completos sem impor quantidade."
            )
        try:
            plan = client.chat_text(
                RECONCILIATION_DECISION_SYSTEM,
                semantic_user,
                max_tokens=plan_tokens,
                timeout=1200,
            )
            _validate_reconciliation_plan(plan, mandatory_names)
            return plan
        except LLMError as exc:
            last_error = str(exc)
            print(
                f"[Stage 5a.2] plano tentativa "
                f"{semantic_attempt}/3 invalida: {last_error}"
            )
    raise LLMError("plano de reconciliacao invalido apos retries: " + last_error)


def _compile_reconciliation_plan(
    json_client,
    plan: str,
    mandatory_names: list[str],
    checkpoint_path: Path,
    reconciliation_fingerprint: str,
    force: bool = False,
) -> list[OrderedDict]:
    expected_count = _validate_reconciliation_plan(plan, mandatory_names)
    blocks = _reconciliation_plan_blocks(plan)
    if len(blocks) != expected_count:
        raise LLMError(
            "quantidade de blocos extraidos diverge do plano validado"
        )

    block_hashes = {
        str(index): _hash_json({
            "version": PIPELINE_VERSION,
            "compiler_version": RECONCILIATION_COMPILER_VERSION,
            "reconciliation_fingerprint": reconciliation_fingerprint,
            "json_model": json_client.model_label,
            "json_system": RECONCILIATION_JSON_SYSTEM,
            "block": block,
        })
        for index, block in enumerate(blocks, start=1)
    }
    compiled: dict[str, dict] = (
        {}
        if force
        else _load_partition_checkpoint(
            checkpoint_path,
            "block_index",
            block_hashes,
        )
    )
    pending = [
        str(index)
        for index in range(1, expected_count + 1)
        if str(index) not in compiled
    ]
    print(
        f"[Stage 5a.2] blocos_reconciliados={expected_count} "
        f"compilados={len(compiled)} pendentes={len(pending)}"
    )
    max_tokens = max(
        900,
        int(os.getenv("STAGE5_RECONCILE_JSON_BLOCK_MAX_TOKENS", "2000")),
    )
    def compile_block(key: str) -> dict:
        block_index = int(key)
        payload = {
            "quantidade_blocos": 1,
            "indice_bloco": block_index,
            "plano_canonico": blocks[block_index - 1],
        }
        item = _call_small_json(
            json_client,
            RECONCILIATION_JSON_SYSTEM,
            payload,
            lambda raw: _normalize_reconciled_portfolio(
                raw,
                [],
                1,
            )[0],
            max_tokens=max_tokens,
        )
        return {"item": item}

    _run_partitioned_queue(
        stage_label="Stage 5a.2",
        pending_keys=pending,
        results=compiled,
        checkpoint_path=checkpoint_path,
        key_field="block_index",
        input_hashes=block_hashes,
        build_payload=compile_block,
        progress_text="blocos JSON compilados",
    )

    items = [
        compiled[str(index)]["item"]
        for index in range(1, expected_count + 1)
    ]
    return _normalize_reconciled_portfolio(
        {"portfolio_reconciliado": items},
        mandatory_names,
        expected_count,
    )


def _reconciliation_portfolio_text(portfolio: list[dict]) -> str:
    lines = []
    for item in portfolio:
        profile = item["perfil_operacional"]
        lines.append(
            f"category_id={item['id']} | chamado={item['nome']} | "
            f"grupo={item['grupo']} | objetivo={profile['objetivo_usuario']} | "
            f"servico_sistema={profile['servico_sistema_alvo']} | "
            f"tratamento={profile['acao_tratamento']} | "
            f"fluxo_responsavel={profile['fluxo_responsavel']} | "
            f"dados_aprovacoes={profile['dados_aprovacoes']} | "
            f"descricao={item['descricao']}"
        )
    return "\n".join(lines)


def _normalize_reconciliation_assignment(
    raw: dict,
    portfolio_by_id: dict[str, dict],
) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("decisao de reconciliacao nao retornou objeto")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("decisao de reconciliacao sem objeto de resultado")
    decision = str(body.get("decisao", "")).strip().lower()
    if decision not in DECISOES_RECONCILIACAO:
        raise LLMError(
            f"decisao de reconciliacao invalida: {decision or '(vazio)'}"
        )
    criteria_raw = body.get("criterios")
    if not isinstance(criteria_raw, dict):
        raise LLMError("decisao de reconciliacao sem criterios")
    criteria = OrderedDict()
    for field in CRITERIOS_RECONCILIACAO:
        value = criteria_raw.get(field)
        if not isinstance(value, bool):
            raise LLMError(f"criterio {field} deve ser booleano")
        criteria[field] = value

    destination = body.get("destino_id")
    destination_text = str(destination).strip() if destination is not None else ""
    if destination_text.lower() in {"", "null", "none"}:
        destination_text = None
    if decision == "dividir_para_revisao":
        if destination_text is not None:
            raise LLMError(
                "dividir_para_revisao nao pode receber destino_id"
            )
    else:
        destination_text = _normalize_closed_destination(
            destination_text,
            portfolio_by_id,
        )
        failed = [field for field, value in criteria.items() if value is not True]
        if failed:
            raise LLMError(
                f"decisao {decision} exige todos os criterios compativeis: "
                + ", ".join(failed)
            )
    reason = str(body.get("justificativa", "")).strip()
    if not reason:
        raise LLMError("decisao de reconciliacao sem justificativa")
    return OrderedDict([
        ("decisao", decision),
        ("destino_id", destination_text),
        ("criterios", criteria),
        ("justificativa", reason[:1000]),
    ])


def _normalize_merge_audit(raw: dict) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("auditoria de fusao nao retornou objeto")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("auditoria de fusao sem objeto de resultado")
    decision = str(body.get("decisao", "")).strip().lower()
    if decision not in DECISOES_AUDITORIA_FUSAO:
        raise LLMError(
            f"decisao de auditoria invalida: {decision or '(vazio)'}"
        )
    criteria_raw = body.get("criterios")
    if not isinstance(criteria_raw, dict):
        raise LLMError("auditoria de fusao sem criterios")
    criteria = OrderedDict()
    for field in CRITERIOS_RECONCILIACAO:
        value = criteria_raw.get(field)
        if not isinstance(value, bool):
            raise LLMError(f"criterio {field} deve ser booleano")
        criteria[field] = value
    all_compatible = all(criteria.values())
    if decision == "aprovar_fusao" and not all_compatible:
        raise LLMError(
            "aprovar_fusao exige todos os criterios operacionais compativeis"
        )
    if decision == "rejeitar_fusao" and all_compatible:
        raise LLMError(
            "rejeitar_fusao exige ao menos um criterio operacional divergente"
        )
    reason = str(body.get("justificativa", "")).strip()
    if not reason:
        raise LLMError("auditoria de fusao sem justificativa")
    return OrderedDict([
        ("decisao", decision),
        ("criterios", criteria),
        ("justificativa", reason[:1000]),
    ])


def _assemble_reconciled_portfolio(
    targets: list[OrderedDict],
    assignments: dict[str, dict],
    natural_items: dict[str, OrderedDict],
    mandatory_names: list[str],
    merge_audits: dict[str, dict] | None = None,
) -> tuple[list[OrderedDict], dict[str, dict], list[OrderedDict]]:
    if set(assignments) != set(natural_items):
        raise LLMError("atribuicoes de reconciliacao nao cobrem os grupos naturais")
    target_by_id = {item["id"]: item for item in targets}
    merge_audits = merge_audits or {}
    owners: dict[str, list[str]] = defaultdict(list)
    for natural_name, assignment in assignments.items():
        destination = assignment.get("destino_id")
        if destination:
            if destination not in target_by_id:
                raise LLMError(
                    f"reconciliacao de {natural_name} usa destino inexistente"
                )
            owners[destination].append(natural_name)

    mandatory_normalized = {_norm(name) for name in mandatory_names}
    portfolio = []
    natural_results = {}
    report_by_natural = {}
    rejected_owners = []
    for target in targets:
        target_owners = owners.get(target["id"], [])
        mandatory = _norm(target["nome"]) in mandatory_normalized
        if not target_owners and not mandatory:
            continue
        if len(target_owners) > 1:
            audit = merge_audits.get(target["id"])
            if not audit:
                raise LLMError(
                    f"fusao de {target['nome']} nao possui auditoria"
                )
            if audit.get("decisao") == "rejeitar_fusao":
                rejected_owners.extend(
                    (natural_name, audit) for natural_name in target_owners
                )
                if not mandatory:
                    continue
                target_owners = []
        item = OrderedDict(target)
        if not target_owners:
            status = "obrigatorio"
            reason = "Categoria obrigatoria preservada sem grupo natural associado."
        elif len(target_owners) == 1:
            status = "manter_separado"
            reason = assignments[target_owners[0]]["justificativa"]
        else:
            status = "fundir"
            reason = " | ".join(
                assignments[name]["justificativa"] for name in target_owners
            )[:1200]
        item["status_reconciliacao"] = status
        item["justificativa_reconciliacao"] = reason
        item["substitui_categorias_atuais"] = []
        item["baseado_nos_grupos"] = []
        item["baseado_nos_outliers"] = []
        portfolio.append(item)
        for natural_name in target_owners:
            natural_results[natural_name] = {
                "grupo_natural": natural_name,
                "destino_id": item["id"],
                "justificativa": assignments[natural_name]["justificativa"],
            }
            report_by_natural[natural_name] = {
                "grupo_natural": natural_name,
                "decisao_llm": assignments[natural_name]["decisao"],
                "decisao_final": status,
                "destino_id": item["id"],
                "destino_nome": item["nome"],
                "criterios": assignments[natural_name]["criterios"],
                "justificativa": assignments[natural_name]["justificativa"],
            }

    used_names = {_norm(item["nome"]) for item in portfolio}
    used_ids = {item["id"] for item in portfolio}
    for natural_name, audit in rejected_owners:
        item = OrderedDict(natural_items[natural_name])
        if _norm(item["nome"]) in used_names or item["id"] in used_ids:
            item["nome"] = f"{item['nome']} (mantido separado)"[:120]
            item["id"] = _category_id(item["grupo"], item["nome"])
        if _norm(item["nome"]) in used_names or item["id"] in used_ids:
            raise LLMError(
                f"nao foi possivel manter item unico para {natural_name}"
            )
        item["status_reconciliacao"] = "manter_separado"
        item["justificativa_reconciliacao"] = audit["justificativa"]
        item["substitui_categorias_atuais"] = []
        item["baseado_nos_grupos"] = []
        item["baseado_nos_outliers"] = []
        portfolio.append(item)
        used_names.add(_norm(item["nome"]))
        used_ids.add(item["id"])
        natural_results[natural_name] = {
            "grupo_natural": natural_name,
            "destino_id": item["id"],
            "justificativa": audit["justificativa"],
        }
        report_by_natural[natural_name] = {
            "grupo_natural": natural_name,
            "decisao_llm": assignments[natural_name]["decisao"],
            "decisao_final": "manter_separado",
            "destino_id": item["id"],
            "destino_nome": item["nome"],
            "criterios": audit["criterios"],
            "justificativa": audit["justificativa"],
        }
    for natural_name, assignment in assignments.items():
        if assignment["decisao"] != "dividir_para_revisao":
            continue
        item = OrderedDict(natural_items[natural_name])
        if _norm(item["nome"]) in used_names or item["id"] in used_ids:
            item["nome"] = f"{item['nome']} (revisar divisao)"[:120]
            item["id"] = _category_id(item["grupo"], item["nome"])
        if _norm(item["nome"]) in used_names or item["id"] in used_ids:
            raise LLMError(
                f"nao foi possivel criar item de revisao unico para {natural_name}"
            )
        item["status_reconciliacao"] = "dividir_para_revisao"
        item["justificativa_reconciliacao"] = assignment["justificativa"]
        item["substitui_categorias_atuais"] = []
        item["baseado_nos_grupos"] = []
        item["baseado_nos_outliers"] = []
        portfolio.append(item)
        used_names.add(_norm(item["nome"]))
        used_ids.add(item["id"])
        natural_results[natural_name] = {
            "grupo_natural": natural_name,
            "destino_id": item["id"],
            "justificativa": assignment["justificativa"],
        }
        report_by_natural[natural_name] = {
            "grupo_natural": natural_name,
            "decisao_llm": "dividir_para_revisao",
            "decisao_final": "dividir_para_revisao",
            "destino_id": item["id"],
            "destino_nome": item["nome"],
            "criterios": assignment["criterios"],
            "justificativa": assignment["justificativa"],
        }

    if set(natural_results) != set(natural_items):
        missing = sorted(set(natural_items) - set(natural_results))
        raise LLMError(
            "grupos naturais ausentes apos reconciliacao: " + ", ".join(missing)
        )
    report = [report_by_natural[name] for name in natural_items]
    return portfolio, natural_results, report


def _portfolio_text(portfolio: list[dict]) -> str:
    lines = []
    for item in portfolio:
        profile = item.get("perfil_operacional", {})
        lines.append(
            f"category_id={item['id']} | grupo={item['grupo']} | "
            f"chamado={item['nome']} | descricao={item['descricao']} | "
            f"objetivo={profile.get('objetivo_usuario', '')} | "
            f"servico_sistema={profile.get('servico_sistema_alvo', '')} | "
            f"tratamento={profile.get('acao_tratamento', '')} | "
            f"status={item.get('status_reconciliacao', '')}"
        )
    return "\n".join(lines)


def _load_partition_checkpoint(
    path: Path,
    key_field: str,
    expected_hashes: dict[str, str],
) -> dict[str, dict]:
    found = {}
    if not path.exists():
        return found
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
            key = str(row[key_field])
            if row.get("_input_hash") == expected_hashes.get(key):
                found[key] = row
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
    return found


def _stage5_workers() -> int:
    return max(
        1,
        int(os.getenv("STAGE5_WORKERS", os.getenv("PIPELINE_WORKERS", "2"))),
    )


def _run_partitioned_queue(
    *,
    stage_label: str,
    pending_keys: list[str],
    results: dict[str, dict],
    checkpoint_path: Path,
    key_field: str,
    input_hashes: dict[str, str],
    build_payload,
    progress_text: str,
    progress_every: int = 10,
) -> None:
    pending = [str(key) for key in pending_keys]
    if not pending:
        return

    workers = min(_stage5_workers(), len(pending))
    print(f"[{stage_label}] workers={workers}")
    lock = threading.Lock()
    errors: dict[str, str] = {}
    handle = open(checkpoint_path, "a", encoding="utf-8")

    def process(key: str) -> bool:
        try:
            payload = build_payload(key)
            if not isinstance(payload, dict):
                raise LLMError("resultado interno da tarefa nao e objeto")
            record = {
                key_field: key,
                **payload,
                "_input_hash": input_hashes[key],
            }
            with lock:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
                handle.flush()
                results[key] = record
                completed = len(results)
                if (
                    completed % progress_every == 0
                    or completed == len(input_hashes)
                ):
                    print(
                        f"   [{stage_label}] {completed}/{len(input_hashes)} "
                        f"{progress_text}"
                    )
            return True
        except LLMError as exc:
            with lock:
                errors[key] = str(exc)
            print(f"   [{stage_label}] ERRO {key}: {exc}")
            return False

    try:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(process, key) for key in pending]
            for future in as_completed(futures):
                future.result()
    finally:
        handle.close()

    missing = [
        key for key in input_hashes
        if key not in results
    ]
    if missing:
        examples = [
            f"{key}: {errors.get(key, 'sem resultado')}"
            for key in missing[:5]
        ]
        raise LLMError(
            f"{stage_label} terminou com {len(missing)} pendencia(s); "
            "reexecute para retomar. Ex.: " + " | ".join(examples)
        )


def _call_small_json(
    client,
    system: str,
    payload: dict,
    normalize,
    max_tokens: int = 500,
) -> dict:
    base_user = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    last_error = "resposta nao processada"
    for attempt in range(1, 4):
        user = base_user
        if attempt > 1:
            user += (
                "\n\nA resposta anterior foi invalida: " + last_error
                + "\nCorrija a resposta usando somente as opcoes fechadas."
            )
        try:
            return normalize(
                client.chat_json(
                    system,
                    user,
                    max_tokens=max_tokens,
                    timeout=900,
                )
            )
        except LLMError as exc:
            last_error = str(exc)
    raise LLMError("resposta invalida apos 3 tentativas: " + last_error)


def _normalize_category_decision(
    raw: dict,
    portfolio_by_id: dict[str, dict],
) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("mapeamento de categoria nao retornou objeto")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("mapeamento de categoria sem objeto de resultado")
    destination = _normalize_closed_destination(
        body.get("destino_id"),
        portfolio_by_id,
    )
    adherence = str(body.get("aderencia", "")).strip().lower()
    if adherence not in ADERENCIAS:
        raise LLMError(f"aderencia invalida: {adherence or '(vazio)'}")
    observation = str(body.get("observacao", "")).strip()
    if not observation:
        raise LLMError("observacao vazia no mapeamento de categoria")
    return OrderedDict([
        ("destino_id", destination),
        ("aderencia", adherence),
        ("observacao", observation[:500]),
    ])


def _normalize_outlier_decision(raw: dict, portfolio_by_id: dict[str, dict]) -> OrderedDict:
    if not isinstance(raw, dict):
        raise LLMError("avaliacao de candidato raro nao retornou objeto")
    body = raw.get("resultado", raw)
    if not isinstance(body, dict):
        raise LLMError("avaliacao de candidato raro sem objeto de resultado")
    decision = str(body.get("decisao", "")).strip().lower()
    if decision not in DECISOES_OUTLIER:
        raise LLMError(f"decisao de outlier invalida: {decision or '(vazio)'}")
    destination = body.get("destino_id")
    destination = str(destination).strip() if destination is not None else ""
    if destination.lower() in {"", "null", "none"}:
        destination = None
    if decision in {"incorporar_portfolio", "fundir_em_chamado"}:
        try:
            destination = _normalize_closed_destination(
                destination,
                portfolio_by_id,
            )
        except LLMError as exc:
            raise LLMError(
                f"decisao {decision} exige destino_id existente"
            ) from exc
    elif destination is not None:
        raise LLMError(f"decisao {decision} nao pode ter destino_id")
    reason = str(body.get("justificativa", "")).strip()
    if not reason:
        raise LLMError("justificativa vazia na avaliacao de candidato raro")
    return OrderedDict([
        ("decisao", decision),
        ("destino_id", destination),
        ("justificativa", reason[:700]),
    ])


def main():
    args = _parse_args()
    stage3_data = _load_json(PD / "03_clusters.json")
    labels_data = _load_json(PD / "04_labels.json")
    labels = labels_data.get("clusters", [])
    if not labels:
        raise SystemExit("ERRO: 04_labels.json sem clusters.")

    stage4_fingerprint = str(
        labels_data.get("metadata", {}).get("stage4_fingerprint", "")
    ).strip() or _hash_json(labels)
    if OUT.exists() and not args.force:
        existing = _load_json(OUT)
        metadata = existing.get("metadata", {})
        if (
            metadata.get("pipeline_version") == PIPELINE_VERSION
            and metadata.get("stage4_fingerprint") == stage4_fingerprint
        ):
            print(f"[Stage 5] {OUT.name} compativel ja existe; mantendo resultado.")
            return
        print(
            "[Stage 5] ERRO: o Stage 5 existente nao corresponde ao Stage 4 atual. "
            "Revise os artefatos e rode com --force para regenerar."
        )
        raise SystemExit(2)

    config = _load_json(config_path()) if config_path().exists() else {}
    catalog = _read_text(contexto_catalogo_path())
    stage3_tickets = stage3_data.get("tickets", [])
    outliers = stage3_data.get("outlier_stats", [])
    if not isinstance(stage3_tickets, list) or not isinstance(outliers, list):
        raise SystemExit("ERRO: 03_clusters.json tem tickets ou outlier_stats invalidos.")
    total_tickets = int(
        len(stage3_tickets)
        or labels_data.get("total_tickets", 0)
        or sum(int(item.get("total_tickets", 0) or 0) for item in labels)
    )
    categories = categorias_uteis(labels, stage3_tickets)
    mandatory_names = _mandatory_names(config)
    client = get_client()
    json_client = _get_json_client(client)
    meta = load_projeto_meta()
    portal_name = meta.get("portal_nome") or meta.get("nome") or "portal de atendimento"
    print(
        f"[Stage 5/{client.model_label}] categorias_uteis={len(categories)} "
        f"grupos_naturais={len(labels)} candidatos_raros={len(outliers)} "
        f"json={json_client.model_label}"
    )

    base_payload = _base_payload(
        config,
        catalog,
        labels,
        categories,
        total_tickets,
        portal_name,
    )
    base_fingerprint = _hash_json({
        "version": PIPELINE_VERSION,
        "stage4_fingerprint": stage4_fingerprint,
        "payload": base_payload,
        "decision_system": BASE_DECISION_SYSTEM,
        "json_system": BASE_JSON_SYSTEM,
        "semantic_model": client.model_label,
        "json_model": json_client.model_label,
    })
    safe_semantic = _safe_name(client.model_label)
    safe_json = _safe_name(json_client.model_label)
    base_cache = PD / (
        f"_ckpt_stage5_base__{safe_semantic}__json_{safe_json}"
        f"__b{base_fingerprint[:12]}.json"
    )
    base = None
    if base_cache.exists() and not args.force:
        try:
            cached = _load_json(base_cache)
            if (
                cached.get("pipeline_version") == PIPELINE_VERSION
                and cached.get("base_fingerprint") == base_fingerprint
                and isinstance(cached.get("base"), dict)
            ):
                base = _normalize_base(
                    {"recomendacao_base": cached["base"]}, mandatory_names
                )
                print(
                    f"[Stage 5a] rascunho-base em cache: "
                    f"{len(base['portfolio_otimizado'])} chamados"
                )
        except (OSError, ValueError, json.JSONDecodeError, LLMError):
            base = None
    if base is None:
        try:
            base, semantic_plan = _build_base(
                client, json_client, base_payload, mandatory_names
            )
        except LLMError as exc:
            print(f"[Stage 5a] ERRO: {exc}")
            print("[Stage 5] 05_portfolio_recommendation.json NAO foi gravado.")
            raise SystemExit(2) from exc
        with open(base_cache, "w", encoding="utf-8") as handle:
            json.dump({
                "pipeline_version": PIPELINE_VERSION,
                "base_fingerprint": base_fingerprint,
                "semantic_model": client.model_label,
                "json_model": json_client.model_label,
                "plano_semantico": semantic_plan,
                "base": base,
            }, handle, ensure_ascii=False, indent=2)
        print(
            f"[Stage 5a] rascunho-base: "
            f"{len(base['portfolio_otimizado'])} chamados"
        )

    draft_portfolio = list(base["portfolio_otimizado"])
    catalog_groups = _catalog_group_names(catalog)
    draft_groups = list(OrderedDict.fromkeys(
        str(item.get("grupo", "")).strip()
        for item in draft_portfolio
        if str(item.get("grupo", "")).strip()
    ))
    natural_request_payloads = {
        str(label["nome"]): {
            "nome_obrigatorio": str(label["nome"]),
            "grupo_natural": _public_cluster(label),
            "agrupadores_atuais": catalog_groups,
            "quantidade_agrupadores_atuais": len(catalog_groups),
            "agrupadores_sugeridos_no_rascunho": draft_groups,
            "politica_agrupadores_logicos": (
                "Prefira agrupadores atuais. Evite aumentar a quantidade de "
                "grupos logicos; separe diferencas finas no request type e no "
                "formulario inteligente."
            ),
            "contexto_portal": config.get("infra_context", {}).get(
                "texto_contexto", ""
            ),
        }
        for label in labels
    }
    natural_request_hashes = {
        name: _hash_json({
            "version": PIPELINE_VERSION,
            "model": client.model_label,
            "system": NATURAL_REQUEST_SYSTEM,
            "payload": payload,
        })
        for name, payload in natural_request_payloads.items()
    }
    natural_request_ckpt = PD / (
        f"_ckpt_stage5_requests__{safe_semantic}.jsonl"
    )
    natural_request_results = (
        {}
        if args.force
        else _load_partition_checkpoint(
            natural_request_ckpt,
            "grupo_natural",
            natural_request_hashes,
        )
    )
    pending_requests = [
        name for name in natural_request_payloads
        if name not in natural_request_results
    ]
    labels_by_name = {
        str(label["nome"]): label for label in labels
    }
    print(
        f"[Stage 5a.1] request_types_naturais={len(natural_request_payloads)} "
        f"feitos={len(natural_request_results)} "
        f"pendentes={len(pending_requests)}"
    )
    try:
        _run_partitioned_queue(
            stage_label="Stage 5a.1",
            pending_keys=pending_requests,
            results=natural_request_results,
            checkpoint_path=natural_request_ckpt,
            key_field="grupo_natural",
            input_hashes=natural_request_hashes,
            build_payload=lambda name: {
                "item": _call_small_json(
                    client,
                    NATURAL_REQUEST_SYSTEM,
                    natural_request_payloads[name],
                    lambda raw: _normalize_natural_request(
                        raw,
                        labels_by_name[name],
                    ),
                    max_tokens=1200,
                ),
            },
            progress_text="request types criados",
        )
    except LLMError as exc:
        print(f"[Stage 5a.1] ERRO: {exc}")
        raise SystemExit(2) from exc

    natural_items = OrderedDict(
        (
            str(label["nome"]),
            natural_request_results[str(label["nome"])]["item"],
        )
        for label in labels
    )
    catalog_items = _catalog_items(catalog)
    reconciliation_payload = OrderedDict([
        (
            "objetivo",
            "Reconciliar candidatos naturais em request types operacionais "
            "sem meta numerica e sem perda de diferencas de tratamento.",
        ),
        (
            "criterio_de_decisao",
            "Manter separados servicos com objetivo, sistema, acao, fluxo, "
            "equipe, formulario, aprovacao, SLA ou seguranca diferentes.",
        ),
        (
            "contexto_portal",
            config.get("infra_context", {}).get("texto_contexto", ""),
        ),
        ("agrupadores_atuais", catalog_groups),
        ("quantidade_agrupadores_atuais", len(catalog_groups)),
        (
            "politica_agrupadores_logicos",
            "O catalogo atual define a referencia de quantidade de grupos "
            "logicos. Aumentar esse numero deve ser excecao justificada. "
            "Diferencas operacionais devem ser preservadas como request types "
            "distintos dentro de grupos logicos compartilhados quando possivel.",
        ),
        ("catalogo_atual", catalog_items),
        ("categorias_atuais_agregadas", categories),
        ("categorias_obrigatorias", config.get("categorias_obrigatorias", [])),
        (
            "candidatos_naturais",
            [
                _reconciliation_candidate(
                    natural_items[str(label["nome"])],
                    label,
                )
                for label in labels
            ],
        ),
    ])
    reconciliation_fingerprint = _hash_json({
        "version": PIPELINE_VERSION,
        "compiler_version": RECONCILIATION_COMPILER_VERSION,
        "stage4_fingerprint": stage4_fingerprint,
        "semantic_model": client.model_label,
        "json_model": json_client.model_label,
        "decision_system": RECONCILIATION_DECISION_SYSTEM,
        "json_system": RECONCILIATION_JSON_SYSTEM,
        "payload": reconciliation_payload,
    })
    reconciliation_cache = PD / (
        f"_ckpt_stage5_reconcile_plan__{safe_semantic}"
        f"__json_{safe_json}__r{reconciliation_fingerprint[:12]}.json"
    )
    reconciliation_compile_ckpt = PD / (
        f"_ckpt_stage5_reconcile_compile__{safe_json}"
        f"__r{reconciliation_fingerprint[:12]}.jsonl"
    )
    reconciliation_targets = None
    reconciliation_plan = None
    if reconciliation_cache.exists() and not args.force:
        try:
            cached = _load_json(reconciliation_cache)
            cached_targets = cached.get("portfolio_reconciliado")
            if (
                cached.get("pipeline_version") == PIPELINE_VERSION
                and cached.get("reconciliation_fingerprint")
                == reconciliation_fingerprint
            ):
                cached_plan = cached.get("plano_semantico")
                if isinstance(cached_plan, str):
                    _validate_reconciliation_plan(
                        cached_plan,
                        mandatory_names,
                    )
                    reconciliation_plan = cached_plan
                if isinstance(cached_targets, list):
                    reconciliation_targets = _normalize_reconciled_portfolio(
                        {"portfolio_reconciliado": cached_targets},
                        mandatory_names,
                        len(cached_targets),
                    )
                    print(
                        f"[Stage 5a.2] plano reconciliado em cache: "
                        f"{len(reconciliation_targets)} destinos"
                    )
        except (OSError, ValueError, json.JSONDecodeError, LLMError):
            reconciliation_targets = None
            reconciliation_plan = None
    if reconciliation_targets is None:
        try:
            if reconciliation_plan is None:
                reconciliation_plan = _build_reconciliation_plan(
                    client,
                    reconciliation_payload,
                    mandatory_names,
                )
                with open(reconciliation_cache, "w", encoding="utf-8") as handle:
                    json.dump({
                        "pipeline_version": PIPELINE_VERSION,
                        "compiler_version": RECONCILIATION_COMPILER_VERSION,
                        "reconciliation_fingerprint": reconciliation_fingerprint,
                        "semantic_model": client.model_label,
                        "json_model": json_client.model_label,
                        "plano_semantico": reconciliation_plan,
                    }, handle, ensure_ascii=False, indent=2)
                print(
                    f"[Stage 5a.2] plano semantico preservado: "
                    f"{_validate_reconciliation_plan(reconciliation_plan, mandatory_names)} "
                    "blocos"
                )
            reconciliation_targets = _compile_reconciliation_plan(
                json_client,
                reconciliation_plan,
                mandatory_names,
                reconciliation_compile_ckpt,
                reconciliation_fingerprint,
                force=args.force,
            )
        except LLMError as exc:
            print(f"[Stage 5a.2] ERRO: {exc}")
            print("[Stage 5] 05_portfolio_recommendation.json NAO foi gravado.")
            raise SystemExit(2) from exc
        with open(reconciliation_cache, "w", encoding="utf-8") as handle:
            json.dump({
                "pipeline_version": PIPELINE_VERSION,
                "compiler_version": RECONCILIATION_COMPILER_VERSION,
                "reconciliation_fingerprint": reconciliation_fingerprint,
                "semantic_model": client.model_label,
                "json_model": json_client.model_label,
                "plano_semantico": reconciliation_plan,
                "portfolio_reconciliado": reconciliation_targets,
            }, handle, ensure_ascii=False, indent=2)
        print(
            f"[Stage 5a.2] plano reconciliado: "
            f"{len(reconciliation_targets)} destinos"
        )

    reconciliation_by_id = {
        item["id"]: item for item in reconciliation_targets
    }
    if len(reconciliation_by_id) != len(reconciliation_targets):
        raise SystemExit("ERRO: plano reconciliado contem category_id duplicado.")
    reconciliation_text = _reconciliation_portfolio_text(
        reconciliation_targets
    )
    catalog_by_name = {
        _norm(item["nome"]): item for item in catalog_items
    }
    reconciliation_assignment_payloads = {}
    for label in labels:
        name = str(label["nome"])
        related_catalog = []
        for category in label.get("distribuicao_categorias_atuais", {}):
            item = catalog_by_name.get(_norm(str(category)))
            if item and item not in related_catalog:
                related_catalog.append(item)
        reconciliation_assignment_payloads[name] = {
            "candidato_natural": _reconciliation_candidate(
                natural_items[name],
                label,
            ),
            "catalogo_atual_relacionado": related_catalog,
            "contexto_portal": config.get("infra_context", {}).get(
                "texto_contexto", ""
            ),
            "portfolio_reconciliado_fechado": reconciliation_text,
        }
    reconciliation_assignment_hashes = {
        name: _hash_json({
            "version": PIPELINE_VERSION,
            "reconciliation_fingerprint": reconciliation_fingerprint,
            "model": client.model_label,
            "system": RECONCILIATION_ASSIGN_SYSTEM,
            "payload": payload,
        })
        for name, payload in reconciliation_assignment_payloads.items()
    }
    reconciliation_assignment_ckpt = PD / (
        f"_ckpt_stage5_reconcile_assign__{safe_semantic}"
        f"__r{reconciliation_fingerprint[:12]}.jsonl"
    )
    reconciliation_assignment_results = (
        {}
        if args.force
        else _load_partition_checkpoint(
            reconciliation_assignment_ckpt,
            "grupo_natural",
            reconciliation_assignment_hashes,
        )
    )
    pending_reconciliation = [
        name for name in natural_items
        if name not in reconciliation_assignment_results
    ]
    print(
        f"[Stage 5a.3] grupos_naturais={len(natural_items)} "
        f"feitos={len(reconciliation_assignment_results)} "
        f"pendentes={len(pending_reconciliation)}"
    )
    try:
        _run_partitioned_queue(
            stage_label="Stage 5a.3",
            pending_keys=pending_reconciliation,
            results=reconciliation_assignment_results,
            checkpoint_path=reconciliation_assignment_ckpt,
            key_field="grupo_natural",
            input_hashes=reconciliation_assignment_hashes,
            build_payload=lambda name: _call_small_json(
                client,
                RECONCILIATION_ASSIGN_SYSTEM,
                reconciliation_assignment_payloads[name],
                lambda raw: _normalize_reconciliation_assignment(
                    raw,
                    reconciliation_by_id,
                ),
                max_tokens=900,
            ),
            progress_text="grupos reconciliados",
        )
    except LLMError as exc:
        print(f"[Stage 5a.3] ERRO: {exc}")
        raise SystemExit(2) from exc
    preliminary_owners: dict[str, list[str]] = defaultdict(list)
    for name, result in reconciliation_assignment_results.items():
        if result.get("destino_id"):
            preliminary_owners[result["destino_id"]].append(name)
    merge_audit_payloads = {}
    for destination, owner_names in preliminary_owners.items():
        if len(owner_names) < 2:
            continue
        merge_audit_payloads[destination] = {
            "destino_proposto": reconciliation_by_id[destination],
            "candidatos_que_seriam_fundidos": [
                _reconciliation_candidate(
                    natural_items[name],
                    labels_by_name[name],
                )
                for name in owner_names
            ],
            "catalogo_atual": catalog_items,
            "contexto_portal": config.get("infra_context", {}).get(
                "texto_contexto", ""
            ),
        }
    merge_audit_hashes = {
        destination: _hash_json({
            "version": PIPELINE_VERSION,
            "reconciliation_fingerprint": reconciliation_fingerprint,
            "model": client.model_label,
            "system": MERGE_AUDIT_SYSTEM,
            "payload": payload,
        })
        for destination, payload in merge_audit_payloads.items()
    }
    merge_audit_ckpt = PD / (
        f"_ckpt_stage5_merge_audit__{safe_semantic}"
        f"__r{reconciliation_fingerprint[:12]}.jsonl"
    )
    merge_audit_results = (
        {}
        if args.force
        else _load_partition_checkpoint(
            merge_audit_ckpt,
            "destino_id",
            merge_audit_hashes,
        )
    )
    pending_merge_audits = [
        destination for destination in merge_audit_payloads
        if destination not in merge_audit_results
    ]
    print(
        f"[Stage 5a.4] fusoes_propostas={len(merge_audit_payloads)} "
        f"auditadas={len(merge_audit_results)} "
        f"pendentes={len(pending_merge_audits)}"
    )
    try:
        _run_partitioned_queue(
            stage_label="Stage 5a.4",
            pending_keys=pending_merge_audits,
            results=merge_audit_results,
            checkpoint_path=merge_audit_ckpt,
            key_field="destino_id",
            input_hashes=merge_audit_hashes,
            build_payload=lambda destination: _call_small_json(
                client,
                MERGE_AUDIT_SYSTEM,
                merge_audit_payloads[destination],
                _normalize_merge_audit,
                max_tokens=900,
            ),
            progress_text="fusoes auditadas",
        )
    except LLMError as exc:
        print(f"[Stage 5a.4] ERRO: {exc}")
        raise SystemExit(2) from exc
    try:
        portfolio_reconciled, natural_results, reconciliation_report = (
            _assemble_reconciled_portfolio(
                reconciliation_targets,
                reconciliation_assignment_results,
                natural_items,
                mandatory_names,
                merge_audit_results,
            )
        )
    except LLMError as exc:
        print(f"[Stage 5a.5] ERRO na reconciliacao: {exc}")
        raise SystemExit(2) from exc
    base["portfolio_otimizado"] = portfolio_reconciled
    status_counts = Counter(
        item["status_reconciliacao"] for item in portfolio_reconciled
    )
    print(
        f"[Stage 5a.5] portfolio operacional: "
        f"{len(portfolio_reconciled)} chamados; "
        f"mantidos={status_counts['manter_separado']} "
        f"fundidos={status_counts['fundir']} "
        f"dividir_para_revisao={status_counts['dividir_para_revisao']} "
        f"obrigatorios={status_counts['obrigatorio']}"
    )
    reports_by_destination: dict[str, list[dict]] = defaultdict(list)
    for report_item in reconciliation_report:
        reports_by_destination[report_item["destino_id"]].append(report_item)
    reconciliation_decisions = []
    for item in portfolio_reconciled:
        source_reports = reports_by_destination.get(item["id"], [])
        reconciliation_decisions.append(OrderedDict([
            ("decisao", item["status_reconciliacao"]),
            (
                "origem",
                [source["grupo_natural"] for source in source_reports]
                or ["categoria obrigatoria"],
            ),
            ("destino", item["nome"]),
            ("grupo_logico", item["grupo"]),
            ("justificativa", item["justificativa_reconciliacao"]),
        ]))
    revision = base["revisao_contexto_catalogo"]
    revision["principio"] = (
        "Candidatos naturais preservados e reconciliados por equivalencia "
        "operacional contra contexto e catalogo atual. A quantidade de "
        "agrupadores atuais e referencia forte; novos grupos logicos devem ser "
        "excecao justificada."
    )
    revision["decisoes_de_agrupamento"] = reconciliation_decisions
    review_names = [
        item["nome"] for item in portfolio_reconciled
        if item["status_reconciliacao"] == "dividir_para_revisao"
    ]
    revision["ajustes_pos_revisao"] = (
        [
            "Revisar divisao interna antes de publicar: "
            + ", ".join(review_names)
        ]
        if review_names else
        ["Nenhum candidato exigiu divisao interna nesta execucao."]
    )
    base["analise_geral"] = (
        f"Foram avaliados {len(labels)} grupos naturais contra o contexto da "
        f"area e o catalogo atual. A reconciliacao produziu "
        f"{len(portfolio_reconciled)} request types: "
        f"{status_counts['manter_separado']} mantidos separadamente, "
        f"{status_counts['fundir']} destinos com fusao, "
        f"{status_counts['dividir_para_revisao']} candidatos que exigem "
        f"divisao e revisao e {status_counts['obrigatorio']} categorias "
        "obrigatorias sem grupo natural."
    )

    portfolio_base_fingerprint = _hash_json(base["portfolio_otimizado"])
    portfolio = json.loads(json.dumps(base["portfolio_otimizado"], ensure_ascii=False))
    portfolio_by_id = {item["id"]: item for item in portfolio}
    if len(portfolio_by_id) != len(portfolio):
        raise SystemExit("ERRO: portfolio-base contem category_id duplicado.")
    portfolio_text = _portfolio_text(portfolio)
    category_payloads = {}
    for category, volume in categories.items():
        candidates = []
        for label in labels:
            count = int(
                label.get("distribuicao_categorias_atuais", {}).get(category, 0) or 0
            )
            if count:
                candidates.append({
                    "nome": label.get("nome"),
                    "total_desta_categoria": count,
                    "descricao": label.get("descricao"),
                    "quando_usar": label.get("quando_usar"),
                })
        category_payloads[category] = {
            "categoria_atual": category,
            "volume": int(volume),
            "grupos_naturais_observados": candidates,
            "portfolio_fechado": portfolio_text,
        }
    category_hashes = {
        category: _hash_json({
            "version": PIPELINE_VERSION,
            "category_mapping_version": CATEGORY_MAPPING_VERSION,
            "portfolio_base_fingerprint": portfolio_base_fingerprint,
            "model": client.model_label,
            "system": CATEGORY_MAPPING_SYSTEM,
            "payload": payload,
        })
        for category, payload in category_payloads.items()
    }
    category_ckpt = PD / (
        f"_ckpt_stage5_categories__{safe_semantic}"
        f"__b{portfolio_base_fingerprint[:12]}.jsonl"
    )
    category_results = (
        {}
        if args.force
        else _load_partition_checkpoint(
            category_ckpt, "categoria_atual", category_hashes
        )
    )
    pending_categories = [item for item in categories if item not in category_results]
    print(
        f"[Stage 5b] categorias={len(categories)} feitos={len(category_results)} "
        f"pendentes={len(pending_categories)}"
    )
    try:
        _run_partitioned_queue(
            stage_label="Stage 5b",
            pending_keys=pending_categories,
            results=category_results,
            checkpoint_path=category_ckpt,
            key_field="categoria_atual",
            input_hashes=category_hashes,
            build_payload=lambda category: _call_small_json(
                client,
                CATEGORY_MAPPING_SYSTEM,
                category_payloads[category],
                lambda raw: _normalize_category_decision(
                    raw,
                    portfolio_by_id,
                ),
            ),
            progress_text="categorias mapeadas",
        )
    except LLMError as exc:
        print(f"[Stage 5b] ERRO: {exc}")
        raise SystemExit(2) from exc

    print(
        f"[Stage 5c] grupos_naturais={len(natural_results)} "
        "vinculados_apos_reconciliacao="
        f"{len(natural_results)}"
    )

    outlier_payloads = {}
    for outlier in outliers:
        outlier_id = str(outlier.get("outlier_id", "")).strip()
        if not outlier_id or outlier_id in outlier_payloads:
            raise SystemExit(
                f"ERRO: candidato raro sem outlier_id unico: {outlier_id or '(vazio)'}"
            )
        outlier_payloads[outlier_id] = {
            "candidato_raro": _public_outlier(outlier),
            "portfolio_fechado": portfolio_text,
        }
    outlier_hashes = {
        outlier_id: _hash_json({
            "version": PIPELINE_VERSION,
            "portfolio_base_fingerprint": portfolio_base_fingerprint,
            "model": client.model_label,
            "system": OUTLIER_MAPPING_SYSTEM,
            "payload": payload,
        })
        for outlier_id, payload in outlier_payloads.items()
    }
    outlier_ckpt = PD / (
        f"_ckpt_stage5_outliers__{safe_semantic}"
        f"__b{portfolio_base_fingerprint[:12]}.jsonl"
    )
    outlier_results = (
        {}
        if args.force
        else _load_partition_checkpoint(
            outlier_ckpt, "outlier_id", outlier_hashes
        )
    )
    technical_outliers = {
        outlier_id for outlier_id, payload in outlier_payloads.items()
        if payload["candidato_raro"].get("tipo_registro")
        == "agrupador_tecnico_residual"
        or payload["candidato_raro"].get("publicavel_no_portfolio") is False
    }
    with open(outlier_ckpt, "a", encoding="utf-8") as handle:
        for outlier_id in sorted(technical_outliers):
            if outlier_id in outlier_results:
                continue
            record = {
                "outlier_id": outlier_id,
                "decisao": "manter_revisao",
                "destino_id": None,
                "justificativa": (
                    "Agrupador tecnico residual para auditoria; nao representa "
                    "um servico publicavel do catalogo."
                ),
                "_input_hash": outlier_hashes[outlier_id],
            }
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
            handle.flush()
            outlier_results[outlier_id] = record
    pending_outliers = [
        outlier_id for outlier_id in outlier_payloads
        if outlier_id not in outlier_results
    ]
    print(
        f"[Stage 5d] candidatos_raros={len(outlier_payloads)} "
        f"feitos={len(outlier_results)} pendentes={len(pending_outliers)}"
    )
    try:
        _run_partitioned_queue(
            stage_label="Stage 5d",
            pending_keys=pending_outliers,
            results=outlier_results,
            checkpoint_path=outlier_ckpt,
            key_field="outlier_id",
            input_hashes=outlier_hashes,
            build_payload=lambda outlier_id: _call_small_json(
                client,
                OUTLIER_MAPPING_SYSTEM,
                outlier_payloads[outlier_id],
                lambda raw: _normalize_outlier_decision(
                    raw,
                    portfolio_by_id,
                ),
            ),
            progress_text="candidatos avaliados",
            progress_every=25,
        )
    except LLMError as exc:
        print(f"[Stage 5d] ERRO: {exc}")
        raise SystemExit(2) from exc

    for category in categories:
        destination = category_results[category]["destino_id"]
        portfolio_by_id[destination]["substitui_categorias_atuais"].append(category)
    for natural in natural_request_payloads:
        destination = natural_results[natural]["destino_id"]
        portfolio_by_id[destination]["baseado_nos_grupos"].append(natural)

    outlier_evaluation = []
    for outlier_id in outlier_payloads:
        decision = outlier_results[outlier_id]
        destination_id = decision.get("destino_id")
        destination_name = None
        if destination_id:
            portfolio_by_id[destination_id]["baseado_nos_outliers"].append(outlier_id)
            destination_name = portfolio_by_id[destination_id]["nome"]
        outlier_evaluation.append(OrderedDict([
            ("outlier_id", outlier_id),
            ("decisao", decision["decisao"]),
            ("destino_portfolio", destination_name),
            ("justificativa", decision["justificativa"]),
        ]))

    items_by_group: OrderedDict[str, list[dict]] = OrderedDict()
    for item in portfolio:
        items_by_group.setdefault(item["grupo"], []).append(item)
    raw_groups = [
        OrderedDict([
            ("nome", group),
            (
                "descricao",
                "Agrupador logico dos chamados: "
                + ", ".join(item["nome"] for item in items),
            ),
            ("chamados", [item["nome"] for item in items]),
        ])
        for group, items in items_by_group.items()
    ]
    raw_mapping = [
        OrderedDict([
            ("categoria_atual", category),
            ("destino_id", category_results[category]["destino_id"]),
            ("aderencia", category_results[category]["aderencia"]),
            ("observacao", category_results[category]["observacao"]),
        ])
        for category in categories
    ]
    assembled = {
        "recomendacao": {
            "analise_geral": base["analise_geral"],
            "problemas_encontrados": base["problemas_encontrados"],
            "mapeamento_atual_vs_natural": raw_mapping,
            "reconciliacao_grupos_naturais": reconciliation_report,
            "revisao_contexto_catalogo": base["revisao_contexto_catalogo"],
            "grupos_otimizados": raw_groups,
            "portfolio_otimizado": portfolio,
            "avaliacao_outliers_stage3": outlier_evaluation,
            "acoes_prioritarias": base["acoes_prioritarias"],
            "impacto_estimado": base["impacto_estimado"],
        }
    }
    try:
        recommendation = normalizar(
            assembled,
            labels,
            categories,
            total_tickets,
            mandatory_names,
            outliers,
        )
    except LLMError as exc:
        print(f"[Stage 5e] ERRO na montagem deterministica: {exc}")
        print("[Stage 5] 05_portfolio_recommendation.json NAO foi gravado.")
        raise SystemExit(2) from exc

    portfolio_fingerprint = _hash_json({
        "pipeline_version": PIPELINE_VERSION,
        "base_input_fingerprint": base_fingerprint,
        "base_fingerprint": portfolio_base_fingerprint,
        "portfolio": [
            {
                "id": item["id"],
                "nome": item["nome"],
                "grupo": item["grupo"],
                "descricao": item["descricao"],
                "perfil_operacional": item["perfil_operacional"],
                "status_reconciliacao": item["status_reconciliacao"],
                "substitui_categorias_atuais": item["substitui_categorias_atuais"],
                "baseado_nos_grupos": item["baseado_nos_grupos"],
                "baseado_nos_outliers": item["baseado_nos_outliers"],
            }
            for item in recommendation["portfolio_otimizado"]
        ],
        "reconciliacao_grupos_naturais": (
            recommendation["reconciliacao_grupos_naturais"]
        ),
        "avaliacao_outliers_stage3": recommendation["avaliacao_outliers_stage3"],
    })
    output = OrderedDict([
        ("metadata", OrderedDict([
            ("pipeline_version", PIPELINE_VERSION),
            ("category_mapping_version", CATEGORY_MAPPING_VERSION),
            ("stage4_fingerprint", stage4_fingerprint),
            ("base_input_fingerprint", base_fingerprint),
            ("base_fingerprint", portfolio_base_fingerprint),
            ("portfolio_fingerprint", portfolio_fingerprint),
            (
                "metodo",
                "candidatos_naturais_e_reconciliacao_operacional",
            ),
            ("modelo_semantico", client.model_label),
            ("modelo_compilador_json", json_client.model_label),
            ("total_tickets", total_tickets),
            ("n_categorias_atuais", len(categories)),
            ("n_grupos_naturais", len(labels)),
            ("n_destinos_propostos_reconciliacao", len(reconciliation_targets)),
            (
                "n_request_types_reconciliados",
                len(recommendation["portfolio_otimizado"]),
            ),
            (
                "n_grupos_para_divisao",
                sum(
                    item.get("status_reconciliacao")
                    == "dividir_para_revisao"
                    for item in recommendation["portfolio_otimizado"]
                ),
            ),
            ("n_outliers_stage3", len(outliers)),
        ])),
        ("categorias_atuais", categories),
        ("grupos_naturais", [_public_cluster(item) for item in labels]),
        ("outliers_stage3", [_public_outlier(item) for item in outliers]),
        ("recomendacao", recommendation),
    ])
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2)
    print(
        f"[Stage 5] OK: {OUT} "
        f"({len(recommendation['portfolio_otimizado'])} chamados em "
        f"{len(recommendation['grupos_otimizados'])} grupos)"
    )


if __name__ == "__main__":
    main()
