"""Public HTTPS acceptance for the explicitly temporary, mock-only free demo."""
import argparse, getpass, json, uuid, sys
from pathlib import Path
from email.message import EmailMessage
from decimal import Decimal
from io import BytesIO
import httpx
from openpyxl import load_workbook

def main():
    p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--out',default='evidence/free_deployment');a=p.parse_args()
    base=a.url.rstrip('/');assert base.startswith('https://')
    out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
    password=getpass.getpass('Admin password (hidden): ')
    report={'url':base,'external':True,'passed':False,'synthetic':True,'model':'mock; no Genesis call','persistence':'ephemeral; not durable','steps':{}}
    def check(r):r.raise_for_status();return r.json()
    try:
        with httpx.Client(timeout=120,follow_redirects=False,headers={'Origin':base}) as c:
            assert c.get(base+'/healthz').status_code==200
            assert c.get(base+'/api/emails').status_code==401
            assert c.get(base+'/api/docs').status_code==401
            assert c.get(base+'/register').status_code==303
            assert '免费临时演示' in c.get(base+'/login').text
            report['steps']['anonymous_and_registration_blocked']=True
            r=c.post(base+'/auth/login',json={'password':password});check(r)
            assert all(x in r.headers['set-cookie'].lower() for x in ('secure','httponly','samesite=strict'))
            assert '免费临时演示' in c.get(base+'/').text
            assert not check(c.get(base+'/api/integration'))['model_connected']
            report['steps']['admin_login_and_explicit_mock_notice']=True
            assert c.post(base+'/api/emails/import',files={'file':('bad.txt',b'bad')}).status_code==415
            assert c.post(base+'/api/emails/import',files={'file':('empty.eml',b'')}).status_code==422
            assert c.post(base+'/api/quote',json={},headers={'Origin':'https://untrusted.invalid'}).status_code==403
            report['steps']['input_and_origin_rejected']=True
            def upload(part):
                ident=uuid.uuid4().hex;eid='<free-'+ident+'@example.invalid>'
                m=EmailMessage();m['From']='SYNTHETIC <test@example.invalid>';m['Subject']='SYNTHETIC FREE '+ident;m['Message-ID']=eid
                m.set_content('RFQ No: FREE-'+ident+'\nPart Number: '+part+'\nQuantity: 3\nUnit: EA\nCondition: FN')
                raw=m.as_bytes();r=check(c.post(base+'/api/emails/import',files={'file':('synthetic.eml',raw,'message/rfc822')}));assert r['new_lines']==1
                assert check(c.post(base+'/api/emails/import',files={'file':('synthetic.eml',raw,'message/rfc822')}))['new_lines']==0
                return check(c.get(base+'/api/lines',params={'email_id':eid}))['rows'][0]['id']
            pn=upload('PN-0001');missing=upload('UNPRICED-FREE-TEST')
            report['steps']['upload_and_duplicate_protection']=True
            q=check(c.post(base+'/api/quote',json={'line_ids':[missing],'asof':'2026-09-20','rate':'20'}))
            review={'version':q['version'],'actor':'AUTOMATED_SYNTHETIC_ACCEPTANCE','reason':'Synthetic public deployment acceptance only','approve':True,'confirm_constraints':True}
            assert c.patch(base+'/api/quotes/'+q['quote_id'],json=review).status_code==409
            report['steps']['unpriced_approval_blocked']=True
            q=check(c.post(base+'/api/quote',json={'line_ids':[pn],'asof':'2026-09-20','rate':'20'}))
            assert Decimal(q['total_cny'])==Decimal('49.89')
            review['version']=q['version'];q=check(c.patch(base+'/api/quotes/'+q['quote_id'],json=review))
            assert q['review_status']=='approved';report['quote_id']=q['quote_id']
            saved=check(c.get(base+'/api/quotes/'+q['quote_id']))
            for kind in ('xlsx','json','csv'):
                r=c.get(base+'/api/quotes/'+q['quote_id']+'/export/'+kind,params={'final':'true'});r.raise_for_status();(out/('quote.'+kind)).write_bytes(r.content)
            wb=load_workbook(out/'quote.xlsx',data_only=True)
            assert Decimal(str(wb.active['F4'].value))==Decimal(saved['total_cny'])==Decimal('49.89')
            assert json.loads((out/'quote.json').read_text())['total_cny']==saved['total_cny']
            report['steps']['pricing_approval_and_export_database_agreement']='49.89 CNY'
            assert c.post(base+'/api/quotes/'+q['quote_id']+'/sync-matrixone',json={}).status_code==409
            report['steps']['unconfigured_cloud_not_claimed']=True
            report['passed']=True
    except Exception as e:
        report['error']=str(e).replace(password,'[redacted]')
    (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False));return 0 if report['passed'] else 1

if __name__=='__main__':sys.exit(main())
