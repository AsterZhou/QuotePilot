"""Local source extraction adapters. Suggestions are never executable quotations.
Supported: labelled text/PDF, tabular XLSX, EML body and PDF/XLSX attachments.
No model invocation, guessed prices, OCR confidence probabilities or silent defaults.
"""
from datetime import date,datetime
from io import BytesIO
import json,re,sqlite3
from pathlib import Path
from uuid import uuid4
from .provenance import stamp,encoded

ALIASES={
 'supplier':['supplier','供应商','供应商名称'], 'part_number':['part number','part_number','pn','零件型号','件号','零件编号'],
 'specification':['specification','spec','技术规格','规格'], 'unit':['unit','uom','单位'],
 'condition':['condition','件状','件状条件'], 'currency':['currency','币种'], 'unit_price':['unit price','price','单价'],
 'fx_to_cny':['fx to cny','汇率','汇率到CNY'], 'fx_source':['fx source','汇率依据'], 'moq':['moq','最小起订量','最低起订量'],
 'lead_days':['lead days','交期天数'], 'shipping_total':['shipping total','运费'],
 'shipping_scope':['shipping scope','运费范围'], 'shipping_group':['shipping group','运输批次'],
 'tax_rate':['tax rate','税率'], 'quote_date':['quote date','报价日期'], 'valid_until':['valid until','有效期','有效期至'],
 'payment_terms':['payment terms','付款条件']}
REQUIRED=set(ALIASES)-{'shipping_scope','shipping_group'}
ALIASES.update({
    'resource_id': ['价格资源编号'], 'supplier_code': ['供应商编码'],
    'supplier_type': ['供应商类型'], 'region': ['国家地区'], 'in_stock': ['是否现货'],
    'certificate': ['证书类型'], 'price_status': ['价格状态'], 'notes': ['备注'],
})
PAGE_SIZE = 100
MAX_ROWS = 1000
MAX_CELLS = 100000

def key(s):return re.sub(r'[\s_\-]','',str(s)).lower()
KEYS={key(alias):field for field,aliases in ALIASES.items() for alias in aliases+[field]}

def install(con):
    con.execute('CREATE TABLE IF NOT EXISTS supplier_extraction_runs(id TEXT PRIMARY KEY,source_id TEXT NOT NULL,source_sha256 TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL)')
    con.execute("""CREATE TABLE IF NOT EXISTS supplier_candidate_pages(
        run_id TEXT NOT NULL, page INTEGER NOT NULL, candidates_json TEXT NOT NULL,
        PRIMARY KEY(run_id,page))""")
    con.execute("""CREATE TABLE IF NOT EXISTS supplier_candidate_offers(
        run_id TEXT NOT NULL, candidate INTEGER NOT NULL, offer_id TEXT NOT NULL,
        PRIMARY KEY(run_id,candidate))""")
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

