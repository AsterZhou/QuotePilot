"""Export clearly labeled draft quotation and audit data."""
from __future__ import annotations
from datetime import datetime
from io import BytesIO,StringIO
from decimal import Decimal
import csv,json
from docx import Document
from docx.shared import Cm,Pt,RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH


def quote_docx(report:dict, customer:str='演示客户', reference:str='DEMO-RFQ') -> bytes:
    doc=Document()
    sec=doc.sections[0]
    sec.top_margin=Cm(1.7);sec.bottom_margin=Cm(1.8)
    sec.left_margin=Cm(1.7);sec.right_margin=Cm(1.7)
    normal=doc.styles['Normal'];normal.font.name='Arial';normal.font.size=Pt(9)
    heading=doc.add_heading('QUOTEPILOT  /  QUOTATION DRAFT',0)
    heading.alignment=WD_ALIGN_PARAGRAPH.CENTER
    for run in heading.runs: run.font.size=Pt(16);run.font.color.rgb=RGBColor(17,55,80)
    p=doc.add_paragraph('AI-assisted RFQ analysis  ·  Draft quotation for human review')
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(f'Customer / 客户：{customer}\nReference / 来源：{reference}\n'
                      f'Pricing date / 核价基准日：{report["asof"]}\n'
                      f'Pricing method / 报价规则：{report["method"]}, rate {report["rate"]}')
    table=doc.add_table(rows=1,cols=7)
    table.style='Light Shading Accent 1'
    headers=['Part Number','Quantity','UOM','Condition','Unit Price CNY','Line Total CNY','Status']
    for cell,title in zip(table.rows[0].cells,headers):cell.text=title
    for line in report['lines']:
        vals=[line['part_number'],str(line['quantity']),line['unit'],line['condition'] or '—',
              line['unit_quote_cny'] or '—',line['line_total_cny'] or '—',line['status']]
        cells=table.add_row().cells
        for cell,v in zip(cells,vals):cell.text=v
    doc.add_paragraph(f'Quoted subtotal (excluding pending lines / 税费运费未计): CNY {report["total_cny"]}',style='Subtitle')
    doc.add_paragraph(f'Quoted lines: {report["quoted_count"]}  |  Pending verification: {report["pending_count"]}')
    doc.add_heading('Audit sources / 核价依据',level=2)
    for line in report['lines']:
        doc.add_paragraph(f'{line["part_number"]}: {line["price_ref"] or "待核价"} / {line["supplier"] or "—"}',style='List Bullet')
        for note in line['audit'][:2]:doc.add_paragraph(note,style='Normal')
        if line['status']=='待核价':doc.add_paragraph('需人工复核：'+'；'.join(line['issues'][:3]),style='Normal')
    doc.add_paragraph('NOTICE / 说明：本文件仅为比赛演示用报价草稿，数据来自官方示例素材。'
                      '无效/缺失价格不纳入金额合计；发出正式报价前必须人工确认币种、数量、件状、证书、交期、税费等。')
    out=BytesIO();doc.save(out);return out.getvalue()


def quote_csv(report:dict) -> bytes:
    f=StringIO();writer=csv.writer(f)
    writer.writerow(['part_number','quantity','unit','condition','status','source_ref','supplier','cost_cny',
                     'quoted_unit_cny','amount_cny','lead_days','issues','quote_id','version','asof','review_status','rfq_no','customer','original_source','rule_version'])
    for l in report['lines']:
        writer.writerow([safe_csv(l.get(k,'')) for k in ('part_number','quantity','unit','condition','status','price_ref',
                         'supplier','cost_cny','unit_quote_cny','line_total_cny','lead_days')]+[safe_csv('; '.join(l['issues']))]+[safe_csv(report.get(k,'')) for k in ('quote_id','version','asof','review_status')]+[safe_csv(l.get(k,'')) for k in ('source_rfq_no','customer','source_ref','rule_version')])
    return f.getvalue().encode('utf-8-sig')


def audit_json(report:dict) -> bytes:
    return json.dumps(report,ensure_ascii=False,indent=2).encode('utf-8')


def quote_xlsx(report):
    """Snapshot-only export: text cells prevent spreadsheet formula injection."""
    from openpyxl import Workbook
    from openpyxl.styles import Font,PatternFill
    wb=Workbook();ws=wb.active;ws.title='报价明细'
    ws.append(['QuotePilot',report.get('quote_id','DRAFT'),report.get('review_status','draft'),report.get('version',1)])
    ws.append(['币种 CNY / 税费运费未计','基准日',report['asof']])
    ws.append(['件号','数量','单位','件状','单价CNY','金额CNY','状态','价格来源','询价来源','规则版本','描述','客户','来源询价号','价格有效至','证书','交期'])
    for l in report['lines']:
        values=[l['part_number'],l['quantity'],l['unit'],l['condition'],l['unit_quote_cny'],l['line_total_cny'],l['status'],l['price_ref'],l.get('source_ref',''),report.get('rule_version',''),l.get('description',''),l.get('customer',''),l.get('source_rfq_no',''),l.get('price_basis',{}).get('record',{}).get('valid_until',''),l.get('price_basis',{}).get('record',{}).get('certificate','待核对'),l.get('lead_days','')]
        ws.append(values)
    ws.append(['建议金额小计','','','','',report['total_cny']])
    for row in ws:
        for cell in row:
            if isinstance(cell.value,str):cell.data_type='s'
    for cell in ws[3]:cell.font=Font(color='FFFFFF',bold=True);cell.fill=PatternFill('solid',fgColor='173D38')
    for col in 'ABCDEFGHIJKLMNOP':ws.column_dimensions[col].width=22 if col not in 'HI' else 55
    ws.freeze_panes='A4';ws.auto_filter.ref=f'A3:P{ws.max_row-1}'
    out=BytesIO();wb.save(out);return out.getvalue()


def safe_csv(value):
    text=str(value)
    return "'"+text if text.lstrip().startswith(('=','+','-','@')) else value
