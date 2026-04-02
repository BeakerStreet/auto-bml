from datetime import date, timedelta

from google.ads.googleads.client import GoogleAdsClient

from ..models import AdsMetrics


def fetch(
    client: GoogleAdsClient,
    customer_id: str,
    campaign_resource: str,
    started_at: date,
) -> AdsMetrics:
    """
    Pulls 6-hour window metrics for a campaign via GAQL.
    Uses today's date range since campaigns run same-day.
    """
    ga_service = client.get_service("GoogleAdsService")
    today = date.today().isoformat()
    yesterday = (date.today() - timedelta(days=1)).isoformat()

    # Extract campaign ID from resource name (customers/CID/campaigns/CAMPAIGN_ID)
    campaign_id = campaign_resource.split("/")[-1]

    query = f"""
        SELECT
            metrics.impressions,
            metrics.clicks,
            metrics.average_cpc,
            metrics.conversions,
            campaign_criterion.keyword.text
        FROM campaign
        WHERE campaign.id = {campaign_id}
          AND segments.date BETWEEN '{yesterday}' AND '{today}'
    """

    response = ga_service.search(customer_id=customer_id, query=query)

    impressions = 0
    clicks = 0
    average_cpc_micros = 0
    conversions = 0.0
    rows = 0

    for row in response:
        m = row.metrics
        impressions += m.impressions
        clicks += m.clicks
        average_cpc_micros += int(m.average_cpc)
        conversions += m.conversions
        rows += 1

    if rows > 0:
        average_cpc_micros = average_cpc_micros // rows

    # Competition index: approximate from CPC relative to typical range ($0.50–$10)
    cpc_usd = average_cpc_micros / 1_000_000
    competition_index = min(1.0, max(0.0, (cpc_usd - 0.5) / 9.5))

    return AdsMetrics(
        impressions=impressions,
        clicks=clicks,
        average_cpc_micros=average_cpc_micros,
        conversions=conversions,
        competition_index=competition_index,
    )
