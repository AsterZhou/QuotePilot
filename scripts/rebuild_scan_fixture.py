"""Regenerate supplemental small scan fixture 11; never overwrites original fixture 08.
The emitted new SHA is explicitly recorded in the synthetic fixture manifest.
"""
from email.message import EmailMessage
import hashlib,json
from pathlib import Path
import pymupdf
root=Path(__file__).resolve().parents[1]/'tests'/'foreign_v07'
text=pymupdf.open();page=text.new_page();page.insert_text((55,75),'SYNTHETIC RFQ - manual fallback test',fontsize=15)
page.insert_text((55,105),'RFQ F07-MANUAL | PN-0001 | 3 EA | FN',fontsize=12)
png=page.get_pixmap().tobytes('png');text.close()
scan=pymupdf.open();page=scan.new_page();page.insert_image(page.rect,stream=png);pdf=scan.tobytes(deflate=True);scan.close()
msg=EmailMessage();msg['From']='Synthetic QA <buyer@fresh07.invalid>';msg['Subject']='SYNTHETIC scan manual test';msg['Message-ID']='<11_scan_small.eml@fresh07.invalid>'
msg.set_content('Synthetic scanned document attached. Manual source verification required.')
msg.add_attachment(pdf,maintype='application',subtype='pdf',filename='scan.pdf')
raw=msg.as_bytes();(root/'11_scan_small.eml').write_bytes(raw)
p=root/'manifest.json';manifest=json.loads(p.read_text())
for case in manifest['cases']:
    if case['name']=='11_scan_small.eml':
        case['sha256']=hashlib.sha256(raw).hexdigest()
        case['fixture_note']='Supplemental small synthetic raster PDF; original fixture 08 is preserved separately.'
p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
