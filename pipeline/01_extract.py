#!/usr/bin/env python3
"""
Stage 1 — Extracao e limpeza dos tickets.

Le os CSVs do Jira, extrai os campos relevantes (titulo, descricao,
comentarios de usuarios E atendentes) e salva em formato estruturado.

Saida: pipeline_data/01_tickets.json
Tempo estimado: ~30 segundos
"""

import sys
import json
import re
import unicodedata
from pathlib import Path

# Permite importar modulos do diretorio pai (projeto/)
sys.path.insert(0, str(Path(__file__).parent.parent))
from data_loader import load_jira_data

PIPELINE_DATA = Path(__file__).parent.parent / "pipeline_data"
OUTPUT_FILE = PIPELINE_DATA / "01_tickets.json"


def clean_text(text: str, max_chars: int = None) -> str:
    """Remove HTML, URLs, caracteres especiais e normaliza espaco."""
    if not text or str(text).strip() in ("nan", "None", ""):
        return ""
    text = str(text)
    text = re.sub(r"<[^>]+>", " ", text)           # HTML tags
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)  # URLs
    text = re.sub(r"\S+@\S+\.\S+", " ", text)       # e-mails
    text = re.sub(r"mailto:\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars:
        text = text[:max_chars]
    return text


def extract_ticket(row) -> dict:
    """
    Extrai os campos relevantes de uma linha do DataFrame.

    Campos extraidos:
      - titulo, descricao: pedido original do usuario
      - comentarios: toda a conversa (usuario + atendente)
      - tipo_atual: categoria cadastrada no Jira (Customer Request Type)
      - situacao, qtd_interacoes, data_criacao: metadados
    """
    titulo = clean_text(row.get("Resumo", ""))
    descricao = clean_text(row.get("Descricao", "") or row.get("Descrição", ""), max_chars=1200)
    comentarios = clean_text(row.get("comentarios_usuarios", ""), max_chars=1000)
    tipo_atual = clean_text(row.get("Customer Request Type", "")) or "Nao categorizado"
    situacao = clean_text(row.get("Situação", "") or row.get("Situacao", ""))
    chave = str(row.get("Chave do item", "")).strip()

    # Texto consolidado para analise
    partes = [p for p in [titulo, descricao, comentarios] if p]
    texto_completo = " | ".join(partes)

    return {
        "chave": chave,
        "titulo": titulo,
        "descricao": descricao,
        "comentarios": comentarios,
        "texto_completo": texto_completo,
        "tipo_atual": tipo_atual,
        "situacao": situacao,
        "qtd_interacoes": int(row.get("qtd_interacoes", 0) or 0),
        "data_criacao": str(row.get("Criado", "") or ""),
    }


def main():
    PIPELINE_DATA.mkdir(parents=True, exist_ok=True)

    print("[Stage 1] Carregando tickets dos CSVs...")
    df = load_jira_data()

    tickets = []
    sem_titulo = 0

    for _, row in df.iterrows():
        t = extract_ticket(row)
        if not t["titulo"]:
            sem_titulo += 1
            continue
        tickets.append(t)

    # Estatisticas
    com_desc = sum(1 for t in tickets if t["descricao"])
    com_coment = sum(1 for t in tickets if t["comentarios"])
    categorias = len(set(t["tipo_atual"] for t in tickets))

    print(f"[Stage 1] {len(tickets)} tickets extraidos ({sem_titulo} ignorados por titulo vazio)")
    print(f"[Stage 1] Com descricao:   {com_desc} ({com_desc/len(tickets)*100:.1f}%)")
    print(f"[Stage 1] Com comentarios: {com_coment} ({com_coment/len(tickets)*100:.1f}%)")
    print(f"[Stage 1] Categorias atuais unicas: {categorias}")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)

    print(f"[Stage 1] Salvo em: {OUTPUT_FILE}")
    return tickets


if __name__ == "__main__":
    main()
