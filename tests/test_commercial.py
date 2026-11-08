"""Three supplier groups exercise actual cost, two-role approval and document exports."""
from datetime import date,timedelta
from io import BytesIO
import pytest
from fastapi.testclient import TestClient
from quotepilot.commercial import calculate

def test_margin_is_not_markup_and_costs_are_transparent():
    offer={'unit_price':'10','fx_to_cny':'7','shipping_total':'10','tax_rate':'.1'}
    r=calculate(offer,10,'2','5','.2')
    assert [r[k] for k in ('purchase_cny','processing_cny','freight_cny','tax_cny','other_cny')]==['700.00','20.00','70.00','70.00','5.00']
    assert r['total_cost_cny']=='865.00' and r['suggested_total_cny']=='1081.30'
    with pytest.raises(ValueError):calculate(offer,10,0,0,1)

@pytest.fixture
def clients(tmp_path,monkeypatch):
    import server
    monkeypatch.setattr(server,'DB',tmp_path/'commercial.db')
    for k,v in {'QUOTEPILOT_ENV':'production','QUOTEPILOT_PROVIDER':'mock','QUOTEPILOT_PUBLIC_URL':'https://commercial.example.invalid','QUOTEPILOT_SESSION_SECRET':'TEST_ONLY_SESSION_SECRET_'+'x'*32,'QUOTEPILOT_LOGIN_PASSWORD':'TEST_ONLY_ADMIN_PASS_1234','QUOTEPILOT_REVIEWER_PASSWORD':'TEST_ONLY_REVIEWER_PASS_5678'}.items():monkeypatch.setenv(k,v)
    with TestClient(server.app,base_url='https://commercial.example.invalid',client=('commercial-admin-'+tmp_path.name,53000)) as admin,TestClient(server.app,base_url='https://commercial.example.invalid',client=('commercial-review-'+tmp_path.name,53001)) as reviewer:
        for client,password in [(admin,'TEST_ONLY_ADMIN_PASS_1234'),(reviewer,'TEST_ONLY_REVIEWER_PASS_5678')]:
            client.headers.update({'Origin':'https://commercial.example.invalid'})
            assert client.post('/auth/login',json={'password':password}).status_code==200
        yield admin,reviewer,server.DB

def offer_body(source,supplier,price,lead,group=0):
    return {'source_id':source,'source_locator':'Synthetic offer / line 1','source_excerpt':'SYNTHETIC supplier quotation - not market data','supplier':supplier,'part_number':'PN-0001','specification':'Synthetic valve spec A','unit':'EA','condition':'FN','currency':'CNY','unit_price':str(price),'fx_to_cny':'1','fx_source':'CNY nominal - synthetic test','moq':1,'lead_days':lead,'shipping_total':str(group),'tax_rate':'0','quote_date':date.today().isoformat(),'valid_until':(date.today()+timedelta(days=60)).isoformat(),'payment_terms':'Net 30'}

def setup_inputs(admin,reviewer,group):
    from email.message import EmailMessage
    msg=EmailMessage();msg['From']='Synthetic Customer <qa@example.invalid>';msg['Subject']='SYNTHETIC commercial RFQ';msg['Message-ID']=f'<commercial-{group}@qa.invalid>'
    msg.set_content('RFQ No: SYN-COM\nPart Number: PN-0001\nQuantity: 10\nUnit Of Measure: EA\nCondition: FN\nDescription: Synthetic valve spec A')
    assert admin.post('/api/emails/import',files={'file':('rfq.eml',msg.as_bytes(),'message/rfc822')}).status_code==200
    lid=admin.get('/api/lines',params={'email_id':f'<commercial-{group}@qa.invalid>'}).json()['rows'][0]['id']
    packet=reviewer.get(f'/api/lines/{lid}/field-evidence').json()
    r=reviewer.post(f'/api/lines/{lid}/review-fields',json={'version':packet['review']['version'],'changes':{},'actor':'业务测试员','reason':'合成需求逐项核对','confirm_source':True});assert r.status_code==200,r.text
    source=admin.post('/api/supplier-offers/sources',files={'file':('synthetic-offers.txt',b'SYNTHETIC supplier quotations - QA only','text/plain')}).json()['source_id']
    ids=[]
    for supplier,price,lead in [('SYN-Cheap',10+group,20),('SYN-Fast',15+group,2),('SYN-Balanced',12+group,7)]:
        r=admin.post('/api/supplier-offers',json=offer_body(source,supplier,price,lead,group));assert r.status_code==200,r.text
        oid=r.json()['id'];ids.append(oid)
        r=reviewer.post('/api/supplier-offers/'+oid+'/confirm',json={'version':1,'actor':'业务测试员','reason':'核对合成供应商原件'});assert r.status_code==200,r.text
    req={'line_ids':[lid],'scheme':'lowest_cost','asof':date.today().isoformat(),'valid_until':(date.today()+timedelta(days=14)).isoformat(),'target_margin':'.2','line_costs':{str(lid):{'processing_per_unit_cny':'1','other_total_cny':'2'}},'company_name':'合成测试公司','company_contact':'QA only','customer_name':'合成客户','customer_contact':'qa@example.invalid','delivery_terms':'EXW synthetic terms','payment_terms':'Net 30','remarks':'SYNTHETIC ONLY - 非真实供应商报价'}
    return lid,ids,req

