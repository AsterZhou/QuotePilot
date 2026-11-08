"""Bounded real platform preflight; no credentials are written to evidence."""
import os,sys,json,time,re
from pathlib import Path
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
WORKSPACE=os.environ.get('MOI_WORKSPACE_ID','ec94c942-2d64-c6be-c968-e793caaef007')
WID='45e246b6-9a6f-5331-82cd-44c00f67cb18'
def redact(value,secret):
    if isinstance(value,dict):return {k:('[REDACTED]' if k.lower() in ('token','access_token','refresh_token','password','secret','authorization','api_key','cookie','set-cookie') else redact(v,secret)) for k,v in value.items()}
    if isinstance(value,list):return [redact(x,secret) for x in value]
    if isinstance(value,str):
        value=value.replace(secret,'[REDACTED]') if secret else value
        return re.sub(r'sk-uca-v1-[A-Za-z0-9_-]+','[REDACTED]',value)
    return value

def probe():
    secret=os.environ.get('MOI_API_KEY') or os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY','')
    endpoints=[('models','https://token.moi.matrixorigin.cn/v1/models'),('workflow','https://api.moi.matrixorigin.cn/v5/workflow/v2/workflow-apps/'+WID),('instances','https://api.moi.matrixorigin.cn/v5/compute-resources'),('specs','https://api.moi.matrixorigin.cn/v5/compute-resource-specs'),('spec_permission','https://api.moi.matrixorigin.cn/v5/compute-resource-specs/management-permission')]
    if not secret:return {'checked_at':datetime.now(timezone.utc).isoformat(),'credential_configured':False,'blocked':'No server credential in this process; no network request fabricated','requests':[]}
    def request(item):
        name,url=item;start=time.monotonic()
        try:
            headers={'Authorization':'Bearer '+secret} if name=='models' else {'X-API-Key':secret,'X-Workspace-ID':WORKSPACE}
            with httpx.Client(timeout=httpx.Timeout(15,connect=8),follow_redirects=False) as client:r=client.get(url,headers=headers)
            try:body=redact(r.json(),secret)
            except ValueError:body=redact(r.text[:3000],secret)
            return {'name':name,'method':'GET','url':url,'status':r.status_code,'elapsed_seconds':round(time.monotonic()-start,3),'trace_headers':{k:v for k,v in r.headers.items() if k.lower() in ('x-request-id','x-trace-id','traceparent')},'response':body}
        except Exception as error:return {'name':name,'method':'GET','url':url,'status':None,'elapsed_seconds':round(time.monotonic()-start,3),'error_type':type(error).__name__,'error':redact(str(error),secret)}
    with ThreadPoolExecutor(max_workers=5) as executor:requests=list(executor.map(request,endpoints))
    return {'checked_at':datetime.now(timezone.utc).isoformat(),'baseline':'43e76e0','credential_configured':True,'workspace_id':WORKSPACE,'workflow_id':WID,'native_execution_verified':False,'requests':requests,'resource_mutations':0,'note':'Real reads only. Workflow success requires an execution ID and terminal result, not this preflight.'}
if __name__=='__main__':
    result=probe();target=Path('evidence/sprint-p0/preflight.json');target.parent.mkdir(parents=True,exist_ok=True);target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'requests':[{'name':x['name'],'status':x.get('status'),'error_type':x.get('error_type')} for x in result['requests']],'credential_configured':result['credential_configured']}))
