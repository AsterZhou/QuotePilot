"""Replaceable, explicit external-search adapters. No key means no search success."""
import ipaddress,json,os,re,socket,time
from datetime import datetime,timezone
from urllib.parse import urlsplit
from uuid import uuid4
import httpx
from .query_center import ensure,now
from .store import open_db

class SearchUnavailable(RuntimeError):pass

NOTICE='公开网页信息仅供参考，不是供应商正式报价、实时库存或采购承诺；价格、单位、币种和时间须另行核验。'


def public_url(value):
    try:
        url=urlsplit(value)
        if url.scheme!='https' or not url.hostname or url.username or url.password or url.port not in (None,443):return False
        if url.hostname.lower()=='localhost' or url.hostname.lower().endswith(('.local','.internal')):return False
        try:return ipaddress.ip_address(url.hostname).is_global
        except ValueError:return '.' in url.hostname
    except ValueError:return False


def config():
    provider=os.environ.get('QUOTEPILOT_SEARCH_PROVIDER','tavily')
    key=os.environ.get('TAVILY_API_KEY' if provider=='tavily' else 'BRAVE_SEARCH_API_KEY','') if provider in ('tavily','brave') else ''
    enabled=os.environ.get('QUOTEPILOT_SEARCH_ENABLED')=='1' and os.environ.get('QUOTEPILOT_SEARCH_FREE_TIER_CONFIRMED')=='1'
    return {'provider':provider,'configured':bool(key),'enabled':enabled,'available':bool(key and enabled),
        'notice':NOTICE,'blocked_reason':None if key and enabled else '尚未配置并启用搜索API。请在后端配置TAVILY_API_KEY或BRAVE_SEARCH_API_KEY，并确认免费套餐、关闭自动超额计费，再设置QUOTEPILOT_SEARCH_ENABLED=1及QUOTEPILOT_SEARCH_FREE_TIER_CONFIRMED=1；未自动开通计费。'}


class SearchService:
    def __init__(self,transport=None):self.transport=transport

    def search(self,query,count=5):
        status=config()
        if not status['available']:raise SearchUnavailable(status['blocked_reason'])
        if not 2<=len(query.strip())<=500:raise ValueError('搜索词须为2至500字')
        started=time.monotonic();count=min(max(count,1),5)
        try:
            with httpx.Client(timeout=15,transport=self.transport,follow_redirects=False) as client:
                if status['provider']=='tavily':
                    r=client.post('https://api.tavily.com/search',headers={'Authorization':'Bearer '+os.environ['TAVILY_API_KEY']},
                       json={'query':query,'search_depth':'basic','max_results':count,'include_answer':False,'include_raw_content':False,'auto_parameters':False})
                    r.raise_for_status();raw=r.json();items=raw.get('results',[])
                else:
                    r=client.get('https://api.search.brave.com/res/v1/web/search',headers={'X-Subscription-Token':os.environ['BRAVE_SEARCH_API_KEY'],'Accept':'application/json'},params={'q':query,'count':count,'text_decorations':False})
                    r.raise_for_status();raw=r.json();items=raw.get('web',{}).get('results',[])
        except Exception:raise SearchUnavailable('外部搜索请求失败、超时或额度受限；未返回伪造的搜索结果。')
        sources=[];seen=set();retrieved=now()
        for item in items[:count]:
            url=item.get('url','')
            if not public_url(url) or url in seen:continue
            seen.add(url)
            sources.append({'source_id':'S'+str(len(sources)+1),'url':url,'title':str(item.get('title') or url)[:250],
                'snippet':str(item.get('content') or item.get('description') or '')[:1800],
                'published_at':item.get('published_date') or item.get('page_age'),'retrieved_at':retrieved,
                'link_status':'not_checked','price_classification':'public_reference_only'})
        return {'search_id':uuid4().hex,'query':query,'provider':status['provider'],'retrieved_at':retrieved,
                'sources':sources,'notice':NOTICE,'elapsed_seconds':round(time.monotonic()-started,3),'live_search':True}


def record(db,sid,result):
    ensure(db);con=open_db(db)
    try:
        con.execute('INSERT INTO external_searches VALUES(?,?,?,?,?,?)',(result['search_id'],sid,result['query'],result['provider'],json.dumps(result,ensure_ascii=False),result['retrieved_at']));con.commit()
    finally:con.close()
    return result


def check_link(url,transport=None,resolver=socket.getaddrinfo):
    """Bounded public HTTPS availability probe; never fetch local/private targets."""
    try:
        for _ in range(3):
            if not public_url(url):return {'status':'rejected'}
            host=urlsplit(url).hostname
            addresses={item[4][0] for item in resolver(host,443,type=socket.SOCK_STREAM)}
            if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):return {'status':'rejected'}
            with httpx.Client(timeout=5,transport=transport,follow_redirects=False) as client:
                # Stream and discard the body; only availability is checked, not price truth.
                with client.stream('GET',url,headers={'User-Agent':'QuotePilot-LinkCheck/1.0'}) as response:
                    if response.status_code in (301,302,303,307,308):
                        from urllib.parse import urljoin
                        url=urljoin(url,response.headers.get('location',''));continue
                    return {'status':'accessible' if 200<=response.status_code<300 else 'unavailable','http_status':response.status_code,'checked_at':now(),'resolved_url':url}
        return {'status':'redirect_limit'}
    except Exception:return {'status':'unavailable','checked_at':now()}


def claim_budget(db):
    from zoneinfo import ZoneInfo
    day=datetime.now(ZoneInfo('Asia/Shanghai')).date().isoformat()
    try:limit=max(0,min(20,int(os.environ.get('QUOTEPILOT_SEARCH_DAILY_LIMIT','20'))))
    except ValueError:raise SearchUnavailable('搜索预算配置无效，未发送外部请求。')
    ensure(db);con=open_db(db)
    try:
        con.execute('BEGIN IMMEDIATE')
        row=con.execute('SELECT attempts FROM external_search_budget WHERE day=?',(day,)).fetchone()
        count=row[0] if row else 0
        if count>=limit:raise SearchUnavailable('今日搜索请求达到配置上限，未继续调用或自动购买额度。')
        con.execute('INSERT OR REPLACE INTO external_search_budget VALUES(?,?)',(day,count+1));con.commit()
    except Exception:con.rollback();raise
    finally:con.close()
