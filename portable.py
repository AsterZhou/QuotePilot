"""Start an isolated QuotePilot instance with its real business routes on a loopback socket."""
from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path
import hmac
import os
import secrets
import socket
import sys
import tempfile
import threading
import time
import webbrowser

ROOT = Path(__file__).resolve().parent
SAMPLES = ROOT / "stage" / "samples"


def configure(origin: str, data_dir: Path) -> dict[str, str]:
    """Keep the demo independent of any service credentials on the presenter's machine."""
    for key in list(os.environ):
        if key.startswith(("QUOTEPILOT_", "GENESIS_", "MOI_", "TAVILY_", "BRAVE_SEARCH_")):
            del os.environ[key]
    passwords = {role: secrets.token_urlsafe(26) for role in ("admin", "reviewer")}
    os.environ.update(QUOTEPILOT_ENV="production", QUOTEPILOT_RELEASE_DEMO="1",
                      QUOTEPILOT_PORTABLE="1", QUOTEPILOT_PROVIDER="mock",
                      QUOTEPILOT_DB=str(data_dir / "session.sqlite3"),
                      QUOTEPILOT_PUBLIC_URL=origin,
                      QUOTEPILOT_SESSION_SECRET=secrets.token_urlsafe(48),
                      QUOTEPILOT_LOGIN_PASSWORD=passwords["admin"],
                      QUOTEPILOT_REVIEWER_PASSWORD=passwords["reviewer"])
    return passwords


def make_supplier_pdf(today) -> bytes:
    """Roll only the two clearly marked synthetic supplier dates forward."""
    import fitz
    with fitz.open(SAMPLES / "suppliers.pdf") as template, fitz.open() as result:
        for page in template:
            lines = page.get_text().splitlines()
            lines = [(f"Quote date: {today.isoformat()}" if line.startswith("Quote date:") else
                      f"Valid until: {(today + timedelta(days=60)).isoformat()}" if line.startswith("Valid until:") else
                      line) for line in lines]
            out = result.new_page()
            out.insert_text((50, 60), "\n".join(lines), fontsize=13, lineheight=1.5)
        return result.tobytes(garbage=3, deflate=True)


def make_app(origin, token, passwords):
    import server
    from fastapi import FastAPI
    from starlette.requests import Request
    from starlette.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, FileResponse
    from starlette.middleware.trustedhost import TrustedHostMiddleware
    # Future annotations need Request resolvable by FastAPI when inspecting these local endpoints.
    globals()["Request"] = Request
    today = server.center_today()
    source_pdf = make_supplier_pdf(today)
    source_mail = (SAMPLES / "structured-backup.eml").read_bytes()

    @asynccontextmanager
    async def lifespan(app):
        async with server.lifespan(server.app):
            yield

    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1"])
    policy = {"Cache-Control": "no-store", "Referrer-Policy": "no-referrer",
              "X-Content-Type-Options": "nosniff",
              "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"}

    def paired(request: Request):
        return hmac.compare_digest(request.cookies.get("qp_presenter", ""), token)

    @app.get("/desk/connect/{pairing}")
    def pair(pairing: str):
        if not hmac.compare_digest(pairing, token):
            return Response(status_code=404)
        reply = RedirectResponse("/desk/", status_code=303, headers=policy)
        reply.set_cookie("qp_presenter", token, httponly=True, samesite="strict", path="/desk", max_age=8*3600)
        return reply

    @app.get("/desk/")
    def desk(request: Request):
        if not paired(request):
            return HTMLResponse("请在本机重新打开启动窗口里显示的完整地址。", status_code=403, headers=policy)
        return FileResponse(ROOT / "stage" / "index.html", media_type="text/html", headers=policy)

    @app.get("/desk/assets/{name}")
    def desk_asset(name: str, request: Request):
        if not paired(request) or name not in ("desk.js", "desk.css"):
            return Response(status_code=404)
        return FileResponse(ROOT / "stage" / name, headers=policy)

    @app.post("/desk/access/{role}")
    def local_role_password(role: str, request: Request):
        if not paired(request) or request.headers.get("origin") != origin or role not in passwords:
            return Response(status_code=403)
        return JSONResponse({"password": passwords[role]}, headers=policy)

    @app.get("/desk/sample/{filename}")
    def sample(filename: str, request: Request):
        if not paired(request):
            return Response(status_code=403)
        if filename == "suppliers.pdf":
            return Response(source_pdf, media_type="application/pdf", headers={"Cache-Control":"no-store"})
        if filename in ("structured-backup.eml", "email.txt"):
            media = "message/rfc822" if filename.endswith("eml") else "text/plain"
            return Response(source_mail, media_type=media, headers=policy)
        return Response(status_code=404)

    @app.get("/desk/dates")
    def dates(request: Request):
        if not paired(request):
            return Response(status_code=403)
        return JSONResponse({"asof": today.isoformat(), "valid_until": (today+timedelta(days=14)).isoformat()}, headers=policy)

    app.mount("/", server.app)
    return app


def main():
    import uvicorn
    run_dir = Path(tempfile.mkdtemp(prefix="QuotePilot-Stage-"))
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen(128)
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        passwords = configure(origin, run_dir)
        token = secrets.token_urlsafe(32)
        app = make_app(origin, token, passwords)
        link = f"{origin}/desk/connect/{token}"
        print(f"\nQuotePilot local demo. Keep this window open.\n\n{link}\n\nSession database: {run_dir}\nPress Ctrl+C to stop.\n", flush=True)
        service = uvicorn.Server(uvicorn.Config(app, log_level="warning", access_log=False, proxy_headers=False))
        def open_when_ready():
            for _ in range(200):
                if service.started:
                    if "--no-browser" not in sys.argv:
                        webbrowser.open(link)
                    return
                if service.should_exit:
                    return
                time.sleep(.05)
        threading.Thread(target=open_when_ready, daemon=True).start()
        service.run(sockets=[listener])


if __name__ == "__main__":
    main()
