"""Sourced supplier offers, Decimal landed cost, alternative drafts and two-account approval."""
from datetime import date,timedelta
from decimal import Decimal,InvalidOperation,ROUND_HALF_UP,localcontext
import json
from uuid import uuid4
from .provenance import encoded,stamp,quote_review_snapshot,assert_ready

SCHEMA='''
CREATE TABLE IF NOT EXISTS supplier_offers(id TEXT PRIMARY KEY,payload_json TEXT NOT NULL,source_id TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS offer_reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,offer_id TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commercial_quotes(id TEXT PRIMARY KEY,payload_json TEXT NOT NULL,created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commercial_quote_states(quote_id TEXT PRIMARY KEY,status TEXT NOT NULL,version INTEGER NOT NULL,reviewer_account TEXT,approver_account TEXT);
CREATE TABLE IF NOT EXISTS commercial_quote_events(id INTEGER PRIMARY KEY AUTOINCREMENT,quote_id TEXT NOT NULL,from_status TEXT NOT NULL,to_status TEXT NOT NULL,
 version INTEGER NOT NULL,account TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commercial_exports(id TEXT PRIMARY KEY,quote_id TEXT NOT NULL,version INTEGER NOT NULL,format TEXT NOT NULL,sha256 TEXT NOT NULL,final INTEGER NOT NULL,at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS supplier_offer_catalog(offer_id TEXT PRIMARY KEY,supplier TEXT NOT NULL,part_number TEXT NOT NULL,
 specification TEXT NOT NULL,unit TEXT NOT NULL,condition TEXT NOT NULL,unit_price TEXT NOT NULL,currency TEXT NOT NULL,
 fx_to_cny TEXT NOT NULL,moq INTEGER NOT NULL,lead_days INTEGER NOT NULL,quote_date TEXT NOT NULL,valid_until TEXT NOT NULL,source_id TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS commercial_quote_items(quote_id TEXT NOT NULL,line_id INTEGER NOT NULL,offer_id TEXT,
 quantity INTEGER NOT NULL,unit_price_cny TEXT,total_cny TEXT,field_review_version INTEGER NOT NULL,
 PRIMARY KEY(quote_id,line_id),FOREIGN KEY(quote_id) REFERENCES commercial_quotes(id),FOREIGN KEY(line_id) REFERENCES rfq_lines(id));
'''

def install(con):
    con.executescript(SCHEMA)
    for table in ('supplier_offers','offer_reviews','commercial_quotes','commercial_quote_events','commercial_exports','supplier_offer_catalog','commercial_quote_items'):
        for op in ('UPDATE','DELETE'):con.execute(f"CREATE TRIGGER IF NOT EXISTS protect_{table}_{op.lower()} BEFORE {op} ON {table} BEGIN SELECT RAISE(ABORT,'immutable commercial record'); END")

def decimal(value,positive=False):
    try:
        if len(str(value))>100:raise ValueError()
        x=Decimal(str(value))
        if not x.is_finite() or x<0 or x>Decimal('1000000000000') or abs(x.as_tuple().exponent)>12 or (positive and x<Decimal('.00000001')):raise ValueError()
        return x
    except (ValueError,InvalidOperation):raise ValueError('金额/比例必须为有界非负数，价格及汇率须大于零')

def money(value):return str(value.quantize(Decimal('.01'),rounding=ROUND_HALF_UP))

