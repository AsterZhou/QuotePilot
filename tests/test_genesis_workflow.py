"""Network contracts are mocked here; separate live_smoke.py makes real calls."""
from pathlib import Path
from email.message import EmailMessage
import json
import httpx,pytest
from fastapi.testclient import TestClient
from quotepilot.providers import GenesisProvider
from quotepilot.store import open_db

@pytest.fixture
def client(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(server,'DB',tmp_path/'workflow.db')
    monkeypatch.setenv('QUOTEPILOT_PROVIDER','mock')
    with TestClient(server.app) as c:yield c

def setup_run(client,monkeypatch,simulated=False):
    import quotepilot.providers as providers
    m=EmailMessage();m['From']='QA <qa@example.invalid>';m['Subject']='New prose RFQ';m['Message-ID']='<workflow@qa.invalid>'
    m.set_content('Please quote three EA of PN-0001 in FN condition.')
    r=client.post('/api/emails/import',files={'file':('test.eml',m.as_bytes(),'message/rfc822')});assert r.status_code==200
    class Fake:
        def extract(self,text):return {'provider':'mock' if simulated else 'genesis','simulated':simulated,'model':'test-model','response_id':'test-only-response','review_required':True,'lines':[{'part_number':'PN-0001','quantity':3,'unit':'EA','condition':'FN','evidence':'Please quote three EA of PN-0001 in FN condition.'}]}
    monkeypatch.setattr(providers,'get_provider',lambda:Fake())
    run=client.post('/api/emails/%3Cworkflow%40qa.invalid%3E/extract',json={});assert run.status_code==200,run.text
    return run.json()

def confirm_body(run):return {'actor':'TEST_ONLY','reason':'合成数据字段核对','confirm_source':True,'lines':[{'source_index':0,'part_number':'PN-0001','quantity':3,'unit':'EA','condition':'FN','source_rfq_no':'SYNTHETIC-QA'}]}

def test_suggestions_do_not_create_rows_before_confirmation(client,monkeypatch):
    run=setup_run(client,monkeypatch)
    assert client.get('/api/lines',params={'email_id':'<workflow@qa.invalid>'}).json()['total']==0
    assert client.get('/api/extractions/'+run['run_id']).json()['status']=='pending'

def test_confirm_and_quote_preserve_evidence(client,monkeypatch):
    run=setup_run(client,monkeypatch);body=confirm_body(run);body['lines'][0]['quantity']=4
    confirmed=client.post('/api/extractions/'+run['run_id']+'/confirm',json=body);assert confirmed.status_code==200,confirmed.text
    obj=confirmed.json();assert obj['new_lines']==1
    detail=client.get('/api/lines/'+str(obj['line_ids'][0])).json();evidence=json.loads(detail['evidence']['raw_json'])
    assert evidence['original_model_suggestion']['quantity']==3 and evidence['confirmed_fields']['quantity']==4
    quote=client.post('/api/quote',json={'line_ids':obj['line_ids'],'asof':'2026-09-20'}).json();assert quote['total_cny']=='66.52'
    again=client.post('/api/extractions/'+run['run_id']+'/confirm',json=body).json();assert again['idempotent'] and again['line_ids']==obj['line_ids']

def test_explicit_confirmation_required(client,monkeypatch):
    run=setup_run(client,monkeypatch);body=confirm_body(run);body['confirm_source']=False
    assert client.post('/api/extractions/'+run['run_id']+'/confirm',json=body).status_code==409

def test_mock_cannot_be_committed(client,monkeypatch):
    run=setup_run(client,monkeypatch,True)
    assert client.post('/api/extractions/'+run['run_id']+'/confirm',json=confirm_body(run)).status_code==409

def test_duplicate_indices_roll_back(client,monkeypatch):
    run=setup_run(client,monkeypatch);body=confirm_body(run);body['lines']*=2
    assert client.post('/api/extractions/'+run['run_id']+'/confirm',json=body).status_code==409
    assert client.get('/api/extractions/'+run['run_id']).json()['status']=='pending'

def test_responses_api_contract(monkeypatch):
    monkeypatch.setenv('GENESIS_ACCESS_TOKEN','fake');monkeypatch.setenv('GENESIS_MODEL_ID','test');monkeypatch.setenv('GENESIS_API_STYLE','responses')
    def respond(req):
        body=json.loads(req.content);assert req.url.path=='/v1/responses';assert body['store'] is False and body['max_output_tokens']==2048
        return httpx.Response(200,json={'id':'contract-only','status':'completed','usage':{'total_tokens':8},'output':[{'type':'reasoning'},{'type':'message','content':[{'type':'output_text','text':'{"lines":[{"part_number":"X-1","quantity":2,"evidence":"X-1 two"}]}'}]}]})
    result=GenesisProvider(httpx.MockTransport(respond)).extract('X-1 two')
    assert result['response_id']=='contract-only' and result['usage']['total_tokens']==8

def test_incomplete_responses_rejected(monkeypatch):
    monkeypatch.setenv('GENESIS_ACCESS_TOKEN','fake');monkeypatch.setenv('GENESIS_MODEL_ID','test');monkeypatch.setenv('GENESIS_API_STYLE','responses')
    p=GenesisProvider(httpx.MockTransport(lambda req:httpx.Response(200,json={'status':'incomplete','output':[]})))
    with pytest.raises(ValueError,match='未完成'):p.extract('anything')

def test_false_verified_status_without_config(client,monkeypatch):
    setup_run(client,monkeypatch)
    state=client.get('/api/integration').json();assert not state['genesis_configured'] and not state['model_connected'] and not state['matrixone_connected']
