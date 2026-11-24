"""Additive PFI 1.0 modules. Money in integer cents; valuations are manual."""
import datetime as dt, sqlite3, math, json
from contextlib import closing
from concurrent.futures import ThreadPoolExecutor
from urllib.request import urlopen
from urllib.parse import urlencode
from typing import Literal
from fastapi import HTTPException
from pydantic import BaseModel, Field

CLASSES=('Caixa','CDB','LCI','LCA','Tesouro Selic','Tesouro IPCA+','Tesouro Prefixado','Ação','FII','ETF','Cripto','Outro')
SERIES={'Selic meta':(432,'% a.a.'),'CDI diário':(12,'% a.d.'),'IPCA mensal':(433,'% a.m.'),'USD/BRL':(1,'R$/USD')}
def migrate(connect,db):
    with closing(connect()) as c:
        if not c.execute("SELECT 1 FROM meta WHERE key='pfi_v1'").fetchone():
            with closing(sqlite3.connect(db.with_name('pfi-pre-v1-'+dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db'))) as dest: c.backup(dest)
            with c:
                c.execute('BEGIN IMMEDIATE')
                c.execute('CREATE TABLE IF NOT EXISTS positions(asset_id INTEGER PRIMARY KEY, institution TEXT NOT NULL, classe TEXT NOT NULL, principal INTEGER NOT NULL, liquidity INTEGER NOT NULL, maturity TEXT, rate TEXT NOT NULL, asof TEXT NOT NULL)')
                c.execute('CREATE TABLE IF NOT EXISTS position_flows(id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL, day TEXT NOT NULL, kind TEXT NOT NULL, cents INTEGER NOT NULL)')
                c.execute('CREATE TABLE IF NOT EXISTS market(name TEXT PRIMARY KEY, value REAL NOT NULL, day TEXT NOT NULL, unit TEXT NOT NULL, fetched TEXT NOT NULL)')
                c.execute('CREATE TABLE IF NOT EXISTS targets(classe TEXT PRIMARY KEY, weight REAL NOT NULL)')
                c.execute('CREATE TABLE IF NOT EXISTS preferences(id INTEGER PRIMARY KEY, reserve_months INTEGER NOT NULL, horizon INTEGER NOT NULL, withdrawal REAL NOT NULL)')
                c.execute('INSERT OR IGNORE INTO preferences VALUES(1,12,20,3)')
                c.executemany('INSERT OR IGNORE INTO targets VALUES(?,?)',[('Caixa',10),('Tesouro Selic',30),('CDB',40),('Tesouro IPCA+',20)])
                c.execute("INSERT OR IGNORE INTO meta VALUES('pfi_v1')")
class Position(BaseModel):
    institution:str=Field(min_length=1,max_length=120)
    classe:str
    principal:int=Field(ge=0,le=10**13)
    liquidity:bool
    maturity:dt.date|None=None
    rate:str=Field(default='',max_length=120)
    asof:dt.date
class Flow(BaseModel):
    day:dt.date
    kind:Literal['aporte','resgate','provento']
    cents:int=Field(gt=0,le=10**13)
class Compare(BaseModel):
    capital:float=Field(gt=0,le=1e10)
    days:int=Field(ge=30,le=10950)
    business_days:int=Field(ge=0,le=8000)
    cdi:float=Field(ge=0,le=50)
    rate_a:float=Field(ge=0,le=200)
    rate_b:float=Field(ge=0,le=200)
    tax_a:float=Field(ge=0,le=100)
    tax_b:float=Field(ge=0,le=100)
class Plan(BaseModel):
    capital:float=Field(ge=0,le=1e10)
    monthly:float=Field(ge=0,le=1e7)
    expenses:float=Field(gt=0,le=1e7)
    nominal:float=Field(ge=-50,le=50)
    inflation:float=Field(ge=0,le=30)
    withdrawal:float=Field(gt=0,le=15)
    years:int=Field(ge=1,le=50)
class Pref(BaseModel):
    reserve_months:int=Field(ge=1,le=36)
    horizon:int=Field(ge=1,le=365)
    withdrawal:float=Field(gt=0,le=15)

def compare(p):
    if p.business_days>p.days: raise HTTPException(422,'Dias úteis não podem exceder dias corridos')
    daily=math.expm1(math.log1p(p.cdi/100)/252)
    result=[]
    for label,rate,tax in [('A',p.rate_a,p.tax_a),('B',p.rate_b,p.tax_b)]:
        gross=p.capital*math.expm1(p.business_days*math.log1p(daily*rate/100)); ir=gross*tax/100
        result.append(dict(label=label,gross=round(gross,2),tax=round(ir,2),net=round(gross-ir,2),total=round(p.capital+gross-ir,2)))
    return result

def plan(p):
    real=(1+p.nominal/100)/(1+p.inflation/100)-1
    r=math.expm1(math.log1p(real)/12); target=p.expenses*12/(p.withdrawal/100)
    rows=[]
    for y in range(p.years+1):
        n=y*12; v=p.capital*math.exp(n*math.log1p(r))+p.monthly*(math.expm1(n*math.log1p(r))/r if r else n)
        rows.append(dict(year=y,value=round(v,2)))
    return dict(real_rate=real*100,target=target,rows=rows,first_year=next((x['year'] for x in rows if x['value']>=target),None))

def fetch_series(name,code,unit):
    today=dt.date.today(); start=today-dt.timedelta(days=120 if code==433 else 15)
    url=f'https://api.bcb.gov.br/dados/serie/bcdata.sgs.{code}/dados?'+urlencode({'formato':'json','dataInicial':start.strftime('%d/%m/%Y'),'dataFinal':today.strftime('%d/%m/%Y')})
    with urlopen(url,timeout=8) as f: rows=json.loads(f.read(1000000))
    pairs=[(dt.datetime.strptime(x['data'],'%d/%m/%Y').date(),float(x['valor'])) for x in rows]
    day,value=max(pairs,key=lambda x:x[0]); assert math.isfinite(value) and day<=today
    return (name,value,str(day),unit,dt.datetime.now(dt.timezone.utc).isoformat())

def install(app,connect,db):
    migrate(connect,db)
    @app.get('/api/v1/positions')
    def positions():
        with closing(connect()) as c:
            return [dict(x) for x in c.execute("SELECT a.id,a.name,a.cents,p.* FROM assets a LEFT JOIN positions p ON p.asset_id=a.id WHERE a.kind='asset' ORDER BY a.id")]
    @app.put('/api/v1/positions/{id}')
    def position(id:int,p:Position):
        if p.classe not in CLASSES or p.asof>dt.date.today(): raise HTTPException(422,'Classe ou data inválida')
        with closing(connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute("SELECT 1 FROM assets WHERE id=? AND kind='asset'",(id,)).fetchone(): raise HTTPException(404,'Ativo não encontrado')
            c.execute('INSERT OR REPLACE INTO positions VALUES(?,?,?,?,?,?,?,?)',(id,p.institution,p.classe,p.principal,int(p.liquidity),str(p.maturity) if p.maturity else None,p.rate,str(p.asof)))
        return {'ok':True}
    @app.get('/api/v1/flows')
    def flows():
        with closing(connect()) as c: return [dict(x) for x in c.execute('SELECT f.*,a.name FROM position_flows f LEFT JOIN assets a ON a.id=f.asset_id ORDER BY day DESC,f.id DESC')]
    @app.post('/api/v1/positions/{id}/flows')
    def flow(id:int,p:Flow):
        if p.day>dt.date.today(): raise HTTPException(422,'Data futura')
        with closing(connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            if not c.execute("SELECT 1 FROM assets WHERE id=? AND kind='asset'",(id,)).fetchone(): raise HTTPException(404,'Ativo não encontrado')
            c.execute('INSERT INTO position_flows(asset_id,day,kind,cents) VALUES(?,?,?,?)',(id,str(p.day),p.kind,p.cents))
        return {'ok':True}
    @app.delete('/api/v1/flows/{id}')
    def delete_flow(id:int):
        with closing(connect()) as c,c: c.execute('DELETE FROM position_flows WHERE id=?',(id,))
        return {'ok':True}
    @app.get('/api/v1/market')
    def market():
        with closing(connect()) as c: return [dict(x) for x in c.execute('SELECT * FROM market ORDER BY name')]
    @app.post('/api/v1/market/refresh')
    def refresh():
        errors=[]; results=[]
        with ThreadPoolExecutor(max_workers=4) as pool:
            jobs={n:pool.submit(fetch_series,n,*v) for n,v in SERIES.items()}
            for n,f in jobs.items():
                try: results.append(f.result())
                except Exception: errors.append(n)
        with closing(connect()) as c,c: c.executemany('INSERT OR REPLACE INTO market VALUES(?,?,?,?,?)',results)
        return {'updated':len(results),'failed':errors,'data':market()}
    @app.post('/api/v1/compare')
    def comparison(p:Compare): return compare(p)
    @app.post('/api/v1/plan')
    def planning(p:Plan): return plan(p)
    @app.get('/api/v1/preferences')
    def preferences():
        with closing(connect()) as c: return dict(c.execute('SELECT * FROM preferences WHERE id=1').fetchone())
    @app.put('/api/v1/preferences')
    def save_preferences(p:Pref):
        with closing(connect()) as c,c: c.execute('UPDATE preferences SET reserve_months=?,horizon=?,withdrawal=? WHERE id=1',(p.reserve_months,p.horizon,p.withdrawal))
        return {'ok':True}
    @app.get('/api/v1/targets')
    def targets():
        with closing(connect()) as c: return {x[0]:x[1] for x in c.execute('SELECT * FROM targets')}
    @app.put('/api/v1/targets')
    def save_targets(weights:dict[str,float]):
        if not weights or any(k not in CLASSES or not math.isfinite(v) or not 0<=v<=100 for k,v in weights.items()) or abs(sum(weights.values())-100)>1e-6: raise HTTPException(422,'Pesos devem somar 100%')
        with closing(connect()) as c,c:
            c.execute('DELETE FROM targets'); c.executemany('INSERT INTO targets VALUES(?,?)',weights.items())
        return {'ok':True}
    @app.get('/api/v1/analysis')
    def analysis():
        rows=positions(); pref=preferences(); weights=targets(); total=sum(x['cents'] for x in rows); liquid=sum(x['cents'] for x in rows if x['liquidity']==1); unknown=sum(x['cents'] for x in rows if x['asset_id'] is None); by={}; inst={}; alerts=[]
        with closing(connect()) as c: expenses=c.execute('SELECT expenses FROM settings WHERE id=1').fetchone()[0]
        for x in rows:
            k=x['classe'] or 'Não classificado'; by[k]=by.get(k,0)+x['cents']; k=x['institution'] or 'Não informado'; inst[k]=inst.get(k,0)+x['cents']
            if x['maturity']:
                days=(dt.date.fromisoformat(x['maturity'])-dt.date.today()).days
                if days<=pref['horizon']: alerts.append(f"{x['name']}: vencido ou vencendo em {days} dias")
            if x['asof'] and (dt.date.today()-dt.date.fromisoformat(x['asof'])).days>30: alerts.append(f"{x['name']}: saldo informado há mais de 30 dias")
        if unknown: alerts.append('Existem ativos sem classificação; liquidez pode estar subestimada.')
        if liquid<expenses*pref['reserve_months']: alerts.append('Liquidez declarada abaixo da reserva-alvo; confira elegibilidade e acesso.')
        for k,v in inst.items():
            if k!='Não informado' and total and v/total>.5: alerts.append(f'Concentração superior a 50% em {k}; avaliar risco do emissor e cobertura.')
        return dict(total=total,liquid=liquid,unknown=unknown,reserve=expenses*pref['reserve_months'],classes=by,institutions=inst,alerts=alerts,allocation=[dict(classe=k,actual=by.get(k,0),target=round(total*weights.get(k,0)/100)) for k in sorted(set(by)|set(weights))])
