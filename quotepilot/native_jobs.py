"""Durable dispatch of a stored RFQ to the published MOI one-shot definition."""
import base64
import hashlib
import json
import os
import httpx
import re
from uuid import uuid4

from . import extraction_workflow as extraction
from .moi_sql import MOISQLClient
from .native_workflow import MOIWorkflowClient
from .providers import Extraction
from .store import audit

TABLE = 'quotepilot.rfq_workflow_runs_v1'
NODES = ('load_rfq', 'extract_rfq', 'persist_suggestions', 'read_back')
SUCCESS = {'completed', 'success', 'succeeded'}
FAILED = {'failed', 'canceled', 'cancelled'}
SCHEMA = """CREATE TABLE IF NOT EXISTS native_rfq_jobs(
    ref TEXT PRIMARY KEY, workspace TEXT NOT NULL, workflow TEXT NOT NULL,
    email_id TEXT NOT NULL REFERENCES emails(email_id), digest TEXT NOT NULL,
    phase TEXT NOT NULL, eid TEXT, review_id TEXT, receipt TEXT NOT NULL DEFAULT '{}',
    error TEXT NOT NULL DEFAULT '', UNIQUE(workspace,workflow,email_id,digest),
    UNIQUE(workspace,workflow,eid))"""


def clients():
    if os.getenv('QUOTEPILOT_NATIVE_RFQ') != '1' or not os.getenv('MOI_WORKFLOW_ID'):
        raise ValueError('独立环境尚未启用 MOI 原生询价')
    return MOIWorkflowClient(), MOISQLClient(), os.environ['MOI_WORKFLOW_ID']


def view(row):
    return {'ref': row['ref'], 'workflow_id': row['workflow'], 'execution_id': row['eid'],
            'phase': row['phase'], 'review_id': row['review_id'], 'input_sha256': row['digest'],
            'receipt': json.loads(row['receipt']), 'error': row['error']}


def read(con, ref, client, wid):
    con.execute(SCHEMA)
    row = con.execute('SELECT * FROM native_rfq_jobs WHERE ref=? AND workspace=? AND workflow=?',
                      (ref, client.workspace, wid)).fetchone()
    if not row:
        raise KeyError('此工作区未找到对应作业')
    return row


def history(con, email_id, client, wid):
    con.execute(SCHEMA)
    return [view(r) for r in con.execute(
        'SELECT * FROM native_rfq_jobs WHERE email_id=? AND workspace=? AND workflow=? ORDER BY rowid DESC',
        (email_id, client.workspace, wid))]


def cells(sql, query, count):
    reply = sql.execute(query)
    rows = reply['data'].get('result', [])
    if len(rows) != 1 or len(rows[0]) != count or not all(c.get('Valid') for c in rows[0]):
        raise ValueError('MatrixOne 读回缺行、空值或列数不匹配')
    return [c['String'] for c in rows[0]], reply['query_id']


def stage(sql, ref, digest, text):
    # ref/digest and base64 data are exclusively server-generated.
    encoded = base64.b64encode(text.encode()).decode()
    sql.execute(f"INSERT IGNORE INTO {TABLE} (run_ref,input_sha256,input_base64,review_status) "
                f"VALUES ('{ref}','{digest}','{encoded}','pending')")
    values, qid = cells(sql, f"SELECT input_sha256,input_base64 FROM {TABLE} WHERE run_ref='{ref}'", 2)
    if values != [digest, encoded]:
        raise ValueError('原生工作流输入的哈希或字节与原件不同')
    return qid