def add_offer(con,payload):
    import re
    payload={**payload}
    for key in ('part_number','unit','condition','currency'):
        if isinstance(payload.get(key),str):payload[key]=payload[key].strip().upper()
    if not re.fullmatch(r'[A-Z]{3}',payload.get('currency','')):raise ValueError('币种须为三字母代码，汇率须另有依据')
    if not str(payload.get('source_excerpt','')).strip():raise ValueError('须保留供应商报价原文片段')
    source=con.execute('SELECT id,filename,sha256,dataset FROM source_files WHERE id=?',(payload['source_id'],)).fetchone()
    if not source:raise ValueError('供应商报价必须关联已保存的原始文件')
    if not all(k in payload for k in ('shipping_total','tax_rate','moq','lead_days','quote_date','valid_until')):raise ValueError('成本、税费、MOQ、交期和有效期不能隐式缺省')
    for key in ('supplier','part_number','specification','unit','condition','currency','source_locator','payment_terms','fx_source'):
        if not isinstance(payload.get(key),str) or not payload[key].strip() or len(payload[key])>1000:raise ValueError('供应商、型号、规格、单位、件状、币种、付款及来源须明确')
    for key in ('unit_price','fx_to_cny'):decimal(payload[key],True)
    decimal(payload.get('shipping_total',0));tax=decimal(payload.get('tax_rate',0))
    if tax>=1:raise ValueError('税率使用小数且小于1')
    if type(payload.get('moq')) is not int or payload['moq']<1 or type(payload.get('lead_days')) is not int or payload['lead_days']<0:raise ValueError('MOQ和交期必须明确为有效整数')
    if payload['currency'].upper()=='CNY' and decimal(payload['fx_to_cny'])!=1:raise ValueError('CNY汇率必须为1')
    if date.fromisoformat(payload['valid_until'])<date.fromisoformat(payload['quote_date']):raise ValueError('报价有效期早于报价日期')
    if payload.get('shipping_scope','line')=='shipment' and not str(payload.get('shipping_group','')).strip():raise ValueError('整票运费需要明确运输批次标识')
    from .supplier_extraction import evidence_for_offer
    extraction=evidence_for_offer(con,payload)
    obj={**payload,'extraction':extraction,'source_file':dict(source),'dataset':source['dataset'],'fx_notice':'人工维护的报价换算汇率，不是实时市场汇率'}
    for r in con.execute('SELECT id,payload_json FROM supplier_offers ORDER BY created_at DESC,id'):
        previous=json.loads(r['payload_json'])
        if all(str(previous[k]).strip().upper()==str(payload[k]).strip().upper() for k in ('supplier','part_number','specification','unit','condition','currency')) and previous['quote_date']<=payload['quote_date']:
            ratio=(decimal(payload['unit_price'],True)-decimal(previous['unit_price'],True))/decimal(previous['unit_price'],True)
            obj['price_change']={'previous_offer_id':r['id'],'previous_price':previous['unit_price'],'change_ratio':str(ratio),'warning_threshold':'.30','warning':abs(ratio)>Decimal('.30')}
            break
    oid='OFFER-'+uuid4().hex[:16]
    from .store import audit
    with con:
        con.execute('INSERT INTO supplier_offers VALUES(?,?,?,?)',(oid,encoded(obj),payload['source_id'],stamp()))
        keys=('supplier','part_number','specification','unit','condition','unit_price','currency','fx_to_cny','moq','lead_days','quote_date','valid_until','source_id')
        con.execute('INSERT INTO supplier_offer_catalog VALUES('+','.join('?' for _ in range(14))+')',[oid]+[str(payload[k]) if k not in ('moq','lead_days') else payload[k] for k in keys])
        audit(con,'supplier_offer_structured',oid,{'source_id':payload['source_id'],'source_sha256':source['sha256'],'supplier':payload['supplier']})
    return {'id':oid,**obj,'review_status':'pending'}

def confirm_offer(con,oid,actor,reason):
    if not actor.strip() or len(reason.strip())<3:raise ValueError('需要报价复核人和原因')
    if not con.execute('SELECT 1 FROM supplier_offers WHERE id=?',(oid,)).fetchone():raise KeyError('供应商报价不存在')
    from .store import audit
    with con:
        con.execute('INSERT INTO offer_reviews(offer_id,actor,reason,at) VALUES(?,?,?,?)',(oid,actor,reason,stamp()))
        audit(con,'supplier_offer_confirmed',oid,{'reason':reason},actor)
    return {'id':oid,'review_status':'confirmed'}

def offers(con):
    return [{'id':r['id'],**json.loads(r['payload_json']),'review_status':'confirmed' if con.execute('SELECT 1 FROM offer_reviews WHERE offer_id=?',(r['id'],)).fetchone() else 'pending'} for r in con.execute('SELECT * FROM supplier_offers ORDER BY created_at DESC,id')]

def calculate(offer,quantity,processing_per_unit,other_total,margin,freight_cny=None):
    if type(quantity) is not int or not 0<quantity<=9007199254740991:raise ValueError('数量无效')
    with localcontext() as context:
        context.prec=64
        return _calculate(offer,quantity,processing_per_unit,other_total,margin,freight_cny)

