"""Local source extraction adapters. Suggestions are never executable quotations.
Supported: labelled text/PDF, tabular XLSX, EML body and PDF/XLSX attachments.
No model invocation, guessed prices, OCR confidence probabilities or silent defaults.
"""
from datetime import date,datetime
from io import BytesIO
import json,re
from pathlib import Path
from uuid import uuid4
from .provenance import stamp,encoded

ALIASES={
 'supplier':['supplier','供应商'], 'part_number':['part number','part_number','pn','零件型号','件号'],
 'specification':['specification','spec','技术规格','规格'], 'unit':['unit','uom','单位'],
 'condition':['condition','件状'], 'currency':['currency','币种'], 'unit_price':['unit price','price','单价'],
 'fx_to_cny':['fx to cny','汇率'], 'fx_source':['fx source','汇率依据'], 'moq':['moq','最小起订量'],
 'lead_days':['lead days','交期天数'], 'shipping_total':['shipping total','运费'],
 'shipping_scope':['shipping scope','运费范围'], 'shipping_group':['shipping group','运输批次'],
 'tax_rate':['tax rate','税率'], 'quote_date':['quote date','报价日期'], 'valid_until':['valid until','有效期'],
 'payment_terms':['payment terms','付款条件']}
REQUIRED=set(ALIASES)-{'shipping_scope','shipping_group'}
def key(s):return re.sub(r'[\s_\-]','',str(s)).lower()
KEYS={key(alias):field for field,aliases in ALIASES.items() for alias in aliases+[field]}

def install(con):
    con.execute('CREATE TABLE IF NOT EXISTS supplier_extraction_runs(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL)')
    for op in ('UPDATE','DELETE'):con.execute(f"CREATE TRIGGER IF NOT EXISTS protect_supplier_extract_{op.lower()} BEFORE {op} ON supplier_extraction_runs BEGIN SELECT RAISE(ABORT,'immutable supplier suggestions'); END")

def normalized(field,value):
    if value is None:return None
    if isinstance(value,(date,datetime)):value=value.date().isoformat() if isinstance(value,datetime) else value.isoformat()
    s=str(value).strip()
    if not s:return None
    if field in ('moq','lead_days'):
        if not re.fullmatch(r'\d+(?:\.0+)?',s):return s
        return int(float(s))
    if field in ('unit_price','fx_to_cny','shipping_total','tax_rate'):
        s=s.replace(',','')
        if field=='tax_rate' and s.endswith('%'):
            from decimal import Decimal,InvalidOperation
            try:return str(Decimal(s[:-1])/100)
            except InvalidOperation:return s
    return s

def text_records(text,locator):
    records=[];values={};evidence={}
    def flush():
        nonlocal values,evidence
        if 'part_number' in values:records.append((values,evidence))
        values={};evidence={}
    for n,line in enumerate(text.splitlines(),1):
        if not line.strip():
            if 'part_number' in values:flush()
            continue
        match=re.match(r'^\s*([^:：]{1,60})\s*[:：]\s*(.*?)\s*$',line)
        if not match:continue
        field=KEYS.get(key(match[1]))
        if not field:continue
        if field=='part_number' and field in values:flush()
        value=normalized(field,match[2])
        if value is None:continue
        values[field]=value;evidence[field]={'locator':f'{locator} / line {n}','raw_text':line,'extracted_value':value}
    flush();return records

def xlsx_records(raw,label):
    import zipfile
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist())>50*1024*1024:raise ValueError('工作簿解压体积超过50MB')
    from openpyxl import load_workbook
    book=load_workbook(BytesIO(raw),read_only=True,data_only=False);records=[];notes=[]
    try:
        if len(book.worksheets)>20:raise ValueError('工作表超过20个，转人工核对')
        for sheet in book:
            headers=None
            for rownum,row in enumerate(sheet.iter_rows(max_row=min(sheet.max_row,1001),max_col=min(sheet.max_column,101)),1):
                if rownum>1000:notes.append(f'{label}/{sheet.title}只读取前1000行');break
                if len(row)>100:raise ValueError('列数超过100，转人工核对')
                mapped={i:KEYS[key(c.value)] for i,c in enumerate(row) if c.value is not None and key(c.value) in KEYS}
                if 'part_number' in mapped.values() and ('unit_price' in mapped.values() or headers is None):headers=mapped;continue
                if not headers:continue
                values={};evidence={}
                for i,field in headers.items():
                    if i>=len(row):continue
                    cell=row[i]
                    if cell.data_type=='f':notes.append(f'公式未执行：{sheet.title}!{cell.coordinate}');continue
                    value=normalized(field,cell.value)
                    if value is not None:values[field]=value;evidence[field]={'locator':f'{label}/{sheet.title}!{cell.coordinate}','raw_text':str(cell.value),'extracted_value':value}
                if 'part_number' in values:records.append((values,evidence))
                if len(records)>100:raise ValueError('报价超过100条，请拆分文件')
    finally:book.close()
    return records,notes

