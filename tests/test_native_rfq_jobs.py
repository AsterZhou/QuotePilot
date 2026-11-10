"""Offline contracts. All platform responses below are synthetic fixtures."""
import base64
import hashlib
import json
import re
from email.message import EmailMessage
from pathlib import Path

import httpx
import pytest

from quotepilot import native_jobs as jobs
from quotepilot.native_workflow import MOIWorkflowClient
from test_commercial import clients
from test_genesis_workflow import confirm_body


class ContractService:
    workspace = 'contract-workspace'
    wid = 'contract-workflow'
    eid = 'contract-execution'
    status = 'completed'
    writes = 0
    launches = 0
    timeout = False
    sql_failure = False
    read_failure = False
    evidence = 'Please quote 3 EA of PN-0001.'
    other_ref = False

    def execute(self, query):
        if query.startswith('INSERT IGNORE'):
            if self.sql_failure:
                raise ValueError('contract staging failure')
            self.ref, self.digest, self.encoded = re.search(
                r"VALUES \('(QN-[a-f0-9]+)','([a-f0-9]+)','([A-Za-z0-9+/=]+)'", query).groups()
            self.writes += 1
            return {}
        if 'input_base64' in query:
            values = [self.digest,self.encoded]
        else:
            if self.read_failure:
                raise ValueError('contract read failure')
            values = [self.digest, self.output64(), 'pending']
        return {'data':{'result':[[{'Valid':True,'String':v} for v in values]]}, 'query_id':'contract-query'}

    def output(self):
        return json.dumps({'lines':[{'part_number':'PN-0001','quantity':3,'unit':'EA','evidence':self.evidence}]})

    def output64(self):
        return base64.b64encode(self.output().encode()).decode()

    def answer(self, request):
        path = request.url.path
        if path.endswith(self.wid):
            data = {'workflow':{'id':self.wid,'status':'ready','execution_mode':'one_shot',
                'dsl_yaml':Path('integration/rfq_native.yaml').read_text(), 'available_actions':['run'],
                'runtime_fields':{'fields':[{'field_id':'run_ref','required':True},
                    {'field_id':'vars_run_ref','bind_to':'vars.run_ref','required':True}]}}}
        elif request.method == 'POST':
            self.launches += 1
            assert json.loads(request.content)['values'] == {'run_ref':self.ref,'vars_run_ref':self.ref}
            if self.timeout:
                raise httpx.ReadTimeout('contract')
            data = {'workflow_run':{'execution_id':self.eid,'workflow_id':self.wid,'status':'queued'}}
        elif '/nodes/' in path:
            key = path.rsplit('.',1)[1]
            outputs = {'load_rfq':{'rows':[{'rfq_text':base64.b64decode(self.encoded).decode()}]},
                       'extract_rfq':{'text':self.output(),'model':'contract-model'},
                       'persist_suggestions':{'affected_rows':1},
                       'read_back':{'rows':[{'run_ref':self.ref,'input_sha256':self.digest,
                            'model_text_base64':self.output64(),'review_status':'pending'}]}}
            data = {'node':{'node_key':'root.'+key},'run':{'status':self.status.upper(),'runtime_output':outputs[key]}}
        else:
            run = {'execution_id':self.eid,'workflow_id':self.wid,'status':self.status,
                   'vars_payload':{'run_ref':'wrong' if self.other_ref else self.ref}}
            data = {'result' if path.endswith('/result') else 'execution':run}
        return httpx.Response(200,json={'code':'OK','data':data})


@pytest.fixture
def inbox(clients,monkeypatch):
    admin, reviewer, _ = clients
    platform = ContractService()
    monkeypatch.setenv('MOI_WORKSPACE_ID',platform.workspace)
    monkeypatch.setenv('MOI_API_KEY','offline-fixture')
    monkeypatch.setenv('MOI_WORKFLOW_ID',platform.wid)
    client = MOIWorkflowClient(httpx.MockTransport(platform.answer))
    monkeypatch.setattr(jobs,'clients',lambda:(client,platform,platform.wid))
    msg=EmailMessage()
    msg['From']='qa@example.invalid'
    msg['Subject']='Synthetic native contract'
    msg['Message-ID']='<native@qa.invalid>'
    msg.set_content(platform.evidence)
    assert admin.post('/api/emails/import',files={'file':('synthetic.eml',msg.as_bytes(),'message/rfc822')}).is_success
    return admin,reviewer,platform


URL='/api/native-workflow/emails/%3Cnative%40qa.invalid%3E/runs'


def start(admin):
    response=admin.post(URL,json={'synthetic_confirmed':True})
    assert response.is_success,response.text
    return response.json()


def refresh(admin,job):
    response=admin.post('/api/native-workflow/runs/'+job['ref']+'/refresh')
    assert response.is_success,response.text
    return response.json()


