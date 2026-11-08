"""QuotePilot v0.7: local rules, optional real Genesis and MOI quote mirror."""
from __future__ import annotations
from contextlib import contextmanager, asynccontextmanager
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path
import json
import os
import re
import sqlite3
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from quotepilot.store import open_db, seed_official, ingest_eml, audit
from quotepilot.reviews import create_quote,load_quote,change_quote
from quotepilot.pricing import supplier_issues
from quotepilot.analytics import summary, run_query, QUESTIONS
from quotepilot.pricing import batch_quote, D
from quotepilot.exports import quote_docx, quote_csv, audit_json
from quotepilot.parsing import parse_eml

ROOT = Path(__file__).resolve().parent
DB = Path(os.environ.get('QUOTEPILOT_DB',str(ROOT / 'workspace' / 'quotepilot.db')))
SAMPLES = ROOT / 'workspace' / 'samples'
WEB = ROOT / 'web'

@asynccontextmanager
async def lifespan(app):
    from quotepilot.security import validate_production
    validate_production()
    con=open_db(DB)
    try:seed_official(con,SAMPLES)
    finally:con.close()
    yield

app = FastAPI(title='QuotePilot — 报价室',version='0.7.0',docs_url='/api/docs',lifespan=lifespan)
from quotepilot.security import DemoAccessMiddleware
app.add_middleware(DemoAccessMiddleware)
app.mount('/assets',StaticFiles(directory=WEB),name='assets')

@contextmanager
def database():
    con = open_db(DB)
    try: yield con
    finally: con.close()

@app.get('/', response_class=HTMLResponse)
def index():
    from quotepilot.security import deployment_notice
    return (WEB / 'index.html').read_text(encoding='utf-8').replace('<body>','<body>'+deployment_notice(),1)

@app.get('/healthz')
def readiness():return {'ok':True,'service':'QuotePilot'}

@app.get('/api/health')
def health():
    with database() as con:
        from quotepilot.integration_status import integration_status
        status=integration_status(con)
        return {'ok':True,'version':'0.7.0','mode':status['mode'],'moi_connected':status['moi_connected'],
                'matrixone_connected':status['matrixone_connected'],'model_connected':status['model_connected'],'stats':summary(con)}

@app.get('/api/overview')
def overview():
    with database() as con:
        s = summary(con)
        s['source_kinds']=[dict(r) for r in con.execute('''SELECT source_kind AS kind, COUNT(*) AS count FROM rfq_lines GROUP BY source_kind ORDER BY count DESC''')]
        s['mail_counts']=[dict(r) for r in con.execute('''SELECT e.email_id, e.subject,e.filename,e.mail_date, COUNT(l.id) AS line_count,
          COUNT(DISTINCT l.source_rfq_no) AS rfq_count FROM emails e LEFT JOIN rfq_lines l ON e.email_id=l.email_id
          GROUP BY e.email_id ORDER BY e.filename''')]
        s['history_distinct_parts']=con.execute('SELECT COUNT(DISTINCT part_number) FROM historical').fetchone()[0]
        s['last_import']=con.execute('SELECT MAX(imported_at) FROM emails').fetchone()[0]
        return s

@app.get('/api/emails')
def emails():
    with database() as con:
        return [dict(x) for x in con.execute('''SELECT e.email_id,e.filename,e.subject,e.sender,e.mail_date,
          COUNT(l.id) AS line_count, GROUP_CONCAT(DISTINCT l.source_kind) AS kinds,
          COUNT(DISTINCT l.source_rfq_no) AS source_rfq_count,
          (SELECT dataset FROM source_files f WHERE f.email_id=e.email_id AND f.kind='eml' LIMIT 1) AS dataset
          FROM emails e LEFT JOIN rfq_lines l ON l.email_id=e.email_id
          GROUP BY e.email_id ORDER BY e.filename''')]

@app.get('/api/lines')
def lines(email_id:str|None=None, search:str='', source_kind:str='', limit:int=Query(500,ge=1,le=1000), offset:int=Query(0,ge=0)):
    filters=[];args=[]
    if email_id:
        filters.append('l.email_id=?');args.append(email_id)
    if search.strip():
        filters.append('(l.part_number LIKE ? OR l.description LIKE ? OR l.source_rfq_no LIKE ?)')
        x='%'+search.strip()[:80]+'%';args.extend([x,x,x])
    if source_kind:
        filters.append('l.source_kind=?');args.append(source_kind)
    wh=' WHERE ' + ' AND '.join(filters) if filters else ''
    with database() as con:
        n=con.execute('SELECT COUNT(*) FROM rfq_lines l'+wh,args).fetchone()[0]
        rows=[dict(r) for r in con.execute('''SELECT l.*,e.subject AS email_subject,e.filename AS email_filename
          FROM rfq_lines l JOIN emails e ON e.email_id=l.email_id'''+wh+' ORDER BY e.filename,l.id LIMIT ? OFFSET ?',args+[limit,offset])]
    return {'total':n,'rows':rows,'offset':offset,'limit':limit}

@app.get('/api/catalog/{kind}')
def catalog(kind:Literal['historical','prices','costs'], search:str=Query('',max_length=100),
            limit:int=Query(25,ge=1,le=100), offset:int=Query(0,ge=0)):
    # Table and column identifiers come only from this fixed map. Values stay bound.
    specs={
        'historical':('historical',['rfq_no','inquiry_no','part_number','description','airline'],'id'),
        'prices':('prices',['resource_id','part_number','supplier','supplier_code'],'resource_id'),
        'costs':('costs',['part_number','description','warehouse'],'part_number'),
    }
    table,columns,order=specs[kind]
    where='';args=[]
    if search.strip():
        needle=search.strip().replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
        where=' WHERE '+' OR '.join(f"{column} LIKE ? ESCAPE '\\'" for column in columns)
        args=['%'+needle+'%']*len(columns)
    with database() as con:
        total=con.execute(f'SELECT COUNT(*) FROM {table}'+where,args).fetchone()[0]
        rows=[dict(row) for row in con.execute(f'SELECT * FROM {table}'+where+f' ORDER BY {order} LIMIT ? OFFSET ?',args+[limit,offset])]
        files=[dict(row) for row in con.execute("SELECT id,filename,dataset FROM source_files WHERE kind='workbook' ORDER BY filename")]
    expected={'historical':'询价报价清单_看板演示数据.xlsx','prices':'价格资源表_演示数据.xlsx','costs':'内部物料成本表_演示数据.xlsx'}[kind]
    return {'total':total,'rows':rows,'offset':offset,'limit':limit,'dataset':'official_sample',
            'source_files':[f for f in files if f['filename']==expected]}

