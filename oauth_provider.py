"""
OAuth 2.1 Authorization Server provider สำหรับ MCP (self-contained, single-user)
===============================================================================
Claude.ai / Cowork web รองรับเฉพาะ OAuth 2.1 (PKCE + Dynamic Client Registration)
ไม่รองรับ static bearer token ในหน้า custom connector

โมดูลนี้ implement OAuthAuthorizationServerProvider ของ MCP SDK:
  - SDK จัดการ endpoints (/authorize /token /register /revoke + .well-known) ให้เอง
  - SDK ตรวจ PKCE, client auth, code expiry, redirect_uri ให้เอง
  - เราแค่: เก็บ state (in-memory) + กั้นด้วยหน้า /login ที่ถาม password

หมายเหตุ: storage เป็น in-memory — เมื่อ container restart/redeploy token จะหาย
ผู้ใช้ต้อง authorize ใหม่ (ยอมรับได้สำหรับ connector ส่วนตัว traffic ต่ำ)
"""

import html
import secrets
import time

from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse, Response

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

ACCESS_TOKEN_TTL = 3600        # 1 ชม.
AUTH_CODE_TTL = 300            # 5 นาที
PENDING_LOGIN_TTL = 600        # 10 นาที


class SimpleOAuthProvider:
    """OAuth AS แบบ in-memory ที่กั้นการอนุมัติด้วย password เดียว (shared secret)"""

    def __init__(self, public_url: str, password: str, static_token: str | None = None):
        self.public_url = public_url.rstrip("/")
        self._password = password
        # static token (optional): ให้ Claude Code CLI ใช้ Bearer <token> ได้ควบคู่กับ OAuth
        self._static_token = static_token or None
        self.clients: dict[str, OAuthClientInformationFull] = {}
        self.auth_codes: dict[str, AuthorizationCode] = {}
        self.access_tokens: dict[str, AccessToken] = {}
        self.refresh_tokens: dict[str, RefreshToken] = {}
        self.pending: dict[str, dict] = {}  # txid -> {client_id, params, expires}

    # --- client registration (DCR) --- #
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self.clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self.clients[client_info.client_id] = client_info

    # --- authorize: ส่งผู้ใช้ไปหน้า /login ของเราก่อน --- #
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        txid = secrets.token_urlsafe(24)
        self.pending[txid] = {
            "client_id": client.client_id,
            "params": params,
            "expires": time.time() + PENDING_LOGIN_TTL,
        }
        return f"{self.public_url}/login?txid={txid}"

    # --- authorization code --- #
    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        code = self.auth_codes.get(authorization_code)
        if code and code.client_id == client.client_id:
            return code
        return None

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        # SDK ตรวจ PKCE / expiry / redirect_uri ให้แล้ว — เราแค่ออก token
        self.auth_codes.pop(authorization_code.code, None)
        return self._issue_tokens(client.client_id, authorization_code.scopes, authorization_code.resource)

    # --- refresh token (rotate) --- #
    async def load_refresh_token(
        self, client: OAuthClientInformationFull, refresh_token: str
    ) -> RefreshToken | None:
        rt = self.refresh_tokens.get(refresh_token)
        if rt and rt.client_id == client.client_id:
            return rt
        return None

    async def exchange_refresh_token(
        self,
        client: OAuthClientInformationFull,
        refresh_token: RefreshToken,
        scopes: list[str],
    ) -> OAuthToken:
        self.refresh_tokens.pop(refresh_token.token, None)
        return self._issue_tokens(client.client_id, scopes or refresh_token.scopes, None)

    # --- access token verification (ใช้โดย ProviderTokenVerifier) --- #
    async def load_access_token(self, token: str) -> AccessToken | None:
        # static token (CLI) — ยอมรับควบคู่กับ OAuth access tokens
        if self._static_token and secrets.compare_digest(token, self._static_token):
            return AccessToken(token=token, client_id="static-bearer", scopes=[], expires_at=None)
        at = self.access_tokens.get(token)
        if not at:
            return None
        if at.expires_at and at.expires_at < time.time():
            self.access_tokens.pop(token, None)
            return None
        return at

    async def revoke_token(self, token) -> None:
        tok = getattr(token, "token", None)
        if tok:
            self.access_tokens.pop(tok, None)
            self.refresh_tokens.pop(tok, None)

    # --- helpers --- #
    def _issue_tokens(self, client_id: str, scopes: list[str], resource: str | None) -> OAuthToken:
        access = secrets.token_urlsafe(32)
        refresh = secrets.token_urlsafe(32)
        now = int(time.time())
        self.access_tokens[access] = AccessToken(
            token=access,
            client_id=client_id,
            scopes=scopes,
            expires_at=now + ACCESS_TOKEN_TTL,
            resource=resource,
        )
        self.refresh_tokens[refresh] = RefreshToken(
            token=refresh, client_id=client_id, scopes=scopes, expires_at=None
        )
        return OAuthToken(
            access_token=access,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_TTL,
            scope=" ".join(scopes) if scopes else None,
            refresh_token=refresh,
        )

    def complete_login(self, txid: str, password: str) -> str:
        """ตรวจ password แล้วสร้าง authorization code; คืน redirect URL กลับไปหา client
        raise PermissionError (password ผิด) / ValueError (txid หมดอายุ)"""
        entry = self.pending.get(txid)
        if not entry or entry["expires"] < time.time():
            self.pending.pop(txid, None)
            raise ValueError("คำขอหมดอายุหรือไม่ถูกต้อง กรุณาเริ่มการเชื่อมต่อใหม่จาก Claude")
        if not (password and secrets.compare_digest(password, self._password)):
            raise PermissionError("รหัสผ่านไม่ถูกต้อง")

        self.pending.pop(txid, None)
        params: AuthorizationParams = entry["params"]
        code = secrets.token_urlsafe(32)
        self.auth_codes[code] = AuthorizationCode(
            code=code,
            scopes=params.scopes or [],
            expires_at=time.time() + AUTH_CODE_TTL,
            client_id=entry["client_id"],
            code_challenge=params.code_challenge,
            redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly,
            resource=params.resource,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)


