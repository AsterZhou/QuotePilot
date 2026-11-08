from email.message import EmailMessage
import json,sqlite3
import pytest
from quotepilot.store import open_db,ingest_eml
from quotepilot.rfq_versions import register,compare,compare_items,load,record_matches

def eml(n,rows,customer='buyer@example.invalid'):
    msg=EmailMessage();msg['From']=customer;msg['Subject']='SYNTHETIC RFQ V'+str(n);msg['Message-ID']=f'<version-{n}@qa.invalid>'
    headers=['RFQ No','Part Number','Quantity','Unit Of Measure','Condition','Line No','Description']
    msg.set_content('Synthetic version comparison. Payment Net 30.')
    msg.add_alternative('<table><tr>'+''.join('<th>'+x+'</th>' for x in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(x)+'</td>' for x in ['RFQ-V',*row])+'</tr>' for row in rows)+'</table>',subtype='html')
    return msg.as_bytes()

def versions(tmp_path,before,after):
    con=open_db(tmp_path/'versions.db')
    ingest_eml(con,eml(1,before),'v1.eml');a=register(con,'<version-1@qa.invalid>','RFQ-V','QA','保留合成初始版本')
    ingest_eml(con,eml(2,after),'v2.eml');b=register(con,'<version-2@qa.invalid>','RFQ-V','QA','保留合成变更版本')
    return con,a,b,compare(con,a['id'],b['id'],'2026-09-20')

def test_quantity_change_and_quote_impact_without_invented_margin(tmp_path):
    con,a,b,d=versions(tmp_path,[['PN-1',100,'EA','FN','1','valve']],[['PN-1',500,'EA','FN','1','valve']])
    old=a['snapshot']['lines'][0]['line_id'];snapshot={'price_basis':{'record':{'supplier':'Synthetic supplier','resource_id':'SYN-1','moq':200,'valid_until':'2026-08-01'}}}
    con.execute("INSERT INTO quotes(id,status,report_json,rule_version) VALUES('SYNTHETIC-Q','draft','{}','test')")
    con.execute('INSERT INTO quote_items VALUES(?,?,?)',('SYNTHETIC-Q',old,json.dumps(snapshot)));con.commit()
    d=compare(con,a['id'],b['id'],'2026-09-20')
    assert d['modified'][0]['changes']['quantity']=={'before':100,'after':500}
    assert d['quote_impacts'][0]['requires_requote'] and d['quote_impacts'][0]['profit_impact']=='unknown_until_recalculated'
    assert '历史供应商报价已过有效期' in d['quote_impacts'][0]['risks']
    assert load(con,a['id'])['snapshot']['lines'][0]['quantity']==100
    with pytest.raises(sqlite3.IntegrityError):con.execute("UPDATE rfq_versions SET payload_json='{}'")
    con.close()

def test_reordering_add_delete_and_unchanged(tmp_path):
    con,a,b,d=versions(tmp_path,[['A-1',1,'EA','FN','1','A'],['B-1',2,'EA','FN','2','B']],[['C-1',3,'EA','FN','3','C'],['A-1',1,'EA','FN','1','A']])
    assert d['summary']=={'added':1,'removed':1,'modified':0,'unchanged':1,'ambiguous':0};con.close()

def test_stable_customer_item_id_can_detect_changed_part_number(tmp_path):
    con,a,b,d=versions(tmp_path,[['A-1',1,'EA','FN','stable-1','A']],[['A-2',1,'EA','FN','stable-1','A']])
    assert d['modified'][0]['changes']['part_number']=={'before':'A-1','after':'A-2'} and not d['added'];con.close()

def test_duplicate_part_without_stable_business_id_needs_manual_matching(tmp_path):
    con,a,b,d=versions(tmp_path,[['A-1',1,'EA','FN','','A'],['A-1',2,'EA','FN','','B']],[['A-1',3,'EA','FN','','A'],['A-1',4,'EA','FN','','B']])
    assert len(d['ambiguous'])==1 and not d['modified'] and not d['added'] and not d['removed']
    old=a['snapshot']['lines'];new=b['snapshot']['lines']
    matches={str(old[0]['line_id']):new[1]['line_id'],str(old[1]['line_id']):new[0]['line_id']}
    record_matches(con,a['id'],b['id'],matches,'QA','人工核对原文对应关系')
    diff=compare(con,a['id'],b['id'],'2026-09-20');assert not diff['ambiguous'] and len(diff['modified'])==2
    with pytest.raises(ValueError):record_matches(con,a['id'],b['id'],{str(old[0]['line_id']):999999},'QA','错误行号匹配测试')
    assert con.execute('SELECT COUNT(*) FROM rfq_match_decisions').fetchone()[0]==1
    con.close()

def test_unit_spec_condition_and_header_terms_are_distinct(tmp_path):
    con,a,b,d=versions(tmp_path,[['A-1',1,'EA','FN','1','size A']],[['A-1',1,'FT','OH','1','size B']])
    assert set(d['modified'][0]['changes'])=={'unit','part_condition','description'}
    source=con.execute("SELECT id FROM source_files WHERE email_id='<version-2@qa.invalid>' AND kind='body'").fetchone()[0]
    terms={'payment_terms':{'value':'Net 30','source_id':source,'locator':'邮件正文第一段','snippet':'Payment Net 30'}}
    c=register(con,'<version-2@qa.invalid>','RFQ-V','QA','人工条款来源登记',terms)
    d=compare(con,b['id'],c['id'],'2026-09-20');assert d['header_changes']['payment_terms']['after']['value']=='Net 30'
    assert not d['modified'] and 'delivery_date' in d['unprovided_terms']
    assert register(con,'<version-2@qa.invalid>','RFQ-V','QA','重复登记测试',terms)['idempotent'];con.close()

def test_customers_are_not_silently_merged(tmp_path):
    con=open_db(tmp_path/'customers.db')
    for n,buyer in [(1,'one@example.invalid'),(2,'two@example.invalid')]:ingest_eml(con,eml(n,[['A-1',1,'EA','FN','1','A']],buyer),f'v{n}.eml')
    a=register(con,'<version-1@qa.invalid>','RFQ-V','QA','客户一版本登记');b=register(con,'<version-2@qa.invalid>','RFQ-V','QA','客户二版本登记')
    with pytest.raises(ValueError,match='不同客户'):compare(con,a['id'],b['id'],'2026-09-20')
    con.close()

def test_version_register_and_compare_api(tmp_path,monkeypatch):
    import server
    from fastapi.testclient import TestClient
    monkeypatch.setattr(server,'DB',tmp_path/'api.db')
    with TestClient(server.app) as c:
        ids=[]
        for n,qty in [(1,100),(2,500)]:
            assert c.post('/api/emails/import',files={'file':(f'v{n}.eml',eml(n,[['PN-0001',qty,'EA','FN','1','test']]),'message/rfc822')}).status_code==200
            r=c.post('/api/rfq-versions',json={'email_id':f'<version-{n}@qa.invalid>','rfq_no':'RFQ-V','actor':'QA','reason':'合成版本来源核对'})
            assert r.status_code==200,r.text
            ids.append(r.json()['id'])
        result=c.get('/api/rfq-versions/compare',params={'left':ids[0],'right':ids[1],'asof':'2026-09-20'})
        assert result.status_code==200 and result.json()['modified'][0]['changes']['quantity']['after']==500
        assert len(c.get('/api/rfq-versions').json()['rows'])==2
        assert c.get('/api/rfq-versions/'+ids[0]).json()['snapshot']['lines'][0]['quantity']==100
