# Decisão curada e alvo congelado

- `feedback_portfolio.json`: decisão operacional humana no nível do catálogo;
- `portfolio_referencia.json`: projeção analítica determinística usada pelo
  estudo comparativo.

O espelho analítico mantém exatamente o SHA executado. No arquivo humano, dois
metadados explicativos antigos foram corrigidos e foram documentados, depois da
execução, a justificativa de consolidação e o mapa de categorias substituídas.
Os bytes originais estão preservados, em base64, em
`../../estudo_comparativo/proveniencia_execucao/`. O gate de coerência comprova
que as duas versões projetam o mesmo alvo e impede alteração retrospectiva das
categorias analíticas.
Sala de Sigilo permanece visível no primeiro arquivo e fora da análise no
segundo.
