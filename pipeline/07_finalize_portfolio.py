#!/usr/bin/env python3
"""
Stage 7 — Finalizacao do portfolio (curadoria humana) e reclassificacao.

Diferente dos Stages 1-6 (genericos e automaticos), o Stage 7 e a etapa de
HUMANO NO LOOP: le o portfolio FINAL definido pelo dono da area em
feedback_portfolio.json e reclassifica TODOS os chamados historicos nele,
aplicando as diretrizes, os servicos fora do catalogo e os encaminhamentos.

Roda DEPOIS dos Stages 1-6 e da curadoria humana. Deixa o dashboard e a
simulacao consistentes com o portfolio que a area escolheu como ideal.

Entrada:  feedback_portfolio.json            (curadoria da area)
          pipeline_data/02_summaries.json     (resumos do Stage 2)
Saida:    pipeline_data/07_portfolio_final.json     (portfolio definido)
          pipeline_data/07_classificados_final.json (reclassificacao per-ticket)
Checkpoint: pipeline_data/07_checkpoint.json
"""

import os
import sys
import json
import time
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.llm_client import generate_json, is_available, OLLAMA_URL

PIPELINE_DATA   = Path(__file__).parent.parent / "pipeline_data"
FEEDBACK_PATH   = Path(__file__).parent.parent / "feedback_portfolio.json"
INPUT_FILE      = PIPELINE_DATA / "02_summaries.json"
OUT_PORTFOLIO   = PIPELINE_DATA / "07_portfolio_final.json"
OUT_CLASSIF     = PIPELINE_DATA / "07_classificados_final.json"
CHECKPOINT_FILE = PIPELINE_DATA / "07_checkpoint.json"

WORKERS = int(os.getenv("STAGE7_WORKERS", "2"))


def _load_feedback() -> dict:
    if not FEEDBACK_PATH.exists():
        print(f"[Stage 7] ERRO: {FEEDBACK_PATH.name} nao encontrado. "
              "Defina o portfolio final (curadoria) antes de rodar o Stage 7.")
        sys.exit(1)
    with open(FEEDBACK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


_FB         = _load_feedback()
_PORTFOLIO  = [c for c in _FB.get("portfolio_final", []) if isinstance(c, dict)]
_DIRETRIZES = _FB.get("diretrizes", [])
_FORA       = _FB.get("fora_do_catalogo", [])
_NOMES_VALIDOS = {c.get("nome", "").strip() for c in _PORTFOLIO if c.get("nome")}
_PORTFOLIO_SIG = sorted(_NOMES_VALIDOS)


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().split())


_NOMES_NORM = {_norm(n): n for n in _NOMES_VALIDOS}


def _resolver_categoria(cat: str):
    """Casa o nome devolvido pelo LLM com uma categoria valida, tolerando variacoes
    (descricao anexada apos ':', acentos, caixa, prefixo). Retorna o nome canonico ou None."""
    if not cat:
        return None
    cat = cat.strip()
    if cat in _NOMES_VALIDOS:
        return cat
    antes = cat.split(":")[0].strip()
    if antes in _NOMES_VALIDOS:
        return antes
    if _norm(antes) in _NOMES_NORM:
        return _NOMES_NORM[_norm(antes)]
    cat_norm = _norm(cat)
    for nome in _NOMES_VALIDOS:
        if cat_norm.startswith(_norm(nome)):
            return nome
    return None


def _build_cats_texto() -> str:
    linhas = []
    for c in _PORTFOLIO:
        nome   = c.get("nome", "").strip()
        desc   = c.get("descricao", "").strip()
        quando = c.get("quando_usar", "").strip()
        if nome:
            linha = f"- {nome}: {desc}"
            if quando:
                linha += f" | Usar quando: {quando}"
            linhas.append(linha)
    return "\n".join(linhas)


def _build_diretrizes_texto() -> str:
    if not _DIRETRIZES:
        return "(nenhuma)"
    return "\n".join(f"- {d}" for d in _DIRETRIZES)


