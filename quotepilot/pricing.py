"""Decimal pricing; eligibility rejects unknown values, with explicit evidence."""
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import re
RULE_VERSION='qp-rules-0.5.0'
TWOPLACES=Decimal('.01')

def strict_decimal(v):
    try:d=Decimal(str(v))
    except (InvalidOperation,ValueError):raise ValueError('缺失或非数值')
    if not d.is_finite():raise ValueError('非有限数值')
    return d

def D(v,default='0'):
    try:return strict_decimal(v if v not in ('',None) else default)
    except ValueError:return Decimal(default)

def money(v):return str(v.quantize(TWOPLACES,rounding=ROUND_HALF_UP))

def calc_unit(cost,rate,method='markup',fee=Decimal(0)):
    cost,rate,fee=map(strict_decimal,(cost,rate,fee))
    if min(cost,rate,fee)<0 or (method=='margin' and rate>=1):raise ValueError('无效成本或费率')
    if method=='margin':return (cost+fee)/(1-rate)
    if method=='markup':return cost*(1+rate)+fee
    raise ValueError('未知报价方法')

def supplier_issues(p,asof,condition,quantity):
    errors=[]
    if p['status'] not in ('有效','VALID','valid'):errors.append('价格状态无效；请更新供应商状态')
    if not p['condition']:errors.append('供应商件状缺失；请重新确认')
    if condition and p['condition'].upper()!=condition:errors.append('件状不符；请核对件状')
    valid_dates=True
    for key,label in [('quote_date','报价日期'),('valid_until','价格有效期')]:
        try:date.fromisoformat(p[key][:10])
        except (ValueError,TypeError):errors.append(label+'缺失或格式错误；请补充日期');valid_dates=False
    if valid_dates:
        if p['quote_date'][:10]>asof:errors.append('报价日期晚于基准日；不能采用未来价格')
        if p['valid_until'][:10]<asof:errors.append('价格已过期；请重新询价')
        if p['valid_until'][:10]<p['quote_date'][:10]:errors.append('有效期早于报价日；数据冲突')
    try:
        moq=strict_decimal(p['moq'])
        if moq<=0:errors.append('起订量异常；请确认 MOQ')
        elif moq>quantity:errors.append(f'起订量 {moq} 大于询价 {quantity}；请协商 MOQ')
    except ValueError:errors.append('最小起订量缺失')
    try:
        price,fx=map(strict_decimal,(p['unit_price'],p['fx_to_cny']))
        if price<=0 or fx<=0:errors.append('价格或汇率非正数；请核价')
        if p['currency']=='CNY' and fx!=1:errors.append('CNY 汇率不等于 1；数据冲突')
    except ValueError:errors.append('价格或汇率缺失/异常；禁止默认汇率为 1')
    if not re.fullmatch('[A-Z]{3}',p['currency'] or ''):errors.append('币种缺失/异常')
    return errors

