"""
One-time onboarding. Run from the root of your landing page repo:

    auto-bml onboard
"""
import shutil
import subprocess
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests
from dotenv import dotenv_values

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "https://www.googleapis.com/auth/adwords"

SCAFFOLD_DIR = Path(__file__).parent.parent / "scaffold"
WORKFLOW_DIR = Path(__file__).parent.parent / "workflow_templates"

REQUIRED = [
    "GOOGLE_ADS_CUSTOMER_ID",
    "GOOGLE_ADS_DEVELOPER_TOKEN",
    "GOOGLE_ADS_CLIENT_ID",
    "GOOGLE_ADS_CLIENT_SECRET",
    "ANTHROPIC_API_KEY",
    "GITHUB_TOKEN",
]


def _detect_repo() -> str:
    """Infer owner/repo from git remote origin."""
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"], text=True
        ).strip()
        # https://github.com/owner/repo.git  or  git@github.com:owner/repo.git
        if url.startswith("https://"):
            parts = url.removesuffix(".git").split("/")
            return f"{parts[-2]}/{parts[-1]}"
        else:
            part = url.split(":")[-1].removesuffix(".git")
            return part
    except Exception:
        raise RuntimeError(
            "Could not detect GitHub repo from git remote. "
            "Run this command from the root of your landing page repo."
        )


def _run_oauth_flow(client_id: str, client_secret: str) -> str:
    auth_code: dict = {}

    class CallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            auth_code["code"] = params.get("code", [None])[0]
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"<h2>auto-bml: authorised. You can close this tab.</h2>")

        def log_message(self, *args):
            pass

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    print("Opening browser for Google authorisation...")
    webbrowser.open(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    HTTPServer(("localhost", 8080), CallbackHandler).handle_request()

    code = auth_code.get("code")
    if not code:
        raise RuntimeError("OAuth flow failed: no authorisation code received.")

    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    })
    resp.raise_for_status()
    return resp.json()["refresh_token"]


def _validate_connection(env: dict) -> None:
    resp = requests.post(GOOGLE_TOKEN_URL, data={
        "client_id": env["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": env["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": env["GOOGLE_ADS_REFRESH_TOKEN"],
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    access_token = resp.json()["access_token"]

    cid = env["GOOGLE_ADS_CUSTOMER_ID"].replace("-", "")
    api_resp = requests.post(
        f"https://googleads.googleapis.com/v17/customers/{cid}/googleAds:search",
        headers={
            "Authorization": f"Bearer {access_token}",
            "developer-token": env["GOOGLE_ADS_DEVELOPER_TOKEN"],
        },
        json={"query": "SELECT campaign.id FROM campaign LIMIT 1"},
    )
    if api_resp.status_code != 200:
        raise RuntimeError(
            f"Google Ads API returned {api_resp.status_code}. "
            "Check your developer token and customer ID."
        )


def _push_github_secrets(token: str, repo: str, secrets: dict) -> None:
    from nacl import encoding, public

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    key_data = requests.get(
        f"https://api.github.com/repos/{repo}/actions/secrets/public-key",
        headers=headers,
    ).json()
    pub_key = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder)

    for name, value in secrets.items():
        sealed = public.SealedBox(pub_key).encrypt(value.encode(), encoding.Base64Encoder)
        requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
            headers=headers,
            json={"encrypted_value": sealed.decode(), "key_id": key_data["key_id"]},
        ).raise_for_status()
        print(f"  ✓ {name}")


def _enable_github_pages(token: str, repo: str) -> str:
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.post(
        f"https://api.github.com/repos/{repo}/pages",
        headers=headers,
        json={"source": {"branch": "main", "path": "/docs"}},
    )
    if resp.status_code not in (201, 409):  # 409 = already enabled
        resp.raise_for_status()
    owner, name = repo.split("/")
    return f"https://{owner}.github.io/{name}"


def _scaffold(repo_path: Path) -> None:
    for f in ["pull.csv", "program.md"]:
        dest = repo_path / f
        if not dest.exists():
            shutil.copy(SCAFFOLD_DIR / f, dest)
            print(f"  ✓ {f}")

    bml_dir = repo_path / ".bml"
    bml_dir.mkdir(exist_ok=True)
    runs_file = bml_dir / "runs.json"
    if not runs_file.exists():
        runs_file.write_text("[]\n")
        print("  ✓ .bml/runs.json")

    workflows_dir = repo_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    for wf in ["bml-launch.yml", "bml-measure.yml"]:
        dest = workflows_dir / wf
        if not dest.exists():
            shutil.copy(WORKFLOW_DIR / wf, dest)
            print(f"  ✓ .github/workflows/{wf}")


def run() -> None:
    env_file = Path(".env")
    if not env_file.exists():
        raise SystemExit(
            "No .env file found. Copy .env.example to .env and fill in your credentials."
        )

    env = {**dotenv_values(env_file)}

    missing = [k for k in REQUIRED if not env.get(k)]
    if missing:
        raise SystemExit(f".env is missing required values: {', '.join(missing)}")

    if not env.get("CONVERSION_URL"):
        conversion_url = input(
            "Conversion URL — where should the landing page CTA send people?\n"
            "(e.g. https://yourapp.com/signup, or press Enter to leave as '#'): "
        ).strip()
        if conversion_url:
            env["CONVERSION_URL"] = conversion_url
            with env_file.open("a") as f:
                f.write(f"\nCONVERSION_URL={conversion_url}\n")
            print("  ✓ CONVERSION_URL saved to .env")

    repo = _detect_repo()
    print(f"Repo: {repo}")

    # OAuth flow if refresh token not already present
    if not env.get("GOOGLE_ADS_REFRESH_TOKEN"):
        env["GOOGLE_ADS_REFRESH_TOKEN"] = _run_oauth_flow(
            env["GOOGLE_ADS_CLIENT_ID"], env["GOOGLE_ADS_CLIENT_SECRET"]
        )
        lines = env_file.read_text().splitlines()
        with env_file.open("w") as f:
            for line in lines:
                if line.startswith("GOOGLE_ADS_REFRESH_TOKEN="):
                    f.write(f"GOOGLE_ADS_REFRESH_TOKEN={env['GOOGLE_ADS_REFRESH_TOKEN']}\n")
                else:
                    f.write(line + "\n")
        print("  ✓ Refresh token saved to .env")

    print("Validating Google Ads connection...")
    _validate_connection(env)
    print("  ✓ Connected")

    print(f"Pushing secrets to {repo}...")
    secrets = {k: env[k] for k in REQUIRED if k != "GITHUB_TOKEN"}
    secrets["GOOGLE_ADS_REFRESH_TOKEN"] = env["GOOGLE_ADS_REFRESH_TOKEN"]
    if env.get("CONVERSION_URL"):
        secrets["CONVERSION_URL"] = env["CONVERSION_URL"]
    _push_github_secrets(env["GITHUB_TOKEN"], repo, secrets)

    print("Enabling GitHub Pages...")
    pages_url = _enable_github_pages(env["GITHUB_TOKEN"], repo)
    print(f"  ✓ {pages_url}")

    print("Scaffolding repo files...")
    _scaffold(Path("."))

    print("\nDone.")
    print(f"Landing page (when lacking is active): {pages_url}/bml/")
    print("Next: fill in program.md and pull.csv, then trigger BML Launch in GitHub Actions.")
