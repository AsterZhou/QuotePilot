"""PDF/XLSX exports read approved cost snapshots; no recalculation or external send."""
from io import BytesIO
from .commercial import load

def export_quote(con,qid,kind,final=True):
    quote=load(con,qid)
    if final and quote['status']!='approved':raise ValueError('正式报价单必须先完成业务审核及管理员审批')
    title='正式报价单' if final else '草稿 / DRAFT — 不可作为正式报价'
    header=[title,quote['company_name'],quote.get('company_contact',''),'报价编号: '+qid,
            '客户: '+quote['customer_name'],quote.get('customer_contact',''),'币种: CNY / 基准日: '+quote['asof'],
            '有效期至: '+quote['valid_until'],'付款条件: '+quote['payment_terms'],'交付约定: '+quote['delivery_terms']]
    lines=[]
    for item in quote['lines']:
        selected=item['selected'];calc=selected['calculation'] if selected else {}
        lines.append([item['part_number'],item['specification'],item['quantity'],item['unit'],calc.get('suggested_unit_price_cny','待核价'),calc.get('suggested_total_cny','待核价'),str(selected['offer']['lead_days'])+'天' if selected else '未知'])
    if kind=='xlsx':
        from openpyxl import Workbook
        from openpyxl.styles import Font,PatternFill,Alignment
        wb=Workbook();ws=wb.active;ws.title='报价单'
        for text in header:ws.append([text])
        ws.append(['件号','规格','数量','单位','单价CNY','金额CNY','交期'])
        start=ws.max_row
        for row in lines:ws.append(row)
        ws.append(['合计CNY','','','','',quote['suggested_total_cny']]);ws.append(['备注',quote.get('remarks','')])
        ws.append(['版本',quote['version'],'审批状态',quote['status']])
        for row in ws:
            for cell in row:
                # Supplier/customer text is never interpreted as an Excel formula.
                if isinstance(cell.value,str) and cell.value.startswith(('=','+','-','@')):cell.data_type='s'
                cell.alignment=Alignment(wrap_text=True,vertical='top')
        for cell in ws[start]:cell.fill=PatternFill('solid',fgColor='173F37');cell.font=Font(color='FFFFFF',bold=True)
        for col,width in [('A',28),('B',45),('C',12),('D',12),('E',18),('F',18),('G',16)]:ws.column_dimensions[col].width=width
        ws.freeze_panes=f'A{start+1}';ws.print_options.horizontalCentered=True;ws.sheet_properties.pageSetUpPr.fitToPage=True
        out=BytesIO();wb.save(out);return out.getvalue(),'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    if kind=='pdf':
        import fitz
        doc=fitz.open();page=None;y=0
        def write(text,size=10):
            nonlocal page,y
            # Conservative wrapping for CJK and Latin; separate item lines avoid clipped columns.
            for paragraph in str(text).splitlines() or ['']:
                for offset in range(0,max(1,len(paragraph)),48):
                    if page is None or y>790:
                        page=doc.new_page(width=595,height=842);y=48
                        page.insert_text((38,24),qid+' / '+quote['status'],fontname='helv',fontsize=8)
                    import re
                    x=38
                    for run in re.findall(r'[\x20-\x7e]+|[^\x00-\x7f]+',paragraph[offset:offset+48]):
                        font='helv' if run.isascii() else 'china-s'
                        page.insert_text((x,y),run,fontname=font,fontsize=size)
                        x+=fitz.get_text_length(run,fontname=font,fontsize=size)
                    y+=size+6
        for text in header:
            if text:write(text,13 if text==title else 10)
        for n,row in enumerate(lines,1):
            write(f'{n}. {row[0]} / {row[2]} {row[3]}')
            write('规格: '+str(row[1]));write('单价CNY '+str(row[4])+' / 金额CNY '+str(row[5])+' / 交期 '+row[6])
        write('合计 CNY '+quote['suggested_total_cny'],13)
        write('备注: '+quote.get('remarks',''));write('审批状态: '+quote['status']+' / v'+str(quote['version']))
        for n,p in enumerate(doc,1):p.insert_text((510,820),f'{n}/{len(doc)}',fontsize=9)
        raw=doc.tobytes(garbage=4,deflate=True);doc.close();return raw,'application/pdf'
    raise ValueError('仅支持PDF或Excel')
