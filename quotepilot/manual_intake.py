"""Explicit human transcription for unreadable sources; never an AI result."""
import hashlib,json
from .store import audit

def create_manual_line(con,email_id,body):
    if not body['confirm_source']:raise ValueError('请先确认已对照原始文件逐项核对')
    for key in ('actor','reason','part_number','unit','source_rfq_no','source_locator'):
        if not body[key].strip():raise ValueError('补录字段、复核人、原因及来源定位不能为空白')
    con.execute('CREATE TABLE IF NOT EXISTS manual_intakes(entry_key TEXT PRIMARY KEY,payload_sha256 TEXT NOT NULL,receipt_json TEXT NOT NULL)');con.commit()
    payload=json.dumps({'email_id':email_id,**body},sort_keys=True,ensure_ascii=False);sha=hashlib.sha256(payload.encode()).hexdigest()
    con.execute('BEGIN IMMEDIATE')
    try:
        old=con.execute('SELECT * FROM manual_intakes WHERE entry_key=?',(body['entry_key'],)).fetchone()
        if old:
            if old['payload_sha256']!=sha:raise ValueError('同一补录标识的字段不一致，请重新核对')
            con.commit();return {**json.loads(old['receipt_json']),'idempotent':True}
        email=con.execute('SELECT * FROM emails WHERE email_id=?',(email_id,)).fetchone()
        source=con.execute('SELECT id,filename,sha256 FROM source_files WHERE id=? AND email_id=?',(body['source_id'],email_id)).fetchone()
        if not email or not source:raise ValueError('来源文件不属于所选邮件')
        ref=f'{email["filename"]} / {source["filename"]} / 人工定位: {body["source_locator"]} / {body["entry_key"]}'
        customer=(email['sender'] or '').split('<')[0].strip().strip('"')
        values=(email_id,body['source_rfq_no'].strip(),body['part_number'].strip().upper(),body.get('description',''),body['quantity'],body['unit'].strip().upper(),'',body.get('condition','').strip().upper(),'','','',customer,'人工补录（已核对来源）',ref)
        cur=con.execute('''INSERT INTO rfq_lines(email_id,source_rfq_no,part_number,description,quantity,unit,urgency,part_condition,mpn,deadline,product_scope,customer,source_kind,source_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',values)
        evidence={'provider':'human','simulated':False,'confirmed_fields':body,'source_id':source['id'],'source_sha256':source['sha256'],'locator_verification':'human_entered_not_automatically_verified'}
        con.execute('INSERT INTO line_evidence VALUES(?,?,?)',(cur.lastrowid,json.dumps(evidence,ensure_ascii=False),'人工核对'))
        con.execute('INSERT OR IGNORE INTO rfq_headers(email_id,source_rfq_no,customer) VALUES(?,?,?)',(email_id,body['source_rfq_no'].strip(),customer))
        result={'line_ids':[cur.lastrowid],'new_lines':1,'provider':'human','source_id':source['id']}
        con.execute('INSERT INTO manual_intakes VALUES(?,?,?)',(body['entry_key'],sha,json.dumps(result)))
        audit(con,'rfq_manual_transcribed',str(cur.lastrowid),evidence,body['actor']);con.commit();return {**result,'idempotent':False}
    except Exception:con.rollback();raise