def test_inbox_to_verified_review_retry_and_confirmation(inbox):
    admin,reviewer,platform=inbox
    assert reviewer.post(URL,json={'synthetic_confirmed':True}).status_code==403
    assert admin.post(URL,json={'synthetic_confirmed':False}).status_code==422
    job=start(admin)
    assert start(admin)['execution_id']==platform.eid
    assert job['ref']==admin.get(URL).json()['rows'][0]['ref']
    platform.read_failure=True
    assert refresh(admin,job)['phase']=='verification_pending'
    platform.read_failure=False
    done=refresh(admin,job)
    assert done['phase']=='review_ready' and done['receipt']['readback_matched']
    assert refresh(admin,job)['review_id']==done['review_id']
    assert platform.launches==1 and len(done['receipt']['nodes'])==4
    review=admin.get('/api/extractions/'+done['review_id']).json()
    assert review['status']=='pending' and review['provider']=='moi_native'
    assert review['input_sha256']==hashlib.sha256(review['input_text'].encode()).hexdigest()
    b=confirm_body(review)
    confirmed=admin.post('/api/extractions/'+done['review_id']+'/confirm',json=b).json()
    assert confirmed['new_lines']==1
    q=admin.post('/api/quote',json={'line_ids':confirmed['line_ids'],'asof':'2026-09-20'}).json()
    assert q['total_cny']=='49.89'


def test_start_write_failure_retries_same_reference(inbox):
    admin,_,p=inbox
    p.sql_failure=True
    job=start(admin)
    assert job['phase']=='preflight_failed' and not p.launches
    p.sql_failure=False
    recovered=start(admin)
    assert recovered['ref']==job['ref'] and recovered['execution_id']==p.eid


def test_timeout_requires_matching_platform_execution(inbox):
    admin,_,p=inbox
    p.timeout=True
    job=start(admin)
    assert job['phase']=='dispatch_unknown' and not job['execution_id']
    assert start(admin)['ref']==job['ref'] and p.launches==1
    path='/api/native-workflow/runs/'+job['ref']+'/reconcile'
    p.other_ref=True
    assert admin.post(path,json={'execution_id':p.eid}).status_code==409
    p.other_ref=False
    assert admin.post(path,json={'execution_id':p.eid}).json()['execution_id']==p.eid
    assert refresh(admin,job)['phase']=='review_ready' and p.launches==1


@pytest.mark.parametrize('failure',['bad_evidence','failed','running'])
def test_unverified_result_does_not_enter_business_data(inbox,failure):
    admin,_,p=inbox
    job=start(admin)
    if failure=='bad_evidence':
        p.evidence='field invented by test model'
    else:
        p.status=failure
    state=refresh(admin,job)
    assert state['phase']=={'bad_evidence':'verification_pending','failed':'failed','running':'tracking'}[failure]
    assert not state['review_id']
    assert admin.get('/api/emails/%3Cnative%40qa.invalid%3E/extractions').json()['rows']==[]


def test_concurrent_dispatch_uses_one_platform_submission(inbox):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    admin,_,platform=inbox
    gate=Barrier(2)
    original=platform.execute
    def stage_together(query):
        if query.startswith('INSERT IGNORE'):
            gate.wait(timeout=10)
        return original(query)
    platform.execute=stage_together
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:start(admin),range(2)))
    assert results[0]['ref']==results[1]['ref']
    assert platform.launches==1 and start(admin)['execution_id']==platform.eid


def test_native_contract_through_approved_pdf_and_excel(inbox):
    from io import BytesIO
    import fitz
    from openpyxl import load_workbook
    from test_commercial import setup_inputs
    admin,reviewer,platform=inbox
    _,_,quote_request=setup_inputs(admin,reviewer,0)
    job=refresh(admin,start(admin))
    confirm=confirm_body({})
    confirm['lines'][0]['description']='Synthetic valve spec A'
    confirmed=admin.post('/api/extractions/'+job['review_id']+'/confirm',json=confirm)
    assert confirmed.is_success
    lid=confirmed.json()['line_ids'][0]
    evidence=reviewer.get(f'/api/lines/{lid}/field-evidence').json()
    reviewed=reviewer.post(f'/api/lines/{lid}/review-fields',json={
        'version':evidence['review']['version'],'changes':{},'actor':'QA reviewer',
        'reason':'核对合成测试文件','confirm_source':True})
    assert reviewed.is_success,reviewed.text
    quote_request.update(line_ids=[lid],line_costs={str(lid):{'processing_per_unit_cny':'1','other_total_cny':'2'}})
    draft=reviewer.post('/api/commercial-quotes',json=quote_request)
    assert draft.is_success,draft.text
    quote=draft.json()
    path='/api/commercial-quotes/'+quote['id']
    body={'version':1,'actor':'QA reviewer','reason':'核对合成报价','confirm_risks':True}
    assert reviewer.post(path+'/review',json=body).is_success
    assert admin.post(path+'/approve',json={**body,'actor':'QA approver','version':2}).is_success
    amount=quote['suggested_total_cny']
    assert amount=='43.74'
    with fitz.open(stream=admin.get(path+'/export/pdf').content,filetype='pdf') as pdf:
        assert amount in ''.join(p.get_text() for p in pdf)
    xlsx=load_workbook(BytesIO(admin.get(path+'/export/xlsx').content))
    assert any(c.value==amount for row in xlsx.active for c in row)
    xlsx.close()
    assert admin.get('/api/audit/verify').json()['valid'] and platform.launches==1
