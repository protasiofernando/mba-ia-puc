# Guia vigente de entrada e extração Jira

## Arquivos de entrada

Coloque os CSVs reais em `data/` com o padrão configurado em
`configuracao/projeto.json`:

```text
<slug>__YYYY-MM__YYYY-MM.csv
```

Os CSVs contêm dados pessoais e não entram no Git, ZIP da comparação ou serviços
externos.

## Descoberta dos arquivos

`scripts/data_loader.py` resolve a pasta do projeto e combina os arquivos
compatíveis com `csv_glob`.

Valide antes do HPC:

```powershell
python scripts\validar_pre_hpc.py
```

## Estágio 1 vigente

O extrator atual é:

```powershell
python scripts\extract.py
```

Ele é Python determinístico e gera `pipeline_data/01_tickets.json`. Na operação
normal, não é necessário chamá-lo separadamente:
`scripts/hpc/job_pipeline.sh` o executa na ordem correta.

O Estágio 2 lê o Estágio 1 e gera `02_summaries.json` com intenção, tema, tipo de
pedido e informações fornecidas/faltantes.

## Relação com a comparação robusta

A comparação não lê CSV nem executa extração:

- usa o novo `02_summaries.json` produzido após o filtro estruturado v6;
- exige o SHA-256 registrado no `MANIFESTO_STAGE2_V6.json`;
- exige 1.456 registros;
- copia o arquivo no próprio HPC;
- nunca o inclui no ZIP code-only.

Assim, mudanças de extração ou sumarização ficam fora do estimando da comparação
dos métodos de descoberta.
