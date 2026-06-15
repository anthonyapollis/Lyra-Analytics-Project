from pathlib import Path
import numpy as np, pandas as pd, zipfile, shutil, re
from datetime import datetime
np.random.seed(123)
BASE=Path('/mnt/data'); PROJ=BASE/'Lyra_Analytics_Project'; DIM=PROJ/'02_Dimensions'; FACT=PROJ/'03_Facts'; SQL=PROJ/'04_SQL'; DOC=PROJ/'05_Documentation'; CODE=PROJ/'06_Code'; QUAL=PROJ/'07_Quality'
for d in [SQL,DOC,CODE,QUAL]: d.mkdir(parents=True,exist_ok=True)
FX={'ZAR':1.0,'USD':18.5,'GBP':23.5,'AUD':12.2,'CAD':13.6}
COUNTRY=pd.read_csv(DIM/'DimCountry.csv'); CLIENT=pd.read_csv(DIM/'DimClientCompany.csv'); SERVICE=pd.read_csv(DIM/'DimServiceType.csv'); ISSUE=pd.read_csv(DIM/'DimIssueCategory.csv'); MED=pd.read_csv(DIM/'DimMedication.csv')
pharm=BASE/'Demo Pharmacy Sales Data.csv'; pat=BASE/'Demo Patient Experience Data_NHC(3).csv'
if not pat.exists(): pat=BASE/'Demo Patient Experience Data_NHC.csv'

def choose(vals,n,p=None): return np.random.choice(vals,n,p=(np.array(p)/np.sum(p) if p is not None else None))
def assign(codes, groups):
 out=np.empty(len(codes), dtype=int); arr=np.asarray(codes)
 for c, vals in groups.items():
  m=(arr==c); out[m]=np.random.choice(vals, m.sum())
 return out
def rc(p):
 with open(p,'rb') as f: return max(sum(1 for _ in f)-1,0)

def patient_experience():
 out=FACT/'FactPatientExperience.csv'
 if out.exists(): return
 df=pd.read_csv(pat); n=len(df); df.columns=[c.replace(' ','_').replace('(','').replace(')','') for c in df.columns]
 df.insert(0,'ExperienceKey',np.arange(1,n+1)); df.insert(1,'ExperienceID','EXP'+pd.Series(np.arange(1,n+1)).astype(str).str.zfill(9))
 df['Feedback_Date']=pd.to_datetime(df.Feedback_Date,errors='coerce'); df['DateKey']=df.Feedback_Date.dt.strftime('%Y%m%d').astype('Int64')
 df['CountryCode']=choose(['US','ZA','UK','AU','CA'],n,[.55,.20,.10,.08,.07]); df=df.merge(COUNTRY[['CountryCode','CountryKey','CountryName','GlobalRegion','CurrencyCode']],on='CountryCode',how='left')
 df['ServiceTypeKey']=choose(SERVICE.ServiceTypeKey.values,n); df=df.merge(SERVICE[['ServiceTypeKey','ServiceTypeName','ServiceCategory','DeliveryChannel']],on='ServiceTypeKey',how='left')
 df['IssueCategoryKey']=choose(ISSUE.IssueCategoryKey.values,n,[.20,.18,.14,.08,.08,.03,.05,.08,.04,.03,.03,.04,.02,.01,.01]); df=df.merge(ISSUE[['IssueCategoryKey','IssueCategoryName','IssueGroup']],on='IssueCategoryKey',how='left')
 df['StaffRating10']=(pd.to_numeric(df.Staff_Rating,errors='coerce')*2).clip(1,10); df['SpeedRating10']=(pd.to_numeric(df.Speed_Rating,errors='coerce')*2).clip(1,10); df['SatisfactionScore']=((df.StaffRating10*.6)+(df.SpeedRating10*.4)).round(1)
 df['NetPromoterScore']=np.where(df.SatisfactionScore>=9,choose([9,10],n,[.45,.55]),np.where(df.SatisfactionScore>=7,choose([7,8],n),choose([0,1,2,3,4,5,6],n)))
 df['OutcomeBeforeScore']=choose([2,3,4,5,6,7],n,[.12,.18,.22,.22,.16,.10]); df['OutcomeAfterScore']=np.minimum(10,df.OutcomeBeforeScore+choose([0,1,2,3],n,[.15,.35,.35,.15])); df['ImprovementScore']=df.OutcomeAfterScore-df.OutcomeBeforeScore; df['WouldRecommendFlag']=(df.NetPromoterScore>=8).astype(int); df['ComplaintFlag']=(df.SatisfactionScore<=5).astype(int); df['LoadDTS']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
 df.to_csv(out,index=False); print('experience',len(df))