@app.get('/api/lines/{line_id}')
def line_detail(line_id:int):
    with database() as con:
        row=con.execute('''SELECT l.*,e.subject AS email_subject,e.sender,e.mail_date,e.filename
             FROM rfq_lines l JOIN emails e ON e.email_id=l.email_id WHERE l.id=?''',(line_id,)).fetchone()
        if row is None: raise HTTPException(status_code=404, detail='未找到原始询价行')
        result=dict(row)
        ev=con.execute('SELECT * FROM line_evidence WHERE line_id=?',(line_id,)).fetchone()
        result['evidence']=dict(ev) if ev else None
        result['files']=[dict(x) for x in con.execute('SELECT id,filename,sha256,kind,dataset,parent_id FROM source_files WHERE email_id=?',(row['email_id'],))]
        result['pricing_workbooks']=[dict(x) for x in con.execute("SELECT id,filename,sha256 FROM source_files WHERE kind='workbook'")]
        result['parse_issues']=[dict(x) for x in con.execute('SELECT source_ref,reason,raw_json FROM parse_issues WHERE email_id=?',(row['email_id'],))]
        return result

@app.post('/api/emails/preview')
async def preview_email(file:UploadFile=File(...)):
    raw = await _read_eml(file)
    try: obj = parse_eml(raw,file.filename or 'upload.eml')
    except Exception as e: raise HTTPException(422, f'邮件解析失败：{e}')
    return {'filename':obj['filename'],'subject':obj['subject'],'sender':obj['sender'],
            'count':len(obj['lines']),'sample_lines':obj['lines'][:12],
            'notes':obj['parse_notes'],'attachments':obj['attachments'],'status':'needs_review' if obj['parse_notes'] or not obj['lines'] else 'parsed'}

@app.post('/api/emails/import')
async def import_email(file:UploadFile=File(...)):
    raw=await _read_eml(file)
    try:
        with database() as con:
            before=con.execute('SELECT COUNT(*) FROM rfq_lines').fetchone()[0]
            obj=ingest_eml(con,raw,Path(file.filename or 'upload.eml').name)
            after=con.execute('SELECT COUNT(*) FROM rfq_lines').fetchone()[0]
        return {'ok':True,'status':'needs_review' if obj['parse_notes'] or not obj['lines'] else 'imported','subject':obj['subject'],'parsed_count':len(obj['lines']),
                'new_lines':after-before,'duplicate_lines':len(obj['lines'])-(after-before),
                'notes':obj['parse_notes']}
    except Exception as e: raise HTTPException(422, f'导入失败：{e}')

async def _read_eml(file:UploadFile)->bytes:
    if not (file.filename or '').lower().endswith('.eml'):
        raise HTTPException(415,'仅支持 EML 文件')
    # Do not allow unlimited uploads or untrusted file paths.
    data=await file.read(10*1024*1024+1)
    if len(data)>10*1024*1024:raise HTTPException(413,'EML 超过 10MB 上限')
    if not data:raise HTTPException(422,'空文件')
    return data

class QuoteRequest(BaseModel):
    line_ids:list[int] = Field(default_factory=list, min_length=1, max_length=300)
    asof:date = date(2026,9,20)
    method:Literal['markup','margin'] = 'markup'
    rate:Decimal = Field(default=Decimal('20'),ge=0,lt=100,max_digits=10,decimal_places=6)


def make_quote(con, req:QuoteRequest)->dict:
    ids=list(dict.fromkeys(req.line_ids))
    if len(ids)>100: raise HTTPException(422,'每次最多核价100行')
    values=','.join('?' for _ in ids)
    found={r['id']:dict(r) for r in con.execute('SELECT * FROM rfq_lines WHERE id IN ('+values+')',ids)}
    if len(found)!=len(ids):raise HTTPException(404,'有询价记录不存在，请重新选择')
    source=[found[i] for i in ids]
    feed=[{'part_number':r['part_number'],'quantity':r['quantity'],'unit':r['unit'],'condition':r['part_condition'] or ''} for r in source]
    report=batch_quote(con,feed,req.asof.isoformat(),str(Decimal(str(req.rate))/100),req.method)
    for x,orig in zip(report['lines'],source):
        from quotepilot.provenance import quote_review_snapshot
        x['field_review_version']=quote_review_snapshot(con,orig['id'])
        x['line_id']=orig['id']
        x['source_rfq_no']=orig['source_rfq_no']
        x['source_ref']=orig['source_ref']
        x['email_filename']=con.execute('SELECT filename FROM emails WHERE email_id=?',(orig['email_id'],)).fetchone()[0]
        x['customer']=orig['customer']
        x['description']=orig['description']
        x['urgency']=orig['urgency']
        if x.get('price_basis'):
            name='内部物料成本表_演示数据.xlsx' if x['price_basis']['table']=='costs' else '价格资源表_演示数据.xlsx'
            source_file=con.execute("SELECT id,filename,sha256 FROM source_files WHERE kind='workbook' AND filename=?",(name,)).fetchone()
            x['price_basis']['source_file']=dict(source_file) if source_file else None
    report['dataset']='原始文件及其数据集标签见来源追溯；预置为官方模拟素材，上传为用户数据'
    customers={str(r['customer'] or '').strip().casefold() for r in source if str(r['customer'] or '').strip()}
    report['approval_blockers']=['跨客户明细不得确认为同一份报价，请按客户拆分草案'] if len(customers)>1 else []
    report['review_required']=True
    report['currency']='CNY'
    return report

@app.post('/api/quote')
def quote(req:QuoteRequest):
    with database() as con:return create_quote(con,make_quote(con,req))

