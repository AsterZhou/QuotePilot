import json,uuid
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path,monkeypatch):
 import server
 monkeypatch.setattr(server,'DB',tmp_path/'manual.db');monkeypatch.setenv('QUOTEPILOT_PROVIDER','mock')
 with TestClient(server.app) as c:yield c

def setup(client):
 p=Path('tests/foreign_v07/08_scan_manual.eml');r=client.post('/api/emails/import',files={'file':(p.name,p.read_bytes(),'message/rfc822')});assert r.status_code==200 and r.json()['new_lines']==0
 email='<08_scan_manual.eml@fresh07.invalid>';files=client.get('/api/emails/'+email+'/sources').json();source=next(x for x in files if x['filename']=='scan.pdf')
 body={'entry_key':str(uuid.uuid4()),'source_id':source['id'],'source_locator':'page 1 / item 0001','actor':'TEST_ONLY','reason':'合成扫描件逐项核对','source_rfq_no':'F07-MANUAL','part_number':'PN-0001','quantity':3,'unit':'EA','condition':'FN','confirm_source':True}
 return email,body

def test_manual_scan_to_quote_and_idempotence(client):
 email,body=setup(client);url='/api/emails/'+email+'/manual-lines'
 r=client.post(url,json=body);assert r.status_code==200,r.text;receipt=r.json()
 assert client.post(url,json=body).json()['idempotent']
 detail=client.get('/api/lines/'+str(receipt['line_ids'][0])).json();raw=json.loads(detail['evidence']['raw_json']);assert raw['provider']=='human' and raw['source_id']==body['source_id'] and raw['source_sha256']
 q=client.post('/api/quote',json={'line_ids':receipt['line_ids'],'asof':'2026-09-20'}).json();assert q['total_cny']=='49.89'
 body['quantity']=4;assert client.post(url,json=body).status_code==409

def test_manual_confirmation_required(client):
 email,body=setup(client);body['confirm_source']=False
 assert client.post('/api/emails/'+email+'/manual-lines',json=body).status_code==409

def test_manual_source_must_belong_to_email(client):
 email,body=setup(client);body['source_id']='not-this-email'
 assert client.post('/api/emails/'+email+'/manual-lines',json=body).status_code==409

@pytest.mark.parametrize('quantity',[0,-1,1.5,'3'])
def test_invalid_manual_quantity(client,quantity):
 email,body=setup(client);body['quantity']=quantity
 assert client.post('/api/emails/'+email+'/manual-lines',json=body).status_code==422
