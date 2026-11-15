/* Parte 2 — Otimização: duas consultas lentas medidas em três configurações de índice.
   A = linha de base (só chaves primárias; índices candidatos desabilitados temporariamente)
   B = índices candidatos de 02/11 (01_schema_seed.sql)
   C = índices ajustados para cada consulta (criados aqui e mantidos)
   Cada consulta: 1 execução de aquecimento + @repeticoes medidas (tempo decorrido em microssegundos).
   Saída: tabela de tempos (mediana, p95, média) por configuração/consulta.
   Leituras lógicas e planos reais: rodar 06_planos_parte2.sql em cada configuração (feito pelo script ps1).
   Somente dados sintéticos; ambiente local de laboratório. */
USE SIGpAcademic;
SET NOCOUNT ON;
SET XACT_ABORT ON;
DECLARE @repeticoes INT = 15;

IF OBJECT_ID('tempdb..#tempos') IS NOT NULL DROP TABLE #tempos;
CREATE TABLE #tempos (configuracao CHAR(1), consulta TINYINT, execucao INT, micros BIGINT);
IF OBJECT_ID('tempdb..#q1') IS NOT NULL DROP TABLE #q1;
CREATE TABLE #q1 (local_id NVARCHAR(40), provedor NVARCHAR(80), ano INT, mes INT, quantidade BIGINT, total DECIMAL(18,2));
IF OBJECT_ID('tempdb..#q2') IS NOT NULL DROP TABLE #q2;
CREATE TABLE #q2 (id BIGINT, local_id NVARCHAR(40), provedor_id NVARCHAR(40), valor_total DECIMAL(12,2), vencimento DATE, status NVARCHAR(24));

DECLARE @cfg CHAR(1), @i INT, @t0 DATETIME2(7);
DECLARE configs CURSOR LOCAL FAST_FORWARD FOR SELECT c FROM (VALUES ('A'), ('B'), ('C')) AS v(c);
OPEN configs;
FETCH NEXT FROM configs INTO @cfg;
WHILE @@FETCH_STATUS = 0
BEGIN
    -- Prepara a configuração.
    IF @cfg = 'A'
    BEGIN
        ALTER INDEX IX_Notas_Local_Vencimento_Status ON app.Notas DISABLE;
        ALTER INDEX IX_Notas_Provedor_Emissao ON app.Notas DISABLE;
        ALTER INDEX IX_Conciliacoes_Nota_Status ON app.Conciliacoes DISABLE;
        IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Emissao_Cobertura', 'IndexID') IS NOT NULL DROP INDEX IX_Notas_Emissao_Cobertura ON app.Notas;
        IF INDEXPROPERTY(OBJECT_ID('app.Notas'), 'IX_Notas_Pendentes_Vencimento', 'IndexID') IS NOT NULL DROP INDEX IX_Notas_Pendentes_Vencimento ON app.Notas;
        IF INDEXPROPERTY(OBJECT_ID('app.Conciliacoes'), 'IX_Conciliacoes_Concluidas', 'IndexID') IS NOT NULL DROP INDEX IX_Conciliacoes_Concluidas ON app.Conciliacoes;
    END;
    IF @cfg = 'B'
    BEGIN
        ALTER INDEX IX_Notas_Local_Vencimento_Status ON app.Notas REBUILD;
        ALTER INDEX IX_Notas_Provedor_Emissao ON app.Notas REBUILD;
        ALTER INDEX IX_Conciliacoes_Nota_Status ON app.Conciliacoes REBUILD;
    END;
    IF @cfg = 'C'
    BEGIN
        -- Consulta 1 filtra só por data_emissao e agrega local/provedor/valor: índice de cobertura.
        CREATE INDEX IX_Notas_Emissao_Cobertura ON app.Notas (data_emissao) INCLUDE (local_id, provedor_id, valor_total);
        -- Consulta 2 lê só notas PENDENTE ordenadas por vencimento: índice filtrado (menor e já ordenado).
        CREATE INDEX IX_Notas_Pendentes_Vencimento ON app.Notas (vencimento, id)
            INCLUDE (local_id, provedor_id, valor_total, status) WHERE status = N'PENDENTE';
        -- NOT EXISTS procura só conciliações CONCLUÍDAS: índice filtrado pequeno.
        CREATE INDEX IX_Conciliacoes_Concluidas ON app.Conciliacoes (nota_id) WHERE status = N'CONCILIADA';
    END;
    UPDATE STATISTICS app.Notas;
    UPDATE STATISTICS app.Conciliacoes;

    SET @i = 0;
    WHILE @i <= @repeticoes
    BEGIN
        TRUNCATE TABLE #q1;
        SET @t0 = SYSDATETIME();
        INSERT INTO #q1
        SELECT n.local_id, p.nome, YEAR(n.data_emissao), MONTH(n.data_emissao), COUNT_BIG(*), SUM(n.valor_total)
        FROM app.Notas AS n
        JOIN app.Provedores AS p ON p.id = n.provedor_id
        WHERE n.data_emissao >= DATEADD(MONTH, -12, CONVERT(date, GETDATE()))
        GROUP BY n.local_id, p.nome, YEAR(n.data_emissao), MONTH(n.data_emissao)
        OPTION (RECOMPILE);
        IF @i > 0 INSERT INTO #tempos VALUES (@cfg, 1, @i, DATEDIFF_BIG(MICROSECOND, @t0, SYSDATETIME()));

        TRUNCATE TABLE #q2;
        SET @t0 = SYSDATETIME();
        INSERT INTO #q2
        SELECT TOP (500) n.id, n.local_id, n.provedor_id, n.valor_total, n.vencimento, n.status
        FROM app.Notas AS n
        WHERE n.status = N'PENDENTE'
          AND n.vencimento < CONVERT(date, GETDATE())
          AND NOT EXISTS (SELECT 1 FROM app.Conciliacoes AS c WHERE c.nota_id = n.id AND c.status = N'CONCILIADA')
        ORDER BY n.vencimento, n.id
        OPTION (RECOMPILE);
        IF @i > 0 INSERT INTO #tempos VALUES (@cfg, 2, @i, DATEDIFF_BIG(MICROSECOND, @t0, SYSDATETIME()));
        SET @i += 1;
    END;
    FETCH NEXT FROM configs INTO @cfg;
END;
CLOSE configs;
DEALLOCATE configs;

SELECT DISTINCT configuracao, consulta,
    COUNT(*) OVER (PARTITION BY configuracao, consulta) AS execucoes,
    CAST(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY micros) OVER (PARTITION BY configuracao, consulta) / 1000.0 AS DECIMAL(10,2)) AS mediana_ms,
    CAST(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY micros) OVER (PARTITION BY configuracao, consulta) / 1000.0 AS DECIMAL(10,2)) AS p95_ms,
    CAST(AVG(micros * 1.0) OVER (PARTITION BY configuracao, consulta) / 1000.0 AS DECIMAL(10,2)) AS media_ms
FROM #tempos
ORDER BY consulta, configuracao;
