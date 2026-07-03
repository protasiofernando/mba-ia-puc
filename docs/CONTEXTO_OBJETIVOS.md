# Contexto do Projeto — Triagem Inteligente de Chamados

## O que é este projeto

Sistema de análise e otimização do portfólio de serviços da DTI FGV (Diretoria de Tecnologia da Informação da Fundação Getulio Vargas). Usa IA para analisar o histórico de chamados de suporte, descobrir os padrões reais de demanda dos usuários e recomendar uma estrutura de categorias mais eficiente.

**Problema que resolve**: o portfólio de atendimento foi definido subjetivamente, sem embasamento em dados. Isso gera categorias sobrepostas, lacunas de cobertura e múltiplas interações de esclarecimento para resolver chamados simples.

## O que o projeto faz

1. **Extrai a intenção real** de cada chamado histórico via LLM — independentemente de como o usuário descreveu o problema ou da categoria atribuída manualmente. Também identifica se a descrição original foi insuficiente e exigiu perguntas adicionais do atendente (`descricao_insuficiente`).
2. **Descobre grupos naturais de demanda** agrupando chamados por similaridade semântica com embeddings `bge-m3`, sem partir das categorias existentes.
3. **Diagnostica o portfólio atual**: sobreposições, fragmentações, lacunas e nomenclaturas que dificultam a auto-seleção pelo usuário.
4. **Recomenda um portfólio otimizado** com categorias coesas, definição clara de escopo, campos obrigatórios a coletar e SLA por categoria.
5. **Aplica a curadoria da área**, quando existir, reclassificando os históricos no portfólio final definido em `feedback_portfolio.json`.
6. **Classifica novos chamados em tempo real** via LLM (Ollama local ou Azure OpenAI) sugerindo a categoria e os campos a preencher com base no portfólio ativo: Stage 7 curado quando presente; caso contrário, Stage 5/6 automático.

## O que o projeto NÃO é

- Não substitui o Jira nem é um sistema de helpdesk.
- Não classifica chamados automaticamente em produção — a classificação é uma ferramenta de apoio.
- Não gera respostas automáticas para usuários.
- Não requer LLM em produção: o pipeline pesado roda uma vez no HPC e os resultados são persistidos como JSON.

## Arquitetura em três camadas

**Camada 1 — Pipeline offline (HPC)**: executa uma vez, consome os CSVs do Jira e produz os JSONs de análise. Usa `gemma4:26b-q8` via Ollama local — nenhum dado sai da infraestrutura FGV.

**Camada 2 — Simulação de triagem (Python/LLM)**: o dashboard envia o chamado para classificação via LLM — Ollama local (gemma4:26b-q8, requer túnel SSH para o HPC) ou Azure OpenAI (gpt-4.1, requer configuração no `.env`). O modelo recebe o portfólio ativo como contexto e retorna categoria, justificativa e campos a coletar.

**Camada 3 — Dashboard web (Flask)**: consome os JSONs estáticos do pipeline e expõe visualizações, tabelas de categorias com mapeamento, simulação de triagem e a análise completa da IA.

## Pipeline genérico + curadoria da área

O projeto separa o que a máquina faz bem (descobrir padrões sem viés) do que só o dono da área sabe (o que é escopo, como nomear, o que encaminhar):

- **Stages 1–6 — genéricos e reaproveitáveis.** Dado um conjunto de chamados + o contexto da área (`infra_context`), descobrem os grupos naturais e **recomendam** um portfólio, sem curadoria humana embutida. Funcionam para qualquer portfólio de qualquer área — basta trocar os CSVs e o `infra_context`.
- **`feedback_portfolio.json` — curadoria humana.** Depois de revisar a recomendação automática, o dono da área define aqui o **portfólio final** (categorias definitivas com `quando_usar` rico), as **diretrizes** (ex: acesso classifica pelo ambiente), os serviços **fora do catálogo** (ex: SharePoint → "Não encontrou") e os **encaminhamentos** (ex: Sala de Sigilo → Segurança). É a única parte específica da área.
- **Stage 7 — finalização.** Lê a recomendação (Stage 5) + o feedback e **reclassifica os chamados históricos no portfólio final**, deixando o dashboard, a simulação, o histórico e o mapeamento consistentes com o que a área escolheu como ideal.

