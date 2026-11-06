"""Synthetic adversarial cases, independent of official-sample assertions."""
from decimal import Decimal
from email.message import EmailMessage
from io import BytesIO
import hashlib,json,csv
import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook,load_workbook
from quotepilot.store import open_db,ingest_eml
from quotepilot.pricing import quote_line,calc_unit
from quotepilot.parsing import parse_eml
from quotepilot.providers import GenesisProvider,MockProvider
import httpx

@pytest.fixture
def db(tmp_path):
    c=open_db(tmp_path/'rules.db');yield c;c.close()

def cost(c,**changes):
    row=dict(part_number='X-1',unit='EA',inventory=5,part_condition='FN',standard_cost='100',currency='CNY',updated_at='2026-09-01',source_row='2',warehouse='TEST')|changes
    c.execute('INSERT INTO costs('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()));c.commit()

def price(c,**changes):
    row=dict(resource_id='P1',part_number='X-1',supplier='TEST ONLY',condition='FN',unit_price='10',currency='USD',fx_to_cny='7.1',moq=1,lead_days=3,quote_date='2026-09-01',valid_until='2026-10-01',status='有效',source_row='2')|changes
    c.execute('INSERT INTO prices('+','.join(row)+') VALUES('+','.join('?' for _ in row)+')',tuple(row.values()));c.commit()

def q(c,qty=2,**kwargs):return quote_line(c,'X-1',qty,condition='FN',**kwargs)

def test_exact_markup_and_margin():
    assert calc_unit(Decimal(100),Decimal('.2'))==Decimal(120)
    assert calc_unit(Decimal(100),Decimal('.2'),'margin')==Decimal(125)
    assert calc_unit(Decimal(100),Decimal('1.5'))==Decimal(250)

@pytest.mark.parametrize('bad',['NaN','Infinity','-Infinity','abc',None])
def test_bad_cost_never_prices(db,bad):
    cost(db,standard_cost=bad);assert q(db)['unit_quote_cny']==''

def test_missing_cost(db):
    assert q(db)['status']=='待核价'

def test_expired(db):
    price(db,valid_until='2026-09-19');r=q(db)
    assert not r['unit_quote_cny'] and any('过期' in x for x in r['issues'])

def test_future(db):
    price(db,quote_date='2026-09-21');assert not q(db)['unit_quote_cny']

@pytest.mark.parametrize('field,value',[('fx_to_cny',''),('fx_to_cny','0'),('fx_to_cny','NaN'),('valid_until',''),('valid_until','bad'),('moq',0),('status','失效'),('currency','')])
def test_incomplete_supplier_blocked(db,field,value):
    price(db,**{field:value});assert q(db)['status']=='待核价'

def test_fx_evidence(db):
    price(db);r=q(db)
    assert r['cost_cny']=='71.00' and r['unit_quote_cny']=='85.20' and r['line_total_cny']=='170.40'
    assert r['price_basis']['fx']=='7.1' and 'P1' in r['price_basis']['fx_source']
    assert r['decision_state']=='待人工确认'

def test_stock_shortage(db):
    cost(db);r=q(db,8)
    assert not r['unit_quote_cny'] and any('差额 3 EA' in x for x in r['issues'])

def test_uom_mismatch(db):
    cost(db,unit='FT');assert not q(db)['unit_quote_cny']

def test_condition_mismatch(db):
    cost(db,part_condition='NE');assert not q(db)['unit_quote_cny']

def test_moq(db):
    price(db,moq=3);r=q(db);assert not r['unit_quote_cny'] and any('起订量' in x for x in r['issues'])

@pytest.mark.parametrize('qty',[0,-2,1.5,'oops','NaN'])
def test_invalid_quantity(db,qty):
    cost(db);assert not q(db,qty)['unit_quote_cny']

def make_mail(mid='synthetic-1',qty='2'):
    m=EmailMessage();m['From']='test@example.invalid';m['Subject']='SYNTHETIC RFQ';m['Message-ID']=f'<{mid}>'
    m.set_content('Synthetic test, not customer data')
    m.add_alternative('<table><tr><th>询价单号</th><th>Part Number</th><th>Quantity</th><th>Unit</th></tr>'+''.join(f'<tr><td>{rfq}</td><td>X-1</td><td>{qty}</td><td>EA</td></tr>' for rfq in ['RFQ-A','RFQ-B'])+'</table>',subtype='html')
    return m.as_bytes()

def test_dedup_and_distinct_rfq(db):
    raw=make_mail();ingest_eml(db,raw,'s.eml');ingest_eml(db,raw,'renamed.eml')
    assert db.execute('SELECT COUNT(*) FROM emails').fetchone()[0]==1
    assert db.execute('SELECT COUNT(*) FROM rfq_lines').fetchone()[0]==2
    assert db.execute('SELECT COUNT(*) FROM rfq_headers').fetchone()[0]==2

