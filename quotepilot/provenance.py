"""Field evidence, explicit human review, immutable revisions and local audit-chain checks."""
import hashlib,json,re
from datetime import datetime,timezone
from .fields import canonical

FIELDS={'source_rfq_no':'询价单号','part_number':'Part Number','quantity':'Quantity','unit':'Unit Of Measure',
        'part_condition':'件状条件','description':'Description','deadline':'截止报价日期','mpn':'询价MPN'}
REQUIRED={'source_rfq_no','part_number','quantity','unit'}
SCHEMA='''
CREATE TABLE IF NOT EXISTS field_evidence(
 line_id INTEGER NOT NULL,field TEXT NOT NULL,source_id TEXT,source_name TEXT,source_sha256 TEXT,
 locator_json TEXT NOT NULL,snippet TEXT NOT NULL,original_json TEXT NOT NULL,method TEXT NOT NULL,
 trust_level TEXT NOT NULL,extracted_at TEXT NOT NULL,PRIMARY KEY(line_id,field),
 FOREIGN KEY(line_id) REFERENCES rfq_lines(id),FOREIGN KEY(source_id) REFERENCES source_files(id));
CREATE TABLE IF NOT EXISTS line_review_state(line_id INTEGER PRIMARY KEY,version INTEGER NOT NULL,status TEXT NOT NULL,
 actor TEXT,reason TEXT,reviewed_at TEXT,FOREIGN KEY(line_id) REFERENCES rfq_lines(id));
CREATE TABLE IF NOT EXISTS field_revisions(id INTEGER PRIMARY KEY AUTOINCREMENT,line_id INTEGER NOT NULL,field TEXT NOT NULL,
 before_json TEXT NOT NULL,after_json TEXT NOT NULL,review_version INTEGER NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,
 confirmed INTEGER NOT NULL,at TEXT NOT NULL,FOREIGN KEY(line_id) REFERENCES rfq_lines(id));
CREATE TABLE IF NOT EXISTS audit_chain(event_id INTEGER PRIMARY KEY,prev_hash TEXT NOT NULL,event_hash TEXT NOT NULL,
 FOREIGN KEY(event_id) REFERENCES audit_events(id));
'''

