"""Explicit aliases only; no guessed semantic field mapping."""
ALIASES={
 'part number':'Part Number','part no':'Part Number','part no.':'Part Number','pn':'Part Number','件号':'Part Number',
 'quantity':'Quantity','qty':'Quantity','数量':'Quantity',
 'unit':'Unit Of Measure','unit of measure':'Unit Of Measure','uom':'Unit Of Measure','单位':'Unit Of Measure',
 'description':'Description','描述':'Description','品名':'Description',
 'condition':'件状条件','件状':'件状条件','件状条件':'件状条件',
 'rfq no':'RFQ No','rfq no.':'RFQ No','询价单号':'询价单号',
}

def canonical(key):
    key=str(key).strip()
    return ALIASES.get(key.casefold(),key)

def validate_headers(headers):
    names=[canonical(h) for h in headers if str(h).strip()]
    if len(names)!=len(set(names)):raise ValueError('规范化后表头重复；拒绝覆盖数量等业务字段')
    return names
