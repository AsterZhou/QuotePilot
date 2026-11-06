"""MOI workflow control through documented APIs; never count a definition as a run."""
import os,re
from urllib.parse import quote
import httpx
from .moi_sql import BASE

class MOIWorkflowClient:
    def __init__(self,transport=None):
        self.key=os.environ.get('MOI_API_KEY') or os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY','')
        self.workspace=os.environ.get('MOI_WORKSPACE_ID','');self.transport=transport
        if not self.key or not self.workspace:raise ValueError('MOI工作流需要服务器密钥及工作区ID')
    def request(self,method,path,body=None):
        with httpx.Client(timeout=40,transport=self.transport,follow_redirects=False) as c:
            r=c.request(method,BASE+path,headers={'X-API-Key':self.key,'X-Workspace-ID':self.workspace},json=body)
            r.raise_for_status();obj=r.json()
        if obj.get('code')!='OK':raise ValueError('MOI工作流请求未成功')
        return obj['data']
    def workflow_path(self,wid):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}',wid):raise ValueError('无效工作流ID')
        return '/workflow/v2/workflow-apps/'+quote(wid,safe='')
    def status(self,wid):
        w=self.request('GET',self.workflow_path(wid))['workflow']
        return {'workflow_id':w['id'],'status':w['status'],'available_actions':w.get('available_actions',[]),'execution_summary':w.get('execution_summary',{}),'definition_exists':True,'native_execution_verified':False,'note':'定义存在不代表已成功运行；当前状态来自真实MOI读取'}
    def start(self,wid,run_ref):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}',run_ref):raise ValueError('无效RFQ运行引用')
        current=self.status(wid)
        if current['status']!='ready':raise ValueError('工作流未就绪：'+current['status']+'；不自动创建资源或重复提交')
        return self.request('POST',self.workflow_path(wid)+'/executions',{'values':{'vars_run_ref':run_ref},'trigger_now':True})
