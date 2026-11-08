"""Contracts only; real provider receipts are separately captured through the browser."""
import json
from fastapi.testclient import TestClient
from test_commercial import clients,setup_inputs
from test_genesis_workflow import client,setup_run


def test_model_input_receipt_is_retrievable(client,monkeypatch):
    run=setup_run(client,monkeypatch)
    assert 'Please quote three EA' in run['input_text'] and len(run['input_sha256'])==64
    loaded=client.get('/api/extractions/'+run['run_id']).json()
    assert loaded['input_text']==run['input_text'] and loaded['input_sha256']==run['input_sha256']
    saved=client.get('/api/emails/%3Cworkflow%40qa.invalid%3E/extractions').json()['rows'];assert saved[0]['id']==run['run_id']


def test_commercial_sync_enforces_approval_roles_and_saved_receipt(clients,monkeypatch):
    admin,reviewer,db=clients;lid,ids,req=setup_inputs(admin,reviewer,0)
    q=reviewer.post('/api/commercial-quotes',json=req).json();url='/api/commercial-quotes/'+q['id']+'/sync-matrixone'
    assert reviewer.post(url,json={}).status_code==403
    assert admin.post(url,json={}).status_code==409
    b={'version':1,'actor':'TEST_ONLY','reason':'合成集成验收','confirm_risks':True}
    assert reviewer.post('/api/commercial-quotes/'+q['id']+'/review',json=b).status_code==200
    assert admin.post('/api/commercial-quotes/'+q['id']+'/approve',json={**b,'version':2}).status_code==200
    import quotepilot.moi_sql as sql,quotepilot.platform_quotes as mirror
    monkeypatch.setattr(sql,'MOISQLClient',lambda:type('ContractClient',(),{'workspace':'CONTRACT_ONLY'})())
    monkeypatch.setattr(mirror,'mirror_commercial_quote',lambda c,q:{'verified':True,'quote_id':q['id'],'version':q['version'],'query_ids':['CONTRACT_ONLY'],'scope':'application_orchestrated_approved_commercial_snapshot'})
    monkeypatch.setenv('MOI_WORKSPACE_ID','CONTRACT_ONLY')
    r=admin.post(url,json={});assert r.status_code==200 and r.json()['verified']
    receipt=admin.get('/api/commercial-quotes/'+q['id']+'/matrixone-receipt').json();assert receipt['verified'] and receipt['evidence_type']=='saved_successful_readback_not_live_ping'
    from quotepilot.store import open_db
    with open_db(db) as con:
        row=con.execute('SELECT receipt_json FROM cloud_quote_receipts WHERE quote_id=?',(q['id'],)).fetchone();assert json.loads(row[0])['query_ids']==['CONTRACT_ONLY']
    def fail(*_):raise ValueError('readback conflict')
    monkeypatch.setattr(mirror,'mirror_commercial_quote',fail)
    assert admin.post(url,json={}).status_code==409
