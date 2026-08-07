# Runbook HPC do estudo comparativo

O experimento foi concluído. Este runbook existe para auditoria e reprodução
controlada, não como fila de trabalho pendente. O resultado válido está em
`../docs/RESULTADOS_COMPARACAO.md`.

## 1. Condições para uma nova execução

Não reexecute apenas para regenerar tabelas ou documentos. Uma nova rodada só
se justifica se houver alteração de dados, método, modelos, portfólio-alvo ou
pergunta de pesquisa. Nesse caso:

- use workspace novo;
- gere pacote code-only novo;
- execute novo Job 00;
- rode todos os oito braços;
- finalize com novo Job 90;
- não reutilize checkpoints ou outputs de outra execução.

## 2. Insumos congelados

| Insumo | Identidade |
|---|---|
| Universo analítico | 1.456 chamados |
| Estágio 2 | SHA-256 `e4fb8e41c910f8f2ed6151d8e69515ae8fd1b01f1310d47fa680d4403fd54ff1` |
| Filtro de Sala | `filtro_sala_sigilo_manifest_v6.json` |
| Portfólio-alvo | `portfolio_referencia.json` |
| Regras | `decision_rules_v1.json` |
| Configuração | `experimento_config.json` |

O Estágio 2 contém dados derivados por chamado. Ele não entra no Git nem no ZIP
code-only e deve ser copiado server-side no HPC.

## 3. Regeneração opcional dos Estágios 1–2

O pacote code-only de preparação é gerado por:

```powershell
python scripts\gerar_pacote_preparacao_insumo.py
```

O nome padrão é `_hpc/pacote/mba-ia-puc_preparacao_insumo.zip`; os CSVs são
enviados separadamente para `data/` no ambiente institucional.

O wrapper específico está em:

```bash
qsub estudo_comparativo/hpc/job_preparar_insumo.sh
```

Ele usa `scripts/hpc/job_pipeline.sh`, limita a execução aos Estágios 1–2 e grava
em:

```text
estudo_comparativo/preparacao_insumo/
```

Antes de submeter:

```bash
source ~/venvs/venv/bin/activate
python scripts/validar_pre_hpc.py
python scripts/validar_filtro_sala_sigilo_v6.py
bash -n scripts/hpc/job_pipeline.sh estudo_comparativo/hpc/job_preparar_insumo.sh
```

O gate deve confirmar 1.584 registros antes do filtro, 128 removidos, 1.456
restantes, chaves únicas, que os 128 casos efetivos correspondem ao request type
legado documentado quando o relatório privado estiver disponível, e zero uso de
LLM ou texto livre para escopo. O
manifesto agregado continua se chamando `MANIFESTO_STAGE2_V6.json` porque o
contrato técnico congelado é versionado, embora o script e a pasta tenham nomes
permanentes.

## 4. Gerar e validar o pacote code-only

Localmente:

```powershell
python scripts\gerar_pacote_comparacao_robusta.py `
  --stage2-manifest _hpc\insumo\MANIFESTO_STAGE2_V6.json

python scripts\validar_pacote_comparacao.py `
  _hpc\pacote\mba-ia-puc_rev6_20260803.zip
```

O gerador usa lista positiva. O ZIP não pode conter CSV, Estágio 1, Estágio 2,
checkpoints, banco, `.env`, chave ou texto de chamado. Registre SHA e tamanho
externamente; o ZIP executado final tem SHA-256
`a2896c3e46f0b8d6dc90660a8715bf719effcfd55af4964e3486cb9283b1967c`.

## 5. Preparar workspace no HPC

Exemplo para uma nova execução autorizada:

```bash
ZIP=~/mba-ia-puc_nova-revisao.zip
WORK=~/mba-ia-puc_nova-revisao
[ -e "$WORK" ] && echo "ERRO: destino existente" && exit 2
sha256sum "$ZIP"
unzip -t "$ZIP"
mkdir "$WORK"
unzip -q "$ZIP" -d "$WORK"
cd "$WORK"
chmod +x hpc/*.sh
sed -i 's/\r$//' hpc/*.sh
bash -n hpc/*.sh
```

Copie o Estágio 2 congelado para `source/02_summaries.json` e valide:

```bash
source ~/venvs/venv/bin/activate
python common/scripts/validar_insumo_comparacao.py --base .
```

O comando deve confirmar 1.456 registros e o SHA esperado pelo pacote.

## 6. Ordem dos jobs

1. `hpc/job_00_referencia.sh`: referência automática, ambiente congelado e
   insumos comuns;
2. `hpc/job_10_m1_legado_llama.sh`: benchmark da arquitetura legada;
3. `hpc/job_20_m2_nativo.sh`: benchmark da arquitetura LLM nativa;
4. `hpc/job_30_ablacao.sh`: seis braços, motores K-means/LLM e seeds 42,
   31415 e 27182;
5. `hpc/job_90_avaliacao.sh`: validação e conclusão.

Encadeie sempre por `afterok` e nunca execute dois Ollama na mesma GPU. O Job
90 só pode ser submetido depois dos oito braços. A relação exata entre jobs,
stages e objetivo científico está em `../docs/FLUXO_COMPLETO_MBA.md`.

## 7. Gates de conclusão

Uma execução só produz conclusão quando:

- todos os oito braços terminaram com exit zero;
- `VALIDACAO_RESULTS.json` tem `status=PASS` e zero falhas;
- as três seeds e as quatro visões de referência estão presentes;
- o cubo seed × referência × camada está completo;
- o relatório usa o vocabulário pré-registrado;
- os tarballs público e privado foram gerados;
- o tar público passou na auditoria de privacidade.

A execução final cumpriu esses gates no Job `2234.HPCGPU`: 302 checks, zero
falhas. O tar público tem SHA-256
`f476e4103044ee0cc578597523689cbafaf7b2b164fa720a5078808bc4545be6`.

## 8. Retomada e falhas

- Falha transitória sem mudança de código: uma retomada é permitida somente se
  checkpoints e hashes forem validados.
- Erro determinístico repetido: parar e corrigir em nova revisão.
- Qualquer mudança de código, regra, prompt, validador ou avaliador: novo
  pacote, workspace, Job 00 e cadeia integral.
- Nunca editar manifesto, output ou checkpoint para fazer um gate passar.
- Dependentes bloqueados por `afterok` não contam como execuções.

A linhagem completa das tentativas invalidadas está em
`../docs/APENDICE_TECNICO.md`.

## 9. Retorno de artefatos

- Tar público: pode ser usado na banca após conferência de privacidade.
- Tar privado: manter somente em armazenamento institucional restrito.
- ZIP executado: preservar para provar o código/configuração da rodada.
- Logs e checkpoints: preservar somente na evidência institucional; não
  versionar.
