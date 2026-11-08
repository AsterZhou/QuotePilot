"""One explicit MOI native-search diagnostic. Does not provision resources or configure keys."""
import argparse,json,os,uuid
from pathlib import Path
import httpx

BASE='https://api.moi.matrixorigin.cn/v5'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--query',default='LM358 manufacturer Texas Instruments datasheet');args=parser.parse_args()
    key=os.environ.get('MOI_API_KEY') or os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY')
    ws=os.environ.get('MOI_WORKSPACE_ID','')
    if not key or not ws:raise SystemExit('需要已有服务端 Key 和 MOI_WORKSPACE_ID；未执行')
    with httpx.Client(timeout=30,follow_redirects=False,headers={'X-API-Key':key,'X-Workspace-ID':ws}) as client:
        prefix=BASE+'/workspaces/'+ws
        r=client.get(prefix+'/agents',params={'limit':200});r.raise_for_status()
        candidates=[a for a in r.json()['data']['items'] if a.get('status')=='active' and any(t['id']=='moi_web_search' for t in a.get('binding',{}).get('tool_refs',[]))]
        if not candidates:raise SystemExit('未找到声明moi_web_search的可见系统助手；未发送任务')
        agent=candidates[0];path=prefix+'/agents/'+agent['id'];params={'agent_workspace_id':agent['workspace_id']}
        card=client.get(path+'/.well-known/agent-card.json',params=params);card.raise_for_status()
        if 'text/plain' not in card.json().get('defaultInputModes',[]):raise SystemExit('Agent Card未声明文本输入；未发送任务')
        # Keep the public workspace-scoped endpoint even if the card contains an internal URL.
        message='Execute exactly one read-only moi_web_search call, count=3, query='+json.dumps(args.query)+'. Return original tool evidence. Do not create/modify resources, provision compute, buy anything or contact people. Report unavailable tools honestly.'
        body={'jsonrpc':'2.0','id':'quotepilot-'+uuid.uuid4().hex,'method':'message/send','params':{'model':os.environ.get('GENESIS_MODEL_ID','qwen3.8-flash'),'message':{'kind':'message','role':'user','messageId':uuid.uuid4().hex,'parts':[{'kind':'text','text':message}]}}}
        r=client.post(path+'/a2a',params=params,json=body,timeout=90);r.raise_for_status();result=r.json()
    out=Path('evidence/batch1/closeout');out.mkdir(parents=True,exist_ok=True)
    record={'http':r.status_code,'body':result,'agent_id':agent['id']}
    (out/('native_search_'+uuid.uuid4().hex+'.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    task=result.get('result',{});meta=task.get('metadata',{})
    print(json.dumps({'http':r.status_code,'task_id':task.get('id'),'state':task.get('status',{}).get('state'),'trace_id':meta.get('traceId'),'reason':meta.get('reason_display'),
                      'note':'completed也须核对实际moi.tool.result、搜索来源和链接，不能仅凭模型回答认定搜索成功'},ensure_ascii=False))
    return task.get('status',{}).get('state')=='completed'

if __name__=='__main__':raise SystemExit(0 if main() else 1)
