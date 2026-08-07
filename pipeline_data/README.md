# Artefatos agregados do pipeline aplicado

Esta pasta contém apenas agregados permitidos para versionamento. Ela não é a
fonte do alvo do estudo comparativo e não contém os dados por chamado usados na
execução final.

Os arquivos `04_labels.json`, `05_portfolio_recommendation.json`,
`06_quality_report.json` e `diagnostico_executivo.json` pertencem à execução
operacional da arquitetura agêntica sobre os 1.456 chamados do universo
analítico. Eles documentam o diagnóstico e a recomendação automática antes da
aplicação do catálogo curado; não são os placares do estudo comparativo.

Não use esses agregados para:

- calcular as métricas finais da comparação;
- inferir que a recomendação automática foi a decisão adotada.

A decisão operacional está em
`formacao_portfolio/decisao_curada/feedback_portfolio.json`; seu espelho
analítico está em `formacao_portfolio/decisao_curada/portfolio_referencia.json`.
Os resultados finais do estudo estão em `resultados_publicaveis/`.

Os artefatos privados `01_tickets.json`, `02_summaries.json`,
`03_clusters.json`, `06_classificados.json`, checkpoints e telemetria bruta
permanecem fora do Git. O arquivo `07_portfolio_final.json` só deve ser gerado
quando o Estágio 7 automático for executado sobre um insumo privado válido. Essa
execução foi concluída sobre os 1.456 chamados: o agregado publicável registra
oito categorias analíticas, com Sala de Sigilo visível mas fora da análise. O
arquivo `07_classificados_final.json`, por conter dados por chamado, permanece
ignorado e não deve ser enviado ao Git.

Os volumes de `07_portfolio_final.json` são uma projeção automática
retrospectiva no catálogo adotado. Não representam uso observado depois da
implantação nem alteram o resultado metodológico do Job 90.