def start(con, email_id, client, sql, wid):
    text, _, _ = extraction.source_context(con, email_id)
    digest = hashlib.sha256(text.encode()).hexdigest()
    con.execute(SCHEMA)
    ref = 'QN-' + uuid4().hex
    with con:
        con.execute('BEGIN IMMEDIATE')
        row = con.execute('SELECT * FROM native_rfq_jobs WHERE workspace=? AND workflow=? AND email_id=? AND digest=?',
                          (client.workspace, wid, email_id, digest)).fetchone()
        if row:
            if row['phase'] not in {'preparing', 'preflight_failed'}:
                return view(row)
            ref = row['ref']
            con.execute("UPDATE native_rfq_jobs SET phase='preparing',error='' WHERE ref=?", (ref,))
        else:
            con.execute("INSERT INTO native_rfq_jobs(ref,workspace,workflow,email_id,digest,phase) "
                        "VALUES (?,?,?,?,?,'preparing')", (ref, client.workspace, wid, email_id, digest))
        audit(con, 'native_rfq_preparing', ref, {'email_id': email_id, 'input_sha256': digest})
    phase = 'preflight_failed'
    try:
        payload = client.prepare(wid, ref)
        qid = stage(sql, ref, digest, text)
        with con:
            claimed = con.execute("UPDATE native_rfq_jobs SET phase='dispatching',receipt=? "
                                  "WHERE ref=? AND phase IN ('preparing','preflight_failed')",
                                  (json.dumps({'stage_query_id': qid}), ref)).rowcount
            if not claimed:
                return view(read(con, ref, client, wid))
        phase = 'dispatch_unknown'
        run = client.submit(wid, payload)['workflow_run']
        with con:
            con.execute("UPDATE native_rfq_jobs SET phase='submitted',eid=? WHERE ref=?",
                        (run['execution_id'], ref))
            audit(con, 'native_rfq_submitted', ref, {'execution_id': run['execution_id']})
    except Exception as error:
        # A dispatch may already exist even if MOI returned HTTP 400 or a timeout.
        message = safe_error(error)
        with con:
            expected = 'preparing' if phase == 'preflight_failed' else 'dispatching'
            updated = con.execute('UPDATE native_rfq_jobs SET phase=?,error=? WHERE ref=? AND phase=? AND eid IS NULL',
                                  (phase, message, ref, expected)).rowcount
            if updated:
                audit(con, 'native_rfq_blocked', ref, {'phase': phase, 'error': message})
    return view(read(con, ref, client, wid))


def safe_error(error):
    if isinstance(error, ValueError) and type(error) is ValueError:
        return str(error)[:300]
    return '处理未完成，错误类型 ' + type(error).__name__


def bind_execution(con, ref, eid, client, wid):
    """Recover a lost submit response only from an exact platform variable match."""
    row = read(con, ref, client, wid)
    if row['eid'] == eid:
        return view(row)
    if row['phase'] not in {'dispatching', 'dispatch_unknown'} or row['eid']:
        raise ValueError('此作业无需关联执行 ID')
    detail = client.execution(wid, eid)
    if (detail.get('vars_payload') or {}).get('run_ref') != ref:
        raise ValueError('平台作业的运行变量与此询价不匹配')
    with con:
        changed = con.execute("UPDATE native_rfq_jobs SET eid=?,phase='submitted',error='' "
                              "WHERE ref=? AND eid IS NULL", (eid, ref)).rowcount
        if changed:
            audit(con, 'native_execution_reconciled', ref, {'execution_id': eid})
    return view(read(con, ref, client, wid))


def verify_output(row, nodes, sql, text):
    ref = row['ref']
    if not re.fullmatch('QN-[a-f0-9]{32}', ref):
        raise ValueError('作业引用损坏')
    values, qid = cells(sql, f"SELECT input_sha256,model_text_base64,review_status FROM {TABLE} "
                        f"WHERE run_ref='{ref}'", 3)
    digest, encoded, status = values
    if digest != row['digest'] or hashlib.sha256(text.encode()).hexdigest() != digest or status != 'pending':
        raise ValueError('输入哈希或数据库复核状态不一致')
    model = nodes['extract_rfq']['runtime_output']
    raw = base64.b64decode(encoded, validate=True).decode()
    if model.get('text') != raw:
        raise ValueError('模型节点输出与数据库读回不一致')
    back = nodes['read_back']['runtime_output'].get('rows', [])
    if len(back) != 1 or any(back[0].get(k) != v for k, v in
        {'run_ref': ref, 'input_sha256': digest, 'review_status': status, 'model_text_base64': encoded}.items()):
        raise ValueError('原生 SQL 节点读回与独立查询不一致')
    source_rows = nodes['load_rfq']['runtime_output'].get('rows')
    expected_source = base64.b64encode(text.encode()).decode()
    # Earlier workflow versions selected decoded text; the current version reads exact base64 bytes.
    if source_rows not in ([{'input_base64': expected_source}], [{'rfq_text': text}]):
        raise ValueError('原生输入节点与上传内容不一致')
    model_input = nodes['extract_rfq'].get('runtime_input') or {}
    if model_input.get('text') != text:
        raise ValueError('原生模型实际收到的文本与上传内容不一致')
    if nodes['persist_suggestions']['runtime_output'].get('affected_rows') != 1:
        raise ValueError('原生写入节点未确认唯一一行')
    parsed = Extraction.model_validate_json(raw)
    if not parsed.lines or any(not line.evidence.strip() or line.evidence not in text for line in parsed.lines):
        raise ValueError('模型未返回可复核行，或引用证据与来源不符')
    return {'provider': 'moi_native', 'simulated': False, 'review_required': True,
            'execution_id': row['eid'], 'model': model.get('model'), 'usage': model.get('usage'),
            'workflow_id': row['workflow'], 'lines': parsed.model_dump()['lines']}, qid


