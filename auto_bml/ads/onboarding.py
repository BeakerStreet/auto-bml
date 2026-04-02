"""
One-time Google Ads onboarding flow.
Run locally: python -m auto_bml.cli onboard
"""
import json
import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlencode, urlparse

import requests

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "https://www.googleapis.com/auth/adwords"


def run_oauth_flow(client_id: str, client_secret: str) -> str:
    """Opens browser for OAuth2 consent and returns a refresh token."""
    auth_code: dict = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            auth_code["code"] = params.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>auto-bml: Authorization complete. You can close this tab.</h2>")

        def log_message(self, *args):
            pass  # suppress server logs

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    print(f"\nOpening browser for Google Ads authorization...")
    webbrowser.open(url)

    server = HTTPServer(("localhost", 8080), CallbackHandler)
    server.handle_request()

    code = auth_code.get("code")
    if not code:
        raise RuntimeError("OAuth flow failed: no authorization code received.")

    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    return resp.json()["refresh_token"]


def push_github_secrets(token: str, repo: str, secrets: dict) -> None:
    """Stores credentials as encrypted GitHub Actions secrets."""
    import base64
    from nacl import encoding, public

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    key_resp = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
    )
    key_resp.raise_for_status()
    key_data = key_resp.json()
    public_key = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder)

    for name, value in secrets.items():
        sealed = public.SealedBox(public_key).encrypt(
            value.encode(), encoding.Base64Encoder
        )
        requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
            headers=headers,
            json={
                "encrypted_value": sealed.decode(),
                "key_id": key_data["key_id"],
            },
        ).raise_for_status()
        print(f"  Stored secret: {name}")


def run(repo: str, github_token: str) -> None:
    print("\n=== auto-bml onboarding ===\n")
    print("You'll need:")
    print("  1. A Google Ads account (create one at ads.google.com if needed)")
    print("  2. A Google Cloud project with the Google Ads API enabled")
    print("  3. A developer token (apply at developers.google.com/google-ads/api/docs/first-call/dev-token)")
    print()

    developer_token = input("Google Ads developer token: ").strip()
    client_id = input("OAuth2 client ID: ").strip()
    client_secret = input("OAuth2 client secret: ").strip()
    customer_id = input("Google Ads customer ID (digits only, no dashes): ").strip()

    print("\nStarting OAuth2 flow...")
    refresh_token = run_oauth_flow(client_id, client_secret)
    print("Authorization successful.")

    anthropic_key = input("\nAnthropic API key: ").strip()

    print(f"\nPushing secrets to {repo}...")
    push_github_secrets(github_token, repo, {
        "GOOGLE_ADS_DEVELOPER_TOKEN": developer_token,
        "GOOGLE_ADS_CLIENT_ID": client_id,
        "GOOGLE_ADS_CLIENT_SECRET": client_secret,
        "GOOGLE_ADS_REFRESH_TOKEN": refresh_token,
        "GOOGLE_ADS_CUSTOMER_ID": customer_id,
        "ANTHROPIC_API_KEY": anthropic_key,
    })

    print("\nOnboarding complete.")
    print("Next: copy workflow-templates/ into your repo's .github/workflows/")
    print("Then fill in pull.csv and program.md, and run the bml-launch workflow.")
