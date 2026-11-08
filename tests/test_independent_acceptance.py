"""Independent regression cases: real source parsers, legacy bypass and multi-line cents."""
from io import BytesIO
from datetime import date,timedelta
from decimal import Decimal
from email.message import EmailMessage
import json,sqlite3
import pytest
from test_commercial import clients,setup_inputs,offer_body
from quotepilot.commercial import calculate,allocate_cents


def source_values():
    return {'Supplier':'SYN-AUTO','Part Number':'PN-0001','Specification':'Synthetic valve spec A','Unit':'EA','Condition':'FN','Currency':'CNY','Unit Price':'4','FX to CNY':'1','FX source':'CNY nominal synthetic','MOQ':'1','Lead days':'2','Shipping total':'0','Tax rate':'0%','Quote date':date.today().isoformat(),'Valid until':(date.today()+timedelta(days=60)).isoformat(),'Payment terms':'Net 30'}


def file_bytes(kind):
    values=source_values();text='\n'.join(f'{k}: {v}' for k,v in values.items())
    if kind=='txt':return text.encode()
    if kind=='pdf':
        import pymupdf
        doc=pymupdf.open();p=doc.new_page();p.insert_text((40,40),text,fontsize=10);raw=doc.tobytes();doc.close();return raw
    if kind=='xlsx':
        from openpyxl import Workbook
        w=Workbook();w.active.append(list(values));w.active.append(list(values.values()));b=BytesIO();w.save(b);w.close();return b.getvalue()
    m=EmailMessage();m['From']='qa@example.invalid';m.set_content(text);return m.as_bytes()


@pytest.mark.parametrize('kind',['txt','pdf','xlsx','eml'])
def test_uploaded_source_extraction_human_confirm_then_pricing(clients,kind):
    admin,review,db=clients;lid,ids,req=setup_inputs(admin,review,0)
    sid=admin.post('/api/supplier-offers/sources',files={'file':('auto.'+kind,file_bytes(kind),'application/octet-stream')}).json()['source_id']
    extracted=review.post(f'/api/supplier-offers/sources/{sid}/extract',json={});assert extracted.status_code==200,extracted.text
    run=extracted.json();assert not run['model_called'] and not run['simulated'] and len(run['candidates'])==1
    c=run['candidates'][0];assert not c['missing_fields'] and c['values']['unit_price']=='4'
    assert c['field_evidence']['unit_price']['source_sha256']==run['source_sha256']
    assert len(admin.get('/api/supplier-offers').json()['rows'])==3  # suggestions not executable
    offer={**c['values'],'source_id':sid,'source_locator':'由真实定位片段核对','source_excerpt':'Unit Price: 4','extraction_run_id':run['id'],'extraction_candidate':0,'unit_price':'5'}
    r=review.post('/api/supplier-offers',json=offer);assert r.status_code==200,r.text;oid=r.json()['id']
    assert r.json()['extraction']['human_changed_fields']['unit_price']=={'extracted':'4','confirmed':'5'}
    q=review.post('/api/commercial-quotes',json=req).json();assert q['lines'][0]['selected']['offer_id']!=oid
    assert review.post(f'/api/supplier-offers/{oid}/confirm',json={'version':1,'actor':'QA','reason':'核对自动提取的真实合成原件'}).status_code==200
    q=review.post('/api/commercial-quotes',json=req).json();assert q['lines'][0]['selected']['offer_id']==oid
    other=admin.get('/api/supplier-offers').json()['rows'][-1]['source_id']
    assert review.post('/api/supplier-offers',json={**offer,'source_id':other}).status_code==409
    from quotepilot.store import open_db
    with open_db(db) as con:
        with pytest.raises(sqlite3.IntegrityError):con.execute('DELETE FROM supplier_extraction_runs')