@app.post('/api/quote/export/{kind}')
def quote_export(kind:Literal['docx','csv','json'], req:QuoteRequest):
    with database() as con:report=create_quote(con,make_quote(con,req))
    if kind=='docx':
        blob=quote_docx(report,reference='OFFICIAL RFQ DATA / HUMAN REVIEW REQUIRED')
        media='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    elif kind=='csv':
        blob=quote_csv(report);media='text/csv; charset=utf-8'
    else:
        blob=audit_json(report);media='application/json; charset=utf-8'
    return Response(content=blob,media_type=media,headers={'Content-Disposition':f'attachment; filename="QuotePilot_Draft_Quotation.{kind}"',
                                                             'X-Content-Type-Options':'nosniff'})

@app.get('/api/price/candidates')
def candidates(part_number:str,asof:date=date(2026,9,20),condition:str='',quantity:int=Query(1,ge=1)):
    part=part_number.strip().upper()
    with database() as con:
        raw=[dict(x) for x in con.execute('SELECT * FROM prices WHERE part_number=? ORDER BY resource_id',(part,))]
        costs=[dict(x) for x in con.execute('SELECT * FROM costs WHERE part_number=?',(part,))]
    def explain(p):
        issues=supplier_issues(p,asof.isoformat(),condition.upper(),quantity)
        return {**dict(p),'status':'有效候选' if not issues else '不符合条件','issues':issues,
                'review_flags':['供应商单位未提供，必须人工确认'],'converted_cny':str((D(p['unit_price'])*D(p['fx_to_cny'])).quantize(Decimal('.01')))}
    return {'part_number':part,'count':len(raw),'candidates':[explain(p) for p in raw], 'inventory':costs}

@app.get('/api/analytics/questions')
def questions():
    return [{'id':k,'label':k} for k in QUESTIONS]

@app.get('/api/analytics')
def analytics(q:str='每月询价趋势',asof:date=date(2026,9,1)):
    if q not in QUESTIONS:raise HTTPException(400,'仅支持已验证的统计问题')
    from quotepilot.query_sql import readonly
    with readonly(DB) as con:
        rows=run_query(con,q,asof.isoformat())
        s=summary(con)
    return {'question':q,'query_mode':'allowlist_sql_offline','model_connected':False,'rows':rows,
            'sql':QUESTIONS[q],'dataset_rows':s['history_lines'],'rfq_groups':s['history_rfq_groups']}

class NaturalQuery(BaseModel):
    question:str = Field(min_length=2,max_length=300)
    asof:date = date(2026,9,1)

@app.post('/api/analytics/ask')
def ask(req:NaturalQuery):
    text=req.question.strip()
    if not text:raise HTTPException(422,'请填写业务问题')
    if os.environ.get('QUOTEPILOT_PROVIDER','mock')=='genesis':
        from quotepilot.providers import get_provider
        from quotepilot.query_planner import interpret,execute_plan
        try:
            plan,receipt=interpret(get_provider(),text,req.asof.isoformat())
            if not plan.supported:
                return {'supported':False,'question':text,'message':plan.explanation,'query_mode':'genesis_structured_plan',
                        'model_connected':True,'response_id':receipt['response_id'],'model':receipt['model'],'suggestions':list(QUESTIONS)}
            with database() as con:
                result=execute_plan(con,plan)
                audit(con,'analytics_genesis_query',receipt['response_id'],{'question':text,'plan':plan.model_dump(mode='json'),
                      'model':receipt['model'],'response_id':receipt['response_id'],'usage':receipt.get('usage',{}),'result_rows':len(result['rows'])})
                con.commit()
            return {**result,'supported':True,'question':text,'interpreted_as':plan.explanation,'query_mode':'genesis_structured_plan',
                    'model_connected':True,'model':receipt['model'],'response_id':receipt['response_id'],'plan':plan.model_dump(mode='json'),
                    'usage':receipt.get('usage',{})}
        except ValueError:
            raise HTTPException(422,'AI未生成可执行的业务查询，请明确数据范围、筛选条件或统计指标；未执行不受支持的查询。')
        except Exception:
            raise HTTPException(502,'AI查询暂时未完成，请稍后重试或使用上方快捷统计；未生成查询结果。')
    if re.search(r'截止|到期|几天|快到',text): q='即将截止的询价'
    elif re.search(r'紧急|客户|航空公司',text): q='客户紧急询价排名'
    elif re.search(r'件号|零件|物料|热门|频繁',text):q='热门询价件号'
    elif re.search(r'趋势|每月|月份|时间|数量|统计',text):q='每月询价趋势'
    else:
        return {'supported':False,'message':'目前离线版只支持四类已核实的统计问法；模型自然语言转SQL尚未接入。',
                'suggestions':list(QUESTIONS)}
    result=analytics(q,req.asof)
    result['supported']=True;result['interpreted_as']=q
    return result

@app.get('/api/integration')
def integration():
    from quotepilot.integration_status import integration_status
    with database() as con:return integration_status(con)


@app.get('/api/sources/{source_id}/download')
def source_download(source_id:str):
    with database() as con:
        r=con.execute('SELECT * FROM source_files WHERE id=?',(source_id,)).fetchone()
        if not r:raise HTTPException(404,'来源文件不存在')
        return Response(bytes(r['content']),media_type='application/octet-stream',headers={'Content-Disposition':'attachment; filename="source.bin"','X-Content-Type-Options':'nosniff'})

@app.get('/api/quotes')
def quote_history():
    with database() as con:
        return [dict(r) for r in con.execute('SELECT id,created_at,status,version,rule_version FROM quotes ORDER BY created_at DESC,rowid DESC LIMIT 100')]

@app.get('/api/quotes/{qid}')
def saved_quote(qid:str):
    with database() as con:
        try:return load_quote(con,qid)
        except KeyError:raise HTTPException(404,'报价不存在')

class LinePatch(BaseModel):
    line_id:int
    unit_price_cny:Decimal|None=Field(default=None,gt=0,max_digits=16,decimal_places=2)
    evidence_ref:str=Field(default='',max_length=500)
    condition:str|None=Field(default=None,max_length=30)
    lead_days:str|None=Field(default=None,max_length=100)