def _calculate(offer,quantity,processing_per_unit,other_total,margin,freight_cny=None):
    qty=Decimal(quantity);fx=decimal(offer['fx_to_cny'],True)
    purchase=decimal(offer['unit_price'],True)*qty*fx
    processing=decimal(processing_per_unit)*qty
    freight=decimal(offer.get('shipping_total',0))*fx if freight_cny is None else decimal(freight_cny)
    tax=purchase*decimal(offer.get('tax_rate',0))
    other=decimal(other_total);target=decimal(margin)
    if target>=1:raise ValueError('目标毛利率必须小于1')
    # Each displayed cost component is posted to cents before totals/margin.
    purchase,processing,freight,tax,other=[Decimal(money(v)) for v in (purchase,processing,freight,tax,other)]
    total=purchase+processing+freight+tax+other
    if total>Decimal('1000000000000000'):raise ValueError('单行成本超出业务计算上限')
    unit_sale=(total/(1-target)/qty).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    sales=unit_sale*qty;actual=(sales-total)/sales if sales else Decimal(0)
    return {'purchase_cny':money(purchase),'processing_cny':money(processing),'freight_cny':money(freight),'tax_cny':money(tax),'other_cny':money(other),
        'total_cost_cny':money(total),'unit_cost_cny':money(total/qty),'suggested_unit_price_cny':money(unit_sale),'suggested_total_cny':money(sales),
        'target_margin':str(target),'actual_margin':str(actual),'formula':'(采购原币单价×数量×汇率 + 加工单价×数量 + 运费原币×汇率 + 采购成本×税率 + 其他成本) ÷ (1−目标毛利率)',
        'tax_basis':'采购成本（CNY），不把税率当加价率','rounding':'各成本项ROUND_HALF_UP至分后相加；销售单价至分后乘数量，实际毛利率按已入账成本计算',
        'risks':(['舍入后销售单价为0，必须调整价格精度并重新核价'] if unit_sale<=0 else [])+(['舍入后毛利率低于目标，审批前须复核'] if actual<target else [])}

