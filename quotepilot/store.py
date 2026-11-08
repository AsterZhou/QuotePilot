"""Local SQLite persistence. MOI/MatrixOne integration is a separate next step."""
from __future__ import annotations
from datetime import datetime,timedelta
from pathlib import Path
import sqlite3
from .xlsxio import read_xlsx
from .parsing import file_preview,parse_eml

SCHEMA = '''
CREATE TABLE IF NOT EXISTS emails (
 email_id TEXT PRIMARY KEY, file_hash TEXT NOT NULL UNIQUE, filename TEXT NOT NULL,
 subject TEXT, sender TEXT, mail_date TEXT, imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rfq_lines (
 id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT NOT NULL, source_rfq_no TEXT,
 part_number TEXT NOT NULL, description TEXT, quantity INTEGER NOT NULL,
 unit TEXT, urgency TEXT, part_condition TEXT, mpn TEXT, deadline TEXT,
 product_scope TEXT, customer TEXT, source_kind TEXT, source_ref TEXT NOT NULL,
 UNIQUE(email_id,source_ref), FOREIGN KEY(email_id) REFERENCES emails(email_id)
);
CREATE TABLE IF NOT EXISTS historical (
 id INTEGER PRIMARY KEY AUTOINCREMENT, inquiry_no TEXT, rfq_no TEXT,
 inquiry_date TEXT, airline TEXT, urgency TEXT, line_no TEXT, part_number TEXT,
 description TEXT, quantity INTEGER, unit TEXT, part_condition TEXT,
 product_scope TEXT, deadline TEXT, source_row TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_history_part ON historical(part_number);
CREATE INDEX IF NOT EXISTS idx_history_date ON historical(inquiry_date);
CREATE TABLE IF NOT EXISTS costs (
 part_number TEXT PRIMARY KEY, description TEXT, product_scope TEXT, unit TEXT,
 inventory INTEGER, warehouse TEXT, part_condition TEXT, standard_cost TEXT,
 avg_cost TEXT, last_purchase_price TEXT, currency TEXT, updated_at TEXT, source_row TEXT
);
CREATE TABLE IF NOT EXISTS prices (
 resource_id TEXT PRIMARY KEY, part_number TEXT, supplier_code TEXT,
 supplier TEXT, condition TEXT, unit_price TEXT, currency TEXT, fx_to_cny TEXT,
 moq INTEGER, lead_days INTEGER, in_stock TEXT, certificate TEXT,
 quote_date TEXT, valid_until TEXT, status TEXT, source_row TEXT
);
CREATE INDEX IF NOT EXISTS idx_price_part ON prices(part_number);
CREATE TABLE IF NOT EXISTS quote_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT DEFAULT CURRENT_TIMESTAMP,
 quote_ref TEXT, part_number TEXT, decision TEXT, rationale TEXT
);
'''


def date_value(s:str) -> str:
    s = str(s or '').strip()
    if not s:return ''
    try:
        n=float(s)
        if 10000<n<100000:
            return (datetime(1899,12,30)+timedelta(days=n)).strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:pass
    return s


