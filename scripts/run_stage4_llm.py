#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 4 via LLM (rotulagem dos grupos naturais) - roda no HPC.

Le pipeline_data/03_clusters.json, chama a LLM para cada grupo natural e grava
pipeline_data/04_labels.json no contrato esperado pelo dashboard.

Resumivel por checkpoint de modelo:
  pipeline_data/_ckpt_stage4__<modelo>.jsonl

Uso: python scripts/run_stage4_llm.py
"""
import hashlib
import json
import sys
import unicodedata
from collections import OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from projeto import config_path, contexto_catalogo_path, pipeline_data_dir, load_projeto_meta
from llm_client import LLMError, get_client

PD = pipeline_data_dir()
OUT = PD / "04_labels.json"
STAGE4_VERSION = "label-per-cluster-v2"

COMPLEXIDADES = {"baixa", "media", "alta"}


SYSTEM = """Voce e especialista senior em ITSM para o portal {portal_nome}.
Sua tarefa e rotular UM grupo natural de chamados descoberto no Stage 3.

Use o contexto do portal, as categorias obrigatorias se existirem, e o catalogo
atual do Jira para criar um rotulo claro, orientado ao usuario, sem duplicar
nomes do catalogo quando uma consolidacao for melhor.

Responda SOMENTE JSON com estes campos:
{
  "nome": "nome da categoria, maximo 5 palavras",
  "descricao": "1 a 2 frases objetivas",
  "quando_usar": "criterio claro de pertencimento",
  "informacoes_necessarias": ["campo 1", "campo 2", "campo 3"],
  "sla_sugerido": "prazo tipico",
  "complexidade": "baixa|media|alta"
}

Regras:
- Nao use travessao nos textos.
- Nao crie categoria generica de diversos se o grupo tiver significado claro.
- Preserve no nome a identidade do servico ou sistema quando ela distinguir o
  fluxo. Nao transforme acessos a sistemas independentes em um unico rotulo de
  acesso generico.
