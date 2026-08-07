#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Stage 2 via LLM (Ollama local / OpenAI / Azure) - sumarizacao chamado a chamado.

Le pipeline_data/01_tickets.json, chama a LLM para CADA chamado e grava
pipeline_data/02_summaries.json (contrato em especificacoes/CONTRATOS_DE_DADOS.md).

Resumivel: cada resultado e anexado a um checkpoint POR MODELO
(pipeline_data/_ckpt_stage2__<modelo>.jsonl); ao reexecutar, chamados ja
resolvidos sao pulados. Concorrente (PIPELINE_WORKERS).

O provedor vem do .env (veja .env.example). Uso:
  python scripts/run_stage2_llm.py
"""
import os
import sys
import json
import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from projeto import pipeline_data_dir, config_path, load_projeto_meta
from llm_client import get_client, LLMError

PD = pipeline_data_dir()
OUT = PD / "02_summaries.json"

TP_VALIDOS = {"incidente", "solicitacao", "acesso", "instalacao", "duvida", "configuracao", "outro"}
STAGE2_VERSION = "intent-blind-v2"


def carregar_contexto() -> str:
    try:
        cfg = json.load(open(config_path(), encoding="utf-8-sig"))
        return cfg.get("infra_context", {}).get("texto_contexto", "")
    except Exception:
        return ""


SYSTEM = """Voce e analista de suporte do portal {portal_nome}. Sua tarefa e destilar a intencao real de UM chamado (Stage 2 do pipeline de triagem).

CONTEXTO DE SERVICOS DO PORTAL:
{contexto}

Leia titulo + descricao + comentarios e responda um objeto JSON com EXATAMENTE estes campos:
- intencao: frase objetiva do que o usuario quer (max. 20 palavras). Descreve o SERVICO ou PROBLEMA, nunca nome de pessoa, codigo, identificador ou nome de base. Vem do contexto completo (descricao/comentarios), nao so do titulo.
- tema: 2-3 palavras que resumem o assunto.
- tipo_pedido: um de [incidente, solicitacao, acesso, instalacao, duvida, configuracao, outro]. Se nao couber, "outro".
- contexto: uma area curta do portal, derivada do CONTEXTO DE SERVICOS DO PORTAL. Use 1 a 3 palavras em minusculas, como o nome da area ou dominio. Se nao houver area clara, use "outro".
- info_fornecidas: lista (ate 3) do que o usuario ja informou.
- info_faltantes: lista (ate 3) de informacoes tipicamente necessarias que faltaram.
- descricao_insuficiente: "sim" SOMENTE se, nos comentarios, o atendente precisou pedir informacoes adicionais ao usuario para resolver (ex.: ambiente, nome da base/objeto, script, mensagem de erro, aprovacao). "nao" se resolveu com a descricao original, se os comentarios sao so status, ou se nao ha comentarios.

