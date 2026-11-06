"""New synthetic inputs after parser freeze; not third-party production files."""
import sys,json,hashlib,random
from pathlib import Path
from email.message import EmailMessage
from io import BytesIO
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
from quotepilot.parsing import parse_eml
import fitz
from openpyxl import Workbook

def main():
 out=root/'tests/foreign_v07';out.mkdir(exist_ok=True);manifest=out/'manifest.json'
 if not manifest.exists():
  frozen={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'quotepilot/parsing.py',root/'quotepilot/xlsxio.py')}
  part='QPX-'+str(random.Random(707113).randrange(100000,999999));cases=[]
  def add(name,attachment,expected,issue=False,body=None):
   m=EmailMessage();m['From']='Synthetic QA <fresh07@example.invalid>';m['Subject']='SYNTHETIC v0.7 '+name;m['Message-ID']='<'+name+'@fresh07.invalid>';m.set_content(body or 'SYNTHETIC TEST ONLY. Please quote attached RFQ.')
   if attachment:
    fn,data=attachment;(out/fn).write_bytes(data);m.add_attachment(data,maintype='application',subtype='octet-stream',filename=fn)
   data=m.as_bytes();(out/name).write_bytes(data);cases.append({'name':name,'sha256':hashlib.sha256(data).hexdigest(),'expected':expected,'must_report_issue':issue})
  def workbook(spec):
   w=Workbook();w.remove(w.active)
   for title,rows,start_col in spec:
    s=w.create_sheet(title)
    for i,row in enumerate(rows,1):
     for j,v in enumerate(row,start_col):s.cell(i,j,v)
   b=BytesIO();w.save(b);return b.getvalue()
  h=['RFQ No','PN','Qty','UOM','Condition']
  add('01_multi_business.eml',('branches.xlsx',workbook([('东区',[h,['F07-A',part,4,'EA','FN']],1),('西区',[h,['F07-B',part,4,'EA','FN']],1)])),[[part,4,'EA','F07-A'],[part,4,'EA','F07-B']])
  add('02_notes.eml',('notes.xlsx',workbook([('RFQ',[h,['F07-N',part,5,'EA','FN']],1),('Instructions',[['Not a business table']],1)])),[[part,5,'EA','F07-N']],True)
  add('03_offset_header.eml',('offset.xlsx',workbook([('需求',[h,['F07-C',part,8,'PCS','NE']],3)])),[[part,8,'PCS','F07-C']])
  add('04_formula.eml',('formula.xlsx',workbook([('RFQ',[h,['F07-F',part,'=2+6','EA','FN']],1)])),[],True)
  def pdf(lines,geometry=False,scan=False):
   d=fitz.open();p=d.new_page(width=1000,height=600);p.insert_text((30,40),'REQUEST FOR QUOTATION # RFQ-NEW-707')
   if geometry:
    for y,row in [(85,['Part Number','Description','Quantity','Unit','Condition']),(120,[part,'CONTROL VALVE','7','EA','NE'])]:
     for x,v in zip([30,220,510,650,760],row):p.insert_text((x,y),v)
   else:p.insert_text((30,85),'\n'.join(lines))
   if scan:
    img=p.get_pixmap(matrix=fitz.Matrix(2,2)).tobytes('png');r=fitz.open();rp=r.new_page(width=1000,height=600);rp.insert_image(rp.rect,stream=img);raw=r.tobytes();r.close()
   else:raw=d.tobytes()
   d.close();return raw
  add('05_geometry_pdf.eml',('geometry.pdf',pdf([],True)),[[part,7,'EA','RFQ-NEW-707']])
  add('06_horizontal_two_rfqs.eml',('horizontal.pdf',pdf(['RFQ No     Part Number     Quantity     Unit','NEW-ROW-1     '+part+'     6     EA','NEW-ROW-2     '+part+'     6     EA'])),[[part,6,'EA','NEW-ROW-1'],[part,6,'EA','NEW-ROW-2']])
  add('07_invalid_pdf_qty.eml',('invalid.pdf',pdf(['Part Number     Quantity     Unit',part+'     0     EA'])),[],True)
  add('08_scan_manual.eml',('scan.pdf',pdf(['0001',part,'CONTROL VALVE','4 EA'],scan=True)),[],True)
  add('09_plain_alias.eml',None,[[part,9,'EA','F07-P']],body='RFQ No: F07-P\nPN: '+part+'\nQty: 9\nUOM: EA\nCondition: FN')
  raw=b'Unrecognized corrupt mail\x00\xff';(out/'10_corrupt.eml').write_bytes(raw);cases.append({'name':'10_corrupt.eml','sha256':hashlib.sha256(raw).hexdigest(),'expected':[],'must_report_issue':True})
  manifest.write_text(json.dumps({'origin':'new post-parser-freeze synthetic inputs; no external customer corpus','parser_freeze_sha256':frozen,'cases':cases},ensure_ascii=False,indent=2))
 data=json.loads(manifest.read_text());results=[]
 for c in data['cases']:
  raw=(out/c['name']).read_bytes();assert hashlib.sha256(raw).hexdigest()==c['sha256']
  try:
   obj=parse_eml(raw,c['name']);actual=[[x['part_number'],x['quantity'],x['unit'],x['source_rfq_no']] for x in obj['lines']];notes=obj['parse_notes'];sources=[x['source'] for x in obj['lines']]
  except Exception as e:actual=[];notes=[type(e).__name__+': '+str(e)];sources=[]
  results.append({**c,'actual':actual,'notes':notes,'sources':sources,'passed':actual==c['expected'] and (not c['must_report_issue'] or bool(notes))})
 result={'origin':data['origin'],'parser_freeze_sha256':data['parser_freeze_sha256'],'summary':{'cases':len(results),'passed':sum(c['passed'] for c in results),'failed':sum(not c['passed'] for c in results)},'cases':results}
 (root/'evidence/foreign_v07.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result['summary']))
 for c in results:print('PASS' if c['passed'] else 'FAIL',c['name'],c['actual'],c['notes'])
 return 0 if all(c['passed'] for c in results) else 1
if __name__=='__main__':sys.exit(main())
