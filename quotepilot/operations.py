"""Metrics from saved receipts only; never claim complete billing, accuracy or tenant isolation."""
import json
from .provenance import verify_audit,stamp

MIGRATIONS=((1,'existing SQLite core adopted'),(2,'field evidence and audit chain'),(3,'immutable RFQ versions and matches'),(4,'commercial costs, offers and approval'),(5,'recorded operations metrics and schema tracking'))

def install(con):
    con.execute('CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,description TEXT NOT NULL,recorded_at TEXT NOT NULL)')
    for version,description in MIGRATIONS:con.execute('INSERT OR IGNORE INTO schema_migrations VALUES(?,?,?)',(version,description,stamp()))
    for sql in ['CREATE INDEX IF NOT EXISTS idx_offer_reviews_offer ON offer_reviews(offer_id)','CREATE INDEX IF NOT EXISTS idx_commercial_items_line ON commercial_quote_items(line_id)','CREATE INDEX IF NOT EXISTS idx_rfq_versions_series ON rfq_versions(series_id,version)','CREATE INDEX IF NOT EXISTS idx_field_revisions_line ON field_revisions(line_id,id)']:con.execute(sql)
    for r in con.execute('SELECT * FROM supplier_offers WHERE id NOT IN (SELECT offer_id FROM supplier_offer_catalog)').fetchall():
        p=json.loads(r['payload_json']);keys=('supplier','part_number','specification','unit','condition','unit_price','currency','fx_to_cny','moq','lead_days','quote_date','valid_until','source_id')
        con.execute('INSERT INTO supplier_offer_catalog VALUES('+','.join('?' for _ in range(14))+')',[r['id']]+[str(p[k]) if k not in ('moq','lead_days') else p[k] for k in keys])
    for r in con.execute('SELECT * FROM commercial_quotes WHERE id NOT IN (SELECT quote_id FROM commercial_quote_items)').fetchall():
        for line in json.loads(r['payload_json'])['lines']:
            selected=line.get('selected');calc=selected['calculation'] if selected else {}
            con.execute('INSERT OR IGNORE INTO commercial_quote_items VALUES(?,?,?,?,?,?,?)',(r['id'],line['line_id'],selected['offer_id'] if selected else None,line['quantity'],calc.get('suggested_unit_price_cny'),calc.get('suggested_total_cny'),line['field_review_version']))
    con.commit()