def test_message_id_collision_rejected(db):
    ingest_eml(db,make_mail(),'s.eml')
    with pytest.raises(ValueError,match='冲突'):ingest_eml(db,make_mail(qty='3'),'changed.eml')
    assert db.execute('SELECT SUM(quantity) FROM rfq_lines').fetchone()[0]==4

def test_source_bytes_retained(db):
    raw=make_mail();ingest_eml(db,raw,'s.eml')
    r=db.execute("SELECT * FROM source_files WHERE kind='eml'").fetchone()
    assert bytes(r['content'])==raw and r['sha256']==hashlib.sha256(raw).hexdigest()
    assert db.execute('SELECT raw_json FROM line_evidence').fetchone()[0].find('RFQ-A')>=0

def test_bad_row_preserved(db):
    ingest_eml(db,make_mail(qty='two'),'s.eml')
    assert db.execute('SELECT COUNT(*) FROM rfq_lines').fetchone()[0]==0
    assert db.execute('SELECT raw_json FROM parse_issues WHERE raw_json LIKE ?',('%two%',)).fetchone()
    assert db.execute("SELECT COUNT(*) FROM source_files WHERE kind='eml'").fetchone()[0]==1

def test_invalid_eml():
    with pytest.raises(ValueError):parse_eml(b'not a mail','bad.eml')