def create_draft(con,request):
    if not request['line_ids'] or len(set(request['line_ids']))!=len(request['line_ids']) or len(request['line_ids'])>100:raise ValueError('选择1到100条不重复的询价行')
    if request['scheme'] not in ('lowest_cost','fastest','balanced'):raise ValueError('未知报价方案')
    available=offers(con);results=[];blockers=[];reference=date.fromisoformat(request['asof'])
    customers=set()
    for lid in request['line_ids']:
        row=con.execute('SELECT * FROM rfq_lines WHERE id=?',(lid,)).fetchone()
        if not row:raise KeyError('询价行不存在')
        from email.utils import parseaddr
        mail=con.execute('SELECT sender FROM emails WHERE email_id=?',(row['email_id'],)).fetchone()
        customer_key=parseaddr(mail['sender'] or '')[1].lower()
        if not customer_key:blockers.append(f'询价行{lid}缺少可核对客户标识')
        customers.add(customer_key);version=quote_review_snapshot(con,lid)
        candidates=[];rejected=[]
        extra=request.get('line_costs',{}).get(str(lid),{})
        if not all(k in extra for k in ('processing_per_unit_cny','other_total_cny')):blockers.append(f'询价行{lid}缺少加工/其他成本；确无费用时也须明确填0')
        for offer in available:
            if offer['part_number'].upper()!=row['part_number'].upper():continue
            reasons=[]
            if offer['review_status']!='confirmed':reasons.append('供应商报价尚未复核')
            if offer['unit'].upper()!=(row['unit'] or '').upper():reasons.append('单位不一致')
            if offer['condition'].upper()!=(row['part_condition'] or '').upper():reasons.append('件状不一致')
            if not row['description'] or offer['specification'].strip()!=row['description'].strip():reasons.append('规格/技术描述不一致或缺失')
            if row['quantity']<offer['moq']:reasons.append('数量低于MOQ')
            if date.fromisoformat(offer['valid_until'])<reference:reasons.append('供应商报价已过期')
            if date.fromisoformat(offer['quote_date'])>reference:reasons.append('报价日期晚于基准日')
            if request.get('delivery_deadline') and reference+timedelta(days=offer['lead_days'])>date.fromisoformat(request['delivery_deadline']):reasons.append('供应商交期无法满足所填目标交付日')
            if reasons:rejected.append({'offer_id':offer['id'],'supplier':offer['supplier'],'reasons':reasons});continue
            calc=calculate(offer,row['quantity'],extra.get('processing_per_unit_cny',0),extra.get('other_total_cny',0),request['target_margin'])
            if not request.get('delivery_deadline'):calc['risks'].append('未提供目标交付日，交期匹配须人工核对')
            if offer.get('price_change',{}).get('warning'):calc['risks'].append('同供应商相同规格原币价相对上一条记录变动超过30%')
            candidates.append({'offer_id':offer['id'],'offer':offer,'calculation':calc})
        if candidates:
            min_cost=max(Decimal('.01'),min(Decimal(x['calculation']['total_cost_cny']) for x in candidates));min_lead=max(1,min(x['offer']['lead_days'] for x in candidates))
            for c in candidates:c['balanced_score']=str(Decimal('.5')*Decimal(c['calculation']['total_cost_cny'])/min_cost+Decimal('.5')*Decimal(c['offer']['lead_days'])/min_lead)
            key={'lowest_cost':lambda x:(Decimal(x['calculation']['total_cost_cny']),x['offer']['lead_days']),
                 'fastest':lambda x:(x['offer']['lead_days'],Decimal(x['calculation']['total_cost_cny'])),
                 'balanced':lambda x:(Decimal(x['balanced_score']),Decimal(x['calculation']['total_cost_cny']))}[request['scheme']]
            selected=min(candidates,key=key)
        else:selected=None;blockers.append(f'询价行{lid}无符合型号、规格、单位、件状、MOQ及有效期的已复核报价')
        results.append({'line_id':lid,'part_number':row['part_number'],'specification':row['description'],'unit':row['unit'],'quantity':row['quantity'],
            'field_review_version':version,'selected':selected,'candidates':candidates,'rejected':rejected})
    # Allocate each explicitly declared shipment charge ONCE across selected lines.
    freight_groups={}
    for line in results:
        if not line['selected']:continue
        offer=line['selected']['offer']
        if offer.get('shipping_scope','line')!='shipment':continue
        key=(offer['supplier'],offer['shipping_group'])
        freight_groups.setdefault(key,[]).append(line)
    allocations=[]
    for (supplier,group),group_lines in freight_groups.items():
        terms={(decimal(l['selected']['offer']['shipping_total']),l['selected']['offer']['currency'],decimal(l['selected']['offer']['fx_to_cny'])) for l in group_lines}
        if len(terms)!=1:raise ValueError('同一运输批次的运费、币种和汇率不一致，不能分摊')
        offer=group_lines[0]['selected']['offer'];total=Decimal(money(decimal(offer['shipping_total'])*decimal(offer['fx_to_cny'],True)))
        weights={l['line_id']:decimal(l['selected']['offer']['unit_price'],True)*Decimal(l['quantity'])*decimal(l['selected']['offer']['fx_to_cny'],True) for l in group_lines}
        shares=allocate_cents(total,weights)
        for line in group_lines:
            selected=line['selected'];extra=request.get('line_costs',{}).get(str(line['line_id']),{})
            c=calculate({**selected['offer'],'shipping_total':'0'},line['quantity'],extra.get('processing_per_unit_cny',0),extra.get('other_total_cny',0),request['target_margin'],freight_cny=shares[line['line_id']])
            c['risks']+= [r for r in selected['calculation']['risks'] if r not in c['risks'] and '舍入' not in r]
            selected['calculation']=c
        allocations.append({'supplier':supplier,'shipping_group':group,'total_cny':money(total),'basis':'采购成本占比；最大余数分摊至分，尾差按line_id稳定分配','lines':{str(k):money(v) for k,v in shares.items()}})
    for line in results:
        if line['selected'] and Decimal(line['selected']['calculation']['suggested_unit_price_cny'])<=0:blockers.append('销售单价舍入为0，需要重新核价')
    if len(customers)>1:blockers.append('跨客户询价不能合并为正式报价')
    for key in ('company_name','customer_name','payment_terms'):
        if not request.get(key,'').strip():blockers.append('报价抬头、客户及付款条件必须完整')
    result={**request,'id':'CQ-'+uuid4().hex[:16].upper(),'lines':results,'approval_blockers':blockers,
        'total_cost_cny':money(sum((Decimal(x['selected']['calculation']['total_cost_cny']) for x in results if x['selected']),Decimal(0))),
        'suggested_total_cny':money(sum((Decimal(x['selected']['calculation']['suggested_total_cny']) for x in results if x['selected']),Decimal(0))),
        'freight_allocations':allocations,'currency':'CNY','decision_method':'确定性成本/交期规则，非AI凭空生成供应商数据','balanced_formula':'逐行评分0.5×成本/最低成本 + 0.5×交期/最短交期；运输批次在选定后分摊，不承诺组合全局最优',
        'specification_basis':'现有RFQ description字段经人工复核后作规格键；不做语义相似自动认定'}
    from .store import audit
    with con:
        con.execute('INSERT INTO commercial_quotes VALUES(?,?,?)',(result['id'],encoded(result),stamp()))
        con.execute('INSERT INTO commercial_quote_states VALUES(?,?,?,NULL,NULL)',(result['id'],'draft',1))
        for line in results:
            selected=line['selected'];calc=selected['calculation'] if selected else {}
            con.execute('INSERT INTO commercial_quote_items VALUES(?,?,?,?,?,?,?)',(result['id'],line['line_id'],selected['offer_id'] if selected else None,line['quantity'],calc.get('suggested_unit_price_cny'),calc.get('suggested_total_cny'),line['field_review_version']))
        audit(con,'commercial_quote_calculated',result['id'],{'scheme':request['scheme'],'line_ids':request['line_ids'],'blockers':blockers,'total_cost_cny':result['total_cost_cny']})
    return load(con,result['id'])

