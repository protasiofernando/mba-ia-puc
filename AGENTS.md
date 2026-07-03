# Guia Rapido Para Agentes

Este e o ponto de entrada para qualquer IA ou novo desenvolvedor neste projeto.
Leia este arquivo primeiro. Abra os documentos em `docs/` apenas quando a tarefa
exigir detalhe especifico.

## Estado Atual

- Aplicacao principal: `app.py` (Flask), `templates/index.html`, `static/script.js`, `static/style.css`.
- Pipeline HPC: `pipeline/01_extract.py` a `pipeline/07_finalize_portfolio.py`.
- Jobs HPC: `hpc/submit_pipeline.sub` para Stages 1-6 e `hpc/stage7.sub` para Stage 7.
- Curadoria da area: `feedback_portfolio.json`.
- O app usa o portfolio curado do Stage 7 quando existem:
  - `pipeline_data/07_portfolio_final.json`
  - `pipeline_data/07_classificados_final.json`
- Se os arquivos `07_*` nao existem, o app cai para a recomendacao automatica:
  - `pipeline_data/05_portfolio_recommendation.json`
  - `pipeline_data/06_classificados.json`, quando disponivel.

## Regras Importantes

- Nao trocar a fonte ativa de portfolio sem preservar a regra `07_*` primeiro, `05/06` como fallback.
- Nao versionar dados sensiveis: CSVs, banco SQLite, resumos por chamado, classificacoes por chamado, checkpoints e logs.
- `pipeline_data/07_portfolio_final.json` e agregado e pode ser usado pelo app; `07_classificados_final.json` contem dados por chamado e fica fora do git.
- O tema visual e FGV light. Nao reverter para dark theme.
- A simulacao local usa Ollama via tunel SSH para o no GPU; detalhes em `docs/NOTAS_TECNICAS.md`.
- No V100, deixar o Ollama detectar CUDA por autodiscovery. Nao definir `CUDA_VISIBLE_DEVICES=0` nem `OLLAMA_LLM_LIBRARY=cuda` por padrao.

## Comandos De Validacao

```powershell
python -m py_compile app.py pipeline\02_summarize.py pipeline\07_finalize_portfolio.py
```

```powershell
python -c "import app,json; c=app.app.test_client(); d=c.get('/api/analise-resumo').get_json(); print(d.get('total_tickets'), d.get('categorias_recomendadas'), d.get('usando_curadoria'), d.get('fonte_portfolio'))"
```

```powershell
Invoke-RestMethod http://127.0.0.1:5000/api/ollama-status
```

## Mapa Da Documentacao

- `README.md`: visao geral, instalacao local e uso basico.
- `docs/GUIA_PROJETO.md`: referencia tecnica completa da arquitetura e dos arquivos.
- `docs/MANUAL_HPC.md`: execucao, copia de arquivos, limpeza e diagnostico no HPC.
- `docs/NOTAS_TECNICAS.md`: decisoes tecnicas, Ollama/CUDA, simulacao local e fonte ativa do portfolio.
- `docs/GUIA_EXTRACAO_JIRA.md`: extracao e tratamento dos CSVs do Jira.
- `docs/CONTEXTO_OBJETIVOS.md`: contexto executivo e objetivos do projeto.
- `docs/IDENTIDADE_VISUAL_FGV.md`: referencia visual institucional para ajustes de UI.

## Coisas Que Nao Fazem Parte Da Fonte Viva

- Docker nao esta em uso neste projeto.
- `classificador.py` nao esta em uso; a simulacao usa o portfolio ativo carregado em `app.py`.
- D3 nao esta em uso; os graficos usam Chart.js.
- Caches `__pycache__`, logs e pastas locais de rascunho devem permanecer fora do git.
