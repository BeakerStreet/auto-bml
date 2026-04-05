import os
from dataclasses import dataclass


@dataclass
class Config:
    anthropic_api_key: str
    google_ads_developer_token: str
    google_ads_client_id: str
    google_ads_client_secret: str
    google_ads_refresh_token: str
    google_ads_customer_id: str
    github_token: str
    github_repository: str
    daily_budget_usd: float
    conversion_url: str = "#"


def load() -> Config:
    required = [
        "ANTHROPIC_API_KEY",
        "GOOGLE_ADS_DEVELOPER_TOKEN",
        "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET",
        "GOOGLE_ADS_REFRESH_TOKEN",
        "GOOGLE_ADS_CUSTOMER_ID",
        "GITHUB_TOKEN",
        "GITHUB_REPOSITORY",
    ]
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
        github_token=os.environ["GITHUB_TOKEN"],
        github_repository=os.environ["GITHUB_REPOSITORY"],
        daily_budget_usd=float(os.getenv("DAILY_BUDGET_USD", "20")),
        conversion_url=os.getenv("CONVERSION_URL", "#"),
    )
