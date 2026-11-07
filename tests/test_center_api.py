import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from tests.test_query_center import ModelContract

@pytest.fixture
def client(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(server,'DB',tmp_path/'center_api.db')
    monkeypatch.setenv('QUOTEPILOT_PROVIDER','genesis')
    model=ModelContract({'action':'query','title':'客户查询','explanation':'历史询价按客户统计','sql':'SELECT airline,COUNT(*) AS n FROM historical GROUP BY airline','parameters':[],'chart':'ranking'})
    monkeypatch.setattr('quotepilot.providers.get_provider',lambda:model)
    with TestClient(server.app) as c:yield c


def test_api_query_and_logs_preserve_sql_and_metadata(client):
    r=client.post('/api/query-center/ask',json={'question':'哪些客户询价最多','asof':'2026-09-01'})
    assert r.status_code==200;r=r.json();assert r['status']=='completed' and r['readonly']
    log=client.get('/api/query-center/sessions/'+r['session_id']).json()['turns'][0]
    assert log['sql']==r['sql'] and log['query_id']==r['query_id']
    assert client.get('/api/query-center/schema').json()['tables']


def test_original_four_shortcuts_remain_available(client):
    for q in ['每月询价趋势','客户紧急询价排名','热门询价件号','即将截止的询价']:
        r=client.post('/api/query-center/quick',json={'question':q,'asof':'2026-09-01'}).json()
        assert r['status']=='completed' and r['readonly'] and r['analysis']['status']=='not_requested'


def test_external_unconfigured_is_explicitly_blocked(client,monkeypatch):
    monkeypatch.delenv('TAVILY_API_KEY',raising=False)
    r=client.post('/api/query-center/external',json={'question':'LM358 datasheet'}).json()
    assert r['status']=='blocked' and r['sources']==[] and not r['live_search']


def test_joint_keeps_internal_result_when_external_is_blocked(client,monkeypatch):
    monkeypatch.delenv('TAVILY_API_KEY',raising=False)
    r=client.post('/api/query-center/joint',json={'question':'供应商参考价格分布','public_query':'LM358 public reference price'}).json()
    assert r['status']=='partial' and r['rows'] and not r['live_search'] and r['comparisons']==[]


def test_session_is_bound_to_current_admin_session(client):
    r=client.post('/api/query-center/quick',json={'question':'每月询价趋势'}).json()
    client.cookies.set('qp_session','TEST_OTHER_SESSION')
    assert client.get('/api/query-center/sessions/'+r['session_id']).status_code==403


def test_admin_boundary_and_csrf_still_apply(client,monkeypatch):
    monkeypatch.setenv('QUOTEPILOT_ENV','production')
    for path in ['/api/query-center/status','/api/query-center/schema','/api/query-center/sessions/'+'a'*32]:
        assert client.get(path).status_code==401
    assert client.post('/api/query-center/ask',json={'question':'客户统计'}).status_code==403
