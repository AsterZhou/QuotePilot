import json
import pytest
from quotepilot.store import open_db,audit
from quotepilot.operations import metrics,health
from quotepilot.query_center import session,save

def test_metrics_deduplicate_receipts_and_leave_unknown_cost(tmp_path):
    path=tmp_path/'ops.db';con=open_db(path);con.close();sid,_=session(path,'TEST_OWNER')
    result={'status':'completed','response_id':'SYNTHETIC_RECEIPT_1','usage':{'total_tokens':12},'elapsed_seconds':2.5,'analysis':{'response_id':'SYNTHETIC_ANALYSIS_1'},'analysis_usage':{'total_tokens':8}}
    save(path,sid,'SYNTHETIC QUERY',result);save(path,sid,'SYNTHETIC JOINT COPY',result)
    save(path,sid,'EXPLICIT MOCK',{'status':'failed','response_id':'TEST_ONLY_FAKE','usage':{'total_tokens':999}})
    save(path,sid,'UNKNOWN USAGE',{'status':'failed','response_id':'SYNTHETIC_UNKNOWN_RECEIPT'})
    con=open_db(path);m=metrics(con)
    assert m['recorded_model_call_count']==3 and m['known_total_tokens']==20
    assert m['unknown_usage_receipts']==1 and m['billing_cost'] is None
    assert m['timed_query_count']==1 and m['average_recorded_query_seconds']==2.5
    assert m['query_failure_count']==2
    assert 'accuracy' not in m and 'roi' not in m;con.close()

def test_schema_tracking_is_idempotent_and_not_external_health(tmp_path):
    path=tmp_path/'ops.db'
    for _ in range(3):
        con=open_db(path);h=health(con)
        assert h['integrity']=='ok' and len(h['schema_migrations'])==5
        assert h['audit']['valid'] and not h['tenant_isolation_tested'] and not h['external_services_checked'];con.close()

def test_bad_record_is_counted_not_used_as_success(tmp_path):
    path=tmp_path/'ops.db';con=open_db(path);con.close();sid,_=session(path,'TEST')
    con=open_db(path);con.execute("INSERT INTO query_turns VALUES('invalid',?,'SYNTHETIC','failed','[]','2026-01-01')",(sid,));con.commit()
    assert metrics(con)['invalid_json_records']==1;con.close()

def test_quote_error_records_do_not_claim_accuracy(tmp_path):
    con=open_db(tmp_path/'ops.db')
    audit(con,'commercial_quote_calculation_failed','SYNTHETIC',{'error_type':'ValueError'});con.commit()
    assert metrics(con)['recorded_quote_calculation_failures']==1
    assert metrics(con)['billing_cost'] is None;con.close()