def test_scan_returns_honest_manual_fallback_and_formula_is_never_executed(clients):
    admin,review,_=clients
    from pathlib import Path
    from email.parser import BytesParser
    from email import policy
    m=BytesParser(policy=policy.default).parsebytes(Path('tests/foreign_v07/11_scan_small.eml').read_bytes());raw=next(p.get_payload(decode=True) for p in m.walk() if p.get_filename()=='scan.pdf')
    sid=admin.post('/api/supplier-offers/sources',files={'file':('scan.pdf',raw,'application/pdf')}).json()['source_id']
    r=review.post(f'/api/supplier-offers/sources/{sid}/extract',json={}).json()
    assert not r['candidates'] and any('OCR' in n for n in r['notes'])
    from openpyxl import Workbook
    w=Workbook();w.active.append(['Part Number','Unit Price']);w.active.append(['PN-1','=1+1']);buf=BytesIO();w.save(buf);w.close()
    sid=admin.post('/api/supplier-offers/sources',files={'file':('formula.xlsx',buf.getvalue(),'application/octet-stream')}).json()['source_id']
    r=review.post(f'/api/supplier-offers/sources/{sid}/extract',json={}).json();assert 'unit_price' in r['candidates'][0]['missing_fields'] and any('公式未执行' in n for n in r['notes'])


def test_legacy_production_approval_is_not_a_two_role_bypass(clients):
    admin,review,db=clients;lid,ids,req=setup_inputs(admin,review,0)
    q=admin.post('/api/quote',json={'line_ids':[lid],'asof':'2026-09-20'}).json();qid=q['quote_id']
    response=admin.patch(f'/api/quotes/{qid}',json={'version':1,'actor':'Admin','reason':'尝试绕过双角色审核','approve':True,'confirm_constraints':True})
    assert response.status_code==409 and '双角色' in response.text
    assert review.patch(f'/api/quotes/{qid}',json={}).status_code==403
    # Legacy draft exports still work, existing approved snapshots stay readable.
    assert admin.get(f'/api/quotes/{qid}/export/xlsx').status_code==200
    from quotepilot.store import open_db
    with open_db(db) as con:
        p=json.loads(con.execute('SELECT report_json FROM quotes WHERE id=?',(qid,)).fetchone()[0]);p['review_status']='approved'
        con.execute("UPDATE quotes SET status='approved',report_json=? WHERE id=?",(json.dumps(p),qid));con.commit()
    assert admin.get(f'/api/quotes/{qid}/export/xlsx?final=true').status_code==200
    assert admin.patch(f'/api/quotes/{qid}',json={'version':1,'actor':'Admin','reason':'旧审批不可改写','patches':[]}).status_code==409


def test_component_rounding_conserves_displayed_cost_and_small_prices_do_not_divide_by_zero():
    c=calculate({'unit_price':'.005','fx_to_cny':'1','shipping_total':'.005','tax_rate':'0'},1,'.005','.005','.2')
    assert c['total_cost_cny']=='0.04'
    assert sum(Decimal(c[k]) for k in ('purchase_cny','processing_cny','freight_cny','tax_cny','other_cny'))==Decimal(c['total_cost_cny'])
    assert c['suggested_total_cny']=='0.05' and Decimal(c['actual_margin'])==Decimal('.2')
    shares=allocate_cents(Decimal('.01'),{3:Decimal(1),1:Decimal(1),2:Decimal(1)})
    assert shares=={3:Decimal(0),1:Decimal('.01'),2:Decimal(0)}