def load(con,qid):
    row=con.execute('SELECT q.payload_json,s.* FROM commercial_quotes q JOIN commercial_quote_states s ON s.quote_id=q.id WHERE q.id=?',(qid,)).fetchone()
    if not row:raise KeyError('商业报价不存在')
    return {**json.loads(row['payload_json']),**{k:row[k] for k in ('status','version','reviewer_account','approver_account')}}

def transition(con,qid,version,action,account,role,actor,reason,today=None,confirm_risks=False):
    if not actor.strip() or len(reason.strip())<3:raise ValueError('需要审核人和原因')
    con.execute('BEGIN IMMEDIATE')
    try:
        quote=load(con,qid);old=quote['status']
        if quote['version']!=version:raise ValueError('报价状态版本冲突')
        expected={'review':('draft','business_reviewed'),'approve':('business_reviewed','approved')}
        if action not in expected or old!=expected[action][0]:raise ValueError('不允许跳过审核或重复审批')
        if action=='review' and role not in ('reviewer','admin'):raise PermissionError('需要业务复核权限')
        if action=='approve' and role!='admin':raise PermissionError('只有管理员可审批')
        if action=='approve' and quote['reviewer_account']==account:raise ValueError('审核与审批必须由不同账户执行')
        if action=='approve' and any(x.get('selected',{}).get('calculation',{}).get('risks') for x in quote['lines'] if x.get('selected')) and not confirm_risks:raise ValueError('存在风险预警，管理员须明确确认风险后审批')
        if quote['approval_blockers']:raise ValueError('；'.join(quote['approval_blockers']))
        if date.fromisoformat(quote['valid_until'])<(today or date.today()):raise ValueError('客户报价有效期已过')
        for line in quote['lines']:
            assert_ready(con,line['line_id'],line['field_review_version'])
            if date.fromisoformat(line['selected']['offer']['valid_until'])<(today or date.today()):raise ValueError('供应商报价已过期，需要重新询价')
        new=expected[action][1]
        con.execute('UPDATE commercial_quote_states SET status=?,version=?,reviewer_account=?,approver_account=? WHERE quote_id=?',
            (new,version+1,account if action=='review' else quote['reviewer_account'],account if action=='approve' else None,qid))
        con.execute('INSERT INTO commercial_quote_events(quote_id,from_status,to_status,version,account,actor,reason,at) VALUES(?,?,?,?,?,?,?,?)',(qid,old,new,version+1,account,actor,reason,stamp()))
        from .store import audit
        audit(con,'commercial_quote_'+action,qid,{'from':old,'to':new,'version':version+1,'account':account,'reason':reason,'risk_acknowledged':confirm_risks},actor)
        con.commit();return load(con,qid)
    except Exception:con.rollback();raise


def allocate_cents(total,weights):
    """Largest remainders, exact cent conservation; deterministic ties by line id."""
    from decimal import ROUND_FLOOR
    if not weights or any(v<=0 for v in weights.values()):raise ValueError('分摊权重必须为正数')
    cents=int(Decimal(money(total))*100);denominator=sum(weights.values())
    exact={k:Decimal(cents)*v/denominator for k,v in weights.items()}
    shares={k:int(v.to_integral_value(rounding=ROUND_FLOOR)) for k,v in exact.items()}
    left=cents-sum(shares.values())
    for key in sorted(weights,key=lambda k:(-(exact[k]-shares[k]),k))[:left]:shares[key]+=1
    return {k:Decimal(v)/100 for k,v in shares.items()}
