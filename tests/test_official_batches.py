"""Exercise bounded import, evidence, and retry against the unmodified release samples."""
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook
import pytest

import server
from quotepilot.store import open_db, seed_official
from quotepilot.supplier_extraction import extract


@pytest.fixture
def official(tmp_path, monkeypatch):
    path = tmp_path / 'isolated.db'
    monkeypatch.setattr(server, 'DB', path)
    monkeypatch.setenv('QUOTEPILOT_RELEASE_DEMO', '1')
    monkeypatch.setenv('QUOTEPILOT_ENV', 'development')
    with open_db(path) as db:
        seed_official(db, server.SAMPLES)
    with TestClient(server.app) as client:
        yield client, path


def test_original_mail_batches_share_inventory_and_preserve_rfq(official):
    client, path = official
    mail = next(server.SAMPLES.rglob('*20260901*.eml'))
    imported = client.post('/api/emails/import', files={'file':(mail.name, mail.read_bytes())}).json()
    assert imported['new_lines'] == 0 and imported['duplicate_lines'] == 122
    lines = client.get('/api/lines',params={'email_id':imported['email_id']}).json()['rows']
    ids = [line['id'] for line in lines]
    body = {'line_ids':ids, 'asof':'2026-11-13'}
    result = client.post('/api/quote', json=body).json()
    assert [b['count'] for b in result['batches']] == [100,22]
    assert [(l['line_id'],l['source_rfq_no'],l['source_ref']) for l in result['lines']] == [
        (l['id'],l['source_rfq_no'],l['source_ref']) for l in lines]
    assert result['approval_blockers']
    from quotepilot.pricing import batch_quote
    feed = [dict(part_number=l['part_number'],quantity=l['quantity'],unit=l['unit'],condition=l['part_condition']) for l in lines]
    with open_db(path) as db:
        unsplit = batch_quote(db,feed,asof=body['asof'])
        count = db.execute('SELECT count(*) FROM quotes').fetchone()[0]
    assert [l['line_total_cny'] for l in result['lines']] == [l['line_total_cny'] for l in unsplit['lines']]
    failure = client.post('/api/quote',json={**body,'line_ids':ids+[999999]})
    assert failure.status_code == 404 and '第2批' in failure.text
    with open_db(path) as db:
        assert db.execute('SELECT count(*) FROM quotes').fetchone()[0] == count


def test_official_supplier_resource_resumable_pages_and_evidence(official):
    client,path = official
    workbook = next(server.SAMPLES.glob('价格资源*.xlsx'))
    source = client.post('/api/supplier-offers/sources',files={'file':(workbook.name,workbook.read_bytes())}).json()
    sid = source['source_id']
    catalog = client.get('/api/catalog/prices').json()['source_files'][0]
    assert client.post('/api/catalog/prices/'+catalog['id']+'/review').json()['source_id'] == sid
    with open_db(path) as db:
        db.execute("""CREATE TRIGGER fail_second BEFORE INSERT ON supplier_candidate_pages
                      WHEN NEW.page=1 BEGIN SELECT RAISE(ABORT,'test interruption'); END""")
        with pytest.raises(ValueError,match="第2批失败"):
            extract(db,sid)
        assert db.execute('SELECT count(*) FROM supplier_candidate_pages').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM supplier_extraction_runs').fetchone()[0] == 0
        db.execute('DROP TRIGGER fail_second')

    def resume(_):
        db = open_db(path)
        try:return extract(db,sid)['id']
        finally:db.close()
    with ThreadPoolExecutor(max_workers=2) as pool:
        run_ids=list(pool.map(resume,range(2)))
    assert run_ids[0] == run_ids[1]
    pages = [client.get(f'/api/supplier-extractions/{run_ids[0]}/pages/{i}').json() for i in range(4)]
    assert [len(p['candidates']) for p in pages] == [100,100,100,42]
    candidates = [c for p in pages for c in p['candidates']]
    assert [c['index'] for c in candidates] == list(range(342))
    assert candidates[-1]['field_evidence']['supplier_code']['cell'] == 'C343'
    assert {'unit','specification','tax_rate','shipping_total'} <= set(candidates[0]['missing_fields'])
    assert client.get('/api/supplier-offers').json()['rows'] == []
    with open_db(path) as db:
        assert db.execute('SELECT count(*) FROM supplier_candidate_pages').fetchone()[0] == 4


def test_missing_dimensions_and_formula_evidence():
    from quotepilot.supplier_extraction import xlsx_records
    workbook=Workbook(write_only=True)
    sheet=workbook.create_sheet()
    sheet.append(['Part Number','单价'])
    sheet.append(['TEST-A','=40+2'])
    buf=BytesIO()
    workbook.save(buf)
    values,notes=xlsx_records(buf.getvalue(),'sample.xlsx')
    assert values[0][0]=={'part_number':'TEST-A'}
    assert notes and values[0][1]['unit_price']['raw_text']=='=40+2'
