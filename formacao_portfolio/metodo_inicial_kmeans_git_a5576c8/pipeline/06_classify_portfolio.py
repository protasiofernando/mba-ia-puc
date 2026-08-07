#!/usr/bin/env python3
"""
Stage 6 — Classificação dos chamados históricos no portfólio otimizado.

Usa os resumos do Stage 2 (intencao, tema, tipo_pedido, contexto) como
entrada — evita reler o texto bruto e aproveita o trabalho já feito pelo LLM.
O prompt é curto e focado: intenção destilada → categoria do portfólio.

Checkpoint automático: retoma de onde parou se o job for interrompido.

Entrada:  pipeline_data/02_summaries.json   (saída do Stage 2)
          pipeline_data/05_portfolio_recommendation.json
          config_portfolio.json
Saída:    pipeline_data/06_classificados.json
Checkpoint: pipeline_data/06_checkpoint.json
"""

import sys
import json
import os
import time
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.llm_client import generate_json, is_available, OLLAMA_URL

PIPELINE_DATA   = Path(__file__).parent.parent / "pipeline_data"
CONFIG_PATH     = Path(__file__).parent.parent / "config_portfolio.json"
INPUT_FILE      = PIPELINE_DATA / "02_summaries.json"
PORTFOLIO_FILE  = PIPELINE_DATA / "05_portfolio_recommendation.json"
OUTPUT_FILE     = PIPELINE_DATA / "06_classificados.json"
CHECKPOINT_FILE = PIPELINE_DATA / "06_checkpoint.json"

WORKERS = int(os.getenv("STAGE6_WORKERS", "1"))


def _build_portfolio() -> list:
    """Carrega categorias do portfólio otimizado + obrigatórias do config."""
    cats = []

    if PORTFOLIO_FILE.exists():
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as f:
            d = json.load(f)
        raw = d.get("recomendacao", {}).get("portfolio_otimizado", [])
        cats = [c for c in raw if isinstance(c, dict)]

    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        obrigatorias = cfg.get("categorias_obrigatorias", [])
        nomes_llm = {c.get("nome", "").strip().lower() for c in cats}
        for cat in obrigatorias:
            nome = cat.get("nome", "").strip()
            if nome.lower() not in nomes_llm:
                cats.append(cat)

    return cats


def _build_cats_texto(portfolio: list) -> str:
    linhas = []
    for cat in portfolio:
        nome   = cat.get("nome", "").strip()
        desc   = cat.get("descricao", "").strip()
        quando = cat.get("quando_usar", "").strip()
        if nome:
            linhas.append(f"- {nome}: {desc} | Usar quando: {quando}")
    return "\n".join(linhas)


_PORTFOLIO     = _build_portfolio()
_CATS_TEXTO    = _build_cats_texto(_PORTFOLIO)
_NOMES_VALIDOS = {c.get("nome", "").strip() for c in _PORTFOLIO if c.get("nome")}
# Assinatura do portfolio: se mudar (categoria adicionada/removida/renomeada), o
# checkpoint antigo fica invalido — as classificacoes foram feitas contra outro portfolio.
_PORTFOLIO_SIG = sorted(_NOMES_VALIDOS)
# Categorias de encaminhamento (ex: Sala de Sigilo → Segurança): identificadas para
# tirar os chamados do "Não encontrou", mas NÃO fazem parte do portfólio otimizado —
# não entram no cálculo das porcentagens do portfólio.
_ENCAMINHAMENTO_NOMES = {c.get("nome", "").strip() for c in _PORTFOLIO if c.get("encaminhamento")}


def _norm(s: str) -> str:
    """Normaliza para comparacao: sem acentos, minusculo, espacos colapsados."""
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode("ascii")
    return " ".join(s.lower().split())


_NOMES_NORM = {_norm(n): n for n in _NOMES_VALIDOS}


def _resolver_categoria(cat: str):
    """Casa o nome devolvido pelo LLM com uma categoria valida, tolerando variacoes.

    O LLM frequentemente anexa a descricao apos o nome ("Nome: descricao...") ou
    varia acentos/caixa. Tenta, em ordem: match exato, texto antes do ':', match
    normalizado e match por prefixo. Retorna o nome canonico ou None.
    """
    if not cat:
        return None
    cat = cat.strip()
    if cat in _NOMES_VALIDOS:
        return cat
    # "Nome: descricao..." -> pega o texto antes do primeiro ':'
    antes = cat.split(":")[0].strip()
    if antes in _NOMES_VALIDOS:
        return antes
    # match normalizado (acentos/caixa/espacos) do texto antes do ':'
    if _norm(antes) in _NOMES_NORM:
        return _NOMES_NORM[_norm(antes)]
    # prefixo: algum nome valido e o inicio do que o LLM devolveu
    cat_norm = _norm(cat)
    for nome in _NOMES_VALIDOS:
        if cat_norm.startswith(_norm(nome)):
            return nome
    return None