@pytest.fixture
def client(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(server,'DB',tmp_path/'api.db')
    with TestClient(server.app) as c:yield c

def good_request(c):
    rows=c.get('/api/lines',params={'search':'PN-0001'}).json()['rows']
    good=next(x for x in rows if x['quantity']==8 and x['part_condition']=='FN' and x['unit']=='EA')
    return {'line_ids':[good['id']],'asof':'2026-09-20','method':'markup','rate':20}

def test_saved_review_exports(client):
    req=good_request(client);r=client.post('/api/quote',json=req).json();qid=r['quote_id']
    assert client.get('/api/quotes/'+qid).json()==r
    assert client.get(f'/api/quotes/{qid}/export/csv?final=true').status_code==409
    body={'version':1,'actor':'SYNTHETIC REVIEWER','reason':'核对来源文件与业务条件','approve':True,'confirm_constraints':True}
    approved=client.patch('/api/quotes/'+qid,json=body).json()
    assert approved['review_status']=='approved' and approved['version']==2
    # Underlying prices change, snapshot remains identical.
    import server
    con=open_db(server.DB);con.execute("UPDATE prices SET unit_price='999' WHERE part_number='PN-0001'");con.commit();con.close()
    rows=list(csv.DictReader(BytesIO(client.get(f'/api/quotes/{qid}/export/csv?final=true').content).read().decode('utf-8-sig').splitlines()))
    assert rows[0]['amount_cny']==approved['lines'][0]['line_total_cny']
    xlsx=client.get(f'/api/quotes/{qid}/export/xlsx').content
    w=load_workbook(BytesIO(xlsx),data_only=True)
    assert w.active['F4'].value==approved['lines'][0]['line_total_cny']
    assert client.patch('/api/quotes/'+qid,json={**body,'version':2}).status_code==409
    assert any(x['action']=='quote_approved' for x in client.get('/api/audit').json())

def test_manual_edit_requires_evidence_and_version(client):
    r=client.post('/api/quote',json=good_request(client)).json();url='/api/quotes/'+r['quote_id'];line=r['lines'][0]['line_id']
    body={'version':1,'actor':'Tester','reason':'合成供应商补充报价','patches':[{'line_id':line,'unit_price_cny':'20.10'}]}
    assert client.patch(url,json=body).status_code==409
    body['patches'][0]['evidence_ref']='SYNTHETIC-PRICE-001'
    changed=client.patch(url,json=body).json()
    assert changed['total_cny']=='160.80' and changed['lines'][0]['original_calculation']
    assert client.patch(url,json=body).status_code==409

def test_metrics_no_invented_amount(client):
    m=client.get('/api/analytics/metrics').json()
    assert m['rfq_count']==94 and m['line_count']==249 and m['part_count']>0
    assert m['inquiry_amount'] is None

def test_rules_persist(client):
    assert client.put('/api/rules',json={'asof':'2026-09-20','rate':'25','method':'margin'}).status_code==200
    assert client.get('/api/rules').json()['rate']=='25'

def test_mock_explicit():
    r=MockProvider().extract('anything');assert r['simulated'] and not r['lines']

def test_genesis_contract_without_real_call(monkeypatch):
    monkeypatch.setenv('GENESIS_ACCESS_TOKEN','test-not-secret');monkeypatch.setenv('GENESIS_MODEL_ID','test-model')
    def reply(req):
        assert req.url.path=='/v1/chat/completions'
        return httpx.Response(200,json={'choices':[{'message':{'content':json.dumps({'lines':[{'part_number':'X-1','quantity':2,'unit':'EA','evidence':'X-1 2 EA'}]})}}]})
    r=GenesisProvider(httpx.MockTransport(reply)).extract('X-1 2 EA')
    assert r['provider']=='genesis' and r['review_required']

def test_genesis_hallucinated_evidence_rejected(monkeypatch):
    monkeypatch.setenv('GENESIS_ACCESS_TOKEN','test');monkeypatch.setenv('GENESIS_MODEL_ID','test')
    p=GenesisProvider(httpx.MockTransport(lambda req:httpx.Response(200,json={'choices':[{'message':{'content':'{"lines":[{"evidence":"invented"}]}'}}]})))
    with pytest.raises(ValueError,match='证据'):p.extract('real text')

def test_same_quote_cannot_double_allocate_stock(db):
    from quotepilot.pricing import batch_quote
    cost(db)
    r=batch_quote(db,[dict(part_number='X-1',quantity=3,unit='EA',condition='FN')]*2)
    assert r['quoted_count']==1 and r['pending_count']==1
    assert any('累计库存不足' in x for x in r['lines'][1]['issues'])

def test_condition_edit_cannot_reuse_wrong_price(client):
    r=client.post('/api/quote',json=good_request(client)).json()
    body={'version':1,'actor':'Test','reason':'修改需求件状','patches':[{'line_id':r['lines'][0]['line_id'],'condition':'UNKNOWN'}]}
    assert client.patch('/api/quotes/'+r['quote_id'],json=body).status_code==409

def test_official_attachment_hash_and_cells(client):
    rows=client.get('/api/lines',params={'source_kind':'EML Excel附件'}).json()['rows']
    d=client.get('/api/lines/'+str(rows[0]['id'])).json()
    assert '!' in d['evidence']['raw_json']
    file=next(f for f in d['files'] if f['kind']=='attachment')
    raw=client.get('/api/sources/'+file['id']+'/download').content
    assert hashlib.sha256(raw).hexdigest()==file['sha256']

def test_moi_operator_local_contract():
    from integration.moi_operator import handle
    r=handle('local-contract',None,{'lines':[{'part_number':'MISSING','quantity':1,'unit':'EA'}],'asof':'2026-09-20'})
    assert r['report']['pending_count']==1 and not r['platform_verified']

def test_two_html_tables_keep_distinct_sources(db):
    raw=make_mail();m=__import__('email').message_from_bytes(raw,policy=__import__('email').policy.default)
    html=next(x for x in m.walk() if x.get_content_type()=='text/html')
    content=html.get_content();html.set_content(content+content,subtype='html')
    o=ingest_eml(db,m.as_bytes(),'two.eml')
    assert len(o['lines'])==4 and db.execute('SELECT COUNT(*) FROM rfq_lines').fetchone()[0]==4

def test_spreadsheet_formula_refused():
    from quotepilot.xlsxio import read_xlsx
    w=Workbook();s=w.active;s.append(['Part Number','Quantity','Unit']);s.append(['X-1','=1+1','EA']);b=BytesIO();w.save(b)
    with pytest.raises(ValueError,match='公式'):read_xlsx(b.getvalue())

def test_csv_formula_injection_protected():
    from quotepilot.exports import safe_csv
    assert safe_csv(' =HYPERLINK("bad")').startswith("'")

def test_unpriced_quote_cannot_approve(client):
    row=client.get('/api/lines',params={'search':'GSK-001'}).json()['rows'][0]
    r=client.post('/api/quote',json={'line_ids':[row['id']]}).json()
    body={'version':1,'actor':'Tester','reason':'不能审批缺价行','approve':True,'confirm_constraints':True}
    assert client.patch('/api/quotes/'+r['quote_id'],json=body).status_code==409

def test_cross_customer_draft_cannot_be_approved(client):
    rows=client.get('/api/lines',params={'search':'PN-0001'}).json()['rows']
    groups={r['customer']:r for r in rows if r['quantity']==8 and r['unit']=='EA' and r['part_condition']=='FN'}
    ids=[r['id'] for r in list(groups.values())[:2]]
    assert len(ids)==2
    report=client.post('/api/quote',json={'line_ids':ids}).json()
    assert report['approval_blockers']
    response=client.patch('/api/quotes/'+report['quote_id'],json={'version':1,'actor':'TEST','reason':'跨客户草案不能审批','approve':True,'confirm_constraints':True})
    assert response.status_code==409 and '跨客户' in response.json()['detail']
