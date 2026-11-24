import unittest, tempfile, datetime, sqlite3
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
import main, intelligence
from upgrade import install
class V1Test(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=patch.object(main,'DB',Path(self.tmp.name)/'pfi.db'); self.p.start(); self.addCleanup(self.p.stop)
        main.init(); install(FastAPI(),main.connect,main.DB); intelligence.migrate(main.connect,main.DB)
        self.c=TestClient(main.app); self.today=str(datetime.date.today())
    def position(self,**kw):
        p=dict(institution='Caixa',classe='Caixa',principal=4900000,liquidity=True,maturity=None,rate='',asof=self.today);p.update(kw);return self.c.put('/api/v1/positions/1',json=p)
    def test_positions(self):
        self.assertEqual(self.position().status_code,200)
        r=self.c.get('/api/v1/positions').json(); self.assertEqual(len(r),1); self.assertEqual(r[0]['cents'],5000000);self.assertEqual(r[0]['principal'],4900000)
        self.assertEqual(self.position(classe='bad').status_code,422)
    def test_flow(self):
        self.assertEqual(self.c.post('/api/v1/positions/1/flows',json=dict(day=self.today,kind='aporte',cents=100)).status_code,200)
        self.assertEqual(self.c.get('/api/state').json()['assets'][0]['cents'],5000000)
        self.assertEqual(self.c.delete('/api/v1/flows/1').status_code,200);self.assertEqual(self.c.get('/api/v1/flows').json(),[])
    def test_targets(self):
        self.assertEqual(self.c.put('/api/v1/targets',json={'Caixa':99}).status_code,422)
        self.assertEqual(self.c.put('/api/v1/targets',json={'Caixa':100}).status_code,200)
        self.assertEqual(self.c.get('/api/v1/targets').json(),{'Caixa':100})
    def test_analysis(self):
        a=self.c.get('/api/v1/analysis').json();self.assertEqual(a['unknown'],5000000);self.assertEqual(a['liquid'],0)
        self.position(maturity=self.today);a=self.c.get('/api/v1/analysis').json();self.assertEqual(a['liquid'],5000000);self.assertEqual(a['reserve'],1200000);self.assertTrue(any('vencendo' in s for s in a['alerts']))
    def test_compare(self):
        p=dict(capital=10000,days=365,business_days=252,cdi=12,rate_a=100,rate_b=100,tax_a=17.5,tax_b=0)
        r=self.c.post('/api/v1/compare',json=p).json();self.assertEqual(r[0]['gross'],1200);self.assertEqual(r[0]['net'],990);self.assertEqual(r[1]['total'],11200)
        p['business_days']=366;self.assertEqual(self.c.post('/api/v1/compare',json=p).status_code,422)
    def test_plan(self):
        p=dict(capital=50000,monthly=2000,expenses=3000,nominal=4,inflation=4,withdrawal=3,years=1)
        r=self.c.post('/api/v1/plan',json=p).json();self.assertEqual(r['rows'][-1]['value'],74000);self.assertEqual(r['target'],1200000);self.assertIsNone(r['first_year'])
    def test_market_cache(self):
        def mock(n,c,u):return (n,1.0,self.today,u,'test')
        with patch('intelligence.fetch_series',side_effect=mock):self.assertEqual(self.c.post('/api/v1/market/refresh').json()['updated'],4)
        with patch('intelligence.fetch_series',side_effect=OSError):r=self.c.post('/api/v1/market/refresh').json();self.assertEqual(r['updated'],0);self.assertEqual(len(r['data']),4);self.assertEqual(len(r['failed']),4)
    def test_migration(self):
        self.position();self.c.put('/api/v1/targets',json={'Caixa':100});intelligence.migrate(main.connect,main.DB)
        self.assertEqual(self.c.get('/api/v1/targets').json(),{'Caixa':100});self.assertEqual(len(list(main.DB.parent.glob('pfi-pre-v1-*.db'))),1)
        with closing(sqlite3.connect(next(main.DB.parent.glob('pfi-pre-v1-*.db')))) as c:self.assertEqual(c.execute('SELECT cents FROM assets WHERE id=1').fetchone()[0],5000000)
    def test_local_security(self):
        self.assertEqual(self.c.get('/api/state',headers={'host':'evil.example'}).status_code,403)
        self.assertEqual(self.c.post('/api/v1/market/refresh',headers={'origin':'https://evil.example'}).status_code,403)
