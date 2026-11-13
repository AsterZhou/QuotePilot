"""Regressions from the release audit. All writes use isolated SQLite files."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from email.message import EmailMessage
from io import BytesIO
from threading import Barrier
from zipfile import ZipFile
import random

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest

import server
from quotepilot import commercial, operations, pricing, security
from quotepilot.parsing import parse_eml
from quotepilot.query_center import session, save
from quotepilot.store import open_db, audit, ingest_eml
from quotepilot.supplier_extraction import normalized, text_records


def workbook(rows):
    book = Workbook()
    for row in rows:
        book.active.append(row)
    buf = BytesIO()
    book.save(buf)
    return buf.getvalue()


def email(subject):
    msg = EmailMessage()
    msg['From'] = 'QA <test@example.invalid>'
    msg['Subject'] = subject
    msg['Message-ID'] = f'<{subject}@example.invalid>'
    msg.set_content('Part Number: TEST\nQuantity: 1\nUnit: EA')
    return msg


@pytest.fixture
def local(tmp_path, monkeypatch):
    path = tmp_path / 'audit.sqlite'
    monkeypatch.setattr(server, 'DB', path)
    monkeypatch.setenv('QUOTEPILOT_RELEASE_DEMO', '1')
    monkeypatch.setenv('QUOTEPILOT_ENV', 'development')
    with TestClient(server.app) as client:
        yield client, path


@pytest.mark.parametrize('field', ['unit_price', 'fx_to_cny', 'tax_rate', 'shipping_total'])
@pytest.mark.parametrize('raw', ['13,86', '1.234,56','1,2,3', '13,86%'])
def test_ambiguous_separators_require_review(field, raw):
    rows = text_records('Part Number: TEST\n' + field + ': ' + raw, 'supplier.txt')
    values, trace = rows[0]
    assert values[field] == raw
    assert raw in trace[field]['raw_text']
    with pytest.raises(ValueError):
        commercial.decimal(values[field])


@pytest.mark.parametrize(('raw','expected'), [('1,234.50','1234.50'), ('1,000,000','1000000'), ('12.5%','0.125')])
def test_supported_separators_preserved(raw,expected):
    assert normalized('tax_rate' if '%' in raw else 'unit_price',raw) == expected


def test_duplicate_attachment_names(local):
    client, db = local
    msg = email('two-attachments')
    msg.set_content('See attached workbooks.')
    for part in ['AAA', 'BBB']:
        raw = workbook([['Part Number','Quantity','Unit'],[part,2,'EA']])
        msg.add_attachment(raw, maintype='application',subtype='octet-stream',filename='清单.xlsx')
    raw = msg.as_bytes()
    response = client.post('/api/emails/import',files={'file':('two.eml',raw)})
    assert response.status_code == 200, response.text
    assert response.json()['new_lines'] == 2
    rows = client.get('/api/lines', params={'email_id':msg['Message-ID']}).json()['rows']
    assert [r['part_number'] for r in rows] == ['AAA','BBB']
    assert len({r['source_ref'] for r in rows}) == 2
    with open_db(db) as con:
        assert con.execute("SELECT count(DISTINCT source_id) FROM field_evidence WHERE field='part_number'").fetchone()[0] == 2
    assert client.post('/api/emails/import',files={'file':('two.eml',raw)}).json()['new_lines'] == 0


def test_inconsistent_html_table_keeps_unmapped_cells():
    msg=email('ragged-table')
    msg.add_alternative('<table><tr><th>PN</th><th>Qty</th><th>Unit</th></tr>'
                        '<tr><td>OK</td><td>2</td><td>EA</td></tr>'
                        '<tr><td>BAD</td><td>9</td><td>48</td><td>EA</td></tr></table>',subtype='html')
    out=parse_eml(msg.as_bytes(),'ragged.eml')
    assert [i['part_number'] for i in out['lines']] == ['OK']
    assert '48' in str(out['rejected_rows']) and 'BAD' in str(out['rejected_rows'])


def test_underreported_sheet_dimensions_keep_all_rows():
    import re
    from quotepilot.xlsxio import read_xlsx

    raw=workbook([['Part Number','Qty','Unit'],['ONE',2,'EA'],['TWO',3,'EA']])
    dest=BytesIO()
    with ZipFile(BytesIO(raw)) as src, ZipFile(dest,'w') as dst:
        for name in src.namelist():
            data=src.read(name)
            if name=='xl/worksheets/sheet1.xml':
                data=re.sub(rb'<dimension ref="[^"]+"',b'<dimension ref="A1:C2"',data)
            dst.writestr(name,data)
    assert [r['Part Number'] for r in read_xlsx(dest.getvalue())] == ['ONE','TWO']


@pytest.mark.parametrize('field,table',[('unit','costs'),('part_condition','costs'),('condition','prices')])
def test_null_candidate_does_not_break_valid_alternative(local,field,table):
    client, path=local
    with open_db(path) as db:
        if table=='costs':
            row={'part_number':'QA','unit':'EA','inventory':20,'warehouse':'QA','part_condition':'FN','standard_cost':'1','currency':'CNY','updated_at':'2026-01-01','source_row':'2'}
        else:
            row={'resource_id':'bad','part_number':'QA','condition':'FN','status':'有效','source_row':'3'}
        row[field]=None
        db.execute(f'INSERT INTO {table} ({",".join(row)}) VALUES ({",".join("?" for _ in row)})',list(row.values()))
        db.execute("INSERT INTO prices(resource_id,part_number,supplier,condition,status,unit_price,currency,fx_to_cny,moq,quote_date,valid_until) VALUES ('good','QA','QA','FN','有效','10','CNY','1',1,'2026-01-01','2026-12-31')")
        db.commit()
        q=pricing.quote_line(db,'QA',1,condition='FN')
        assert q['price_ref']=='good' and q['unit_quote_cny']=='12.00'
        assert any(c['issues'] for c in q['candidates'])


def test_concurrent_confirmations_only_record_one_review(local):
    client,path=local
    with open_db(path) as db:
        db.execute("INSERT INTO supplier_offers VALUES ('offer','{}','source','2026-01-01')")
        db.execute("INSERT INTO supplier_offer_catalog VALUES ('offer','S','PN','SPEC','EA','FN','1','CNY','1',1,0,'2026-01-01','2026-12-31','source')")
        db.commit()
    barrier=Barrier(4)
    def confirm(n):
        barrier.wait()
        response=client.post('/api/supplier-offers/offer/confirm',json={'actor':'QA','reason':'test retry','version':1})
        return response.status_code
    with ThreadPoolExecutor(max_workers=4) as pool:
        assert list(pool.map(confirm,range(4)))==[200]*4
    with open_db(path) as db:
        assert db.execute("SELECT count(*) FROM offer_reviews WHERE offer_id='offer'").fetchone()[0]==1
        assert db.execute("SELECT count(*) FROM audit_events WHERE action='supplier_offer_confirmed'").fetchone()[0]==1


def test_import_counts_only_own_committed_rows(local,monkeypatch):
    client,path=local
    def interleaved(con,raw,name):
        result=ingest_eml(con,raw,name)
        with open_db(path) as other:
            ingest_eml(other,email('other').as_bytes(),'other.eml')
        return result
    monkeypatch.setattr(server,'ingest_eml',interleaved)
    r=client.post('/api/emails/import',files={'file':('this.eml',email('this').as_bytes())}).json()
    assert (r['parsed_count'],r['new_lines'],r['duplicate_lines'])==(1,1,0)


def test_analytics_receipts_are_counted_and_deduplicated(local):
    _,path=local
    sid,_=session(path,'qa')
    save(path,sid,'overlap',{'status':'completed','response_id':'shared','usage':{'total_tokens':2}})
    with open_db(path) as db:
        for rid,n in [('shared',2),('only-in-analytics',9)]:
            audit(db,'analytics_genesis_query',rid,{'response_id':rid,'usage':{'total_tokens':n}})
        db.commit()
        result=operations.metrics(db)
        assert (result['recorded_model_call_count'],result['known_total_tokens'])==(2,11)


@pytest.mark.parametrize('analysis',[None,[],42])
def test_malformed_historical_analysis_keeps_other_receipts(local,analysis):
    _,path=local
    sid,_=session(path,'qa')
    save(path,sid,'old shape',{'status':'completed','analysis':analysis,'response_id':'valid','usage':{'total_tokens':9}})
    with open_db(path) as db:
        result=operations.metrics(db)
    assert result['recorded_model_call_count']==1 and result['known_total_tokens']==9
    assert result['invalid_json_records']==1


def test_non_ascii_cookie_signature_is_unauthenticated(monkeypatch):
    monkeypatch.setenv('QUOTEPILOT_SESSION_SECRET','x'*40)
    prefix=security.signed_session().rsplit('.',1)[0]
    assert not security.valid_session(prefix+'.é')


@pytest.mark.parametrize('seed',range(8))
def test_cost_and_freight_conservation(seed):
    rng=random.Random(seed)
    for _ in range(30):
        weights={i:Decimal(rng.randint(1,10000))/100 for i in range(rng.randint(1,15))}
        amount=Decimal(rng.randint(0,10000))/100
        shares=commercial.allocate_cents(amount,weights)
        assert set(shares)==set(weights) and sum(shares.values())==amount and min(shares.values())>=0
        qty=rng.randint(1,500)
        q=commercial.calculate({'unit_price':str(weights[0]),'fx_to_cny':'1','tax_rate':'.13','shipping_total':str(amount)},qty,'0.03','1','.2')
        assert sum(Decimal(q[k]) for k in ('purchase_cny','processing_cny','tax_cny','freight_cny','other_cny'))==Decimal(q['total_cost_cny'])
        assert Decimal(q['suggested_total_cny'])==Decimal(q['suggested_unit_price_cny'])*qty


def test_saved_workbook_candidate_retry_preserves_original_offer(local):
    from test_commercial import offer_body
    client, path = local
    raw = workbook([['Part Number','Unit Price'], ['PN-0001','11']])
    source = client.post('/api/supplier-offers/sources',files={'file':('supplier.xlsx',raw)}).json()['source_id']
    run = client.post('/api/supplier-offers/sources/'+source+'/extract').json()
    offer = dict(offer_body(source,'S-1',11,3),extraction_run_id=run['id'],extraction_candidate=0)
    first = client.post('/api/supplier-offers',json=offer)
    retried = client.post('/api/supplier-offers',json=offer)
    assert first.status_code == retried.status_code == 200
    assert first.json()['id'] == retried.json()['id']
    assert client.post('/api/supplier-offers',json={**offer,'unit_price':'99'}).status_code==409


def test_official_candidate_requires_explicit_shipping_scope(local):
    from test_commercial import offer_body
    client, path = local
    raw = workbook([['价格资源编号','Part Number','价格状态','报价日期','有效期至','单价'],
                    ['QA-01','PN-0001','有效','2026-01-01','2026-12-31','11']])
    source = client.post('/api/supplier-offers/sources',files={'file':('catalog.xlsx',raw)}).json()['source_id']
    run = client.post('/api/supplier-offers/sources/'+source+'/extract').json()
    offer = dict(offer_body(source,'S-1',11,3),extraction_run_id=run['id'],extraction_candidate=0,
                 quote_date='2026-01-01',valid_until='2026-12-31',supplement_basis='confirmed by source')
    implicit = client.post('/api/supplier-offers',json=offer)
    assert implicit.status_code == 409 and '运费范围' in implicit.text
    assert client.post('/api/supplier-offers',json={**offer,'shipping_scope':'line'}).status_code == 200


def test_collision_releases_writer_lock(local):
    _,path = local
    with open_db(path) as db:
        first = email('same-message')
        ingest_eml(db,first.as_bytes(),'first.eml')
        first.set_content('Part Number: OTHER\nQuantity: 2\nUnit: EA')
        with pytest.raises(ValueError,match='冲突'):
            ingest_eml(db,first.as_bytes(),'changed.eml')
        assert not db.in_transaction


def test_html_only_short_row_and_corrupted_attachments(local):
    client,_=local
    for filename,payload,status in [('zero.eml',b'',422),('bad.csv',b'pn,qty\nP,1',415),
                                    ('fake.eml',b'random bytes',422),('large.eml',b'X'*(10*1024*1024+1),413)]:
        r=client.post('/api/emails/preview',files={'file':(filename,payload)})
        assert r.status_code==status,(filename,r.status_code)
    msg=email('broken-attachment')
    msg.add_attachment(b'not a pdf', maintype='application',subtype='pdf',filename='damaged.pdf')
    r=client.post('/api/emails/import',files={'file':('mixed.eml',msg.as_bytes())})
    assert r.status_code==200 and r.json()['status']=='needs_review' and r.json()['parsed_count']==1


@pytest.mark.parametrize('count',[1,99,100,101,122,299,300,301,342])
def test_batch_boundaries_preserve_order_and_refuse_partial_results(local,count):
    client,path = local
    msg=email(f'batch-{count}')
    msg.set_content('See attached.')
    original=workbook([['Part Number','Qty','Unit','Condition','RFQ No']]+
                      [[f'QA-{i:04d}',1+(i%9),'EA','FN','QA-BATCH'] for i in range(count)])
    msg.add_attachment(original,maintype='application',subtype='octet-stream',filename='inquiry.xlsx')
    incoming=client.post('/api/emails/import',files={'file':('batch.eml',msg.as_bytes())})
    assert incoming.status_code==200 and incoming.json()['new_lines']==count
    rows=client.get('/api/lines',params={'email_id':msg['Message-ID'],'limit':1000}).json()['rows']
    assert [r['part_number'] for r in rows]==[f'QA-{i:04d}' for i in range(count)]
    ids=[r['id'] for r in reversed(rows)]
    res=client.post('/api/quote',json={'line_ids':ids})
    if count>300:
        assert res.status_code==422
        with open_db(path) as con:
            assert not con.execute('SELECT 1 FROM quotes').fetchone()
    else:
        assert res.status_code==200
        assert [line['line_id'] for line in res.json()['lines']]==ids
        assert res.json()['pending_count']==count and res.json()['total_cny']=='0.00'
