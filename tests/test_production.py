"""Production configuration and access checks; no claims of external deployment."""
import os,time
import pytest
from fastapi.testclient import TestClient
from quotepilot.security import validate_production,signed_session,valid_session,RateLimiter

@pytest.fixture
def prod(tmp_path,monkeypatch):
 import server
 monkeypatch.setattr(server,'DB',tmp_path/'production.db')
 monkeypatch.setenv('QUOTEPILOT_ENV','production');monkeypatch.setenv('QUOTEPILOT_LOGIN_PASSWORD','TEST_ONLY_PASSWORD_1234')
 monkeypatch.setenv('QUOTEPILOT_SESSION_SECRET','TEST_SESSION_SECRET_'+'x'*32)
 monkeypatch.setenv('QUOTEPILOT_PUBLIC_URL','https://quote.example.invalid');monkeypatch.setenv('QUOTEPILOT_PROVIDER','mock')
 with TestClient(server.app,base_url='https://quote.example.invalid') as c:
  stack=server.app.middleware_stack
  while stack:
   if hasattr(stack,'limiter'):stack.limiter=RateLimiter()
   stack=getattr(stack,'app',None)
  yield c

def login(c):return c.post('/auth/login',json={'password':'TEST_ONLY_PASSWORD_1234'},headers={'Origin':'https://quote.example.invalid'})

def test_fail_closed_config(monkeypatch):
 monkeypatch.setenv('QUOTEPILOT_ENV','production');monkeypatch.delenv('QUOTEPILOT_LOGIN_PASSWORD',raising=False)
 with pytest.raises(ValueError,match='password'):validate_production()

def test_anonymous_denied(prod):
 assert prod.get('/').history[0].status_code==303
 assert prod.get('/api/emails').status_code==401
 assert prod.get('/api/docs').status_code==401
 assert prod.get('/healthz').json()=={'ok':True,'service':'QuotePilot'}

def test_origin_and_password_rejection(prod):
 assert prod.post('/auth/login',json={'password':'TEST_ONLY_PASSWORD_1234'}).status_code==403
 assert prod.post('/auth/login',json={'password':'wrong'},headers={'Origin':'https://quote.example.invalid'}).status_code==401

def test_cookie_and_authenticated_read(prod):
 r=login(prod);assert r.status_code==200
 cookie=r.headers['set-cookie'];assert all(x in cookie.lower() for x in ('httponly','secure','samesite=strict'))
 assert prod.get('/api/emails').status_code==200
 assert 'GENESIS_ACCESS_TOKEN' not in prod.get('/').text
 assert "script-src 'self'" in prod.get('/').headers['content-security-policy']

def test_csrf_and_logout(prod):
 login(prod)
 assert prod.post('/api/quote',json={}).status_code==403
 assert prod.post('/auth/logout',headers={'Origin':'https://quote.example.invalid'}).status_code==200
 assert prod.get('/api/emails').status_code==401

def test_tampered_cookie(prod):
 token=signed_session();assert valid_session(token)
 assert not valid_session(token[:-1]+('0' if token[-1]!='0' else '1'))

def test_login_rate_limit(prod):
 for _ in range(8):assert prod.post('/auth/login',json={'password':'wrong'},headers={'Origin':'https://quote.example.invalid'}).status_code==401
 assert login(prod).status_code==429

def test_limiter_bounded_window():
 r=RateLimiter();assert r.allow('x',1,60) and not r.allow('x',1,60)
