"""One real native start attempt + Genesis extraction + approved synthetic quote mirror.
Requires existing server env credentials. No instance creation, retries or production DB.
"""
import sys,os,json,time,hashlib,base64
from pathlib import Path
from datetime import datetime,timezone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.sprint_probe import redact,WORKSPACE,WID
import httpx

class EvidenceTransport(httpx.BaseTransport):
    def __init__(self,secret):
        self.secret=secret;self.calls=[];self.inner=httpx.HTTPTransport(proxy=os.environ.get('HTTPS_PROXY') or None)
    def handle_request(self,request):
        started=time.monotonic();item={'method':request.method,'url':str(request.url)}
        try:
            try:body=json.loads(request.content)
            except ValueError:body={}
            if 'query' in body:body={**body,'query':{'sha256':hashlib.sha256(body['query'].encode()).hexdigest(),'prefix':body['query'][:180]}}
            item['request_body']=redact(body,self.secret)
            response=self.inner.handle_request(request);response.read()
            try:result=response.json()
            except ValueError:result={'non_json':response.text[:2000]}
            # Quote readback may be large; verified in adapter, record hash/size in evidence.
            for row in result.get('data',{}).get('result',[]) if isinstance(result.get('data'),dict) else []:
                for cell in row:
                    if isinstance(cell,dict) and len(str(cell.get('String','')))>2000:
                        value=cell['String'];cell['String']={'bytes':len(value),'sha256':hashlib.sha256(value.encode()).hexdigest(),'note':'body omitted; full content verified by mirror adapter'}
            item.update(status=response.status_code,response=redact(result,self.secret),trace_headers={k:v for k,v in response.headers.items() if k in ('x-request-id','x-trace-id','traceparent')})
            return response
        except Exception as error:
            item.update(status=None,error_type=type(error).__name__,error=redact(str(error),self.secret));raise
        finally:item['elapsed_seconds']=round(time.monotonic()-started,3);self.calls.append(item)
    def close(self):pass


def run():
    secret=os.environ.get('GENESIS_API_KEY') or os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('MOI_API_KEY')
    if not secret:raise ValueError('缺少现有服务端密钥，不要求新建Key')
    os.environ['MOI_WORKSPACE_ID']=WORKSPACE;os.environ['GENESIS_MODEL_ID']='qwen3.8-flash';os.environ['GENESIS_API_STYLE']='responses'
    transport=EvidenceTransport(secret);report={'checked_at':datetime.now(timezone.utc).isoformat(),'baseline':'43e76e0','synthetic_only':True,'native_execution_id':None,'native_execution_verified':False,'resource_creations':0}
    try:
        from quotepilot.native_workflow import MOIWorkflowClient
        client=MOIWorkflowClient(transport)
        try:
            # One documented server attempt, even though preflight reports disabled.
            data=client.request('POST',client.workflow_path(WID)+'/executions',{'values':{'vars_run_ref':'SPRINT-SYNTHETIC-20261108'},'trigger_now':True})
            eid=data.get('workflow_run',{}).get('execution_id');report['native_execution_id']=eid
            if eid:report['native_execution_detail']=client.execution(WID,eid)
            report['native_start_response']=data
        except Exception as error:report['native_blocker']={'type':type(error).__name__,'reason':redact(str(error),secret),'preflight':'workflow disabled, no compute instances; no auto enable or resource creation'}
        from quotepilot.providers import GenesisProvider
        try:
            text='SYNTHETIC RFQ: Please quote 100 EA of PN-0001 in FN condition. RFQ BROWSER-RFQ. Description: Synthetic valve spec A.'
            extracted=GenesisProvider(transport).extract(text)
            assert extracted['lines'] and extracted['lines'][0]['part_number']=='PN-0001' and extracted['lines'][0]['quantity']==100
            report['genesis']={'verified':True,**extracted,'input':text,'input_sha256':hashlib.sha256(text.encode()).hexdigest(),'human_review_required':True,'note':'真实独立Genesis推理；不等于MOI原生工作流节点已运行'}
        except Exception as error:report['genesis']={'verified':False,'error_type':type(error).__name__,'error':redact(str(error),secret)}
        from quotepilot.moi_sql import MOISQLClient
        sql=MOISQLClient(transport)
        try:
            report['sql_probe']=sql.execute('SELECT 1 AS quotepilot_sprint_connectivity')
            from scripts.business_cycle import run_cycle
            from quotepilot.platform_quotes import mirror_commercial_quote
            def sink(approved):report['commercial_mirror']=mirror_commercial_quote(sql,approved)
            report['local_quote_cycle']=run_cycle(approved_sink=sink)
        except Exception as error:report['sql_or_mirror_blocker']={'type':type(error).__name__,'error':redact(str(error),secret)}
    finally:
        report['http_calls']=transport.calls;report['automatic_retries']=0
        path=Path('evidence/sprint-p0/live.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');transport.inner.close()
    print(json.dumps({'native_execution_id':report['native_execution_id'],'native_verified':report['native_execution_verified'],'genesis_verified':report.get('genesis',{}).get('verified'),'matrixone_mirror_verified':report.get('commercial_mirror',{}).get('verified'),'http_calls':len(transport.calls)},ensure_ascii=False))
if __name__=='__main__':run()
