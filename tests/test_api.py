"""End-to-end API tests with official synthetic challenge data."""
from pathlib import Path
import zipfile
import pytest
from fastapi.testclient import TestClient
from server import app, SAMPLES

@pytest.fixture(scope='module')
def client(tmp_path_factory):
    import server
    original=server.DB;server.DB=tmp_path_factory.mktemp('official')/'test.db'
    try:
        with TestClient(app) as c:yield c
    finally:server.DB=original


def test_health_and_offline_truth(client):
    r=client.get('/api/health')
    assert r.status_code==200
    d=r.json()
    assert d['ok'] and not d['moi_connected']
    assert d['stats']=={'mails':6,'mail_lines':300,'history_lines':249,'history_rfq_groups':94,'cost_records':163,'price_records':342}


def test_frontend_assets(client):
    assert client.get('/').status_code==200
    h=client.get('/').text
    assert '报价室' in h and 'QUOTE' in h
    assert client.get('/assets/style.css').status_code==200
    assert client.get('/assets/app.js').status_code==200


def test_inbox_and_source_details(client):
    res=client.get('/api/emails').json()
    assert len(res)==6
    assert sorted([x['line_count'] for x in res])==[7,7,21,21,122,122]
    line=client.get('/api/lines',params={'email_id':res[0]['email_id']}).json()
    assert line['total']==res[0]['line_count']
    one=client.get(f"/api/lines/{line['rows'][0]['id']}").json()
    assert one['source_ref'] and one['email_subject']


def test_invalid_line(client):
    assert client.get('/api/lines/999999').status_code==404


def test_search_filters(client):
    res=client.get('/api/lines',params={'search':'PN-0001','limit':500}).json()
    assert res['total']>1
    assert all('PN-0001' in x['part_number'] or 'PN-0001' in x['description'] or 'PN-0001' in (x['source_rfq_no'] or '') for x in res['rows'])


def test_distinct_inquiry_ids_preserved(client):
    allrows=client.get('/api/lines',params={'limit':500}).json()['rows']
    pn=[x for x in allrows if x['part_number']=='PN-0001' and x['quantity']==8 and x['unit']=='EA']
    assert len(pn)>=2
    assert len(set(x['source_rfq_no'] for x in pn))>=2


def _sample_ids(client):
    rows=client.get('/api/lines',params={'limit':500}).json()['rows']
    good=next(x['id'] for x in rows if x['part_number']=='PN-0001' and x['quantity']==8 and x['unit']=='EA' and x['part_condition']=='FN')
    missing=next(x['id'] for x in rows if x['part_number']=='GSK-001')
    return good,missing


def test_real_price_and_no_price(client):
    good,missing=_sample_ids(client)
    r=client.post('/api/quote',json={'line_ids':[good,missing], 'asof':'2026-09-20','method':'markup','rate':20})
    assert r.status_code==200,r.text
    d=r.json()
    assert d['quoted_count']==1 and d['pending_count']==1
    assert d['lines'][0]['part_number']=='PN-0001'
    assert d['lines'][0]['unit_quote_cny']=='16.63'
    assert d['lines'][0]['line_total_cny']=='133.04'
    assert d['lines'][1]['status']=='待核价'
    assert d['lines'][1]['unit_quote_cny']==''
    assert d['lines'][0]['source_ref'] and d['lines'][0]['price_ref']
    assert d['review_required']


def test_margin_vs_markup(client):
    good,_=_sample_ids(client)
    m=client.post('/api/quote',json={'line_ids':[good],'asof':'2026-09-20','method':'margin','rate':20}).json()
    x=client.post('/api/quote',json={'line_ids':[good],'asof':'2026-09-20','method':'markup','rate':20}).json()
    assert float(m['lines'][0]['unit_quote_cny'])>float(x['lines'][0]['unit_quote_cny'])


def test_late_price_not_automatically_accepted(client):
    good,_=_sample_ids(client)
    r=client.post('/api/quote',json={'line_ids':[good],'asof':'2020-01-01','method':'markup','rate':20}).json()
    assert r['pending_count']==1


def test_candidates_show_rejection_reasons(client):
    r=client.get('/api/price/candidates',params={'part_number':'PN-0001','quantity':8,'condition':'FN','asof':'2026-09-20'}).json()
    assert r['count']>0
    assert any(x['status']=='有效候选' for x in r['candidates'])
    assert any('有效期' in ';'.join(x['issues']) or '件状' in ';'.join(x['issues']) or '起订' in ';'.join(x['issues']) for x in r['candidates'] if x['issues'])


def test_exports(client):
    good,missing=_sample_ids(client)
    body={'line_ids':[good,missing], 'asof':'2026-09-20','rate':20,'method':'markup'}
    for kind in ('docx','csv','json'):
        r=client.post('/api/quote/export/'+kind,json=body)
        assert r.status_code==200
        assert len(r.content)>100
        assert 'attachment' in r.headers['content-disposition']
        if kind=='docx':
            assert zipfile.is_zipfile(__import__('io').BytesIO(r.content))
        if kind=='csv':assert 'PN-0001' in r.content.decode('utf-8-sig')
        if kind=='json': assert r.json()['quoted_count']==1


def test_query_templates_and_interpreter(client):
    for q in ('每月询价趋势','客户紧急询价排名','热门询价件号','即将截止的询价'):
        r=client.get('/api/analytics',params={'q':q})
        assert r.status_code==200
        assert not r.json()['model_connected']
        assert r.json()['sql'].startswith('SELECT')
    good=client.post('/api/analytics/ask',json={'question':'哪些航空公司的紧急询价最多？'}).json()
    assert good['supported'] and good['interpreted_as']=='客户紧急询价排名'
    unknown=client.post('/api/analytics/ask',json={'question':'计算一个从未实现的复杂成本分配模型'}).json()
    assert not unknown['supported']


def test_preview_and_deduplicated_import(client):
    f=next(SAMPLES.rglob('*.eml'))
    data=f.read_bytes()
    r=client.post('/api/emails/preview', files={'file':(f.name,data,'message/rfc822')})
    assert r.status_code==200
    assert r.json()['count']>0
    r=client.post('/api/emails/import',files={'file':(f.name,data,'message/rfc822')})
    assert r.status_code==200
    assert r.json()['new_lines']==0
    assert r.json()['duplicate_lines']==r.json()['parsed_count']


def test_reject_invalid_eml(client):
    r=client.post('/api/emails/preview',files={'file':('evil.exe',b'hello','application/octet-stream')})
    assert r.status_code==415


def test_validation(client):
    assert client.post('/api/quote',json={'line_ids':[]}).status_code==422
    assert client.post('/api/quote',json={'line_ids':[999999]}).status_code==404
    assert client.post('/api/quote',json={'line_ids':[1],'rate':120}).status_code==422
    assert client.get('/api/analytics',params={'q':'DROP TABLE historical'}).status_code==400


def test_integration_transparent(client):
    r=client.get('/api/integration').json()
    assert not r['moi_connected'] and not r['model_connected']
