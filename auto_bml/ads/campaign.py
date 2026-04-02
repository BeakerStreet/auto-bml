from datetime import date

from google.ads.googleads.client import GoogleAdsClient

from ..config import Config
from ..models import AdCopy


def create_experiment_campaign(
    client: GoogleAdsClient,
    config: Config,
    run_id: str,
    copy: AdCopy,
) -> str:
    """
    Creates a Search campaign + ad group + responsive search ad for one BML run.
    Returns the campaign resource name.
    """
    customer_id = config.google_ads_customer_id
    campaign_name = f"auto-bml-{run_id}-{date.today().isoformat()}"

    # --- Budget ---
    budget_service = client.get_service("CampaignBudgetService")
    budget_op = client.get_type("CampaignBudgetOperation")
    budget = budget_op.create
    budget.name = f"{campaign_name}-budget"
    budget.amount_micros = int(config.daily_budget_usd * 1_000_000)
    budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD

    budget_response = budget_service.mutate_campaign_budgets(
        customer_id=customer_id, operations=[budget_op]
    )
    budget_resource = budget_response.results[0].resource_name

    # --- Campaign ---
    campaign_service = client.get_service("CampaignService")
    campaign_op = client.get_type("CampaignOperation")
    campaign = campaign_op.create
    campaign.name = campaign_name
    campaign.advertising_channel_type = (
        client.enums.AdvertisingChannelTypeEnum.SEARCH
    )
    campaign.status = client.enums.CampaignStatusEnum.ENABLED
    campaign.campaign_budget = budget_resource
    campaign.manual_cpc.enhanced_cpc_enabled = True
    campaign.network_settings.target_google_search = True
    campaign.network_settings.target_search_network = True

    campaign_response = campaign_service.mutate_campaigns(
        customer_id=customer_id, operations=[campaign_op]
    )
    campaign_resource = campaign_response.results[0].resource_name

    # --- Ad Group ---
    ad_group_service = client.get_service("AdGroupService")
    ag_op = client.get_type("AdGroupOperation")
    ad_group = ag_op.create
    ad_group.name = f"{campaign_name}-adgroup"
    ad_group.campaign = campaign_resource
    ad_group.status = client.enums.AdGroupStatusEnum.ENABLED
    ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
    ad_group.cpc_bid_micros = 2_000_000  # $2.00 default; auto-adjusts

    ag_response = ad_group_service.mutate_ad_groups(
        customer_id=customer_id, operations=[ag_op]
    )
    ag_resource = ag_response.results[0].resource_name

    # --- Keywords ---
    kw_service = client.get_service("AdGroupCriterionService")
    kw_ops = []
    for kw in copy.keywords[:20]:
        kw_op = client.get_type("AdGroupCriterionOperation")
        criterion = kw_op.create
        criterion.ad_group = ag_resource
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.keyword.text = kw
        criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum.PHRASE
        kw_ops.append(kw_op)

    if kw_ops:
        kw_service.mutate_ad_group_criteria(
            customer_id=customer_id, operations=kw_ops
        )

    # --- Responsive Search Ad ---
    ad_service = client.get_service("AdGroupAdService")
    ad_op = client.get_type("AdGroupAdOperation")
    ad_group_ad = ad_op.create
    ad_group_ad.ad_group = ag_resource
    ad_group_ad.status = client.enums.AdGroupAdStatusEnum.ENABLED

    rsa = ad_group_ad.ad.responsive_search_ad
    for headline_text in copy.ad_headlines[:5]:
        headline = client.get_type("AdTextAsset")
        headline.text = headline_text[:30]
        rsa.headlines.append(headline)
    for desc_text in copy.ad_descriptions[:4]:
        desc = client.get_type("AdTextAsset")
        desc.text = desc_text[:90]
        rsa.descriptions.append(desc)

    ad_service.mutate_ad_group_ads(customer_id=customer_id, operations=[ad_op])

    return campaign_resource


def pause_campaign(client: GoogleAdsClient, customer_id: str, campaign_resource: str) -> None:
    campaign_service = client.get_service("CampaignService")
    op = client.get_type("CampaignOperation")
    campaign = op.update
    campaign.resource_name = campaign_resource
    campaign.status = client.enums.CampaignStatusEnum.PAUSED
    client.copy_from(op.update_mask, protobuf_helpers.field_mask(None, campaign._pb))
    campaign_service.mutate_campaigns(customer_id=customer_id, operations=[op])
