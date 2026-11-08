"""Isolated synthetic ASGI demonstration. No socket, platform or model calls.
Run: python scripts/business_cycle.py --output evidence/business_cycle.json
"""
import argparse, hashlib, json, sys, tempfile, time
from contextlib import ExitStack
from datetime import date, timedelta, datetime, timezone
from email.message import EmailMessage
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))


def run_cycle():
    import server
    from fastapi.testclient import TestClient
    from quotepilot.query_sql import execute
    from quotepilot.backups import inspect, restore
    import fitz
    from openpyxl import load_workbook
    calls=[];today=date.today();url='https://synthetic.example.invalid'
    def call(client,method,path,expected=200,**kwargs):
        started=time.perf_counter();r=client.request(method,path,**kwargs)
        calls.append({'method':method,'path':path,'status':r.status_code,'elapsed_ms':round((time.perf_counter()-started)*1000,2),'expected_status':expected})
        if r.status_code!=expected:raise AssertionError(f'{method} {path}: {r.status_code} {r.text[:500]}')
        return r
    with tempfile.TemporaryDirectory(prefix='quotepilot-synthetic-') as folder,ExitStack() as stack:
        root=Path(folder);db=root/'isolated.db';samples=root/'empty';samples.mkdir()
        env={'QUOTEPILOT_ENV':'production','QUOTEPILOT_PROVIDER':'mock','QUOTEPILOT_PUBLIC_URL':url,'QUOTEPILOT_SESSION_SECRET':'SYNTHETIC_ONLY_'+'x'*40,'QUOTEPILOT_LOGIN_PASSWORD':'SYNTHETIC_ADMIN_123456','QUOTEPILOT_REVIEWER_PASSWORD':'SYNTHETIC_REVIEWER_123456'}
        stack.enter_context(patch.dict('os.environ',env));stack.enter_context(patch.object(server,'DB',db));stack.enter_context(patch.object(server,'SAMPLES',samples));stack.enter_context(patch.object(server,'seed_official',lambda *_:None))
        admin=stack.enter_context(TestClient(server.app,base_url=url,client=('cycle-admin',55000)))
        review=stack.enter_context(TestClient(server.app,base_url=url,client=('cycle-review',55001)))
        call(admin,'GET','/api/operations/metrics',401)
        for client,password in [(admin,env['QUOTEPILOT_LOGIN_PASSWORD']),(review,env['QUOTEPILOT_REVIEWER_PASSWORD'])]:
            client.headers['Origin']=url;call(client,'POST','/auth/login',json={'password':password})
        call(review,'GET','/api/operations/metrics',403)
        versions=[];line_ids=[];q=None
        for n,qty in [(1,100),(2,500)]:
            email_id=f'<synthetic-cycle-{n}@example.invalid>'
            msg=EmailMessage();msg['From']='Synthetic buyer <buyer@example.invalid>';msg['Subject']='SYNTHETIC RFQ';msg['Message-ID']=email_id
            msg.set_content(f'SYNTHETIC ONLY\nRFQ No: SYN-CYCLE\nPart Number: PN-0001\nQuantity: {qty}\nUnit Of Measure: EA\nCondition: FN\nDescription: Synthetic valve spec A')
            call(admin,'POST','/api/emails/import',files={'file':(f'v{n}.eml',msg.as_bytes(),'message/rfc822')})
            lid=call(admin,'GET','/api/lines',params={'email_id':email_id}).json()['rows'][0]['id'];line_ids.append(lid)
            evidence=call(review,'GET',f'/api/lines/{lid}/field-evidence').json()
            call(review,'POST',f'/api/lines/{lid}/review-fields',json={'version':evidence['review']['version'],'changes':{},'actor':'合成演示业务员','reason':'对照合成邮件原文确认','confirm_source':True})
            versions.append(call(review,'POST','/api/rfq-versions',json={'email_id':email_id,'rfq_no':'SYN-CYCLE','actor':'合成演示业务员','reason':'登记合成客户版本'}).json()['id'])
            if n==2:continue
            lines=['SYNTHETIC ONLY - NOT MARKET DATA','SYN-Cheap | PN-0001 | Synthetic valve spec A | EA | FN | CNY 10 | MOQ 1 | lead 20 days','SYN-Fast | PN-0001 | Synthetic valve spec A | EA | FN | CNY 15 | MOQ 1 | lead 2 days','SYN-Balanced | PN-0001 | Synthetic valve spec A | EA | FN | CNY 12 | MOQ 1 | lead 7 days']
            source=call(admin,'POST','/api/supplier-offers/sources',files={'file':('synthetic-suppliers.txt','\n'.join(lines).encode(),'text/plain')}).json()['source_id']
            for index,(supplier,price,lead) in enumerate([('SYN-Cheap',10,20),('SYN-Fast',15,2),('SYN-Balanced',12,7)],2):
                offer={'source_id':source,'source_locator':f'line {index}','source_excerpt':lines[index-1],'supplier':supplier,'part_number':'PN-0001','specification':'Synthetic valve spec A','unit':'EA','condition':'FN','currency':'CNY','unit_price':str(price),'fx_to_cny':'1','fx_source':'CNY nominal synthetic','moq':1,'lead_days':lead,'shipping_total':'0','tax_rate':'0','quote_date':today.isoformat(),'valid_until':(today+timedelta(days=60)).isoformat(),'payment_terms':'Net 30'}
                oid=call(admin,'POST','/api/supplier-offers',json=offer).json()['id']
                call(review,'POST',f'/api/supplier-offers/{oid}/confirm',json={'version':1,'actor':'合成演示业务员','reason':'对照合成供应商原件确认'})
            request={'line_ids':[lid],'asof':today.isoformat(),'valid_until':(today+timedelta(days=14)).isoformat(),'target_margin':'.2','line_costs':{str(lid):{'processing_per_unit_cny':'1','other_total_cny':'2'}},'company_name':'合成演示公司','company_contact':'QA only','customer_name':'合成演示客户','customer_contact':'buyer@example.invalid','delivery_terms':'EXW synthetic','payment_terms':'Net 30','remarks':'SYNTHETIC ONLY - 非真实供应商报价'}
            plans={}
            for scheme in ('lowest_cost','fastest','balanced'):
                plans[scheme]=call(review,'POST','/api/commercial-quotes',json={**request,'scheme':scheme}).json()
            q=plans['lowest_cost'];qid=q['id']
            call(admin,'GET',f'/api/commercial-quotes/{qid}/export/pdf',409)
            body={'version':1,'actor':'合成演示业务员','reason':'审核合成成本与风险','confirm_risks':True}
            call(admin,'POST',f'/api/commercial-quotes/{qid}/approve',409,json=body)
            call(review,'POST',f'/api/commercial-quotes/{qid}/review',json=body)
            call(review,'POST',f'/api/commercial-quotes/{qid}/approve',403,json={**body,'version':2})
            call(admin,'POST',f'/api/commercial-quotes/{qid}/approve',json={**body,'version':2,'actor':'合成演示管理员'})
            pdf=call(admin,'GET',f'/api/commercial-quotes/{qid}/export/pdf').content
            with fitz.open(stream=pdf,filetype='pdf') as doc:
                text=''.join(p.get_text() for p in doc);assert q['suggested_total_cny'] in text and 'PN-0001' in text
            xlsx=call(admin,'GET',f'/api/commercial-quotes/{qid}/export/xlsx').content
            book=load_workbook(BytesIO(xlsx));assert any(c.value==q['suggested_total_cny'] for row in book.active for c in row);book.close()
        diff=call(admin,'GET','/api/rfq-versions/compare',params={'left':versions[0],'right':versions[1],'asof':today.isoformat()}).json()
        assert diff['modified'][0]['changes']['quantity']=={'before':100,'after':500}
        assert any(p['requires_requote'] for p in diff['quote_impacts'])
        unchanged=call(admin,'GET',f'/api/commercial-quotes/{q["id"]}').json()
        assert unchanged['lines'][0]['quantity']==100
        sql=execute(db,'SELECT COUNT(*) AS n FROM commercial_quote_states WHERE status = ?',('approved',));assert sql['rows']==[{'n':1}]
        health=call(admin,'GET','/api/operations/health').json();assert health['integrity']=='ok' and health['audit']['valid']
        metrics=call(admin,'GET','/api/operations/metrics').json();assert metrics['recorded_model_call_count']==0
        backup=call(admin,'GET','/api/admin/backup/download');backup_path=root/'download.db';backup_path.write_bytes(backup.content)
        restored=restore(backup_path,root/'restored.db',backup.headers['X-Backup-SHA256']);assert restored['tables']==inspect(db)['tables']
        return {'run_at':datetime.now(timezone.utc).isoformat(),'synthetic_only':True,'transport':'in-process ASGI TestClient, not public HTTP','external_model_calls':0,'native_platform_verified':False,'public_acceptance':False,'calls':calls,'http_checks':len(calls),'rfq_versions':versions,'quote_id':q['id'],'plans':{k:{'supplier':v['lines'][0]['selected']['offer']['supplier'],'cost_cny':v['total_cost_cny'],'selling_total_cny':v['suggested_total_cny']} for k,v in plans.items()},'quantity_change':diff['modified'][0]['changes']['quantity'],'quote_impacts':diff['quote_impacts'],'approved_snapshot_quantity':unchanged['lines'][0]['quantity'],'exports':{'pdf_sha256':hashlib.sha256(pdf).hexdigest(),'xlsx_sha256':hashlib.sha256(xlsx).hexdigest(),'readback_verified':True},'sql':{**sql,'generation':'script-authored SELECT, not natural language/model'},'audit_valid':health['audit']['valid'],'backup_restore_verified':True,'synthetic_rfq_lines':metrics['rfq_line_count'],'remaining':'No native platform, live model, public network, multitenancy or production deployment verified'}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    result=run_cycle();output=Path(args.output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'report':str(output),'http_checks':result['http_checks'],'audit_valid':result['audit_valid'],'backup_restore_verified':result['backup_restore_verified']},ensure_ascii=False))
