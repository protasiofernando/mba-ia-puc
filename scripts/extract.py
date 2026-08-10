#!/usr/bin/env python3
"""
Stage 1 - Extração e limpeza dos chamados (determinístico, sem LLM).

Lê os CSVs do portal, extrai os campos relevantes (título, descrição,
comentários de usuários E atendentes) e salva em formato estruturado que
alimenta o Stage 2 (sumarização feita por LLM local no HPC/Azure).

Entrada:  <projeto>/data/*.csv
Saída:    <projeto>/pipeline_data/01_tickets.json
Tempo:    ~segundos

Uso (a partir da pasta do projeto):
  python scripts/extract.py
"""

import sys
import json
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from data_loader import load_jira_data
from projeto import pipeline_data_dir


def clean_text(text: str, max_chars: int = None) -> str:
    """Remove HTML, URLs, e-mails e normaliza espaço."""
    if not text or str(text).strip() in ("nan", "None", ""):
        return ""
    text = str(text)
    text = re.sub(r"<[^>]+>", " ", text)                 # HTML tags
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)   # URLs
    text = re.sub(r"\S+@\S+\.\S+", " ", text)            # e-mails
    text = re.sub(r"mailto:\S+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if max_chars:
        text = text[:max_chars]
    return text


def titulo_seguro(titulo: str, descricao: str, comentarios: str, tipo_atual: str) -> tuple[str, bool]:
    """Garante um titulo util mesmo quando a limpeza removeu PII do resumo."""
    if titulo:
        return titulo, False
    for candidato in (descricao, comentarios, tipo_atual):
        if candidato and candidato != "Não categorizado":
            return candidato[:120].strip(), True
    return "", False


def extract_ticket(row) -> dict:
    """Extrai os campos relevantes de uma linha do DataFrame."""
    titulo = clean_text(row.get("Resumo", ""))
    descricao = clean_text(row.get("Descricao", "") or row.get("Descrição", ""), max_chars=4000)
    comentarios = clean_text(row.get("comentarios_usuarios", ""), max_chars=6000)
    tipo_atual = clean_text(row.get("Customer Request Type", "")) or "Não categorizado"
    situacao = clean_text(row.get("Situação", "") or row.get("Situacao", ""))
    chave = str(row.get("Chave do item", "")).strip()
    titulo, usou_titulo_fallback = titulo_seguro(titulo, descricao, comentarios, tipo_atual)

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
        "_titulo_fallback": usou_titulo_fallback,
    }


def main():
    output_file = pipeline_data_dir() / "01_tickets.json"

    print("[Stage 1] Carregando chamados dos CSVs...")
    df = load_jira_data()

    tickets = []
    sem_conteudo = 0
    titulos_fallback = 0
    for _, row in df.iterrows():
        t = extract_ticket(row)
        titulos_fallback += 1 if t.pop("_titulo_fallback", False) else 0
        if not t["texto_completo"]:
            sem_conteudo += 1
            continue
        tickets.append(t)

    com_desc = sum(1 for t in tickets if t["descricao"])
    com_coment = sum(1 for t in tickets if t["comentarios"])
    categorias = len(set(t["tipo_atual"] for t in tickets))

    print(f"[Stage 1] {len(tickets)} chamados extraídos ({sem_conteudo} ignorados por conteudo vazio)")
    print(f"[Stage 1] Titulos reconstruidos apos limpeza de PII: {titulos_fallback}")
    print(f"[Stage 1] Com descrição:   {com_desc} ({com_desc/max(len(tickets),1)*100:.1f}%)")
    print(f"[Stage 1] Com comentários: {com_coment} ({com_coment/max(len(tickets),1)*100:.1f}%)")
    print(f"[Stage 1] Categorias atuais únicas: {categorias}")

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(tickets, f, ensure_ascii=False, indent=2)

    print(f"[Stage 1] Salvo em: {output_file}")
    return tickets


if __name__ == "__main__":
    main()
