# Estudo comparativo

Esta pasta contém o protocolo, as regras, os jobs PBS e os validadores da
comparação entre descoberta estatística e descoberta por LLM.

## Resultado

O estudo foi concluído sobre 1.456 chamados, após remoção determinística de 128
registros de Sala de Sigilo. A validação final passou em 302 checks, sem
falhas. A evidência primária favorece K-means, mas o resultado de aderência é
dependente de semente, camada e referência; não há vencedor global único. O
custo favorece o motor estatístico.

Leia primeiro:

1. `../docs/RESULTADOS_COMPARACAO.md`;
2. `../docs/FLUXO_COMPLETO_MBA.md`;
3. `PROTOCOLO_METODOLOGICO.md`;
4. `DOSSIE_AUDITORIA.md`;
5. `../docs/APENDICE_TECNICO.md`.

## Desenho

- Benchmark: duas arquiteturas completas, resultado descritivo.
- Ablação: somente o motor do Stage 3 varia; Stage 2, interface, Stages 4–6,
  alvo e avaliador são comuns.
- Motores: `bge-m3` + K-means e descoberta hierárquica por LLM.
- Seeds: 42, 31415 e 27182.
- Referência: consenso automático Llama+Qwen, em múltiplas visões.
- Alvo: portfólio curado adotado, não ground truth externa.

## Escopo

Sala de Sigilo continua visível no portal, mas é atendida pela Segurança da
Informação. Ela não entra em descoberta, prompts, métricas ou ranking. O filtro
usa o campo estruturado anterior ao Stage 1 e não usa LLM nem texto livre.

## Arquivos principais

- `experimento_config.json`: configuração congelada;
- `decision_rules_v1.json`: regras de decisão;
- `filtro_sala_sigilo_manifest_v6.json`: fronteira de escopo;
- `PROTOCOLO_METODOLOGICO.md`: desenho estatístico;
- `DOSSIE_AUDITORIA.md`: justificativa dos controles;
- `RUNBOOK_HPC.md`: reprodução controlada;
- `hpc/`: jobs PBS;
- `source/`: ponto privado de injeção do Stage 2 no HPC.

Não versionar CSV, Stage 1, Stage 2, checkpoints, logs, classificações por
chamado ou tar privado.
