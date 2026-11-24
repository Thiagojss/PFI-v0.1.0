import unittest, tempfile, datetime, sqlite3
from pathlib import Path
from contextlib import closing
from unittest.mock import patch
from fastapi.testclient import TestClient
import os, atexit
_test_dir=tempfile.TemporaryDirectory()
atexit.register(_test_dir.cleanup)
os.environ.setdefault("PFI_DB", _test_dir.name+"/test.db")
import main
from upgrade import install
class UpgradeTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.p=patch.object(main,'DB',Path(self.tmp.name)/'pfi.db'); self.p.start(); self.addCleanup(self.p.stop)
        main.init(); from fastapi import FastAPI
        install(FastAPI(),main.connect,main.DB); self.client=TestClient(main.app); self.today=str(datetime.date.today())
    def test_migration(self):
        with closing(main.connect()) as c, c: c.execute("INSERT INTO movements(day,kind,cents,note) VALUES('2026-01-01','income',123,'preserve')")
        from fastapi import FastAPI
        install(FastAPI(),main.connect,main.DB)
        self.assertEqual(self.client.get('/api/state').json()['movements'][0]['cents'],123)
        self.assertEqual(len(list(main.DB.parent.glob('pfi-pre-*.db'))),1)
    def test_history(self):
        self.assertEqual(self.client.get('/api/history').json(),[])
        for _ in range(2): self.assertEqual(self.client.post('/api/history',json={'day':self.today}).status_code,200)
        h=self.client.get('/api/history').json(); self.assertEqual(len(h),1); self.assertEqual(h[0]['net'],4478900)
    def test_installments(self):
        self.assertEqual(self.client.put('/api/installments/2',json={'amount':57900,'remaining':8}).status_code,409)
        self.assertEqual(self.client.put('/api/installments/2',json={'amount':57900,'remaining':9}).status_code,200)
        p={'day':self.today,'expected_remaining':9}
        self.assertEqual(self.client.post('/api/installments/2/pay',json=p).status_code,200)
        self.assertEqual(self.client.post('/api/installments/2/pay',json=p).status_code,409)
        self.assertEqual(self.client.get('/api/installments').json()['plans'][0]['cents'],463200)
    def test_reports(self):
        for k,v in [('income',300000),('expense',100000),('contribution',200000)]: self.assertEqual(self.client.post('/api/movements',json={'day':self.today,'kind':k,'cents':v,'note':'=unsafe'}).status_code,200)
        self.assertEqual(self.client.put('/api/movements/2/category',json={'category':'Casa'}).status_code,200)
        r=self.client.get('/api/report',params={'month':self.today[:7]}).json(); self.assertEqual(r['balance'],200000); self.assertEqual(r['categories'],{'Casa':100000})
        self.assertIn("'=unsafe",self.client.get('/api/report.csv',params={'month':self.today[:7]}).text)
        self.assertEqual(self.client.get('/api/report?month=2026-99').status_code,422)
    def test_existing(self):
        self.assertEqual(self.client.get('/').status_code,200); self.assertEqual(self.client.get('/static/upgrade.js').status_code,200); self.assertEqual(self.client.get('/api/backup').status_code,200)
