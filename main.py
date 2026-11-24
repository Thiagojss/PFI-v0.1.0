from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from pathlib import Path
import sqlite3, datetime, math
BASE=Path(__file__).resolve().parent
DB=BASE/'data'/'pfi.db'
DB.parent.mkdir(exist_ok=True)
app=FastAPI(title='PFI',version='0.1.0')
def connect():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
    with connect() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS assets(id INTEGER PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,cents INTEGER NOT NULL CHECK(cents>=0),note TEXT NOT NULL DEFAULT ''); CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1),goal INTEGER NOT NULL,expenses INTEGER NOT NULL); CREATE TABLE IF NOT EXISTS movements(id INTEGER PRIMARY KEY,day TEXT NOT NULL,kind TEXT NOT NULL,cents INTEGER NOT NULL,note TEXT NOT NULL); CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY);''')
        if not c.execute("SELECT 1 FROM meta WHERE key='seed'").fetchone():
            c.execute('INSERT INTO settings VALUES(1,1000000,0)'); c.execute("INSERT INTO meta VALUES('seed')")
init()
@app.middleware('http')
async def local_only(request:Request,call_next):
    from fastapi.responses import JSONResponse
    if request.headers.get('host','').split(':')[0] not in ('localhost','127.0.0.1','testserver') or (request.method not in ('GET','HEAD') and request.headers.get('origin') not in (None,'http://127.0.0.1:8000','http://localhost:8000')):
        return JSONResponse({'detail':'Acesso local apenas'},403)
    return await call_next(request)
class Asset(BaseModel):
    name:str=Field(min_length=1,max_length=100); kind:str; cents:int=Field(ge=0,le=10**13); note:str=Field(default='',max_length=500)
class Movement(BaseModel):
    day:datetime.date; kind:str; cents:int=Field(gt=0,le=10**13); note:str=Field(default='',max_length=500)
class Settings(BaseModel):
    goal:int=Field(gt=0,le=10**13); expenses:int=Field(ge=0,le=10**13)
@app.get('/api/state')
def state():
    with connect() as c:
        return {'assets':[dict(x) for x in c.execute('SELECT * FROM assets ORDER BY id')],'movements':[dict(x) for x in c.execute('SELECT * FROM movements ORDER BY day DESC,id DESC')],'settings':dict(c.execute('SELECT * FROM settings').fetchone())}
@app.post('/api/assets')
def add(a:Asset):
    if a.kind not in ('asset','debt'): raise HTTPException(422,'Tipo inválido')
    with connect() as c: c.execute('INSERT INTO assets(name,kind,cents,note) VALUES(?,?,?,?)',(a.name,a.kind,a.cents,a.note))
    return {'ok':True}
@app.put('/api/assets/{id}')
def edit(id:int,a:Asset):
    if a.kind not in ('asset','debt'): raise HTTPException(422,'Tipo inválido')
    with connect() as c:
        if not c.execute('UPDATE assets SET name=?,kind=?,cents=?,note=? WHERE id=?',(a.name,a.kind,a.cents,a.note,id)).rowcount: raise HTTPException(404)
    return {'ok':True}
@app.delete('/api/assets/{id}')
def delete(id:int):
    with connect() as c: c.execute('DELETE FROM assets WHERE id=?',(id,))
    return {'ok':True}
@app.post('/api/movements')
def movement(a:Movement):
    if a.kind not in ('income','expense','contribution','withdrawal'): raise HTTPException(422,'Tipo inválido')
    with connect() as c: c.execute('INSERT INTO movements(day,kind,cents,note) VALUES(?,?,?,?)',(str(a.day),a.kind,a.cents,a.note))
    return {'ok':True}
@app.delete('/api/movements/{id}')
def remove_movement(id:int):
    with connect() as c: c.execute('DELETE FROM movements WHERE id=?',(id,))
    return {'ok':True}
@app.put('/api/settings')
def settings(s:Settings):
    with connect() as c: c.execute('UPDATE settings SET goal=?,expenses=? WHERE id=1',(s.goal,s.expenses))
    return {'ok':True}
@app.get('/api/backup')
def backup():
    import tempfile
    from starlette.background import BackgroundTask
    with tempfile.NamedTemporaryFile(suffix='.db',delete=False) as f: p=Path(f.name)
    with connect() as c, sqlite3.connect(p) as dest: c.backup(dest)
    return FileResponse(p,filename='pfi-backup.db',background=BackgroundTask(p.unlink))
def projection(capital,aporte,annual,months):
    r=math.expm1(math.log1p(annual/100)/12)
    return capital*(1+r)**months+aporte*(math.expm1(months*math.log1p(r))/r if r else months)
@app.get('/api/project')
def project(capital:float=50000,aporte:float=2000,annual:float=9,years:int=10):
    if not all(math.isfinite(x) for x in (capital,aporte,annual)) or not(0<=capital<=1e10 and 0<=aporte<=1e7 and -50<=annual<=50 and 1<=years<=50): raise HTTPException(422,'Parâmetros inválidos')
    return [{'year':y,'value':round(projection(capital,aporte,annual,y*12),2),'paid':capital+aporte*y*12} for y in range(years+1)]
@app.get('/')
def home(): return FileResponse(BASE/'static'/'index.html')
app.mount('/static',StaticFiles(directory=BASE/'static'),name='static')
