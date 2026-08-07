#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cliente LLM para o pipeline (Stages 2-6) - roda FORA do Claude.

Detecta o provedor pelo .env do projeto e expoe chat_json(system, user) -> dict:
  - Ollama (local)  : OLLAMA_MODEL (+ OLLAMA_BASE_URL, padrao http://localhost:11434)
  - Azure OpenAI    : AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT (+ DEPLOYMENT)
  - OpenAI padrao   : OPENAI_API_KEY (+ PIPELINE_OPENAI_MODEL, padrao gpt-4o-mini)

Force o provedor com PIPELINE_LLM_PROVIDER=ollama|azure|openai.
Usa apenas 'requests' (ja e dependencia). Todos via API compativel com OpenAI
(/v1/chat/completions) + JSON mode + retries com backoff.
"""
import os
import json
import time
import random
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).parent))
from projeto import projeto_dir

try:
    from dotenv import load_dotenv
    load_dotenv(projeto_dir() / ".env")
except Exception:
    pass


class LLMError(Exception):
    pass


_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": ", ",
    "\u2013": ", ",
    "\u2014": ", ",
    "\u2015": ", ",
    "\u2212": "-",
    "\u2e3a": ", ",
    "\u2e3b": ", ",
})
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}

# Telemetria de custo (metrica 7 da comparacao justa). Se OLLAMA_METRICS_FILE
# estiver definido, cada chamada bem-sucedida grava tokens (campo `usage` do
# endpoint OpenAI-compat) e duracao (r.elapsed) por stage (via env PIPELINE_STAGE)
# num JSONL. Nunca interfere na chamada: qualquer erro de log e silenciado.
_METRICS_FILE = os.getenv("OLLAMA_METRICS_FILE")


def _log_metrics(model: str, kind: str, data: dict, elapsed_s: float) -> None:
    if not _METRICS_FILE:
        return
    try:
        usage = (data or {}).get("usage") or {}
        rec = {
            "ts": time.time(),
            "stage": os.getenv("PIPELINE_STAGE", ""),
            "model": model,
            "kind": kind,
            "prompt_eval_count": usage.get("prompt_tokens"),
            "eval_count": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
            "elapsed_s": round(float(elapsed_s or 0), 3),
        }
        with open(_METRICS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _sanitize_text(text: str) -> str:
    return text.translate(_DASH_TRANSLATION)


def _sanitize_json(value):
    if isinstance(value, str):
        return _sanitize_text(value)
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _sanitize_json(item) for key, item in value.items()}
    return value


class LLMClient:
    def __init__(
        self,
        provider_override: str | None = None,
        model_override: str | None = None,
    ):
        forcar = (
            provider_override
            if provider_override is not None
            else (os.getenv("PIPELINE_LLM_PROVIDER", "") or "")
        ).strip().lower()
        az_key = os.getenv("AZURE_OPENAI_API_KEY", "").strip()
        az_ep = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
        oa_key = os.getenv("OPENAI_API_KEY", "").strip()
        oll_model = (model_override or os.getenv("OLLAMA_MODEL", "")).strip()

        tem_azure = bool(az_key and az_ep)
        tem_openai = bool(oa_key)
        tem_ollama = bool(oll_model)

        if forcar == "ollama" or (not forcar and tem_ollama and not tem_azure and not tem_openai):
            provider = "ollama"
        elif forcar == "azure" or (not forcar and tem_azure):
            provider = "azure"
        elif forcar == "openai" or (not forcar and tem_openai):
            provider = "openai"
        elif tem_ollama:
            provider = "ollama"
        else:
            raise LLMError(
                "Nenhuma credencial/modelo LLM encontrado no .env do projeto.\n"
                "Configure OLLAMA_MODEL (Ollama local), OPENAI_API_KEY (OpenAI) ou "
                "AZURE_OPENAI_API_KEY + AZURE_OPENAI_ENDPOINT (Azure). Veja .env.example."
            )

        self.provider = provider
        self.timeout = int(os.getenv("LLM_TIMEOUT", "90"))
        if provider == "ollama":
            if not oll_model:
                raise LLMError(
                    "PIPELINE_LLM_PROVIDER=ollama mas OLLAMA_MODEL esta vazio no .env.\n"
                    "Defina o modelo baixado na GPU (ex.: OLLAMA_MODEL=llama3.3:70b) e, se "
                    "o Ollama estiver em outra maquina, ajuste OLLAMA_BASE_URL."
                )
            base = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
            self.model = oll_model
            self.url = f"{base}/v1/chat/completions"
            self.headers = {"Authorization": "Bearer ollama", "Content-Type": "application/json"}
            self.model_label = f"ollama:{self.model}"
            self.timeout = int(os.getenv("OLLAMA_TIMEOUT", "600"))
        elif provider == "azure":
            self.deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4.1")
            self.api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2025-01-01-preview")
            self.url = (f"{az_ep}/openai/deployments/{self.deployment}"
                        f"/chat/completions?api-version={self.api_version}")
            self.headers = {"api-key": az_key, "Content-Type": "application/json"}
            self.model_label = f"azure:{self.deployment}"
        else:  # openai
            self.model = os.getenv("PIPELINE_OPENAI_MODEL", "gpt-4o-mini")
            base = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
            self.url = f"{base}/chat/completions"
            self.headers = {"Authorization": f"Bearer {oa_key}", "Content-Type": "application/json"}
            self.model_label = f"openai:{self.model}"

    def chat_json(self, system: str, user: str, temperature: float = 0.0,
                  max_tokens: int = 700, max_retries: int = 6, timeout: int = None) -> dict:
        body = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        if self.provider in ("openai", "ollama"):
            body["model"] = self.model
        to = timeout or self.timeout

        last = None
        for tent in range(max_retries):
            try:
                r = requests.post(self.url, headers=self.headers, json=body, timeout=to)
                if r.status_code in _RETRYABLE_STATUS:
                    last = f"HTTP {r.status_code}"
                    espera = min(60, (2 ** tent)) + random.uniform(0, 1.5)
                    ra = r.headers.get("retry-after")
                    if ra:
                        try:
                            espera = max(espera, float(ra))
                        except ValueError:
                            pass
                    time.sleep(espera)
                    continue
                if r.status_code >= 400:
                    detail = _sanitize_text(r.text[:500]).strip()
                    raise LLMError(
                        f"HTTP {r.status_code} nao retentavel"
                        + (f": {detail}" if detail else "")
                    )
                r.raise_for_status()
                data = r.json()
                _log_metrics(self.model_label, "chat_json", data, r.elapsed.total_seconds())
                content = data["choices"][0]["message"]["content"]
                return _sanitize_json(json.loads(_sanitize_text(content)))
            except (requests.RequestException, KeyError, ValueError, json.JSONDecodeError) as e:
                last = str(e)
                time.sleep(min(30, (2 ** tent)) + random.uniform(0, 1.0))
        raise LLMError(f"Falha apos {max_retries} tentativas: {last}")

    def chat_text(self, system: str, user: str, temperature: float = 0.0,
                  max_tokens: int = 700, max_retries: int = 6, timeout: int = None) -> str:
        body = {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if self.provider in ("openai", "ollama"):
            body["model"] = self.model
        to = timeout or self.timeout

        last = None
        for tent in range(max_retries):
            try:
                r = requests.post(self.url, headers=self.headers, json=body, timeout=to)
                if r.status_code in _RETRYABLE_STATUS:
                    last = f"HTTP {r.status_code}"
                    espera = min(60, (2 ** tent)) + random.uniform(0, 1.5)
                    ra = r.headers.get("retry-after")
                    if ra:
                        try:
                            espera = max(espera, float(ra))
                        except ValueError:
                            pass
                    time.sleep(espera)
                    continue
                if r.status_code >= 400:
                    detail = _sanitize_text(r.text[:500]).strip()
                    raise LLMError(
                        f"HTTP {r.status_code} nao retentavel"
                        + (f": {detail}" if detail else "")
                    )
                r.raise_for_status()
                data = r.json()
                _log_metrics(self.model_label, "chat_text", data, r.elapsed.total_seconds())
                return _sanitize_text(str(data["choices"][0]["message"]["content"]))
            except (requests.RequestException, KeyError, ValueError) as e:
                last = str(e)
                time.sleep(min(30, (2 ** tent)) + random.uniform(0, 1.0))
        raise LLMError(f"Falha apos {max_retries} tentativas: {last}")


_client = None


def get_client() -> "LLMClient":
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
