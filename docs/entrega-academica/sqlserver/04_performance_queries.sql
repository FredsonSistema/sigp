USE SIGpAcademic;
GO

SET NOCOUNT ON;
SET STATISTICS IO ON;
SET STATISTICS TIME ON;
SET STATISTICS XML ON;

-- Consulta candidata 1: resumo mensal por local e provedor.
SELECT
    n.local_id,
    p.nome AS provedor,
    YEAR(n.data_emissao) AS ano,
    MONTH(n.data_emissao) AS mes,
    COUNT_BIG(*) AS quantidade_notas,
    SUM(n.valor_total) AS total_faturado
FROM app.Notas AS n
JOIN app.Provedores AS p ON p.id = n.provedor_id
WHERE n.data_emissao >= DATEADD(MONTH, -12, CONVERT(date, GETDATE()))
GROUP BY n.local_id, p.nome, YEAR(n.data_emissao), MONTH(n.data_emissao)
ORDER BY ano, mes, n.local_id, provedor
OPTION (RECOMPILE);

-- Consulta candidata 2: pendências vencidas ainda sem conciliação concluída.
SELECT TOP (500)
    n.id, n.local_id, n.provedor_id, n.valor_total, n.vencimento, n.status
FROM app.Notas AS n
WHERE n.status = N'PENDENTE'
  AND n.vencimento < CONVERT(date, GETDATE())
  AND NOT EXISTS (
      SELECT 1
      FROM app.Conciliacoes AS c
      WHERE c.nota_id = n.id
        AND c.status = N'CONCILIADA'
  )
ORDER BY n.vencimento, n.id
OPTION (RECOMPILE);

SET STATISTICS TIME OFF;
SET STATISTICS IO OFF;
SET STATISTICS XML OFF;
GO
