"""Immutable RFQ snapshots and conservative item matching. No generated supplier prices."""
from collections import Counter
from datetime import date
from email.utils import parseaddr
import hashlib,json
from uuid import uuid4
from .provenance import encoded,stamp

SCHEMA='''
CREATE TABLE IF NOT EXISTS rfq_series(id TEXT PRIMARY KEY,customer_key TEXT NOT NULL,rfq_no TEXT NOT NULL,UNIQUE(customer_key,rfq_no));
CREATE TABLE IF NOT EXISTS rfq_versions(id TEXT PRIMARY KEY,series_id TEXT NOT NULL,version INTEGER NOT NULL,email_id TEXT NOT NULL,
 payload_json TEXT NOT NULL,payload_sha256 TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL,
 UNIQUE(series_id,version),FOREIGN KEY(series_id) REFERENCES rfq_series(id));
CREATE TABLE IF NOT EXISTS rfq_match_decisions(id TEXT PRIMARY KEY,left_id TEXT NOT NULL,right_id TEXT NOT NULL,matches_json TEXT NOT NULL,
 actor TEXT NOT NULL,reason TEXT NOT NULL,created_at TEXT NOT NULL);
'''
TERMS={'delivery_date','delivery_location','payment_terms','special_requirements'}
COMPARE_FIELDS=('part_number','description','quantity','unit','part_condition','deadline','mpn')

def install(con):
    con.executescript(SCHEMA)
    for table in ('rfq_versions','rfq_match_decisions'):
        for operation in ('UPDATE','DELETE'):
            con.execute(f"CREATE TRIGGER IF NOT EXISTS protect_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable RFQ version or match decision'); END")

def load(con,vid):
    row=con.execute('SELECT * FROM rfq_versions WHERE id=?',(vid,)).fetchone()
    if not row:raise KeyError('RFQ版本不存在')
    obj=dict(row);obj['snapshot']=json.loads(obj.pop('payload_json'));return obj

def register(con,email_id,rfq_no,actor,reason,terms=None):
    from .store import audit
    if not actor.strip() or len(reason.strip())<3:raise ValueError('登记人和原因必须填写')
    if set(terms or {})-TERMS:raise ValueError('不支持的RFQ条款')
    email=con.execute('SELECT * FROM emails WHERE email_id=?',(email_id,)).fetchone()
    rows=con.execute('SELECT * FROM rfq_lines WHERE email_id=? AND source_rfq_no=? ORDER BY id',(email_id,rfq_no)).fetchall()
    if not email or not rows:raise ValueError('所选邮件中没有该RFQ明细')
    identity=parseaddr(email['sender'])[1].strip().lower()
    if not identity:raise ValueError('缺少稳定客户邮件标识，请先核对原邮件，不自动合并')
    sources=[dict(r) for r in con.execute("SELECT id,filename,sha256 FROM source_files WHERE email_id=? AND kind='attachment' ORDER BY filename,id",(email_id,))]
    verified_terms={}
    for field,item in (terms or {}).items():
        if not isinstance(item,dict) or set(item)-{'value','source_id','locator','snippet'} or not all(isinstance(item.get(k),str) and item[k].strip() for k in ('value','source_id','locator','snippet')):raise ValueError('条款须保留值、来源文件、人工定位和原文')
        if any(len(v)>4000 for v in item.values()):raise ValueError('条款字段过长')
        source=con.execute('SELECT id,sha256 FROM source_files WHERE id=? AND email_id=?',(item['source_id'],email_id)).fetchone()
        if not source:raise ValueError('条款来源文件不属于所选邮件')
        verified_terms[field]={**item,'sha256':source['sha256'],'method':'human_entered_source_reference','verification':'human_asserted_not_automatically_verified'}
    lines=[]
    for row in rows:
        line=dict(row);evidence=con.execute('SELECT raw_json FROM line_evidence WHERE line_id=?',(row['id'],)).fetchone()
        raw=json.loads(evidence[0]) if evidence else {}
        stable=next((str(raw[k]).strip() for k in ('Item No','Line No','行号','客户行号') if raw.get(k)),None)
        lines.append({**{k:line[k] for k in COMPARE_FIELDS},'line_id':line['id'],'stable_key':stable,'source_ref':line['source_ref']})
    payload={'rfq_no':rfq_no,'customer_key':identity,'email_id':email_id,'lines':lines,'terms':verified_terms,'attachments':sources,
             'data_notice':'数据集标签随源文件保留；本快照不是成交订单'}
    digest=hashlib.sha256(encoded(payload).encode()).hexdigest()
    con.execute('BEGIN IMMEDIATE')
    try:
        series=con.execute('SELECT id FROM rfq_series WHERE customer_key=? AND rfq_no=?',(identity,rfq_no)).fetchone()
        sid=series[0] if series else 'RFQS-'+uuid4().hex[:16]
        if not series:con.execute('INSERT INTO rfq_series VALUES(?,?,?)',(sid,identity,rfq_no))
        previous=con.execute('SELECT id,payload_sha256,version FROM rfq_versions WHERE series_id=? ORDER BY version DESC LIMIT 1',(sid,)).fetchone()
        if previous and previous['payload_sha256']==digest:con.commit();return {**load(con,previous['id']),'idempotent':True}
        vid='RFQV-'+uuid4().hex[:16];version=previous['version']+1 if previous else 1
        con.execute('INSERT INTO rfq_versions VALUES(?,?,?,?,?,?,?,?,?)',(vid,sid,version,email_id,encoded(payload),digest,actor,reason,stamp()))
        audit(con,'rfq_version_registered',vid,{'series_id':sid,'version':version,'source_email':email_id,'sha256':digest},actor)
        con.commit();return {**load(con,vid),'idempotent':False}
    except Exception:con.rollback();raise

