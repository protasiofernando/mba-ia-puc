"""
Cliente para Ollama (LLM local).

Configuravel via variaveis de ambiente:
  OLLAMA_URL   - endereco do servidor Ollama (padrao: http://localhost:11434)
  OLLAMA_MODEL - modelo a usar         (padrao: llama3.3:70b)

Suporta retry automatico e extracao de JSON da resposta.

Duas praticas adotadas no uso do Ollama (validas para qualquer modelo):
  1. Endpoint /api/chat (com `messages`), nao /api/generate. O /api/chat aplica
     o template de conversa do modelo; alguns modelos so respondem coerentemente
     por ele. A resposta vem em `message.content`.
  2. think=False no payload. Modelos de raciocinio colocam
     o raciocinio em `message.thinking` e so depois a resposta em `content`; em
     prompts grandes podem gastar todo o orcamento de tokens "pensando" e devolver
     `content` vazio. Como so queremos JSON, desligamos com think=False. Em modelos
     sem raciocinio o parametro e simplesmente ignorado.
"""

import os
import json
import time
import re
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.3:70b")

_CHAT_ENDPOINT = "/api/chat"
_VERSION_ENDPOINT = "/api/version"
_PULL_ENDPOINT = "/api/pull"

# Telemetria de custo (metrica 7 da comparacao). Se OLLAMA_METRICS_FILE estiver
# definido, cada chamada registra tokens e duracao por stage num JSONL. Nunca
# interfere na chamada: qualquer erro de log e silenciado.
_METRICS_FILE = os.getenv("OLLAMA_METRICS_FILE")


def _log_metrics(data: dict, elapsed_s: float = None, kind: str = "chat") -> None:
    if not _METRICS_FILE:
        return
    try:
        rec = {
            "ts": time.time(),
            "stage": os.getenv("PIPELINE_STAGE", ""),
            "model": data.get("model"),
            "kind": kind,
            "prompt_eval_count": data.get("prompt_eval_count"),
            "eval_count": data.get("eval_count"),
            "total_duration_ns": data.get("total_duration"),
            "load_duration_ns": data.get("load_duration"),
            "elapsed_s": round(float(elapsed_s), 3) if elapsed_s is not None else None,
        }
        with open(_METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def is_available() -> bool:
    """Verifica se o Ollama esta rodando."""
    try:
        r = requests.get(f"{OLLAMA_URL}{_VERSION_ENDPOINT}", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def generate(
    prompt: str,
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    timeout: int = 180,
    retries: int = 3,
    num_ctx: int = 2048,
    format_json: bool = False,
) -> str:
    """
    Envia um prompt para o Ollama e retorna o texto da resposta.
    Tenta ate `retries` vezes em caso de falha.

    Usa /api/chat (endpoint de conversa) e desliga o modo de raciocinio com
    think=False — ver nota no topo do arquivo.
    """
    model = model or DEFAULT_MODEL
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "think": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
            "num_ctx": num_ctx,
        },
    }
    if format_json:
        payload["format"] = "json"

    last_error = None
    for attempt in range(retries):
        try:
            r = requests.post(
                f"{OLLAMA_URL}{_CHAT_ENDPOINT}",
                json=payload,
                timeout=timeout,
            )
            r.raise_for_status()
            data = r.json()
            _log_metrics(data, r.elapsed.total_seconds())
            return data["message"]["content"].strip()
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                print(f"  [LLM] Tentativa {attempt+1} falhou ({e}). Aguardando {wait}s...")
                time.sleep(wait)

    raise RuntimeError(f"Ollama falhou apos {retries} tentativas: {last_error}")


def generate_json(
    prompt: str,
    model: str = None,
    temperature: float = 0.1,
    max_tokens: int = 1024,
    timeout: int = 180,
    retries: int = 3,
    num_ctx: int = 2048,
    json_prefix_in_prompt: bool = False,
) -> dict:
    """
    Gera uma resposta e extrai o JSON contido nela.

    json_prefix_in_prompt=True: o prompt termina com '{' — o modelo retorna apenas
    o interior do objeto; recompõe adicionando o '{' antes de parsear.
    Usar apenas nos stages cujo prompt termina com '{'.

    Lida com respostas que envolvem o JSON em blocos de codigo markdown.
    """
    text = generate(
        prompt,
        model,
        temperature,
        max_tokens,
        timeout,
        retries,
        num_ctx,
        format_json=True,
    )
    if not text.strip():
        raise ValueError("Resposta vazia do Ollama")

    # Recompõe o objeto se o prompt terminou com '{'
    texto_completo = ("{" + text) if json_prefix_in_prompt else text

    # Remove blocos ```json ... ``` ou ``` ... ```
    texto_completo = re.sub(r"```json\s*", "", texto_completo)
    texto_completo = re.sub(r"```\s*", "", texto_completo)

    # Extrai do primeiro { ao último }
    inicio = texto_completo.find("{")
    fim    = texto_completo.rfind("}")
    if inicio != -1 and fim > inicio:
        try:
            return json.loads(texto_completo[inicio:fim+1])
        except json.JSONDecodeError:
            pass

    # Fallback: regex greedy
    match = re.search(r"\{.*\}", texto_completo, re.DOTALL)
    if not match:
        raise ValueError(f"Nenhum JSON encontrado na resposta:\n{text[:300]}")

    return json.loads(match.group())


def pull_model(model: str = None) -> None:
    """Baixa o modelo se ainda nao estiver disponivel localmente."""
    model = model or DEFAULT_MODEL
    print(f"[LLM] Verificando modelo {model}...")
    r = requests.post(
        f"{OLLAMA_URL}{_PULL_ENDPOINT}",
        json={"name": model, "stream": False},
        timeout=600,
    )
    r.raise_for_status()
    print(f"[LLM] Modelo {model} pronto.")
