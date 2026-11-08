"""Create only synthetic browser inputs and a local self-signed TLS certificate."""
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
from email.message import EmailMessage
from pathlib import Path
import subprocess
import pymupdf
root=Path('tmp/local-acceptance');root.mkdir(parents=True,exist_ok=True)
if not (root/'key.pem').exists():
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-keyout',str(root/'key.pem'),'-out',str(root/'cert.pem'),'-days','2','-subj','/CN=localhost'],check=True,capture_output=True)
for n,qty in [(1,100),(2,500)]:
    msg=EmailMessage();msg['From']='Synthetic Buyer <browser@example.invalid>';msg['Subject']=f'SYNTHETIC BROWSER V{n}';msg['Message-ID']=f'<browser-v{n}@example.invalid>'
    msg.set_content(f'SYNTHETIC ONLY\nRFQ No: BROWSER-RFQ\nPart Number: PN-0001\nQuantity: {qty}\nUnit Of Measure: EA\nCondition: FN\nDescription: Synthetic valve spec A')
    (root/f'rfq-v{n}.eml').write_bytes(msg.as_bytes())
today=datetime.now(ZoneInfo('Asia/Shanghai')).date();doc=pymupdf.open()
for supplier,price,lead in [('SYN-Cheap',10,20),('SYN-Fast',15,2),('SYN-Balanced',12,7)]:
    page=doc.new_page();values={'Supplier':supplier,'Part Number':'PN-0001','Specification':'Synthetic valve spec A','Unit':'EA','Condition':'FN','Currency':'CNY','Unit Price':price,'FX to CNY':1,'FX source':'CNY nominal synthetic','MOQ':1,'Lead days':lead,'Shipping total':0,'Tax rate':'0%','Quote date':today.isoformat(),'Valid until':(today+timedelta(days=60)).isoformat(),'Payment terms':'Net 30'}
    page.insert_text((40,45),'SYNTHETIC QUOTATION - NOT MARKET DATA\n'+'\n'.join(f'{k}: {v}' for k,v in values.items()),fontsize=11)
(root/'suppliers.pdf').write_bytes(doc.tobytes(deflate=True));doc.close()
print('Synthetic inputs ready; existing test databases remain untouched.')
