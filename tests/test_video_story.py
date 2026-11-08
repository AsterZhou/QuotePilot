"""Media claim/continuity checks, not a substitute for actual video decoding."""
import json
from pathlib import Path

def test_storyboard_is_exactly_three_minutes_without_gaps():
    scenes=json.loads(Path('media/storyboard.json').read_text())['scenes'];clock=0
    for scene in scenes:
        assert scene['start']==clock and scene['duration']>0 and scene['narration']
        clock+=scene['duration']
    assert clock==180 and len({s['id'] for s in scenes})==len(scenes)

def test_platform_claims_match_saved_real_receipts():
    live=json.loads(Path('evidence/sprint-p0/live.json').read_text());story=json.loads(Path('media/storyboard.json').read_text())
    assert live['genesis']['verified'] and live['genesis']['usage']['total_tokens']==1083
    assert live['commercial_mirror']['verified'] and not live['commercial_mirror']['native_workflow_execution']
    assert live['native_execution_id'] is None and not live['native_execution_verified']
    platform=next(s for s in story['scenes'] if s['id']=='platform')
    assert '尚未运行' in ''.join(platform['bullets']) and '400' in ''.join(platform['bullets'])

def test_preview_is_not_advertised_as_a_deployed_public_site():
    result=json.loads(Path('evidence/sprint-p1/result.json').read_text())
    assert not result['public_acceptance'] and not result['persistent_hosting_deployed'] and not result.get('url')
    assert '合成' in json.loads(Path('media/storyboard.json').read_text())['case']
