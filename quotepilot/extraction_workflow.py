"""Explicit AI suggestion -> human confirmation -> RFQ rows. Never auto-price model output."""
import hashlib,json,sqlite3
from io import BytesIO
from uuid import uuid4
from .store import audit

SCHEMA='''CREATE TABLE IF NOT EXISTS extraction_runs (
 id TEXT PRIMARY KEY, email_id TEXT NOT NULL, input_text TEXT NOT NULL,
 input_sha256 TEXT NOT NULL, result_json TEXT NOT NULL, status TEXT NOT NULL,
 model TEXT, provider TEXT, confirmation_json TEXT,
 created_at TEXT DEFAULT CURRENT_TIMESTAMP,
 FOREIGN KEY(email_id) REFERENCES emails(email_id)
);'''

def ensure_schema(con):con.executescript(SCHEMA)

def source_context(con,email_id):
    rows=con.execute('SELECT id,filename,kind,content FROM source_files WHERE email_id=? ORDER BY kind,id',(email_id,)).fetchall()
    if not rows:raise KeyError('没有找到原始邮件来源')
    chunks=[];refs=[];notes=[]
    for row in rows:
        raw=bytes(row['content']);name=row['filename']
        if row['kind']=='body':
            text=raw.decode('utf-8',errors='replace');chunks.append(f'FILE {name}\n{text}');refs.append(row['id'])
        elif row['kind']=='attachment' and name.lower().endswith('.pdf'):
            import fitz
            with fitz.open(stream=raw,filetype='pdf') as doc:
                if len(doc)>10:raise ValueError('AI预览最多处理10页PDF；请先拆分文件')
                texts=[(i+1,page.get_text()) for i,page in enumerate(doc)]
                if not any(t.strip() for _,t in texts):notes.append(name+' 没有文字层；本次文本提取不包含此扫描附件');continue
                chunks.extend(f'FILE {name} PAGE {i}\n{t}' for i,t in texts);refs.append(row['id'])
        elif row['kind']=='attachment' and name.lower().endswith('.xlsx'):
            from openpyxl import load_workbook
            import zipfile
            with zipfile.ZipFile(BytesIO(raw)) as z:
                if sum(x.file_size for x in z.infolist())>50*1024*1024:raise ValueError('工作簿解压体积超限')
            wb=load_workbook(BytesIO(raw),read_only=True,data_only=False)
            try:
                if len(wb.worksheets)>5:raise ValueError('AI预览最多5个工作表')
                for ws in wb.worksheets:
                    if ws.max_row>200 or ws.max_column>30:raise ValueError('工作表超过200行/30列，请先选择范围')
                    data=[]
                    for cells in ws:
                        if any(c.data_type=='f' for c in cells):raise ValueError('公式值未核验，不提交模型猜测')
                        values=[f'{c.coordinate}={c.value}' for c in cells if c.value is not None]
                        if values:data.append(' | '.join(values))
                    chunks.append(f'FILE {name} SHEET {ws.title}\n'+'\n'.join(data))
                refs.append(row['id'])
            finally:wb.close()
    text='\n\n'.join(chunks)
    if not text.strip():raise ValueError('没有可提交的文字；扫描件OCR尚未接入')
    if len(text)>30000:raise ValueError('来源文本超过30000字符；请拆分，禁止静默截断')
    return text,refs,notes

def create_run(con,email_id,result,text,refs,notes):
    ensure_schema(con)
    rid='EX-'+uuid4().hex[:12].upper()
    result={**result,'source_ids':refs,'source_notes':notes,'run_id':rid,'email_id':email_id}
    with con:
        con.execute('INSERT INTO extraction_runs(id,email_id,input_text,input_sha256,result_json,status,model,provider) VALUES(?,?,?,?,?,?,?,?)',
                    (rid,email_id,text,hashlib.sha256(text.encode()).hexdigest(),json.dumps(result,ensure_ascii=False),'pending',result.get('model'),result['provider']))
        audit(con,'ai_suggestions_created',rid,{'email_id':email_id,'provider':result['provider'],'simulated':result['simulated'],'model':result.get('model'),'response_id':result.get('response_id'),'usage':result.get('usage'),'candidate_count':len(result['lines']),'source_notes':notes})
    return {**result,'input_text':text,'input_sha256':hashlib.sha256(text.encode()).hexdigest()}