## Insumos principais

- **CSVs exportados do Jira** (dados históricos de chamados): título, descrição, categoria atribuída, status, timestamps, comentários. Não são versionados — contêm dados pessoais.
- **`config_portfolio.json`** (genérico): `infra_context.texto_contexto` — contexto da infraestrutura/serviços da área, injetado nos prompts do Stage 2 (por ticket) e Stage 5 (recomendação). `categorias_obrigatorias` — mantém apenas o catch-all universal ("Não encontrou o que procurava?"). Toda categoria fixa específica da área agora vive na curadoria (`feedback_portfolio.json`), não aqui.
- **`feedback_portfolio.json`** (curadoria da área): portfólio final + diretrizes + fora-do-catálogo + encaminhamentos. Consumido pelo Stage 7.

## Outputs persistidos

- `pipeline_data/04_labels.json` — grupos naturais rotulados com nome, quando_usar, campos obrigatórios e SLA. Usado pelo dashboard (abas Grupos Naturais e Análise IA).
- `pipeline_data/05_portfolio_recommendation.json` — análise completa automática: diagnóstico, mapeamento do portfólio atual para os grupos naturais, portfólio otimizado recomendado, ações prioritárias e impacto estimado.
- `pipeline_data/06_classificados.json` — chamados históricos reclassificados no portfólio recomendado automático; usado como fallback quando não há Stage 7.
- `pipeline_data/07_portfolio_final.json` — portfólio final curado pela área; quando existe, vira a fonte ativa do dashboard e da simulação.
- `pipeline_data/07_classificados_final.json` — chamados históricos reclassificados no portfólio curado; quando existe, vira a fonte ativa do histórico e do mapeamento.

Arquivos agregados podem ser versionados quando não contêm dados pessoais. Arquivos com classificação por chamado (`06_classificados.json`, `07_classificados_final.json`) são sensíveis e ficam fora do git.

## Decisões de design relevantes

- **LLM local no pipeline**: Ollama com modelo local no HPC. Nenhum dado de chamado enviado para APIs externas durante a análise histórica.
- **Azure OpenAI opcional na simulação**: a aba de simulação suporta Azure OpenAI (gpt-4.1) para classificação interativa. Apenas o título e a descrição do chamado digitado são enviados — nunca dados históricos. Credenciais configuradas via arquivo `.env` (não versionado).
- **Pipeline one-shot**: não é contínuo. Roda sob demanda no HPC, gera os JSONs e encerra.
- **Checkpoint no Stage 2**: a sumarização salva progresso a cada 10 tickets. Se interrompida, retoma do ponto exato. Apagar o checkpoint antes de rodar do zero.
- **`descricao_insuficiente` por LLM**: o Stage 2 analisa os comentários de cada chamado e marca se o atendente precisou solicitar informações adicionais ao usuário. Essa tag alimenta as métricas de qualidade de descrição no dashboard com maior precisão do que a simples contagem de interações.
- **Pipeline genérico, curadoria separada**: os Stages 1–6 não têm decisões específicas da área embutidas — toda curadoria (categorias finais, diretrizes, encaminhamentos, fora-do-catálogo) vive no `feedback_portfolio.json` e é aplicada pelo Stage 7. O app sempre prefere `07_*` quando esses arquivos estão presentes; se não estão, usa a recomendação automática dos Stages 5/6. Isso mantém o pipeline reaproveitável em qualquer área.
- **Privacidade por design**: arquivos com texto dos chamados são gitignored. Apenas outputs agregados são versionados.
