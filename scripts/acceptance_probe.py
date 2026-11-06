"""Fresh post-development inputs. Synthetic, not third-party/customer files.
Freeze fixture bytes once; replay identical bytes against baseline and candidate.
"""
import argparse,sys,json,hashlib
from pathlib import Path
from email.message import EmailMessage
from io import BytesIO

def main():
 a=argparse.ArgumentParser();a.add_argument('--project',required=True);a.add_argument('--out',required=True);a.add_argument('--fixtures',required=True);o=a.parse_args()
 sys.path.insert(0,str(Path(o.project).resolve()))
 from quotepilot.parsing import parse_eml
 from quotepilot.xlsxio import read_xlsx
 import fitz
 from openpyxl import Workbook
 fixtures=Path(o.fixtures);fixtures.mkdir(parents=True,exist_ok=True)
 manifest=fixtures/'manifest.json'
 if not manifest.exists():
  cases=[]
  def eml(body=None,html=None,attachment=None,name='fixture.eml'):
   m=EmailMessage();m['From']='Fresh QA <fresh@example.invalid>';m['To']='sales@example.invalid';m['Date']='Thu, 05 Nov 2026 10:00:00 +0800';m['Subject']='SYNTHETIC QA RFQ';m['Message-ID']='<'+name+'@fixture.invalid>'
   m.set_content(body or 'Please quote the attached RFQ. Synthetic acceptance test.')
   if html:m.add_alternative(html,subtype='html')
   if attachment:
    fn,data=attachment;m.add_attachment(data,maintype='application',subtype='octet-stream',filename=fn)
   return m.as_bytes()
  def table(headers,rows):return '<table><tr>'+''.join('<th>'+s+'</th>' for s in headers)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in rows)+'</table>'
  def xlsx(rows,multi=False):
   w=Workbook();w.active.title='Fresh RFQ'
   for row in rows:w.active.append(row)
   if multi:w.create_sheet('Notes').append(['Separate notes'])
   b=BytesIO();w.save(b);return b.getvalue()
  def pdf(text,scan=False):
   d=fitz.open();p=d.new_page();p.insert_text((50,50),text,fontsize=11)
   if scan:
    pix=p.get_pixmap();s=fitz.open();s.new_page().insert_image(p.rect,stream=pix.tobytes('png'));raw=s.tobytes();s.close()
   else:raw=d.tobytes()
   d.close();return raw
  def add(name,raw,expected,issue=False):
   (fixtures/name).write_bytes(raw);cases.append({'name':name,'sha256':hashlib.sha256(raw).hexdigest(),'expected':expected,'must_report_issue':issue,'origin':'new synthetic input created after v0.5 freeze'})
  H=['RFQ No','Part Number','Description','Quantity','Unit','Condition']
  row=['QA-ONE','VX-731','VALVE',3,'EA','FN'];E=[['VX-731',3,'EA']]
  add('01_standard_html.eml',eml(html=table(H,[row]),name='01'),E)
  add('02_plain_text.eml',eml(body='RFQ QA-TEXT\nPart Number: VX-731\nQuantity: 3\nUnit: EA\nCondition: FN',name='02'),E)
  add('03_alias_html.eml',eml(html=table(['询价单号','件号','描述','数量','单位','件状'],[row]),name='03'),E)
  add('04_duplicate_html_header.eml',eml(html=table(['Part Number','Quantity','Quantity','Unit'],[['VX-731',3,300,'EA']]),name='04'),[],True)
  add('05_partial_missing_part.eml',eml(html=table(H,[row,['QA-TWO','','Missing PN',2,'EA','FN']]),name='05'),E,True)
  add('06_zero_quantity.eml',eml(html=table(H,[['QA-ZERO','VX-731','VALVE',0,'EA','FN']]),name='06'),[],True)
  X=[['Part Number','Description','Quantity','Unit','Condition'],['VX-731','VALVE',3,'EA','FN']]
  binaries={
   '07_standard.xlsx':xlsx(X),
   '08_alias.xlsx':xlsx([['件号','数量','单位','件状'],['VX-731',3,'EA','FN']]),
   '09_title_rows.xlsx':xlsx([['CUSTOMER RFQ QA / SYNTHETIC'],[],*X]),
   '10_duplicate_trimmed_headers.xlsx':xlsx([['Part Number','Quantity','Quantity ','Unit'],['VX-731',3,300,'EA']]),
   '11_multisheet.xlsx':xlsx(X,True),
   '12_formula.xlsx':xlsx([X[0],['VX-731','VALVE','=1+2','EA','FN']]),
  }
  for name,data in binaries.items():
   (fixtures/name).write_bytes(data)
   expected=E if name.startswith(('07','08','09','11')) else []
   add(name+'.eml',eml(attachment=(name,data),name=name),expected,not expected)
  ps={
   '13_template.pdf':pdf('REQUEST FOR QUOTATION # RFQ-QA42\n0001\nVX-731\nVALVE\n3 EA'),
   '14_wide_table.pdf':pdf('REQUEST FOR QUOTATION # RFQ-QA43\nPart Number     Description     Quantity     Unit\nVX-731          VALVE           3            EA'),
   '15_long_part.pdf':pdf('REQUEST FOR QUOTATION # RFQ-QA44\n0001\nNAS1149F0363P\nWASHER\n3 EA'),
   '16_wrapped_description.pdf':pdf('REQUEST FOR QUOTATION # RFQ-QA45\n0001\nVX-731\nVALVE ASSEMBLY\nFOR SERVICE\n3 EA'),
   '17_not_an_rfq.pdf':pdf('WAREHOUSE INVENTORY COUNT - NOT A REQUEST\n2026\nVX-731\nVALVE\n3 EA'),
   '18_scan.pdf':pdf('REQUEST FOR QUOTATION # RFQ-QA46\n0001\nVX-731\nVALVE\n3 EA',scan=True),
  }
  for name,data in ps.items():
   (fixtures/name).write_bytes(data)
   expected=[] if name.startswith('17') else ([['NAS1149F0363P',3,'EA']] if name.startswith('15') else E)
   add(name+'.eml',eml(attachment=(name,data),name=name),expected,name.startswith('17'))
  add('19_unknown_part.eml',eml(html=table(H,[['QA-UNKNOWN','UNSEEN-2026','NEW ITEM',2,'FT','NE']]),name='19'),[['UNSEEN-2026',2,'FT']])
  add('20_known_price_new_mail.eml',eml(html=table(H,[['QA-NEW','PN-0001','WASHER',3,'EA','FN']]),name='20'),[['PN-0001',3,'EA']])
  manifest.write_text(json.dumps(cases,ensure_ascii=False,indent=2))
 cases=json.loads(manifest.read_text());results=[]
 for case in cases:
  path=fixtures/case['name'];raw=path.read_bytes();assert hashlib.sha256(raw).hexdigest()==case['sha256']
  try:
   parsed=parse_eml(raw,path.name);actual=[[x['part_number'],x['quantity'],x['unit']] for x in parsed['lines']];notes=parsed['parse_notes'];error=None
  except Exception as ex:actual=[];notes=[str(ex)];error=type(ex).__name__
  extraction_ok=actual==case['expected'];issues_ok=not case['must_report_issue'] or bool(notes)
  results.append({**case,'actual':actual,'notes':notes,'exception':error,'extraction_ok':extraction_ok,'safety_diagnostic_ok':issues_ok,'passed':extraction_ok and issues_ok})
 out={'project':str(Path(o.project).resolve()),'origin':'post-freeze synthetic fixtures; no third-party real customer corpus executed','summary':{'cases':len(results),'passed':sum(x['passed'] for x in results),'failed':sum(not x['passed'] for x in results)},'cases':results}
 Path(o.out).write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out['summary']))
 for c in results:print(('PASS' if c['passed'] else 'FAIL'),c['name'],'expected=',c['expected'],'actual=',c['actual'],'notes=',c['notes'])
 return 0 if not out['summary']['failed'] else 1
if __name__=='__main__':sys.exit(main())
