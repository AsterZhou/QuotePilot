"""Single-team demo access. Production fails closed; not an enterprise identity system."""
import collections,hashlib,hmac,json,os,secrets,time,threading
from urllib.parse import urlsplit
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse,RedirectResponse,HTMLResponse

COOKIE='qp_session'

def production():return os.environ.get('QUOTEPILOT_ENV')=='production'

def local_interactive_preview():
    # Only the owned cloud-browser preview origin; never an arbitrary HTTP public host.
    return os.environ.get('QUOTEPILOT_LOCAL_PREVIEW')=='1' and os.environ.get('QUOTEPILOT_PUBLIC_URL')=='http://terminal.local:4173'

def login_digest(role):
    name = 'QUOTEPILOT_LOGIN_PASSWORD' if role == 'admin' else 'QUOTEPILOT_REVIEWER_PASSWORD'
    encoded = os.environ.get(name + '_SHA256', '')
    if encoded:
        if len(encoded) != 64 or not all(c in '0123456789abcdef' for c in encoded):
            raise ValueError('Invalid demo access digest')
        return encoded
    value = os.environ.get(name, '')
    if value and len(value) < 12:
        raise ValueError('Production password must be at least 12 characters')
    return hashlib.sha256(value.encode()).hexdigest() if value else ''


def validate_production():
    if not production():return
    if not login_digest('admin'):raise ValueError('production requires a login password of at least 12 characters')
    if len(os.environ.get('QUOTEPILOT_SESSION_SECRET',''))<32:raise ValueError('production requires a session secret of at least 32 characters')
    url=urlsplit(os.environ.get('QUOTEPILOT_PUBLIC_URL',''))
    if (url.scheme!='https' and not local_interactive_preview()) or not url.hostname or url.path not in ('','/') or url.query or url.fragment or url.username:raise ValueError('production requires an HTTPS public origin')
    if os.environ.get('QUOTEPILOT_PROVIDER')=='genesis' and not(os.environ.get('GENESIS_ACCESS_TOKEN') or os.environ.get('GENESIS_API_KEY')):raise ValueError('Genesis credentials missing')
    reviewer = login_digest('reviewer')
    if reviewer and hmac.compare_digest(reviewer, login_digest('admin')):
        raise ValueError('reviewer password must be distinct')

def origin():return os.environ.get('QUOTEPILOT_PUBLIC_URL','').rstrip('/')

def signed_session(role='admin'):
    if role not in ('admin','reviewer'):raise ValueError('unknown role')
    body=str(int(time.time())+8*3600)+'.'+secrets.token_hex(16)+'.'+role
    sig=hmac.new(os.environ['QUOTEPILOT_SESSION_SECRET'].encode(),body.encode(),hashlib.sha256).hexdigest()
    return body+'.'+sig

def valid_session(value):
    try:
        parts=value.split('.')
        if len(parts)==3:expiry,nonce,sig=parts;body=expiry+'.'+nonce
        elif len(parts)==4:
            expiry,nonce,role,sig=parts
            if role not in ('admin','reviewer'):return False
            body=expiry+'.'+nonce+'.'+role
        else:return False
        remaining=int(expiry)-int(time.time())
        if not 0<remaining<=8*3600 or len(nonce)!=32:return False
        expected=hmac.new(os.environ['QUOTEPILOT_SESSION_SECRET'].encode(),body.encode(),hashlib.sha256).hexdigest()
        return sig.isascii() and hmac.compare_digest(sig,expected)
    except (ValueError,KeyError,AttributeError):return False

def session_role(value):
    if not valid_session(value):return None
    parts=value.split('.')
    return parts[2] if len(parts)==4 else 'admin'

def reviewer_allowed(path,method):
    if method in ('GET','HEAD'):
        return not path.startswith(('/api/admin/','/api/query-center/','/api/audit','/api/operations','/api/integration','/api/native-workflow'))
    if method=='POST':
        return path in ('/api/emails/import','/api/emails/preview','/api/supplier-offers/sources','/api/supplier-offers','/api/commercial-quotes','/api/rfq-versions','/api/rfq-versions/matches') or bool(__import__('re').fullmatch(r'/api/(catalog/prices/[^/]+/review|lines/\d+/review-fields|supplier-offers/[^/]+/confirm|supplier-offers/sources/[^/]+/extract|commercial-quotes/[^/]+/review)',path))
    return False

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
    ai=('AI模式：Genesis（请求由用户主动触发，成功记录见平台接入）' if os.environ.get('QUOTEPILOT_PROVIDER','mock')=='genesis'
        else 'AI模式：Mock模拟，未调用Genesis')
    return ('<div role="alert" style="background:#fff3d6;color:#704a00;padding:12px 20px;font:14px/1.6 system-ui;border-bottom:1px solid #e8ce8b">'
            '<strong>免费临时演示 · 仅限赛事/合成测试文件</strong>：来件和报价使用临时存储，实例重置后恢复为预置样例。请及时下载正式文件。'
            +ai+'；核价、审批与导出由真实规则和数据库执行。使用管理员或业务复核员访问码登录。</div>')