def refresh(con, ref, client, sql, wid):
    row = read(con, ref, client, wid)
    eid = row['eid']
    if not eid or row['phase'] in {'review_ready', 'failed'}:
        return view(row)
    detail = client.execution(wid, eid)
    status = detail['status'].lower()
    receipt = json.loads(row['receipt'])
    receipt['platform_status'] = status
    receipt['task_id'] = detail.get('moi_task_id')
    receipt['workflow_version_id'] = detail.get('moi_workflow_version_id')
    phase = 'tracking'
    message = ''
    candidate = None
    # During an active/failed run MOI may have no record for a later node yet.
    if status not in SUCCESS:
        receipt['nodes'] = {}
        for key in NODES:
            try:
                node = client.node(wid, eid, key)
                receipt['nodes'][key] = {'status': node['status'], 'duration_ms': node.get('duration_ms')}
            except (ValueError, KeyError, OSError, httpx.RequestError) as error:
                receipt['nodes'][key] = {'status': '未取得记录', 'detail': safe_error(error)}
    if status in FAILED:
        phase = 'failed'
        failed_nodes = [key for key, n in receipt['nodes'].items() if n['status'].lower() in FAILED]
        message = 'MOI 返回 ' + status + '。失败节点：' + ('、'.join(failed_nodes) or '平台暂无节点明细')
    elif status in SUCCESS:
        try:
            result = client.result(wid, eid)['result']
            if result['status'].lower() not in SUCCESS:
                raise ValueError('平台作业详情与结果终态尚不一致')
            nodes = {key: client.node(wid, eid, key) for key in NODES}
            receipt['nodes'] = {key: {'status': node['status'], 'duration_ms': node.get('duration_ms')}
                                for key, node in nodes.items()}
            if not all(n['status'].lower() in SUCCESS for n in nodes.values()):
                raise ValueError('原生节点尚未全部成功')
            text, sources, notes = extraction.source_context(con, row['email_id'])
            candidate, receipt['readback_query_id'] = verify_output(row, nodes, sql, text)
            receipt['model_output_sha256'] = hashlib.sha256(nodes['extract_rfq']['runtime_output']['text'].encode()).hexdigest()
            receipt['write_affected_rows'] = 1
            receipt['readback_matched'] = True
            phase = 'review_ready'
        except Exception as error:
            phase, message = 'verification_pending', safe_error(error)
    extraction.ensure_schema(con)
    with con:
        con.execute('BEGIN IMMEDIATE')
        current = read(con, ref, client, wid)
        if current['phase'] in {'review_ready', 'failed'}:
            return view(current)
        rid = None
        if candidate:
            rid = extraction.record_suggestions(con, row['email_id'], candidate, text, sources, notes)['run_id']
        con.execute('UPDATE native_rfq_jobs SET phase=?,receipt=?,review_id=?,error=? WHERE ref=?',
                    (phase, json.dumps(receipt), rid, message, ref))
        if current['phase'] != phase or current['error'] != message:
            audit(con, 'native_rfq_progress', ref, {'phase': phase, 'eid': eid, 'receipt': receipt, 'review': rid})
    return view(read(con, ref, client, wid))
