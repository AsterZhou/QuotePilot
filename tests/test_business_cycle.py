"""One isolated customer version change impacts an already approved quote."""
from scripts.business_cycle import run_cycle


def test_synthetic_full_cycle_preserves_approved_snapshot_and_restores_backup():
    report=run_cycle()
    assert report['synthetic_only'] and not report['public_acceptance']
    assert report['http_checks']==36
    assert all(c['status']==c['expected_status'] for c in report['calls'])
    assert report['quantity_change']=={'before':100,'after':500}
    assert report['approved_snapshot_quantity']==100
    assert report['backup_restore_verified'] and report['audit_valid']
    assert report['exports']['readback_verified'] and report['synthetic_rfq_lines']==2
    assert report['external_model_calls']==0 and not report['native_platform_verified']
