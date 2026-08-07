# Status do projeto

Atualizado em 7 de agosto de 2026.

## Situação

| Item | Estado |
|---|---|
| Pipeline e escopo | concluídos |
| Universo analítico | 1.456 chamados |
| Escopo de Sala de Sigilo | 128 registros do request type legado homônimo removidos; item preservado no portal |
| Comparação | concluída |
| Job 90 | `2234.HPCGPU`, `F/exit 0`, `00:01:04` |
| Validação final | `PASS`, 302 checks, zero falhas |
| Resultado global de aderência | não único; dependente da camada |
| Evidência primária | favorece K-means |
| Custo | favorece o motor estatístico |
| Decisão operacional | portfólio curado |
| Stage 7 operacional | concluído; 1.456 classificações automáticas, agregado publicável |
| Jobs pendentes | nenhum |
| Formação e curadoria | processo e runners formalizados em `formacao_portfolio/` |
| Auditoria de coerência | `PASS`, 49 checks, zero falhas/avisos |
| Gate integral pré-publicação | `PASS`, 163 arquivos, 39 testes |
| Pré-registro público | proveniência interna disponível; anterioridade não atestada por timestamp externo |

## Entregáveis

- Resultado formal: `docs/RESULTADOS_COMPARACAO.md`.
- Fluxo técnico: `docs/FLUXO_COMPLETO_MBA.md`.
- Manual: `docs/MANUAL_DO_PROJETO.md`.
- Linhagem: `docs/APENDICE_TECNICO.md`.
- Estado estruturado: `docs/ESTADO_COMPARACAO_ROBUSTA.json`.
- Resultado público versionável: `resultados_publicaveis/`.
- Projeção operacional agregada do Stage 7:
  `pipeline_data/07_portfolio_final.json`.
- Evidência original local/privada: `_hpc/resultado/`, fora do Git.
- Gate de publicação: `docs/PUBLICACAO_NOVO_REPOSITORIO.md`.

## Interpretação autorizada

O estudo mostra que K-means é a alternativa mais econômica e recebe o sinal
mais favorável na evidência primária. A banca não deve receber a alegação de
“vencedor absoluto”: as conclusões formais do benchmark e da ablação são
dependentes da camada e a referência automática mede aderência ao portfólio
curado, não acurácia contra verdade externa.

O portfólio adotado continua sendo o curado pela área porque sua seleção inclui
governança, responsabilidade técnica, navegação e visibilidade de serviços. A
comparação informa essa decisão; não a substitui.

Sua linhagem é: candidato formado inicialmente pelo Método Estatístico,
curadoria humana no nível do catálogo, congelamento do alvo e reexecução dos
dois métodos na comparação. Não houve rotulagem humana por chamado.

Depois do encerramento da comparação, o Stage 7 classificou automaticamente os
1.456 chamados no catálogo congelado. Essa materialização produziu volumes
operacionais retrospectivos, não alterou o alvo nem as métricas do Job 90 e não
mede adoção futura do portal. O agregado pode ser versionado; a classificação
por chamado permanece privada.

## Próximo passo

Não há execução pendente. Preservar a evidência publicada e não reexecutar a
cadeia, salvo mudança de dados, método, modelos ou pergunta de pesquisa.
