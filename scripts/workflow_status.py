"""Read actual workflow state; no deployment, compute allocation or inferred success."""
import getpass,os,sys,json,argparse
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from quotepilot.native_workflow import MOIWorkflowClient
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--workspace',required=True);p.add_argument('--workflow',required=True);a=p.parse_args()
 os.environ['MOI_WORKSPACE_ID']=a.workspace
 if not(os.environ.get('MOI_API_KEY') or os.environ.get('GENESIS_ACCESS_TOKEN')):os.environ['MOI_API_KEY']=getpass.getpass('Personal token (hidden): ').strip()
 print(json.dumps(MOIWorkflowClient().status(a.workflow),ensure_ascii=False,indent=2))
