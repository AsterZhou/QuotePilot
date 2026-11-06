"""Run from QuotePilot directory. Key is entered invisibly and stays in process memory."""
import getpass,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--workspace',default=os.environ.get('MOI_WORKSPACE_ID',''));args=p.parse_args()
    token=os.environ.get('GENESIS_ACCESS_TOKEN') or getpass.getpass('Genesis API key (hidden): ').strip()
    if not token:raise SystemExit('没有密钥；离线模式请用 run.sh / run.bat')
    os.environ['GENESIS_ACCESS_TOKEN']=token;os.environ['QUOTEPILOT_PROVIDER']='genesis'
    os.environ.setdefault('GENESIS_MODEL_ID','qwen3.8-flash');os.environ.setdefault('GENESIS_API_STYLE','responses')
    if args.workspace:os.environ['MOI_WORKSPACE_ID']=args.workspace
    os.chdir(Path(__file__).resolve().parents[1])
    import uvicorn
    uvicorn.run('server:app',host='127.0.0.1',port=args.port)
