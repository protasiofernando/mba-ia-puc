# Resultados públicos e auditáveis

Esta pasta contém os artefatos agregados promovidos do pacote público validado
do Job 90 e um snapshot estático do dashboard gerado posteriormente apenas com
agregados publicáveis. Ela permite auditar os números da documentação sem
acessar `_hpc/`, CSVs, resumos, checkpoints ou resultados por chamado.

Origem congelada:

- Job 90: `2234.HPCGPU`, `Exit_status=0`;
- tar público: `comparacao_publicavel_20260804_131120.tar.gz`;
- SHA-256 do tar: `f476e4103044ee0cc578597523689cbafaf7b2b164fa720a5078808bc4545be6`;
- validação: `VALIDACAO_RESULTS.json = PASS`, 302 verificações, zero falhas.

Conteúdo:

- `estudo_comparativo/avaliacao/`: relatório, métricas completas e validações;
- `estudo_comparativo/referencia/`: qualidade agregada da referência automática;
- manifestos e ambiente congelado necessários para a proveniência.
- `RESULTADO_DASHBOARD.html`: visualização offline do catálogo, da projeção
  agregada do Estágio 7 e dos resultados permitidos; não integra o tar do Job 90.

O tar privado não foi copiado. Esta pasta não contém chave Jira, texto de
chamado, classificação por chamado, CSV, banco, checkpoint ou segredo.

Valide antes de publicar:

```powershell
python scripts\verificar_publicacao_novo_repo.py
```