def compare_items(left,right,matches=None):
    pairs=[];used_left=set();used_right=set();ambiguous=[]
    for old_id,new_id in (matches or {}).items():
        a=next((i for i,x in enumerate(left) if x['line_id']==int(old_id)),None)
        b=next((j for j,x in enumerate(right) if x['line_id']==int(new_id)),None)
        if a is None or b is None or a in used_left or b in used_right:raise ValueError('人工匹配包含无效或重复行')
        pairs.append((left[a],right[b]));used_left.add(a);used_right.add(b)
    for key in ('stable_key','part_number'):
        lc=Counter(str(x.get(key) or '') for x in left if x.get(key));rc=Counter(str(x.get(key) or '') for x in right if x.get(key))
        for i,a in enumerate(left):
            if i in used_left or not a.get(key):continue
            token=str(a[key])
            candidates=[(j,b) for j,b in enumerate(right) if j not in used_right and str(b.get(key) or '')==token]
            if lc[token]==rc[token]==1 and candidates:
                j,b=candidates[0];pairs.append((a,b));used_left.add(i);used_right.add(j)
    unmatched_left=[(i,x) for i,x in enumerate(left) if i not in used_left];unmatched_right=[(j,x) for j,x in enumerate(right) if j not in used_right]
    ambiguous_tokens={x['part_number'] for _,x in unmatched_left}&{x['part_number'] for _,x in unmatched_right}
    for token in sorted(ambiguous_tokens):ambiguous.append({'part_number':token,'status':'manual_match_required','old_line_ids':[x['line_id'] for _,x in unmatched_left if x['part_number']==token],'new_line_ids':[x['line_id'] for _,x in unmatched_right if x['part_number']==token]})
    added=[x for _,x in unmatched_right if x['part_number'] not in ambiguous_tokens]
    removed=[x for _,x in unmatched_left if x['part_number'] not in ambiguous_tokens]
    modified=[];unchanged=[]
    for a,b in pairs:
        changes={k:{'before':a.get(k),'after':b.get(k)} for k in COMPARE_FIELDS if a.get(k)!=b.get(k)}
        (modified if changes else unchanged).append({'before':a,'after':b,'changes':changes})
    return {'added':added,'removed':removed,'modified':modified,'unchanged':unchanged,'ambiguous':ambiguous}

def record_matches(con,left_id,right_id,matches,actor,reason):
    if not actor.strip() or len(reason.strip())<3 or not matches or len(matches)>100:raise ValueError('人工匹配需要有效对应关系、操作人和原因')
    left,right=load(con,left_id),load(con,right_id)
    if left['series_id']!=right['series_id'] or left['version']>=right['version']:raise ValueError('人工匹配必须使用同系列较早及较新版本')
    if any(not str(k).isdigit() or type(v) is not int for k,v in matches.items()):raise ValueError('匹配必须为实际询价行ID')
    con.execute('BEGIN IMMEDIATE')
    try:
        old=con.execute('SELECT matches_json FROM rfq_match_decisions WHERE left_id=? AND right_id=? ORDER BY rowid DESC LIMIT 1',(left_id,right_id)).fetchone()
        combined={**(json.loads(old[0]) if old else {}),**matches}
        compare_items(left['snapshot']['lines'],right['snapshot']['lines'],combined)
        rid='MATCH-'+uuid4().hex[:16]
        con.execute('INSERT INTO rfq_match_decisions VALUES(?,?,?,?,?,?,?)',(rid,left_id,right_id,encoded(combined),actor,reason,stamp()))
        from .store import audit
        audit(con,'rfq_matches_confirmed',rid,{'left_id':left_id,'right_id':right_id,'matches':combined,'reason':reason},actor)
        con.commit();return {'id':rid,'matches':combined,'actor':actor,'reason':reason}
    except Exception:con.rollback();raise

