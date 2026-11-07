import json
from pathlib import Path
import httpx
import pytest
from fastapi.testclient import TestClient
from quotepilot.providers import GenesisProvider
from quotepilot.query_planner import Plan,compile_plan,execute_plan


@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import server
    original=server.DB;server.DB=tmp_path_factory.mktemp('nlquery')/'test.db'
    try:
        with TestClient(server.app) as c:yield c
    finally:server.DB=original


def provider(monkeypatch,plan):
    monkeypatch.setenv('QUOTEPILOT_PROVIDER','genesis')
    monkeypatch.setenv('GENESIS_ACCESS_TOKEN','TEST_ONLY_NOT_A_KEY')
    monkeypatch.setenv('GENESIS_MODEL_ID','test-planner')
    monkeypatch.setenv('GENESIS_API_STYLE','responses')
    def handle(request):
        body=json.loads(request.content)
        assert '只输出符合schema的JSON' in body['instructions']
        assert 'TEST_ONLY_NOT_A_KEY' not in body['instructions']
        return httpx.Response(200,json={'id':'TEST-PLANNER-RESPONSE','status':'completed','usage':{'total_tokens':10},
            'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps(plan,ensure_ascii=False)}]}]})
    p=GenesisProvider(transport=httpx.MockTransport(handle))
    monkeypatch.setattr('quotepilot.providers.get_provider',lambda:p)


def test_true_model_plan_queries_real_filtered_data(client,monkeypatch):
    provider(monkeypatch,{'supported':True,'explanation':'统计2025年各客户的紧急询价前五名','dataset':'historical',
        'group_by':['customer'],'metrics':['rfq_count','record_count'],'filters':[{'field':'urgency','op':'in','value':['AOG','URGENT','USR','WSP']}],
        'date_from':'2025-01-01','date_to':'2025-12-31','order_by':'rfq_count','limit':5})
    r=client.post('/api/analytics/ask',json={'question':'2025年各客户的紧急询价前五名','asof':'2026-09-01'})
    assert r.status_code==200;r=r.json()
    assert r['supported'] and r['model_connected'] and r['response_id']=='TEST-PLANNER-RESPONSE'
    import server
    with server.database() as con:
        expected=[dict(x) for x in con.execute("SELECT COALESCE(NULLIF(airline,''),'未提供') AS 客户, COUNT(DISTINCT rfq_no) AS 询价份数,COUNT(*) AS 明细行数 FROM historical WHERE urgency IN ('AOG','URGENT','USR','WSP') AND substr(inquiry_date,1,10)>='2025-01-01' AND substr(inquiry_date,1,10)<='2025-12-31' GROUP BY 1 ORDER BY 2 DESC,1 ASC LIMIT 5")]
    assert r['rows']==expected and r['rows']
    assert r['sql_parameters'][-1]==5 and '2025-01-01' not in r['sql']


def test_flights_are_not_mapped_to_airline_rfq(client,monkeypatch):
    provider(monkeypatch,{'supported':False,'explanation':'当前只有零件询价与供应商数据，无法查询上海至洛杉矶的机票或实时航班。'})
    r=client.post('/api/analytics/ask',json={'question':'上海飞洛杉矶机票查询'}).json()
    assert not r['supported'] and '机票' in r['message'] and 'rows' not in r


@pytest.mark.parametrize('changes',[
    {'group_by':['part; DROP TABLE historical;--']},
    {'metrics':['price_avg']},
    {'order_by':'random()'},
    {'filters':[{'field':'password','value':'x'}]},
    {'date_from':'2026-01-01','date_to':'2025-01-01'},
])
def test_untrusted_plan_cannot_introduce_sql(changes):
    p=Plan.model_validate({'supported':True,'explanation':'test',**changes})
    with pytest.raises(ValueError):compile_plan(p)


def test_filter_value_remains_bound(client):
    p=Plan(supported=True,explanation='test',filters=[{'field':'customer','op':'contains','value':"%' OR 1=1 --"}])
    sql,args,_=compile_plan(p)
    assert "OR 1=1" not in sql and args[0]=="%\\%' OR 1=1 --%"
    import server
    with server.database() as con:
        assert execute_plan(con,p)['rows'][0]['明细行数']==0
        assert con.execute('SELECT COUNT(*) FROM historical').fetchone()[0]==249


def test_sum_never_combines_units(client):
    p=Plan(supported=True,explanation='test',group_by=['scope'],metrics=['quantity_sum'],order_by='quantity_sum')
    import server
    with server.database() as con:r=execute_plan(con,p)
    assert r['group_labels']==['产品范围','单位'] and all('单位' in row for row in r['rows'])


def test_average_never_combines_currencies(client):
    p=Plan(supported=True,explanation='test',dataset='prices',group_by=['part'],metrics=['price_avg'],order_by='price_avg')
    import server
    with server.database() as con:r=execute_plan(con,p)
    assert r['group_labels']==['件号','币种'] and all('币种' in row for row in r['rows'])


def test_model_error_is_not_presented_as_query_success(client,monkeypatch):
    monkeypatch.setenv('QUOTEPILOT_PROVIDER','genesis')
    class Broken:
        def complete_json(self,*args):raise RuntimeError('TEST_NETWORK_FAILURE')
    monkeypatch.setattr('quotepilot.providers.get_provider',lambda:Broken())
    r=client.post('/api/analytics/ask',json={'question':'2025年询价数量'})
    assert r.status_code==502 and 'rows' not in r.json() and 'TEST_NETWORK_FAILURE' not in r.text


def test_invalid_model_field_is_rejected_before_sql(client,monkeypatch):
    provider(monkeypatch,{'supported':True,'explanation':'test','group_by':['auth.users'],'metrics':['record_count']})
    assert client.post('/api/analytics/ask',json={'question':'客户询价统计'}).status_code==422
