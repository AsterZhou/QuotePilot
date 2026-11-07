"""Single-team demo access. Production fails closed; not an enterprise identity system."""
import collections,hashlib,hmac,json,os,secrets,time,threading
from urllib.parse import urlsplit
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse,RedirectResponse,HTMLResponse

COOKIE='qp_session'

def production():return os.environ.get('QUOTEPILOT_ENV')=='production'

def validate_production():
    if not production():return
    if len(os.environ.get('QUOTEPILOT_LOGIN_PASSWORD',''))<12:raise ValueError('production requires a login password of at least 12 characters')
    if len(os.environ.get('QUOTEPILOT_SESSION_SECRET',''))<32:raise ValueError('production requires a session secret of at least 32 characters')
    url=urlsplit(os.environ.get('QUOTEPILOT_PUBLIC_URL',''))
    if url.scheme!='https' or not url.hostname or url.path not in ('','/') or url.query or url.fragment or url.username:raise ValueError('production requires an HTTPS public origin')
    if os.environ.get('QUOTEPILOT_PROVIDER')=='genesis' and not(os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY')):raise ValueError('Genesis credentials missing')

def origin():return os.environ.get('QUOTEPILOT_PUBLIC_URL','').rstrip('/')

def signed_session():
    body=str(int(time.time())+8*3600)+'.'+secrets.token_hex(16)
    sig=hmac.new(os.environ['QUOTEPILOT_SESSION_SECRET'].encode(),body.encode(),hashlib.sha256).hexdigest()
    return body+'.'+sig

def valid_session(value):
    try:
        expiry,nonce,sig=value.split('.')
        remaining=int(expiry)-int(time.time())
        if not 0<remaining<=8*3600 or len(nonce)!=32:return False
        expected=hmac.new(os.environ['QUOTEPILOT_SESSION_SECRET'].encode(),(expiry+'.'+nonce).encode(),hashlib.sha256).hexdigest()
        return hmac.compare_digest(sig,expected)
    except (ValueError,KeyError,AttributeError):return False

class RateLimiter:
    def __init__(self):self.events={};self.lock=threading.Lock()
    def allow(self,key,limit,window):
        now=time.monotonic()
        with self.lock:
            if len(self.events)>1000:self.events={k:v for k,v in self.events.items() if v and now-v[-1]<3600}
            q=self.events.setdefault(key,collections.deque())
            while q and now-q[0]>=window:q.popleft()
            if len(q)>=limit:return False
            q.append(now);return True

def deployment_notice():
    if os.environ.get('QUOTEPILOT_EPHEMERAL_DEMO')!='1':return ''
    return ('<div role="alert" style="background:#fff3d6;color:#704a00;padding:12px 20px;font:14px/1.6 system-ui;border-bottom:1px solid #e8ce8b">'
            '<strong>免费临时演示 · 仅限赛事/合成测试文件</strong>：SQLite与上传附件存于临时磁盘，休眠、重启或重新部署后会丢失；请及时下载报价和审计记录。'
            '当前AI使用明确Mock模式，未调用Genesis；核价、审批与导出由真实规则和数据库执行。管理员密码访问，无公众注册。</div>')

LOGIN='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>QuotePilot · 登录</title><style>body{font:16px system-ui;background:#f5f6f8;color:#172032;max-width:420px;margin:15vh auto;padding:28px}form{background:white;padding:32px;border:1px solid #e0e3e8;border-radius:12px}input,button{box-sizing:border-box;width:100%;padding:13px;margin:14px 0;border:1px solid #cbd0d9;border-radius:6px}button{background:#173f37;color:white}small{color:#667085}</style><form id="login"><h1>QuotePilot</h1><p>参赛演示工作台</p><label>访问密码<input type="password" id="password" autocomplete="current-password" required></label><button>进入工作台</button><p id="result" role="alert"></p><small>此为共享演示空间。请仅使用赛事素材或合成测试文件。</small></form><script src="/auth/login.js"></script></html>'''
LOGIN_JS="""document.querySelector('#login').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.querySelector('#password').value})});if(!r.ok)throw Error(r.status===429?'尝试过于频繁，请稍后再试':'登录未成功，请核对访问密码');location.href='/'}catch(e){document.querySelector('#result').textContent=e.message}finally{b.disabled=false}});"""

class DemoAccessMiddleware(BaseHTTPMiddleware):
    def __init__(self,app):super().__init__(app);self.limiter=RateLimiter()
    async def dispatch(self,request,call_next):
        if not production():return await call_next(request)
        path=request.url.path;ip=request.client.host if request.client else 'unknown'
        response=None
        if path=='/healthz' and request.method=='GET':response=JSONResponse({'ok':True,'service':'QuotePilot'})
        elif path=='/auth/login.js' and request.method=='GET':
            from starlette.responses import Response
            response=Response(LOGIN_JS,media_type='application/javascript')
        elif path=='/login' and request.method=='GET':response=HTMLResponse(LOGIN.replace('<form id="login">',deployment_notice()+'<form id="login">'))
        else:
            if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin')!=origin():response=JSONResponse({'detail':'请求来源不匹配'},403)
            elif path=='/auth/login' and request.method=='POST':
                if not self.limiter.allow(('login',ip),8,300):response=JSONResponse({'detail':'登录尝试过于频繁'},429)
                elif int(request.headers.get('content-length','0') or '0')>2048:response=JSONResponse({'detail':'请求过大'},413)
                else:
                    try:
                        raw=await request.body()
                        if len(raw)>2048:raise ValueError()
                        password=json.loads(raw).get('password','')
                        ok=isinstance(password,str) and hmac.compare_digest(hashlib.sha256(password.encode()).digest(),hashlib.sha256(os.environ['QUOTEPILOT_LOGIN_PASSWORD'].encode()).digest())
                    except (ValueError,TypeError,AttributeError):ok=False
                    response=JSONResponse({'ok':True} if ok else {'detail':'访问密码错误'},200 if ok else 401)
                    if ok:response.set_cookie(COOKIE,signed_session(),max_age=8*3600,secure=True,httponly=True,samesite='strict',path='/')
            elif not valid_session(request.cookies.get(COOKIE,'')):
                response=JSONResponse({'detail':'请先登录'},401) if path.startswith('/api/') else RedirectResponse('/login',303)
            elif path=='/auth/logout' and request.method=='POST':
                response=JSONResponse({'ok':True});response.delete_cookie(COOKIE,path='/',secure=True,httponly=True,samesite='strict')
            elif path.endswith('/extract') or path=='/api/extraction/preview':
                if not self.limiter.allow('ai-global',30,3600):response=JSONResponse({'detail':'演示模型调用已达每小时30次上限，请稍后再试'},429)
            if response is None:response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response