def _build_fora_texto() -> str:
    if not _FORA:
        return "(nenhum)"
    return "\n".join(f"- {x.get('tema','')}" for x in _FORA if x.get("tema"))


_CATS_TEXTO       = _build_cats_texto()
_DIRETRIZES_TEXTO = _build_diretrizes_texto()
_FORA_TEXTO       = _build_fora_texto()

PROMPT_TEMPLATE = """Voce e um analista de triagem de chamados. Classifique o chamado em EXATAMENTE UMA das categorias do portfolio final definido pela area.

DIRETRIZES (aplique rigorosamente):
{diretrizes}

SERVICOS FORA DO CATALOGO (se o chamado for sobre um destes, classifique como "Nao encontrou o que procurava?"):
{fora}

CATEGORIAS DO PORTFOLIO FINAL:
{cats_texto}

CHAMADO (resumo extraido por IA):
Intencao: {intencao}
Tema: {tema}
Tipo de pedido: {tipo_pedido}
Contexto: {contexto}
Informacoes fornecidas: {info_fornecidas}

Responda APENAS com JSON valido:
{{
  "categoria_nova": "nome EXATO de uma das categorias acima — apenas o nome, SEM a descricao",
  "justificativa": "1-2 frases explicando a escolha",
  "confianca": "alta|media|baixa"
}}"""


def _fmt_list(v) -> str:
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else "—"
    return str(v) if v else "—"


def classify_ticket(summary: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        diretrizes=_DIRETRIZES_TEXTO,
        fora=_FORA_TEXTO,
        cats_texto=_CATS_TEXTO,
        intencao=summary.get("intencao") or "—",
        tema=summary.get("tema") or "—",
        tipo_pedido=summary.get("tipo_pedido") or "—",
        contexto=summary.get("contexto") or "—",
        info_fornecidas=_fmt_list(summary.get("info_fornecidas")),
    )

    result = None
    for tentativa in range(2):
        try:
            result = generate_json(prompt, temperature=0.1, max_tokens=220, timeout=300, num_ctx=4096)
        except Exception as e:
            result = {
                "categoria_nova": "Não encontrou o que procurava?",
                "justificativa":  "Erro na classificação.",
                "confianca":      "baixa",
                "_erro":          str(e),
            }
            break

        cat = result.get("categoria_nova", "").strip()
        resolvido = _resolver_categoria(cat)
        if resolvido:
            result["categoria_nova"] = resolvido
            break
        if tentativa == 0:
            result["_retry_motivo"] = f"Categoria '{cat}' não reconhecida — tentando novamente."
        else:
            result["categoria_nova"] = "Não encontrou o que procurava?"
            result["_aviso"] = f"Categoria '{cat}' não reconhecida após retry — substituída."

    result["chave"]      = summary["chave"]
    result["intencao"]   = summary.get("intencao", "")
    result["tipo_atual"] = summary.get("tipo_atual", "")
    return result


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(processed: dict) -> None:
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump({"processed": processed, "portfolio_sig": _PORTFOLIO_SIG}, f, ensure_ascii=False)


