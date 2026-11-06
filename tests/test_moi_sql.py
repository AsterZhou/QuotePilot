"""Mock SQL contracts; separate live cloud evidence is not counted as a unit test."""
import base64,hashlib,json
import httpx,pytest
from quotepilot.moi_sql import MOISQLClient,mirror_quote

class FakeSQL:
    workspace='TEST_ONLY'
    def __init__(self,quote,bad=False):self.sql=[];self.quote=quote;self.bad=bad
    def execute(self,sql):
        self.sql.append(sql)
        raw=json.dumps(self.quote,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
        result=[[{'String':hashlib.sha256(raw).hexdigest(),'Valid':True},{'String':base64.b64encode(raw).decode() if not self.bad else 'bad','Valid':True}]]
        return {'query_id':'CONTRACT-'+str(len(self.sql)),'data':{'result':result}}

def test_only_approved():
    with pytest.raises(ValueError,match='人工确认'):mirror_quote(FakeSQL({}),{'review_status':'draft'})

def test_mirror_and_hash():
    q={'quote_id':'QP-ABCDEF123456','version':2,'review_status':'approved','description':"中文 ' \\ \n quote"}
    c=FakeSQL(q);r=mirror_quote(c,q)
    assert r['verified'] and len(c.sql)==4 and 'INSERT IGNORE' in c.sql[2]
    assert q['description'] not in c.sql[2]

def test_readback_mismatch_rejected():
    q={'quote_id':'QP-ABCDEF123456','version':2,'review_status':'approved'}
    with pytest.raises(ValueError,match='校验失败'):mirror_quote(FakeSQL(q,True),q)

def test_sql_identifier_injection_rejected():
    with pytest.raises(ValueError,match='编号'):mirror_quote(FakeSQL({}),{'quote_id':"QP-';DROP",'version':1,'review_status':'approved'})

def test_async_sql_contract(monkeypatch):
    monkeypatch.setenv('MOI_API_KEY','TEST_SECRET');monkeypatch.setenv('MOI_WORKSPACE_ID','TEST_WORKSPACE')
    paths=[]
    def handle(req):
        assert req.headers['X-API-Key']=='TEST_SECRET' and req.headers['X-Workspace-ID']=='TEST_WORKSPACE'
        assert 'cookie' not in req.headers
        paths.append(req.url.path)
        if req.url.path.endswith('execute'):return httpx.Response(200,json={'code':200,'data':{'query_id':'test-query'}},headers={'Set-Cookie':'blocked-auth=test'})
        if req.url.path.endswith('describe'):return httpx.Response(200,json={'code':200,'data':{'status':'success','statement_id':'test-statement'}})
        return httpx.Response(200,json={'code':200,'data':{'result':[[{'String':'1','Valid':True}]]}})
    result=MOISQLClient(httpx.MockTransport(handle)).execute('SELECT 1')
    assert result['data']['result'][0][0]['String']=='1' and len(paths)==3

def test_http_200_business_error_rejected(monkeypatch):
    monkeypatch.setenv('MOI_API_KEY','TEST_SECRET');monkeypatch.setenv('MOI_WORKSPACE_ID','TEST_WORKSPACE')
    c=MOISQLClient(httpx.MockTransport(lambda r:httpx.Response(200,json={'code':'Denied'})))
    with pytest.raises(ValueError,match='未成功'):c.execute('SELECT 1')
