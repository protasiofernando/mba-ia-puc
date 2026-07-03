#!/usr/bin/env python3
"""
Análise do ganho de tempo: resolução direta vs múltiplas interações.

Compara o tempo de resolução dos chamados atendidos de forma direta
(até 1 interação humana) com os que exigiram múltiplas interações
(2 ou mais trocas com o solicitante) — o mesmo conceito exibido na aba
Análise IA do dashboard.

Uma "interação humana" é um comentário cujo autor não é o robô de
automação do Jira (`automato`) — a mesma regra aplicada pelo script de
extração (`extracao/extrair_jira.py`). Comentários de automação não
representam troca com o solicitante e são ignorados.

O resultado quantifica o ganho de tempo de um chamado aberto já com as
informações completas — a evidência que motiva o assistente de triagem.

Uso:
  python analise_tempo_interacoes.py                        # CSVs reais em data/ ou JIRA_DATA_DIR
  python analise_tempo_interacoes.py --dados data_exemplo   # base sintética de exemplo

Os CSVs reais do Jira não são versionados (dados pessoais). A pasta
data_exemplo/ contém uma base fictícia com o mesmo schema, que permite
executar esta análise em qualquer clone do repositório.
"""

import argparse
import os
import sys

AUTOR_AUTOMACAO = "automato"


def _contar_interacoes_humanas(df, pd):
    """
    Conta, por chamado, os comentários cujo autor não é o robô de automação.

    O formato bruto de cada coluna Comentário é "data hora;autor;texto;...".
    Retorna None quando o CSV não traz as colunas Comentário (nesse caso o
    chamador usa a coluna qtd_interacoes já derivada).
    """
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
        description="Ganho de tempo: resolução direta vs múltiplas interações")
    parser.add_argument(
        "--dados",
        help="Pasta com os CSVs Extracao_Jira*.csv (padrão: data/ ou JIRA_DATA_DIR)",
    )
    args = parser.parse_args()

    if args.dados:
        # data_loader resolve o diretório no import — definir antes de importar
        os.environ["JIRA_DATA_DIR"] = args.dados

    import pandas as pd
    from data_loader import load_jira_data

    df = load_jira_data()

    interacoes = _contar_interacoes_humanas(df, pd)
    if interacoes is None:
        print("[AVISO] CSV sem colunas Comentário — usando qtd_interacoes derivada.")
        interacoes = df["qtd_interacoes"]

    # Apenas chamados com tempo de resolução válido (Resolvido posterior a Criado)
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
    print(f"Ganho de tempo da resolução direta: {100 * (1 - 1 / razao_mediana):.0f}% "
          f"(mediana) | {100 * (1 - 1 / razao_media):.0f}% (média)")


if __name__ == "__main__":
    main()
