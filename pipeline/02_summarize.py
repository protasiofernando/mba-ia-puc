#!/usr/bin/env python3
"""
Stage 2 — Sumarizacao de intencao por LLM.

Para cada ticket, o modelo lê titulo + descricao + comentarios e extrai:
  - intencao:   o que o usuario realmente quer (frase curta)
  - tema:       2-3 palavras que resumem o assunto
  - tipo_pedido: incidente | solicitacao | acesso | instalacao | duvida | outro
  - contexto:   infraestrutura | nuvem | software | pesquisa | outro
  - info_fornecidas:  o que o usuario ja informou
  - info_faltantes:   o que faltou no chamado original

Checkpoint automatico: retoma de onde parou se o job for interrompido.

Entrada:  pipeline_data/01_tickets.json
Saida:    pipeline_data/02_summaries.json
Checkpoint: pipeline_data/02_checkpoint.json

Tempo estimado (gemma4:26b-q8 no V100):
  ~4-6 segundos por ticket; em ~1.600 tickets, ~110-160 minutos
"""

import sys
import json
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from pipeline.llm_client import generate_json, is_available, OLLAMA_URL

PIPELINE_DATA = Path(__file__).parent.parent / "pipeline_data"
CONFIG_PATH   = Path(__file__).parent.parent / "config_portfolio.json"
INPUT_FILE    = PIPELINE_DATA / "01_tickets.json"
OUTPUT_FILE   = PIPELINE_DATA / "02_summaries.json"
CHECKPOINT_FILE = PIPELINE_DATA / "02_checkpoint.json"


def _build_infra_context() -> str:
    """Lê texto_contexto do config_portfolio.json e retorna pronto para o prompt."""
    if not CONFIG_PATH.exists():
        return ""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    return cfg.get("infra_context", {}).get("texto_contexto", "")


# -------------------------------------------------------------------
# Prompt de extracao de intencao
# Construido dinamicamente para incluir o contexto de infraestrutura.
# Temperatura baixa (0.1) para respostas consistentes e factuais.
# -------------------------------------------------------------------
_INFRA_CONTEXT = _build_infra_context()

# O infra_context é injetado por concatenação em build_prompt() — não via .format() —
# para evitar KeyError quando o texto_contexto contém chaves {} (JSON, exemplos, etc.).
_PROMPT_BODY = """Voce e um analista de suporte de TI da FGV. Leia o chamado abaixo e use o contexto de infraestrutura acima para identificar corretamente o pedido.

Titulo: {titulo}
Descricao: {descricao}
Comentarios (usuario e atendente): {comentarios}

REGRAS IMPORTANTES:
- A intencao deve ser identificada pelo contexto completo do chamado (descricao e comentarios), nao apenas pelo titulo. O titulo frequentemente contem apenas um nome proprio ou codigo interno sem valor semantico.
- A intencao deve descrever o SERVICO ou PROBLEMA solicitado, nunca um nome de pessoa, codigo ou identificador.
- Se nao houver descricao nem comentarios uteis, classifique como "Chamado sem descricao de demanda" e tipo_pedido "outro".
- Para descricao_insuficiente: responda "sim" SOMENTE se nos comentarios o atendente precisou solicitar ao usuario informacoes adicionais para poder resolver o chamado (ex: pediu o nome do sistema, servidor, link, mensagem de erro exata, credenciais, periodo). Responda "nao" se o chamado foi resolvido com as informacoes da descricao original, se os comentarios sao apenas atualizacoes de status/andamento, ou se nao ha comentarios.

Identifique o pedido real do usuario e responda APENAS com JSON valido, sem nenhum texto adicional:
{{
  "intencao": "frase objetiva do que o usuario quer (maximo 20 palavras)",
  "tema": "2-3 palavras que resumem o assunto",
  "tipo_pedido": "incidente|solicitacao|acesso|instalacao|duvida|configuracao|outro",
  "contexto": "infraestrutura|nuvem|software|pesquisa|acesso|outro",
  "info_fornecidas": ["informacoes que o usuario ja forneceu no chamado"],
  "info_faltantes": ["informacoes tipicamente necessarias que estavam ausentes"],
  "descricao_insuficiente": "sim|nao"
}}"""


