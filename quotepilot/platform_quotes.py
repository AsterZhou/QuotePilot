"""Real MatrixOne commercial quote mirror. Local approval is mandatory; not a workflow run."""
import base64,hashlib,json,re

def mirror_commercial_quote(client,quote):
    if quote.get('status')!='approved':raise ValueError('仅同步已双角色审批的商业报价')
    if not quote.get('reviewer_account') or not quote.get('approver_account') or quote['reviewer_account']==quote['approver_account']:raise ValueError('商业报价缺少不同角色的审批依据')
    qid=quote['id'];version=quote['version']
    if not re.fullmatch(r'CQ-[A-F0-9]{16}',qid) or type(version) is not int or version<3:raise ValueError('商业报价编号/版本无效')
    raw=json.dumps(quote,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
    if len(raw)>2_000_000:raise ValueError('快照超过2MB')
    payload=base64.b64encode(raw).decode();digest=hashlib.sha256(raw).hexdigest()
    table='quotepilot_sprint.commercial_quote_snapshots_v1';results=[]
    for sql in ['CREATE DATABASE IF NOT EXISTS quotepilot_sprint',f'CREATE TABLE IF NOT EXISTS {table} (quote_id VARCHAR(32) NOT NULL, version INT NOT NULL, payload_sha256 CHAR(64) NOT NULL, payload_base64 LONGTEXT NOT NULL, PRIMARY KEY(quote_id,version))',f"INSERT IGNORE INTO {table} VALUES ('{qid}',{version},'{digest}','{payload}')",f"SELECT payload_sha256,payload_base64 FROM {table} WHERE quote_id='{qid}' AND version={version}"]:
        results.append(client.execute(sql))
    cells=results[-1]['data'].get('result',[])
    if len(cells)!=1 or len(cells[0])!=2 or not all(isinstance(c,dict) and c.get('Valid') for c in cells[0]):raise ValueError('云端快照读回为空/不唯一')
    remote_hash,remote_payload=[c['String'] for c in cells[0]]
    if remote_hash!=digest or remote_payload!=payload or hashlib.sha256(base64.b64decode(remote_payload,validate=True)).hexdigest()!=digest:raise ValueError('云端商业报价快照校验失败')
    return {'verified':True,'quote_id':qid,'version':version,'payload_sha256':digest,'table':table,'query_ids':[r['query_id'] for r in results],'scope':'application_orchestrated_approved_commercial_snapshot','native_workflow_execution':False,'primary_store':'SQLite'}