def quote_line(con,part,quantity,unit='EA',condition='',asof='2026-09-20',rate=Decimal('.20'),method='markup'):
    part,condition,unit=(str(x or '').upper().strip() for x in (part,condition,unit))
    date.fromisoformat(asof);calc_unit(Decimal(0),rate,method)
    r=dict(part_number=part,quantity=quantity,unit=unit,condition=condition,asof=asof,status='待核价',decision_state='待核价',supplier='',price_ref='',cost_cny='',unit_quote_cny='',line_total_cny='',lead_days='',issues=[],audit=[],review_flags=[],candidates=[],rule_version=RULE_VERSION)
    try:q=strict_decimal(quantity)
    except ValueError:q=Decimal(0)
    if not part or not unit or q<=0 or q!=q.to_integral_value():
        r['issues']=['件号/数量/单位无效；请修改需求字段（当前只支持整数数量）'];return r
    if not condition:r['review_flags'].append('需求件状缺失；请核对原询价并补充件状')
    elif condition not in ('FN','NE','OH','SV'):r['review_flags'].append('件状代码未配置释义；请人工确认原代码 '+condition)
    choices=[]
    cost=con.execute('SELECT * FROM costs WHERE part_number=?',(part,)).fetchone()
    if cost:
        errors=[]
        if cost['unit'].upper()!=unit:errors.append(f'库存单位 {cost["unit"]} 与需求 {unit} 不一致；请核对单位，不自动换算')
        if not cost['part_condition']:errors.append('库存件状缺失')
        if condition and cost['part_condition'].upper()!=condition:errors.append('库存件状不符；请核对件状')
        try:
            inv=strict_decimal(cost['inventory'])
            if inv<q:errors.append(f'库存不足：可用 {inv}，需求 {q}，差额 {q-inv} {unit}；请补货或选择供应商')
        except ValueError:errors.append('库存数量异常')
        if cost['currency']!='CNY':errors.append('库存成本非 CNY，未配置换算；请提供汇率')
        try:
            base=strict_decimal(cost['standard_cost'])
            if base<=0:errors.append('库存标准成本必须大于零；请补充成本')
        except ValueError:errors.append('库存标准成本缺失/异常；请补充成本')
        try:
            if date.fromisoformat(cost['updated_at'][:10])>date.fromisoformat(asof):errors.append('库存成本更新日晚于基准日；不能采用未来成本')
        except (ValueError,TypeError):errors.append('库存成本日期缺失/异常')
        ref=f'costs:{part}:row{cost["source_row"]}'
        r['candidates'].append({'ref':ref,'issues':errors});r['issues']+=errors
        if not errors:choices.append(dict(base=base,supplier='内部库存 / '+cost['warehouse'],ref=ref,lead_days='库存（需确认出库时效）',review=[],basis=dict(table='costs',record=dict(cost),currency='CNY',fx='1',fx_source='同币种，无需换算'),audit=f'库存标准成本 CNY {base}；原表行 {cost["source_row"]}'))
    for p in con.execute('SELECT * FROM prices WHERE part_number=?',(part,)):
        errors=supplier_issues(p,asof,condition,q)
        r['candidates'].append({'ref':p['resource_id'],'issues':errors});r['issues'] += [f'{p["resource_id"]}: {x}' for x in errors]
        if errors:continue
        base=strict_decimal(p['unit_price'])*strict_decimal(p['fx_to_cny'])
        choices.append(dict(base=base,supplier=p['supplier'],ref=p['resource_id'],lead_days=str(p['lead_days']),review=['供应商价格表未提供单位；请确认与需求单位一致','请核对证书、交期、税费与运费'],basis=dict(table='prices',record=dict(p),currency=p['currency'],fx=p['fx_to_cny'],fx_source=f'价格资源表 {p["resource_id"]} / 行 {p["source_row"]} / 汇率到CNY'),audit=f'价格 {p["resource_id"]}: {p["unit_price"]} {p["currency"]} × {p["fx_to_cny"]} = CNY {money(base)}；有效期 {p["valid_until"][:10]}'))
    if not choices:
        r['issues'].append('没有可靠且满足条件的价格；请补充成本或重新向供应商询价');return r
    best=min(choices,key=lambda c:(c['base'],c['ref']))
    if sum(c['base']==best['base'] for c in choices)>1:r['review_flags'].append('存在同价候选；请核对供应商与交期后确认来源')
    rounded=calc_unit(best['base'],rate,method).quantize(TWOPLACES,rounding=ROUND_HALF_UP)
    r.update(status='可报价（待人工审批）',supplier=best['supplier'],price_ref=best['ref'],cost_cny=money(best['base']),unit_quote_cny=money(rounded),line_total_cny=money(rounded*q),lead_days=best['lead_days'],price_basis=best['basis'])
    r['review_flags']+=best['review'];r['decision_state']='待人工确认' if r['review_flags'] else '可报价'
    r['audit']=[best['audit'],f'{method} {rate}；单价 {money(rounded)} × {q} = {r["line_total_cny"]} CNY；ROUND_HALF_UP 两位',f'规则版本 {RULE_VERSION}；税费运费未计']
    return r

def batch_quote(con,lines,asof='2026-09-20',rate='0.20',method='markup'):
    items=[quote_line(con,l['part_number'],l['quantity'],l.get('unit',''),l.get('condition',''),asof,strict_decimal(rate),method) for l in lines]
    used={}
    for item in items:
        if not item.get('price_basis') or item['price_basis']['table']!='costs':continue
        ref=item['price_ref'];qty=Decimal(str(item['quantity']))
        stock=Decimal(str(item['price_basis']['record']['inventory']))
        available=stock-used.get(ref,Decimal(0))
        if available<qty:
            item['issues'].append(f'同份报价累计库存不足：剩余 {available}，需求 {qty}，差额 {qty-available} {item["unit"]}；请补货或拆分报价')
            item.update(status='待核价',decision_state='待核价',unit_quote_cny='',line_total_cny='')
        else:used[ref]=used.get(ref,Decimal(0))+qty
    return dict(asof=asof,method=method,rate=rate,lines=items,total_cny=money(sum((D(x['line_total_cny']) for x in items),Decimal(0))),quoted_count=sum(bool(x['unit_quote_cny']) for x in items),pending_count=sum(not x['unit_quote_cny'] for x in items),review_count=sum(x['decision_state']=='待人工确认' for x in items),rule_version=RULE_VERSION,note='仅为建议金额小计；缺价行不计入；人工确认后生效。币种 CNY；税费与运费未计。')