def _build_prompt(titulo: str, descricao: str, comentarios: str) -> str:
    """Monta o prompt JSON injetando o infra_context por concatenação (seguro para texto com chaves {})."""
    cabecalho = (_INFRA_CONTEXT + "\n\n") if _INFRA_CONTEXT else ""
    corpo = _PROMPT_BODY.format(
        titulo=titulo,
        descricao=descricao,
        comentarios=comentarios,
    )
    return cabecalho + corpo


def _normalize_result(result: dict) -> dict:
    """Garante tipos simples e valores esperados antes de seguir para os próximos stages."""
    tipo_validos = {"incidente", "solicitacao", "acesso", "instalacao", "duvida", "configuracao", "outro"}
    contexto_validos = {"infraestrutura", "nuvem", "software", "pesquisa", "acesso", "outro"}

    def as_list(value):
        if isinstance(value, list):
            return [str(v)[:160] for v in value[:3] if str(v).strip()]
        if isinstance(value, str) and value.strip():
            return [value[:160]]
        return []

    result["intencao"] = str(result.get("intencao") or "Chamado sem descricao de demanda")[:220]
    result["tema"] = str(result.get("tema") or "indefinido")[:80]
    if result.get("tipo_pedido") not in tipo_validos:
        result["tipo_pedido"] = "outro"
    if result.get("contexto") not in contexto_validos:
        result["contexto"] = "outro"
    result["info_fornecidas"] = as_list(result.get("info_fornecidas"))
    result["info_faltantes"] = as_list(result.get("info_faltantes"))
    if result.get("descricao_insuficiente") not in {"sim", "nao", "indefinido"}:
        result["descricao_insuficiente"] = "indefinido"
    return result