@pytest.mark.parametrize('group',[0,1,2],ids=['supplier-group-A','supplier-group-B','supplier-group-C'])
def test_three_groups_complete_calculate_review_approve_export(clients,group):
    admin,reviewer,db=clients;lid,ids,req=setup_inputs(admin,reviewer,group);drafts={}
    for scheme in ('lowest_cost','fastest','balanced'):
        r=reviewer.post('/api/commercial-quotes',json={**req,'scheme':scheme});assert r.status_code==200,r.text
        drafts[scheme]=r.json()
    assert drafts['lowest_cost']['lines'][0]['selected']['offer']['supplier']=='SYN-Cheap'
    assert drafts['fastest']['lines'][0]['selected']['offer']['supplier']=='SYN-Fast'
    q=drafts['lowest_cost'];qid=q['id'];body={'version':1,'actor':'审核员','reason':'逐项核对合成成本和交期','confirm_risks':True}
    assert admin.get(f'/api/commercial-quotes/{qid}/export/pdf').status_code==409
    assert admin.post(f'/api/commercial-quotes/{qid}/approve',json=body).status_code==409
    r=reviewer.post(f'/api/commercial-quotes/{qid}/review',json=body);assert r.status_code==200,r.text
    assert reviewer.post(f'/api/commercial-quotes/{qid}/approve',json={**body,'version':2}).status_code==403
    r=admin.post(f'/api/commercial-quotes/{qid}/approve',json={**body,'version':2});assert r.status_code==200,r.text
    pdf=admin.get(f'/api/commercial-quotes/{qid}/export/pdf');assert pdf.status_code==200 and pdf.content.startswith(b'%PDF')
    import fitz
    with fitz.open(stream=pdf.content,filetype='pdf') as doc:
        text=''.join(p.get_text() for p in doc);assert 'PN-0001' in text and q['suggested_total_cny'] in text
    xlsx=admin.get(f'/api/commercial-quotes/{qid}/export/xlsx');assert xlsx.status_code==200
    from openpyxl import load_workbook
    book=load_workbook(BytesIO(xlsx.content),data_only=False);assert any(c.value==q['suggested_total_cny'] for row in book.active for c in row);book.close()
    from quotepilot.store import open_db
    with open_db(db) as con:assert con.execute('SELECT COUNT(*) FROM commercial_exports WHERE quote_id=?',(qid,)).fetchone()[0]==2
    assert admin.get('/api/audit/verify').json()['valid']

def test_role_signature_and_admin_routes(clients):
    admin,reviewer,db=clients
    assert reviewer.get('/api/auth/me').json()['role']=='reviewer'
    assert reviewer.get('/api/admin/backup/download').status_code==403
    assert reviewer.get('/api/query-center/schema').status_code==403
    assert reviewer.post('/api/rules',json={}).status_code==403
    assert admin.post('/auth/register',json={}).status_code==404
    cookie=reviewer.cookies.get('qp_session');assert '.reviewer.' in cookie
    reviewer.cookies.set('qp_session',cookie.replace('.reviewer.','.admin.'))
    assert reviewer.get('/api/emails').status_code==401

def test_one_account_cannot_self_approve_and_missing_cost_is_explicit(clients):
    admin,reviewer,db=clients;lid,ids,req=setup_inputs(admin,reviewer,0)
    q=admin.post('/api/commercial-quotes',json=req).json();qid=q['id'];body={'version':1,'actor':'Admin','reason':'合成业务复核测试'}
    assert admin.post(f'/api/commercial-quotes/{qid}/review',json=body).status_code==200
    r=admin.post(f'/api/commercial-quotes/{qid}/approve',json={**body,'version':2});assert r.status_code==409 and '不同账户' in r.text
    q=admin.post('/api/commercial-quotes',json={**req,'line_costs':{}}).json();assert any('缺少加工' in b for b in q['approval_blockers'])

def test_moq_spec_expiry_and_delivery_risks_are_actual_rules(clients):
    admin,reviewer,db=clients;lid,ids,req=setup_inputs(admin,reviewer,0)
    source=admin.get('/api/supplier-offers').json()['rows'][0]['source_id']
    bads=[{'moq':1000},{'specification':'DIFFERENT SPEC'},{'quote_date':(date.today()-timedelta(days=30)).isoformat(),'valid_until':(date.today()-timedelta(days=1)).isoformat()}]
    for n,patch in enumerate(bads):
        r=admin.post('/api/supplier-offers',json={**offer_body(source,'SYN-Rejected'+str(n),'.01',1),**patch});assert r.status_code==200,r.text
        assert reviewer.post('/api/supplier-offers/'+r.json()['id']+'/confirm',json={'version':1,'actor':'QA','reason':'异常报价合成核对'}).status_code==200
    q=admin.post('/api/commercial-quotes',json=req).json()
    reasons=';'.join(';'.join(x['reasons']) for x in q['lines'][0]['rejected'])
    assert all(x in reasons for x in ('MOQ','规格','已过期'))
    q=admin.post('/api/commercial-quotes',json={**req,'delivery_deadline':(date.today()+timedelta(days=1)).isoformat()}).json()
    assert q['lines'][0]['selected'] is None and q['approval_blockers']

def test_non_finite_and_extreme_cost_inputs_are_rejected():
    for value in ('NaN','Infinity','1e-1000','1e1000'):
        with pytest.raises(ValueError):calculate({'unit_price':value,'fx_to_cny':'1'},1,0,0,'.2')

def test_price_anomaly_compares_only_same_supplier_spec_currency(clients):
    admin,reviewer,db=clients;lid,ids,req=setup_inputs(admin,reviewer,0)
    source=admin.get('/api/supplier-offers').json()['rows'][0]['source_id']
    r=admin.post('/api/supplier-offers',json=offer_body(source,'SYN-Cheap','20',20));assert r.status_code==200
    assert r.json()['price_change']['warning'] and r.json()['price_change']['change_ratio']=='1'
    other=offer_body(source,'SYN-Cheap','20',20);other.update(currency='USD',fx_to_cny='7')
    assert 'price_change' not in admin.post('/api/supplier-offers',json=other).json()
