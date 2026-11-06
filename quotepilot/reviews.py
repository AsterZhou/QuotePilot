"""Versioned quote snapshots: exports never recalculate an approved quote."""
import json
from uuid import uuid4
from decimal import Decimal
from .pricing import money,strict_decimal,RULE_VERSION
from .store import audit

def load_quote(con,qid):
    r=con.execute('SELECT * FROM quotes WHERE id=?',(qid,)).fetchone()
    if not r:raise KeyError('报价不存在')
    obj=json.loads(r['report_json']);obj.update(quote_id=qid,version=r['version'],review_status=r['status'])
    return obj

def _save(con,obj,status,version):
    qid=obj['quote_id'];obj.update(version=version,review_status=status)
    con.execute('UPDATE quotes SET status=?,version=?,report_json=? WHERE id=?',(status,version,json.dumps(obj,ensure_ascii=False),qid))
    for line in obj['lines']:
        con.execute('INSERT OR REPLACE INTO quote_items VALUES(?,?,?)',(qid,line['line_id'],json.dumps(line,ensure_ascii=False)))

def create_quote(con,report):
    report=dict(report);report.update(quote_id='QP-'+uuid4().hex[:12].upper(),version=1,review_status='draft')
    with con:
        con.execute('INSERT INTO quotes(id,status,report_json,rule_version) VALUES(?,?,?,?)',(report['quote_id'],'draft',json.dumps(report,ensure_ascii=False),RULE_VERSION))
        _save(con,report,'draft',1);audit(con,'quote_created',report['quote_id'],{'report':report})
    return report

def change_quote(con,qid,version,actor,reason,patches,approve=False,confirm=False):
    # Serializes version check and write, protecting against lost updates.
    con.execute('BEGIN IMMEDIATE')
    try:
        obj=load_quote(con,qid)
        if obj['version']!=version:raise ValueError('版本冲突，请重新打开报价后操作')
        if obj['review_status']=='approved':raise ValueError('已确认报价不可修改；请生成新草案')
        byid={x['line_id']:x for x in obj['lines']}
        for patch in patches:
            if patch['line_id'] not in byid:raise ValueError('报价中没有该询价行')
            line=byid[patch['line_id']]
            # Manual sourced price is explicit; retain calculated original values.
            if patch.get('unit_price_cny') is not None:
                if not patch.get('evidence_ref','').strip():raise ValueError('人工价格必须填写可核对的价格凭据')
                price=strict_decimal(patch['unit_price_cny'])
                if price<=0:raise ValueError('人工价格必须为正数')
                line.setdefault('original_calculation',dict(line))
                line.update(unit_quote_cny=money(price),line_total_cny=money(Decimal(money(price))*Decimal(str(line['quantity']))),price_ref='人工凭据: '+patch['evidence_ref'],status='可报价（待人工审批）',decision_state='待人工确认')
                line['audit'].append(f'人工调整 / {actor} / {reason} / {patch["evidence_ref"]}')
            if patch.get('condition') is not None:
                condition=patch['condition'].strip().upper()
                source=line.get('price_basis',{}).get('record',{})
                priced_condition=source.get('condition') or source.get('part_condition')
                if priced_condition and condition!=priced_condition.upper() and patch.get('unit_price_cny') is None:
                    raise ValueError('修改件状与价格来源不符；请重新核价或提供对应件状的人工价格凭据')
                line['condition']=condition
            if patch.get('lead_days') is not None:line['lead_days']=patch['lead_days']
        obj['total_cny']=money(sum((strict_decimal(x['line_total_cny']) for x in obj['lines'] if x['line_total_cny']),Decimal(0)))
        obj['quoted_count']=sum(bool(x['unit_quote_cny']) for x in obj['lines']);obj['pending_count']=len(obj['lines'])-obj['quoted_count']
        if approve:
            if obj.get('approval_blockers'):raise ValueError('；'.join(obj['approval_blockers']))
            if not confirm:raise ValueError('必须明确确认单位、件状、证书、交期、税费和来源')
            if obj['pending_count']:raise ValueError('仍有待核价行；请补全价格或新建仅含可报价行的草案')
            if any(not x['condition'] for x in obj['lines']):raise ValueError('需求件状未确认，请填写后再审批')
            obj['review_required']=False;obj['approved_by']=actor;obj['approval_reason']=reason
            for line in obj['lines']:line['decision_state']='已人工确认';line['status']='已人工确认'
        _save(con,obj,'approved' if approve else 'draft',version+1)
        audit(con,'quote_approved' if approve else 'quote_edited',qid,{'reason':reason,'before_version':version,'patches':patches,'confirmed_constraints':confirm,'after':obj},actor)
        con.commit();return obj
    except Exception:
        con.rollback();raise
