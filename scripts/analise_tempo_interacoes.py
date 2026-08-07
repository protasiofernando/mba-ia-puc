#!/usr/bin/env python3
"""
Análise descritiva do tempo: resolução direta vs múltiplas interações.

Compara o tempo de resolução dos chamados atendidos de forma direta (até 1
interação humana) com os que exigiram múltiplas interações (2+ trocas com o
solicitante). A associação motiva o assistente de triagem, mas não estima o
efeito causal de abrir o chamado na categoria certa ou com descrição completa.
Complexidade, prioridade, equipe, período e tipo de demanda podem confundir a
diferença observada.

Uma "interação humana" é um comentário cujo autor não é o robô de automação do
Jira (`automato`). Comentários de automação são ignorados.

Uso (a partir da pasta do projeto):
  python scripts/analise_tempo_interacoes.py
  python scripts/analise_tempo_interacoes.py --dados "C:\\outra\\pasta\\csvs"
"""

import argparse
import os
import sys
from pathlib import Path

AUTOR_AUTOMACAO = "automato"


def _contar_interacoes_humanas(df, pd):
    cols = [c for c in df.columns
            if c.strip() == "Comentário" or c.strip().startswith("Comentário.")]
    if not cols:
        return None

    def conta(row):
        n = 0
        for valor in row:
            if pd.isna(valor):
                continue
            texto = str(valor).strip()
            if not texto:
                continue
            partes = texto.split(";")
            autor = partes[1].strip().lower() if len(partes) > 1 else ""
            if autor and autor != AUTOR_AUTOMACAO:
                n += 1
        return n

    return df[cols].apply(conta, axis=1)


def main():
    parser = argparse.ArgumentParser(
        description="Associação entre tempo e número de interações")
    parser.add_argument(
        "--dados",
        help="Pasta com os CSVs (padrão: <projeto>/data ou JIRA_DATA_DIR)",
    )
    args = parser.parse_args()

    if args.dados:
        # data_loader resolve o diretório via JIRA_DATA_DIR - definir antes de importar
        os.environ["JIRA_DATA_DIR"] = args.dados

    sys.path.insert(0, str(Path(__file__).parent))
    import pandas as pd
    from data_loader import load_jira_data

    df = load_jira_data()

    interacoes = _contar_interacoes_humanas(df, pd)
    if interacoes is None:
        print("[AVISO] CSV sem colunas Comentário - usando qtd_interacoes derivada.")
        interacoes = df["qtd_interacoes"]

    df = df.assign(interacoes_humanas=interacoes)
    validos = df[df["Tempo total conclusão"] > 0].copy()
    validos["dias"] = validos["Tempo total conclusão"] / 24.0

    diretos = validos.loc[validos["interacoes_humanas"] <= 1, "dias"]
    multiplos = validos.loc[validos["interacoes_humanas"] >= 2, "dias"]

    print()
    print(f"Chamados carregados: {len(df)} | com tempo de resolução válido: {len(validos)}")
    print()

    if diretos.empty or multiplos.empty:
        print("Grupos insuficientes para comparação (é preciso haver chamados nos dois grupos).")
        sys.exit(1)

    for nome, grupo in (("Resolução direta (<=1 interação humana)", diretos),
                        ("Múltiplas interações (>=2)", multiplos)):
        print(f"{nome:40s} | n={len(grupo):5d} | média={grupo.mean():7.1f} dias "
              f"| mediana={grupo.median():6.1f} dias")

    razao_media = multiplos.mean() / diretos.mean()
    razao_mediana = multiplos.median() / diretos.median()

    print()
    print(f"Razão das médias   (múltiplas/direta): {razao_media:.2f}x "
          f"(=> +{100 * (razao_media - 1):.0f}% mais lento)")
    print(f"Razão das medianas (múltiplas/direta): {razao_mediana:.2f}x "
          f"(=> +{100 * (razao_mediana - 1):.0f}% mais lento)")
    print()
    if razao_mediana > 0 and razao_media > 0:
        print(f"Diferença descritiva associada à resolução direta: "
              f"{100 * (1 - 1 / razao_mediana):.0f}% (mediana) | "
              f"{100 * (1 - 1 / razao_media):.0f}% (média)")
        print("Ressalva: associação observacional; não interpretar como ganho causal.")


if __name__ == "__main__":
    main()