def metrics(con):
    tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    receipts={};invalid=0;statuses={};durations=[];timed_ids=set();extractions=0;confirmed=0;scanned={}
    def add(rid,usage,source):
        if not isinstance(rid,str) or not rid or rid.lower().startswith(('test','contract','mock')):return
        count=usage.get('total_tokens') if isinstance(usage,dict) else None
        receipts.setdefault(rid,{'response_id':rid,'total_tokens':count if type(count) is int and count>=0 else None,'source':source})
        if receipts[rid]['total_tokens'] is None and type(count) is int and count>=0:receipts[rid]['total_tokens']=count
    if 'query_turns' in tables:
        scanned['query_turns']=con.execute('SELECT COUNT(*) FROM query_turns').fetchone()[0]
        for row in con.execute('SELECT id,result_json FROM query_turns ORDER BY rowid DESC LIMIT 10000'):
            try:
                r=json.loads(row['result_json'])
                if not isinstance(r,dict):raise ValueError()
            except (ValueError,TypeError):invalid+=1;continue
            status=r.get('status','unknown');statuses[status]=statuses.get(status,0)+1
            add(r.get('response_id'),r.get('usage'),'query_plan')
            analysis = r.get('analysis', {})
            if isinstance(analysis, dict):
                add(analysis.get('response_id'),r.get('analysis_usage'),'query_analysis')
            else:
                invalid += 1
            attempts = r.get('validation_attempts', [])
            if isinstance(attempts, list) and all(isinstance(a, dict) for a in attempts):
                for attempt in attempts:
                    add(attempt.get('response_id'),attempt.get('usage'),'sql_repair_original')
            else:
                invalid += 1
            add(r.get('repair_response_id'),r.get('repair_usage'),'sql_repair')
            add(r.get('public_extraction_response_id'),None,'public_extraction_usage_unrecorded')
            timing_id=r.get('response_id') or row['id']
            if timing_id not in timed_ids and isinstance(r.get('elapsed_seconds'),(int,float)) and r['elapsed_seconds']>=0:
                durations.append(r['elapsed_seconds']);timed_ids.add(timing_id)
    for row in con.execute("SELECT detail_json FROM audit_events WHERE action='analytics_genesis_query' ORDER BY id DESC LIMIT 10000"):
        try:
            receipt = json.loads(row[0])
            if not isinstance(receipt, dict):
                raise ValueError()
        except (ValueError, TypeError):
            invalid += 1
            continue
        add(receipt.get('response_id'), receipt.get('usage'), 'business_analytics')
    if 'extraction_runs' in tables:
        scanned['extraction_runs']=con.execute('SELECT COUNT(*) FROM extraction_runs').fetchone()[0]
        for row in con.execute('SELECT result_json,status FROM extraction_runs ORDER BY rowid DESC LIMIT 10000'):
            extractions+=1;confirmed+=int(row['status']=='confirmed')
            try:r=json.loads(row['result_json'])
            except (ValueError,TypeError):invalid+=1;continue
            if not isinstance(r,dict):invalid+=1;continue
            if not r.get('simulated'):add(r.get('response_id'),r.get('usage'),'extraction')
    reviews={r['status']:r['n'] for r in con.execute('SELECT status,COUNT(*) AS n FROM line_review_state GROUP BY status')}
    datasets={}
    for row in con.execute("SELECT detail_json FROM audit_events WHERE action='import'"):
        try:p=json.loads(row[0])
        except (ValueError,TypeError):invalid+=1;continue
        if not isinstance(p,dict):invalid+=1;continue
        d=datasets.setdefault(p.get('dataset','unknown'),{'imports':0,'with_extracted_rows':0,'with_notes':0})
        d['imports']+=1;d['with_extracted_rows']+=int(p.get('lines',0)>0);d['with_notes']+=int(bool(p.get('notes')))
    count=con.execute('SELECT COUNT(*) FROM rfq_lines').fetchone()[0];values=list(receipts.values())
    return {'receipts':values,'recorded_model_call_count':len(values),'known_total_tokens':sum(x['total_tokens'] or 0 for x in values),'unknown_usage_receipts':sum(x['total_tokens'] is None for x in values),
      'billing_cost':None,'cost_note':'缺少实际模型单价和账单，未推算每份RFQ费用或商业ROI；记录不是完整计费账单',
      'query_status_counts':statuses,'query_failure_count':sum(statuses.get(s,0) for s in ('failed','rejected')),'timed_query_count':len(durations),'average_recorded_query_seconds':round(sum(durations)/len(durations),3) if durations else None,
      'extraction_runs':extractions,'confirmed_extraction_runs':confirmed,'line_review_counts':reviews,'rfq_line_count':count,'confirmed_line_fraction':reviews.get('confirmed',0)/count if count else None,'untracked_legacy_lines':count-sum(reviews.values()),
      'changed_field_revisions':con.execute('SELECT COUNT(*) FROM field_revisions WHERE before_json!=after_json').fetchone()[0],'parse_imports_by_dataset':datasets,
      'recorded_quote_calculation_failures':con.execute("SELECT COUNT(*) FROM audit_events WHERE action='commercial_quote_calculation_failed'").fetchone()[0],'invalid_json_records':invalid,'scan_scope':scanned,'receipt_scope_limit':10000,
      'scope_note':'查询、业务分析回执和提取各最多最近10000条，响应ID去重；合成与官方示例不代表客户业务效果。没有准确率指标。'}

def health(con):
    return {'database':'SQLite','integrity':con.execute('PRAGMA quick_check').fetchone()[0],'audit':verify_audit(con),'schema_migrations':[dict(r) for r in con.execute('SELECT * FROM schema_migrations ORDER BY version')],
      'source_files':con.execute('SELECT COUNT(*) FROM source_files').fetchone()[0],'source_bytes':con.execute('SELECT COALESCE(SUM(length(content)),0) FROM source_files').fetchone()[0],
      'tenant_isolation_tested':False,'identity_scope':'两个共享角色账户，不是多租户或企业SSO','external_services_checked':False,'note':'本接口不调用外部服务，不表示Genesis、MOI或搜索在线'}
