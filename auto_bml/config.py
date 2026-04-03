import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    anthropic_api_key: str
    google_ads_developer_token: str
    google_ads_client_id: str
    google_ads_client_secret: str
    google_ads_refresh_token: str
    google_ads_customer_id: str
    deploy_provider: str
    deploy_webhook_url: str
    deploy_site_url: str
    github_token: str
    daily_budget_usd: float
    vercel_api_token: Optional[str] = None
    vercel_project_id: Optional[str] = None


def load() -> Config:
    provider = os.getenv("DEPLOY_PROVIDER", "").lower()
    required = [
        "ANTHROPIC_API_KEY",
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET",
        "GOOGLE_ADS_REFRESH_TOKEN",
        "GOOGLE_ADS_CUSTOMER_ID",
        "DEPLOY_PROVIDER",
        "DEPLOY_WEBHOOK_URL",
        "DEPLOY_SITE_URL",
        "GITHUB_TOKEN",
    ]
    if provider == "vercel":
        required += ["VERCEL_API_TOKEN", "VERCEL_PROJECT_ID"]

    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise EnvironmentError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        google_ads_developer_token=os.environ["GOOGLE_ADS_DEVELOPER_TOKEN"],
        google_ads_client_id=os.environ["GOOGLE_ADS_CLIENT_ID"],
        google_ads_client_secret=os.environ["GOOGLE_ADS_CLIENT_SECRET"],
        google_ads_refresh_token=os.environ["GOOGLE_ADS_REFRESH_TOKEN"],
        google_ads_customer_id=os.environ["GOOGLE_ADS_CUSTOMER_ID"],
        deploy_provider=os.environ["DEPLOY_PROVIDER"],
        deploy_webhook_url=os.environ["DEPLOY_WEBHOOK_URL"],
        deploy_site_url=os.environ["DEPLOY_SITE_URL"],
        github_token=os.environ["GITHUB_TOKEN"],
        daily_budget_usd=float(os.getenv("DAILY_BUDGET_USD", "20")),
        vercel_api_token=os.getenv("VERCEL_API_TOKEN"),
        vercel_project_id=os.getenv("VERCEL_PROJECT_ID"),
    )