def open_db(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    con = sqlite3.connect(str(path), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def _g(r:dict, *keys):
    for k in keys:
        if k in r and r[k] not in ('',None): return str(r[k]).strip()
    return ''


def _num(s:str) -> int:
    try:return int(float(str(s)))
    except (ValueError,TypeError):return 0


def seed_official(con:sqlite3.Connection, sample_dir:Path) -> dict:
    sample_dir=Path(sample_dir)
    for path in sorted(sample_dir.rglob('*.eml')):
        ingest_eml(con,path.read_bytes(),path.name,dataset='official_sample')
    import hashlib
    for workbook in sample_dir.glob('*.xlsx'):
        data=workbook.read_bytes();digest=hashlib.sha256(data).hexdigest()
        con.execute('INSERT OR IGNORE INTO source_files(id,filename,sha256,content,kind,dataset) VALUES(?,?,?,?,?,?)',(digest,workbook.name,digest,data,'workbook','official_sample'))
    historical=read_xlsx(sample_dir/'询价报价清单_看板演示数据.xlsx')
    for r in historical:
        con.execute('''INSERT OR IGNORE INTO historical
           (inquiry_no,rfq_no,inquiry_date,airline,urgency,line_no,part_number,description,quantity,
            unit,part_condition,product_scope,deadline,source_row) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (_g(r,'询价单号'),_g(r,'RFQ No'),date_value(_g(r,'询价日期')),_g(r,'航空公司'),
             _g(r,'紧急程度'),_g(r,'行号'),_g(r,'Part Number'),_g(r,'Description'),
             _num(_g(r,'Quantity')),_g(r,'Unit Of Measure'),_g(r,'件状条件'),
             _g(r,'产品范围'),date_value(_g(r,'截止报价日期')),_g(r,'_source_row')))
    costs=read_xlsx(sample_dir/'内部物料成本表_演示数据.xlsx')
    for r in costs:
        con.execute('''INSERT OR IGNORE INTO costs
          (part_number,description,product_scope,unit,inventory,warehouse,part_condition,
           standard_cost,avg_cost,last_purchase_price,currency,updated_at,source_row)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (_g(r,'Part Number').upper(),_g(r,'Description'),_g(r,'产品范围'),_g(r,'Unit Of Measure').upper(),
           _num(_g(r,'库存数量')),_g(r,'仓库'),_g(r,'库存件状').upper(),_g(r,'标准成本'),
           _g(r,'平均成本'),_g(r,'最近采购价'),_g(r,'币种').upper(),
           date_value(_g(r,'成本更新日期')),_g(r,'_source_row')))
    prices=read_xlsx(sample_dir/'价格资源表_演示数据.xlsx')
    for r in prices:
        con.execute('''INSERT OR IGNORE INTO prices
           (resource_id,part_number,supplier_code,supplier,condition,unit_price,currency,fx_to_cny,
            moq,lead_days,in_stock,certificate,quote_date,valid_until,status,source_row)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
          (_g(r,'价格资源编号'),_g(r,'Part Number').upper(),_g(r,'供应商编码'),_g(r,'供应商名称'),
           _g(r,'件状条件').upper(),_g(r,'单价'),_g(r,'币种').upper(),_g(r,'汇率到CNY'),
           _num(_g(r,'最小起订量')),_num(_g(r,'交期天数')),_g(r,'是否现货'),_g(r,'证书类型'),
           date_value(_g(r,'报价日期')),date_value(_g(r,'有效期至')),_g(r,'价格状态'),_g(r,'_source_row')))
    con.commit()
    return {name:con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
            for name in ('emails','rfq_lines','historical','costs','prices')}

# v0.5 adds immutable source bytes and persisted reviewable quote snapshots.
EXT_SCHEMA = '''
CREATE TABLE IF NOT EXISTS source_files (
 id TEXT PRIMARY KEY, email_id TEXT, parent_id TEXT, filename TEXT NOT NULL,
 sha256 TEXT NOT NULL, content BLOB NOT NULL, kind TEXT NOT NULL,
 dataset TEXT NOT NULL DEFAULT 'user_upload', imported_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS rfq_headers (
 id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT NOT NULL, source_rfq_no TEXT NOT NULL,
 customer TEXT, UNIQUE(email_id,source_rfq_no)
);
CREATE TABLE IF NOT EXISTS line_evidence (
 line_id INTEGER PRIMARY KEY, raw_json TEXT NOT NULL, extraction_status TEXT NOT NULL,
 FOREIGN KEY(line_id) REFERENCES rfq_lines(id)
);
CREATE TABLE IF NOT EXISTS parse_issues (
 id INTEGER PRIMARY KEY AUTOINCREMENT, email_id TEXT, source_ref TEXT, raw_json TEXT,
 reason TEXT, UNIQUE(email_id,source_ref,raw_json,reason)
);
CREATE TABLE IF NOT EXISTS quotes (
 id TEXT PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 1, report_json TEXT NOT NULL, rule_version TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS quote_items (
 quote_id TEXT NOT NULL, line_id INTEGER NOT NULL, snapshot_json TEXT NOT NULL,
 PRIMARY KEY(quote_id,line_id), FOREIGN KEY(quote_id) REFERENCES quotes(id)
);
CREATE TABLE IF NOT EXISTS audit_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, at TEXT DEFAULT CURRENT_TIMESTAMP,
 action TEXT NOT NULL, entity_id TEXT, actor TEXT NOT NULL, detail_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value_json TEXT NOT NULL);
'''

_old_open_db = open_db

def open_db(path):
    con = _old_open_db(path)
    con.execute('PRAGMA foreign_keys=ON')
    con.execute('PRAGMA busy_timeout=5000')
    con.executescript(EXT_SCHEMA)
    from .provenance import install
    install(con)
    from .rfq_versions import install as install_versions
    install_versions(con)
    from .commercial import install as install_commercial
    install_commercial(con)
    from .operations import install as install_operations
    install_operations(con)
    return con


def audit(con, action, entity_id, detail, actor='local_operator'):
    import json
    con.execute('INSERT INTO audit_events(action,entity_id,actor,detail_json) VALUES(?,?,?,?)',
                (action,str(entity_id),actor,json.dumps(detail,ensure_ascii=False)))
    from .provenance import seal_audit
    seal_audit(con)


def ingest_eml(con, raw, filename, dataset='user_upload'):
    import hashlib,json
    from email import policy
    from email.parser import BytesParser
    o = parse_eml(raw, filename)
    existing=con.execute('SELECT * FROM emails WHERE file_hash=? OR email_id=?',
                         (o['sha256'],o['message_id'])).fetchone()
    if existing:
        if existing['file_hash'] != o['sha256']:
            raise ValueError('Message-ID 冲突：内容不同，已拒绝覆盖；请核对原邮件')
        audit(con,'import_duplicate',existing['email_id'],{'sha256':o['sha256']});con.commit()
        return o
    with con:
        con.execute('INSERT INTO emails(email_id,file_hash,filename,subject,sender,mail_date) VALUES(?,?,?,?,?,?)',
                    (o['message_id'],o['sha256'],filename,o['subject'],o['sender'],o['date']))
        def save_blob(data,name,kind,parent=None):
            digest=hashlib.sha256(data).hexdigest()
            source_id=hashlib.sha256((o['message_id']+kind+name+digest).encode()).hexdigest()
            con.execute('INSERT OR IGNORE INTO source_files(id,email_id,parent_id,filename,sha256,content,kind,dataset) VALUES(?,?,?,?,?,?,?,?)',
                        (source_id,o['message_id'],parent,name,digest,data,kind,dataset))
            return source_id
        parent=save_blob(raw,filename,'eml')
        msg=BytesParser(policy=policy.default).parsebytes(raw)
        for part in msg.walk():
            if part.get_filename() or part.get_content_disposition()=='attachment':
                save_blob(part.get_payload(decode=True) or b'',part.get_filename() or 'untitled','attachment',parent)
        save_blob(o['body'].encode(), 'body.txt','body',parent)
        for item in o['lines']:
            cur=con.execute('''INSERT INTO rfq_lines
             (email_id,source_rfq_no,part_number,description,quantity,unit,urgency,part_condition,mpn,deadline,product_scope,customer,source_kind,source_ref)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
             (o['message_id'],item['source_rfq_no'],item['part_number'],item['description'],item['quantity'],item['unit'],item['urgency'],
              item['condition'],item['mpn'],item['deadline'],item['product_scope'],item['customer'],item['source_kind'],item['source']))
            con.execute('INSERT INTO line_evidence VALUES(?,?,?)',(cur.lastrowid,json.dumps(item['raw_record'],ensure_ascii=False),item['extraction_status']))
            from .provenance import capture
            capture(con,cur.lastrowid,item['raw_record'])
            con.execute('INSERT OR IGNORE INTO rfq_headers(email_id,source_rfq_no,customer) VALUES(?,?,?)',
                        (o['message_id'],item['source_rfq_no'] or '待确认',item['customer']))
        for issue in o['rejected_rows']:
            con.execute('INSERT OR IGNORE INTO parse_issues(email_id,source_ref,raw_json,reason) VALUES(?,?,?,?)',
                        (o['message_id'],issue['source'],json.dumps(issue['raw'],ensure_ascii=False),issue['reason']))
        for note in o['parse_notes']:
            con.execute('INSERT OR IGNORE INTO parse_issues(email_id,source_ref,raw_json,reason) VALUES(?,?,?,?)',
                        (o['message_id'],filename,'{}',note))
        audit(con,'import',o['message_id'],{'dataset':dataset,'sha256':o['sha256'],'lines':len(o['lines']),'notes':o['parse_notes']})
    return o