REGRAS:
- Sem descricao nem comentarios uteis: intencao="Chamado sem descricao de demanda", tipo_pedido="outro", contexto="outro".
- Nao use travessao em nenhum texto; use virgula, ponto ou dois-pontos.
- Responda APENAS o objeto JSON, nada mais."""


def montar_user(t: dict) -> str:
    return (
        f"TITULO: {t.get('titulo','')}\n"
        f"DESCRICAO: {t.get('descricao','')}\n"
        f"COMENTARIOS: {t.get('comentarios','')}"
    )


def normalizar(res: dict, t: dict) -> dict:
    tp = str(res.get("tipo_pedido", "outro")).strip().lower()
    if tp not in TP_VALIDOS:
        tp = "outro"
    ctx = " ".join(str(res.get("contexto", "outro")).strip().lower().split())[:60] or "outro"
    di = "sim" if str(res.get("descricao_insuficiente", "nao")).strip().lower() == "sim" else "nao"

    def lista(x):
        if isinstance(x, list):
            return [str(i).strip() for i in x if str(i).strip()][:3]
        if x:
            return [str(x).strip()][:3]
        return []

    return {
        "chave": t["chave"],
        "intencao": str(res.get("intencao", "")).strip()[:300] or "Chamado sem descricao de demanda",
        "tema": str(res.get("tema", "")).strip()[:60],
        "tipo_pedido": tp,
        "contexto": ctx,
        "info_fornecidas": lista(res.get("info_fornecidas")),
        "info_faltantes": lista(res.get("info_faltantes")),
        "descricao_insuficiente": di,
        "tipo_atual": t.get("tipo_atual", ""),
        "qtd_interacoes": int(t.get("qtd_interacoes", 0) or 0),
        "situacao": t.get("situacao", ""),
    }


def _source_hash(ticket: dict, contexto: str = "") -> str:
    payload = {
        "version": STAGE2_VERSION,
        "titulo": ticket.get("titulo", ""),
        "descricao": ticket.get("descricao", ""),
        "comentarios": ticket.get("comentarios", ""),
        "contexto_portal": contexto,
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()


def carregar_ckpt(*paths: Path, source_hashes: dict[str, str] | None = None) -> dict:
    feitos = {}
    for ckpt in paths:
        if not ckpt.exists():
            continue
        for ln in ckpt.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                o = json.loads(ln)
                key = o["chave"]
                if source_hashes is None or o.get("_source_hash") == source_hashes.get(key):
                    feitos[key] = o
            except Exception:
                pass
    return feitos


def main():
    tickets = json.load(open(PD / "01_tickets.json", encoding="utf-8"))
    contexto = carregar_contexto()
    meta = load_projeto_meta()
    portal_nome = meta.get("portal_nome") or meta.get("nome") or "portal de atendimento"
    system = (
        SYSTEM
        .replace("{portal_nome}", portal_nome)
        .replace("{contexto}", contexto or "(sem contexto adicional)")
    )
    client = get_client()
    workers = int(os.getenv("PIPELINE_WORKERS", "8"))
    safe = client.model_label.replace(":", "_").replace("/", "_")
    ckpt = PD / f"_ckpt_stage2__{safe}.jsonl"
    legacy_ckpt = PD / "_ckpt_stage2.jsonl"
    source_hashes = {t["chave"]: _source_hash(t, contexto) for t in tickets}

    feitos = carregar_ckpt(legacy_ckpt, ckpt, source_hashes=source_hashes)
    pendentes = [t for t in tickets if t["chave"] not in feitos]
    print(f"[Stage 2/{client.model_label}] total={len(tickets)} feitos={len(feitos)} pendentes={len(pendentes)} workers={workers}")
    print(f"[Stage 2] checkpoint: {ckpt.name}")

    lock = threading.Lock()
    ck = open(ckpt, "a", encoding="utf-8")
    contad = {"ok": 0, "erro": 0}

    def processa(t):
        try:
            res = client.chat_json(system, montar_user(t), max_tokens=500)
            obj = normalizar(res, t)
            obj["_source_hash"] = source_hashes[t["chave"]]
            with lock:
                ck.write(json.dumps(obj, ensure_ascii=False) + "\n")
                ck.flush()
                contad["ok"] += 1
                if (contad["ok"] + contad["erro"]) % 100 == 0:
                    print(f"   ... {contad['ok']} ok, {contad['erro']} erro")
            return True
        except LLMError as e:
            with lock:
                contad["erro"] += 1
            print(f"   [ERRO] {t['chave']}: {e}")
            return False

    if pendentes:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = [ex.submit(processa, t) for t in pendentes]
            for _ in as_completed(futs):
                pass
    ck.close()

    feitos = carregar_ckpt(legacy_ckpt, ckpt, source_hashes=source_hashes)
    saida = [
        {key: value for key, value in feitos[t["chave"]].items() if not key.startswith("_")}
        for t in tickets if t["chave"] in feitos
    ]
    faltando = [t["chave"] for t in tickets if t["chave"] not in feitos]
    print(f"[Stage 2] resolvidos={len(saida)} faltando={len(faltando)}")
    if faltando:
        print(f"[Stage 2] AINDA FALTAM {len(faltando)} (reexecute para completar). Ex.: {faltando[:5]}")
        print("[Stage 2] 02_summaries.json NAO foi gravado (incompleto).")
        raise SystemExit(2)
    json.dump(saida, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"[Stage 2] OK: {OUT} ({len(saida)} resumos) via {client.model_label}")


if __name__ == "__main__":
    main()
