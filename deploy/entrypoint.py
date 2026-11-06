"""Load mounted Docker secrets into the server environment, never the frontend."""
import os
from pathlib import Path
for filename,variable in [('genesis_api_key','GENESIS_ACCESS_TOKEN'),('login_password','QUOTEPILOT_LOGIN_PASSWORD'),('session_secret','QUOTEPILOT_SESSION_SECRET')]:
    path=Path('/run/secrets')/filename
    if path.exists():os.environ[variable]=path.read_text().strip()
from quotepilot.security import validate_production
validate_production()
import uvicorn
uvicorn.run('server:app',host='0.0.0.0',port=8765,workers=1,proxy_headers=True,forwarded_allow_ips='*',timeout_keep_alive=10)
