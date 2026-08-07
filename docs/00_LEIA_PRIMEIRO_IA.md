# Estado resumido do projeto

Este documento apresenta uma síntese do projeto `mba-ia-masterbi-puc`. O
experimento está concluído e não há execução pendente. Uma nova execução somente
se justifica se houver alteração nos dados, métodos, modelos ou na pergunta de
pesquisa.

## Estado em uma frase

A comparação sobre 1.456 chamados foi concluída no A100, passou em 302 verificações
sem falhas e não encontrou um vencedor global único de aderência: a evidência
primária favorece K-means, mas o resultado varia com semente, camada e visão de
referência; o custo favorece o motor estatístico e o portfólio curado permanece
a decisão operacional. Depois do estudo, o Estágio 7 projetou automaticamente os
1.456 chamados nesse portfólio; sua distribuição agregada é publicável e a
classificação por chamado permanece privada.

## Leitura mínima

1. `MANUAL_DO_PROJETO.md`: identidade, arquitetura e desenho do estudo;
2. `RESULTADOS_COMPARACAO.md`: medições e conclusão;
3. `FLUXO_COMPLETO_MBA.md`: explicação técnica dos Estágios e jobs;
4. `AUDITORIA_COERENCIA_PROJETO.md`: confronto entre narrativa, código e evidência;
5. `ESTADO_COMPARACAO_ROBUSTA.json`: estado e linhagem máquina-legíveis;
6. `APENDICE_TECNICO.md`: tentativas invalidadas e correções.

## Fatos congelados

- Universo bruto: 1.584 chamados.
- Escopo de Sala removido antes do Estágio 1: 128 registros, todos com o request
  type legado `Solicitação de Acesso a Bases de Dados`, do fluxo de dados
  confidenciais/Sala de Sigilo atendido fora da DTI Pesquisa pela equipe de
  Banco de Dados, sem LLM e sem texto livre. Esse rótulo não é o
  serviço curado homônimo de acesso comum a bases fora da Sala.
- Universo analítico: 1.456 chamados.
- Estágio 2: SHA-256
  `e4fb8e41c910f8f2ed6151d8e69515ae8fd1b01f1310d47fa680d4403fd54ff1`.
- Portfólio curado: decisão operacional adotada, não referência externa
  independente.
- Sala de Sigilo: visível e imutável no portal, atendida pela Segurança da
  Informação e fora de descoberta, métricas e ranking.
- Pré-registro: a proveniência interna é preservada por hashes, manifestos e
  timestamps, mas o commit-raiz público reúne regras e resultados e não funciona
  como comprovação temporal externa da anterioridade das regras.
- Referência por chamado: automática, por consenso Llama+Qwen; não houve
  rotulação humana individual.
- Job 90 final: `2234.HPCGPU`, `Exit_status=0`, walltime `00:01:04`.
- `VALIDACAO_RESULTS.json`: `PASS`, 302 verificações, zero falhas.
- Estágio 7 operacional: 1.456 classificações automáticas, oito categorias
  analíticas, zero Sala de Sigilo; agregado em
  `pipeline_data/07_portfolio_final.json`.

## Resultado

Há dois estimandos e eles não podem ser misturados:

- benchmark de arquiteturas completas: resultado dependente da camada;
- ablação justa do motor de descoberta: resultado dependente da camada.

Na evidência primária, K-means apresenta melhor aderência. Isso não autoriza a
conclusão de que o método venceu globalmente, porque a vantagem não é invariável
entre sementes, camadas e referências. O custo foi classificado como
`custo_convergente_estatistico`.

Também não há evidência para atribuir especificamente ao Estágio 5 uma eventual
vantagem do pipeline agêntico: os Estágios 4–6 formam a camada semântica comum e
não houve ablação isolada do Estágio 5.

## Artefatos finais

- ZIP executado: `_hpc/pacote/mba-ia-puc_rev6_20260803.zip`, SHA-256
  `a2896c3e46f0b8d6dc90660a8715bf719effcfd55af4964e3486cb9283b1967c`.
- Tar público: `_hpc/resultado/comparacao_publicavel_20260804_131120.tar.gz`,
  SHA-256
  `f476e4103044ee0cc578597523689cbafaf7b2b164fa720a5078808bc4545be6`.
- Tar privado: `_hpc/resultado/comparacao_privada_20260804_131120.tar.gz`,
  SHA-256
  `a8c66f9a1923c98a5756566040b1b8f216c586d46ed9f3d3a933641e741053eb`.

O tar privado contém dados por chamado: não versionar, não anexar à monografia
e não enviar a serviços externos.

## Mapa do repositório

```text
scripts/                    pipeline, validações e runners gerais
scripts/hpc/                runner PBS do pipeline operacional
dashboard/                  aplicação Flask local
configuracao/               identidade, contexto institucional e catálogo real
data/                       CSVs sensíveis, fora do Git
pipeline_data/              agregados operacionais permitidos
formacao_portfolio/          linhagem, formação e decisão curada congelada
estudo_comparativo/         protocolo, jobs PBS e regras do estudo
metodo_estatistico/         motor usado na formação e reexecutado na comparação
resultados_publicaveis/     métricas e validações agregadas, seguras para Git
docs/                       narrativa, resultado, estado e apêndice
_hpc/                       pacote, manifesto e resultados transferidos
```

O antigo `job_triagem.sh` está em `scripts/hpc/job_pipeline.sh`. O antigo
`job_preparar_stage12_comparacao_v6.sh` está em
`estudo_comparativo/hpc/job_preparar_insumo.sh`. A mudança é organizacional;
os caminhos originais executados permanecem no estado JSON e no apêndice.

## Regras invioláveis

- não reutilizar o Estágio 2 de 1.584 registros;
- não inserir Sala de Sigilo no universo analítico;
- não tratar o portfólio curado como referência humana independente;
- não publicar CSV, Estágio 1, Estágio 2, checkpoints, chaves ou texto por chamado;
- não reconstruir uma conclusão diferente a partir de tentativas parciais;
- separar custo de aderência e medição de interpretação.

## Situação de encerramento

O trabalho computacional e a publicação foram concluídos. O gate de coerência passou
em 49 verificações, e o gate integral passou sobre 163 arquivos e 39 testes. A árvore
code-only validada ocupa a `main` de
`protasiofernando/mba-ia-puc` em um único commit-raiz. O repositório de entrega
não possui histórico anterior, branch de arquivo ou tag; os repositórios
reaproveitados permanecem separados e não integram a publicação final. Não há
ação computacional pendente. Uma nova rodada só é necessária se dados, método,
modelos ou pergunta de pesquisa mudarem.

A precedência do alvo está formalizada em `../formacao_portfolio/README.md`:
candidato estatístico, curadoria humana no catálogo, alvo congelado e só então
comparação dos dois métodos. A execução posterior do Estágio 7 foi uma
materialização operacional e não altera o estudo já concluído.