LOGIN='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>QuotePilot · 登录</title><style>body{font:16px system-ui;background:#f5f6f8;color:#172032;max-width:420px;margin:15vh auto;padding:28px}form{background:white;padding:32px;border:1px solid #e0e3e8;border-radius:12px}input,button{box-sizing:border-box;width:100%;padding:13px;margin:14px 0;border:1px solid #cbd0d9;border-radius:6px}button{background:#173f37;color:white}small{color:#667085}</style><form id="login"><h1>QuotePilot</h1><p><a href="/guide/technical.html">技术架构与工程验证</a></p><p>首次体验请使用管理员访问码。</p><p><a href="/guide/#login">查看演示访问码与使用说明</a>，复制管理员码后回到这里登录。</p><label>访问密码<input type="password" id="password" autocomplete="current-password" required></label><button>进入工作台</button><p id="result" role="alert"></p><small>此为共享演示空间。请仅使用赛事素材或合成测试文件。</small></form><script src="/auth/login.js"></script></html>'''
LOGIN_JS="""document.querySelector('#login').addEventListener('submit',async e=>{e.preventDefault();const b=e.target.querySelector('button');b.disabled=true;try{const r=await fetch('/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:document.querySelector('#password').value})});if(!r.ok)throw Error(r.status===429?'尝试过于频繁，请稍后再试':'登录未成功，请核对访问密码');location.href='/'}catch(e){document.querySelector('#result').textContent=e.message}finally{b.disabled=false}});"""

class DemoAccessMiddleware(BaseHTTPMiddleware):
    def __init__(self,app):super().__init__(app);self.limiter=RateLimiter()
    async def dispatch(self,request,call_next):
        if not production():return await call_next(request)
        path=request.url.path;ip=request.client.host if request.client else 'unknown'
        response=None
        if path=='/healthz' and request.method=='GET':response=JSONResponse({'ok':True,'service':'QuotePilot'})
        elif path.startswith('/guide/') and request.method in ('GET','HEAD'):
            response=await call_next(request)
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
                        digest = hashlib.sha256(password.encode()).hexdigest() if isinstance(password, str) else None
                        role = 'admin'
                        ok = digest is not None and hmac.compare_digest(digest, login_digest(role))
                        if not ok and digest is not None:
                            role = 'reviewer'
                            ok = hmac.compare_digest(digest, login_digest(role))
                    except (ValueError,TypeError,AttributeError):ok=False
                    response=JSONResponse({'ok':True} if ok else {'detail':'访问密码错误'},200 if ok else 401)
                    if ok:response.set_cookie(COOKIE,signed_session(role),max_age=8*3600,secure=not local_interactive_preview(),httponly=True,samesite='strict',path='/')
            elif not valid_session(request.cookies.get(COOKIE,'')):
                response=JSONResponse({'detail':'请先登录'},401) if path.startswith('/api/') else RedirectResponse('/login',303)
            elif path=='/auth/logout' and request.method=='POST':
                response=JSONResponse({'ok':True});response.delete_cookie(COOKIE,path='/',secure=not local_interactive_preview(),httponly=True,samesite='strict')
            elif session_role(request.cookies.get(COOKIE,''))=='reviewer' and not reviewer_allowed(path,request.method):
                response=JSONResponse({'detail':'当前复核角色无此权限'},403)
            elif __import__('re').fullmatch(r'/api/supplier-offers/sources/[^/]+/extract',path):
                if not self.limiter.allow('local-supplier-extraction',60,3600):response=JSONResponse({'detail':'本地原件解析达到每小时60次上限，请稍后再试'},429)
            elif path.endswith('/extract') or path in ('/api/extraction/preview','/api/analytics/ask','/api/query-center/ask','/api/query-center/joint'):
                if not self.limiter.allow('ai-global',30,3600):response=JSONResponse({'detail':'演示模型调用已达每小时30次上限，请稍后再试'},429)
            elif path=='/api/query-center/external':
                if not self.limiter.allow('external-search-global',20,3600):response=JSONResponse({'detail':'公开搜索达到每小时20次上限，未自动购买额度'},429)
            if response is None:response=await call_next(request)
        response.headers['Cache-Control']='no-store'
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; font-src 'self'; img-src 'self' data: blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        return response

