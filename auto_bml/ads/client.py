from google.ads.googleads.client import GoogleAdsClient

from ..config import Config


def get_client(config: Config) -> GoogleAdsClient:
    credentials = {
        "developer_token": config.google_ads_developer_token,
        "client_id": config.google_ads_client_id,
        "client_secret": config.google_ads_client_secret,
        "refresh_token": config.google_ads_refresh_token,
        "use_proto_plus": True,
    }
    return GoogleAdsClient.load_from_dict(credentials)
