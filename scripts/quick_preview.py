"""Accountless temporary public preview, synthetic-only. Stops at timeout; no Render mutations."""
import subprocess,os,sys,time,re,json,secrets
from pathlib import Path
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))

def public_tunnel_url(text):
    from urllib.parse import urlsplit
    for candidate in re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com',text):
        if urlsplit(candidate).hostname!='api.trycloudflare.com':return candidate
    return None

def run():
    root=Path('evidence/sprint-p1');root.mkdir(parents=True,exist_ok=True)
    report={'kind':'Cloudflare Quick Tunnel (temporary process-bound preview)','paid_resources_created':0,'production_service_touched':False,'public_acceptance':False,'account_login_required':False}
    log=(root/'tunnel.log').open('w');server=None;tunnel=None
    try:
        tunnel=subprocess.Popen(['../sprint-runtime/cloudflared','tunnel','--url','http://127.0.0.1:8877','--protocol','http2','--no-autoupdate'],stdout=log,stderr=log)
        until=time.monotonic()+45;url=None
        while time.monotonic()<until:
            content=(root/'tunnel.log').read_text(errors='replace');candidate=public_tunnel_url(content)
            if candidate:url=candidate;break
            if tunnel.poll() is not None:break
            time.sleep(.25)
        if not url:raise RuntimeError('Quick Tunnel未分配公网域名；进程退出码='+str(tunnel.poll())+'，详见DNS/连接失败日志；最长等待45秒')
        report['url']=url
        env={**os.environ,'QUOTEPILOT_ACCEPTANCE_PUBLIC_URL':url,'QUOTEPILOT_ACCEPTANCE_HTTP':'1','QUOTEPILOT_ACCEPTANCE_RUN':str(time.time_ns()),'QUOTEPILOT_ACCEPTANCE_ADMIN':secrets.token_urlsafe(24),'QUOTEPILOT_ACCEPTANCE_REVIEWER':secrets.token_urlsafe(24),'QUOTEPILOT_ACCEPTANCE_SECRET':secrets.token_urlsafe(40)}
        # Never copy any model key into this public preview process.
        for key in ('GENESIS_API_KEY','GENESIS_ACCESS_TOKEN','MOI_API_KEY','RENDER_API_KEY'):env.pop(key,None)
        server_log=(root/'server.log').open('w');server=subprocess.Popen([sys.executable,'scripts/acceptance_server.py'],env=env,stdout=server_log,stderr=server_log)
        started=time.monotonic();checks=[]
        for _ in range(8):
            try:
                with httpx.Client(timeout=12) as c:r=c.get(url+'/healthz')
                checks.append({'url':url+'/healthz','status':r.status_code,'elapsed_seconds':round(time.monotonic()-started,3),'body':r.text[:500]})
                if r.status_code==200 and r.json().get('service')=='QuotePilot':break
            except Exception as error:checks.append({'error_type':type(error).__name__,'error':str(error)[:500]})
            time.sleep(1)
        report['health_checks']=checks
        if not checks or checks[-1].get('status')!=200:raise RuntimeError('Public origin did not become reachable; no E2E success claimed')
        env.update(QUOTEPILOT_TEST_URL=url,QUOTEPILOT_SKIP_START_SERVER='1',QUOTEPILOT_BROWSER_OUTPUT=str(root/'browser'),CHROMIUM_EXECUTABLE=str(Path('../sprint-runtime/headless/chrome-headless-shell-linux64/chrome-headless-shell').resolve()))
        run=subprocess.run([os.environ.get('CODEX_PRIMARY_RUNTIME_NODE','node'),'scripts/independent_browser.cjs'],env=env,capture_output=True,text=True,timeout=180)
        (root/'browser-run.log').write_text(run.stdout+run.stderr);report['browser_exit_code']=run.returncode;report['public_acceptance']=run.returncode==0
    except Exception as error:report['blocker']={'type':type(error).__name__,'reason':str(error)[:1000]}
    finally:
        for process in (server,tunnel):
            if process is not None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close();report['preview_closed_after_test']=True;report['persistent_hosting_deployed']=False
        (root/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n');print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':run()