def parse(raw,name):
    suffix=Path(name).suffix.lower();notes=[];rows=[]
    if suffix=='.xlsx':return xlsx_records(raw,name)
    if suffix=='.pdf':
        import pymupdf
        with pymupdf.open(stream=raw,filetype='pdf') as doc:
            if doc.is_encrypted or len(doc)>30:raise ValueError('加密或超过30页的PDF需人工核对')
            for n,page in enumerate(doc,1):
                text=page.get_text(sort=True)
                if not text.strip():notes.append(f'{name}第{n}页无文字层；未运行OCR，转人工录入')
                rows+=text_records(text,f'{name} / page {n}')
    elif suffix=='.eml':
        from email import policy
        from email.parser import BytesParser
        msg=BytesParser(policy=policy.default).parsebytes(raw);attachments=0
        for part in msg.walk():
            filename=part.get_filename()
            if filename and Path(filename).suffix.lower() in ('.pdf','.xlsx','.txt'):
                attachments+=1
                if attachments>10:raise ValueError('供应商附件超过10个，请拆分')
                sub,subnotes=parse(part.get_payload(decode=True) or b'',filename);rows+=sub;notes+=subnotes
            elif part.get_content_type()=='text/plain' and part.get_content_disposition()!='attachment':rows+=text_records(str(part.get_content()),name+' / body')
    elif suffix=='.txt':rows=text_records(raw.decode('utf-8-sig'),name)
    else:raise ValueError('不支持的供应商文件格式')
    if len(rows)>100:raise ValueError('提取超过100条，请拆分文件')
    return rows,notes

def extract(con,source_id):
    source=con.execute('SELECT * FROM source_files WHERE id=?',(source_id,)).fetchone()
    if not source or source['kind']!='supplier_quote':raise ValueError('供应商原件不存在')
    rows,notes=parse(source['content'],source['filename']);at=stamp();candidates=[]
    for i,(values,fields) in enumerate(rows):
        for f in fields.values():f.update(source_id=source_id,source_sha256=source['sha256'],method='local_label_or_table_parser',extracted_at=at)
        candidates.append({'index':i,'values':values,'field_evidence':fields,'missing_fields':sorted(REQUIRED-set(values)),'review_required':True})
    if not candidates:notes.append('没有识别到明确的型号字段报价行；未猜测数值，转人工录入')
    result={'id':'SUPX-'+uuid4().hex[:16],'source_id':source_id,'source_sha256':source['sha256'],'method':'local_label_or_table_parser','model_called':False,'simulated':False,'candidates':candidates,'notes':notes,'status':'suggestions_only','trust_note':'规则解析真实上传内容，不是外部AI或联网结果；所有字段须由人工对照原件确认'}
    from .store import audit
    with con:
        con.execute('INSERT INTO supplier_extraction_runs VALUES(?,?,?,?,?)',(result['id'],source_id,source['sha256'],encoded(result),at))
        audit(con,'supplier_source_extracted',result['id'],{'source_id':source_id,'candidate_count':len(candidates),'method':result['method']})
    return result

def evidence_for_offer(con,payload):
    rid=payload.get('extraction_run_id')
    if not rid:return {'method':'human_structured','note':'由人对照原件录入；未声明自动提取'}
    row=con.execute('SELECT * FROM supplier_extraction_runs WHERE id=?',(rid,)).fetchone()
    if not row or row['source_id']!=payload['source_id']:raise ValueError('提取建议与报价原件不匹配')
    candidates=json.loads(row['result_json'])['candidates'];index=payload.get('extraction_candidate')
    if type(index) is not int or not 0<=index<len(candidates):raise ValueError('提取建议行不存在')
    suggestion=candidates[index]
    return {'method':'local_extraction_then_human_confirmation','run_id':rid,'candidate_index':index,'original_values':suggestion['values'],'field_evidence':suggestion['field_evidence'],'human_changed_fields':{k:{'extracted':v,'confirmed':payload.get(k)} for k,v in suggestion['values'].items() if str(payload.get(k))!=str(v)}}