class ReviewRequest(BaseModel):
    version:int=Field(ge=1)
    actor:str=Field(min_length=1,max_length=100)
    reason:str=Field(min_length=3,max_length=1000)
    patches:list[LinePatch]=Field(default_factory=list,max_length=100)
    approve:bool=False
    confirm_constraints:bool=False

@app.patch('/api/quotes/{qid}')
def review_quote(qid:str,req:ReviewRequest):
    from quotepilot.security import production
    if req.approve and production():raise HTTPException(409,'旧报价仅保留试算及历史归档；新的正式审批须进入商用报价双角色流程')
    with database() as con:
        try:return change_quote(con,qid,req.version,req.actor,req.reason,[p.model_dump(mode='json') for p in req.patches],req.approve,req.confirm_constraints)
        except KeyError:raise HTTPException(404,'报价不存在')
        except ValueError as ex:raise HTTPException(409,str(ex))

@app.get('/api/quotes/{qid}/export/{kind}')
def saved_export(qid:str,kind:Literal['csv','json','xlsx'],final:bool=False):
    from quotepilot.exports import quote_xlsx
    with database() as con:
        try:obj=load_quote(con,qid)
        except KeyError:raise HTTPException(404,'报价不存在')
        if final and obj['review_status']!='approved':raise HTTPException(409,'请先完成人工确认')
        if kind=='csv':blob=quote_csv(obj);media='text/csv; charset=utf-8'
        elif kind=='xlsx':blob=quote_xlsx(obj);media='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        else:blob=audit_json(obj);media='application/json'
        audit(con,'quote_exported',qid,{'version':obj['version'],'format':kind,'final':final});con.commit()
    return Response(blob,media_type=media,headers={'Content-Disposition':f'attachment; filename="{qid}_v{obj["version"]}.{kind}"','X-Content-Type-Options':'nosniff'})

@app.get('/api/audit')
def audit_trail(limit:int=Query(100,ge=1,le=500)):
    with database() as con:return [dict(r) for r in con.execute('SELECT * FROM audit_events ORDER BY id DESC LIMIT ?',(limit,))]

@app.get('/api/exceptions')
def exceptions():
    with database() as con:
        return {'parse_issues':[dict(x) for x in con.execute('SELECT * FROM parse_issues ORDER BY id DESC LIMIT 100')],
                'pending_quotes':[dict(x) for x in con.execute("SELECT id,created_at,status,version FROM quotes WHERE status='draft' ORDER BY rowid DESC LIMIT 50")]}

class RulesRequest(BaseModel):
    method:Literal['markup','margin']='markup'
    rate:Decimal=Field(default=20,ge=0,lt=100)
    asof:date=date(2026,9,20)

@app.get('/api/rules')
def get_rules():
    with database() as con:
        r=con.execute("SELECT value_json FROM settings WHERE key='pricing'").fetchone()
        return json.loads(r[0]) if r else {'method':'markup','rate':20,'asof':'2026-09-20'}

@app.put('/api/rules')
def put_rules(req:RulesRequest):
    obj=req.model_dump(mode='json')
    with database() as con:
        con.execute("INSERT OR REPLACE INTO settings VALUES('pricing',?)",(json.dumps(obj),))
        audit(con,'rules_updated','pricing',obj);con.commit()
    return obj

@app.get('/api/analytics/metrics')
def metrics():
    with database() as con:
        obj=dict(con.execute('SELECT COUNT(DISTINCT rfq_no) AS rfq_count,COUNT(*) AS line_count,COUNT(DISTINCT part_number) AS part_count FROM historical').fetchone())
        rows=con.execute('SELECT report_json FROM quotes').fetchall()
        # Count latest stored versions once per quote, not every audit event.
        obj['quote_draft_amount_cny']=str(sum((Decimal(json.loads(x[0])['total_cny']) for x in rows),Decimal(0)))
        obj['inquiry_amount']=None;obj['amount_note']='历史询价未提供可靠金额，不推算询价金额；报价草案金额单独统计，未代表订单或收入'
        return obj

class ExtractionRequest(BaseModel):
    text:str=Field(min_length=1,max_length=30000)

@app.post('/api/extraction/preview')
def extraction_preview(req:ExtractionRequest):
    from quotepilot.providers import get_provider
    try:return get_provider().extract(req.text)
    except ValueError as e:raise HTTPException(422,str(e))
    except Exception:raise HTTPException(502,'模型服务失败或响应不符合结构约束；未写入业务数据')

@app.post('/api/emails/{email_id}/extract')
def extract_stored_email(email_id:str):
    from quotepilot.extraction_workflow import source_context,create_run
    from quotepilot.providers import get_provider
    try:
        with database() as con:text,refs,notes=source_context(con,email_id)
        result=get_provider().extract(text)
        with database() as con:return create_run(con,email_id,result,text,refs,notes)
    except KeyError as ex:raise HTTPException(404,str(ex))
    except ValueError as ex:raise HTTPException(422,str(ex))
    except Exception:raise HTTPException(502,'模型服务未成功或响应不满足约束；未写入需求行')

class ConfirmSuggestion(BaseModel):
    source_index:int=Field(ge=0)
    part_number:str=Field(min_length=1,max_length=150)
    quantity:int=Field(gt=0,le=9007199254740991,strict=True)
    unit:str=Field(min_length=1,max_length=30)
    condition:str=Field(default='',max_length=30)
    source_rfq_no:str=Field(min_length=1,max_length=100)
    description:str=Field(default='',max_length=1000)

class ConfirmExtraction(BaseModel):
    actor:str=Field(min_length=1,max_length=100)
    reason:str=Field(min_length=3,max_length=1000)
    lines:list[ConfirmSuggestion]=Field(min_length=1,max_length=100)
    confirm_source:bool=False

@app.get('/api/extractions/{rid}')
def extraction_detail(rid:str):
    from quotepilot.extraction_workflow import load_run
    with database() as con:
        try:return load_run(con,rid)
        except KeyError:raise HTTPException(404,'提取记录不存在')