def medication_sales_fast():
 out=FACT/'FactMedicationSales.csv'
 if out.exists(): return
 header=True; start=1; groups=CLIENT.groupby('CountryCode')['ClientCompanyKey'].apply(lambda s:s.to_numpy()).to_dict()
 for ch in pd.read_csv(pharm,chunksize=250000,low_memory=False):
  n=len(ch); df=ch.copy(); df.columns=[c.replace(' ','_') for c in df.columns]
  df.insert(0,'MedicationSalesKey',np.arange(start,start+n)); df.insert(1,'MedicationSalesID','MEDSALE'+pd.Series(np.arange(start,start+n)).astype(str).str.zfill(9)); start+=n
  df['Date_Sold']=pd.to_datetime(df.Date_Sold,errors='coerce'); df['DateKey']=df.Date_Sold.dt.strftime('%Y%m%d').astype('Int64')
  df['CountryCode']=choose(['US','ZA','UK','AU','CA'],n,[.55,.20,.10,.08,.07]); df=df.merge(COUNTRY[['CountryCode','CountryKey','CountryName','GlobalRegion','CurrencyCode']],on='CountryCode',how='left')
  # Use fast class-based mental-health flag rather than expensive merge for every row
  cls=df.Med_class.astype(str).str.lower()
  df['MentalHealthMedicationFlag']=cls.str.contains('antidepressant|benzodiazepine|antipsychotic|mood|anxiolytic|stimulant|serotonin|norepinephrine|sedative|hypnotic',regex=True).astype(int)
  df['TherapeuticClass']=df.Med_class
  df['MedicationName']=df.Med_name.str.replace(r'\s*\(.*?\)','',regex=True).str.strip()
  df['MedicationKey']=pd.factorize(df.Med_name + '|' + df.Med_class)[0] + 1
  df['ClientCompanyKey']=assign(df.CountryCode.values,groups); df=df.merge(CLIENT[['ClientCompanyKey','ClientCompanyName','IndustrySectorName']],on='ClientCompanyKey',how='left')
  df['MedicationSalesAmountLocal']=(pd.to_numeric(df.Quantity_Sold,errors='coerce').fillna(0)*pd.to_numeric(df.Price,errors='coerce').fillna(0)).round(2)
  df['MedicationSalesAmountZAR']=(df.MedicationSalesAmountLocal*df.CurrencyCode.map(FX).fillna(1)).round(2)
  df['PrescriptionRequiredFlag']=cls.str.contains('antidepressant|benzodiazepine|antipsychotic|opioid|mood|stimulant|anxiolytic',regex=True).astype(int)
  df['TreatmentType']=np.where(df.MentalHealthMedicationFlag==1,'Mental Health Medication','General Healthcare Medication')
  df['LoadDTS']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  df.to_csv(out,index=False,mode='w' if header else 'a',header=header); header=False; print('med chunk',n)

