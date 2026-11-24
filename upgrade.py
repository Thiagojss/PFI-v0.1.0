import sqlite3, datetime, csv, io
from pathlib import Path
from contextlib import closing
from fastapi import HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

def install(app, connect, db):
    # Additive migration, backup before schema change. No synthetic history.
    with closing(connect()) as c:
        if not c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='snapshots'").fetchone():
            backup=db.with_name('pfi-pre-v02-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.db')
            with closing(sqlite3.connect(backup)) as dest: c.backup(dest)
        with c:
            c.execute('BEGIN IMMEDIATE')
            c.execute('CREATE TABLE IF NOT EXISTS snapshots(day TEXT PRIMARY KEY, gross INTEGER NOT NULL, debt INTEGER NOT NULL)')
            c.execute('CREATE TABLE IF NOT EXISTS installments(asset_id INTEGER PRIMARY KEY, amount INTEGER NOT NULL CHECK(amount>0), remaining INTEGER NOT NULL CHECK(remaining>=0))')
            c.execute('CREATE TABLE IF NOT EXISTS payments(id INTEGER PRIMARY KEY, asset_id INTEGER NOT NULL, day TEXT NOT NULL, amount INTEGER NOT NULL, name TEXT NOT NULL)')
            if 'category' not in [r[1] for r in c.execute('PRAGMA table_info(movements)')]:
                c.execute("ALTER TABLE movements ADD COLUMN category TEXT NOT NULL DEFAULT 'Outros'")
    class Snapshot(BaseModel):
        day:datetime.date
    class Plan(BaseModel):
        amount:int=Field(gt=0,le=10**13)
        remaining:int=Field(ge=1,le=600)
    class Payment(BaseModel):
        day:datetime.date
        expected_remaining:int=Field(ge=1,le=600)
    class Category(BaseModel):
        category:str=Field(min_length=1,max_length=80)
    @app.get('/api/history')
    def history():
        with closing(connect()) as c:
            return [dict(r) for r in c.execute('SELECT *,gross-debt AS net FROM snapshots ORDER BY day')]
    @app.post('/api/history')
    def snapshot(s:Snapshot):
        if s.day!=datetime.date.today(): raise HTTPException(422,'Registre somente a posição de hoje')
        with closing(connect()) as c, c:
            c.execute('BEGIN IMMEDIATE')
            gross,debt=c.execute("SELECT COALESCE(SUM(CASE WHEN kind='asset' THEN cents ELSE 0 END),0),COALESCE(SUM(CASE WHEN kind='debt' THEN cents ELSE 0 END),0) FROM assets").fetchone()
            c.execute('INSERT INTO snapshots VALUES(?,?,?) ON CONFLICT(day) DO UPDATE SET gross=excluded.gross,debt=excluded.debt',(str(s.day),gross,debt))
        return {'ok':True}
    @app.get('/api/installments')
    def installments():
        with closing(connect()) as c:
            return {'plans':[dict(r) for r in c.execute("SELECT i.*,a.name,a.cents FROM installments i JOIN assets a ON a.id=i.asset_id WHERE a.kind='debt'")], 'payments':[dict(r) for r in c.execute('SELECT * FROM payments ORDER BY id DESC')]}
    @app.put('/api/installments/{id}')
    def plan(id:int,p:Plan):
        with closing(connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            a=c.execute("SELECT cents FROM assets WHERE id=? AND kind='debt'",(id,)).fetchone()
            if not a: raise HTTPException(404,'Dívida não encontrada')
            if a[0]!=p.amount*p.remaining: raise HTTPException(409,'Saldo deve corresponder ao total nominal das parcelas')
            c.execute('INSERT INTO installments VALUES(?,?,?) ON CONFLICT(asset_id) DO UPDATE SET amount=excluded.amount,remaining=excluded.remaining',(id,p.amount,p.remaining))
        return {'ok':True}
    @app.post('/api/installments/{id}/pay')
    def pay(id:int,p:Payment):
        if p.day>datetime.date.today(): raise HTTPException(422,'Data futura')
        with closing(connect()) as c,c:
            c.execute('BEGIN IMMEDIATE')
            a=c.execute("SELECT i.*,a.name,a.cents FROM installments i JOIN assets a ON a.id=i.asset_id WHERE a.kind='debt' AND a.id=?",(id,)).fetchone()
            if not a: raise HTTPException(404,'Plano não encontrado')
            if a['remaining']!=p.expected_remaining or a['cents']!=a['amount']*a['remaining']: raise HTTPException(409,'Plano desatualizado; revise o saldo')
            c.execute('UPDATE assets SET cents=cents-? WHERE id=?',(a['amount'],id))
            c.execute('UPDATE installments SET remaining=remaining-1 WHERE asset_id=?',(id,))
            c.execute('INSERT INTO payments(asset_id,day,amount,name) VALUES(?,?,?,?)',(id,str(p.day),a['amount'],a['name']))
        return {'ok':True}
    @app.put('/api/movements/{id}/category')
    def category(id:int,p:Category):
        with closing(connect()) as c,c:
            if not c.execute('UPDATE movements SET category=? WHERE id=?',(p.category.strip() or 'Outros',id)).rowcount: raise HTTPException(404)
        return {'ok':True}
    @app.get('/api/report')
    def report(month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')):
        with closing(connect()) as c:
            rows=[dict(r) for r in c.execute('SELECT * FROM movements WHERE substr(day,1,7)=? ORDER BY day,id',(month,))]
        totals={k:sum(r['cents'] for r in rows if r['kind']==k) for k in ('income','expense','contribution','withdrawal')}
        categories={k:sum(r['cents'] for r in rows if r['kind']=='expense' and r['category']==k) for k in sorted({r['category'] for r in rows if r['kind']=='expense'})}
        return {'month':month,'totals':totals,'balance':totals['income']-totals['expense'],'net_contributions':totals['contribution']-totals['withdrawal'],'categories':categories,'rows':rows}
    @app.get('/api/report.csv')
    def export(month:str=Query(pattern=r'^\d{4}-(0[1-9]|1[0-2])$')):
        data=report(month); out=io.StringIO(); w=csv.writer(out,delimiter=';'); w.writerow(['Data','Tipo','Categoria','Valor BRL','Descrição'])
        def safe(s): return "'"+s if s.lstrip().startswith(('=','+','-','@')) or s.startswith(('\t','\r','\n')) else s
        for r in data['rows']: w.writerow([r['day'],r['kind'],safe(r['category']),f"{r['cents']/100:.2f}".replace('.',','),safe(r['note'])])
        return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':f'attachment; filename="pfi-{month}.csv"'})
