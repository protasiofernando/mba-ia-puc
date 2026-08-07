# Snapshot do método inicial

Esta pasta é uma cópia **exata e somente leitura** dos arquivos relevantes do
commit público `a5576c83d47e9eda7e6087b59e57bac65c04e1b4`, de 3 de julho de
2026, no repositório
`https://github.com/protasiofernando/mba-ia-masterbi-puc`.

Ela existe para provar qual processo formou o primeiro portfólio recomendado:

1. `pipeline/03_cluster.py`: embeddings `bge-m3` + K-means, com K escolhido por
   silhouette score;
2. `pipeline/04_label_clusters.py`: rotulação dos grupos por LLM;
3. `pipeline/05_compare_portfolio.py`: recomendação automática;
4. `pipeline_data/05_portfolio_recommendation.json`: resultado automático de
   dez itens;
5. `feedback_portfolio.json`: curadoria humana para sete categorias;
6. `pipeline/07_finalize_portfolio.py` e `hpc/run_stage7.sh`: aplicação
   automática da decisão humana;
7. `pipeline_data/07_portfolio_final.json`: resultado agregado materializado.

Não altere estes arquivos para corrigir ou modernizar o projeto. A versão
mantida está fora do snapshot, em `../../metodo_estatistico/`, `../../scripts/`
e `../hpc/`. Qualquer correção deve ocorrer nesses caminhos atuais.

O snapshot não contém CSVs, textos por chamado, checkpoints, banco ou segredo.
Os JSONs incluídos são agregados públicos que já estavam no GitHub.

Para verificar a integridade sem rede:

```powershell
python formacao_portfolio\verificar_snapshot.py
```

Com o histórico Git disponível, o mesmo comando também confere cada arquivo
contra o blob do commit de origem.
