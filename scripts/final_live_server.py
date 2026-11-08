"""Local synthetic real-provider capture. Credentials arrive on hidden stdin, never persisted."""
import os,sys,json,subprocess,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
print('Ready for existing server credential on stdin',flush=True)
import getpass
config=json.loads(getpass.getpass('Hidden configuration: '));key=config.pop('existing_key')
local_db=config.pop('local_db',None);browser_script=config.pop('browser_script','scripts/final_browser.cjs')
if browser_script not in ('scripts/final_browser.cjs','scripts/record_final_demo.cjs','scripts/verify_final_user_path.cjs'):raise ValueError('unknown capture script')
if local_db and Path(local_db).resolve().parent!=Path('tmp/final-live').resolve():raise ValueError('synthetic DB directory required')
os.environ.update({str(k):str(v) for k,v in config.items()})
os.environ.update(QUOTEPILOT_ENV='production',QUOTEPILOT_PROVIDER='genesis',GENESIS_API_KEY=key,GENESIS_MODEL_ID='qwen3.8-flash',GENESIS_API_STYLE='responses',MOI_WORKSPACE_ID='ec94c942-2d64-c6be-c968-e793caaef007',QUOTEPILOT_DB=str(Path(local_db or ('tmp/final-live/synthetic-'+str(time.time_ns())+'.db')).resolve()),QUOTEPILOT_PUBLIC_URL='https://127.0.0.1:8877',QUOTEPILOT_LOGIN_PASSWORD='SYNTHETIC_BROWSER_ADMIN_123456',QUOTEPILOT_REVIEWER_PASSWORD='SYNTHETIC_BROWSER_REVIEWER_123456',QUOTEPILOT_SESSION_SECRET='SYNTHETIC_FINAL_LOCAL_ONLY_'+'x'*40)
cache=Path.home()/'.cache/ms-playwright/ffmpeg-1011';cache.mkdir(parents=True,exist_ok=True)
ff=cache/'ffmpeg-linux'
if not ff.exists():ff.symlink_to('/usr/bin/ffmpeg')
import server,uvicorn
server.seed_official=lambda *_:None
Path('tmp/final-live').mkdir(parents=True,exist_ok=True)
# Server and browser share the same process namespace; model credentials never reach browser env.
from threading import Thread
uv=uvicorn.Server(uvicorn.Config(server.app,host='127.0.0.1',port=8877,ssl_keyfile='tmp/local-acceptance/key.pem',ssl_certfile='tmp/local-acceptance/cert.pem',log_level='warning'))
thread=Thread(target=uv.run,daemon=True);thread.start()
env={k:v for k,v in os.environ.items() if not any(x in k.upper() for x in ('GENESIS','MOI_API_KEY','ACCESS_TOKEN'))}
env.update(QUOTEPILOT_SKIP_START_SERVER='1',QUOTEPILOT_TEST_URL='https://127.0.0.1:8877',QUOTEPILOT_BROWSER_OUTPUT='evidence/final-p1/browser',QUOTEPILOT_RECORD_VIDEO='tmp/final-video/raw',CHROMIUM_EXECUTABLE=str(Path('../sprint-runtime/headless/chrome-headless-shell-linux64/chrome-headless-shell').resolve()))
try:
 result=subprocess.run([os.environ['CODEX_PRIMARY_RUNTIME_NODE'],browser_script],env=env)
finally:uv.should_exit=True;thread.join(timeout=10)
sys.exit(result.returncode)
