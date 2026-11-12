"""Run: python stage/smoke_test.py. Starts a private app and checks access and the sample import."""
from pathlib import Path
import re
import subprocess
import sys
import time

import httpx


def main():
    root = Path(__file__).resolve().parents[1]
    with subprocess.Popen([sys.executable, "-B", str(root / "portable.py"), "--no-browser"],
                          cwd=root, text=True, stdout=subprocess.PIPE) as proc:
        try:
            for line in proc.stdout:
                if line.startswith("http://127.0.0.1:"):
                    link = line.strip()
                    break
            else:
                raise RuntimeError("The local launcher did not return a pairing URL")
            origin = link.split("/desk/")[0]
            with httpx.Client(base_url=origin, trust_env=False, follow_redirects=True, timeout=15) as user:
                for _ in range(80):
                    try:
                        if user.get("/healthz").status_code == 200:
                            break
                    except httpx.ConnectError:
                        pass
                    time.sleep(.1)
                assert user.get("/desk/").status_code == 403
                assert user.get("/desk/connect/wrong").status_code == 404
                assert user.get("/healthz", headers={"Host":"external.invalid"}).status_code == 400
                assert user.get(link).status_code == 200
                assert user.get("/api/auth/me").status_code == 401
                assert user.post("/desk/access/admin", headers={"Origin":"https://other.invalid"}).status_code == 403
                user.headers["Origin"] = origin
                password = user.post("/desk/access/reviewer").json()
                assert user.post("/auth/login", json=password).is_success
                assert user.get("/api/auth/me").json()["role"] == "reviewer"
                assert user.get("/api/audit/verify").status_code == 403
                data = user.get("/desk/sample/structured-backup.eml").content
                imported = user.post("/api/emails/import", files={"file":("stage.eml",data,"message/rfc822")}).json()
                assert imported["parsed_count"] == 1
                row = user.get("/api/lines", params={"email_id":imported["email_id"]}).json()["rows"][0]
                assert (row["part_number"],row["quantity"]) == ("PN-0001",3)
                print("PASS — unpaired / cross-origin / role restrictions and real sample intake")
        finally:
            proc.terminate()
            proc.wait(timeout=10)


if __name__ == "__main__":
    main()
