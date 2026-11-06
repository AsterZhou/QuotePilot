"""Run on a real Docker daemon, e.g. GitHub Actions. No model key is needed.
This tests container/production access/persistence; not real Genesis or public UI.
"""
import argparse,subprocess,os,json,secrets,time,urllib.request,urllib.error,uuid,shutil
from email.message import EmailMessage
from http.cookies import SimpleCookie
from pathlib import Path

def main():
 p=argparse.ArgumentParser();p.add_argument('--tag',default='quotepilot-container-test:local');a=p.parse_args()
 root=Path(__file__).resolve().parents[1];out=root/'evidence/container';out.mkdir(exist_ok=True)
 report={'real_docker':False,'passed':False,'real_genesis':'未执行：容器检查使用明确Mock模式','public_browser':'未执行','steps':{}}
 def save(): (out/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 if not shutil.which('docker'):
  report['error']='Docker CLI unavailable';save();print(json.dumps(report,ensure_ascii=False));return 2
 suffix=uuid.uuid4().hex[:10];container='qp-test-'+suffix;volume='qp-data-'+suffix
 env=dict(os.environ,QUOTEPILOT_LOGIN_PASSWORD=secrets.token_urlsafe(24),QUOTEPILOT_SESSION_SECRET=secrets.token_hex(32))
 origin='https://container-test.example.invalid'
 def cmd(args,**kw):return subprocess.run(['docker']+args,check=True,text=True,**kw)
 def request(base,path,data=None,cookie=None,content_type='application/json'):
  headers={'Origin':origin}
  if cookie:headers['Cookie']=cookie
  if data is not None:headers['Content-Type']=content_type
  r=urllib.request.Request(base+path,data=data,headers=headers)
  try:
   with urllib.request.urlopen(r,timeout=20) as x:return x.status,x.read(),x.headers
  except urllib.error.HTTPError as e:return e.code,e.read(),e.headers
 def start():
  cmd(['run','-d','--name',container,'-p','127.0.0.1::10000','-v',volume+':/data',
       '-e','PORT=10000','-e','QUOTEPILOT_ENV=production','-e','QUOTEPILOT_PUBLIC_URL='+origin,
       '-e','QUOTEPILOT_PROVIDER=mock','-e','QUOTEPILOT_LOGIN_PASSWORD','-e','QUOTEPILOT_SESSION_SECRET',a.tag],env=env,capture_output=True)
  port=cmd(['port',container,'10000/tcp'],capture_output=True).stdout.strip().rsplit(':',1)[1];base='http://127.0.0.1:'+port
  for _ in range(90):
   try:
    if request(base,'/healthz')[0]==200:return base
   except (OSError,ValueError):pass
   time.sleep(1)
  raise RuntimeError('Container health did not become ready')
 def login(base):
  status,body,headers=request(base,'/auth/login',json.dumps({'password':env['QUOTEPILOT_LOGIN_PASSWORD']}).encode());assert status==200
  cookies=SimpleCookie();cookies.load(headers['Set-Cookie']);v=cookies['qp_session'];assert v['secure'] and v['httponly'] and v['samesite']=='strict'
  # Render terminates HTTPS upstream; this direct loopback test forwards the secure cookie explicitly.
  return 'qp_session='+v.value
 try:
  cmd(['info'],capture_output=True);report['real_docker']=True
  with (out/'build.log').open('w') as log:cmd(['build','--pull','-t',a.tag,'.'],cwd=root,stdout=log,stderr=subprocess.STDOUT)
  report['steps']['image_built']=True;save();base=start()
  assert request(base,'/api/emails')[0]==401;cookie=login(base);report['steps']['production_session']=True
  m=EmailMessage();m['From']='CI SYNTHETIC <ci@example.invalid>';m['Subject']='SYNTHETIC CONTAINER '+suffix;m['Message-ID']='<container-'+suffix+'@example.invalid>';m.set_content('RFQ No: CI-'+suffix+'\nPart Number: PN-0001\nQuantity: 3\nUnit: EA\nCondition: FN')
  boundary='qp-'+suffix;raw=m.as_bytes();multipart=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="ci.eml"\r\nContent-Type: message/rfc822\r\n\r\n'.encode()+raw+f'\r\n--{boundary}--\r\n'.encode())
  status,body,_=request(base,'/api/emails/import',multipart,cookie,'multipart/form-data; boundary='+boundary);assert status==200 and json.loads(body)['new_lines']==1
  report['steps']['eml_uploaded']=True;save();cmd(['rm','-f',container],capture_output=True);base=start();cookie=login(base)
  status,body,_=request(base,'/api/emails',cookie=cookie);assert status==200 and any(x['subject']==m['Subject'] for x in json.loads(body));report['steps']['persistent_volume_survived_recreation']=True
  status,body,_=request(base,'/api/emails/import',multipart,cookie,'multipart/form-data; boundary='+boundary);assert status==200 and json.loads(body)['new_lines']==0;report['steps']['repeat_import_no_duplicate']=True
  report['passed']=True;save();print(json.dumps(report,ensure_ascii=False));return 0
 except Exception as e:
  report['error']=type(e).__name__+': '+str(e);save();print(json.dumps(report,ensure_ascii=False));return 1
 finally:
  with (out/'container.log').open('w') as log:subprocess.run(['docker','logs',container],stdout=log,stderr=log,text=True)
  subprocess.run(['docker','rm','-f',container],capture_output=True)
  subprocess.run(['docker','volume','rm',volume],capture_output=True)
if __name__=='__main__':raise SystemExit(main())
