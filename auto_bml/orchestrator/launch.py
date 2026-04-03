"""
Launch: read active variable from state → generate appropriate copy
→ deploy if lacking → create Google Ads campaign → store run metadata.
"""
import sys

from .. import config as cfg
from .. import pull_io, run_store, copywriter, deployer
from ..ads import client as ads_client, campaign as ads_campaign
from ..models import AdCopy, RunMetadata, RunStatus


def run() -> None:
    config = cfg.load()

    runs = run_store.load()
    active = [r for r in runs if r.status == RunStatus.running]
    if active:
        print(f"Warning: {len(active)} run(s) already in progress. Proceeding anyway.")

    hypothesis = pull_io.read_hypothesis()
    program = pull_io.read_program()
    stripe_link = pull_io.read_stripe_link()
    state = run_store.load_state()

    if not any([hypothesis.project, hypothesis.urgency, hypothesis.look, hypothesis.lacking]):
        print("Error: pull.csv has no hypothesis. Fill in at least one variable.")
        sys.exit(1)

    print(f"Active variable: {state.active_variable}")
    if state.uses_landing_page():
        print("Mode: landing page iteration (lacking)")
    else:
        print("Mode: ad copy iteration")
    if state.locked:
        print(f"Locked: {', '.join(state.locked.keys())}")

    client = ads_client.get_client(config)
    run = RunMetadata(active_variable=state.active_variable, pull_snapshot=hypothesis)

    if state.uses_landing_page():
        print("Generating landing page copy...")
        page_copy = copywriter.generate_page_copy(hypothesis, program, config.anthropic_api_key)
        print(f"  Headline: {page_copy.headline}")

        print("Deploying landing page...")
        provider = deployer.get_provider(config)
        deploy_url = provider.deploy(page_copy, stripe_link)
        run.deploy_url = deploy_url
        print(f"  Deployed: {deploy_url}")

        # Minimal ad to drive traffic to the page; keywords from locked look variable
        look_value = state.locked.get("look") or hypothesis.look or "solution"
        ad_copy = AdCopy(
            ad_headlines=["Finally, what you need", "Stop settling for less", "Built for your workflow"],
            ad_descriptions=["Stop settling for tools that almost work.", "The gap is finally filled."],
            keywords=[look_value],
        )
    else:
        print(f"Generating ad copy (active: {state.active_variable})...")
        ad_copy = copywriter.generate_ad_copy(hypothesis, state, program, config.anthropic_api_key)
        print(f"  Keywords: {', '.join(ad_copy.keywords[:5])}...")

    print("Creating Google Ads campaign...")
    campaign_resource = ads_campaign.create_experiment_campaign(
        client, config, run.run_id, ad_copy
    )
    run.campaign_id = campaign_resource

    run_store.append(run)
    print(f"Run {run.run_id} launched. Metrics collected in 6 hours.")