PROMPT_TEMPLATE = """Você é um analista de suporte da DTI FGV. Classifique o chamado abaixo em uma das categorias do portfólio.

CATEGORIAS DO PORTFÓLIO OTIMIZADO:
{cats_texto}

CHAMADO (resumo extraído por IA):
Intenção: {intencao}
Tema: {tema}
Tipo de pedido: {tipo_pedido}
Contexto: {contexto}
Informações fornecidas: {info_fornecidas}

Responda APENAS com JSON válido:
{{
  "categoria_nova": "nome EXATO de uma das categorias acima — apenas o nome, SEM a descrição que vem depois dos dois-pontos",
  "justificativa": "1-2 frases explicando por que esta categoria",
  "confianca": "alta|media|baixa"
}}"""


def _fmt_list(v) -> str:
    if isinstance(v, list):
        return ", ".join(str(x) for x in v) if v else "—"
    return str(v) if v else "—"


def classify_ticket(summary: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        cats_texto=_CATS_TEXTO,
        intencao=summary.get("intencao") or "—",
        tema=summary.get("tema") or "—",
        tipo_pedido=summary.get("tipo_pedido") or "—",
        contexto=summary.get("contexto") or "—",
        info_fornecidas=_fmt_list(summary.get("info_fornecidas")),
    )

    result = None
    for tentativa in range(2):  # até 2 tentativas: normal + retry se categoria inválida
        try:
            result = generate_json(prompt, temperature=0.1, max_tokens=300, timeout=120, num_ctx=4096)
        except Exception as e:
            result = {
                "categoria_nova": "Não encontrou o que procurava?",
                "justificativa":  "Erro na classificação.",
                "confianca":      "baixa",
                "_erro":          str(e),
            }
            break  # falha de LLM/JSON não melhora com retry — sai imediatamente

        cat = result.get("categoria_nova", "").strip()
        resolvido = _resolver_categoria(cat)
        if resolvido:
            result["categoria_nova"] = resolvido  # nome canônico (corrige descrição anexada, acentos, etc.)
            break

        # Categoria inválida: na primeira tentativa, faz retry; na segunda, usa fallback
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
        print(f"[Stage 6] ERRO: Ollama não está rodando em {OLLAMA_URL}")
        sys.exit(1)

    if not PORTFOLIO_FILE.exists():
        print("[Stage 6] ERRO: 05_portfolio_recommendation.json não encontrado.")
        sys.exit(1)

    if not INPUT_FILE.exists():
        print("[Stage 6] ERRO: 02_summaries.json não encontrado.")
        sys.exit(1)

    print(f"[Stage 6] {len(_PORTFOLIO)} categorias no portfólio")

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        summaries = json.load(f)

    total = len(summaries)
    print(f"[Stage 6] {total} chamados para classificar (workers={WORKERS})")

    checkpoint = load_checkpoint()
    if checkpoint.get("portfolio_sig") != _PORTFOLIO_SIG:
        if checkpoint.get("processed"):
            print("[Stage 6] Portfolio mudou desde o checkpoint anterior — "
                  "descartando classificacoes antigas e reclassificando do zero.")
        processed: dict = {}
    else:
        processed = checkpoint.get("processed", {})
    ja_feitos = len(processed)

    if ja_feitos:
        print(f"[Stage 6] Retomando: {ja_feitos}/{total} já classificados")

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
                    feitos_total = ja_feitos + novos
                    print(
                        f"[Stage 6] {feitos_total}/{total} "
                        f"({elapsed/60:.1f}min decorridos, ~{eta_min:.0f}min restantes)"
                    )

    save_checkpoint(processed)

    chaves_ordenadas = [s["chave"] for s in summaries]
    classificados = [processed[c] for c in chaves_ordenadas if c in processed]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(classificados, f, ensure_ascii=False, indent=2)

    erros      = sum(1 for s in classificados if "_erro" in s)
    avisos     = sum(1 for s in classificados if "_aviso" in s)
    retentados = sum(1 for s in classificados if "_retry_motivo" in s)
    print(f"[Stage 6] Concluído: {len(classificados)} classificados")
    if erros:
        print(f"  {erros} com erro de LLM/JSON → fallback")
    if avisos:
        print(f"  {avisos} com categoria inválida após retry → fallback")
    if retentados:
        print(f"  {retentados} resolvidos no retry (categoria inválida na 1ª tentativa)")
    print(f"[Stage 6] Salvo em: {OUTPUT_FILE}")

    from collections import Counter
    cats = Counter(s.get("categoria_nova", "?") for s in classificados)

    # Separa portfólio (escopo DTI Pesquisa) dos encaminhamentos (ex: Sala de Sigilo → Segurança).
    enc  = {k: n for k, n in cats.items() if k in _ENCAMINHAMENTO_NOMES}
    port = {k: n for k, n in cats.items() if k not in _ENCAMINHAMENTO_NOMES}
    base = sum(port.values()) or 1  # base do portfólio exclui os encaminhamentos

    print(f"[Stage 6] Portfólio otimizado — {sum(port.values())} chamados no escopo da DTI Pesquisa:")
    for cat, n in sorted(port.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {n} ({n/base*100:.1f}%)")
    if enc:
        total_enc = sum(enc.values())
        print(f"[Stage 6] Encaminhamentos (fora do portfólio) — {total_enc} chamados ({total_enc/len(classificados)*100:.1f}% do total):")
        for cat, n in sorted(enc.items(), key=lambda x: -x[1]):
            print(f"  {cat}: {n}")


if __name__ == "__main__":
    main()
