"""Run on deployment host. Secret directory must be outside source checkout."""
import getpass,os,secrets
from pathlib import Path
if not hasattr(os,'geteuid') or os.geteuid()!=0:raise SystemExit('Run on Linux with sudo so mounted secrets can be assigned to container UID 10001')
root=Path(__file__).resolve().parents[1]
dest=Path(os.environ.get('QP_SECRET_DIR',str(Path.home()/'.local/share/quotepilot-secrets'))).expanduser().resolve()
if dest==root or root in dest.parents:raise SystemExit('Secret directory must be outside project source')
dest.mkdir(parents=True,exist_ok=True,mode=0o700)
if any((dest/x).exists() for x in ('genesis_api_key','login_password','session_secret')):raise SystemExit('Existing secrets found; refusing to overwrite')
key=getpass.getpass('Genesis personal key (hidden): ').strip();password=getpass.getpass('Demo access password, >=12 chars (hidden): ')
if not key or len(password)<12:raise SystemExit('Missing key or password too short; no secret files written')
for name,value in [('genesis_api_key',key),('login_password',password),('session_secret',secrets.token_hex(32))]:
    fd=os.open(dest/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:f.write(value)
# Container UID 10001 needs read access to bind-mounted secrets; deploy with the same UID ownership.
if os.geteuid()==0:
    for path in dest.iterdir():os.chown(path,10001,10001)
print('Secrets initialized. Set QP_SECRET_DIR to: '+str(dest))