def iter_workbook(raw, label, notes):
    import zipfile
    from openpyxl import load_workbook
    with zipfile.ZipFile(BytesIO(raw)) as archive:
        if sum(i.file_size for i in archive.infolist()) > 50*1024*1024:
            raise ValueError('工作簿解压体积超过50MB')
    book = load_workbook(BytesIO(raw), read_only=True, data_only=False)
    scanned = 0
    candidates = 0
    try:
        if len(book.worksheets) > 20:
            raise ValueError('工作表超过20个，转人工核对')
        for sheet in book:
            # Traverse actual XML rather than trusting missing or stale worksheet dimensions.
            sheet.reset_dimensions()
            headers = {}
            for n, row in enumerate(sheet.iter_rows(), 1):
                scanned += len(row)
                if n > MAX_ROWS + 1 or len(row) > 100 or scanned > MAX_CELLS:
                    raise ValueError(f'{sheet.title} 第{n}行超出工作簿处理上限，请拆分后重新上传')
                mapped = {i: KEYS[key(c.value)] for i,c in enumerate(row)
                          if c.value is not None and key(c.value) in KEYS}
                if 'part_number' in mapped.values() and ('unit_price' in mapped.values() or not headers):
                    if len(set(mapped.values())) != len(mapped):
                        raise ValueError(f'{sheet.title} 第{n}行有重复字段，无法确定来源列')
                    headers = {i:(field, str(row[i].value)) for i,field in mapped.items()}
                    continue
                if not headers or not any(c.value is not None for c in row):
                    continue
                values, evidence = {}, {}
                for i, (field, header) in headers.items():
                    if i >= len(row) or row[i].value is None:
                        continue
                    cell = row[i]
                    if len(str(cell.value)) > 2000:
                        raise ValueError(f'{sheet.title}!{cell.coordinate} 字段超过2000字')
                    value = None if cell.data_type == 'f' else normalized(field, cell.value)
                    conversion = ('公式未执行' if cell.data_type == 'f' else
                                  'Excel日期转ISO日期' if isinstance(cell.value,date) else
                                  '保留原值或按字段规范转换')
                    evidence[field] = {'locator': f'{label}/{sheet.title}!{cell.coordinate}',
                                       'sheet': sheet.title, 'row': n, 'cell': cell.coordinate,
                                       'header':header, 'raw_text':str(cell.value),
                                       'extracted_value':value, 'conversion':conversion}
                    if cell.data_type == 'f':
                        notes.append(f'公式未执行：{sheet.title}!{cell.coordinate}')
                    if value is not None:
                        values[field] = value
                if 'part_number' not in values:
                    notes.append(f'{sheet.title} 第{n}行件号缺失，保留待核对')
                candidates += 1
                if candidates > MAX_ROWS:
                    raise ValueError(f'全工作簿超过{MAX_ROWS}条候选，请拆分后重试')
                yield values,evidence
            if not headers:
                notes.append(f'{sheet.title} 未识别件号表头，需核对原表')
    finally:
        book.close()

def xlsx_records(raw,label):
    notes = []
    return list(iter_workbook(raw,label,notes)), notes

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
    if source['filename'].lower().endswith('.xlsx'):
        return extract_workbook(con, source)
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

def candidate_page(con, run_id, page):
    row = con.execute('SELECT result_json FROM supplier_extraction_runs WHERE id=?',(run_id,)).fetchone()
    if not row:
        raise ValueError('提取尚未完成，请对同一原件重试')
    result = json.loads(row[0])
    if page < 0 or page >= max(1, result.get('page_count',1)):
        raise ValueError('候选页不存在')
    if result.get('paged'):
        data = con.execute('SELECT candidates_json FROM supplier_candidate_pages WHERE run_id=? AND page=?',
                           (run_id,page)).fetchone()
        result['candidates'] = json.loads(data[0]) if data else []
    return {**result, 'page':page}

