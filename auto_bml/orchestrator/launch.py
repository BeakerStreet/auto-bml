"""
Launch phase: generate copy → deploy → create Google Ads campaign → store run metadata.
"""
import sys

from .. import config as cfg
from .. import pull_io, run_store, copywriter, deployer
from ..ads import client as ads_client, campaign as ads_campaign
from ..models import RunMetadata, RunStatus


def run() -> None:
    config = cfg.load()

    # Warn if a run is already in progress
    runs = run_store.load()
    active = [r for r in runs if r.status == RunStatus.running]
    if active:
        print(f"Warning: {len(active)} run(s) already in progress. Proceeding anyway.")

    hypothesis = pull_io.read_hypothesis()
    program = pull_io.read_program()

    if not any([hypothesis.project, hypothesis.urgency, hypothesis.look, hypothesis.lacking]):
        print("Error: pull.csv has no hypothesis. Fill in at least one variable.")
        sys.exit(1)

    print("Generating landing page copy...")
    copy = copywriter.generate(hypothesis, program, config.anthropic_api_key)
    print(f"  Headline: {copy.headline}")
    print(f"  Keywords: {', '.join(copy.keywords[:5])}...")

    print("Deploying landing page...")
    provider = deployer.get_provider(config.deploy_provider, config.deploy_webhook_url)
    deploy_url = provider.deploy(copy)
    print(f"  Deployed: {deploy_url}")

    print("Creating Google Ads campaign...")
    client = ads_client.get_client(config)
    run = RunMetadata(pull_snapshot=hypothesis)
    campaign_resource = ads_campaign.create_experiment_campaign(
        client, config, run.run_id, copy
    )
    run.campaign_id = campaign_resource
    run.deploy_url = deploy_url

    run_store.append(run)
    print(f"Run {run.run_id} launched. Metrics will be collected in 6 hours.")
