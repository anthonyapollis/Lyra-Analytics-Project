from pathlib import Path
import pandas as pd, numpy as np, zipfile, shutil, os
BASE=Path('/mnt/data'); PROJ=BASE/'Lyra_Analytics_Project'; DIM=PROJ/'02_Dimensions'; FACT=PROJ/'03_Facts'; SQL=PROJ/'04_SQL'; DOC=PROJ/'05_Documentation'; CODE=PROJ/'06_Code'; QUAL=PROJ/'07_Quality'
for d in [SQL,DOC,CODE,QUAL]: d.mkdir(parents=True,exist_ok=True)

def rc(p):
    with open(p,'rb') as f: return max(sum(1 for _ in f)-1,0)

def choose(vals,n,p=None): return np.random.choice(vals,n,p=(np.array(p)/np.sum(p) if p is not None else None))
np.random.seed(321)
# create SCD dims if missing
if not (DIM/'DimEmployee_SCD2.csv').exists():
    sample=pd.read_csv(FACT/'FactCounsellingSessions.csv',usecols=['EmployeeNaturalKey','Age','Gender','CountryCode'],nrows=100000).drop_duplicates('EmployeeNaturalKey')
    n=len(sample); emp=sample.copy(); emp.insert(0,'EmployeeKey',np.arange(1,n+1)); emp['AgeBand']=pd.cut(emp.Age,[0,24,34,44,54,64,200],labels=['18-24','25-34','35-44','45-54','55-64','65+']).astype(str); emp['EmploymentLevel']=choose(['Junior','Intermediate','Senior','Manager','Executive'],n,[.18,.30,.28,.18,.06]); emp['Department']=choose(['Finance','Information Technology','Human Resources','Operations','Sales','Marketing','Customer Service','Legal','Supply Chain'],n); emp['EffectiveFromDate']='2024-01-01'; emp['EffectiveToDate']='9999-12-31'; emp['IsCurrent']=1; emp['ChangeReason']='Initial Load'; emp['HashValue']=pd.util.hash_pandas_object(emp[['EmployeeNaturalKey','AgeBand','Gender','EmploymentLevel','Department','CountryCode']].astype(str),index=False).astype(str); emp.to_csv(DIM/'DimEmployee_SCD2.csv',index=False)
if not (DIM/'DimConsent_SCD2.csv').exists():
    emp=pd.read_csv(DIM/'DimEmployee_SCD2.csv',usecols=['EmployeeNaturalKey','CountryCode'])
    types=['Service Delivery','Analytics','Marketing','Research','Data Sharing']; con=emp.loc[emp.index.repeat(len(types))].reset_index(drop=True); con.insert(0,'ConsentKey',np.arange(1,len(con)+1)); con['ConsentType']=types*len(emp); con['ConsentStatus']=choose(['Granted','Declined'],len(con),[.88,.12]); con['ConsentChannel']=choose(['Mobile App','Web Portal','Call Centre','HR Upload'],len(con)); con['EffectiveFromDate']='2024-01-01'; con['EffectiveToDate']='9999-12-31'; con['IsCurrent']=1; con['ChangeReason']='Initial Consent'; con['HashValue']=pd.util.hash_pandas_object(con[['EmployeeNaturalKey','ConsentType','ConsentStatus','ConsentChannel']].astype(str),index=False).astype(str); con.to_csv(DIM/'DimConsent_SCD2.csv',index=False)
# quality
counts=[]
for folder in [DIM,FACT]:
    for f in sorted(folder.glob('*.csv')):
        try: cols=len(pd.read_csv(f,nrows=0).columns)
        except Exception: cols=0
        counts.append({'TableName':f.stem,'Layer':'DIM' if folder==DIM else 'FACT','RowCount':rc(f),'ColumnCount':cols,'FileName':f.name})
pd.DataFrame(counts).to_csv(QUAL/'Generated_Table_Row_Counts.csv',index=False)
source_files=['Demo Hospital Outpatient Data_NHC.csv','Demo Hospital Outpatient Data Clean_NHC(2).csv','Demo Patient Experience Data_NHC(3).csv','Demo Health Facilities Geo Data_NHC(3).csv','Demo Pharmacy Sales Data.csv','1000 Generic Medication Names_NHC(3).txt']
srows=[]
for name in source_files:
    f=BASE/name
    if f.exists(): srows.append({'SourceFile':name,'RowCount':rc(f) if f.suffix=='.csv' else sum(1 for line in open(f,encoding='utf-8',errors='ignore') if line.strip())})