def extract_workbook(con, source):
    from itertools import islice
    from .store import audit
    # A parser version and immutable content ID uniquely identify resumable pages.
    run_id = 'SUPX-W1-' + source['sha256']
    if con.execute('SELECT 1 FROM supplier_extraction_runs WHERE id=?',(run_id,)).fetchone():
        return candidate_page(con,run_id,0)
    notes, count, page = [], 0, 0
    price_resource = False
    at = source['imported_at']
    stream = iter_workbook(source['content'],source['filename'],notes)
    try:
        while True:
            batch = list(islice(stream,PAGE_SIZE))
            if not batch:
                break
            candidates = []
            for values, fields in batch:
                price_resource |= bool({"resource_id","price_status"} & fields.keys())
                for field in fields.values():
                    field.update(source_id=source['id'],source_sha256=source['sha256'],
                                 method='local_label_or_table_parser',extracted_at=at)
                candidates.append({'index':count,'values':values,'field_evidence':fields,
                                   'missing_fields':sorted(REQUIRED-values.keys()),'review_required':True})
                count += 1
            with con:
                con.execute('INSERT OR IGNORE INTO supplier_candidate_pages VALUES(?,?,?)',
                            (run_id,page,encoded(candidates)))
            page += 1
    except (ValueError, OSError, sqlite3.DatabaseError) as error:
        raise ValueError(f'第{page+1}批失败，已保存{page}批；可重试同一文件。{error}') from error
    finally:
        stream.close()
    if not count:
        notes.append('未识别到候选，请核对原表')
    result = {'id':run_id,'source_id':source['id'],'source_sha256':source['sha256'],
              'method':'local_label_or_table_parser','model_called':False,'simulated':False,
              'notes':notes,'status':'suggestions_only','paged':True,'total':count,
              'page_count':page,'page_size':PAGE_SIZE,'price_resource':price_resource,
              'trust_note':'工作簿原值仅作复核候选。单位、规格、费用和有效性须按原件及补充凭据确认。'}
    with con:
        inserted = con.execute('INSERT OR IGNORE INTO supplier_extraction_runs VALUES(?,?,?,?,?)',
                               (run_id,source['id'],source['sha256'],encoded(result),stamp()))
        if inserted.rowcount:
            audit(con,'supplier_source_extracted',run_id,{'source_id':source['id'],'candidate_count':count,'pages':page})
    return candidate_page(con,run_id,0)

def evidence_for_offer(con,payload):
    rid=payload.get('extraction_run_id')
    if not rid:
        official = con.execute("""SELECT 1 FROM source_files s WHERE s.id=? AND
            (s.filename='价格资源表_演示数据.xlsx' OR EXISTS (
                SELECT 1 FROM source_files w WHERE w.sha256=s.sha256 AND w.kind='workbook'
                AND w.filename='价格资源表_演示数据.xlsx') OR EXISTS (
                SELECT 1 FROM supplier_extraction_runs x WHERE x.source_id=s.id
                AND json_extract(x.result_json,'$.price_resource')=1))""",(payload['source_id'],)).fetchone()
        if official:
            raise ValueError('请先提取价格资源原件并选择具体候选行，保留来源单元格')
        return {'method':'human_structured','note':'由人对照原件录入；未声明自动提取'}
    row=con.execute('SELECT * FROM supplier_extraction_runs WHERE id=?',(rid,)).fetchone()
    if not row or row['source_id']!=payload['source_id']:raise ValueError('提取建议与报价原件不匹配')
    index = payload.get('extraction_candidate')
    if type(index) is not int or index < 0:
        raise ValueError('提取建议行不存在')
    page, offset = divmod(index, PAGE_SIZE)
    candidates = candidate_page(con,rid,page)['candidates']
    if offset >= len(candidates):
        raise ValueError('提取建议行不存在')
    suggestion = candidates[offset]
    original = suggestion['values']
    changed = {k:{'extracted':original.get(k),'confirmed':payload[k]} for k in REQUIRED
               if k in payload and str(payload[k]) != str(original.get(k))}
    if json.loads(row['result_json']).get('price_resource') or 'resource_id' in original or 'price_status' in original:
        if original.get('price_status') not in ('有效','valid','VALID'):
            raise ValueError('价格资源状态无效或缺失，须取得新的供应商报价原件')
        if original.get('valid_until') != payload['valid_until'] or original.get('quote_date') != payload['quote_date']:
            raise ValueError('资源日期不得改写，续价请提供新的报价原件')
        if not (payload.get('supplement_basis') or '').strip():
            raise ValueError('请记录核实当前有效性、库存、证书、单位、规格及费用条件的补充凭据')
    return {'method':'local_extraction_then_human_confirmation','run_id':rid,'candidate_index':index,
            'original_values':original,'field_evidence':suggestion['field_evidence'],
            'human_changed_fields':changed,'supplement_basis':payload.get('supplement_basis')}