@app.post('/api/extractions/{rid}/confirm')
def confirm_extraction(rid:str,req:ConfirmExtraction):
    from quotepilot.extraction_workflow import confirm_run
    if not req.actor.strip() or not req.reason.strip():raise HTTPException(422,'复核人及原因不能为空白')
    if not req.confirm_source:raise HTTPException(409,'必须明确确认已对照原文核对建议字段')
    with database() as con:
        try:return confirm_run(con,rid,[x.model_dump() for x in req.lines],req.actor.strip(),req.reason.strip())
        except KeyError:raise HTTPException(404,'提取记录不存在')
        except ValueError as ex:raise HTTPException(409,str(ex))

@app.post('/api/quotes/{qid}/sync-matrixone')
def sync_approved_quote(qid:str):
    from quotepilot.moi_sql import sync_quote
    with database() as con:
        try:quote=load_quote(con,qid)
        except KeyError:raise HTTPException(404,'报价不存在')
        if quote['review_status']!='approved':raise HTTPException(409,'仅允许同步已人工确认的报价')
        try:return sync_quote(con,quote)
        except ValueError as ex:raise HTTPException(409,str(ex))
        except Exception:raise HTTPException(502,'云端同步未确认成功；请稍后重试，不能据此判定写入成功')

@app.get('/api/emails/{email_id}/sources')
def email_sources(email_id:str):
    with database() as con:
        if not con.execute('SELECT 1 FROM emails WHERE email_id=?',(email_id,)).fetchone():raise HTTPException(404,'邮件不存在')
        return [dict(x) for x in con.execute('SELECT id,filename,kind,sha256 FROM source_files WHERE email_id=?',(email_id,))]

class ManualIntake(BaseModel):
    entry_key:str=Field(pattern=r'^[a-f0-9-]{36}$')
    source_id:str=Field(min_length=1,max_length=100)
    source_locator:str=Field(min_length=1,max_length=200)
    actor:str=Field(min_length=1,max_length=100)
    reason:str=Field(min_length=3,max_length=1000)
    source_rfq_no:str=Field(min_length=1,max_length=100)
    part_number:str=Field(min_length=1,max_length=150)
    quantity:int=Field(gt=0,le=9007199254740991,strict=True)
    unit:str=Field(min_length=1,max_length=30)
    condition:str=Field(default='',max_length=30)
    description:str=Field(default='',max_length=1000)
    confirm_source:bool=False

@app.post('/api/emails/{email_id}/manual-lines')
def manual_intake(email_id:str,req:ManualIntake):
    from quotepilot.manual_intake import create_manual_line
    with database() as con:
        try:return create_manual_line(con,email_id,req.model_dump())
        except ValueError as ex:raise HTTPException(409,str(ex))

@app.get('/api/native-workflow/status')
def native_workflow_status():
    from quotepilot.native_workflow import MOIWorkflowClient
    wid=os.environ.get('MOI_WORKFLOW_ID','')
    if not wid:raise HTTPException(409,'请在服务端配置真实 MOI_WORKFLOW_ID')
    try:return MOIWorkflowClient().status(wid)
    except ValueError as ex:raise HTTPException(409,str(ex))
    except Exception:raise HTTPException(502,'MOI工作流状态读取失败；不能判定运行成功')


# Batch one: independent read-only AI query center. Existing business APIs remain intact.
def center_today():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo('Asia/Shanghai')).date()


@app.get('/api/admin/backup/download')
def download_sqlite_backup():
    # Existing production middleware requires the same administrator session.
    # No path input, no secret environment export, no restore-through-web endpoint.
    import tempfile
    from starlette.background import BackgroundTask
    from fastapi.responses import FileResponse
    from quotepilot.backups import snapshot
    folder=Path(tempfile.mkdtemp(prefix='quotepilot-backup-'))
    target=folder/'quotepilot.sqlite3'
    def cleanup():
        target.unlink(missing_ok=True);folder.rmdir()
    try:meta=snapshot(DB,target)
    except Exception:
        cleanup();raise HTTPException(503,'备份未完成；原数据库保持不变')
    return FileResponse(target,media_type='application/octet-stream',filename='quotepilot-backup.sqlite3',
        headers={'X-Backup-SHA256':meta['sha256'],'X-Backup-Integrity':'ok','Cache-Control':'no-store'},
        background=BackgroundTask(cleanup))


class CenterQuestion(BaseModel):
    question:str=Field(min_length=2,max_length=1000)
    asof:date=Field(default_factory=center_today)
    session_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')


class FieldReviewRequest(BaseModel):
    version:int=Field(ge=1)
    changes:dict[str,str|int]=Field(default_factory=dict)
    actor:str=Field(min_length=1,max_length=100)
    reason:str=Field(min_length=3,max_length=1000)
    confirm_source:bool=False


class VersionRequest(BaseModel):
    email_id:str=Field(min_length=1,max_length=500)
    rfq_no:str=Field(min_length=1,max_length=150)
    actor:str=Field(min_length=1,max_length=100)
    reason:str=Field(min_length=3,max_length=1000)
    terms:dict=Field(default_factory=dict)


class MatchRequest(BaseModel):
    left:str
    right:str
    matches:dict[str,int]
    actor:str=Field(min_length=1,max_length=100)
    reason:str=Field(min_length=3,max_length=1000)


class SupplierOfferRequest(BaseModel):
    source_id:str=Field(min_length=1,max_length=100)
    source_locator:str=Field(min_length=1,max_length=1000)
    source_excerpt:str=Field(min_length=1,max_length=4000)
    supplier:str=Field(min_length=1,max_length=200)
    part_number:str=Field(min_length=1,max_length=150)
    specification:str=Field(min_length=1,max_length=1000)
    unit:str=Field(min_length=1,max_length=30)
    condition:str=Field(min_length=1,max_length=30)
    currency:str=Field(min_length=3,max_length=3)
    unit_price:Decimal=Field(gt=0,le=1000000000000)
    fx_to_cny:Decimal=Field(gt=0,le=1000000)
    fx_source:str=Field(min_length=1,max_length=1000)
    moq:int=Field(ge=1,le=1000000000,strict=True)
    lead_days:int=Field(ge=0,le=3650,strict=True)
    shipping_scope:Literal['line','shipment']='line'
    shipping_group:str=Field(default='',max_length=100)
    extraction_run_id:str|None=None
    extraction_candidate:int|None=None
    shipping_total:Decimal=Field(ge=0,le=1000000000000)
    tax_rate:Decimal=Field(ge=0,lt=1)
    quote_date:date
    valid_until:date
    payment_terms:str=Field(min_length=1,max_length=1000)


