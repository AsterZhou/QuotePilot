"""Ten independently generated synthetic RFQ files; no external/model API is used."""
from email.message import EmailMessage
from io import BytesIO
import json,sqlite3
import pytest
from quotepilot.store import open_db,ingest_eml,seed_official
from quotepilot.provenance import detail,review,verify_field,verify_audit,assert_ready

def document(index):
    msg=EmailMessage();msg['From']='Synthetic <qa@example.invalid>';msg['Subject']='SYNTHETIC FIELD QA '+str(index);msg['Message-ID']=f'<field-{index}@qa.invalid>'
    msg.set_content('Synthetic attachment for provenance testing.')
    rfq=f'RFQ-QA{index:02d}'
    if index<3:
        msg.set_content(f'RFQ No: {rfq}\nPart Number: PN-0001\nQuantity: 3\nUnit Of Measure: EA\nCondition: FN\nDescription: Synthetic valve')
    elif index<6:
        msg.add_alternative(f'<table><tr><th>RFQ No</th><th>Part Number</th><th>Quantity</th><th>Unit Of Measure</th><th>Condition</th></tr><tr><td>{rfq}</td><td>PN-0001</td><td>3</td><td>EA</td><td>FN</td></tr></table>',subtype='html')
    elif index<8:
        from openpyxl import Workbook
        book=Workbook();sheet=book.active;sheet.title='RFQ items';sheet.append(['RFQ No','Part Number','Quantity','Unit Of Measure','Condition']);sheet.append([rfq,'PN-0001',3,'EA','FN']);out=BytesIO();book.save(out)
        msg.add_attachment(out.getvalue(),maintype='application',subtype='vnd.openxmlformats-officedocument.spreadsheetml.sheet',filename=f'synthetic-{index}.xlsx')
    else:
        import fitz
        pdf=fitz.open();page=pdf.new_page();page.insert_text((35,40),'REQUEST FOR QUOTATION # '+rfq)
        for x,label in [(35,'Part Number'),(190,'Quantity'),(290,'Unit Of Measure'),(420,'Condition')]:page.insert_text((x,80),label,fontsize=10)
        for x,value in [(35,'PN-0001'),(190,'3'),(290,'EA'),(420,'FN')]:page.insert_text((x,110),value,fontsize=10)
        raw=pdf.tobytes();pdf.close();msg.add_attachment(raw,maintype='application',subtype='pdf',filename=f'synthetic-{index}.pdf')
    return msg.as_bytes()

@pytest.mark.parametrize('index',range(10),ids=lambda n:f'synthetic-file-{n:02d}')
def test_ten_files_source_value_review_and_history(tmp_path,index):
    raw=document(index);con=open_db(tmp_path/'qa.db');result=ingest_eml(con,raw,f'synthetic-{index}.eml',dataset='synthetic_test')
    assert len(result['lines'])==1,result['parse_notes']
    lid=con.execute('SELECT id FROM rfq_lines').fetchone()[0];packet=detail(con,lid);con.commit()
    pn=next(f for f in packet['fields'] if f['field']=='part_number')
    assert pn['source_id'] and pn['source_sha256'] and pn['extracted_at'] and pn['snippet']=='PN-0001'
    assert verify_field(con,pn) in ('cell_value_found','page_span_found','text_span_found')
    if 6<=index<8:assert pn['locator']['cell']=='RFQ items!B2'
    if index>=8:assert pn['locator']['page']==1
    with pytest.raises(ValueError,match='尚未人工复核'):assert_ready(con,lid)
    after=review(con,lid,1,{'quantity':4},'QA_REVIEWER','合成文件数量修改核对',True)
    assert after['review']['status']=='confirmed' and after['line']['quantity']==4
    qty=next(f for f in after['fields'] if f['field']=='quantity');assert qty['extracted_value']==3
    changed=next(r for r in after['revisions'] if r['field']=='quantity');assert changed['before']==3 and changed['after']==4 and changed['actor']=='QA_REVIEWER'
    assert_ready(con,lid,2)
    with pytest.raises(ValueError,match='版本冲突'):review(con,lid,1,{},'OTHER','过期版本复核',True)
    with pytest.raises(sqlite3.IntegrityError):con.execute('DELETE FROM field_revisions')
    assert verify_audit(con)['valid'];con.close()

def test_audit_and_source_bytes_are_immutable_and_chain_detects_privileged_tampering(tmp_path):
    con=open_db(tmp_path/'qa.db');ingest_eml(con,document(0),'original.eml')
    original=con.execute("SELECT content FROM source_files WHERE kind='eml'").fetchone()[0]
    assert original==document(0)
    for statement in ["UPDATE source_files SET content=X'00'","DELETE FROM audit_events","UPDATE field_evidence SET snippet='forged'"]:
        with pytest.raises(sqlite3.IntegrityError):con.execute(statement)
    assert verify_audit(con)['valid']
    con.execute('DROP TRIGGER protect_audit_events_update');con.execute("UPDATE audit_events SET actor='forged'");con.commit()
    assert not verify_audit(con)['valid'];con.close()

def test_review_gate_and_stale_quote_api(tmp_path,monkeypatch):
    import server
    from fastapi.testclient import TestClient
    monkeypatch.setattr(server,'DB',tmp_path/'api.db')
    with TestClient(server.app) as c:
        assert c.post('/api/emails/import',files={'file':('synthetic.eml',document(0),'message/rfc822')}).status_code==200
        lid=c.get('/api/lines',params={'email_id':'<field-0@qa.invalid>'}).json()['rows'][0]['id']
        request={'line_ids':[lid],'asof':'2026-09-20'};draft=c.post('/api/quote',json=request).json();qid=draft['quote_id']
        approve={'version':1,'actor':'QA','reason':'测试审批限制','approve':True,'confirm_constraints':True}
        assert c.patch('/api/quotes/'+qid,json=approve).status_code==409
        evidence=c.get(f'/api/lines/{lid}/field-evidence').json()
        result=c.post(f'/api/lines/{lid}/review-fields',json={'version':evidence['review']['version'],'changes':{'quantity':4},'actor':'QA','reason':'逐字段核对数量','confirm_source':True});assert result.status_code==200,result.text
        assert c.patch('/api/quotes/'+qid,json=approve).status_code==409
        fresh=c.post('/api/quote',json=request).json()
        checked=c.patch('/api/quotes/'+fresh['quote_id'],json=approve);assert checked.status_code==200,checked.text
        assert c.get('/api/review-queue').status_code==200 and c.get('/api/audit/verify').json()['valid']
