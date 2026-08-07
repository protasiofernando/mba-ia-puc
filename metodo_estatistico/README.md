# Baseline estatístico usado pela comparação robusta

Este diretório não é um pipeline operacional, um dashboard nem um arquivo
histórico de resultados. Ele contém somente a implementação mínima necessária
ao braço `m1_legacy_llama` do benchmark downstream descrito em
`estudo_comparativo/PROTOCOLO_METODOLOGICO.md`.

Arquivos executados:

- `pipeline/03_cluster.py`: embeddings `bge-m3` e K-means;
- `pipeline/04_label_clusters.py`;
- `pipeline/05_compare_portfolio.py`;
- `pipeline/06_classify_portfolio.py`;
- `pipeline/llm_client.py`;
- `config_portfolio.json`.

O Stage 2 não é gerado aqui. O job robusto copia para `pipeline_data/` o mesmo
`02_summaries.json` filtrado usado por todos os braços. O job também fixa
`OLLAMA_MODEL=llama3.3:70b`; não há Stage 7, dashboard ou resultado antigo
neste diretório.

Não execute esses módulos diretamente a partir do repositório local. O ponto de
entrada controlado é `estudo_comparativo/hpc/job_10_m1_legado_llama.sh`, dentro
do ZIP versionado do experimento.