def build_auth_settings(public_url: str) -> AuthSettings:
    base = public_url.rstrip("/")
    return AuthSettings(
        issuer_url=base,
        resource_server_url=base + "/mcp",
        client_registration_options=ClientRegistrationOptions(enabled=True),
        revocation_options=RevocationOptions(enabled=True),
        required_scopes=None,
    )


def _login_html(txid: str, error: str | None = None) -> str:
    txid_e = html.escape(txid)
    err_html = (
        f'<p style="color:#c0392b;margin:0 0 16px;font-size:14px">⚠️ {html.escape(error)}</p>'
        if error
        else ""
    )
    return f"""<!doctype html>
<html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>เข้าสู่ระบบ — Crypto News MCP</title></head>
<body style="margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#0f172a;
display:flex;min-height:100vh;align-items:center;justify-content:center">
  <form method="post" action="/login" style="background:#fff;padding:32px;border-radius:14px;
  width:320px;box-shadow:0 10px 40px rgba(0,0,0,.3)">
    <h1 style="margin:0 0 4px;font-size:20px;color:#0f172a">🔐 Crypto News MCP</h1>
    <p style="margin:0 0 20px;color:#64748b;font-size:13px">กรอกรหัสผ่านเพื่ออนุญาตให้ Claude เชื่อมต่อ</p>
    {err_html}
    <input type="hidden" name="txid" value="{txid_e}">
    <input type="password" name="password" placeholder="รหัสผ่าน" autofocus required
      style="width:100%;box-sizing:border-box;padding:12px;border:1px solid #cbd5e1;
      border-radius:8px;font-size:15px;margin-bottom:16px">
    <button type="submit" style="width:100%;padding:12px;border:0;border-radius:8px;
      background:#2563eb;color:#fff;font-size:15px;font-weight:600;cursor:pointer">
      อนุญาต & เชื่อมต่อ</button>
  </form>
</body></html>"""


def register_login_route(mcp, provider: SimpleOAuthProvider) -> None:
    """ลงทะเบียนหน้า /login (public route — ไม่ต้อง auth) บน FastMCP instance"""

    @mcp.custom_route("/login", methods=["GET", "POST"])
    async def login(request: Request) -> Response:
        if request.method == "GET":
            return HTMLResponse(_login_html(request.query_params.get("txid", "")))
        form = await request.form()
        txid = str(form.get("txid", ""))
        password = str(form.get("password", ""))
        try:
            url = provider.complete_login(txid, password)
        except PermissionError as e:
            return HTMLResponse(_login_html(txid, error=str(e)), status_code=401)
        except ValueError as e:
            return HTMLResponse(_login_html(txid, error=str(e)), status_code=400)
        return RedirectResponse(url=url, status_code=302)
