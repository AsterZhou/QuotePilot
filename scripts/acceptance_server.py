"""Local isolated HTTPS acceptance ONLY. Never loads a production database or key."""
import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
root=Path('tmp/local-acceptance').resolve();root.mkdir(parents=True,exist_ok=True)
os.environ.update(QUOTEPILOT_ENV='production',QUOTEPILOT_PROVIDER='mock',QUOTEPILOT_DB=str(root/('synthetic-'+os.environ.get('QUOTEPILOT_ACCEPTANCE_RUN','default')+'.db')),QUOTEPILOT_PUBLIC_URL='https://127.0.0.1:8877',QUOTEPILOT_SESSION_SECRET='SYNTHETIC_LOCAL_ACCEPTANCE_'+'x'*40,QUOTEPILOT_LOGIN_PASSWORD='SYNTHETIC_BROWSER_ADMIN_123456',QUOTEPILOT_REVIEWER_PASSWORD='SYNTHETIC_BROWSER_REVIEWER_123456')
import server,uvicorn
server.seed_official=lambda *_:None  # isolated empty database; only explicit synthetic browser uploads
uvicorn.run(server.app,host='127.0.0.1',port=8877,ssl_keyfile=str(root/'key.pem'),ssl_certfile=str(root/'cert.pem'),access_log=True)
