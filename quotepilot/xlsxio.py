"""Static XLSX values, all RFQ worksheets, immutable sheet/cell provenance."""
from io import BytesIO
from pathlib import Path
import zipfile
from openpyxl import load_workbook
from .fields import canonical,validate_headers

class ParsedRows(list):
    def __init__(self,*args,notes=None):super().__init__(*args);self.notes=notes or []

def read_xlsx(source):
    raw=source if isinstance(source,bytes) else Path(source).read_bytes()
    with zipfile.ZipFile(BytesIO(raw)) as z:
        if sum(i.file_size for i in z.infolist())>50*1024*1024:raise ValueError('XLSX 解压体积超过 50MB')
    wb=load_workbook(BytesIO(raw),read_only=True,data_only=False)
    result=ParsedRows();multi=len(wb.worksheets)>1
    try:
        if len(wb.worksheets)>20:raise ValueError('工作表超过20个，请拆分或人工选择')
        for ws in wb.worksheets:
            if (ws.max_row or 0)>10000 or (ws.max_column or 0)>150:
                raise ValueError('工作表超过10000行/150列，请拆分')
            # Excel producers can understate the used range. Bound the actual XML rows too.
            ws.reset_dimensions()
            rows=[]
            for row_number, row in enumerate(ws, 1):
                if row_number > 10000 or len(row) > 150:
                    raise ValueError('工作表超过10000行/150列，请拆分')
                cells={c.column_letter:('' if c.value is None else str(c.value)) for c in row if c.value is not None}
                if cells:rows.append((next(c.row for c in row if c.value is not None),cells,row))
            if not rows:continue
            header_index=next((i for i,(_,cells,_) in enumerate(rows[:30]) if {'Part Number','Quantity'}.issubset({canonical(v) for v in cells.values()})),None)
            if header_index is None:
                if multi:
                    result.notes.append(f'工作表 {ws.title} 未识别询价表头，未解析；请人工核对原附件')
                    continue
                header_index=0  # Single-sheet master data keeps original schema.
            if ws.sheet_state!='visible':result.notes.append(f'工作表 {ws.title} 为隐藏状态，提取结果需人工复核')
            head=rows[header_index][1];validate_headers(list(head.values()))
            for number,cells,original in rows[header_index+1:]:
                if any(c.data_type=='f' for c in original):raise ValueError(f'公式单元格 {ws.title}!{next(c.coordinate for c in original if c.data_type=="f")} 不作为可靠询价值，请提供静态值')
                record={header.strip():cells.get(col,'').strip() for col,header in head.items() if header.strip()}
                if any(record.values()):
                    record['_source_row']=f'{ws.title} / row {number}' if multi else str(number)
                    record['_source_sheet']=ws.title
                    record['_source_sheet_state']=ws.sheet_state
                    record['_source_cells']={header.strip():f'{ws.title}!{col}{number}' for col,header in head.items() if header.strip()}
                    result.append(record)
        return result
    finally:wb.close()
