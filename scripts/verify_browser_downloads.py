"""Read actual browser downloads back; match recorded hashes and approved total."""
from pathlib import Path
from io import BytesIO
import json,hashlib
import pymupdf
from openpyxl import load_workbook
root=Path('evidence/independent/browser');run=json.loads((root/'result.json').read_text())
assert run['passed']
expected=next(s['total'] for s in run['steps'] if s['name']=='approved_snapshot_unchanged');results={}
for kind in ('pdf','xlsx'):
    raw=(root/f'approved.{kind}').read_bytes();digest=hashlib.sha256(raw).hexdigest()
    assert digest==next(s['sha256'] for s in run['steps'] if s['name']=='download' and s['format']==kind)
    if kind=='pdf':
        with pymupdf.open(stream=raw,filetype='pdf') as doc:
            text=''.join(p.get_text() for p in doc);assert expected in text and 'PN-0001' in text
    else:
        book=load_workbook(BytesIO(raw),data_only=False)
        try:assert any(c.value==expected for row in book.active for c in row)
        finally:book.close()
    results[kind]={'sha256':digest,'amount_readback_verified':True,'expected_total_cny':expected}
(root/'download-readback.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results))