def test_multiline_shipment_freight_once_and_persisted_export_total(clients):
    admin,review,_=clients
    _,_,req=setup_inputs(admin,review,0)
    m=EmailMessage();m['From']='Synthetic Customer <qa@example.invalid>';m['Message-ID']='<multi-cent@qa.invalid>';m['Subject']='SYNTHETIC three line shipment'
    m.set_content('SYNTHETIC ONLY')
    fields=['RFQ No','Part Number','Quantity','Unit Of Measure','Condition','Description']
    rows=[['SHIP-1',f'FREIGHT-{i}',3,'EA','FN','Synthetic valve spec A'] for i in range(1,4)]
    m.add_alternative('<table><tr>'+''.join(f'<th>{f}</th>' for f in fields)+'</tr>'+''.join('<tr>'+''.join(f'<td>{v}</td>' for v in row)+'</tr>' for row in rows)+'</table>',subtype='html')
    assert admin.post('/api/emails/import',files={'file':('multi.eml',m.as_bytes(),'message/rfc822')}).status_code==200
    lids=[l['id'] for l in admin.get('/api/lines',params={'email_id':'<multi-cent@qa.invalid>'}).json()['rows']]
    sid=admin.post('/api/supplier-offers/sources',files={'file':('ship.txt',b'SYNTHETIC shared freight 0.01 CNY','text/plain')}).json()['source_id']
    for i,lid in enumerate(lids,1):
        packet=review.get(f'/api/lines/{lid}/field-evidence').json()
        assert review.post(f'/api/lines/{lid}/review-fields',json={'version':packet['review']['version'],'changes':{},'actor':'QA','reason':'核对多明细原件','confirm_source':True}).status_code==200
        body={**offer_body(sid,'SYN-SHIP','1',2),'part_number':f'FREIGHT-{i}','shipping_scope':'shipment','shipping_group':'SYN-SHARED-1','shipping_total':'.01'}
        oid=review.post('/api/supplier-offers',json=body).json()['id'];assert review.post(f'/api/supplier-offers/{oid}/confirm',json={'version':1,'actor':'QA','reason':'整票运费明确来自原件'}).status_code==200
    req.update(line_ids=lids,line_costs={str(l):{'processing_per_unit_cny':'0','other_total_cny':'0'} for l in lids})
    response=review.post('/api/commercial-quotes',json=req);assert response.status_code==200,response.text;q=response.json()
    assert q['total_cost_cny']=='9.01'
    assert sum(Decimal(l['selected']['calculation']['freight_cny']) for l in q['lines'])==Decimal('.01')
    assert q['freight_allocations'][0]['total_cny']=='0.01'
    assert list(q['freight_allocations'][0]['lines'].values()).count('0.01')==1
    assert Decimal(q['suggested_total_cny'])==sum(Decimal(l['selected']['calculation']['suggested_unit_price_cny'])*l['quantity'] for l in q['lines'])
    export=admin.get(f'/api/commercial-quotes/{q["id"]}/export/xlsx?final=false');assert export.status_code==200
    from openpyxl import load_workbook
    book=load_workbook(BytesIO(export.content));assert any(c.value==q['suggested_total_cny'] for row in book.active for c in row);book.close()


def test_actual_v07_schema_upgrade_preserves_source_and_approved_amount(tmp_path):
    from pathlib import Path
    import hashlib
    from quotepilot.store import open_db
    from quotepilot.reviews import load_quote
    from quotepilot.commercial_exports import export_quote
    from quotepilot.exports import quote_xlsx
    from quotepilot.provenance import verify_audit
    db=tmp_path/'legacy.db';old=sqlite3.connect(db)
    old.executescript(Path('tests/legacy_v07.sql').read_text());old.commit()
    qid,original=old.execute('SELECT id,report_json FROM quotes').fetchone()
    original_sources=old.execute('SELECT id,content FROM source_files ORDER BY id').fetchall();old.close()
    for _ in range(3):
        con=open_db(db);q=load_quote(con,qid)
        assert q['total_cny']=='49.89' and q['review_status']=='approved'
        assert con.execute('SELECT report_json FROM quotes WHERE id=?',(qid,)).fetchone()[0]==original
        assert [(r['id'],r['content']) for r in con.execute('SELECT id,content FROM source_files ORDER BY id')]==original_sources
        assert con.execute('PRAGMA foreign_key_check').fetchall()==[]
        assert verify_audit(con)['valid']
        assert quote_xlsx(q).startswith(b'PK');con.close()