pd.DataFrame(srows).to_csv(QUAL/'Source_Row_Counts.csv',index=False)
# data dictionary based headers/samples
dict_rows=[]
for folder in [DIM,FACT]:
    for f in sorted(folder.glob('*.csv')):
        df=pd.read_csv(f,nrows=1000,low_memory=False)
        for col in df.columns:
            dict_rows.append({'TableName':f.stem,'ColumnName':col,'InferredDataTypeFromSample':str(df[col].dtype),'SampleDistinctCount':int(df[col].nunique(dropna=True))})
pd.DataFrame(dict_rows).to_csv(QUAL/'Data_Dictionary_Sample.csv',index=False)
# DDL
lines=['-- LYRA WELLBEING ANALYTICS SNOWFLAKE DDL','CREATE DATABASE IF NOT EXISTS LYRA_ANALYTICS;','CREATE SCHEMA IF NOT EXISTS LYRA_ANALYTICS.DIM;','CREATE SCHEMA IF NOT EXISTS LYRA_ANALYTICS.FACT;','']
for folder,schema in [(DIM,'DIM'),(FACT,'FACT')]:
    for f in sorted(folder.glob('*.csv')):
        df=pd.read_csv(f,nrows=100,low_memory=False); lines.append(f'CREATE OR REPLACE TABLE LYRA_ANALYTICS.{schema}.{f.stem.upper()} ('); cols=[]
        for c in df.columns:
            d=str(df[c].dtype).lower(); typ='NUMBER(38,0)' if 'int' in d else ('NUMBER(18,4)' if 'float' in d else ('TIMESTAMP_NTZ' if 'datetime' in d else 'VARCHAR'))
            cols.append(f'    {c.upper()} {typ}')
        lines.append(',\n'.join(cols)); lines.append(');\n')
(SQL/'01_Create_Lyra_Snowflake_Tables.sql').write_text('\n'.join(lines),encoding='utf-8')
# docs
md='# Lyra Wellbeing Analytics Additional Data Model\n\nThis ZIP adds Lyra-relevant analytics tables to your supplied healthcare data without overwriting the source files. It uses the existing million-row outpatient and pharmacy datasets as the base for two large fact tables.\n\n## Generated Tables\n\n| Layer | Table | Rows | Columns |\n|---|---|---:|---:|\n'
for r in counts: md+=f"| {r['Layer']} | {r['TableName']} | {r['RowCount']:,} | {r['ColumnCount']} |\n"
md+='''\n## Data Model / ERD\n```text\nDimDate ─┬─ FactCounsellingSessions ─ DimServiceType ─ DimIssueCategory\n         │             ├ DimClientCompany ─ DimCountry ─ DimCurrency\n         │             ├ DimFacilityGeography\n         │             ├ DimCounsellor\n         │             ├ DimEmployee_SCD2\n         │             └ DimConsent_SCD2\n         ├─ FactMedicationSales ─ DimMedication\n         └─ FactPatientExperience ─ DimServiceType / DimIssueCategory\n```\n\n## Why these tables were added\n- `DimClientCompany`: Lyra is an employee wellbeing provider serving corporate clients.\n- `DimServiceType`: maps telephone counselling, in-person counselling, work-life services, crisis support, coaching, digital solutions and upskilling.\n- `DimIssueCategory`: adds mental health/wellbeing categories such as depression, anxiety, burnout, trauma, stress and work conflict.\n- `DimCountry` and `DimCurrency`: keeps the US source context and adds South Africa plus other regions, with ZAR conversion.\n- `DimEmployee_SCD2` and `DimConsent_SCD2`: demonstrates SCD Type 2 and privacy-aware modelling.\n\n## Important note\nThe largest generated fact tables are:\n- `FactCounsellingSessions`: 1,000,000 rows.\n- `FactMedicationSales`: 1,000,000 rows.\n\n`FactPatientExperience` remains at the source row count because the uploaded experience dataset contains 20,000 records.\n'''
(DOC/'Data_Model_and_Project_Guide.md').write_text(md,encoding='utf-8')
# copy code
for src in [BASE/'build_project_chunked.py', BASE/'continue_project.py', Path(__file__)]:
    if src.exists(): shutil.copy2(src,CODE/src.name)
# zip - store to avoid timeout
z=BASE/'Lyra_Analytics_Project.zip'
if z.exists(): z.unlink()
with zipfile.ZipFile(z,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=1) as zipf:
    for f in PROJ.rglob('*'):
        if f.is_file(): zipf.write(f,f.relative_to(PROJ.parent))
print('ZIP_DONE', z, z.stat().st_size/1024/1024)
