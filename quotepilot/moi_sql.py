"""Documented MOI asynchronous SQL API. Approved quote mirror, not primary storage."""
import base64,hashlib,json,os,re,time
import httpx
from .store import audit

BASE='https://api.moi.matrixorigin.cn/v5'
DATABASE='quotepilot'
TABLE='quote_snapshots_v1'

class MOISQLClient:
    def __init__(self,transport=None):
        self.key=os.environ.get('MOI_API_KEY') or os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY','')
        self.workspace=os.environ.get('MOI_WORKSPACE_ID','')
        self.transport=transport
        if not self.key or not self.workspace:raise ValueError('需要API密钥和MOI_WORKSPACE_ID')
    def request(self,path,body):
        # Separate clients deliberately avoid server-issued cookie/header auth conflicts.
        with httpx.Client(timeout=30,transport=self.transport,follow_redirects=False) as client:
            r=client.post(BASE+path,headers={'X-API-Key':self.key,'X-Workspace-ID':self.workspace},json=body)
            r.raise_for_status();obj=r.json()
        if obj.get('code') not in (200,'OK'):raise ValueError('MOI请求未成功，未记录同步成功')
        return obj.get('data',{})
    def execute(self,sql):
        data=self.request('/query/execute',{'query':sql,'offset':0,'limit':10})
        qid=data.get('query_id') or data.get('id')
        if not qid:raise ValueError('MOI未返回query_id')
        for _ in range(30):
            state=self.request('/query/describe',{'query_id':qid})
            if state.get('status')=='success':
                sid=state.get('statement_id')
                result=self.request('/query/result',{'statement_id':sid,'offset':0,'limit':10}) if sid and sql.lstrip().upper().startswith(('SELECT ','SHOW ','WITH ')) else state
                return {'query_id':qid,'statement_id':sid,'data':result}
            if state.get('status') in ('failed','killed'):raise ValueError('MOI SQL执行失败；没有确认云端写入')
            time.sleep(.5)
        raise ValueError('MOI SQL超时；状态未知，可安全重试并读回校验')

def mirror_quote(client,quote):
    if quote.get('review_status')!='approved':raise ValueError('仅允许同步已人工确认的报价')
    qid=quote['quote_id'];version=quote['version']
    if not re.fullmatch(r'QP-[A-Z0-9]{12}',qid) or type(version) is not int or version<1:raise ValueError('无效报价编号或版本')
    raw=json.dumps(quote,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    digest=hashlib.sha256(raw).hexdigest();encoded=base64.b64encode(raw).decode()
    if len(raw)>2_000_000:raise ValueError('报价快照超过2MB，请使用批量迁移')
    # All interpolated values are validated ASCII/base64/hex/integers, no arbitrary SQL text.
    queries=[]
    queries.append(client.execute('CREATE DATABASE IF NOT EXISTS '+DATABASE))
    name=DATABASE+'.'+TABLE
    queries.append(client.execute('CREATE TABLE IF NOT EXISTS '+name+' (quote_id VARCHAR(32) NOT NULL, version INT NOT NULL, payload_sha256 CHAR(64) NOT NULL, payload_base64 LONGTEXT NOT NULL, PRIMARY KEY (quote_id,version))'))
    queries.append(client.execute("INSERT IGNORE INTO "+name+" (quote_id,version,payload_sha256,payload_base64) VALUES ('"+qid+"',"+str(version)+",'"+digest+"','"+encoded+"')"))
    result=client.execute("SELECT payload_sha256,payload_base64 FROM "+name+" WHERE quote_id='"+qid+"' AND version="+str(version));queries.append(result)
    rows=result['data'].get('result',[])
    if len(rows)!=1 or len(rows[0])!=2:raise ValueError('云端报价读回不唯一或为空')
    cells=rows[0]
    if not all(isinstance(c,dict) and c.get('Valid') for c in cells):raise ValueError('云端读回存在空值')
    returned_hash,returned_payload=[c['String'] for c in cells]
    if returned_hash!=digest or returned_payload!=encoded or hashlib.sha256(base64.b64decode(returned_payload,validate=True)).hexdigest()!=digest:
        raise ValueError('云端快照校验失败；同编号版本可能已存在不同内容')
    return {'verified':True,'quote_id':qid,'version':version,'workspace_id':client.workspace,'database':DATABASE,'table':TABLE,'payload_sha256':digest,'query_ids':[q['query_id'] for q in queries],'primary_store':'sqlite','scope':'approved_quote_snapshot_mirror'}

def ensure_receipts(con):
    con.execute('''CREATE TABLE IF NOT EXISTS cloud_quote_receipts (quote_id TEXT NOT NULL,version INTEGER NOT NULL,workspace_id TEXT NOT NULL,receipt_json TEXT NOT NULL,verified_at TEXT DEFAULT CURRENT_TIMESTAMP,PRIMARY KEY(quote_id,version,workspace_id))''');con.commit()

def sync_quote(con,quote,client=None):
    client=client or MOISQLClient();receipt=mirror_quote(client,quote)
    ensure_receipts(con)
    with con:
        con.execute('INSERT OR REPLACE INTO cloud_quote_receipts(quote_id,version,workspace_id,receipt_json) VALUES(?,?,?,?)',(quote['quote_id'],quote['version'],client.workspace,json.dumps(receipt,ensure_ascii=False)))
        audit(con,'matrixone_snapshot_verified',quote['quote_id'],receipt)
    return receipt