def stamp():return datetime.now(timezone.utc).isoformat()
def encoded(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'))

def seal_audit(con):
    last=con.execute('SELECT event_id,event_hash FROM audit_chain ORDER BY event_id DESC LIMIT 1').fetchone()
    previous=last['event_hash'] if last else '0'*64
    for row in con.execute('SELECT * FROM audit_events WHERE id>? ORDER BY id',(last['event_id'] if last else 0,)).fetchall():
        digest=hashlib.sha256((previous+encoded(dict(row))).encode()).hexdigest()
        con.execute('INSERT INTO audit_chain VALUES(?,?,?)',(row['id'],previous,digest));previous=digest

def install(con):
    con.executescript(SCHEMA)
    for table in ('source_files','field_evidence','field_revisions','audit_events','audit_chain'):
        for operation in ('UPDATE','DELETE'):
            con.execute(f"CREATE TRIGGER IF NOT EXISTS protect_{table}_{operation.lower()} BEFORE {operation} ON {table} BEGIN SELECT RAISE(ABORT,'immutable evidence or audit record'); END")
    seal_audit(con);con.commit()

def verify_audit(con):
    previous='0'*64;count=0
    for r in con.execute('SELECT e.*,c.prev_hash,c.event_hash FROM audit_events e LEFT JOIN audit_chain c ON c.event_id=e.id ORDER BY e.id'):
        obj=dict(r);prior=obj.pop('prev_hash');digest=obj.pop('event_hash')
        expected=hashlib.sha256((previous+encoded(obj)).encode()).hexdigest()
        if prior!=previous or digest!=expected:return {'valid':False,'checked':count,'first_invalid_event':r['id']}
        previous=digest;count+=1
    return {'valid':True,'checked':count,'head_hash':previous,'scope':'本地追加日志校验；有文件系统管理员权限者仍可重写整个库，未使用外部时间戳锚点'}

def _source(con,line,raw):
    sources=con.execute('SELECT id,filename,sha256,kind FROM source_files WHERE email_id=?',(line['email_id'],)).fetchall()
    digest=raw.get('_source_sha256')
    if digest:
        return next((s for s in sources if s['sha256']==digest and s['filename']==raw.get('_source_file')),None)
    return next((s for s in sources if s['kind']=='eml'),None)

def locate_snippet(con,email_id,snippet):
    clean=lambda x:' '.join(str(x).split())
    if not snippet:return None,{'verification':'unlocated'}
    for row in con.execute('SELECT id,filename,kind,content FROM source_files WHERE email_id=?',(email_id,)):
        data=bytes(row['content']);name=row['filename'].lower()
        if name.endswith('.pdf'):
            import fitz
            with fitz.open(stream=data,filetype='pdf') as doc:
                for i,page in enumerate(doc):
                    if clean(snippet) in clean(page.get_text()):return row['id'],{'page':i+1,'verification':'literal_span'}
        elif row['kind']=='body' and clean(snippet) in clean(data.decode('utf-8',errors='replace')):
            return row['id'],{'kind':'email_body','verification':'literal_span'}
        elif name.endswith('.xlsx'):
            from .xlsxio import read_xlsx
            for record in read_xlsx(data):
                values=' | '.join(str(v) for k,v in record.items() if not k.startswith('_'))
                if clean(snippet) in clean(values):return row['id'],{'sheet':record['_source_sheet'],'row':record['_source_row'],'verification':'literal_row_span'}
    return None,{'verification':'unlocated'}

def verify_field(con,field):
    if not field.get('source_id'):return 'no_source'
    source=con.execute('SELECT * FROM source_files WHERE id=?',(field['source_id'],)).fetchone()
    if not source:return 'source_missing'
    raw=bytes(source['content'])
    if hashlib.sha256(raw).hexdigest()!=field['source_sha256']:return 'hash_mismatch'
    loc=field['locator'];snippet=field['snippet']
    if not snippet:return 'missing_value'
    if 'cell' in loc:
        from io import BytesIO
        from openpyxl import load_workbook
        sheet,cell=loc['cell'].rsplit('!',1);book=load_workbook(BytesIO(raw),read_only=True,data_only=False)
        try:return 'cell_value_found' if str(book[sheet][cell].value).strip()==snippet.strip() else 'cell_mismatch'
        finally:book.close()
    if 'page' in loc:
        import fitz
        with fitz.open(stream=raw,filetype='pdf') as doc:
            page=int(loc['page'])
            if not 1<=page<=len(doc):return 'page_missing'
            return 'page_span_found' if ' '.join(snippet.split()) in ' '.join(doc[page-1].get_text().split()) else 'span_not_found'
    if source['kind'] in ('body','eml'):
        return 'text_span_found' if snippet in raw.decode('utf-8',errors='replace') else 'human_location_required'
    return 'human_location_required'

def capture(con,line_id,raw=None,method='deterministic_parser',source_id=None,locator=None,confirmed=False,actor='local_operator',reason='',original_values=None):
    line=con.execute('SELECT * FROM rfq_lines WHERE id=?',(line_id,)).fetchone()
    if not line:raise KeyError('询价行不存在')
    if con.execute('SELECT 1 FROM line_review_state WHERE line_id=?',(line_id,)).fetchone():return
    if raw is None:
        old=con.execute('SELECT raw_json FROM line_evidence WHERE line_id=?',(line_id,)).fetchone()
        raw=json.loads(old[0]) if old else {}
    source=con.execute('SELECT id,filename,sha256,kind FROM source_files WHERE id=? AND email_id=?',(source_id,line['email_id'])).fetchone() if source_id else _source(con,line,raw)
    values={canonical(k):(k,v) for k,v in raw.items() if not k.startswith('_')}
    for field,label in FIELDS.items():
        key,value=values.get(label,('',None))
        loc=dict(locator or {})
        if not loc:
            loc={'row':raw.get('_source_row',line['source_ref']),'kind':line['source_kind']}
            if raw.get('_source_cells',{}).get(key):loc.update(sheet=raw.get('_source_sheet'),cell=raw['_source_cells'][key],verified='parser_cell')
            page=raw.get('_source_page') or (re.search(r'page (\d+)',str(raw.get('_source_row',''))) or [None,None])[1]
            if page:loc.update(page=int(page),verified='parser_page')
        snippet=str(raw.get('_source_snippets',{}).get(key,value) or '')
        if method.startswith('genesis'):snippet=str(raw.get('evidence') or snippet)
        trust='source_located' if source and snippet and ('cell' in loc or 'page' in loc or raw.get('_raw_text') or value is not None) else 'requires_review'
        if not line[field]:trust='missing'
        if loc.get('verification')=='unlocated':trust='requires_review'
        con.execute('INSERT INTO field_evidence VALUES(?,?,?,?,?,?,?,?,?,?,?)',
          (line_id,field,source['id'] if source else None,source['filename'] if source else None,source['sha256'] if source else None,
           encoded(loc),snippet,encoded((original_values or {}).get(field,line[field])),method,trust,stamp()))
    con.execute('INSERT INTO line_review_state VALUES(?,?,?,?,?,?)',(line_id,1,'confirmed' if confirmed else 'pending',actor if confirmed else None,reason if confirmed else None,stamp() if confirmed else None))

def detail(con,line_id):
    capture(con,line_id)
    state=dict(con.execute('SELECT * FROM line_review_state WHERE line_id=?',(line_id,)).fetchone())
    line=dict(con.execute('SELECT * FROM rfq_lines WHERE id=?',(line_id,)).fetchone())
    fields=[]
    for r in con.execute('SELECT * FROM field_evidence WHERE line_id=? ORDER BY field',(line_id,)):
        item=dict(r);item['locator']=json.loads(item.pop('locator_json'));item['extracted_value']=json.loads(item.pop('original_json'));item['current_value']=line[item['field']];item['review_status']=state['status'];fields.append(item)
    revisions=[{**dict(r),'before':json.loads(r['before_json']),'after':json.loads(r['after_json'])} for r in con.execute('SELECT * FROM field_revisions WHERE line_id=? ORDER BY id',(line_id,))]
    return {'line':line,'review':state,'fields':fields,'revisions':revisions,'trust_note':'可信等级表示来源定位情况，不是模型准确率或统计概率'}

def review(con,line_id,version,changes,actor,reason,confirm):
    if not actor.strip() or len(reason.strip())<3:raise ValueError('复核人和至少三个字的修改原因必须填写')
    if set(changes)-set(FIELDS):raise ValueError('不允许修改未知字段')
    capture(con,line_id);con.commit();con.execute('BEGIN IMMEDIATE')
    try:
        old=detail(con,line_id);state=old['review'];line=old['line']
        if state['version']!=version:raise ValueError('复核版本冲突，请重新读取')
        after={k:changes.get(k,line[k] if line[k] is not None else '') for k in FIELDS}
        for key,value in after.items():
            if key=='quantity':
                if type(value) is not int or not 0<value<=9007199254740991:raise ValueError('数量必须为正整数')
            elif not isinstance(value,str) or len(value)>1000:raise ValueError('字段文本无效或过长')
            else:after[key]=value.strip().upper() if key in ('part_number','unit','part_condition') else value.strip()
        if confirm and any(not after[k] for k in REQUIRED):raise ValueError('件号、数量、单位、RFQ号缺失，不能确认')
        for field in FIELDS:
            if line[field]!=after[field] or confirm:
                con.execute('INSERT INTO field_revisions(line_id,field,before_json,after_json,review_version,actor,reason,confirmed,at) VALUES(?,?,?,?,?,?,?,?,?)',
                    (line_id,field,encoded(line[field]),encoded(after[field]),version+1,actor,reason,int(confirm),stamp()))
        con.execute('UPDATE rfq_lines SET '+','.join(k+'=?' for k in FIELDS)+' WHERE id=?',list(after.values())+[line_id])
        con.execute('UPDATE line_review_state SET version=?,status=?,actor=?,reason=?,reviewed_at=? WHERE line_id=?',(version+1,'confirmed' if confirm else 'pending',actor,reason,stamp(),line_id))
        from .store import audit
        audit(con,'rfq_fields_confirmed' if confirm else 'rfq_fields_edited',line_id,{'before_version':version,'after_version':version+1,'changes':{k:{'before':line[k],'after':after[k]} for k in changes},'confirmed':confirm},actor)
        con.commit();return detail(con,line_id)
    except Exception:con.rollback();raise

def assert_ready(con,line_id,snapshot=None):
    state=con.execute('SELECT * FROM line_review_state WHERE line_id=?',(line_id,)).fetchone()
    if not state or state['status']!='confirmed':raise ValueError('询价字段尚未人工复核，请先完成证据复核')
    if snapshot is not None and snapshot!=state['version']:raise ValueError('询价字段已变更，请重新核价生成新草案')

def quote_review_snapshot(con,line_id):
    capture(con,line_id)
    return con.execute('SELECT version FROM line_review_state WHERE line_id=?',(line_id,)).fetchone()[0]
