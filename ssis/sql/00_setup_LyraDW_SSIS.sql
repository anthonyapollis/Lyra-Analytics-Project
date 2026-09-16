/*
================================================================================
LYRA WELLBEING - SSIS (Biml) SCD Type 2 load of the consent dimension
================================================================================
The Snowflake warehouse models consent as DIMCONSENT_SCD2. This database is the
SQL Server target for the Biml-generated SSIS package that maintains that history
from daily consent snapshots:

  stg.ConsentSnapshot  the day's snapshot, as received
  stg.ConsentChanged   rows whose tracked attributes differ from the current version
  dw.DimConsent        Type 2 history: one current row per employee + consent type,
                       expired versions closed the day before the change
  etl.Config           where the snapshot files live and which one to load
  etl.PackageRun       one row per package run (row counts, error text)

Tracked (Type 2) attributes: CountryCode, ConsentStatus, ConsentChannel.
ChangeReason describes a version and does not create one on its own.
Re-runnable: drops and recreates this database's objects.
================================================================================
*/
SET QUOTED_IDENTIFIER ON;   -- required for the filtered unique index (sqlcmd defaults it to OFF)
SET ANSI_NULLS ON;
GO
IF DB_ID('LyraDW_SSIS') IS NULL CREATE DATABASE LyraDW_SSIS;
GO
-- staging/warehouse loads are re-runnable from source, so point-in-time log backups are not needed
ALTER DATABASE LyraDW_SSIS SET RECOVERY SIMPLE;
GO
USE LyraDW_SSIS;
GO
IF SCHEMA_ID('etl') IS NULL EXEC('CREATE SCHEMA etl');
IF SCHEMA_ID('stg') IS NULL EXEC('CREATE SCHEMA stg');
IF SCHEMA_ID('dw')  IS NULL EXEC('CREATE SCHEMA dw');
GO

IF OBJECT_ID('etl.PackageRun') IS NULL
CREATE TABLE etl.PackageRun (
    RunId          int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    PackageName    nvarchar(200)  NOT NULL,
    ExecutionGuid  nvarchar(50)   NULL,
    StartTime      datetime2(0)   NOT NULL DEFAULT SYSDATETIME(),
    EndTime        datetime2(0)   NULL,
    Status         varchar(20)    NOT NULL DEFAULT 'Running',
    RowsRead       bigint         NULL,
    RowsWritten    bigint         NULL,
    RowsRejected   bigint         NULL,
    Message        nvarchar(4000) NULL
);
IF OBJECT_ID('etl.Config') IS NULL
CREATE TABLE etl.Config (
    ConfigKey   varchar(50)    NOT NULL PRIMARY KEY,
    ConfigValue nvarchar(400)  NOT NULL,
    UpdatedAt   datetime2(0)   NOT NULL DEFAULT SYSDATETIME()
);
GO

DROP TABLE IF EXISTS stg.ConsentSnapshot, stg.ConsentChanged, dw.DimConsent;
GO
CREATE TABLE stg.ConsentSnapshot (
    EmployeeNaturalKey varchar(20)  NOT NULL,
    CountryCode        varchar(5)   NOT NULL,
    ConsentType        varchar(50)  NOT NULL,
    ConsentStatus      varchar(20)  NOT NULL,
    ConsentChannel     varchar(30)  NOT NULL,
    ChangeReason       varchar(100) NULL,
    SnapshotDate       date         NOT NULL
);
CREATE TABLE stg.ConsentChanged (
    ConsentKey         int          NOT NULL,     -- current version being replaced
    EmployeeNaturalKey varchar(20)  NOT NULL,
    CountryCode        varchar(5)   NOT NULL,
    ConsentType        varchar(50)  NOT NULL,
    ConsentStatus      varchar(20)  NOT NULL,
    ConsentChannel     varchar(30)  NOT NULL,
    ChangeReason       varchar(100) NULL,
    SnapshotDate       date         NOT NULL,
    RowHash            char(40)     NOT NULL
);
CREATE TABLE dw.DimConsent (
    ConsentKey         int IDENTITY(1,1) NOT NULL PRIMARY KEY,
    EmployeeNaturalKey varchar(20)  NOT NULL,
    CountryCode        varchar(5)   NOT NULL,
    ConsentType        varchar(50)  NOT NULL,
    ConsentStatus      varchar(20)  NOT NULL,
    ConsentChannel     varchar(30)  NOT NULL,
    ChangeReason       varchar(100) NULL,
    RowHash            char(40)     NOT NULL,     -- SHA1 of the tracked attributes
    EffectiveFromDate  date         NOT NULL,
    EffectiveToDate    date         NOT NULL,
    IsCurrent          bit          NOT NULL,
    LoadRunId          int          NULL
);
/* The Type 2 rule the database itself enforces: at most one current version per business key. */
CREATE UNIQUE INDEX UX_DimConsent_Current ON dw.DimConsent (EmployeeNaturalKey, ConsentType) WHERE IsCurrent = 1;
GO

CREATE OR ALTER VIEW dw.vw_DimConsentSummary AS
SELECT COUNT(*)                                        AS dim_rows,
       SUM(CASE WHEN IsCurrent = 1 THEN 1 ELSE 0 END)  AS current_rows,
       SUM(CASE WHEN IsCurrent = 0 THEN 1 ELSE 0 END)  AS expired_rows,
       COUNT(DISTINCT EmployeeNaturalKey)              AS employees,
       MAX(EffectiveFromDate)                          AS latest_effective_from
FROM dw.DimConsent;
GO
