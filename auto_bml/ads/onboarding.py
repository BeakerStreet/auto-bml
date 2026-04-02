"""
One-time Google Ads onboarding flow.
Run locally: auto-bml onboard --repo owner/repo
"""
import shutil
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = "https://www.googleapis.com/auth/adwords"

SCAFFOLD_DIR = Path(__file__).parent.parent.parent / "onboarding" / "scaffold"
WORKFLOW_DIR = Path(__file__).parent.parent.parent / "workflow-templates"


def _step(n: int, title: str) -> None:
    print(f"\n{'─' * 50}")
    print(f"  Step {n}: {title}")
    print(f"{'─' * 50}")


def _prompt(label: str, instructions: str = "") -> str:
    if instructions:
        print(f"\n{instructions}")
    value = input(f"{label}: ").strip()
    while not value:
        value = input(f"  (required) {label}: ").strip()
    return value


def _validate_customer_id(customer_id: str, developer_token: str, refresh_token: str, client_id: str, client_secret: str) -> bool:
    """Makes a lightweight API call to confirm credentials work together."""
    try:
        # Get access token
        resp = requests.post(GOOGLE_TOKEN_URL, data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        resp.raise_for_status()
        access_token = resp.json()["access_token"]

        # Try listing campaigns (empty result is fine — we just want a 200)
        cid = customer_id.replace("-", "")
        api_resp = requests.post(
            f"https://googleads.googleapis.com/v17/customers/{cid}/googleAds:search",
            headers={
                "Authorization": f"Bearer {access_token}",
                "developer-token": developer_token,
            },
            json={"query": "SELECT campaign.id FROM campaign LIMIT 1"},
        )
        return api_resp.status_code == 200
    except Exception:
        return False


def _run_oauth_flow(client_id: str, client_secret: str) -> str:
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
            pass

    params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "access_type": "offline",
        "prompt": "consent",
    }
    webbrowser.open(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    print("  Browser opened. Complete the Google sign-in and return here.")

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


def _push_github_secrets(token: str, repo: str, secrets: dict) -> None:
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
    pub_key = public.PublicKey(key_data["key"].encode(), encoding.Base64Encoder)

    for name, value in secrets.items():
        sealed = public.SealedBox(pub_key).encrypt(value.encode(), encoding.Base64Encoder)
        requests.put(
            f"https://api.github.com/repos/{repo}/actions/secrets/{name}",
            headers=headers,
            json={"encrypted_value": sealed.decode(), "key_id": key_data["key_id"]},
        ).raise_for_status()
        print(f"  ✓ {name}")


def _scaffold_repo(repo_path: Path, stripe_link: str, deploy_webhook: str) -> None:
    """Copy scaffold files into the user's repo."""
    # pull.csv and program.md
    for f in ["pull.csv", "program.md"]:
        dest = repo_path / f
        if not dest.exists():
            shutil.copy(SCAFFOLD_DIR / f, dest)
            print(f"  ✓ Created {f}")
        else:
            print(f"  — {f} already exists, skipping")

    # Write Stripe link and webhook into program.md
    program = (repo_path / "program.md").read_text()
    if "https://buy.stripe.com" not in program and stripe_link:
        with (repo_path / "program.md").open("a") as f:
            f.write(f"\n## Payment Link\n{stripe_link}\n")

    # .bml/runs.json
    bml_dir = repo_path / ".bml"
    bml_dir.mkdir(exist_ok=True)
    runs_file = bml_dir / "runs.json"
    if not runs_file.exists():
        runs_file.write_text("[]\n")
        print("  ✓ Created .bml/runs.json")

    # Workflow files
    workflows_dir = repo_path / ".github" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    for wf in ["bml-launch.yml", "bml-measure.yml"]:
        dest = workflows_dir / wf
        if not dest.exists():
            shutil.copy(WORKFLOW_DIR / wf, dest)
            print(f"  ✓ Created .github/workflows/{wf}")
        else:
            print(f"  — .github/workflows/{wf} already exists, skipping")


def run(repo: str, github_token: str) -> None:
    print("\n=== auto-bml onboarding ===")
    print("This will take about 15 minutes. You need:")
    print("  • An existing Google Ads account (with spend history)")
    print("  • A Google Cloud project with OAuth2 credentials")
    print("  • An Anthropic API key")
    print("  • A Stripe payment link for your product")
    print("  • Your deploy webhook URL (Vercel or Netlify)")

    # ── Step 1: Google Ads credentials ───────────────────────────────────────
    _step(1, "Google Ads credentials")
    print(
        "\n  Your Customer ID is the number in the top-right of your Google Ads account\n"
        "  (format: xxx-xxx-xxxx). Enter digits only."
    )
    customer_id = _prompt("Google Ads Customer ID (digits only)")
    customer_id = customer_id.replace("-", "")

    print(
        "\n  Your Developer Token is in Google Ads → Tools → API Center.\n"
        "  If you don't see API Center, you need Super Admin access on the account."
    )
    developer_token = _prompt("Developer token")

    # ── Step 2: OAuth2 ───────────────────────────────────────────────────────
    _step(2, "Google OAuth2 setup")
    print(
        "\n  You need a Google Cloud project with the Google Ads API enabled.\n"
        "  If you haven't done this:\n"
        "    1. Go to console.cloud.google.com\n"
        "    2. Create a project\n"
        "    3. Enable the Google Ads API\n"
        "    4. Go to APIs & Services → Credentials → Create OAuth 2.0 Client ID\n"
        "    5. Application type: Desktop app\n"
        "    6. Copy the Client ID and Client Secret below"
    )
    client_id = _prompt("OAuth2 Client ID")
    client_secret = _prompt("OAuth2 Client Secret")

    print("\n  Starting OAuth2 browser flow...")
    refresh_token = _run_oauth_flow(client_id, client_secret)
    print("  Authorization successful.")

    # ── Step 3: Validate credentials ─────────────────────────────────────────
    _step(3, "Validating credentials")
    print("  Testing Google Ads API connection...")
    if _validate_customer_id(customer_id, developer_token, refresh_token, client_id, client_secret):
        print("  ✓ Connected to Google Ads account successfully")
    else:
        print("  ✗ Could not connect. Check that your developer token has API access")
        print("    and that the Customer ID belongs to the account you just authorized.")
        raise SystemExit(1)

    # ── Step 4: Other credentials ─────────────────────────────────────────────
    _step(4, "Remaining credentials")
    anthropic_key = _prompt(
        "Anthropic API key",
        "  Get yours at console.anthropic.com → API Keys"
    )
    deploy_provider = _prompt(
        "Deploy provider",
        "  Which platform hosts your landing page? (vercel / netlify)"
    ).lower()
    deploy_webhook = _prompt(
        "Deploy webhook URL",
        "  Vercel: Project Settings → Git → Deploy Hooks\n"
        "  Netlify: Site Settings → Build & Deploy → Build Hooks"
    )
    stripe_link = _prompt(
        "Stripe payment link URL",
        "  Create one at dashboard.stripe.com → Payment Links.\n"
        "  This becomes the CTA on your landing page."
    )

    # ── Step 5: Push secrets to GitHub ───────────────────────────────────────
    _step(5, f"Pushing secrets to {repo}")
    _push_github_secrets(github_token, repo, {
        "ANTHROPIC_API_KEY": anthropic_key,
        "GOOGLE_ADS_DEVELOPER_TOKEN": developer_token,
        "GOOGLE_ADS_CLIENT_ID": client_id,
        "GOOGLE_ADS_CLIENT_SECRET": client_secret,
        "GOOGLE_ADS_REFRESH_TOKEN": refresh_token,
        "GOOGLE_ADS_CUSTOMER_ID": customer_id,
        "DEPLOY_PROVIDER": deploy_provider,
        "DEPLOY_WEBHOOK_URL": deploy_webhook,
    })

    # ── Step 6: Scaffold repo files ───────────────────────────────────────────
    _step(6, "Scaffolding repo files")
    repo_path = Path(".").resolve()
    _scaffold_repo(repo_path, stripe_link, deploy_webhook)

    print("\n" + "═" * 50)
    print("  Onboarding complete.")
    print("═" * 50)
    print("\n  Next steps:")
    print("  1. Fill in program.md — describe your startup and target customer")
    print("  2. Fill in the first row of pull.csv with your best current hypotheses")
    print("  3. Wire your landing page to read BML_HEADLINE, BML_SUBHEADLINE,")
    print("     BML_BODY, BML_CTA, BML_CTA_URL from environment variables")
    print("  4. Commit and push, then trigger 'BML Launch' from GitHub Actions")
    print()