def compare(con,left_id,right_id,asof):
    left=load(con,left_id);right=load(con,right_id)
    if left['series_id']!=right['series_id']:raise ValueError('不同客户或RFQ系列不能自动比较')
    if left['version']>=right['version']:raise ValueError('请选择较早版本到较新版本')
    a,b=left['snapshot'],right['snapshot']
    decision=con.execute('SELECT * FROM rfq_match_decisions WHERE left_id=? AND right_id=? ORDER BY rowid DESC LIMIT 1',(left_id,right_id)).fetchone()
    diff=compare_items(a['lines'],b['lines'],json.loads(decision['matches_json']) if decision else None)
    terms={k:{'before':a['terms'].get(k),'after':b['terms'].get(k)} for k in TERMS if a['terms'].get(k,{}).get('value')!=b['terms'].get(k,{}).get('value')}
    attachment_changes=sorted((x['filename'],x['sha256']) for x in a['attachments'])!=sorted((x['filename'],x['sha256']) for x in b['attachments'])
    impacts=[]
    affected=[(x['before'],x['after'],list(x['changes'])) for x in diff['modified']]+[(x,None,['removed']) for x in diff['removed']]
    if terms or attachment_changes:
        affected.extend((x['before'],x['after'],['header_terms' if terms else 'attachment_changed']) for x in diff['unchanged'])
    for old,new,changed in affected:
        quotes=[dict(r) for r in con.execute('SELECT q.id,q.status,i.snapshot_json FROM quote_items i JOIN quotes q ON q.id=i.quote_id WHERE i.line_id=?',(old['line_id'],))]
        for r in con.execute('SELECT q.id,s.status,q.payload_json FROM commercial_quote_items i JOIN commercial_quotes q ON q.id=i.quote_id JOIN commercial_quote_states s ON s.quote_id=q.id WHERE i.line_id=?',(old['line_id'],)):
            item=next((x for x in json.loads(r['payload_json'])['lines'] if x['line_id']==old['line_id']),None)
            offer=(item.get('selected') or {}).get('offer',{}) if item else {}
            quotes.append({'id':r['id'],'status':r['status'],'snapshot_json':json.dumps({'price_basis':{'record':offer}})})
        for quote in quotes:
            snapshot=json.loads(quote['snapshot_json']);source=snapshot.get('price_basis',{}).get('record',{})
            risks=['原报价有效性待人工复核','报价需重新核价，历史报价快照保持不变']
            if 'quantity' in changed:risks+=['采购量变化，需重新核对供应商单价及MOQ','单位成本和利润需重新计算，不假定数量折扣']
            moq=source.get('moq');new_qty=new.get('quantity') if new else None
            if moq and new_qty is not None and new_qty<int(moq):risks.append('新数量低于已记录MOQ')
            if any(x in changed for x in ('unit','part_condition','description','mpn','part_number')):risks.append('规格/单位/件状或型号变化，原供应商报价不能直接复用')
            if terms or 'deadline' in changed:risks.append('交期、运输或付款条件需人工复核')
            if source.get('valid_until') and str(source['valid_until'])[:10]<asof:risks.append('历史供应商报价已过有效期')
            impacts.append({'quote_id':quote['id'],'quote_status':quote['status'],'old_line_id':old['line_id'],'part_number':old['part_number'],
                'supplier':source.get('supplier'),'source_resource_id':source.get('resource_id'),'new_quantity':new_qty,'known_moq':moq,'changes':changed,'requires_requote':True,'risks':risks,'profit_impact':'unknown_until_recalculated'})
    return {'left':{'id':left_id,'version':left['version'],'sha256':left['payload_sha256']},'right':{'id':right_id,'version':right['version'],'sha256':right['payload_sha256']},
        **diff,'header_changes':terms,'attachments_changed':attachment_changes,'quote_impacts':impacts,'manual_match_decision':dict(decision) if decision else None,
        'unprovided_terms':[k for k in sorted(TERMS) if k not in a['terms'] or k not in b['terms']],
        'summary':{k:len(diff[k]) for k in diff},'asof':asof,'note':'差异是实际快照字段比较；未匹配项须人工确认，不自动修改旧版本或供应商报价。截止日期是询价截止，不冒充交付日期。'}
