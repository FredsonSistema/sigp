/* Parte 2 — leituras lógicas e plano real das duas consultas em uma configuração de índice.
   Variável sqlcmd: CFG = A | B | C (mesmas configurações de 05_benchmark_parte2.sql).
   Uso: sqlcmd ... -v CFG=A -i 06_planos_parte2.sql  (chamado por benchmark-parte2.ps1). */
USE SIGpAcademic;
SET NOCOUNT ON;
DECLARE @cfg CHAR(1) = '$(CFG)';
IF @cfg = 'A'
BEGIN
    ALTER INDEX IX_Notas_Local_Vencimento_Status ON app.Notas DISABLE;
    ALTER INDEX IX_Notas_Provedor_Emissao ON app.Notas DISABLE;
    ALTER INDEX IX_Conciliacoes_Nota_Status ON app.Conciliacoes DISABLE;
    IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Emissao_Cobertura', 'IndexID') IS NOT NULL DROP INDEX IX_Notas_Emissao_Cobertura ON app.Notas;
    IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Pendentes_Vencimento', 'IndexID') IS NOT NULL DROP INDEX IX_Notas_Pendentes_Vencimento ON app.Notas;
    IF INDEXPROPERTY(OBJECT_ID('app.Conciliacoes'), 'IX_Conciliacoes_Concluidas', 'IndexID') IS NOT NULL DROP INDEX IX_Conciliacoes_Concluidas ON app.Conciliacoes;
END;
IF @cfg IN ('B', 'C')
BEGIN
    ALTER INDEX IX_Notas_Local_Vencimento_Status ON app.Notas REBUILD;
    ALTER INDEX IX_Notas_Provedor_Emissao ON app.Notas REBUILD;
    ALTER INDEX IX_Conciliacoes_Nota_Status ON app.Conciliacoes REBUILD;
END;
IF @cfg = 'C'
BEGIN
    IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Emissao_Cobertura', 'IndexID') IS NULL
        CREATE INDEX IX_Notas_Emissao_Cobertura ON app.Notas (data_emissao) INCLUDE (local_id, provedor_id, valor_total);
    IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Pendentes_Vencimento', 'IndexID') IS NULL
        CREATE INDEX IX_Notas_Pendentes_Vencimento ON app.Notas (vencimento, id)
            INCLUDE (local_id, provedor_id, valor_total, status) WHERE status = N'PENDENTE';
    IF INDEXPROPERTY(OBJECT_ID('app.Conciliacoes'), 'IX_Conciliacoes_Concluidas', 'IndexID') IS NULL
        CREATE INDEX IX_Conciliacoes_Concluidas ON app.Conciliacoes (nota_id) WHERE status = N'CONCILIADA';
END;
IF @cfg = 'B'
BEGIN
    IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Emissao_Cobertura', 'IndexID') IS NOT NULL DROP INDEX IX_Notas_Emissao_Cobertura ON app.Notas;
    IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Pendentes_Vencimento', 'IndexID') IS NOT NULL DROP INDEX IX_Notas_Pendentes_Vencimento ON app.Notas;
    IF INDEXPROPERTY(OBJECT_ID('app.Conciliacoes'), 'IX_Conciliacoes_Concluidas', 'IndexID') IS NOT NULL DROP INDEX IX_Conciliacoes_Concluidas ON app.Conciliacoes;
END;
UPDATE STATISTICS app.Notas;
UPDATE STATISTICS app.Conciliacoes;
PRINT '### CONFIGURACAO ' + @cfg;
SET STATISTICS IO ON;
SET STATISTICS XML ON;
PRINT '### CONSULTA 1';
SELECT n.local_id, p.nome AS provedor, YEAR(n.data_emissao) AS ano, MONTH(n.data_emissao) AS mes,
       COUNT_BIG(*) AS quantidade_notas, SUM(n.valor_total) AS total_faturado
FROM app.Notas AS n
JOIN app.Provedores AS p ON p.id = n.provedor_id
WHERE n.data_emissao >= DATEADD(MONTH, -12, CONVERT(date, GETDATE()))
GROUP BY n.local_id, p.nome, YEAR(n.data_emissao), MONTH(n.data_emissao)
ORDER BY ano, mes, n.local_id, provedor
OPTION (RECOMPILE);
PRINT '### CONSULTA 2';
SELECT TOP (500) n.id, n.local_id, n.provedor_id, n.valor_total, n.vencimento, n.status
FROM app.Notas AS n
WHERE n.status = N'PENDENTE'
  AND n.vencimento < CONVERT(date, GETDATE())
  AND NOT EXISTS (SELECT 1 FROM app.Conciliacoes AS c WHERE c.nota_id = n.id AND c.status = N'CONCILIADA')
ORDER BY n.vencimento, n.id
OPTION (RECOMPILE);
SET STATISTICS XML OFF;
SET STATISTICS IO OFF;
