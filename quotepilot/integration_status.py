"""Configuration and last successful evidence; never pretend this is a live ping."""
import os,json

def integration_status(con):
    configured=(os.environ.get('QUOTEPILOT_PROVIDER','mock')=='genesis' and
                bool(os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY')) and bool(os.environ.get('GENESIS_MODEL_ID')))
    verified=None
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='extraction_runs'").fetchone():
        for row in con.execute("SELECT model,result_json,created_at FROM extraction_runs WHERE provider='genesis' ORDER BY rowid DESC LIMIT 30"):
            result=json.loads(row['result_json'])
            if not result.get('simulated') and result.get('response_id') and row['model']==os.environ.get('GENESIS_MODEL_ID'):
                verified={'model':row['model'],'response_id':result['response_id'],'at':row['created_at']};break
    cloud=None
    workspace=os.environ.get('MOI_WORKSPACE_ID','')
    cloud_configured=bool(workspace and (os.environ.get('MOI_API_KEY') or os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY')))
    if con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cloud_quote_receipts'").fetchone():
        row=con.execute('SELECT receipt_json,verified_at FROM cloud_quote_receipts WHERE workspace_id=? ORDER BY rowid DESC LIMIT 1',(workspace,)).fetchone()
        if row:cloud={**json.loads(row['receipt_json']),'at':row['verified_at']}
    return {'moi_connected':bool(cloud_configured and cloud),'matrixone_connected':bool(cloud_configured and cloud),'model_connected':bool(configured and verified),
            'moi_sql_configured':cloud_configured,'last_verified_cloud_snapshot':cloud,'moi_workflow_connected':False,
            'genesis_configured':bool(configured),'last_successful_genesis_call':verified,
            'connection_check':'已保存的最近成功调用证据，不代表持续在线探测',
            'mode':'genesis_assisted_local' if configured else 'local_offline',
            'next_steps':['在来件页明确触发Genesis提取','对照原文人工确认再入库','确认报价后显式同步MOI云端快照','部署并验证评委访问'],
            'disclaimer':'Genesis模型调用与MOI工作区/MatrixOne数据库是独立验收项；当前业务主库仍为SQLite；云端只镜像已确认报价快照，不代表RFQ/成本/供应商表已迁移，也不代表AI Studio工作流已部署。'}
