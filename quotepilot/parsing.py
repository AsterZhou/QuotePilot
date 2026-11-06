"""Real RFQ EML / embedded PDF / XLSX parser for supplied challenge samples."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from decimal import Decimal
import json
from email import policy
from email.parser import BytesParser
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
import hashlib
import re
import fitz
from .xlsxio import read_xlsx
from .fields import canonical,validate_headers


class HTMLTables(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.in_cell = False
        self.cell_fragments: list[str] = []
        self.row: list[str] = []
        self.rows: list[list[str]] = []
        self.tables = []
    def handle_starttag(self, tag, attrs):
        if tag == 'table':
            self.depth += 1
            if self.depth==1:self.rows=[]
        elif self.depth and tag == 'tr': self.row = []
        elif self.depth and tag in ('td', 'th'):
            self.in_cell = True
            self.cell_fragments = []
    def handle_data(self, data):
        if self.in_cell: self.cell_fragments.append(data)
    def handle_endtag(self, tag):
        if self.depth and tag in ('td','th') and self.in_cell:
            self.row.append(' '.join(''.join(self.cell_fragments).split()))
            self.in_cell = False
        elif self.depth and tag == 'tr':
            if self.row: self.rows.append(self.row)
        elif tag == 'table' and self.depth:
            if self.depth==1:self.tables.append(self.rows)
            self.depth -= 1


def parse_pdf(raw: bytes, filename: str) -> list[dict[str, str]]:
    """Extract specific official RFQ quote-form layout; no OCR or invented values."""
    with fitz.open(stream=raw,filetype='pdf') as doc:
        header=doc[0].get_text(sort=False) if len(doc) else ''
        # A row-shaped sequence alone cannot establish that a document is an RFQ.
        match=re.search(r'REQUEST FOR QUOTATION\s*#\s*(RFQ-[0-9A-Z][0-9A-Z._-]*)',header,re.I)
        if not match:raise ValueError('未识别可靠的 RFQ 标题；文档用途待人工确认')
        result=[]
        if not any(p.get_text().strip() for p in doc):raise ValueError('PDF无文字层；扫描件请走OCR建议复核或人工录入')
        for page_idx,page in enumerate(doc,1):
            horizontal=_horizontal_pdf(page,page_idx,match.group(1))
            if horizontal:
                result.extend(horizontal);continue
            tokens=[s.strip() for s in page.get_text(sort=False).splitlines() if s.strip()]
            for i,token in enumerate(tokens[:-2]):
                if not re.fullmatch(r'\d{4}',token):continue
                part=tokens[i+1]
                if not re.fullmatch(r'(?=[A-Z0-9.-]*[A-Z])[A-Z0-9][A-Z0-9.-]{2,49}',part):continue
                description=[]
                for candidate in tokens[i+2:i+10]:
                    q=re.fullmatch(r'(\d+)\s+(Each|EA|FT|IN|PCS|PC)',candidate,re.I)
                    if q:
                        if description:
                            result.append({'询价单号':match.group(1),'Part Number':part,'Description':' '.join(description),
                                           'Quantity':q.group(1),'Unit Of Measure':'EA' if q.group(2).lower()=='each' else q.group(2).upper(),
                                           '_source_row':f'page {page_idx} / item {token}'})
                        break
                    if re.fullmatch(r'\d{4}',candidate):break
                    description.append(candidate)
        return result


def _horizontal_pdf(page,page_idx,rfq_no):
    """Only explicit labelled columns; reject ambiguous row alignment."""
    text=page.get_text(sort=True);lines=[x.strip() for x in text.splitlines() if x.strip()]
    for i,line in enumerate(lines):
        labels=re.split(r'\s{2,}|\t+',line)
        names=[canonical(x) for x in labels]
        if {'Part Number','Quantity','Unit Of Measure'}.issubset(set(names)):
            validate_headers(labels);result=[]
            for j,body in enumerate(lines[i+1:],i+2):
                cells=re.split(r'\s{2,}|\t+',body)
                if len(cells)!=len(labels):
                    # A non-row footer may be ignored only if it has no table-shaped content.
                    if re.search(r'\b(?:EA|PCS|FT|IN|Each)\b',body,re.I) or len(cells)>1:raise ValueError(f'PDF page {page_idx} 横向第{j}行列数不符，需人工处理')
                    continue
                if [canonical(x) for x in cells]==names:continue
                rec=dict(zip(names,cells));rec['询价单号']=rec.get('询价单号') or rec.get('RFQ No') or rfq_no
                rec['_source_row']=f'page {page_idx} / horizontal row {j}'
                if not re.fullmatch(r'[1-9]\d*',rec.get('Quantity','')):raise ValueError(f'PDF page {page_idx} 横向数量不可靠，需人工处理')
                result.append(rec)
            return result
    # Coordinate-based tables: headings can be separate text objects on one line.
    words=page.get_text('words');bands=[]
    for w in sorted(words,key=lambda w:(round(w[1]/3),w[0])):
        band=next((b for b in bands if abs(b[0][1]-w[1])<3),None)
        if band is None:bands.append([w])
        else:band.append(w)
    for idx,band in enumerate(bands):
        band=sorted(band,key=lambda w:w[0]);heads=[];k=0
        while k<len(band):
            found=False
            for count in (3,2,1):
                phrase=' '.join(w[4] for w in band[k:k+count])
                name=canonical(phrase)
                if name in ('Part Number','Quantity','Unit Of Measure','Description','件状条件','RFQ No','询价单号'):
                    heads.append((band[k][0],name));k+=count;found=True;break
            if not found:k+=1
        if not {'Part Number','Quantity','Unit Of Measure'}.issubset({h[1] for h in heads}):continue
        validate_headers([h[1] for h in heads]);result=[]
        starts=[h[0]-3 for h in heads]
        for row in bands[idx+1:]:
            values=['']*len(heads)
            for w in sorted(row,key=lambda w:w[0]):
                col=max((c for c,x in enumerate(starts) if w[0]>=x),default=-1)
                if col>=0:values[col]+=(' ' if values[col] else '')+w[4]
            record=dict(zip([h[1] for h in heads],values))
            if not record.get('Part Number'):continue
            if not re.fullmatch(r'[1-9]\d*',record.get('Quantity','')):raise ValueError('PDF横向表格字段未对齐，需人工核对')
            record['询价单号']=record.get('询价单号') or record.get('RFQ No') or rfq_no
            record['_source_row']=f'page {page_idx} / y {min(w[1] for w in row):.1f}'
            record['_source_bbox']=[min(w[0] for w in row),min(w[1] for w in row),max(w[2] for w in row),max(w[3] for w in row)]
            result.append(record)
        return result
    return []


def normalize_line(raw:dict[str,str], source:str, source_kind:str, customer:str, mail_id:str) -> dict:
    def field(*names):
        for n in names:
            if raw.get(n) not in ('', None):return str(raw[n]).strip()
        return ''
    q=field('Quantity','数量')
    if not re.fullmatch(r'\d+(?:\.0+)?',q):
        raise ValueError(f'Unrecognized quantity {q!r} for {field("Part Number")}')
    if not field('Part Number','Part No','PN'):raise ValueError('件号缺失；保留原始行待人工修复')
    if Decimal(q)<=0 or Decimal(q)>Decimal('9007199254740991'):raise ValueError('数量必须为正整数且不超过精确存储上限')
    return {
        'source_rfq_no':field('询价单号','RFQ No.','RFQ No'),
        'part_number':field('Part Number','Part No','PN').upper(),
        'description':field('Description','品名'),
        'quantity':int(Decimal(q)),
        'raw_record':raw,
        'extraction_status':'待确认' if not field('Part Number','Part No','PN') or not field('Unit Of Measure','Unit of Measure','Unit') else '已解析',
        'unit':field('Unit Of Measure','Unit of Measure','Unit of Measure','Unit').upper(),
        'urgency':field('优先级','紧急程度'),
        'condition':field('件状条件','Condition').upper(),
        'mpn':field('询价MPN','MPN'),
        'deadline':field('截止报价日期','Due Date','Respond by'),
        'product_scope':field('产品范围'),
        'customer':customer,
        'email_id':mail_id,
        'source_kind':source_kind,
        'source':f'{source} · {raw.get("_source_row", "row ?")}',
    }


def parse_eml(raw:bytes, filename:str) -> dict:
    msg=BytesParser(policy=policy.default).parsebytes(raw)
    ident=str(msg.get('Message-ID') or hashlib.sha256(raw).hexdigest())
    sender=str(msg.get('From') or '')
    customer=sender.split('<')[0].strip().strip('"')
    subject=str(msg.get('Subject') or filename)
    if not msg.get('From') and not msg.get('Subject'):
        raise ValueError('缺少邮件头，无法识别标准 EML')
    email_record={'message_id':ident,'sha256':hashlib.sha256(raw).hexdigest(),
                  'filename':filename,'sender':sender,'subject':subject,'date':str(msg.get('Date') or ''),
                  'lines':[], 'attachments':[], 'parse_notes':[], 'rejected_rows':[],
                  'body': '\n'.join(p.get_content() for p in msg.walk() if p.get_content_type() in ('text/plain','text/html') and p.get_content_disposition()!='attachment')}
    def append_record(record, source, kind):
        try:
            # Preserve raw headers/cells; normalize only the separate working copy.
            validate_headers([k for k in record if not k.startswith('_')])
            normalized={canonical(k):v for k,v in record.items()}
            item=normalize_line(normalized,source,kind,customer,ident)
            item['raw_record']=record
            email_record['lines'].append(item)
        except (ValueError,OverflowError) as ex:
            email_record['parse_notes'].append(str(ex))
            email_record['rejected_rows'].append({'raw':record,'source':source,'reason':str(ex)})
    htmls=[p.get_content() for p in msg.walk() if p.get_content_type()=='text/html' and p.get_content_disposition()!='attachment']
    for html_idx,html in enumerate(htmls,1):
        parser=HTMLTables();parser.feed(html)
        for table_idx,tbl in enumerate(parser.tables,1):
            if not tbl or 'Part Number' not in {canonical(x) for x in tbl[0]}:
                email_record['parse_notes'].append(f'HTML part {html_idx} / table {table_idx}: 未识别标准 Part Number 表头，需人工核对')
                continue
            headers=tbl[0]
            try:validate_headers(headers)
            except ValueError as ex:
                email_record['parse_notes'].append(str(ex));email_record['rejected_rows'].append({'raw':{'headers':headers,'rows':tbl[1:]},'source':filename,'reason':str(ex)});continue
            for i,row in enumerate(tbl[1:],2):
                record=dict(zip(headers,row));record['_source_row']=f'HTML part {html_idx} / table {table_idx} / row {i}'
                if any(str(v).strip() for v in row):append_record(record,filename,'EML正文表格')
    if not htmls:
        for text_idx,part in enumerate((p for p in msg.walk() if p.get_content_type()=='text/plain' and not p.get_filename()),1):
            record={};raw_lines=[]
            def flush_plain():
                if 'Part Number' in record or 'Quantity' in record:
                    record['_source_row']=f'plain part {text_idx} / record {len(email_record["lines"])+1}'
                    record['_raw_text']='\n'.join(raw_lines)
                    append_record(dict(record),filename,'EML结构化文本')
            for text_line in part.get_content().splitlines():
                pair=re.fullmatch(r'\s*([^:：]{1,50})\s*[:：]\s*(.*?)\s*',text_line)
                if not pair:continue
                key,value=canonical(pair.group(1)),pair.group(2)
                if key=='Part Number' and 'Part Number' in record:
                    flush_plain();record={};raw_lines=[]
                if key in record and key!='Part Number':
                    email_record['parse_notes'].append('纯文本字段重复，整段待人工确认：'+key)
                    record={};raw_lines=[];break
                record[key]=value;raw_lines.append(text_line)
            flush_plain()
    for part in msg.walk():
        if part.get_content_disposition()!='attachment' and not part.get_filename(): continue
        part_name=part.get_filename() or 'untitled'
        data=part.get_payload(decode=True) or b''
        email_record['attachments'].append({'filename':part_name,'size':len(data),'sha256':hashlib.sha256(data).hexdigest()})
        try:
            if part_name.lower().endswith('.xlsx'):
                items=read_xlsx(data);kind='EML Excel附件'
                email_record['parse_notes'].extend(getattr(items,'notes',[]))
            elif part_name.lower().endswith('.pdf'):
                items=parse_pdf(data,part_name);kind='EML PDF附件'
                if not items: email_record['parse_notes'].append(f'{part_name}: 未识别表格行；待人工确认或模型提取')
            else:
                email_record['parse_notes'].append(f'Unsupported attachment: {part_name}')
                continue
            for row in items:
                if any(str(v).strip() for k,v in row.items() if not k.startswith('_')):append_record(row,f'{filename} / {part_name}',kind)
        except Exception as ex:
            email_record['parse_notes'].append(f'{part_name}: {type(ex).__name__}: {ex}')
    if not email_record['lines']: email_record['parse_notes'].append('没有可靠提取的需求行；请人工录入或使用提取 Provider')
    return email_record


def file_preview(path:Path) -> dict:
    return parse_eml(path.read_bytes(),path.name)