def main():
    if not is_available():
        print(f"[Stage 7] ERRO: Ollama não está rodando em {OLLAMA_URL}")
        sys.exit(1)

    if not _PORTFOLIO:
        print("[Stage 7] ERRO: feedback_portfolio.json não tem 'portfolio_final'.")
        sys.exit(1)

    if not INPUT_FILE.exists():
        print("[Stage 7] ERRO: 02_summaries.json não encontrado (rode os Stages 1-2 antes).")
        sys.exit(1)

    print(f"[Stage 7] Portfólio final: {len(_PORTFOLIO)} categorias | "
          f"{len(_DIRETRIZES)} diretrizes | {len(_FORA)} temas fora do catálogo")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    total = len(summaries)
    print(f"[Stage 7] {total} chamados para reclassificar no portfólio final (workers={WORKERS})")

    checkpoint = load_checkpoint()
    if checkpoint.get("portfolio_sig") != _PORTFOLIO_SIG:
        if checkpoint.get("processed"):
            print("[Stage 7] Portfólio final mudou desde o checkpoint anterior — reclassificando do zero.")
        processed: dict = {}
    else:
        processed = checkpoint.get("processed", {})
    ja_feitos = len(processed)
    if ja_feitos:
        print(f"[Stage 7] Retomando: {ja_feitos}/{total} já classificados")

    pendentes = [s for s in summaries if s["chave"] not in processed]

    start = time.time()
    lock  = threading.Lock()
    novos = 0

    def processar(summary):
        return summary["chave"], classify_ticket(summary)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(processar, s): s for s in pendentes}
        for future in as_completed(futures):
            chave, result = future.result()
            with lock:
                processed[chave] = result
                novos += 1
                if novos % 10 == 0:
                    save_checkpoint(processed)
                    elapsed = time.time() - start
                    restantes = len(pendentes) - novos
                    eta_min = (elapsed / novos * restantes / 60) if novos > 0 else 0
                    print(f"[Stage 7] {ja_feitos + novos}/{total} "
                          f"({elapsed/60:.1f}min decorridos, ~{eta_min:.0f}min restantes)")

    save_checkpoint(processed)

    chaves_ordenadas = [s["chave"] for s in summaries]
    classificados = [processed[c] for c in chaves_ordenadas if c in processed]

    with open(OUT_CLASSIF, "w", encoding="utf-8") as f:
        json.dump(classificados, f, ensure_ascii=False, indent=2)

    # Portfólio final definido (definição + metadados) — alimenta o dashboard
    from collections import Counter
    cont = Counter(s.get("categoria_nova", "?") for s in classificados)
    enc_nomes = {c.get("nome", "").strip() for c in _PORTFOLIO if c.get("encaminhamento")}
    base = sum(n for k, n in cont.items() if k not in enc_nomes) or 1
    portfolio_out = []
    for c in _PORTFOLIO:
        nome = c.get("nome", "").strip()
        n = cont.get(nome, 0)
        item = dict(c)
        item["volume"] = n
        item["percentual_portfolio"] = None if c.get("encaminhamento") else round(n / base * 100, 1)
        portfolio_out.append(item)

    with open(OUT_PORTFOLIO, "w", encoding="utf-8") as f:
        json.dump({
            "portfolio_final": portfolio_out,
            "diretrizes": _DIRETRIZES,
            "fora_do_catalogo": _FORA,
            "metadata": {"total_classificados": len(classificados), "base_portfolio": base},
        }, f, ensure_ascii=False, indent=2)

    erros  = sum(1 for s in classificados if "_erro" in s)
    avisos = sum(1 for s in classificados if "_aviso" in s)
    print(f"[Stage 7] Concluído: {len(classificados)} reclassificados no portfólio final")
    if erros:
        print(f"  {erros} com erro de LLM/JSON → fallback")
    if avisos:
        print(f"  {avisos} com categoria inválida após retry → fallback")
    print(f"[Stage 7] Salvo: {OUT_CLASSIF.name} + {OUT_PORTFOLIO.name}")

    port = {k: v for k, v in cont.items() if k not in enc_nomes}
    enc  = {k: v for k, v in cont.items() if k in enc_nomes}
    print(f"[Stage 7] Portfólio final — {sum(port.values())} chamados no escopo:")
    for k, n in sorted(port.items(), key=lambda x: -x[1]):
        print(f"  {k}: {n} ({n/base*100:.1f}%)")
    if enc:
        print(f"[Stage 7] Encaminhamentos (fora do portfólio) — {sum(enc.values())} chamados:")
        for k, n in sorted(enc.items(), key=lambda x: -x[1]):
            print(f"  {k}: {n}")


if __name__ == "__main__":
    main()
