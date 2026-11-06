"""Post-freeze regression cases. Unsupported formats stay failed in the independent probe."""
from pathlib import Path
import json,hashlib
import pytest
from quotepilot.parsing import parse_eml
ROOT=Path(__file__).parent/'acceptance_fixtures'
CASES=json.loads((ROOT/'manifest.json').read_text())
SUPPORTED=[x for x in CASES if not x['name'].startswith(('11_','14_','18_'))]

@pytest.mark.parametrize('case',SUPPORTED,ids=[x['name'] for x in SUPPORTED])
def test_post_freeze_case(case):
    raw=(ROOT/case['name']).read_bytes()
    assert hashlib.sha256(raw).hexdigest()==case['sha256']
    parsed=parse_eml(raw,case['name'])
    assert [[x['part_number'],x['quantity'],x['unit']] for x in parsed['lines']]==case['expected']
    if case['must_report_issue']:assert parsed['parse_notes']