- Campos obrigatorios devem ser especificos do servico deste portal, nao genericos."""


def _load_json(path: Path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig")


def _as_list(value, limit: int = 6) -> list[str]:
    if isinstance(value, list):
        items = value
    elif value:
        items = [value]
    else:
        items = []
    return [str(v).strip() for v in items if str(v).strip()][:limit]


def _norm(value: str) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return " ".join(text.casefold().split())


def _normalizar_label(res: dict, stat: dict, total_tickets: int) -> OrderedDict:
    if not isinstance(res, dict):
        raise LLMError(f"Stage 4 retornou resposta nao objeto para cluster {stat.get('cluster_id')}")
    nome = str(res.get("nome", "")).strip()
    if not nome:
        raise LLMError(f"Stage 4 sem nome para cluster {stat.get('cluster_id')}")

    descricao = str(res.get("descricao", "")).strip()
    quando_usar = str(res.get("quando_usar", "")).strip()
    informacoes = _as_list(res.get("informacoes_necessarias"))
    sla = str(res.get("sla_sugerido", "")).strip()
    if not descricao or not quando_usar or not informacoes or not sla:
        raise LLMError(
            f"Stage 4 com campos obrigatorios vazios para cluster {stat.get('cluster_id')}"
        )

    complexidade = str(res.get("complexidade", "")).strip().lower()
    if complexidade not in COMPLEXIDADES:
        raise LLMError(f"complexidade invalida no cluster {stat.get('cluster_id')}: {complexidade}")

    total = int(stat.get("total", 0) or 0)
    percentual = round(total / max(total_tickets, 1) * 100, 1)

    return OrderedDict([
        ("cluster_id", int(stat["cluster_id"])),
        ("nome", nome[:90]),
        ("descricao", descricao[:700]),
        ("quando_usar", quando_usar[:700]),
        ("informacoes_necessarias", informacoes),
        ("sla_sugerido", sla[:80]),
        ("complexidade", complexidade),
        ("total_tickets", total),
        ("volume_percentual", percentual),
        ("distribuicao_categorias_atuais", stat.get("distribuicao_categorias_atuais", {})),
        ("rotulo_gerado_por_fallback", False),
    ])


def carregar_ckpt(ckpt: Path) -> dict[int, dict]:
    feitos = {}
    if not ckpt.exists():
        return feitos
    for ln in ckpt.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
            feitos[int(obj["cluster_id"])] = obj
        except Exception:
            pass
    return feitos


def montar_user(stat: dict, definicao: dict | None, contexto: str,
                categorias_obrigatorias: list, catalogo: str,
                correction: str = "", nomes_usados: list[str] | None = None) -> str:
    payload = OrderedDict([
        ("contexto_portal", contexto),
        ("categorias_obrigatorias", categorias_obrigatorias),
        ("catalogo_atual", catalogo),
        ("grupo_stage3", OrderedDict([
            ("cluster_id", stat.get("cluster_id")),
            ("total", stat.get("total")),
            ("keywords", stat.get("keywords", [])),
            ("sample_intencoes", stat.get("sample_intencoes", [])),
            ("distribuicao_categorias_atuais", stat.get("distribuicao_categorias_atuais", {})),
            ("distribuicao_tipos_pedido", stat.get("distribuicao_tipos_pedido", {})),
            ("definicao_inicial", definicao or {}),
        ])),
        ("nomes_ja_usados", nomes_usados or []),
    ])
    text = json.dumps(payload, ensure_ascii=False)
    if correction:
        text += (
            "\n\nA resposta anterior foi invalida: " + correction
            + "\nCorrija somente este rotulo e preencha todos os campos obrigatorios."
        )
    return text


def main():
    clusters = _load_json(PD / "03_clusters.json")
    stats = clusters.get("cluster_stats", [])
    if not stats:
        raise SystemExit("ERRO: 03_clusters.json sem cluster_stats.")

    config = _load_json(config_path()) if config_path().exists() else {}
    contexto = config.get("infra_context", {}).get("texto_contexto", "")
    categorias_obrigatorias = config.get("categorias_obrigatorias", [])
    catalogo = _read_text(contexto_catalogo_path())
    total_tickets = len(clusters.get("tickets", [])) or (
        sum(int(s.get("total", 0) or 0) for s in stats)
        + sum(int(s.get("total", 0) or 0) for s in clusters.get("outlier_stats", []))
    )
    meta = load_projeto_meta()
    portal_nome = meta.get("portal_nome") or meta.get("nome") or "portal de atendimento"

    clustering_fingerprint = str(
        clusters.get("metadata", {}).get("clustering_fingerprint", "")
    ).strip()
    if not clustering_fingerprint:
        payload = [
            (item.get("chave"), item.get("cluster_id"))
            for item in clusters.get("tickets", [])
        ]
        clustering_fingerprint = hashlib.sha256(
            json.dumps(payload, ensure_ascii=False).encode("utf-8")
        ).hexdigest()
    client = get_client()
    safe = client.model_label.replace(":", "_").replace("/", "_")
    definicoes = {
        int(d.get("cluster_id")): d
        for d in clusters.get("_definicoes", [])
        if "cluster_id" in d
    }
    # Stats e definições entram no prompt. Incluí-los no fingerprint impede
    # reaproveitar checkpoint após normalizar a interface do Stage 3.
    label_input_fingerprint = hashlib.sha256(json.dumps({
        "version": STAGE4_VERSION,
        "clustering_fingerprint": clustering_fingerprint,
        "cluster_stats": stats,
        "definicoes": list(definicoes.values()),
        "contexto": contexto,
        "categorias_obrigatorias": categorias_obrigatorias,
        "catalogo": catalogo,
        "system": SYSTEM,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    ckpt = PD / f"_ckpt_stage4__{safe}__l{label_input_fingerprint[:12]}.jsonl"
    feitos = carregar_ckpt(ckpt)

    print(f"[Stage 4/{client.model_label}] grupos={len(stats)} feitos={len(feitos)} checkpoint={ckpt.name}")

    used_names = {}
    for cid, label in feitos.items():
        normalized = _norm(str(label.get("nome", "")))
        if not normalized or normalized in used_names:
            raise SystemExit(
                "ERRO: checkpoint do Stage 4 contem nome vazio ou duplicado; "
                "arquive o checkpoint e reexecute."
            )
        used_names[normalized] = cid

    with open(ckpt, "a", encoding="utf-8") as ck:
        for stat in stats:
            cid = int(stat["cluster_id"])
            if cid in feitos:
                continue
            label = None
            last_error = "resposta nao processada"
            for attempt in range(1, 4):
                user = montar_user(
                    stat,
                    definicoes.get(cid),
                    contexto,
                    categorias_obrigatorias,
                    catalogo,
                    last_error if attempt > 1 else "",
                    [item["nome"] for item in feitos.values()],
                )
                try:
                    res = client.chat_json(
                        SYSTEM.replace("{portal_nome}", portal_nome),
                        user,
                        max_tokens=900,
                        timeout=900,
                    )
                    candidate = _normalizar_label(res, stat, total_tickets)
                    normalized = _norm(candidate["nome"])
                    if normalized in used_names:
                        raise LLMError(
                            f"nome duplicado com cluster {used_names[normalized]}: "
                            f"{candidate['nome']}"
                        )
                    label = candidate
                    break
                except LLMError as exc:
                    last_error = str(exc)
                    print(
                        f"[Stage 4] cluster {cid} tentativa {attempt}/3 invalida: "
                        f"{last_error}"
                    )
            if label is None:
                print(f"[Stage 4] ERRO cluster {cid}: {last_error}")
                print("[Stage 4] 04_labels.json NAO foi gravado. Reexecute para continuar.")
                raise SystemExit(2)
            ck.write(json.dumps(label, ensure_ascii=False) + "\n")
            ck.flush()
            feitos[cid] = label
            used_names[_norm(label["nome"])] = cid
            print(f"   cluster {cid}: {label['nome']}")

    faltando = [int(s["cluster_id"]) for s in stats if int(s["cluster_id"]) not in feitos]
    if faltando:
        print(f"[Stage 4] faltam clusters: {faltando}. Reexecute para continuar.")
        raise SystemExit(2)

    labels = [feitos[int(s["cluster_id"])] for s in stats]
    stage4_fingerprint = hashlib.sha256(json.dumps({
        "label_input_fingerprint": label_input_fingerprint,
        "labels": labels,
    }, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    out = OrderedDict([
        ("optimal_k", int(clusters.get("optimal_k", len(labels)))),
        ("total_tickets", total_tickets),
        ("metadata", OrderedDict([
            ("clustering_fingerprint", clustering_fingerprint),
            ("label_input_fingerprint", label_input_fingerprint),
            ("stage4_fingerprint", stage4_fingerprint),
            ("stage3_method", clusters.get("metodo", "")),
            ("label_model", client.model_label),
        ])),
        ("clusters", labels),
    ])
    json.dump(out, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[Stage 4] OK: {OUT} ({len(labels)} grupos)")


if __name__ == "__main__":
    main()