def load_run(con,rid):
    ensure_schema(con)
    r=con.execute('SELECT * FROM extraction_runs WHERE id=?',(rid,)).fetchone()
    if not r:raise KeyError('提取复核记录不存在')
    return {**json.loads(r['result_json']),'input_text':r['input_text'],'input_sha256':r['input_sha256'],'status':r['status'],'confirmed':json.loads(r['confirmation_json']) if r['confirmation_json'] else None}

def confirm_run(con,rid,lines,actor,reason):
    ensure_schema(con);con.execute('BEGIN IMMEDIATE')
    try:
        r=con.execute('SELECT * FROM extraction_runs WHERE id=?',(rid,)).fetchone()
        if not r:raise KeyError('提取记录不存在')
        if r['status']=='confirmed':
            obj=json.loads(r['confirmation_json']);con.commit();return {**obj,'idempotent':True}
        original=json.loads(r['result_json'])
        if original.get('simulated'):raise ValueError('Mock不能确认为真实模型提取')
        email=con.execute('SELECT * FROM emails WHERE email_id=?',(r['email_id'],)).fetchone()
        indices=[x['source_index'] for x in lines]
        if len(set(indices))!=len(indices):raise ValueError('同一建议行不能重复确认')
        ids=[];added=0
        for patch in lines:
            idx=patch['source_index']
            if idx>=len(original['lines']):raise ValueError('建议行索引不存在')
            pn=patch['part_number'].strip().upper();unit=patch['unit'].strip().upper();cond=patch.get('condition','').strip().upper();rfq=patch['source_rfq_no'].strip()
            if not pn or not unit or not rfq:raise ValueError('件号、单位、询价号不能为空白')
            qty=patch['quantity'];suggested=original['lines'][idx]
            existing=con.execute('SELECT id FROM rfq_lines WHERE email_id=? AND source_rfq_no=? AND part_number=? AND quantity=? AND unit=? AND part_condition=?',
                                 (r['email_id'],rfq,pn,qty,unit,cond)).fetchone()
            if existing:ids.append(existing['id']);continue
            ref=f'{email["filename"]} · {rid} / suggestion {idx+1}'
            customer=(email['sender'] or '').split('<')[0].strip().strip('"')
            cur=con.execute('''INSERT INTO rfq_lines(email_id,source_rfq_no,part_number,description,quantity,unit,urgency,part_condition,mpn,deadline,product_scope,customer,source_kind,source_ref)
                                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                            (r['email_id'],rfq,pn,patch.get('description',''),qty,unit,'',cond,'','','',customer,'Genesis建议（已人工确认）',ref))
            lid=cur.lastrowid;ids.append(lid);added+=1
            evidence={'run_id':rid,'original_model_suggestion':suggested,'confirmed_fields':patch,'actor':actor,'reason':reason,'source_ids':original['source_ids']}
            con.execute('INSERT INTO line_evidence VALUES(?,?,?)',(lid,json.dumps(evidence,ensure_ascii=False),'人工确认'))
            from .provenance import capture,locate_snippet,FIELDS
            sid,location=locate_snippet(con,r['email_id'],suggested.get('evidence',''))
            original_values={k:suggested.get('condition' if k=='part_condition' else k) for k in FIELDS}
            capture(con,lid,suggested,method='genesis:'+str(original.get('model') or 'unknown'),source_id=sid,locator=location,
                confirmed=True,actor=actor,reason=reason,original_values=original_values)
            con.execute('INSERT OR IGNORE INTO rfq_headers(email_id,source_rfq_no,customer) VALUES(?,?,?)',(r['email_id'],rfq,customer))
        receipt={'run_id':rid,'line_ids':ids,'new_lines':added,'actor':actor,'reason':reason,'selected_indices':indices,'unselected_indices':[i for i in range(len(original['lines'])) if i not in indices]}
        con.execute('UPDATE extraction_runs SET status=?,confirmation_json=? WHERE id=?',('confirmed',json.dumps(receipt,ensure_ascii=False),rid))
        audit(con,'ai_suggestions_confirmed',rid,receipt,actor);con.commit();return {**receipt,'idempotent':False}
    except Exception:con.rollback();raise