class CommercialQuoteRequest(BaseModel):
    line_ids:list[int]=Field(min_length=1,max_length=100)
    scheme:Literal['lowest_cost','fastest','balanced']='balanced'
    asof:date=Field(default_factory=center_today)
    valid_until:date
    delivery_deadline:date|None=None
    target_margin:Decimal=Field(ge=0,lt=1)
    line_costs:dict[str,dict[str,Decimal]]=Field(default_factory=dict)
    company_name:str=Field(min_length=1,max_length=200)
    company_contact:str=Field(default='',max_length=500)
    customer_name:str=Field(min_length=1,max_length=200)
    customer_contact:str=Field(default='',max_length=500)
    delivery_terms:str=Field(min_length=1,max_length=1000)
    payment_terms:str=Field(min_length=1,max_length=1000)
    remarks:str=Field(default='',max_length=1000)


class CommercialReviewRequest(BaseModel):
    version:int=Field(ge=1)
    actor:str=Field(min_length=1,max_length=100)
    reason:str=Field(min_length=3,max_length=1000)
    confirm_risks:bool=False


@app.get('/api/auth/me')
def auth_me(request:Request):
    from quotepilot.security import session_role,COOKIE,production
    role=session_role(request.cookies.get(COOKIE,'')) if production() else 'admin'
    return {'today':center_today().isoformat(),'role':role,'account':role,'production':production(),'identity_scope':'单团队共享角色账户；无公众注册，不是多租户'}


@app.post('/api/supplier-offers/sources')
async def supplier_source(file:UploadFile=File(...)):
    import hashlib
    name=Path(file.filename or '').name
    if Path(name).suffix.lower() not in ('.pdf','.xlsx','.eml','.txt'):raise HTTPException(415,'仅接受PDF、Excel、EML或TXT原报价文件')
    raw=await file.read(5*1024*1024+1)
    if not raw or len(raw)>5*1024*1024:raise HTTPException(413,'文件为空或超过5MB')
    if name.lower().endswith('.xlsx'):
        import zipfile
        from io import BytesIO
        try:
            with zipfile.ZipFile(BytesIO(raw)) as z:
                if sum(x.file_size for x in z.infolist())>50*1024*1024:raise ValueError()
        except Exception:raise HTTPException(422,'工作簿无效或解压体积超限')
    digest=hashlib.sha256(raw).hexdigest();sid='SUPSRC-'+digest
    with database() as con:
        with con:
            con.execute("INSERT OR IGNORE INTO source_files(id,filename,sha256,content,kind,dataset) VALUES(?,?,?,?,?,?)",(sid,name,digest,raw,'supplier_quote','user_upload'))
            audit(con,'supplier_source_uploaded',sid,{'filename':name,'sha256':digest,'bytes':len(raw)})
    return {'source_id':sid,'filename':name,'sha256':digest,'parse_method':'人工结构化并复核，不声称已自动解析文件'}


@app.post('/api/supplier-offers')
def add_supplier_offer(req:SupplierOfferRequest):
    from quotepilot.commercial import add_offer
    with database() as con:
        try:return add_offer(con,req.model_dump(mode='json'))
        except ValueError as ex:raise HTTPException(409,str(ex))


@app.get('/api/supplier-offers')
def supplier_offers():
    from quotepilot.commercial import offers
    with database() as con:return {'rows':offers(con)}


@app.post('/api/supplier-offers/{oid}/confirm')
def review_supplier_offer(oid:str,req:CommercialReviewRequest,request:Request):
    from quotepilot.commercial import confirm_offer
    from quotepilot.security import session_role,COOKIE,production
    role=session_role(request.cookies.get(COOKIE,'')) if production() else 'admin'
    with database() as con:
        try:return confirm_offer(con,oid,str(role)+' / '+req.actor,req.reason)
        except KeyError:raise HTTPException(404,'供应商报价不存在')
        except ValueError as ex:raise HTTPException(409,str(ex))


@app.post('/api/commercial-quotes')
def new_commercial_quote(req:CommercialQuoteRequest):
    from quotepilot.commercial import create_draft
    if req.valid_until<req.asof:raise HTTPException(422,'报价有效期早于基准日')
    with database() as con:
        try:return create_draft(con,req.model_dump(mode='json'))
        except KeyError:raise HTTPException(404,'询价行不存在')
        except ValueError as ex:
            con.rollback()
            with con:audit(con,'commercial_quote_calculation_failed','new_draft',{'error_type':type(ex).__name__})
            raise HTTPException(409,str(ex))


@app.get('/api/commercial-quotes')
def commercial_quote_list():
    with database() as con:return {'rows':[dict(r) for r in con.execute('SELECT q.id,q.created_at,s.status,s.version FROM commercial_quotes q JOIN commercial_quote_states s ON q.id=s.quote_id ORDER BY q.created_at DESC LIMIT 100')]}


@app.get('/api/commercial-quotes/{qid}')
def commercial_quote_detail(qid:str):
    from quotepilot.commercial import load
    with database() as con:
        try:
            obj=load(con,qid);obj['approval_history']=[dict(r) for r in con.execute('SELECT * FROM commercial_quote_events WHERE quote_id=? ORDER BY id',(qid,))];return obj
        except KeyError:raise HTTPException(404,'报价不存在')


@app.get('/api/commercial-quotes/{qid}/export/{kind}')
def export_commercial_quote(qid:str,kind:Literal['pdf','xlsx'],final:bool=True):
    from quotepilot.commercial_exports import export_quote
    from quotepilot.commercial import load
    from quotepilot.provenance import stamp
    import hashlib
    from uuid import uuid4
    with database() as con:
        try:raw,media=export_quote(con,qid,kind,final);version=load(con,qid)['version']
        except KeyError:raise HTTPException(404,'报价不存在')
        except ValueError as ex:raise HTTPException(409,str(ex))
        with con:
            eid='EXPORT-'+uuid4().hex
            con.execute('INSERT INTO commercial_exports VALUES(?,?,?,?,?,?,?)',(eid,qid,version,kind,hashlib.sha256(raw).hexdigest(),int(final),stamp()))
            audit(con,'commercial_quote_exported',qid,{'export_id':eid,'version':version,'format':kind,'final':final,'sha256':hashlib.sha256(raw).hexdigest()})
    return Response(raw,media_type=media,headers={'Content-Disposition':f'attachment; filename="{qid}_v{version}.{kind}"','X-Content-Type-Options':'nosniff'})


