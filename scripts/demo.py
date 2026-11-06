"""Creates a fresh reproducible official-data quotation and retains evidence."""
from pathlib import Path
import sys,tempfile,json,csv,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quotepilot.store import open_db,ingest_eml,seed_official
from quotepilot.reviews import create_quote,change_quote,load_quote
from quotepilot.exports import quote_csv,quote_xlsx,audit_json
from server import make_quote,QuoteRequest
root=Path(__file__).resolve().parents[1];out=root/'evidence/demo';out.mkdir(parents=True,exist_ok=True)
with tempfile.TemporaryDirectory() as d:
    con=open_db(Path(d)/'demo.db')
    sample=next((root/'workspace/samples/1').glob('航空询价*.eml'))
    raw=sample.read_bytes();parsed=ingest_eml(con,raw,sample.name,dataset='official_sample')
    stats=seed_official(con,root/'workspace/samples')
    line=con.execute("SELECT id FROM rfq_lines WHERE part_number='PN-0001' AND quantity=8 AND unit='EA' AND part_condition='FN' LIMIT 1").fetchone()[0]
    r=create_quote(con,make_quote(con,QuoteRequest(line_ids=[line],asof='2026-09-20',rate=20)))
    r=change_quote(con,r['quote_id'],1,'AUTOMATED_DEMO_ONLY','自动测试确认，供复现使用；不代表真实业务审批',[],True,True)
    saved=load_quote(con,r['quote_id']);assert saved['total_cny']=='133.04'
    (out/'quotation.csv').write_bytes(quote_csv(saved));(out/'quotation.xlsx').write_bytes(quote_xlsx(saved));(out/'quote_snapshot.json').write_bytes(audit_json(saved))
    summary={'dataset':'official_sample (organizer simulated data, not real customers)','first_import_lines':len(parsed['lines']),'stats':stats,'quote_id':saved['quote_id'],'rule_version':saved['rule_version'],'unit_cny':saved['lines'][0]['unit_quote_cny'],'total_cny':saved['total_cny'],'source_sha256':hashlib.sha256(raw).hexdigest(),'review_actor':'AUTOMATED_DEMO_ONLY'}
    (out/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(summary,ensure_ascii=False,indent=2));con.close()
