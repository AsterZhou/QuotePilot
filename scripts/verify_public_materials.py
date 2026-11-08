"""Anonymous external HTTP validation of material links, never business/public E2E."""
import argparse,json,urllib.request,time,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--origin',required=True);p.add_argument('--output',default='evidence/final-p3/public-http-final.json');args=p.parse_args()
origin=args.origin.rstrip('/');rows=[]
for path in ['/docs/','/video/','/quotepilot-v2.mp4']:
 start=time.monotonic()
 try:
  request=urllib.request.Request(origin+path,headers={'User-Agent':'QuotePilot-public-link-verifier/1.0'})
  with urllib.request.urlopen(request,timeout=25) as response:
   raw=response.read();rows.append({'url':response.url,'status':response.status,'elapsed_ms':round((time.monotonic()-start)*1000),'bytes':len(raw),'content_type':response.headers.get('Content-Type'),'cache_control':response.headers.get('Cache-Control'),'sha256':hashlib.sha256(raw).hexdigest(),'authentication_sent':False})
 except Exception as ex:rows.append({'url':origin+path,'error_type':type(ex).__name__,'error':str(ex),'elapsed_ms':round((time.monotonic()-start)*1000),'authentication_sent':False})
Path(args.output).parent.mkdir(parents=True,exist_ok=True);Path(args.output).write_text(json.dumps(rows,indent=2)+'\n')
assert all(x.get('status')==200 for x in rows),rows
assert rows[-1]['sha256']==json.loads(Path('evidence/final-p2/video-validation.json').read_text())['sha256']
print(json.dumps({'passed':True,'anonymous_http_200':3,'public_business_acceptance':False,'video_sha256':rows[-1]['sha256']}))