@app.post('/api/commercial-quotes/{qid}/{action}')
def commercial_quote_action(qid:str,action:Literal['review','approve'],req:CommercialReviewRequest,request:Request):
    from quotepilot.commercial import transition
    from quotepilot.security import session_role,COOKIE,production
    role=session_role(request.cookies.get(COOKIE,'')) if production() else 'admin'
    with database() as con:
        try:return transition(con,qid,req.version,action,str(role),str(role),req.actor,req.reason,center_today(),req.confirm_risks)
        except KeyError:raise HTTPException(404,'报价不存在')
        except PermissionError as ex:raise HTTPException(403,str(ex))
        except ValueError as ex:raise HTTPException(409,str(ex))


@app.post('/api/rfq-versions/matches')
def confirm_rfq_matches(req:MatchRequest,request:Request):
    from quotepilot.rfq_versions import record_matches
    with database() as con:
        try:return record_matches(con,req.left,req.right,req.matches,'admin_session:'+center_owner(request)[:12]+' / '+req.actor,req.reason)
        except KeyError:raise HTTPException(404,'版本不存在')
        except ValueError as ex:raise HTTPException(409,str(ex))


@app.post('/api/rfq-versions')
def register_rfq_version(req:VersionRequest,request:Request):
    from quotepilot.rfq_versions import register
    with database() as con:
        try:return register(con,req.email_id,req.rfq_no,'admin_session:'+center_owner(request)[:12]+' / '+req.actor,req.reason,req.terms)
        except ValueError as ex:raise HTTPException(409,str(ex))


@app.get('/api/rfq-versions')
def list_rfq_versions(limit:int=Query(100,ge=1,le=200),offset:int=Query(0,ge=0)):
    with database() as con:
        return {'rows':[dict(r) for r in con.execute('SELECT v.id,v.series_id,v.version,v.email_id,v.created_at,v.payload_sha256,s.customer_key,s.rfq_no FROM rfq_versions v JOIN rfq_series s ON s.id=v.series_id ORDER BY v.created_at DESC,v.version DESC LIMIT ? OFFSET ?',(limit,offset))]}


@app.get('/api/rfq-versions/compare')
def compare_rfq_versions(left:str,right:str,asof:date=Query(default_factory=center_today)):
    from quotepilot.rfq_versions import compare
    with database() as con:
        try:return compare(con,left,right,asof.isoformat())
        except KeyError:raise HTTPException(404,'RFQ版本不存在')
        except ValueError as ex:raise HTTPException(409,str(ex))


@app.get('/api/rfq-versions/{vid}')
def get_rfq_version(vid:str):
    from quotepilot.rfq_versions import load
    with database() as con:
        try:return load(con,vid)
        except KeyError:raise HTTPException(404,'RFQ版本不存在')


@app.get('/api/review-queue')
def field_review_queue(limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)):
    from quotepilot.provenance import capture
    with database() as con:
        missing=con.execute('SELECT id FROM rfq_lines WHERE id NOT IN (SELECT line_id FROM line_review_state)').fetchall()
        for row in missing:capture(con,row['id'])
        con.commit()
        total=con.execute("SELECT COUNT(*) FROM line_review_state WHERE status='pending'").fetchone()[0]
        rows=[dict(r) for r in con.execute("SELECT l.id,l.part_number,l.source_rfq_no,l.source_ref,s.version,s.status FROM rfq_lines l JOIN line_review_state s ON s.line_id=l.id WHERE s.status='pending' ORDER BY l.id LIMIT ? OFFSET ?",(limit,offset))]
        return {'total':total,'rows':rows,'offset':offset,'limit':limit}


@app.get('/api/lines/{line_id}/field-evidence')
def field_evidence_detail(line_id:int):
    from quotepilot.provenance import detail,verify_field
    with database() as con:
        try:
            result=detail(con,line_id)
            for field in result['fields']:field['source_check']=verify_field(con,field)
            con.commit();return result
        except KeyError:raise HTTPException(404,'询价行不存在')


@app.post('/api/lines/{line_id}/review-fields')
def review_fields(line_id:int,req:FieldReviewRequest,request:Request):
    from quotepilot.provenance import review
    identity='admin_session:'+center_owner(request)[:12]
    with database() as con:
        try:return review(con,line_id,req.version,req.changes,identity+' / '+req.actor,req.reason,req.confirm_source)
        except KeyError:raise HTTPException(404,'询价行不存在')
        except ValueError as ex:raise HTTPException(409,str(ex))


@app.get('/api/audit/verify')
def audit_integrity():
    from quotepilot.provenance import verify_audit
    with database() as con:return verify_audit(con)

class CenterQuick(BaseModel):
    question:str=Field(min_length=2,max_length=100)
    asof:date=Field(default_factory=center_today)
    session_id:str|None=Field(default=None,pattern=r'^[a-f0-9]{32}$')

class PublicSearch(CenterQuestion):
    pass

class JointQuestion(CenterQuestion):
    public_query:str=Field(min_length=2,max_length=500)


def center_owner(request):
    from quotepilot.query_center import owner_hash
    from quotepilot.security import COOKIE
    return owner_hash(request.cookies.get(COOKIE,'local-development'))


def center_provider():
    from quotepilot.providers import get_provider
    if os.environ.get('QUOTEPILOT_PROVIDER','mock')!='genesis':raise HTTPException(503,'尚未启用真实Genesis；快捷统计仍可使用。')
    return get_provider()


from fastapi import Request