def digital():
 out=FACT/'FactDigitalEngagement.csv'
 if out.exists(): return
 header=True; start=1; groups=CLIENT.groupby('CountryCode')['ClientCompanyKey'].apply(lambda s:s.to_numpy()).to_dict()
 for _ in range(5):
  n=200000; dates=pd.to_datetime(np.random.randint(pd.Timestamp('2022-01-01').value//10**9,pd.Timestamp('2026-12-31').value//10**9,n),unit='s').normalize()
  df=pd.DataFrame({'DigitalEngagementKey':np.arange(start,start+n),'DigitalEngagementID':'DIG'+pd.Series(np.arange(start,start+n)).astype(str).str.zfill(9),'EngagementDate':dates}); start+=n
  df['DateKey']=df.EngagementDate.dt.strftime('%Y%m%d').astype(int); df['CountryCode']=choose(['US','ZA','UK','AU','CA'],n,[.55,.20,.10,.08,.07]); df=df.merge(COUNTRY[['CountryCode','CountryKey','CountryName','GlobalRegion','CurrencyCode']],on='CountryCode',how='left')
  df['ClientCompanyKey']=assign(df.CountryCode.values,groups); df['ServiceTypeKey']=choose(SERVICE.ServiceTypeKey.values,n,[.18,.02,.10,.02,.01,.02,.12,.35,.01,.12,.02,.02,.01]); df['IssueCategoryKey']=choose(ISSUE.IssueCategoryKey.values,n,[.20,.18,.14,.08,.08,.03,.05,.08,.04,.03,.03,.04,.02,.01,.01])
  df['DigitalChannel']=choose(['Mobile App','Web Portal','Live Chat','Push-to-Call','Self-Service Article','Video Content'],n,[.35,.22,.13,.10,.15,.05]); df['EngagementType']=choose(['Article View','Self Assessment','Live Chat','Call Request','Video View','Resource Download'],n,[.28,.18,.14,.12,.16,.12]); df['EngagementDurationSeconds']=np.random.randint(30,1801,n); df['CompletedEngagementFlag']=choose([0,1],n,[.22,.78]); df['ConversionToCounsellingFlag']=choose([0,1],n,[.88,.12]); df['LoadDTS']=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
  df.to_csv(out,index=False,mode='w' if header else 'a',header=header); header=False; print('digital chunk',n)

def scd():
 eout=DIM/'DimEmployee_SCD2.csv'; cout=DIM/'DimConsent_SCD2.csv'
 if eout.exists() and cout.exists(): return
 sample=pd.read_csv(FACT/'FactCounsellingSessions.csv',usecols=['EmployeeNaturalKey','Age','Gender','CountryCode'],nrows=100000).drop_duplicates('EmployeeNaturalKey')
 n=len(sample); emp=sample.copy(); emp.insert(0,'EmployeeKey',np.arange(1,n+1)); emp['AgeBand']=pd.cut(emp.Age,[0,24,34,44,54,64,200],labels=['18-24','25-34','35-44','45-54','55-64','65+']).astype(str); emp['EmploymentLevel']=choose(['Junior','Intermediate','Senior','Manager','Executive'],n,[.18,.30,.28,.18,.06]); emp['Department']=choose(['Finance','Information Technology','Human Resources','Operations','Sales','Marketing','Customer Service','Legal','Supply Chain'],n); emp['EffectiveFromDate']='2024-01-01'; emp['EffectiveToDate']='9999-12-31'; emp['IsCurrent']=1; emp['ChangeReason']='Initial Load'; emp['HashValue']=pd.util.hash_pandas_object(emp[['EmployeeNaturalKey','AgeBand','Gender','EmploymentLevel','Department','CountryCode']].astype(str),index=False).astype(str); emp.to_csv(eout,index=False); print('emp',len(emp))
 types=['Service Delivery','Analytics','Marketing','Research','Data Sharing']; con=emp[['EmployeeNaturalKey','CountryCode']].loc[emp.index.repeat(len(types))].reset_index(drop=True); con.insert(0,'ConsentKey',np.arange(1,len(con)+1)); con['ConsentType']=types*len(emp); con['ConsentStatus']=choose(['Granted','Declined'],len(con),[.88,.12]); con['ConsentChannel']=choose(['Mobile App','Web Portal','Call Centre','HR Upload'],len(con)); con['EffectiveFromDate']='2024-01-01'; con['EffectiveToDate']='9999-12-31'; con['IsCurrent']=1; con['ChangeReason']='Initial Consent'; con['HashValue']=pd.util.hash_pandas_object(con[['EmployeeNaturalKey','ConsentType','ConsentStatus','ConsentChannel']].astype(str),index=False).astype(str); con.to_csv(cout,index=False); print('consent',len(con))

def docs_zip():
 counts=[]
 for folder in [DIM,FACT]:
  for f in folder.glob('*.csv'): counts.append({'TableName':f.stem,'RowCount':rc(f),'ColumnCount':len(pd.read_csv(f,nrows=0).columns)})
 pd.DataFrame(counts).to_csv(QUAL/'Generated_Table_Row_Counts.csv',index=False)
 pd.DataFrame([{'SourceFile':v.name,'RowCount':rc(v) if v.suffix=='.csv' else sum(1 for line in open(v,encoding='utf-8',errors='ignore') if line.strip())} for v in [BASE/'Demo Hospital Outpatient Data_NHC.csv',BASE/'Demo Hospital Outpatient Data Clean_NHC(2).csv',pat,BASE/'Demo Health Facilities Geo Data_NHC(3).csv',pharm,BASE/'1000 Generic Medication Names_NHC(3).txt'] if v.exists()]).to_csv(QUAL/'Source_Row_Counts.csv',index=False)
 lines=['-- LYRA WELLBEING ANALYTICS SNOWFLAKE DDL','CREATE DATABASE IF NOT EXISTS LYRA_ANALYTICS;','CREATE SCHEMA IF NOT EXISTS LYRA_ANALYTICS.DIM;','CREATE SCHEMA IF NOT EXISTS LYRA_ANALYTICS.FACT;','']
 for folder,schema in [(DIM,'DIM'),(FACT,'FACT')]:
  for f in sorted(folder.glob('*.csv')):
   df=pd.read_csv(f,nrows=20,low_memory=False); lines.append(f'CREATE OR REPLACE TABLE LYRA_ANALYTICS.{schema}.{f.stem.upper()} ('); cols=[]
   for c in df.columns:
    d=str(df[c].dtype).lower(); typ='NUMBER(38,0)' if 'int' in d else ('NUMBER(18,4)' if 'float' in d else ('TIMESTAMP_NTZ' if 'datetime' in d else 'VARCHAR'))
    cols.append(f'    {c.upper()} {typ}')
   lines.append(',\n'.join(cols)); lines.append(');\n')
 (SQL/'01_Create_Lyra_Snowflake_Tables.sql').write_text('\n'.join(lines),encoding='utf-8')
 md='# Lyra Wellbeing Analytics Additional Data Model\n\nThis pack extends your supplied healthcare data into a Lyra-relevant employee wellbeing analytics model.\n\n## Generated Tables\n\n| Table | Rows | Columns |\n|---|---:|---:|\n'
 for r in counts: md+=f"| {r['TableName']} | {r['RowCount']:,} | {r['ColumnCount']} |\n"
 md+='''\n## ERD\n```text\nDimDate ─┬─ FactCounsellingSessions ─ DimServiceType ─ DimIssueCategory\n         │             ├ DimClientCompany ─ DimCountry ─ DimCurrency\n         │             ├ DimFacilityGeography\n         │             ├ DimCounsellor\n         │             ├ DimEmployee_SCD2\n         │             └ DimConsent_SCD2\n         ├─ FactMedicationSales ─ DimMedication\n         ├─ FactDigitalEngagement\n         └─ FactPatientExperience\n```\n\nThe main million-row tables are FactCounsellingSessions, FactMedicationSales and FactDigitalEngagement.\n'''
 (DOC/'Data_Model_and_Project_Guide.md').write_text(md,encoding='utf-8')
 shutil.copy2(__file__,CODE/'continue_project.py')
 shutil.copy2(BASE/'build_project_chunked.py',CODE/'build_project_chunked.py')
 z=BASE/'Lyra_Analytics_Project.zip'
 if z.exists(): z.unlink()
 with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as zipf:
  for f in PROJ.rglob('*'):
   if f.is_file(): zipf.write(f,f.relative_to(PROJ.parent))
 print('zip',z,z.stat().st_size/1024/1024)

patient_experience(); medication_sales_fast(); digital(); scd(); docs_zip()
