#!/usr/bin/env python3
"""Contrato unico dos campos permitidos na descoberta de grupos."""

import hashlib
from collections import OrderedDict


DISCOVERY_CONTRACT_VERSION = "discovery-common-fields-v2"
DISCOVERY_FIELDS = ("intencao", "tema", "tipo_pedido")
ROUNDTRIP_IDENTIFIER_POLICY = "sha256-domain-separated-128-v1"


def _text(value) -> str:
    if isinstance(value, list):
        return " ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def opaque_roundtrip_id(key: str) -> str:
    """Cria um identificador tecnico sem sinal sequencial da chave Jira."""
    normalized = str(key or "").strip()
    if not normalized:
        raise ValueError("chave vazia nao pode gerar identificador opaco")
    digest = hashlib.sha256(
        b"stage3-roundtrip-id-v1\x00" + normalized.encode("utf-8")
    ).hexdigest()
    return f"rid_{digest[:32]}"


def discovery_payload(item: dict, include_key: bool = True) -> OrderedDict:
    output = OrderedDict()
    if include_key:
        output["chave"] = str(item.get("chave", "")).strip()
    for field in DISCOVERY_FIELDS:
        output[field] = _text(item.get(field))
    return output
