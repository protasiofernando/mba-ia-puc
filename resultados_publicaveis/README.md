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

## Nota editorial sobre o relatório congelado

Os arquivos relacionados no `MANIFESTO_RESULTADOS.json` foram preservados byte a
byte, conforme extraídos do pacote público validado. Por esse motivo, o relatório
automático `estudo_comparativo/avaliacao/RESULTADO_COMPARACAO_ROBUSTA.md` mantém
duas formulações que exigem esclarecimento:

- a abertura descreve uma máscara automática e conservadora de Sala de Sigilo.
  Essa é uma formulação genérica legada do gerador do relatório e não descreve o
  recorte efetivamente executado. Na execução final, 128 registros do request
  type legado `Solicitação de Acesso a Bases de Dados` foram removidos por
  correspondência exata do campo estruturado, antes do Estágio 1, sem LLM e sem
  leitura de texto livre. Os outros seis rótulos previstos tiveram zero
  ocorrências. O procedimento canônico está em
  `../estudo_comparativo/PROTOCOLO_METODOLOGICO.md`;
- na seção “Leitura correta”, a frase “não é a resultados históricos” contém um
  erro de redação. A interpretação correta é: o M1 legado foi reexecutado com
  Llama, portanto a comparação não reutiliza resultados históricos.

Essas observações são editoriais e não alteram métricas, validações ou a
conclusão do Job 90. O relatório original permanece intacto para preservar sua
integridade criptográfica.

O tar privado não foi copiado. Esta pasta não contém chave Jira, texto de
chamado, classificação por chamado, CSV, banco, checkpoint ou segredo.

Valide antes de publicar:

```powershell
python scripts\verificar_publicacao_novo_repo.py
```