@app.get('/api/query-center/status')
def center_status():
    from quotepilot.search_service import config
    return {'genesis_enabled':os.environ.get('QUOTEPILOT_PROVIDER','mock')=='genesis','external_search':config(),
            'default_reference_date':datetime.now(__import__('zoneinfo').ZoneInfo('Asia/Shanghai')).date().isoformat(),'database':'SQLite','read_only_queries':True,'max_rows':100,'query_timeout_seconds':1,
            'storage_notice':'沿用当前SQLite存储；本批次未迁移数据库。免费临时部署的新增记录仍可能随重新部署丢失。'}

@app.get('/api/query-center/schema')
def center_schema():
    from quotepilot.query_sql import discover
    return discover(DB)

@app.get('/api/query-center/sessions/{sid}')
def center_history(sid:str,request:Request):
    from quotepilot.query_center import history
    try:return {'turns':history(DB,center_owner(request),sid)}
    except PermissionError:raise HTTPException(403,'无法访问该查询会话')

@app.post('/api/query-center/ask')
def center_ask(req:CenterQuestion,request:Request):
    from quotepilot.query_center import run
    if not req.question.strip():raise HTTPException(422,'问题不能为空')
    try:return run(DB,center_provider(),req.question.strip(),req.asof.isoformat(),center_owner(request),req.session_id)
    except PermissionError:raise HTTPException(403,'无法访问该查询会话')

@app.post('/api/query-center/quick')
def center_quick(req:CenterQuick,request:Request):
    from datetime import timedelta
    from quotepilot.query_center import session,save
    from quotepilot.query_sql import execute
    if req.question not in QUESTIONS:raise HTTPException(422,'未知快捷统计')
    try:sid,_=session(DB,center_owner(request),req.session_id)
    except PermissionError:raise HTTPException(403,'无法访问该查询会话')
    params=[req.asof.isoformat(),req.asof.isoformat()] if req.question=='即将截止的询价' else []
    result=execute(DB,QUESTIONS[req.question],params)
    return save(DB,sid,req.question,{**result,'status':'completed','question':req.question,'title':req.question,
       'reference_date':req.asof.isoformat(),'interpretation':'历史询价示例；询价份数按RFQ No计，物料明细分别统计；非实时订单。',
       'statistics_scope':'历史询价示例 / 固定快捷统计 / 日期按所选基准日',
       'chart':'line' if req.question=='每月询价趋势' else 'ranking' if req.question!='即将截止的询价' else 'table',
       'analysis':{'status':'not_requested','summary':'已直接执行只读快捷统计，本次未调用AI。','findings':[],'caveats':[]}})

@app.post('/api/query-center/external')
def center_external(req:PublicSearch,request:Request):
    from quotepilot.query_center import session,save
    from quotepilot.search_service import SearchService,SearchUnavailable,record,config,claim_budget
    try:sid,_=session(DB,center_owner(request),req.session_id)
    except PermissionError:raise HTTPException(403,'无法访问该查询会话')
    try:
        if len(req.question.strip())<2:raise HTTPException(422,'请填写公开检索关键词')
        if not config()['available']:raise SearchUnavailable(config()['blocked_reason'])
        claim_budget(DB)
        result=record(DB,sid,SearchService().search(req.question.strip()))
        return save(DB,sid,req.question,{**result,'status':'completed','mode':'external','message':'已取得公开搜索来源；网页价格不等于正式报价或实时库存。'})
    except SearchUnavailable as error:
        return save(DB,sid,req.question,{'status':'blocked','mode':'external','message':str(error),'sources':[],'live_search':False})

@app.post('/api/query-center/joint')
def center_joint(req:JointQuestion,request:Request):
    from quotepilot.query_center import run,save
    from quotepilot.search_service import SearchService,SearchUnavailable,record,config,claim_budget
    from quotepilot.joint_analysis import extract_public,compare,verify_internal
    provider=center_provider()
    instruction=req.question+'（联合分析内部查询：如可提供报价参考，请逐条返回part_number,specification,unit,condition,currency,unit_price,price_date,price_basis,source_id字段。缺失字段返回NULL；price_basis只能按实际依据为approved_quote或supplier_reference。没有真实成交字段时仍须追问，不得冒充成交。）'
    try:internal=run(DB,provider,instruction,req.asof.isoformat(),center_owner(request),req.session_id)
    except PermissionError:raise HTTPException(403,'无法访问该查询会话')
    if internal['status']!='completed':return internal
    sid=internal['session_id']
    try:
        if not config()['available']:raise SearchUnavailable(config()['blocked_reason'])
        claim_budget(DB)
        external=record(DB,sid,SearchService().search(req.public_query.strip(),3))
    except SearchUnavailable as error:
        return save(DB,sid,req.question,{**internal,'status':'partial','mode':'joint','message':'内部查询完成；'+str(error),'sources':[],'comparisons':[],'live_search':False})
    try:observations,receipt=extract_public(provider,external)
    except Exception:
        return save(DB,sid,req.question,{**internal,'status':'partial','mode':'joint','message':'外部来源已保存，但公开价格提取未通过证据校验，未计算价差。','sources':external['sources'],'comparisons':[],'live_search':True})
    verified_internal=verify_internal(DB,internal['rows'])
    aligned=compare(verified_internal,observations,external['sources'])
    return save(DB,sid,req.question,{**internal,'status':'completed','mode':'joint','sources':external['sources'],
        'comparisons':aligned,'live_search':True,'public_extraction_response_id':receipt['response_id'],
        'message':'仅对型号、规格、件状、单位、币种及价格日期均可核对的记录计算参考价差；不代表成交机会或可采购库存。'})

@app.get('/api/operations/metrics')
def recorded_operations_metrics():
    from quotepilot.operations import metrics
    with database() as con:return metrics(con)

@app.get('/api/operations/health')
def operations_health():
    from quotepilot.operations import health
    with database() as con:return health(con)


@app.post('/api/supplier-offers/sources/{sid}/extract')
def extract_supplier_source(sid:str):
    from quotepilot.supplier_extraction import extract
    with database() as con:
        try:return extract(con,sid)
        except (ValueError,UnicodeError) as ex:raise HTTPException(422,str(ex))
        except Exception as ex:
            audit(con,'supplier_extraction_failed',sid,{'error_type':type(ex).__name__});con.commit()
            raise HTTPException(422,'原件解析失败；请人工核对或更换可读文字版文件')
