"""Owned cloud-browser interactive preview; isolated synthetic DB, no public hosting claim."""
import os,sys,json,secrets,sqlite3
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
root=Path('tmp/interactive-preview').resolve();root.mkdir(parents=True,exist_ok=True)
secret=root/'access.json'
if not secret.exists():
 secret.write_text(json.dumps({'admin':'QP-Admin-'+secrets.token_urlsafe(10),'reviewer':'QP-Review-'+secrets.token_urlsafe(10),'session':secrets.token_urlsafe(36)}));secret.chmod(0o600)
a=json.loads(secret.read_text());db=root/'synthetic.db'
os.environ.update(QUOTEPILOT_ENV='production',QUOTEPILOT_LOCAL_PREVIEW='1',QUOTEPILOT_PROVIDER='mock',QUOTEPILOT_DB=str(db),QUOTEPILOT_PUBLIC_URL='http://terminal.local:4173',QUOTEPILOT_LOGIN_PASSWORD=a['admin'],QUOTEPILOT_REVIEWER_PASSWORD=a['reviewer'],QUOTEPILOT_SESSION_SECRET=a['session'],QUOTEPILOT_EPHEMERAL_DEMO='1')
import server
server.seed_official=lambda *_:None
if not db.exists():
 from scripts.business_cycle import run_cycle
 def save(_):
  with sqlite3.connect(server.DB) as src,sqlite3.connect(db) as dst:src.backup(dst)
 report=run_cycle(approved_sink=save)
 (root/'seed-evidence.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
 print('Synthetic business workspace ready; no production files used.',flush=True)
import uvicorn
uvicorn.run(server.app,host='0.0.0.0',port=4173,access_log=False)
