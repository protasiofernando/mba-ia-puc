# Documentação (comece por aqui)

Este é o índice único e canônico da pasta `docs/`; qualquer outro arquivo de
índice apenas aponta para cá. O experimento está concluído.

A síntese acadêmica, que reúne a questão de pesquisa, a fundamentação teórica,
a modelagem, os resultados, a discussão, as ameaças à validade, as conclusões e
as referências, está no
[`README.md` da raiz](../README.md). Esta pasta preserva o detalhamento técnico
e as evidências sem duplicar essa narrativa.

## Leitura mínima

1. `MANUAL_DO_PROJETO.md`: visão formal, arquitetura e desenho;
2. `RESULTADOS_COMPARACAO.md`: medições e conclusão;
3. `FLUXO_COMPLETO_MBA.md`: fluxo técnico de ponta a ponta;
4. `RESUMO_EXECUTIVO.md`: síntese do estado vigente;
5. `ESTADO_COMPARACAO_ROBUSTA.json`: estado estruturado;
6. `AUDITORIA_COERENCIA_PROJETO.md`: confronto entre história, scripts,
   alvos e resultados;
7. `APENDICE_TECNICO.md`: tentativas, falhas e correções;
8. `PUBLICACAO_NOVO_REPOSITORIO.md`: gate e sequência segura de publicação.

## Operação e código

- `README_TECNICO.md`: execução local, privacidade e validações.
- `MANUAL_HPC.md`: regras gerais do HPC.
- `GUIA_EXTRACAO_JIRA.md`: origem e preparação dos CSVs.
- `../estudo_comparativo/RUNBOOK_HPC.md`: reprodução controlada do estudo.
- `../estudo_comparativo/PROTOCOLO_METODOLOGICO.md`: protocolo estatístico.
- `../estudo_comparativo/DOSSIE_AUDITORIA.md`: justificativa dos controles.

## Fonte de verdade

- Resultado científico: `RESULTADOS_COMPARACAO.md`.
- Decisão operacional: `../formacao_portfolio/decisao_curada/feedback_portfolio.json`.
- Espelho analítico: `../formacao_portfolio/decisao_curada/portfolio_referencia.json`.
- Formação e precedência temporal do alvo: `../formacao_portfolio/README.md`.
- Estado de auditoria: `ESTADO_COMPARACAO_ROBUSTA.json`.
- Veredito de coerência pré-publicação: `AUDITORIA_COERENCIA_PROJETO.md`.
- Artefatos originais privados/locais: `../_hpc/resultado/`, fora do Git.
- Cópia publicável e versionável dos resultados: `../resultados_publicaveis/`.

Documentos históricos antes espalhados foram consolidados no apêndice. Nomes de
revisão e IDs de jobs aparecem somente onde são necessários à proveniência.
