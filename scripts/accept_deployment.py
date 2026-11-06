"""Real authenticated end-to-end acceptance against a deployed HTTPS server.
Never mocks the model or cloud. Uses synthetic data and explicit test-only approval.
"""
import argparse,getpass,os,sys,json,uuid,ssl,csv
from decimal import Decimal
from pathlib import Path
from email.message import EmailMessage
from io import BytesIO
import httpx
from openpyxl import load_workbook
from urllib.parse import urlsplit

def main():
 p=argparse.ArgumentParser();p.add_argument('--url',required=True);p.add_argument('--out',default='evidence/deployment_acceptance');p.add_argument('--ca');p.add_argument('--skip-cloud',action='store_true');a=p.parse_args()
 base=a.url.rstrip('/');u=urlsplit(base)
 if u.scheme!='https' or u.username or u.password or u.path not in ('','/'):raise SystemExit('An HTTPS origin is required')
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True)
 password=os.environ.get('QP_ACCEPTANCE_PASSWORD') or getpass.getpass('Demo login password (hidden): ')
 report={'public_url':base,'external':u.hostname not in ('localhost','127.0.0.1','::1'),'passed':False,'synthetic':True,'steps':{}}
 def save(): (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 def check(response):response.raise_for_status();return response.json()
 verify=ssl.create_default_context(cafile=a.ca) if a.ca else True
 try:
  with httpx.Client(verify=verify,timeout=180,trust_env=report['external'],headers={'Origin':base},follow_redirects=False) as c:
   assert c.get(base+'/api/emails').status_code==401;report['steps']['anonymous_api_denied']=True
   r=c.post(base+'/auth/login',json={'password':password});check(r);cookie=r.headers.get('set-cookie','').lower();assert all(x in cookie for x in ('secure','httponly','samesite=strict'));report['steps']['authenticated_session']=True
   ident=str(uuid.uuid4());email_id='<v07-'+ident+'@synthetic.invalid>';m=EmailMessage();m['From']='SYNTHETIC ACCEPTANCE <test@example.invalid>';m['Subject']='SYNTHETIC acceptance '+ident;m['Message-ID']=email_id
   m.set_content('SYNTHETIC RFQ ONLY. Please quote three EA of PN-0001 in FN condition. Also quote two EA of GSK-001; condition not specified. Do not invent prices.')
   raw=m.as_bytes();(out/'input.eml').write_bytes(raw)
   check(c.post(base+'/api/emails/preview',files={'file':('acceptance.eml',raw,'message/rfc822')}));check(c.post(base+'/api/emails/import',files={'file':('acceptance.eml',raw,'message/rfc822')}));report['steps']['eml_upload']=True
   from urllib.parse import quote
   path=base+'/api/emails/'+quote(email_id,safe='')
   ai=check(c.post(path+'/extract',json={}));assert ai['provider']=='genesis' and ai['simulated'] is False and ai.get('response_id')
   (out/'extraction.json').write_text(json.dumps(ai,ensure_ascii=False,indent=2));report['steps']['real_genesis']={'model':ai['model'],'response_id':ai['response_id'],'usage':ai.get('usage')}
   before=check(c.get(base+'/api/lines',params={'email_id':email_id}));assert before['total']==0
   selected=[]
   for idx,line in enumerate(ai['lines']):
    assert line['evidence'] in m.get_content()
    if line['part_number']=='PN-0001':assert line['quantity']==3;qty=4;condition='FN'
    elif line['part_number']=='GSK-001':assert line['quantity']==2;qty=2;condition=''
    else:raise AssertionError('Unexpected model part; no adoption')
    selected.append({'source_index':idx,'part_number':line['part_number'],'quantity':qty,'unit':'EA','condition':condition,'source_rfq_no':'SYNTH-'+ident[:8]})
   assert len(selected)==2
   body={'actor':'AUTOMATED_ACCEPTANCE_ONLY','reason':'合成测试对照原文；将PN数量由3修正为4以验证人工变更留痕','lines':selected,'confirm_source':False}
   url=base+'/api/extractions/'+ai['run_id']+'/confirm';assert c.post(url,json=body).status_code==409
   body['confirm_source']=True;adopted=check(c.post(url,json=body));again=check(c.post(url,json=body));assert again['idempotent'];report['steps']['human_confirmation_and_repeat_protection']=True
   demand=check(c.get(base+'/api/lines',params={'email_id':email_id}))['rows'];ids=[r['id'] for r in demand]
   mixed=check(c.post(base+'/api/quote',json={'line_ids':ids,'asof':'2026-09-20','rate':'20'}));missing=next(x for x in mixed['lines'] if x['part_number']=='GSK-001');assert not missing['line_total_cny']
   review={'version':mixed['version'],'actor':'AUTOMATED_ACCEPTANCE_ONLY','reason':'合成自动化验收','approve':True,'confirm_constraints':True}
   assert c.patch(base+'/api/quotes/'+mixed['quote_id'],json=review).status_code==409;report['steps']['missing_price_blocks_approval']=True
   pn=next(r for r in demand if r['part_number']=='PN-0001');detail=check(c.get(base+'/api/lines/'+str(pn['id'])));ev=json.loads(detail['evidence']['raw_json']);assert ev['original_model_suggestion']['quantity']==3 and ev['confirmed_fields']['quantity']==4
   q=check(c.post(base+'/api/quote',json={'line_ids':[pn['id']],'asof':'2026-09-20','rate':'20'}));review['version']=q['version'];q=check(c.patch(base+'/api/quotes/'+q['quote_id'],json=review));assert q['total_cny']=='66.52';report['quote_id']=q['quote_id'];report['steps']['deterministic_total_cny']='66.52'
   for kind in ('csv','xlsx','json'):
    r=c.get(base+'/api/quotes/'+q['quote_id']+'/export/'+kind,params={'final':'true'});r.raise_for_status();(out/('quote.'+kind)).write_bytes(r.content)
   wb=load_workbook(out/'quote.xlsx',data_only=True);assert str(wb.active['F4'].value)=='66.52';assert json.loads((out/'quote.json').read_text())['total_cny']=='66.52';rows=list(csv.DictReader((out/'quote.csv').read_text(encoding='utf-8-sig').splitlines()));assert sum((Decimal(x['amount_cny']) for x in rows if x['amount_cny']),Decimal(0))==Decimal(q['total_cny']);report['steps']['export_and_db_agree']=True
   if not a.skip_cloud:
    receipt=check(c.post(base+'/api/quotes/'+q['quote_id']+'/sync-matrixone',json={}));assert receipt['verified'];report['steps']['real_cloud_snapshot']=receipt
   else:report['steps']['real_cloud_snapshot']='未执行：显式skip-cloud'
   report['passed']=True;save();print('PASS',base,'66.52 CNY; real Genesis; cloud=' + str(not a.skip_cloud))
 except Exception as e:
  report['error']={'type':type(e).__name__,'message':str(e).replace(password,'[redacted]')};save();print('FAILED; see result.json');return 1
 return 0
if __name__=='__main__':sys.exit(main())