def load_checkpoint() -> dict:
    if CHECKPOINT_FILE.exists():
        with open(CHECKPOINT_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_checkpoint(processed: dict) -> None:
    with open(CHECKPOINT_FILE, "w", encoding="utf-8") as f:
        json.dump(processed, f, ensure_ascii=False)


def summarize_ticket(ticket: dict) -> dict:
    """Extrai a intenção do ticket via LLM. Em caso de falha, usa o título como fallback."""
    titulo     = (ticket["titulo"]     or "(sem titulo)")[:400]
    descricao  = (ticket["descricao"]  or "(sem descricao)")[:3000]
    comentarios = (ticket["comentarios"] or "(sem comentarios)")[:4000]

    try:
        prompt = _build_prompt(titulo, descricao, comentarios)
        result = generate_json(prompt, temperature=0.1, max_tokens=1024, timeout=300, num_ctx=8192)
        result = _normalize_result(result)
    except Exception as e:
        print(f"  [Stage 2] {ticket['chave']}: falha LLM ({str(e)[:80]}) — usando fallback.")
        result = {
            "intencao": ticket["titulo"][:80],
            "tema": "indefinido",
            "tipo_pedido": "outro",
            "contexto": "outro",
            "info_fornecidas": [],
            "info_faltantes": [],
            "descricao_insuficiente": "indefinido",
            "_erro": str(e),
        }

    result["chave"]          = ticket["chave"]
    result["tipo_atual"]     = ticket["tipo_atual"]
    result["qtd_interacoes"] = ticket["qtd_interacoes"]
    result["situacao"]       = ticket["situacao"]
    return result


WORKERS = int(os.getenv("STAGE2_WORKERS", "1"))
MAX_ERROR_RATE = float(os.getenv("STAGE2_MAX_ERROR_RATE", "0.25"))
MIN_RESULTS_BEFORE_ABORT = int(os.getenv("STAGE2_MIN_RESULTS_BEFORE_ABORT", "20"))


def main():
    if not is_available():
        print(f"[Stage 2] ERRO: Ollama nao esta rodando em {OLLAMA_URL}")
        print("[Stage 2] Inicie com: ollama serve")
        sys.exit(1)

    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        tickets = json.load(f)

    total = len(tickets)
    print(f"[Stage 2] {total} tickets para processar (workers={WORKERS})")

    # Carrega checkpoint para retomar de onde parou
    checkpoint = load_checkpoint()
    processed: dict = checkpoint.get("processed", {})
    ja_feitos = len(processed)

    if ja_feitos:
        print(f"[Stage 2] Retomando: {ja_feitos}/{total} tickets ja processados")
        erros_checkpoint = sum(1 for s in processed.values() if isinstance(s, dict) and "_erro" in s)
        if ja_feitos >= MIN_RESULTS_BEFORE_ABORT and erros_checkpoint / ja_feitos > MAX_ERROR_RATE:
            print(
                "[Stage 2] ERRO: checkpoint existente tem taxa de erro alta "
                f"({erros_checkpoint}/{ja_feitos}). Apague {CHECKPOINT_FILE.name} "
                "e verifique Ollama/modelo antes de reexecutar."
            )
            sys.exit(2)

    pendentes = [t for t in tickets if t["chave"] not in processed]

    start = time.time()
    lock = threading.Lock()
    novos = 0
    erros_novos = 0

    def processar(ticket):
        return ticket["chave"], summarize_ticket(ticket)

    with ThreadPoolExecutor(max_workers=WORKERS) as executor:
        futures = {executor.submit(processar, t): t for t in pendentes}
        for future in as_completed(futures):
            chave, result = future.result()
            with lock:
                processed[chave] = result
                novos += 1
                if isinstance(result, dict) and "_erro" in result:
                    erros_novos += 1
                    if erros_novos <= 5:
                        print(
                            f"[Stage 2] Falha LLM em {chave}: "
                            f"{str(result.get('_erro', 'erro desconhecido'))[:500]}"
                        )

                # Checkpoint a cada 10 tickets
                if novos % 10 == 0:
                    save_checkpoint({"processed": processed})
                    elapsed = time.time() - start
                    restantes = len(pendentes) - novos
                    eta_min = (elapsed / novos * restantes / 60) if novos > 0 else 0
                    feitos_total = ja_feitos + novos
                    print(
                        f"[Stage 2] {feitos_total}/{total} "
                        f"({elapsed/60:.1f}min decorridos, ~{eta_min:.0f}min restantes)"
                    )

                if (
                    novos >= MIN_RESULTS_BEFORE_ABORT
                    and erros_novos / novos > MAX_ERROR_RATE
                ):
                    save_checkpoint({"processed": processed})
                    print(
                        "[Stage 2] ERRO: taxa de falhas do LLM muito alta "
                        f"({erros_novos}/{novos}, limite {MAX_ERROR_RATE:.0%}). "
                        "Abortando para evitar gerar clusters e recomendacoes com fallback."
                    )
                    for pending in futures:
                        pending.cancel()
                    sys.exit(2)

    # Salva checkpoint final
    save_checkpoint({"processed": processed})

    # Salva resultado ordenado pelo indice original
    chaves_ordenadas = [t["chave"] for t in tickets]
    summaries = [processed[c] for c in chaves_ordenadas if c in processed]

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=2)

    erros = sum(1 for s in summaries if "_erro" in s)
    print(f"[Stage 2] Concluido: {len(summaries)} summaries ({erros} com erro/fallback)")
    print(f"[Stage 2] Salvo em: {OUTPUT_FILE}")

    # Distribuicao de tipos de pedido
    from collections import Counter
    tipos = Counter(s.get("tipo_pedido", "outro") for s in summaries)
    print("[Stage 2] Distribuicao de tipos:")
    for tipo, n in tipos.most_common():
        print(f"  {tipo}: {n} ({n/len(summaries)*100:.1f}%)")


if __name__ == "__main__":
    main()
