# Session-only interactive workspace

Built from the application code at commercial-upgrades/0c45316. This is an owned managed-browser preview, not public hosting or judge acceptance. Formal Render service/SQLite remain untouched.

The preview runs the actual FastAPI/SQLite app with a separately generated synthetic business cycle (two RFQ versions, three suppliers/plans, distinct-role approval and actual exports). Mock is explicitly enabled; this preview does not claim live Genesis/MatrixOne calls. All standard administrator/reviewer checks remain enabled.

Only the exact local managed-preview origin http://terminal.local:4173 may opt into HTTP session cookies through QUOTEPILOT_LOCAL_PREVIEW=1. Normal production still requires HTTPS and Secure cookies; arbitrary HTTP public origins fail validation. Passwords and session secret are generated in ignored runtime storage, never committed. Access instructions are privately delivered to the owner. No public registration or charged resource is created.

The managed preview image cannot use the executor's Python venv path or resolve PyPI. Install requirements into tmp/preview-deps from the executor, write .ready only after success, then run scripts.dev with python3 scripts/preview_boot.py. Vendored dependencies are local-only and not committed. sites-preview owns the process.

Initial API checks: anonymous401; valid admin login200; three saved plans200; reviewer forbidden admin metrics403; non-local HTTP origin rejected. Synthetic seed cycle evidence is recorded separately. Browser control's secure credential-entry helper returned locator_invalid twice for the local HTTP login, so automated browser sign-in is not claimed; retain the real login page for the user's own product login.
