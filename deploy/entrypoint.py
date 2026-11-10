"""Server runtime entry for Docker Compose or Render; never emits credentials."""
import os
from pathlib import Path

def load_runtime_environment():
    mapping=[('genesis_api_key','GENESIS_ACCESS_TOKEN'),('login_password','QUOTEPILOT_LOGIN_PASSWORD'),('session_secret','QUOTEPILOT_SESSION_SECRET')]
    for filename,variable in mapping:
        if os.environ.get(variable):continue
        for directory in ('/run/secrets','/etc/secrets'):
            path=Path(directory)/filename
            if path.exists():os.environ[variable]=path.read_text().strip();break
    if not os.environ.get('QUOTEPILOT_PUBLIC_URL') and os.environ.get('RENDER_EXTERNAL_URL'):
        os.environ['QUOTEPILOT_PUBLIC_URL']=os.environ['RENDER_EXTERNAL_URL'].rstrip('/')
    port=int(os.environ.get('PORT','8765'))
    if not 1<=port<=65535:raise ValueError('PORT must be between 1 and 65535')
    return port

def main():
    port=load_runtime_environment()
    from quotepilot.security import validate_production
    if os.environ.get('QUOTEPILOT_RELEASE_DEMO') == '1':
        import secrets
        os.environ.setdefault('QUOTEPILOT_SESSION_SECRET', secrets.token_urlsafe(48))
    validate_production()
    if os.environ.get('QUOTEPILOT_RELEASE_DEMO') == '1':
        from deploy.release_seed import install_seed
        install_seed(Path('/app/release-demo.sqlite'), Path(os.environ['QUOTEPILOT_DB']))
    import uvicorn
    uvicorn.run('server:app',host='0.0.0.0',port=port,workers=1,proxy_headers=True,forwarded_allow_ips=os.environ.get('FORWARDED_ALLOW_IPS','*'),timeout_keep_alive=10)

if __name__=='__main__':main()
