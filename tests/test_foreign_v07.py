"""Frozen synthetic corpus generated after parser work; no real customer claims."""
import json,hashlib
from pathlib import Path
import pytest
from quotepilot.parsing import parse_eml
ROOT=Path(__file__).parent/'foreign_v07'
CASES=json.loads((ROOT/'manifest.json').read_text())['cases']
@pytest.mark.parametrize('case',CASES,ids=[c['name'] for c in CASES])
def test_new_unfamiliar_files(case):
 raw=(ROOT/case['name']).read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256']
 try:
  r=parse_eml(raw,case['name']);actual=[[x['part_number'],x['quantity'],x['unit'],x['source_rfq_no']] for x in r['lines']];notes=r['parse_notes']
 except ValueError as e:actual=[];notes=[str(e)]
 assert actual==case['expected']
 if case['must_report_issue']:assert notes
 if case['name']=='01_multi_business.eml':assert len(set(x['source'] for x in r['lines']))==2
