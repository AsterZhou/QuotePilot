"""Mock protocol contracts; live API evidence is in evidence/sprint-p0, never these IDs."""
import base64,hashlib,json
import httpx,pytest
from quotepilot.platform_quotes import mirror_commercial_quote
from quotepilot.native_workflow import MOIWorkflowClient
from scripts.sprint_probe import redact

class ContractSQL:
    def __init__(self,q,bad=False):self.q=q;self.calls=[];self.bad=bad
    def execute(self,query):
        self.calls.append(query);raw=json.dumps(self.q,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        digest=hashlib.sha256(raw).hexdigest();payload=base64.b64encode(raw).decode()
        return {'query_id':'CONTRACT-'+str(len(self.calls)),'data':{'result':[[{'Valid':True,'String':digest},{'Valid':True,'String':'wrong' if self.bad else payload}]]}}

def approved():return {'id':'CQ-ABCDEF1234567890','version':3,'status':'approved','reviewer_account':'reviewer','approver_account':'admin','remarks':"SYNTHETIC ' \\ quote"}

def test_commercial_mirror_reads_back_exact_approved_bytes():
    q=approved();sql=ContractSQL(q);r=mirror_commercial_quote(sql,q)
    assert r['verified'] and not r['native_workflow_execution'] and len(sql.calls)==4
    assert r['table']=='quotepilot_sprint.commercial_quote_snapshots_v1'
    assert q['remarks'] not in sql.calls[2] and 'INSERT IGNORE' in sql.calls[2]

@pytest.mark.parametrize('patch',[{'status':'draft'},{'reviewer_account':'admin'},{'id':"CQ-';DROP"},{'version':True}])
def test_mirror_rejects_unapproved_self_approved_or_invalid_id(patch):
    q={**approved(),**patch};sql=ContractSQL(q)
    with pytest.raises(ValueError):mirror_commercial_quote(sql,q)
    assert not sql.calls

def test_mirror_conflict_is_not_claimed_success():
    q=approved()
    with pytest.raises(ValueError,match='校验失败'):mirror_commercial_quote(ContractSQL(q,True),q)

def test_native_execution_id_must_match_response(monkeypatch):
    monkeypatch.setenv('MOI_API_KEY','TEST_ONLY');monkeypatch.setenv('MOI_WORKSPACE_ID','TEST_WORKSPACE')
    c=MOIWorkflowClient(httpx.MockTransport(lambda r:httpx.Response(200,json={'code':'OK','data':{'execution':{'execution_id':'CONTRACT-execution','workflow_id':'CONTRACT-workflow','status':'running'}}})))
    assert c.execution('CONTRACT-workflow','CONTRACT-execution')['status']=='running'
    with pytest.raises(ValueError,match='不匹配'):c.execution('CONTRACT-workflow','OTHER')
    with pytest.raises(ValueError):c.result('CONTRACT-workflow','../bad')

def test_redactor_keeps_usage_but_removes_credentials():
    r=redact({'api_key':'TEST_SECRET','usage':{'input_tokens':12,'total_tokens':20},'text':'TEST_SECRET','Authorization':'Bearer TEST_SECRET'},'TEST_SECRET')
    assert r['usage']['total_tokens']==20 and 'TEST_SECRET' not in json.dumps(r)
